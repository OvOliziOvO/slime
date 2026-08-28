import sys
import os
import threading
import time
import glob
import gc
import json
import ctypes
import re
import math
import atexit
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QSize, QPropertyAnimation, QPointF, QUrl
from PyQt6.QtGui import QPixmap, QPixmapCache, QKeySequence, QShortcut, QImage, QPainter, QColor, QPen, QAction, QIcon, QPainterPath, QPolygonF, QFont, QDesktopServices

try:
    from litemapy import Schematic, Region, BlockState
    HAS_LITEMAPY = True
except ImportError:
    # Keep the app importable so export_proj() can show its friendly warning.
    HAS_LITEMAPY = False
    Schematic = BlockState = None
    Region = object

FILTER_MUSHROOM_ISLAND = True
APP_VERSION = "V1"
MAX_CANDIDATE_BUFFER = 3_000_000
MAX_SEARCH_RADIUS = (2_147_483_647 - 17) // 2
WORLD_BORDER_RADIUS_CHUNKS = 1_875_000
DEFAULT_MC_VERSION = "1.21.11"
SUPPORTED_MC_VERSIONS = (
    "1.19", "1.20", "1.21.1", "1.21.3", "1.21.4",
    "1.21.5", "1.21.6", "1.21.9", "1.21.11", "26.1", "26.2",
)
CUBIOMES_GENERATOR_BUFFER_SIZE = 256 * 1024
CUBIOMES_DOWNLOAD_URL = "https://github.com/OvOliziOvO/slime/raw/refs/heads/main/downloads/cubiomes_latest_26.2.zip"
Y_PACK_SHIFT = 20
Y_PACK_MASK = (1 << Y_PACK_SHIFT) - 1
Y_PACK_BIAS = 1024
DEFAULT_RESULT_LIMIT = 50
MAX_RESULT_LIMIT = 1000

# ===== 投影 =====
PROJECTION_MAX_SIZE = 1024
SPAWN_INNER_RADIUS = 24
SPAWN_OUTER_RADIUS = 128
SPAWN_INNER_SQ = SPAWN_INNER_RADIUS * SPAWN_INNER_RADIUS
SPAWN_OUTER_SQ = SPAWN_OUTER_RADIUS * SPAWN_OUTER_RADIUS

def is_spawnable_floor_block(
        afk_x, afk_z, block_x, block_z, is_slime_chunk_at,
        afk_y=-64, platform_y=-64):
    dy = int(platform_y) - int(afk_y)
    dist_sq = (
        (int(block_x) - int(afk_x)) ** 2
        + (int(block_z) - int(afk_z)) ** 2
        + dy * dy
    )
    if dist_sq <= SPAWN_INNER_SQ or dist_sq > SPAWN_OUTER_SQ:
        return False
    return bool(is_slime_chunk_at(int(block_x) >> 4, int(block_z) >> 4))

def build_floor_distance_field(
        afk_x, afk_z, width, length, is_slime_chunk_at, distance_limit=4,
        afk_y=-64, platform_y=-64):
    width = int(width)
    length = int(length)
    origin_x = -(width // 2)
    origin_z = -(length // 2)
    start_x = int(afk_x) + origin_x
    start_z = int(afk_z) + origin_z
    distance_field = bytearray([distance_limit] * (width * length))

    for x in range(width):
        wx = start_x + x
        row_offset = x * length
        for z in range(length):
            if is_spawnable_floor_block(
                    afk_x, afk_z, wx, start_z + z, is_slime_chunk_at,
                    afk_y=afk_y, platform_y=platform_y):
                distance_field[row_offset + z] = 0

    for x in range(width):
        row_offset = x * length
        prev_row_offset = (x - 1) * length
        for z in range(length):
            idx = row_offset + z
            val = distance_field[idx]
            if x > 0:
                val = min(val, distance_field[prev_row_offset + z] + 1)
                if z > 0:
                    val = min(val, distance_field[prev_row_offset + z - 1] + 1)
                if z + 1 < length:
                    val = min(val, distance_field[prev_row_offset + z + 1] + 1)
            if z > 0:
                val = min(val, distance_field[idx - 1] + 1)
            distance_field[idx] = min(val, distance_limit)

    for x in range(width - 1, -1, -1):
        row_offset = x * length
        next_row_offset = (x + 1) * length
        for z in range(length - 1, -1, -1):
            idx = row_offset + z
            val = distance_field[idx]
            if x + 1 < width:
                val = min(val, distance_field[next_row_offset + z] + 1)
                if z > 0:
                    val = min(val, distance_field[next_row_offset + z - 1] + 1)
                if z + 1 < length:
                    val = min(val, distance_field[next_row_offset + z + 1] + 1)
            if z + 1 < length:
                val = min(val, distance_field[idx + 1] + 1)
            distance_field[idx] = min(val, distance_limit)

    return origin_x, origin_z, start_x, start_z, distance_field

def floor_distance_at(distance_field, width, length, start_x, start_z, wx, wz, distance_limit=4):
    x = int(wx) - int(start_x)
    z = int(wz) - int(start_z)
    if x < 0 or x >= width or z < 0 or z >= length:
        return distance_limit
    return distance_field[x * length + z]

def is_floor_portal_position(wx, wz, distance, enabled, axis_x):
    if not enabled or distance != 0:
        return False
    cx, cz = int(wx) % 16, int(wz) % 16
    if axis_x:
        return (cx + (cz % 2) * 2) % 4 == 2
    return (cz + (cx % 2) * 2) % 4 == 2

def is_floor_bait_position(distance_field, width, length, start_x, start_z, wx, wz, enabled):
    if not enabled or floor_distance_at(distance_field, width, length, start_x, start_z, wx, wz) != 3:
        return False
    distance = lambda x, z: floor_distance_at(
        distance_field, width, length, start_x, start_z, x, z)
    return (
        (int(wx) % 16 == 7 and (distance(wx, wz - 3) == 0 or distance(wx, wz + 3) == 0))
        or (int(wz) % 16 == 7 and (distance(wx - 3, wz) == 0 or distance(wx + 3, wz) == 0))
    )

def ensure_litematic_extension(path):
    path = str(path)
    return path if path.lower().endswith(".litematic") else path + ".litematic"

def validate_projection_dimensions(width, length):
    try:
        width, length = int(width), int(length)
    except (TypeError, ValueError):
        raise ValueError("总宽度和总长度必须是整数。")
    if width < 16 or length < 16:
        raise ValueError("总宽度和总长度必须至少为 16。")
    if width > PROJECTION_MAX_SIZE or length > PROJECTION_MAX_SIZE:
        raise ValueError(f"尺寸过大，最大支持 {PROJECTION_MAX_SIZE} x {PROJECTION_MAX_SIZE}。")
    return width, length

def create_slime_floor_schematic(
        active_seed, afk_x, afk_z, width, length, floor_block_id,
        use_magma=True, use_wither=True, use_rod=True,
        use_portal_array=True, portal_axis_x=True,
        wither_base_soul=False, slime_chunk_at=None,
        afk_y=-64, platform_y=-64):
    if not HAS_LITEMAPY:
        raise RuntimeError("需要安装环境 litemapy")
    width, length = int(width), int(length)
    origin_x, origin_z = -(width // 2), -(length // 2)
    region_height = 3 if use_rod else (2 if use_wither else 1)
    floor = Region(origin_x, 0, origin_z, width, 1, length)
    portal = Region(origin_x, 1, origin_z, width, region_height, length)
    schem = Schematic(
        name="SlimePerimeter", author="li_zi_O_O",
        regions={"floor": floor, "portal": portal})

    obsidian = BlockState("minecraft:obsidian")
    magma = BlockState("minecraft:magma_block")
    floor_block = BlockState(floor_block_id)
    center_marker = BlockState("minecraft:composter", level="0")
    soul_sand = BlockState("minecraft:soul_sand")
    wither_rose = BlockState("minecraft:wither_rose")
    turtle_egg = BlockState("minecraft:turtle_egg", eggs="1")
    portal_block = BlockState("minecraft:nether_portal", axis="x" if portal_axis_x else "z")
    lightning_rod = BlockState("minecraft:lightning_rod")

    chunk_cache = {}
    slime_test = slime_chunk_at or (lambda cx, cz: is_slime_chunk(active_seed, cx, cz))
    def is_slime_cached(cx, cz):
        key = (int(cx), int(cz))
        if key not in chunk_cache:
            chunk_cache[key] = bool(slime_test(*key))
        return chunk_cache[key]

    _, _, start_x, start_z, distance_field = build_floor_distance_field(
        afk_x, afk_z, width, length, is_slime_cached,
        afk_y=afk_y, platform_y=platform_y)

    for x in range(width):
        wx = start_x + x
        for z in range(length):
            wz = start_z + z
            if wx == afk_x and wz == afk_z:
                floor[(x, 0, z)] = center_marker
                if use_rod:
                    portal[(x, 2, z)] = lightning_rod
                continue
            distance = distance_field[x * length + z]
            if distance == 0:
                floor[(x, 0, z)] = obsidian
                if is_floor_portal_position(
                        wx, wz, distance, use_portal_array, portal_axis_x):
                    portal[(x, 0, z)] = portal_block
            elif distance == 1:
                floor[(x, 0, z)] = magma if use_magma else floor_block
            elif distance == 2:
                floor[(x, 0, z)] = floor_block
            elif is_floor_bait_position(
                    distance_field, width, length, start_x, start_z,
                    wx, wz, use_wither):
                floor[(x, 0, z)] = soul_sand if wither_base_soul else floor_block
                portal[(x, 0, z)] = wither_rose
                portal[(x, 1, z)] = turtle_egg
            else:
                floor[(x, 0, z)] = floor_block
    return schem

# ===== 精准评分 =====
# 128 格范围与史莱姆聚类圆不是同一套几何，外围区块也必须参与评分。
SPAWNABLE_CHUNK_REL_OFFSETS = tuple(
    (dcx, dcz)
    for dcx in range(-8, 9)
    for dcz in range(-8, 9)
)

def build_spawnable_overlap_table():
    table = {}
    inner_sq = 24 * 24
    outer_sq = 128 * 128
    for local_x in range(16):
        for local_z in range(16):
            entries = []
            for dcx, dcz in SPAWNABLE_CHUNK_REL_OFFSETS:
                block_count = 0
                base_dx = dcx * 16 - local_x
                base_dz = dcz * 16 - local_z
                for bx in range(16):
                    dx = base_dx + bx
                    dx_sq = dx * dx
                    for bz in range(16):
                        dz = base_dz + bz
                        dist_sq = dx_sq + dz * dz
                        if inner_sq < dist_sq <= outer_sq:
                            block_count += 1
                if block_count:
                    entries.append((dcx, dcz, block_count))
            table[(local_x, local_z)] = tuple(entries)
    return table

SPAWNABLE_CHUNK_OVERLAP = build_spawnable_overlap_table()

# 严格上界，只用于安全剪枝。
PRECISE_SPAWN_SAFE_BOUND = (
    3701,3957,4213,4469,4725,4981,5237,5493,5749,6005,6261,6517,6773,7029,7285,7541,
    7797,8053,8309,8565,8821,9077,9333,9589,9845,10101,10357,10613,10869,11125,11381,
    11637,11893,12149,12405,12661,12917,13173,13429,13685,13941,14197,14453,14709,
    14965,15221,15477,15733,15989,16245,16501,16757,17013,17269,17525,17781,18037,
    18293,18549,18805,19061,19317,19573,19829,20085,20341,20597,20853,21109,21365,
    21621,21877,22133,22389,22645,22901,23157,23413,23669,23925,24181,24437,24693,
    24949,25205,25461,25717,25973,26229,26485,26741,26997,27253,27509,27765,28021,
    28277,28533,28789,29045,29301,29557,29813,30069,30325,30581,30837,31093,31349,
    31605,31861,32117,32373,32629,32885,33141,33397,33653,33909,34165,34421,34677,
    34933,35189,35445,35701,35957,36213,36469,36725,36981,37237,37493,37749,38005,
    38261,38517,38773,39029,39285,39541,39797,40053,40309,40565,40821,41077,41333,
    41589,41845,42101,42357,42613,42869,43125,43381,43637,43893,44149,44405,44661,
    44917,45172,45427,45660,45893,46119,46345,46566,46787,46972,47157,47340,47523,
    47694,47865,47997,48115,48233,48346,48459,48564,48669,48772,48875,48978,49079,
    49180,49275,49370,49425,49480,49531,49582,49600,49618,49626,49629,49632,49634,
    49636,49637,49640,49640,49640,49640,49640,49640,49640,49640,49640,49640,49640,
    49640,49640,49640,49640,49640,49640,49640,49640,49640,
)

# 扫描 Y 时使用独立的严格上界。
PRECISE_Y_SPAWN_SAFE_BOUND = PRECISE_SPAWN_SAFE_BOUND[:182] + (
    48694,48833,48929,49025,49100,49180,49275,49370,49425,49480,
    49531,49593,49620,49647,49671,49695,49696,49696,49696,49696,
    49696,49696,49696,49696,49696,49696,49696,49696,49696,49696,
    49696,49696,49696,49696,49696,49696,49696,49696,49696,49696,
)

def clamp_int(value, default, min_value, max_value):
    try:
        value = int(value)
    except Exception:
        value = int(default)
    return max(int(min_value), min(int(value), int(max_value)))


def format_elapsed(seconds):
    try:
        seconds = max(0.0, float(seconds))
    except Exception:
        seconds = 0.0
    if seconds < 10:
        return f"{seconds:.2f}秒"
    if seconds < 60:
        return f"{seconds:.1f}秒"
    whole = int(round(seconds))
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}小时{m:02d}分{s:02d}秒"
    return f"{m:d}分{s:02d}秒"

def precise_eval_target_pool(has_biome_filter=False, config=None):
    result_limit = clamp_int(
        getattr(config, "result_limit", DEFAULT_RESULT_LIMIT) if config is not None else DEFAULT_RESULT_LIMIT,
        DEFAULT_RESULT_LIMIT, 1, MAX_RESULT_LIMIT)
    default_pool = result_limit * (40 if has_biome_filter else 4)
    configured = getattr(config, "precise_target_pool", 0) if config is not None else 0
    if configured:
        value = configured
    else:
        try:
            value = int(os.environ.get("SLIME_PRECISE_TARGET_POOL", str(default_pool)))
        except Exception:
            value = default_pool
    return max(result_limit, min(int(value), 20000))

def precise_exhaustive_enabled(config=None):
    if bool(getattr(config, "precise_exhaustive", False)):
        return True
    value = os.environ.get("SLIME_PRECISE_EXHAUSTIVE", "0").strip().lower()
    return value in ("1", "true", "yes", "on", "all")

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

if getattr(sys, 'frozen', False):
    RESOURCE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
    PACKAGE_DIR = APP_DIR
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    PACKAGE_DIR = os.path.dirname(RESOURCE_DIR) if os.path.basename(RESOURCE_DIR).lower() == "app" else RESOURCE_DIR
    APP_DIR = PACKAGE_DIR

# ===== 资源与原生 DLL =====
RESOURCE_SEARCH_DIRS = [
    RESOURCE_DIR,
    APP_DIR,
    PACKAGE_DIR,
    os.path.join(PACKAGE_DIR, "release"),
    os.path.join(PACKAGE_DIR, "runtime"),
    os.path.join(PACKAGE_DIR, "native", "cpu"),
    os.path.join(PACKAGE_DIR, "native", "gpu"),
    os.path.join(PACKAGE_DIR, "app"),
]


def _unique_existing_dirs(paths):
    out = []
    seen = set()
    for p in paths:
        if not p:
            continue
        try:
            p = os.path.abspath(p)
        except Exception:
            continue
        key = os.path.normcase(p)
        if key in seen:
            continue
        seen.add(key)
        if os.path.isdir(p):
            out.append(p)
    return out

RESOURCE_SEARCH_DIRS = _unique_existing_dirs(RESOURCE_SEARCH_DIRS)

def find_resource(filename):
    for base_dir in RESOURCE_SEARCH_DIRS:
        path = os.path.join(base_dir, filename)
        if os.path.exists(path):
            return path
    return os.path.join(APP_DIR, filename)

def searched_dirs_text(limit=10):
    dirs = RESOURCE_SEARCH_DIRS[:limit]
    text = "; ".join(dirs)
    if len(RESOURCE_SEARCH_DIRS) > limit:
        text += "；另有 {} 个目录".format(len(RESOURCE_SEARCH_DIRS) - limit)
    return text

_DLL_DIR_HANDLES = []
_REGISTERED_DLL_DIRS = set()

_PE_MACHINE_NAMES = {
    0x014c: "x86/32位",
    0x8664: "x64/64位",
    0x01c0: "ARM",
    0xaa64: "ARM64",
}

def _python_arch_text():
    return "x64/64位" if sys.maxsize > 2 ** 32 else "x86/32位"

def _describe_pe_arch(path):
    try:
        with open(path, "rb") as f:
            mz = f.read(2)
            if mz != b"MZ":
                return "不是 Windows PE DLL"
            f.seek(0x3C)
            pe_offset = int.from_bytes(f.read(4), "little", signed=False)
            f.seek(pe_offset)
            if f.read(4) != b"PE\0\0":
                return "PE 头异常"
            machine = int.from_bytes(f.read(2), "little", signed=False)
            return _PE_MACHINE_NAMES.get(machine, "未知架构 0x{:04X}".format(machine))
    except Exception as e:
        return "无法读取架构: {}".format(e)

def _register_dll_directory(dir_path):
    if not dir_path or not os.path.isdir(dir_path):
        return
    dir_path = os.path.abspath(dir_path)
    key = os.path.normcase(dir_path)
    if key in _REGISTERED_DLL_DIRS:
        return
    _REGISTERED_DLL_DIRS.add(key)
    if hasattr(os, "add_dll_directory"):
        _DLL_DIR_HANDLES.append(os.add_dll_directory(dir_path))

for _dll_dir in RESOURCE_SEARCH_DIRS:
    _register_dll_directory(_dll_dir)


def _ctypes_load(path):
    if sys.platform.startswith("win"):
        try:
            return ctypes.CDLL(path, winmode=0x00000100 | 0x00001000)
        except TypeError:
            return ctypes.CDLL(path)
    return ctypes.CDLL(path)

def _format_native_load_error(path, errors):
    info = []
    info.append("文件: {}".format(path))
    info.append("存在: {}".format("是" if os.path.exists(path) else "否"))
    if os.path.exists(path):
        try:
            info.append("大小: {} 字节".format(os.path.getsize(path)))
        except Exception:
            pass
        info.append("DLL架构: {}".format(_describe_pe_arch(path)))
    info.append("Python架构: {}".format(_python_arch_text()))
    info.append("搜索目录: {}".format(searched_dirs_text()))
    if errors:
        info.append("加载尝试:")
        info.extend("- " + str(e) for e in errors[-8:])
    info.append("提示: 这个报错通常不是 cubiomes.dll 本体不存在，而是它依赖的 DLL 缺失或 DLL 架构不匹配。")
    info.append("如果仍失败，把 cubiomes.dll 同目录下的 libgcc_s_seh-1.dll、libstdc++-6.dll、libwinpthread-1.dll 一起放到程序目录。")
    return "\n".join(info)

def load_native_library(path):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise OSError("文件不存在: {}".format(path))

    dll_dir = os.path.dirname(path)
    for d in [dll_dir] + RESOURCE_SEARCH_DIRS:
        _register_dll_directory(d)
    try:
        return _ctypes_load(path)
    except Exception as e:
        raise OSError(_format_native_load_error(path, [f"{type(e).__name__}: {e}"])) from e

class CubiomesPos(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int32), ("z", ctypes.c_int32)]

DLL_PATH = find_resource("cubiomes.dll")
cb = None
DLL_ERROR_MSG = ""
if not os.path.exists(DLL_PATH):
    DLL_ERROR_MSG = f"未找到文件: cubiomes.dll；已搜索：{searched_dirs_text()}"
else:
    try:
        cb = load_native_library(DLL_PATH)
        cb.setupGenerator.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
        cb.applySeed.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint64]
        cb.getBiomeAt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        cb.getBiomeAt.restype = ctypes.c_int
        if hasattr(cb, "str2mc"):
            cb.str2mc.argtypes = [ctypes.c_char_p]
            cb.str2mc.restype = ctypes.c_int
        if hasattr(cb, "mc2str"):
            cb.mc2str.argtypes = [ctypes.c_int]
            cb.mc2str.restype = ctypes.c_char_p
        if hasattr(cb, "getSpawn"):
            cb.getSpawn.argtypes = [ctypes.c_void_p]
            cb.getSpawn.restype = CubiomesPos
    except Exception as e:
        DLL_ERROR_MSG = f"加载失败: {DLL_PATH}\n{type(e).__name__}: {e}"
        cb = None

class ExtChunkResult(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_int32), ("center_x", ctypes.c_int32), ("center_z", ctypes.c_int32),
        ("obs_count", ctypes.c_int32), ("afk_x", ctypes.c_int32), ("afk_z", ctypes.c_int32)
    ]

GPU_AVAILABLE = False
GPU_STATUS_MSG = "GPU 算法未检测。"
GPU_DEVICE_COUNT = 0
GPU_DEVICE_NAME = "NVIDIA GPU"
GPU_V1_ALGORITHM = "V1 GPU 方形滚动 + 角落差分精确圆形 + 全局 Top-K"

def cpu_algorithm_available():
    return sc_cpu_lib is not None

def gpu_algorithm_available():
    return bool(sc_gpu_lib and GPU_AVAILABLE)

def is_gpu_engine(choice):
    return choice == "GPU (CUDA)"

def resolve_engine_choice(choice):
    """Map UI selection to an actual engine. Python is hidden from the UI, but
    remains as the emergency fallback when neither native algorithm is usable.
    """
    choice = (choice or "Auto").strip()
    if choice == "GPU (CUDA)" and gpu_algorithm_available():
        return "GPU (CUDA)", GPU_STATUS_MSG
    if choice == "CPU (AVX2/OpenMP)" and cpu_algorithm_available():
        return "CPU (AVX2/OpenMP)", CPU_STATUS_MSG
    if choice != "Auto":
        choice = "Auto"

    if gpu_algorithm_available():
        return "GPU (CUDA)", "Auto：检测到可用 CUDA 驱动和 GPU 算法，默认使用 GPU。"
    if cpu_algorithm_available():
        return "CPU (AVX2/OpenMP)", "Auto：未检测到可用 GPU，使用 CPU 原生算法。"
    return "Python", "Auto：GPU/CPU 原生算法都不可用，自动启用隐藏的 Python 后备模式。"

sc_cpu_lib = None
sc_gpu_lib = None
is_slime_chunk_fast = None
CPU_DLL_ERROR_MSG = ""
CPU_STATUS_MSG = "CPU 原生算法未检测。"

CPU_DLL = find_resource("slimecore.dll")
if not os.path.exists(CPU_DLL):
    CPU_STATUS_MSG = f"未找到 CPU DLL: {CPU_DLL}"
else:
    try:
        _cpu = load_native_library(CPU_DLL)
        _cpu.search_slime_clusters_centered.argtypes = [
            ctypes.c_int64, ctypes.c_int64, ctypes.c_int32, ctypes.c_int32,
            ctypes.c_int64, ctypes.c_int32, ctypes.c_int32,
            ctypes.POINTER(ExtChunkResult), ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        _cpu.search_slime_clusters_centered.restype = ctypes.c_int64

        if hasattr(_cpu, "is_slime_chunk_c"):
            _cpu.is_slime_chunk_c.argtypes = [ctypes.c_int64, ctypes.c_int64, ctypes.c_int64]
            _cpu.is_slime_chunk_c.restype = ctypes.c_bool
            is_slime_chunk_fast = _cpu.is_slime_chunk_c
        for func in ["request_cancel", "reset_cancel", "request_pause", "resume_search"]:
            getattr(_cpu, func).argtypes = []
            getattr(_cpu, func).restype = None
        _cpu.set_y_scan_config.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        _cpu.set_y_scan_config.restype = None
        _cpu.refine_candidates_y.argtypes = [ctypes.c_int64, ctypes.POINTER(ExtChunkResult), ctypes.c_int32, ctypes.c_int32]
        _cpu.refine_candidates_y.restype = None
        _cpu.score_candidates_precise.argtypes = [ctypes.c_int64, ctypes.POINTER(ExtChunkResult), ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        _cpu.score_candidates_precise.restype = None
        _cpu.get_progress.argtypes = []
        _cpu.get_progress.restype = ctypes.c_int32
        sc_cpu_lib = _cpu
        CPU_STATUS_MSG = f"CPU 原生算法可用: {CPU_DLL}"
    except Exception as e:
        CPU_DLL_ERROR_MSG = f"{type(e).__name__}: {e}"
        CPU_STATUS_MSG = (
            f"CPU DLL 加载失败: {CPU_DLL}\n{CPU_DLL_ERROR_MSG}\n"
            "请确认是 64 位 DLL，并且 VS C++ 运行库 / OpenMP 运行库可用。"
        )
        sc_cpu_lib = None

GPU_DLL = find_resource("slimecore_gpu.dll")
if os.path.exists(GPU_DLL):
    try:
        sc_gpu_lib = load_native_library(GPU_DLL)
        for name in ("search_slime_clusters_gpu_v1_centered", "search_slime_clusters_gpu_v34_centered"):
            if hasattr(sc_gpu_lib, name):
                fn = getattr(sc_gpu_lib, name)
                fn.argtypes = [
                    ctypes.c_int64, ctypes.c_int64, ctypes.c_int32, ctypes.c_int32,
                    ctypes.c_int64, ctypes.c_int32, ctypes.c_int32,
                    ctypes.POINTER(ExtChunkResult), ctypes.c_int32, ctypes.c_int32]
                fn.restype = ctypes.c_int64

        if hasattr(sc_gpu_lib, "is_slime_chunk_c"):
            sc_gpu_lib.is_slime_chunk_c.argtypes = [ctypes.c_int64, ctypes.c_int64, ctypes.c_int64]
            sc_gpu_lib.is_slime_chunk_c.restype = ctypes.c_bool
            if not is_slime_chunk_fast: is_slime_chunk_fast = sc_gpu_lib.is_slime_chunk_c
        for func in ["request_cancel", "reset_cancel", "request_pause", "resume_search", "cleanup_gpu_resources"]:
            getattr(sc_gpu_lib, func).argtypes = []
            getattr(sc_gpu_lib, func).restype = None
        sc_gpu_lib.set_y_scan_config.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        sc_gpu_lib.set_y_scan_config.restype = None
        sc_gpu_lib.refine_candidates_y.argtypes = [ctypes.c_int64, ctypes.POINTER(ExtChunkResult), ctypes.c_int32]
        sc_gpu_lib.refine_candidates_y.restype = None
        sc_gpu_lib.get_progress.argtypes = []
        sc_gpu_lib.get_progress.restype = ctypes.c_int32
        sc_gpu_lib.get_processed_centers.argtypes = []
        sc_gpu_lib.get_processed_centers.restype = ctypes.c_int64
        sc_gpu_lib.get_gpu_scan_work_ns.argtypes = []
        sc_gpu_lib.get_gpu_scan_work_ns.restype = ctypes.c_int64
        sc_gpu_lib.get_cuda_device_count.argtypes = []
        sc_gpu_lib.get_cuda_device_count.restype = ctypes.c_int32
        sc_gpu_lib.get_cuda_device_name.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_int32]
        sc_gpu_lib.get_cuda_device_name.restype = ctypes.c_int32
        for name in ("get_gpu_v1_shape", "get_gpu_v34_shape", "get_gpu_v1_rng", "get_gpu_v34_rng"):
            if hasattr(sc_gpu_lib, name):
                fn = getattr(sc_gpu_lib, name)
                fn.argtypes = []
                fn.restype = ctypes.c_int32
    except Exception: sc_gpu_lib = None

if sc_gpu_lib:
    try:
        GPU_DEVICE_COUNT = int(sc_gpu_lib.get_cuda_device_count())
        GPU_AVAILABLE = GPU_DEVICE_COUNT > 0
        GPU_STATUS_MSG = (
            f"检测到 CUDA 设备 {GPU_DEVICE_COUNT} 个，GPU 算法可用。"
            if GPU_AVAILABLE else "GPU DLL 已加载，但未检测到 CUDA 设备。")
    except Exception as e:
        GPU_AVAILABLE = False
        GPU_STATUS_MSG = f"CUDA 设备检查失败：{e}"
else:
    GPU_STATUS_MSG = "未加载 slimecore_gpu.dll。"

if GPU_AVAILABLE:
    try:
        _gpu_name_buf = ctypes.create_string_buffer(256)
        if int(sc_gpu_lib.get_cuda_device_name(_gpu_name_buf, len(_gpu_name_buf))) > 0:
            GPU_DEVICE_NAME = _gpu_name_buf.value.decode("utf-8", errors="replace").strip() or GPU_DEVICE_NAME
    except Exception:
        pass

# ===== 搜索核心 =====
if not sc_cpu_lib and not GPU_AVAILABLE:
    is_slime_chunk_fast = None

def cleanup_native_resources():
    for lib in (sc_cpu_lib, sc_gpu_lib):
        if lib:
            try: lib.request_cancel()
            except Exception: pass
    if sc_gpu_lib:
        try: sc_gpu_lib.cleanup_gpu_resources()
        except Exception: pass

atexit.register(cleanup_native_resources)
thread_local = threading.local()
_active_mc_version = DEFAULT_MC_VERSION

JAVA_LONG_MIN = -(1 << 63)
JAVA_LONG_MAX = (1 << 63) - 1

def is_minecraft_text_seed(seed):
    if not isinstance(seed, str):
        return False
    text = seed
    if not re.fullmatch(r"[+-]?[0-9]+", text):
        return True
    try:
        value = int(text, 10)
    except ValueError:
        return True
    return value < JAVA_LONG_MIN or value > JAVA_LONG_MAX

def java_string_hash_seed(text):
    data = str(text).encode("utf-16-be", errors="surrogatepass")
    value = 0
    for i in range(0, len(data), 2):
        code_unit = (data[i] << 8) | data[i + 1]
        value = (value * 31 + code_unit) & 0xFFFFFFFF
    return ctypes.c_int32(value).value

def normalize_java_seed(seed):
    if isinstance(seed, str):
        if is_minecraft_text_seed(seed):
            return java_string_hash_seed(seed)
        return int(seed, 10)
    return ctypes.c_int64(int(seed)).value

def cubiomes_version_code(version=None):
    version = "1.21.4" if str(version or _active_mc_version) == "1.21 WD" else str(version or _active_mc_version)
    if cb and hasattr(cb, "str2mc"):
        code = int(cb.str2mc(version.encode("ascii")))
        if code > 0:
            return code
    fallback = {
        "1.19": 24, "1.20": 25, "1.21.1": 26, "1.21.3": 27,
        "1.21.4": 28, "1.21.5": 29, "1.21.6": 30, "1.21.9": 31,
        "1.21.11": 32, "26.1": 33, "26.2": 34,
    }
    return fallback.get(version, fallback[DEFAULT_MC_VERSION])

def set_cubiomes_mc_version(version):
    global _active_mc_version
    version = "1.21.4" if str(version) == "1.21 WD" else str(version)
    if version not in SUPPORTED_MC_VERSIONS:
        version = DEFAULT_MC_VERSION
    _active_mc_version = version
    return _active_mc_version

def get_local_generator(seed):
    if not cb: return None
    version_code = cubiomes_version_code()
    if not hasattr(thread_local, "buf") or getattr(thread_local, "generator_version", None) != version_code:
        try:
            buf = ctypes.create_string_buffer(CUBIOMES_GENERATOR_BUFFER_SIZE)
            cb.setupGenerator(buf, version_code, 0)
            thread_local.buf = buf
            thread_local.generator_version = version_code
            thread_local.generator_seed = None
        except Exception: return None
    seed_i64 = normalize_java_seed(seed)
    if getattr(thread_local, "generator_seed", None) != seed_i64:
        cb.applySeed(thread_local.buf, 0, ctypes.c_uint64(seed_i64 & 0xFFFFFFFFFFFFFFFF))
        thread_local.generator_seed = seed_i64
    return thread_local.buf

def is_slime_chunk(seed, chunk_x, chunk_z):
    if is_slime_chunk_fast: return is_slime_chunk_fast(normalize_java_seed(seed), chunk_x, chunk_z)
    x = chunk_x & 0xFFFFFFFF
    z = chunk_z & 0xFFFFFFFF
    x_sq = (x * x) & 0xFFFFFFFF
    p1 = ctypes.c_int32(x_sq * 0x4c1906).value
    p2 = ctypes.c_int32(x * 0x5ac0db).value
    z_sq = (z * z) & 0xFFFFFFFF
    p3 = ctypes.c_int64(ctypes.c_int32(z_sq).value * 0x4307a7).value
    p4 = ctypes.c_int32(z * 0x5f24f).value
    s = normalize_java_seed(seed)
    s = ctypes.c_int64(s + p1).value
    s = ctypes.c_int64(s + p2).value
    s = ctypes.c_int64(s + p3).value
    s = ctypes.c_int64(s + p4).value
    s = ctypes.c_int64(s ^ 0x3ad8025f).value
    s = (s ^ 0x5DEECE66D) & 0xFFFFFFFFFFFF
    s = (s * 0x5DEECE66D + 0xB) & 0xFFFFFFFFFFFF
    bits = s >> 17
    val = bits % 10
    while True:
        diff = ctypes.c_int32(bits - val + 9).value
        if diff >= 0: break
        s = (s * 0x5DEECE66D + 0xB) & 0xFFFFFFFFFFFF
        bits = s >> 17
        val = bits % 10
    return val == 0

def calc_spawnable_spaces_cached(seed, ox, oz, chunk_cache=None):
    count = 0
    center_cx, center_cz = ox >> 4, oz >> 4
    local_key = (ox & 15, oz & 15)
    for dcx, dcz, block_count in SPAWNABLE_CHUNK_OVERLAP[local_key]:
        cx, cz = center_cx + dcx, center_cz + dcz
        if chunk_cache is None:
            slime = is_slime_chunk(seed, cx, cz)
        else:
            key = (cx, cz)
            try:
                slime = chunk_cache[key]
            except KeyError:
                slime = is_slime_chunk(seed, cx, cz)
                chunk_cache[key] = slime
        if slime:
            count += block_count
    return count

def calc_spawnable_spaces(seed, ox, oz):
    return calc_spawnable_spaces_cached(seed, ox, oz, None)

def unpack_obs_y(raw_obs, scan_y):
    if scan_y and raw_obs >= (1 << Y_PACK_SHIFT):
        return raw_obs & Y_PACK_MASK, (raw_obs >> Y_PACK_SHIFT) - Y_PACK_BIAS
    return raw_obs, None

def configure_y_scan(scan_y):
    enabled = 1 if scan_y else 0
    for lib in (sc_cpu_lib, sc_gpu_lib):
        if lib and hasattr(lib, "set_y_scan_config"):
            lib.set_y_scan_config(enabled, -64, -64, 0, 1)

def refine_y_candidates(seed, candidates, engine_choice, threads):
    if not candidates: return candidates
    buffer = (ExtChunkResult * len(candidates))()
    for i, item in enumerate(candidates):
        # 从原始候选中心细化，避免重复细化漂移。
        center_x = int(item[3]) * 16 + 8
        center_z = int(item[4]) * 16 + 8
        buffer[i].size, buffer[i].center_x, buffer[i].center_z = int(item[0]), center_x, center_z
        buffer[i].obs_count, buffer[i].afk_x, buffer[i].afk_z = 0, center_x, center_z
    refined = False
    if is_gpu_engine(engine_choice) and gpu_algorithm_available() and hasattr(sc_gpu_lib, "refine_candidates_y"):
        sc_gpu_lib.refine_candidates_y(normalize_java_seed(seed), buffer, len(candidates))
        refined = True
    elif sc_cpu_lib and hasattr(sc_cpu_lib, "refine_candidates_y"):
        sc_cpu_lib.refine_candidates_y(normalize_java_seed(seed), buffer, len(candidates), threads)
        refined = True
    if not refined: return candidates
    out = []
    for i, item in enumerate(candidates):
        obs_from_y_scan, afk_y = unpack_obs_y(buffer[i].obs_count, True)
        out.append((
            item[0],
            int(buffer[i].afk_x),
            int(buffer[i].afk_z),
            item[3],
            item[4],
            item[5],
            int(obs_from_y_scan),
            afk_y
        ))
    return out


def native_precise_scorer_available(preferred_engine=None):
    if sc_cpu_lib and hasattr(sc_cpu_lib, "score_candidates_precise"):
        return True
    if is_gpu_engine(preferred_engine) and gpu_algorithm_available() and hasattr(sc_gpu_lib, "refine_candidates_y"):
        return True
    if sc_cpu_lib and hasattr(sc_cpu_lib, "refine_candidates_y"):
        return True
    if gpu_algorithm_available() and hasattr(sc_gpu_lib, "refine_candidates_y"):
        return True
    return False

def native_precise_chunk_size(config=None):
    configured = getattr(config, "native_score_chunk", 0) if config is not None else 0
    if configured:
        value = configured
    else:
        try:
            value = int(os.environ.get("SLIME_NATIVE_SCORE_CHUNK", "8192"))
        except Exception:
            value = 8192
    return max(128, min(int(value), 20000))

def choose_native_precise_scorer(preferred_engine=None):
    """Return (kind, unpack_packed_y).
    Existing DLLs already have refine_candidates_y(); despite the name, with
    y-scan disabled it scores candidates at platform Y and finds better AFK X/Z.
    Newer CPU DLLs may expose score_candidates_precise(), which returns plain obs.
    """
    if is_gpu_engine(preferred_engine) and gpu_algorithm_available() and hasattr(sc_gpu_lib, "refine_candidates_y"):
        return "gpu_refine", True
    if sc_cpu_lib and hasattr(sc_cpu_lib, "score_candidates_precise"):
        return "cpu_score", False
    if sc_cpu_lib and hasattr(sc_cpu_lib, "refine_candidates_y"):
        return "cpu_refine", True
    if gpu_algorithm_available() and hasattr(sc_gpu_lib, "refine_candidates_y"):
        return "gpu_refine", True
    return None, False

def score_candidates_precise_native(
        seed, candidates, threads, progress_cb=None, preferred_engine=None,
        config=None, scan_y=False):
    if not candidates:
        return None
    scorer_kind, unpack_packed_y = choose_native_precise_scorer(preferred_engine)
    if not scorer_kind:
        return None

    out = []
    total = len(candidates)
    chunk_size = native_precise_chunk_size(config)
    seed_i64 = normalize_java_seed(seed)
    threads = max(1, int(threads))
    done = 0

    while done < total:
        if progress_cb:
            try:
                progress_cb(done, total)
            except Exception:
                pass
        chunk = candidates[done:done + chunk_size]
        buffer = (ExtChunkResult * len(chunk))()
        for i, item in enumerate(chunk):
            buffer[i].size = int(item[0])
            # item[3:5] 是原始候选中心。
            center_x = int(item[3]) * 16 + 8
            center_z = int(item[4]) * 16 + 8
            buffer[i].center_x = center_x
            buffer[i].center_z = center_z
            buffer[i].obs_count = 0
            buffer[i].afk_x = center_x
            buffer[i].afk_z = center_z

        configure_y_scan(bool(scan_y))
        try:
            if scorer_kind == "gpu_refine":
                sc_gpu_lib.refine_candidates_y(seed_i64, buffer, len(chunk))
            elif scorer_kind == "cpu_score":
                sc_cpu_lib.score_candidates_precise(seed_i64, buffer, len(chunk), threads, 1)
            elif scorer_kind == "cpu_refine":
                sc_cpu_lib.refine_candidates_y(seed_i64, buffer, len(chunk), threads)
            else:
                return None
        finally:
            if scan_y:
                configure_y_scan(False)

        for i, item in enumerate(chunk):
            obs, afk_y = unpack_obs_y(
                buffer[i].obs_count, unpack_packed_y or bool(scan_y))
            afk_x = int(buffer[i].afk_x)
            afk_z = int(buffer[i].afk_z)
            out.append((
                int(item[0]),
                afk_x,
                afk_z,
                int(item[3]),
                int(item[4]),
                item[5],
                int(obs),
                afk_y
            ))
        done += len(chunk)
    if progress_cb:
        try:
            progress_cb(total, total)
        except Exception:
            pass
    return out

def read_native_candidates(buffer, count, seed, scan_y=False):
    return [(buffer[i].size, buffer[i].afk_x, buffer[i].afk_z, buffer[i].center_x // 16, buffer[i].center_z // 16, seed, unpack_obs_y(buffer[i].obs_count, scan_y)[0], unpack_obs_y(buffer[i].obs_count, scan_y)[1]) for i in range(count)]

def run_gpu_scan(seed, rd_max, min_size, max_size, rd_min, buf_size, precise, center_cx=0, center_cz=0):
    buffer = (ExtChunkResult * buf_size)()
    seed_i64 = normalize_java_seed(seed)
    search_fn = getattr(sc_gpu_lib, "search_slime_clusters_gpu_v1_centered", None)
    if search_fn is None:
        search_fn = sc_gpu_lib.search_slime_clusters_gpu_v34_centered
    found_count = search_fn(
        seed_i64, rd_max, min_size, max_size, rd_min,
        int(center_cx), int(center_cz), buffer, buf_size, precise)
    if found_count < 0:
        raise RuntimeError("当前 GPU 精确算法执行失败；正式版不包含旧算法回退。")
    algorithm = GPU_V1_ALGORITHM
    shape_fn = getattr(sc_gpu_lib, "get_gpu_v1_shape", getattr(sc_gpu_lib, "get_gpu_v34_shape", None))
    if shape_fn:
        shape = int(shape_fn())
        shape_names = {1: "128×8", 2: "256×4", 3: "256×8", 4: "512×4"}
        if shape in shape_names:
            algorithm += " · 自动选择 {}".format(shape_names[shape])
    rng_fn = getattr(sc_gpu_lib, "get_gpu_v1_rng", getattr(sc_gpu_lib, "get_gpu_v34_rng", None))
    if rng_fn:
        rng = int(rng_fn())
        rng_names = {0: "Native", 1: "Limb32", 2: "Truncated"}
        algorithm += " · RNG {}".format(rng_names.get(rng, "Native"))
    extract_count = max(0, min(int(found_count), buf_size))
    return read_native_candidates(buffer, extract_count, seed_i64, False), found_count, algorithm

def run_cpu_scan(seed, rd_max, min_size, max_size, rd_min, buf_size, threads, precise, center_cx=0, center_cz=0):
    buffer = (ExtChunkResult * buf_size)()
    seed_i64 = normalize_java_seed(seed)
    found_count = sc_cpu_lib.search_slime_clusters_centered(
        seed_i64, rd_max, min_size, max_size, rd_min,
        int(center_cx), int(center_cz), buffer, buf_size, threads, precise)
    if found_count < 0:
        raise RuntimeError("当前 CPU 精确算法执行失败。")
    extract_count = max(0, min(int(found_count), buf_size))
    return read_native_candidates(buffer, extract_count, seed_i64, False), found_count

def search_slime_clusters_py(seed, rd_max, min_size, max_size, rd_min, buf_size, c_obj=None, is_precise=True, center_cx=0, center_cz=0):
    import heapq
    rd_min_sq = float(rd_min * rd_min)
    total_rows = 2 * rd_max + 1
    leaderboard = []
    max_keep = min(buf_size, MAX_CANDIDATE_BUFFER if is_precise else 500000)
    absolute_total = 0

    def push_candidate(key, item):
        if len(leaderboard) < max_keep:
            heapq.heappush(leaderboard, (key, item))
        elif key > leaderboard[0][0]:
            heapq.heapreplace(leaderboard, (key, item))

    min_cx, max_cx = int(center_cx) - rd_max, int(center_cx) + rd_max
    min_cz, max_cz = int(center_cz) - rd_max, int(center_cz) + rd_max
    for row_idx, cx in enumerate(range(min_cx, max_cx + 1)):
        while c_obj and c_obj.pause and not c_obj.cancel:
            time.sleep(0.05)
        if c_obj and c_obj.cancel: break
        if c_obj and row_idx % max(1, (total_rows // 20)) == 0: c_obj.p.emit(10 + int(row_idx / total_rows * 30))
        for cz in range(min_cz, max_cz + 1):
            if rd_min > 0 and ((float(cx - center_cx) ** 2 + float(cz - center_cz) ** 2) < rd_min_sq): continue
            count = sum(1 for dx in range(-8, 9) for dz in range(-8, 9) if dx*dx + dz*dz <= 68 and is_slime_chunk(seed, cx + dx, cz + dz))
            if min_size <= count <= max_size:
                absolute_total += 1
                bx, bz = cx * 16 + 8, cz * 16 + 8
                if is_precise:
                    # Python 后备模式没有 DLL 的精准排序能力，所以这里必须对每个满足用户规模条件的候选
                    # 直接计算刷怪格数，再只保留当前最优池。否则会先按规模截断，漏掉低规模但高刷怪格数的候选。
                    obs = calc_spawnable_spaces(seed, bx, bz)
                    item = (count, bx, bz, bx // 16, bz // 16, seed, obs, None)
                    key = (obs, count, -bx, -bz, seed)
                else:
                    item = (count, bx, bz, bx // 16, bz // 16, seed, 0, None)
                    key = (count, -bx, -bz, seed)
                push_candidate(key, item)

    final_res = [item for _key, item in leaderboard]
    if is_precise:
        final_res.sort(key=lambda x: (x[6], x[0], -x[1], -x[2], x[5]), reverse=True)
    else:
        final_res.sort(key=lambda x: (x[0], -x[1], -x[2], x[5]), reverse=True)
    return final_res, absolute_total

def check_deep_dark_fast(buf, center_chunk_x, center_chunk_z, seed):
    if not buf or not cb:
        return False
    for dx in range(-8, 9):
        for dz in range(-8, 9):
            if dx * dx + dz * dz <= 68 and is_slime_chunk(seed, center_chunk_x + dx, center_chunk_z + dz):
                node_cx, node_cz = (center_chunk_x + dx) * 4, (center_chunk_z + dz) * 4
                for y_node in range(-16, 1):
                    for nx in range(4):
                        for nz in range(4):
                            if cb.getBiomeAt(buf, 4, node_cx + nx, y_node, node_cz + nz) == 183:
                                return True
    return False

def check_mushroom_fast(buf, center_chunk_x, center_chunk_z, seed):
    if not buf or not cb:
        return False
    for dx in range(-8, 9):
        for dz in range(-8, 9):
            if dx * dx + dz * dz <= 68 and is_slime_chunk(seed, center_chunk_x + dx, center_chunk_z + dz):
                node_cx, node_cz = (center_chunk_x + dx) * 4, (center_chunk_z + dz) * 4
                for nx in range(4):
                    for nz in range(4):
                        if cb.getBiomeAt(buf, 4, node_cx + nx, 16, node_cz + nz) == 14:
                            return True
    return False

def create_slime_map(seed, block_x, block_z, dest_path):
    img = QImage(512, 512, QImage.Format.Format_ARGB32)
    img.fill(QColor(30, 30, 30))
    painter = QPainter(img)
    center_pixel = 256
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(76, 175, 80))
    center_cx, center_cz = block_x >> 4, block_z >> 4
    for dx in range(-17, 18):
        for dz in range(-17, 18):
            cx, cz = center_cx + dx, center_cz + dz
            if is_slime_chunk(seed, cx, cz):
                painter.drawRect(center_pixel + (cx * 16 - block_x), center_pixel + (cz * 16 - block_z), 16, 16)
    painter.setPen(QColor(100, 100, 100))
    for i in range((center_pixel - block_x) % 16, 513, 16): painter.drawLine(i, 0, i, 512)
    for i in range((center_pixel - block_z) % 16, 513, 16): painter.drawLine(0, i, 512, i)
    painter.setPen(QPen(QColor(255, 50, 50), 2, Qt.PenStyle.SolidLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(center_pixel - 128, center_pixel - 128, 256, 256)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 150, 255))
    painter.drawEllipse(center_pixel - 4, center_pixel - 4, 8, 8)
    painter.end()
    img.save(dest_path)

# ===== 配置与任务 =====
class Config:
    def __init__(self):
        self.settings_file = os.path.join(APP_DIR, "settings.json")
        self.max_sys_threads = os.cpu_count() or 4
        self.load()
    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.use_range = data.get('use_range', False)
                    self.use_min_radius = data.get('use_min_radius', False)
                    self.max_size = data.get('max', 100)
                    self.min_size = data.get('min', 40)
                    self.last_seed = data.get('last_seed', '')
                    self.last_radius = data.get('last_radius', '512')
                    self.search_center_x = int(data.get('search_center_x', 0))
                    self.search_center_z = int(data.get('search_center_z', 0))
                    self.min_search_radius = data.get('min_search_radius', 0)
                    self.threads = min(clamp_int(data.get('threads', max(1, int(self.max_sys_threads * 0.8))), max(1, int(self.max_sys_threads * 0.8)), 1, self.max_sys_threads), self.max_sys_threads)
                    self.selected_engine = data.get('selected_engine', "Auto")
                    if self.selected_engine not in ("Auto", "GPU (CUDA)", "CPU (AVX2/OpenMP)"):
                        self.selected_engine = "Auto"
                    self.precise_afk = data.get('precise_afk', True)
                    self.scan_y = data.get('scan_y', False)
                    self.result_limit = clamp_int(data.get('result_limit', DEFAULT_RESULT_LIMIT), DEFAULT_RESULT_LIMIT, 1, MAX_RESULT_LIMIT)
                    self.candidate_buffer = clamp_int(data.get('candidate_buffer', 1000000), 1000000, 1000, MAX_CANDIDATE_BUFFER)
                    # 0 means auto: no-biome filter keeps Top 200, biome filter keeps Top 2000.
                    self.precise_target_pool = clamp_int(data.get('precise_target_pool', 0), 0, 0, 20000)
                    self.native_score_chunk = clamp_int(data.get('native_score_chunk', 8192), 8192, 128, 20000)
                    self.precise_exhaustive = bool(data.get('precise_exhaustive', False))
                    self.minecraft_version = str(data.get('minecraft_version', DEFAULT_MC_VERSION))
                    if self.minecraft_version == "1.21 WD":
                        self.minecraft_version = "1.21.4"
                    if self.minecraft_version not in SUPPORTED_MC_VERSIONS:
                        self.minecraft_version = DEFAULT_MC_VERSION
            except Exception: self.set_defaults()
        else: self.set_defaults()
    def set_defaults(self):
        self.use_range, self.use_min_radius, self.max_size, self.min_size = False, False, 100, 40
        self.last_seed, self.last_radius, self.min_search_radius = '', '512', 0
        self.search_center_x, self.search_center_z = 0, 0
        self.threads = max(1, int(self.max_sys_threads * 0.8))
        self.selected_engine, self.precise_afk, self.scan_y = "Auto", True, False
        self.result_limit = DEFAULT_RESULT_LIMIT
        self.candidate_buffer = 1000000
        self.precise_target_pool = 0
        self.native_score_chunk = 8192
        self.precise_exhaustive = False
        self.minecraft_version = DEFAULT_MC_VERSION
    def save(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'use_range': self.use_range, 'use_min_radius': self.use_min_radius,
                    'max': self.max_size, 'min': self.min_size,
                    'last_seed': self.last_seed, 'last_radius': self.last_radius,
                    'search_center_x': self.search_center_x,
                    'search_center_z': self.search_center_z,
                    'min_search_radius': self.min_search_radius, 'threads': self.threads,
                    'selected_engine': self.selected_engine,
                    'precise_afk': self.precise_afk,
                    'scan_y': self.scan_y,
                    'result_limit': self.result_limit,
                    'candidate_buffer': self.candidate_buffer,
                    'precise_target_pool': self.precise_target_pool,
                    'native_score_chunk': self.native_score_chunk,
                    'precise_exhaustive': self.precise_exhaustive,
                    'minecraft_version': self.minecraft_version
                }, f, ensure_ascii=False, indent=2)
        except Exception: pass


class C(QObject):
    l = pyqtSignal(str); i = pyqtSignal(str); p = pyqtSignal(int); t = pyqtSignal(str); info = pyqtSignal(str)
    btn_state = pyqtSignal(bool); search_done = pyqtSignal(object); manual_done = pyqtSignal(object)
    msg_box = pyqtSignal(str, str, str)
    widget_enabled = pyqtSignal(object, bool)
    widget_text = pyqtSignal(object, str)
    native_scan_state = pyqtSignal(bool, str, float, float, int, object)
    cancel = False
    pause = False

def run_full_logic(app, seeds, rd_max, ms, max_s, use_range, rd_min, engine_choice, is_precise, scan_y, result_limit=DEFAULT_RESULT_LIMIT, is_dd_checked=None, center_cx=0, center_cz=0):
    result_limit = max(1, min(MAX_RESULT_LIMIT, int(result_limit or DEFAULT_RESULT_LIMIT)))
    def emit_progress(value):
        app.c.p.emit(max(0, min(100, int(value))))

    def candidate_obs_score(item):
        return int(item[6]) if item[6] is not None else 0

    def ranking_key(item):
        obs_score = candidate_obs_score(item)
        score = obs_score if is_precise and obs_score > 0 else item[0]
        return (score, item[0], -item[1], -item[2], item[5])

    def with_obs(item, obs_count):
        return (item[0], item[1], item[2], item[3], item[4], item[5], int(obs_count), item[7])

    def needs_precise_score(item):
        return candidate_obs_score(item) <= 0

    def candidate_upper_key(item):
        slime_count = max(0, min(221, int(item[0])))
        bounds = PRECISE_Y_SPAWN_SAFE_BOUND if scan_y else PRECISE_SPAWN_SAFE_BOUND
        ub = bounds[slime_count]
        # The score bound is safe by construction. Infinite tie components are
        # deliberate: if an exact score equals the bound, the whole tuple must
        # still dominate every possible final ranking key.
        return (ub, item[0], float("inf"), float("inf"), float("inf"), float("inf"))

    def precise_native_batch_enabled():
        value = os.environ.get("SLIME_PRECISE_NATIVE_BATCH", "1").strip().lower()
        return value not in ("0", "false", "no", "off")

    def native_branch_bound_score(seed, missing_items, ready_items, target_pool, exhaustive):
        """Native batch exact scoring + upper-bound stop.
        This is the fast path: C++/OpenMP scores candidates in chunks, while
        Python only maintains the top heap and updates UI progress.
        """
        import heapq
        heap = []
        counter = 0
        for item in ready_items:
            counter += 1
            key = ranking_key(item)
            if len(heap) < target_pool:
                heapq.heappush(heap, (key, counter, item))
            elif key > heap[0][0]:
                heapq.heapreplace(heap, (key, counter, item))

        missing_items.sort(key=candidate_upper_key, reverse=True)
        total_missing = len(missing_items)
        scored_count = 0
        skipped = 0
        start_precise_time = time.time()
        batch_size = native_precise_chunk_size(app.config)
        last_ui_update = 0.0

        app.c.l.emit("精准比对：使用原生批量评分器，避免 Python 逐候选计算。")

        while scored_count < total_missing:
            if getattr(app.c, "cancel", False):
                app.c.l.emit("精准比对已取消。")
                return []

            if not exhaustive and len(heap) >= target_pool:
                next_upper = candidate_upper_key(missing_items[scored_count])
                if next_upper <= heap[0][0]:
                    skipped = total_missing - scored_count
                    break

            end_idx = min(total_missing, scored_count + batch_size)
            batch = missing_items[scored_count:end_idx]

            def on_native_progress(done, total_batch):
                nonlocal last_ui_update
                now = time.time()
                if now - last_ui_update < 0.2 and done < total_batch:
                    return
                last_ui_update = now
                done_global = scored_count + done
                elapsed = max(0.001, now - start_precise_time)
                speed = done_global / elapsed if done_global else 0.0
                remain = max(0, total_missing - done_global)
                eta = int(remain / max(0.001, speed)) if done_global else 0
                mm, ss = divmod(eta, 60)
                app.c.t.emit("原生精准比对 {}/{} | 已用时 {} | 预计剩余 {:02d}分{:02d}秒".format(
                    done_global, total_missing, format_elapsed(elapsed), mm, ss))
                try:
                    frac = min(1.0, done_global / max(1, total_missing))
                    emit_progress(seed_base_pct + (35 + int(frac * 47)) / total_seeds)
                except Exception:
                    pass

            scored_batch = score_candidates_precise_native(
                seed, batch, threads, on_native_progress, engine_choice,
                app.config, scan_y=scan_y)
            if scored_batch is None:
                return None

            for item2 in scored_batch:
                counter += 1
                key = ranking_key(item2)
                if len(heap) < target_pool:
                    heapq.heappush(heap, (key, counter, item2))
                elif key > heap[0][0]:
                    heapq.heapreplace(heap, (key, counter, item2))

            scored_count = end_idx
            elapsed = max(0.001, time.time() - start_precise_time)
            speed = scored_count / elapsed
            remain = max(0, total_missing - scored_count)
            eta = int(remain / max(0.001, speed)) if scored_count else 0
            mm, ss = divmod(eta, 60)
            app.c.t.emit("原生精准比对 {}/{} | 已用时 {} | 预计剩余 {:02d}分{:02d}秒".format(scored_count, total_missing, format_elapsed(elapsed), mm, ss))
            try:
                frac = min(1.0, scored_count / max(1, total_missing))
                emit_progress(seed_base_pct + (35 + int(frac * 47)) / total_seeds)
            except Exception:
                pass

        out = [entry[2] for entry in heap]
        out.sort(key=ranking_key, reverse=True)
        precise_elapsed = format_elapsed(time.time() - start_precise_time)
        if skipped:
            app.c.l.emit("原生精准快速比对完成：实际评分 {:,} 个，按安全上界跳过 {:,} 个，用时 {}。".format(scored_count, skipped, precise_elapsed))
        else:
            app.c.l.emit("原生精准比对完成：实际评分 {:,} 个，用时 {}。".format(scored_count, precise_elapsed))
        return out

    def enrich_precise_scores(seed, items, limit=None):
        """精准模式的候选比对。
        优先使用新 CPU DLL 的 score_candidates_precise() 批量评分接口；
        没有新 DLL 时才回退到 Python 分支定界。
        """
        if not is_precise or not items:
            return items

        total = len(items)
        missing_items = []
        ready_items = []
        for item in items:
            # Platform-Y scores produced by the first native scan are not final
            # when Y scanning is requested. Every candidate entering this stage
            # must therefore be rescored against the real Y=-64..0 search.
            if scan_y or needs_precise_score(item):
                missing_items.append(item)
            else:
                ready_items.append(item)

        if not missing_items:
            return items

        has_biome_filter = bool(cb and (is_dd_checked or FILTER_MUSHROOM_ISLAND))
        exhaustive = precise_exhaustive_enabled(app.config)
        target_pool = total if exhaustive else min(total, precise_eval_target_pool(has_biome_filter, app.config))
        app.c.l.emit(
            "精准模式：候选 {:,} 个；{}。".format(
                total,
                "正在全量比对" if exhaustive else "启用上界剪枝，只精算有机会进入前 {:,} 的候选".format(target_pool)
            )
        )

        if native_precise_scorer_available(engine_choice) and precise_native_batch_enabled():
            native_out = native_branch_bound_score(seed, missing_items, ready_items, target_pool, exhaustive)
            if native_out is not None:
                return native_out
            app.c.l.emit("原生批量评分不可用，回退到 Python 精准比对。")
        elif not native_precise_scorer_available(engine_choice):
            app.c.l.emit("提示：未找到可用的原生批量评分接口，只能使用较慢的 Python 精准比对。")

        if not exhaustive:
            app.c.l.emit("如需强制全量精准比对，可设置环境变量 SLIME_PRECISE_EXHAUSTIVE=1；会更慢。")

        import heapq
        heap = []
        heap_counter = 0
        for item in ready_items:
            key = ranking_key(item)
            heap_counter += 1
            if len(heap) < target_pool:
                heapq.heappush(heap, (key, heap_counter, item))
            elif key > heap[0][0]:
                heapq.heapreplace(heap, (key, heap_counter, item))

        missing_items.sort(key=candidate_upper_key, reverse=True)
        chunk_cache = {}
        evaluated = 0
        skipped = 0
        last_ui_update = 0.0
        total_missing = len(missing_items)
        start_precise_time = time.time()

        for item in missing_items:
            if getattr(app.c, "cancel", False):
                app.c.l.emit("精准比对已取消。")
                return []

            upper_key = candidate_upper_key(item)
            if not exhaustive and len(heap) >= target_pool and upper_key <= heap[0][0]:
                skipped = total_missing - evaluated
                break

            try:
                obs = calc_spawnable_spaces_cached(seed, item[1], item[2], chunk_cache)
                item2 = with_obs(item, obs)
            except Exception:
                item2 = item
            key = ranking_key(item2)
            heap_counter += 1
            if len(heap) < target_pool:
                heapq.heappush(heap, (key, heap_counter, item2))
            elif key > heap[0][0]:
                heapq.heapreplace(heap, (key, heap_counter, item2))
            evaluated += 1

            now = time.time()
            if evaluated == total_missing or evaluated % 100 == 0 or now - last_ui_update > 0.25:
                last_ui_update = now
                elapsed = max(0.001, now - start_precise_time)
                speed = evaluated / elapsed
                remain = max(0, total_missing - evaluated)
                eta = int(remain / max(0.001, speed)) if evaluated else 0
                mm, ss = divmod(eta, 60)
                app.c.t.emit("Python 精准比对 {}/{} | 缓存区块 {:,} | 已用时 {} | 预计剩余 {:02d}分{:02d}秒".format(
                    evaluated, total_missing, len(chunk_cache), format_elapsed(elapsed), mm, ss))
                try:
                    frac = min(1.0, evaluated / max(1, total_missing))
                    emit_progress(seed_base_pct + (35 + int(frac * 47)) / total_seeds)
                except Exception:
                    pass

        out = [entry[2] for entry in heap]
        out.sort(key=ranking_key, reverse=True)
        precise_elapsed = format_elapsed(time.time() - start_precise_time)
        if skipped:
            app.c.l.emit("Python 精准快速比对完成：实际精算 {:,} 个，按安全上界跳过 {:,} 个，缓存区块 {:,} 个，用时 {}。".format(
                evaluated, skipped, len(chunk_cache), precise_elapsed))
        else:
            app.c.l.emit("Python 精准比对完成：实际精算 {:,} 个，缓存区块 {:,} 个，用时 {}。".format(evaluated, len(chunk_cache), precise_elapsed))
        return out

    def apply_y_after_selection(seed, items, label="候选"):
        if not scan_y or not items:
            return items
        if is_precise and all(len(item) > 7 and item[7] is not None for item in items):
            return items
        app.c.l.emit("正在为 {} 个{}补扫最佳挂机 XYZ（Y=-64..0, step=1）...".format(len(items), label))
        app.c.t.emit("正在扫描挂机 Y...")
        configure_y_scan(True)
        try:
            return refine_y_candidates(seed, items, engine_choice, threads)
        finally:
            configure_y_scan(False)

    def prepare_candidates_for_sort(seed, candidates):
        """把候选整理到真正用于排序的状态。
        - 快速模式：按规模排序。
        - 精准模式：必须有 obs_count 才按刷怪格数排序。
        - 精准+Y模式：直接按最终最佳 XYZ/Y 分数做安全上界剪枝和排序。
        """
        if not candidates:
            return candidates

        if is_precise:
            candidates = enrich_precise_scores(seed, candidates)
        candidates.sort(key=ranking_key, reverse=True)
        return candidates


    def run_native_scan_with_heartbeat(label, seed, scan_callable, native_lib, seed_base_pct, total_seeds, start_time):
        """Run a blocking native CPU/GPU scan in a child thread while this
        worker thread keeps sending UI heartbeat/progress updates.

        Older DLLs either do not export get_progress() or only update it after
        large chunks of work. Without this wrapper a very large search can look
        stuck at 2% even though the native scan is still running normally.
        """
        done_event = threading.Event()
        result_box = {}
        last_ui = 0.0
        last_phase = 2

        def scan_worker():
            try:
                result_box["result"] = scan_callable()
            except Exception as exc:
                result_box["error"] = exc
            finally:
                done_event.set()

        try:
            # Use a Qt signal for cross-thread state changes. Directly changing
            # QWidget-owned fields from this worker can be lost or delayed on
            # some Windows/PyQt builds, which is why the bar could stay at 2%.
            app.c.native_scan_state.emit(True, label, float(start_time), float(seed_base_pct), max(1, int(total_seeds)), native_lib)
        except Exception:
            try:
                app._native_scan_active = True
                app._native_scan_started = start_time
                app._native_scan_base_pct = float(seed_base_pct)
                app._native_scan_total_seeds = max(1, int(total_seeds))
                app._native_scan_label = label
                app._native_scan_lib = native_lib
            except Exception:
                pass

        threading.Thread(target=scan_worker, daemon=True).start()
        while not done_event.is_set():
            now = time.time()
            if getattr(app, "_search_paused", False) and not getattr(app.c, "cancel", False):
                app.c.t.emit("{} 已暂停 · 点击“继续”恢复".format(label))
                time.sleep(0.2)
                continue
            if getattr(app.c, "cancel", False):
                if native_lib and hasattr(native_lib, "request_cancel"):
                    try:
                        native_lib.request_cancel()
                    except Exception:
                        pass
                app.c.t.emit("{} 扫描取消中...".format(label))

            if now - last_ui >= 0.5:
                last_ui = now
                elapsed = max(0.001, now - start_time)
                native_pct = None
                if native_lib and hasattr(native_lib, "get_progress"):
                    try:
                        raw_pct = int(native_lib.get_progress())
                        if 0 <= raw_pct <= 100:
                            native_pct = raw_pct
                    except Exception:
                        native_pct = None

                if native_pct is not None and native_pct > 0:
                    phase = 2 + int(min(33, max(0, native_pct) * 33 / 100))
                else:
                    # Soft heartbeat progress: never claims the scan stage is
                    # complete, but prevents the UI from appearing frozen on
                    # huge ranges when the DLL cannot report fine-grained progress.
                    phase = 2 + int((1.0 - math.exp(-elapsed / 45.0)) * 31)
                    if elapsed >= 1.0:
                        phase = max(3, phase)
                    phase = min(34, max(2, phase))

                if phase > last_phase:
                    last_phase = phase
                    emit_progress(seed_base_pct + phase / total_seeds)

                elapsed_text = format_elapsed(elapsed)
                if native_pct is not None and native_pct > 0:
                    app.c.t.emit("{} 扫描中：{}% | 已用时 {}".format(label, native_pct, elapsed_text))
                else:
                    app.c.t.emit("{} 扫描中：已用时 {}".format(label, elapsed_text))

            time.sleep(0.2)
        try:
            app.c.native_scan_state.emit(False, label, float(start_time), float(seed_base_pct), max(1, int(total_seeds)), native_lib)
        except Exception:
            try:
                app._native_scan_active = False
            except Exception:
                pass
        if "error" in result_box:
            raise result_box["error"]
        return result_box.get("result")

    task_start_time = time.time()
    try:
        for lib in (sc_cpu_lib, sc_gpu_lib):
            if lib and hasattr(lib, "reset_cancel"):
                try:
                    lib.reset_cancel()
                except Exception:
                    pass
        # 第一阶段扫描不能开启 Y 扫配置；Y 只在 refine_y_candidates 前临时开启。
        # 否则只要勾选“扫描挂机Y”，DLL 就可能走带 Y/obs 的精准路径，表现成强制精准。
        configure_y_scan(False)
        threads = max(1, int(app.config.threads))
        configured_buffer = getattr(app.config, "candidate_buffer", 1000000 if is_precise else 500000)
        try:
            env_buffer = os.environ.get("SLIME_CANDIDATE_BUFFER")
            buf_size = int(env_buffer) if env_buffer else int(configured_buffer)
        except Exception:
            buf_size = int(configured_buffer)
        buf_size = max(1000, min(buf_size, MAX_CANDIDATE_BUFFER))
        app.c.cancel = False
        emit_progress(1)
        app.c.t.emit("准备扫描...")
        app.c.l.emit("任务开始：{} 个种子，半径 {} 区块，最小规模 {}{}，模式 {}。".format(
            len(seeds), rd_max, ms, f"，最大规模 {max_s}" if use_range else "", engine_choice))
        app.c.l.emit("排序模式：{}。".format("精准挂机点 / 刷怪格数优先" if is_precise else "快速 / 规模优先"))
        app.c.l.emit("候选缓冲上限：{:,}；原生评分批量：{:,}。".format(buf_size, native_precise_chunk_size(app.config)))
        if is_precise:
            mode_text = "全量精准" if precise_exhaustive_enabled(app.config) else "智能精准"
            pool_text = "自动" if getattr(app.config, "precise_target_pool", 0) == 0 else "{:,}".format(getattr(app.config, "precise_target_pool", 0))
            app.c.l.emit("精准处理：{}；结果池：{}。".format(mode_text, pool_text))
        if scan_y:
            app.c.l.emit("已启用挂机 Y 扫描；精准模式会按最终最佳 XYZ/Y 直接排名。")
        if not is_precise:
            app.c.l.emit("当前为快速模式：不会按刷怪格数排序。")

        total_seeds = max(1, len(seeds))
        all_results = []
        algorithms_used = set()

        for d in ["data", "images"]:
            os.makedirs(os.path.join(APP_DIR, d), exist_ok=True)

        if is_dd_checked is None:
            try:
                is_dd_checked = app.chk_dd.isChecked()
            except Exception:
                is_dd_checked = False

        for idx, sd in enumerate(seeds):
            if app.c.cancel:
                app.c.l.emit("任务已取消。")
                break

            seed_base_pct = (idx / total_seeds) * 100
            start_time = time.time()
            # 第一阶段是否精准，只由“精准挂机点”控制；和扫描Y无关。
            # 扫描Y会在 prepare_candidates_for_sort() 里作为后处理执行。
            native_precise = 1 if is_precise else 0
            size_limit = max_s if use_range else 999
            emit_progress(seed_base_pct + 2 / total_seeds)
            app.c.t.emit("正在扫描第 {}/{} 个种子...".format(idx + 1, total_seeds))
            app.c.l.emit("开始扫描种子 {}...".format(sd))

            if engine_choice == "GPU (CUDA)" and gpu_algorithm_available():
                app.c.l.emit("GPU 模式扫描中...")
                scan_result = run_native_scan_with_heartbeat(
                    "GPU",
                    sd,
                    lambda sd=sd: run_gpu_scan(
                        sd, rd_max, ms, size_limit, rd_min, buf_size, native_precise,
                        center_cx, center_cz),
                    sc_gpu_lib,
                    seed_base_pct,
                    total_seeds,
                    start_time
                )
                candidates, found_count, gpu_algorithm = scan_result
                algorithms_used.add(gpu_algorithm)
                app.c.l.emit("GPU 精确算法：{}。".format(gpu_algorithm))
                app.c.l.emit("GPU 扫图完成：发现 {:,} 处候选，用时 {}。".format(found_count, format_elapsed(time.time() - start_time)))
            elif engine_choice == "CPU (AVX2/OpenMP)" and sc_cpu_lib:
                algorithms_used.add("V1 CPU 行前缀/SAT 精确模式")
                app.c.l.emit("CPU 模式扫描中...")
                candidates, found_count = run_native_scan_with_heartbeat(
                    "CPU",
                    sd,
                    lambda sd=sd: run_cpu_scan(
                        sd, rd_max, ms, size_limit, rd_min, buf_size, threads, native_precise,
                        center_cx, center_cz),
                    sc_cpu_lib,
                    seed_base_pct,
                    total_seeds,
                    start_time
                )
                app.c.l.emit("CPU 扫图完成：发现 {:,} 处候选，用时 {}。".format(found_count, format_elapsed(time.time() - start_time)))
            else:
                algorithms_used.add("V1 Python 精确后备模式")
                app.c.l.emit("启动 Python 后备模式（较慢）...")
                candidates, found_count = search_slime_clusters_py(
                    sd, rd_max, ms, size_limit, rd_min, buf_size, app.c, is_precise,
                    center_cx, center_cz)
                app.c.l.emit("Python 扫图完成：发现 {:,} 处候选，用时 {}。".format(found_count, format_elapsed(time.time() - start_time)))

            if is_precise:
                total_found = int(found_count)
                if total_found > len(candidates):
                    if total_found > MAX_CANDIDATE_BUFFER:
                        raise RuntimeError(
                            "精准结果已停止：共有 {:,} 个候选，但当前完整精准模式最多可回传 {:,} 个。"
                            "继续排名会存在漏掉真实最佳点的风险；请提高最小规模或缩小搜索范围。".format(
                                total_found, MAX_CANDIDATE_BUFFER))

                    retry_buf = max(1000, total_found)
                    app.c.l.emit(
                        "精准完整性保护：首次缓冲只取回 {:,}/{:,} 个候选，自动扩大到 {:,} 并重新扫描。".format(
                            len(candidates), total_found, retry_buf))

                    retry_start = time.time()
                    if engine_choice == "GPU (CUDA)" and gpu_algorithm_available():
                        candidates, found_count, gpu_algorithm = run_native_scan_with_heartbeat(
                            "GPU 完整候选重扫",
                            sd,
                            lambda sd=sd, retry_buf=retry_buf: run_gpu_scan(
                                sd, rd_max, ms, size_limit, rd_min, retry_buf, native_precise,
                                center_cx, center_cz),
                            sc_gpu_lib,
                            seed_base_pct,
                            total_seeds,
                            retry_start)
                        algorithms_used.add(gpu_algorithm)
                    elif engine_choice == "CPU (AVX2/OpenMP)" and sc_cpu_lib:
                        candidates, found_count = run_native_scan_with_heartbeat(
                            "CPU 完整候选重扫",
                            sd,
                            lambda sd=sd, retry_buf=retry_buf: run_cpu_scan(
                                sd, rd_max, ms, size_limit, rd_min, retry_buf, threads, native_precise,
                                center_cx, center_cz),
                            sc_cpu_lib,
                            seed_base_pct,
                            total_seeds,
                            retry_start)
                    else:
                        candidates, found_count = search_slime_clusters_py(
                            sd, rd_max, ms, size_limit, rd_min, retry_buf, app.c, is_precise,
                            center_cx, center_cz)

                    if int(found_count) > len(candidates):
                        raise RuntimeError(
                            "精准结果已停止：自动重扫后仍只取回 {:,}/{:,} 个候选，无法证明排名完整。".format(
                                len(candidates), int(found_count)))
                    app.c.l.emit("精准完整性保护通过：{:,} 个候选已全部取回。".format(len(candidates)))

            emit_progress(seed_base_pct + 35 / total_seeds)

            if app.c.cancel:
                app.c.l.emit("任务已取消。")
                break
            if not candidates:
                app.c.l.emit("种子 {} 未发现候选。".format(sd))
                emit_progress(((idx + 1) / total_seeds) * 95)
                continue

            candidates = prepare_candidates_for_sort(sd, candidates)
            if app.c.cancel:
                app.c.l.emit("任务已取消。")
                break
            if not candidates:
                app.c.l.emit("种子 {} 没有可用于最终排序的候选。".format(sd))
                emit_progress(((idx + 1) / total_seeds) * 95)
                continue

            if cb and (is_dd_checked or FILTER_MUSHROOM_ISLAND):
                candidates.sort(key=ranking_key, reverse=True)
                check_msg = "排查群系"
                if is_dd_checked and FILTER_MUSHROOM_ISLAND:
                    check_msg = "排查深谙之域与蘑菇岛"
                elif is_dd_checked:
                    check_msg = "排查深谙之域"
                elif FILTER_MUSHROOM_ISLAND:
                    check_msg = "排查蘑菇岛"

                # 精准+Y在进入群系过滤前已按最终最佳XYZ/Y完成评分和排序；
                # 因此只需从榜首向下检查，凑够最终Top-N即可停止。
                target_valid = result_limit
                accepted_this_seed = 0
                accepted_candidates = []
                processed = 0
                filtered_this_seed = 0
                dd_start_time = time.time()
                if scan_y:
                    app.c.l.emit("正在{}，先检查全部 {} 个精准候选，再按最佳Y重新排名...".format(check_msg, target_valid))
                else:
                    app.c.l.emit("正在{}，目标保留前 {} 个有效结果...".format(check_msg, target_valid))

                def validate_task(item):
                    generator = get_local_generator(item[5])
                    bad_biome = False
                    if is_dd_checked and check_deep_dark_fast(generator, item[3], item[4], item[5]):
                        bad_biome = True
                    if not bad_biome and FILTER_MUSHROOM_ISLAND and check_mushroom_fast(generator, item[3], item[4], item[5]):
                        bad_biome = True
                    return (bad_biome, item)

                max_in_flight = max(16, min(128, threads * 4))
                executor = ThreadPoolExecutor(max_workers=threads)
                future_to_index = {}
                completed_results = {}
                next_ordered_index = 0
                next_submit_index = 0

                def submit_more_tasks():
                    nonlocal next_submit_index
                    while len(future_to_index) < max_in_flight and next_submit_index < len(candidates):
                        if app.c.cancel or accepted_this_seed >= target_valid:
                            break
                        item = candidates[next_submit_index]
                        future = executor.submit(validate_task, item)
                        future_to_index[future] = next_submit_index
                        next_submit_index += 1

                try:
                    submit_more_tasks()
                    while future_to_index:
                        if app.c.cancel or accepted_this_seed >= target_valid:
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        done_future = next(as_completed(list(future_to_index)))
                        candidate_index = future_to_index.pop(done_future)
                        completed_results[candidate_index] = done_future.result()

                        while next_ordered_index in completed_results:
                            has_bad, item = completed_results.pop(next_ordered_index)
                            next_ordered_index += 1
                            if has_bad:
                                filtered_this_seed += 1
                            elif accepted_this_seed < target_valid:
                                accepted_candidates.append(item)
                                accepted_this_seed += 1
                            processed += 1

                            if processed > 0:
                                remaining = max(0, len(candidates) - processed)
                                elapsed = max(0.001, time.time() - dd_start_time)
                                seconds_est = int((elapsed / processed) * remaining)
                                minutes_left, seconds_left = divmod(seconds_est, 60)
                                app.c.t.emit("正在排查群系... 已保留 {}/{}，预计剩余 {:02d}分{:02d}秒".format(
                                    accepted_this_seed, target_valid, minutes_left, seconds_left))
                                denom = max(1, len(candidates))
                                per_seed_progress = min(90, 35 + int((processed / denom) * 55))
                                emit_progress(seed_base_pct + per_seed_progress / total_seeds)

                            if app.c.cancel or accepted_this_seed >= target_valid:
                                executor.shutdown(wait=False, cancel_futures=True)
                                break
                        submit_more_tasks()
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)

                accepted_candidates.sort(key=ranking_key, reverse=True)
                accepted_candidates = apply_y_after_selection(sd, accepted_candidates, "有效候选")
                accepted_candidates.sort(key=ranking_key, reverse=True)
                all_results.extend(accepted_candidates[:result_limit])
                app.c.l.emit("群系排查完成：检查 {} 个，保留 {} 个，过滤 {} 个，用时 {}。".format(
                    processed, accepted_this_seed, filtered_this_seed, format_elapsed(time.time() - dd_start_time)))
            else:
                candidates.sort(key=ranking_key, reverse=True)
                if scan_y:
                    # Y changes the actual score, so it must run before the
                    # per-seed Top-N cut. Cutting first can discard a candidate
                    # that should move into the final ranking after Y refinement.
                    candidates = apply_y_after_selection(sd, candidates, "精准候选")
                    candidates.sort(key=ranking_key, reverse=True)
                # Keep only the requested Top-N from each seed after every score
                # component that can affect ranking has been finalized.
                candidates = candidates[:result_limit]
                all_results.extend(candidates)

            emit_progress(((idx + 1) / total_seeds) * 95)

        if app.c.cancel:
            app.c.t.emit("任务已取消 | 已用时 {}".format(format_elapsed(time.time() - task_start_time)))
            emit_progress(0)
            return
        if not all_results:
            app.c.l.emit("未发现任何完全符合条件的区块。")
            app.c.t.emit("未找到结果 | 用时 {}".format(format_elapsed(time.time() - task_start_time)))
            emit_progress(0)
            return

        all_results.sort(key=ranking_key, reverse=True)
        best = all_results[0]
        size, block_x, block_z, chunk_x, chunk_z, seed, obs_count = best[:7]
        afk_y = best[7] if len(best) > 7 else None

        top_50_results = []
        for i, item in enumerate(all_results[:result_limit]):
            _s, _bx, _bz, _cx, _cz, _sd, _obs = item[:7]
            _ay = item[7] if len(item) > 7 else None
            top_50_results.append((i + 1, _sd, _s, _obs, _bx, _bz, _ay))

        obs_text = str(obs_count) if is_precise else "未计算(快速模式)"
        y_text = f", 挂机Y: {afk_y}" if afk_y is not None else ""
        app.c.l.emit("最优区块 - 种子: {}, 规模: {}, 刷怪格数: {}{}".format(seed, size, obs_text, y_text))
        emit_progress(96)
        app.c.t.emit("正在生成结果图片...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(APP_DIR, "images", f"map_{timestamp}.png")
        create_slime_map(seed, block_x, block_z, dest)

        # Minecraft block-coordinate conversion uses floor division.  int(x/8)
        # truncates toward zero and is off by one for negative non-multiples.
        nether_x = block_x // 8
        nether_z = block_z // 8
        algorithm_used = " / ".join(sorted(algorithms_used)) if algorithms_used else str(engine_choice)
        search_params = {
            "seeds": [int(v) for v in seeds],
            "radius": int(rd_max),
            "center_x": int(app.config.search_center_x),
            "center_z": int(app.config.search_center_z),
            "min_radius": int(rd_min),
            "min_size": int(ms),
            "max_size": int(max_s) if use_range else None,
            "use_range": bool(use_range),
            "engine": str(engine_choice),
            "minecraft_version": str(app.config.minecraft_version),
            "precise_afk": bool(is_precise),
            "scan_y": bool(scan_y),
            "result_limit": int(result_limit),
        }
        app.c.search_done.emit({
            "main_pos": (block_x, block_z),
            "nether_pos": (nether_x, nether_z),
            "current_seed": seed,
            "current_size": size,
            "current_obs_count": obs_count,
            "current_afk_y": afk_y,
            "current_algorithm": algorithm_used,
            "search_params": search_params,
            "history_timestamp": timestamp,
            "history_image": dest,
            "ranked_results": top_50_results,
            "result_limit": int(result_limit)
        })
        app.c.i.emit(dest)
        afk_display = f"({block_x}, {afk_y}, {block_z})" if afk_y is not None else f"({block_x}, {block_z})"
        app.c.info.emit("种子: {} | 规模: {} | 刷怪格数: {} | 挂机点: {} | 地狱: ({}, {})".format(
            seed, size, obs_text, afk_display, nether_x, nether_z))

        total_elapsed = format_elapsed(time.time() - task_start_time)
        app.c.l.emit("任务完成，总耗时：{}。".format(total_elapsed))
        app.c.t.emit("完成 | 总耗时 {}".format(total_elapsed))
        emit_progress(100)

    except Exception as e:
        app.c.l.emit("运行错误: {}".format(e))
        app.c.t.emit("运行错误")
    finally:
        # Million-candidate searches can make a full forced collection pause
        # for a noticeable time after the result and "任务完成" were already
        # emitted. Candidate tuples are acyclic and are reclaimed by normal
        # reference counting, so restore the UI immediately.
        app.c.btn_state.emit(True)

def generate_manual_image(app, seed, block_x, block_z):
    try:
        if not os.path.exists(os.path.join(APP_DIR, "images")): os.makedirs(os.path.join(APP_DIR, "images"))
        dest = os.path.join(APP_DIR, "images", f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        create_slime_map(seed, block_x, block_z, dest)
        obs_count = calc_spawnable_spaces(seed, block_x, block_z)
        nether_x = block_x // 8
        nether_z = block_z // 8
        app.c.manual_done.emit({"main_pos": (block_x, block_z), "nether_pos": (nether_x, nether_z), "current_seed": seed, "current_size": "M", "current_obs_count": obs_count, "current_afk_y": None})
        app.c.i.emit(dest)
        app.c.info.emit(f"种子: {seed} | 刷怪格数: {obs_count} | 主世界: ({block_x}, {block_z}) | 地狱: ({nether_x}, {nether_z})")
    except Exception as e: app.c.l.emit(str(e))

_ICON_CACHE = {}

# ===== UI =====
def _qcolor_key(color):
    c = QColor(color)
    return (c.red(), c.green(), c.blue(), c.alpha())

def _draw_icon_pixmap(drawer, color=None, size=24):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        drawer(painter, QColor(color) if color is not None else None)
    finally:
        painter.end()
    return pixmap

def _cached_icon(key, maker):
    icon = _ICON_CACHE.get(key)
    if icon is None:
        icon = maker()
        _ICON_CACHE[key] = icon
    return icon

def create_slime_icon():
    def make():
        def draw(p, _):
            p.setBrush(QColor(16, 212, 114))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(2, 2, 20, 20, 4, 4)
            p.setBrush(QColor(40, 60, 50))
            p.drawRect(6, 8, 4, 4)
            p.drawRect(14, 8, 4, 4)
            p.drawRect(10, 14, 4, 2)
        return QIcon(_draw_icon_pixmap(draw))
    return _cached_icon(('slime',), make)

def create_gear_icon(color=None):
    color = QColor(200, 200, 200) if color is None else QColor(color)
    key = ('gear', _qcolor_key(color))
    def make():
        def draw(p, c):
            p.setPen(QPen(c, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(7, 7, 10, 10)
            for i in range(8):
                angle = i * math.pi / 4
                x1 = 12 + 5 * math.cos(angle)
                y1 = 12 + 5 * math.sin(angle)
                x2 = 12 + 9 * math.cos(angle)
                y2 = 12 + 9 * math.sin(angle)
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        return QIcon(_draw_icon_pixmap(draw, color))
    return _cached_icon(key, make)

def create_fluent_icon(icon_color=None):
    icon_color = QColor(200, 200, 200) if icon_color is None else QColor(icon_color)
    key = ('fluent', _qcolor_key(icon_color))
    def make():
        def draw(p, c):
            p.setPen(QPen(c, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(2, 2, 8, 8, 1.5, 1.5)
            p.drawPolygon(QPolygonF([
                QPointF(18, 2), QPointF(22, 6), QPointF(18, 10), QPointF(14, 6)
            ]))
            p.drawRoundedRect(14, 14, 8, 8, 1.5, 1.5)
            path = QPainterPath()
            for i in range(12):
                angle = i * math.pi / 6
                radius = 4.2 if i % 2 == 0 else 2.2
                x = 6 + radius * math.cos(angle)
                y = 18 + radius * math.sin(angle)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.closeSubpath()
            p.drawPath(path)
            p.drawEllipse(5, 17, 2, 2)
        icon = QIcon()
        icon.addPixmap(_draw_icon_pixmap(draw, icon_color), QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(_draw_icon_pixmap(draw, QColor(255, 255, 255)), QIcon.Mode.Normal, QIcon.State.On)
        return icon
    return _cached_icon(key, make)

def create_history_icon(color=None):
    color = QColor(200, 200, 200) if color is None else QColor(color)
    key = ('history', _qcolor_key(color))
    def make():
        def draw(p, c):
            p.setPen(QPen(c, 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(3, 3, 18, 18)
            p.drawLine(12, 12, 12, 7)
            p.drawLine(12, 12, 16, 14)
        return QIcon(_draw_icon_pixmap(draw, color))
    return _cached_icon(key, make)


def create_burger_icon(color=None):
    color = QColor(200, 200, 200) if color is None else QColor(color)
    key = ('burger', _qcolor_key(color))
    def make():
        def draw(p, c):
            p.setPen(QPen(c, 2))
            for y in (6, 12, 18):
                p.drawLine(4, y, 20, y)
        return QIcon(_draw_icon_pixmap(draw, color))
    return _cached_icon(key, make)


class SlimeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.c = C()
        self.config = Config()
        set_cubiomes_mc_version(self.config.minecraft_version)
        self.main_pos = self.nether_pos = self.current_seed = self.current_size = self.current_image = self.current_obs_count = self.current_afk_y = None
        self.current_algorithm = None
        self.is_sidebar_expanded = True
        self._log_lines = []
        self.top_50_results = []
        self._rank_render_token = 0
        self._progress_busy = False
        self._search_cancelled = False
        self.active_engine = ""

        # ===== 彩蛋状态 =====
        self._gpu_perf_click_times = []
        self._gpu_perf_easter_until = 0.0
        self._gpu_perf_restore_text = ""
        self._pause_click_times = []
        self._copy_easter_count = 0
        self._empty_history_open_count = 0
        self._hamburger_click_times = []
        self._settings_cancel_count = 0
        self._ranking_double_click_counts = {}
        self._projection_save_cancel_count = 0
        self._rank_one_apply_count = 0
        self._resize_last_width = None
        self._resize_last_dir = 0
        self._resize_reversal_times = []
        self._resize_easter_cooldown_until = 0.0

        # External palette overrides the built-in floor preview colors when available.
        self.color_card = {}
        self.floor_color_card = {}
        self.color_card_warning = ""
        self._load_color_card()
        self.floor_color_card = self._default_color_card()
        self.floor_color_card.update(self.color_card)
        self._floor_block_color_cache = {}

        self.initUI()
        self.c.l.connect(self.upd_log)
        self.c.i.connect(self.sw)
        self.c.p.connect(self._set_progress_value)
        self.c.t.connect(self.update_time)
        self.c.info.connect(self.info.setText)
        self.c.btn_state.connect(self.update_btns)
        self.native_progress_timer = QTimer(self)
        self.native_progress_timer.setInterval(500)
        self.native_progress_timer.timeout.connect(self.poll_native_progress)
        self._native_scan_active = False
        self._native_scan_started = 0.0
        self._native_scan_base_pct = 0.0
        self._native_scan_total_seeds = 1
        self._native_scan_total_centers = 1
        self._native_scan_label = "原生"
        self._native_scan_lib = None
        self._gpu_perf_samples = []
        self._gpu_perf_prev_centers = 0
        self._gpu_perf_prev_work_ns = 0
        self._gpu_perf_total_centers = 0
        self._gpu_perf_total_work_ns = 0
        self._search_in_progress = False
        self._search_started_at = 0.0
        self._search_paused = False
        self._pause_started_at = 0.0
        self._native_pause_accum = 0.0
        self._search_soft_ceiling = 34
        self.c.native_scan_state.connect(self._set_native_scan_state)

        self.c.search_done.connect(self._on_search_done)
        self.c.manual_done.connect(self._on_manual_done)
        self.c.msg_box.connect(self._show_thread_message)
        self.c.widget_enabled.connect(self._set_widget_enabled)
        self.c.widget_text.connect(self._set_widget_text)

        self.setup_shortcuts()
        QTimer.singleShot(0, self._report_native_status)
        if self.color_card_warning:
            QTimer.singleShot(0, self._report_color_card_warning)


    def open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("高级设置")
        dlg.setFixedSize(620, 560)
        dlg.setStyleSheet(self.styleSheet())
        v = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_v = QVBoxLayout(body)

        g1 = QGroupBox("高级搜索限制")
        l1 = QVBoxLayout(g1)
        mc_row = QHBoxLayout()
        mc_row.addWidget(QLabel("Minecraft 版本:"))
        mc_version_combo = QComboBox()
        for label, value in (
            ("1.19", "1.19"),
            ("1.20.x", "1.20"),
            ("1.21.0-1.21.1", "1.21.1"),
            ("1.21.2-1.21.3", "1.21.3"),
            ("1.21.4", "1.21.4"),
            ("1.21.5", "1.21.5"),
            ("1.21.6-1.21.8", "1.21.6"),
            ("1.21.9-1.21.10", "1.21.9"),
            ("1.21.11", "1.21.11"),
            ("26.1", "26.1"),
            ("26.2", "26.2"),
        ):
            mc_version_combo.addItem(label, value)
        current_index = mc_version_combo.findData(self.config.minecraft_version)
        mc_version_combo.setCurrentIndex(max(0, current_index))
        mc_version_combo.setToolTip("只影响 cubiomes 的出生点、深暗与蘑菇岛等世界生成辅助判断；史莱姆区块本身与版本无关。")
        mc_row.addWidget(mc_version_combo)
        mc_row.addStretch()
        l1.addLayout(mc_row)
        cb_range = QCheckBox("启用最大规模限制")
        cb_range.setChecked(self.config.use_range)
        l1.addWidget(cb_range)
        cb_min_rad = QCheckBox("启用中心排空 (最小搜索半径)")
        cb_min_rad.setChecked(self.config.use_min_radius)
        l1.addWidget(cb_min_rad)
        body_v.addWidget(g1)

        g2 = QGroupBox(f"并发性能 (检测到 {self.config.max_sys_threads} 核心)")
        l2 = QVBoxLayout(g2)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("分配线程数:"))
        thread_spin = QSpinBox()
        thread_spin.setRange(1, self.config.max_sys_threads)
        thread_spin.setValue(self.config.threads)
        thread_spin.setToolTip("主要影响 CPU 模式、Python 后处理和群系检查的并发；不会让 CUDA 主扫描按这个数字开更多 GPU 线程。")
        row1.addWidget(thread_spin)
        row1.addStretch()
        l2.addLayout(row1)
        thread_slider = QSlider(Qt.Orientation.Horizontal)
        thread_slider.setRange(1, self.config.max_sys_threads)
        thread_slider.setValue(self.config.threads)
        l2.addWidget(thread_slider)
        body_v.addWidget(g2)
        thread_spin.valueChanged.connect(thread_slider.setValue)
        thread_slider.valueChanged.connect(thread_spin.setValue)

        g3 = QGroupBox("排名、候选与精准比对")
        form = QFormLayout(g3)

        result_limit_spin = QSpinBox()
        result_limit_spin.setRange(1, MAX_RESULT_LIMIT)
        result_limit_spin.setValue(self.config.result_limit)
        result_limit_spin.setToolTip("最终前端保留并显示多少名结果。默认 50；只影响最终 Top-N 数量，不改变 GPU 扫图范围。")
        form.addRow("最终显示排名数量:", result_limit_spin)

        buffer_spin = QSpinBox()
        buffer_spin.setRange(1000, MAX_CANDIDATE_BUFFER)
        buffer_spin.setSingleStep(50000)
        buffer_spin.setValue(self.config.candidate_buffer)
        buffer_spin.setToolTip("GPU/CPU DLL 最多把多少个候选坐标交给 Python 做后处理。不是扫描上限；扫描仍会完整进行。")
        form.addRow("最多回传候选数量:", buffer_spin)

        pool_spin = QSpinBox()
        pool_spin.setRange(0, 20000)
        pool_spin.setSingleStep(50)
        pool_spin.setValue(self.config.precise_target_pool)
        pool_spin.setSpecialValueText("自动")
        pool_spin.setToolTip("精准模式不会把所有候选都算到底，而是先用上界筛选，保留这批最有希望的候选做完整刷怪格数计算。0=自动。")
        form.addRow("进入完整精准评分的候选数:", pool_spin)

        chunk_spin = QSpinBox()
        chunk_spin.setRange(128, 20000)
        chunk_spin.setSingleStep(128)
        chunk_spin.setValue(self.config.native_score_chunk)
        chunk_spin.setToolTip("一次交给原生 CPU/GPU 评分函数多少个候选。大一点通常吞吐更好，但单批耗时更长、取消响应稍慢。")
        form.addRow("每批精准评分数量:", chunk_spin)

        exhaustive_cb = QCheckBox("所有回传候选都做完整精准评分（非常慢）")
        exhaustive_cb.setChecked(self.config.precise_exhaustive)
        exhaustive_cb.setToolTip("关闭时使用智能上界剪枝；开启后跳过剪枝，对候选缓冲里的全部候选计算刷怪格数。大范围不推荐。")
        form.addRow("全量精准模式:", exhaustive_cb)

        hint = QLabel(
            "简单理解：GPU先完整扫地图 → 回传一批最好的候选 → 精准模式再从里面挑最有希望的一批算刷怪格数 → 最终只显示Top-N。\n"
            "正常使用建议：排名50、回传100万、精准候选自动、每批8192、全量精准关闭。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #aaa;")
        form.addRow("", hint)
        body_v.addWidget(g3)

        body_v.addStretch()
        scroll.setWidget(body)
        v.addWidget(scroll)

        btns = QHBoxLayout()
        save_btn, cancel_btn = QPushButton("保存"), QPushButton("取消")
        save_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        v.addLayout(btns)

        dialog_result = dlg.exec()
        if dialog_result:
            self.config.use_range = cb_range.isChecked()
            self.config.use_min_radius = cb_min_rad.isChecked()
            self.config.minecraft_version = str(mc_version_combo.currentData())
            set_cubiomes_mc_version(self.config.minecraft_version)
            self.config.threads = thread_spin.value()
            self.config.result_limit = result_limit_spin.value()
            self.config.candidate_buffer = buffer_spin.value()
            self.config.precise_target_pool = pool_spin.value()
            self.config.native_score_chunk = chunk_spin.value()
            self.config.precise_exhaustive = exhaustive_cb.isChecked()
            self.config.save()
            self.max_label.setVisible(self.config.use_range)
            self.m_max.setVisible(self.config.use_range)
            self.rad_min_label.setVisible(self.config.use_min_radius)
            self.r_inner.setVisible(self.config.use_min_radius)
            self.upd_log("高级设置已保存：Minecraft {}，候选缓冲 {:,}，智能结果池 {}，原生批量 {:,}，{}。".format(
                mc_version_combo.currentText(),
                self.config.candidate_buffer,
                "自动" if self.config.precise_target_pool == 0 else f"{self.config.precise_target_pool:,}",
                self.config.native_score_chunk,
                "全量精准" if self.config.precise_exhaustive else "智能精准"
            ))
        else:
            self._settings_cancel_count += 1
            if self._settings_cancel_count >= 20:
                self._settings_cancel_count = 0
                self.upd_log("那你打开它干什么")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        now = time.monotonic()
        width = event.size().width()
        if self._resize_last_width is not None:
            delta = width - self._resize_last_width
            direction = 1 if delta >= 3 else (-1 if delta <= -3 else 0)
            if direction and self._resize_last_dir and direction != self._resize_last_dir:
                self._resize_reversal_times = [
                    t for t in self._resize_reversal_times if now - t <= 2.5]
                self._resize_reversal_times.append(now)
                if (len(self._resize_reversal_times) >= 6
                        and now >= self._resize_easter_cooldown_until
                        and hasattr(self, "time_label")
                        and not getattr(self, "_search_in_progress", False)):
                    self._resize_reversal_times.clear()
                    self._resize_easter_cooldown_until = now + 10.0
                    self.time_label.setText("别拽了")
                    QTimer.singleShot(2000, self._restore_resize_easter_text)
            if direction:
                self._resize_last_dir = direction
        self._resize_last_width = width
        if hasattr(self, 'floor_scroller') and self.stacked.currentIndex() == 1:
            self.trigger_floor_preview_update()

    def _restore_resize_easter_text(self):
        if hasattr(self, "time_label") and self.time_label.text() == "别拽了":
            self.time_label.setText("准备就绪")

    def _set_gpu_perf_text(self, text):
        if time.monotonic() < self._gpu_perf_easter_until:
            return
        self.gpu_perf_label.setText(text)

    def _on_gpu_perf_click(self):
        now = time.monotonic()
        self._gpu_perf_click_times = [t for t in self._gpu_perf_click_times if now - t <= 2.5]
        self._gpu_perf_click_times.append(now)
        if len(self._gpu_perf_click_times) < 7:
            return
        self._gpu_perf_click_times.clear()
        self._gpu_perf_restore_text = self.gpu_perf_label.text()
        self._gpu_perf_easter_until = now + 2.0
        self.gpu_perf_label.setText("你到底在看什么")
        QTimer.singleShot(2000, self._restore_gpu_perf_easter)

    def _restore_gpu_perf_easter(self):
        self._gpu_perf_easter_until = 0.0
        if self.gpu_perf_label.text() == "你到底在看什么":
            self.gpu_perf_label.setText(self._gpu_perf_restore_text or "-- B/s")

    def get_floor_material_id(self) -> str:
        if self.chk_custom_floor_material.isChecked():
            return self._normalize_minecraft_block_id(self.proj_custom_block.text())
        return "minecraft:" + self.glass_options[self.proj_glass.currentText()]

    def _toggle_floor_material_input(self, checked):
        self.proj_glass_stack.setCurrentIndex(1 if checked else 0)
        if checked:
            # Avoid an empty custom ID causing repeated preview exceptions while
            # the user has just switched to manual material mode.
            if not self.proj_custom_block.text().strip():
                self.proj_custom_block.setText("minecraft:stone")
            self.proj_custom_block.setFocus()
        self.trigger_floor_preview_update()

    def _normalize_minecraft_block_id(self, block_id):
        block_id = (block_id or "").strip().lower().replace(" ", "")
        if not block_id:
            raise ValueError("材质不能为空。示例：minecraft:stone 或 stone")
        if "[" in block_id or "]" in block_id:
            raise ValueError("这里只能填写方块ID，不能填写方块状态。示例：minecraft:stone")
        if ":" not in block_id:
            block_id = "minecraft:" + block_id
        if not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", block_id):
            raise ValueError("材质格式错误。示例：minecraft:stone、stone、minecraft:tinted_glass")
        return block_id

    def _report_native_status(self):
        try:
            self.upd_log("cubiomes.dll：已加载" if cb else "cubiomes.dll：未加载")
            self.upd_log(f"GPU：{GPU_DEVICE_NAME}" if GPU_AVAILABLE else "GPU：未检测到可用设备")
            self.upd_log("GPU算法：已加载" if gpu_algorithm_available() else "GPU算法：未加载")
            self.upd_log("CPU驱动：已加载" if cpu_algorithm_available() else "CPU驱动：未加载")
            if not gpu_algorithm_available() and not cpu_algorithm_available():
                self.upd_log("原生算法：未加载，Auto 将使用 Python 后备模式")
        except Exception:
            pass

    def _set_widget_text(self, widget, text):
        if widget is not None:
            widget.setText(text)

    def _set_widget_enabled(self, widget, enabled):
        if widget is not None:
            widget.setEnabled(enabled)

    def _show_thread_message(self, level, title, text):
        if level == "critical":
            QMessageBox.critical(self, title, text)
        elif level == "warning":
            QMessageBox.warning(self, title, text)
        else:
            QMessageBox.information(self, title, text)

    def get_floor_block_color(self, block):
        """Floor preview color.

        Floor generation keeps the built-in fallback palette, but external
        color_card entries override built-in colors when present. Unknown
        custom floor blocks still render as visible gray.
        """
        try:
            key = self._normalize_minecraft_block_id(str(block))
        except Exception:
            return QColor(96, 96, 96, 255)

        cache = self._floor_block_color_cache
        cached = cache.get(key)
        if cached is not None:
            return cached

        color = self._lookup_color_from_palette(self.floor_color_card, key, QColor(110, 110, 110, 255))
        cache[key] = color
        return color

    def _lookup_color_from_palette(self, palette, block, fallback_color):
        try:
            block = self._normalize_minecraft_block_id(str(block))
        except Exception:
            return fallback_color
        color = palette.get(block)
        if color is None:
            short_name = block.split(":", 1)[1]
            for name, candidate_color in palette.items():
                if name.split(":", 1)[-1] == short_name:
                    color = candidate_color
                    break
        return color if color is not None else fallback_color

    def _report_color_card_warning(self):
        try:
            self.upd_log(self.color_card_warning)
            QMessageBox.warning(self, "色卡提示", self.color_card_warning)
        except Exception:
            pass

    def _load_color_card(self):
        path = find_resource("color_card")
        errors = []
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line_no, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split()
                        if len(parts) != 4:
                            errors.append(f"第 {line_no} 行格式错误")
                            continue
                        key, r, g, b = parts
                        key = self._normalize_minecraft_block_id(key)
                        try:
                            self.color_card[key] = QColor(
                                max(0, min(255, int(r))),
                                max(0, min(255, int(g))),
                                max(0, min(255, int(b))),
                                255
                            )
                        except Exception:
                            errors.append(f"第 {line_no} 行颜色不是整数")
            except Exception as e:
                errors.append(str(e))
        if not self.color_card:
            self.color_card_warning = (
                "未读取到有效的 color_card 色卡文件；地板预览将使用内置色卡。\n"
                "如需自定义颜色，请确认程序目录存在 color_card，且每行格式为：minecraft:block r g b"
            )
        elif errors:
            self.color_card_warning = "color_card 部分行无法解析，已跳过：" + "；".join(errors[:5])

    def _default_color_card(self):
        return {
            "minecraft:air": QColor(0, 0, 0, 0),
            "minecraft:cave_air": QColor(0, 0, 0, 0),
            "minecraft:void_air": QColor(0, 0, 0, 0),
            "minecraft:obsidian": QColor(18, 12, 28, 255),
            "minecraft:nether_portal": QColor(120, 35, 220, 210),
            "minecraft:composter": QColor(130, 95, 45, 255),
            "minecraft:lightning_rod": QColor(230, 165, 70, 255),
            "minecraft:magma_block": QColor(235, 70, 20, 255),
            "minecraft:orange_concrete": QColor(235, 90, 25, 255),
            "minecraft:soul_sand": QColor(95, 70, 55, 255),
            "minecraft:wither_rose": QColor(20, 20, 20, 255),
            "minecraft:turtle_egg": QColor(232, 225, 192, 255),
            "minecraft:glass": QColor(140, 200, 225, 140),
            "minecraft:white_stained_glass": QColor(245, 245, 245, 190),
            "minecraft:orange_stained_glass": QColor(240, 118, 19, 190),
            "minecraft:magenta_stained_glass": QColor(199, 50, 185, 190),
            "minecraft:light_blue_stained_glass": QColor(58, 175, 217, 190),
            "minecraft:yellow_stained_glass": QColor(248, 198, 39, 190),
            "minecraft:lime_stained_glass": QColor(112, 185, 25, 190),
            "minecraft:pink_stained_glass": QColor(243, 140, 170, 190),
            "minecraft:gray_stained_glass": QColor(71, 79, 82, 190),
            "minecraft:light_gray_stained_glass": QColor(157, 157, 151, 190),
            "minecraft:cyan_stained_glass": QColor(21, 137, 145, 190),
            "minecraft:purple_stained_glass": QColor(137, 41, 176, 190),
            "minecraft:blue_stained_glass": QColor(51, 76, 178, 190),
            "minecraft:brown_stained_glass": QColor(114, 71, 40, 190),
            "minecraft:green_stained_glass": QColor(97, 122, 41, 190),
            "minecraft:red_stained_glass": QColor(160, 39, 34, 190),
            "minecraft:black_stained_glass": QColor(20, 20, 25, 230),
        }

    def upd_log(self, m):
        self.log.append(m)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _set_progress_busy(self, busy):
        """Switch the progress bar between numeric percent and native-scan busy mode.

        Some native DLL builds do not report fine-grained progress during the
        blocking CPU/GPU scan, so showing a fake slowly-increasing percent can
        still be overwritten by old 2% signals on some machines. Busy mode is
        deterministic: while native scanning is running, the bar animates instead
        of staying at 2%; once scoring/filtering starts we restore 0-100 percent.
        """
        try:
            self._progress_busy = bool(busy)
            if busy:
                self.progress.setRange(0, 0)
                self.progress.setFormat("")
            else:
                if self.progress.minimum() == 0 and self.progress.maximum() == 0:
                    self.progress.setRange(0, 100)
                    self.progress.setFormat("%p%")
        except Exception:
            pass

    def _set_progress_value(self, value):
        try:
            value = max(0, min(100, int(value)))
        except Exception:
            return
        # Ignore the old 1%-34% numeric signals while the native scan is in
        # indeterminate mode. These are exactly what made the bar appear stuck at
        # 2%. The first real post-scan stage (35%+) restores normal percent mode.
        if self._progress_busy:
            if value in (0, 100) or value >= 35:
                self._set_progress_busy(False)
            else:
                return
        # During a running search, queued older progress signals must not pull
        # the bar back after a newer stage has already moved it forward.
        if self._search_in_progress and value not in (0, 100):
            if value < self.progress.value():
                return
        self.progress.setValue(value)

    def _apply_run_state(self, state):
        self.main_pos = state.get("main_pos")
        self.nether_pos = state.get("nether_pos")
        self.current_seed = state.get("current_seed")
        self.current_size = state.get("current_size")
        self.current_obs_count = state.get("current_obs_count")
        self.current_afk_y = state.get("current_afk_y")
        self.current_algorithm = state.get("current_algorithm", self.current_algorithm)

    def _on_search_done(self, state):
        self._apply_run_state(state)
        self.top_50_results = state.get("ranked_results", [])
        self._refresh_rank_controls()
        if self.current_seed is not None: self.proj_manual_seed.setText(str(self.current_seed))
        if self.main_pos is not None:
            self.proj_manual_x.setText(str(self.main_pos[0]))
            self.proj_manual_z.setText(str(self.main_pos[1]))
        self.proj_manual_y.setText("" if self.current_afk_y is None else str(self.current_afk_y))
        self.trigger_floor_preview_update()
        self._save_search_history(state)

    def _refresh_rank_controls(self):
        results = self.top_50_results
        count = len(results)
        enabled = count > 0
        self.rank_select_spin.setEnabled(enabled)
        self.rank_select_spin.setRange(1, max(1, count))
        if enabled:
            self.rank_select_spin.setValue(min(max(1, self.rank_select_spin.value()), count))
            self.result_status_label.setText(f"已保留 {count} 个排名结果 · 当前使用 #1")
            self._update_rank_detail(results[0])
        else:
            self.rank_select_spin.setValue(1)
            self.result_status_label.setText("尚未产生排名结果")
            self.rank_detail_label.setText("搜索完成后，可直接选择第 1～N 名作为当前坐标和地板投影中心。")
        self.rank_apply_btn.setEnabled(enabled)
        self.rank_list_btn.setEnabled(enabled)
        self.rank_export_btn.setEnabled(enabled)
        self.rank_toggle_btn.setEnabled(enabled)

    def _toggle_rank_panel(self):
        expanded = not self.rank_panel.isVisible()
        self.rank_panel.setVisible(expanded)
        self.rank_toggle_btn.setText("收起排名" if expanded else "查看排名")

    def _update_rank_detail(self, entry):
        if not entry:
            return
        rank, seed, size, obs, bx, bz, ay = entry[:7]
        obs_text = "未计算" if obs is None else str(obs)
        y_text = "未扫描" if ay is None else str(ay)
        extra = " · 我知道这是第一名" if rank == 1 and getattr(self, "_rank_one_easter_active", False) else ""
        self.rank_detail_label.setText(
            f"#{rank} · 种子 {seed} · 规模 {size} · 刷怪格数 {obs_text} · "
            f"主世界 ({bx}, {y_text}, {bz}) · 地狱 ({bx // 8}, {bz // 8}){extra}")

    def _apply_rank_from_button(self):
        if self.rank_select_spin.value() == 1 and self.top_50_results:
            self._rank_one_apply_count += 1
            if self._rank_one_apply_count >= 7:
                self._rank_one_apply_count = 0
                self._rank_one_easter_active = True
                QTimer.singleShot(3500, self._clear_rank_one_easter)
        self.apply_ranked_result()

    def _clear_rank_one_easter(self):
        self._rank_one_easter_active = False
        if self.top_50_results and self.rank_select_spin.value() == 1:
            self._update_rank_detail(self.top_50_results[0])

    def _record_ranking_double_click(self, entry):
        key = (entry[1], entry[4], entry[5])
        count = self._ranking_double_click_counts.get(key, 0) + 1
        if count >= 5:
            self._ranking_double_click_counts[key] = 0
            self.upd_log("我知道你喜欢这个")
        else:
            self._ranking_double_click_counts[key] = count

    def preview_ranked_result(self, rank):
        results = self.top_50_results
        if not results:
            return
        rank = max(1, min(len(results), int(rank)))
        self._update_rank_detail(results[rank - 1])

    def apply_ranked_result(self, rank=None):
        results = self.top_50_results
        if not results:
            return
        if rank is None:
            rank = self.rank_select_spin.value()
        rank = max(1, min(len(results), int(rank)))
        self.rank_select_spin.setValue(rank)
        entry = results[rank - 1]
        _rank, seed, size, obs, bx, bz, ay = entry[:7]
        self.current_seed = seed
        self.current_size = size
        self.current_obs_count = obs
        self.current_afk_y = ay
        self.main_pos = (bx, bz)
        self.nether_pos = (bx // 8, bz // 8)
        self.result_status_label.setText(f"已保留 {len(results)} 个排名结果 · 当前使用 #{rank}")
        self._update_rank_detail(entry)
        self.proj_manual_seed.setText(str(seed))
        self.proj_manual_x.setText(str(bx))
        self.proj_manual_z.setText(str(bz))
        self.proj_manual_y.setText("" if ay is None else str(ay))
        self.trigger_floor_preview_update()
        obs_text = "未计算(快速模式)" if obs is None else str(obs)
        y_text = f", 挂机Y: {ay}" if ay is not None else ""
        self.info.setText(
            f"排名 #{rank} | 种子: {seed} | 规模: {size} | 刷怪格数: {obs_text} | "
            f"主世界: ({bx}, {bz}){y_text} | 地狱: ({bx // 8}, {bz // 8})")
        self.upd_log(f"已切换到排名 #{rank}：种子 {seed}，坐标 ({bx}, {bz})。")

        self._rank_render_token += 1
        token = self._rank_render_token
        def render_selected():
            try:
                os.makedirs(os.path.join(APP_DIR, "images"), exist_ok=True)
                dest = os.path.join(APP_DIR, "images", f"rank_{rank}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png")
                create_slime_map(seed, bx, bz, dest)
                if token == self._rank_render_token:
                    self.c.i.emit(dest)
            except Exception as e:
                self.c.l.emit(f"排名 #{rank} 图片生成失败: {e}")
        threading.Thread(target=render_selected, daemon=True).start()

    def show_rankings_dialog(self):
        results = self.top_50_results
        if not results:
            self.upd_log("当前没有排名结果。")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"排名 · {len(results)} 个结果")
        dlg.resize(900, 590)
        dlg.setStyleSheet(self.styleSheet())
        v = QVBoxLayout(dlg)
        top = QHBoxLayout()
        hint = QLabel("双击结果即可使用")
        hint.setObjectName("Muted")
        jump = QLineEdit()
        jump.setFixedWidth(90)
        jump.setPlaceholderText("排名 1-N")
        jump_btn = QPushButton("跳转")
        top.addWidget(hint)
        top.addStretch()
        top.addWidget(jump)
        top.addWidget(jump_btn)
        v.addLayout(top)

        table = QTableWidget(len(results), 9)
        table.setHorizontalHeaderLabels(["排名", "种子", "规模", "刷怪格数", "主世界 X", "Y", "主世界 Z", "地狱 X", "地狱 Z"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        for row, entry in enumerate(results):
            rank, seed, size, obs, bx, bz, ay = entry[:7]
            values = (rank, seed, size, "" if obs is None else obs, bx, "" if ay is None else ay, bz, bx // 8, bz // 8)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col != 1:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                table.setItem(row, col, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(table, 1)

        bottom = QHBoxLayout()
        export_btn = QPushButton("导出 CSV")
        use_btn = QPushButton("使用所选")
        use_btn.setObjectName("Primary")
        close_btn = QPushButton("关闭")
        bottom.addWidget(export_btn)
        bottom.addStretch()
        bottom.addWidget(close_btn)
        bottom.addWidget(use_btn)
        v.addLayout(bottom)

        def use_row(row=None, _col=None):
            if row is None:
                row = table.currentRow()
            if row is None or row < 0:
                return
            self.apply_ranked_result(row + 1)
            dlg.accept()

        def jump_to_rank():
            try:
                rank = int(jump.text().strip())
            except Exception:
                jump.setText("")
                jump.setPlaceholderText(f"1-{len(results)}")
                return
            if rank < 1 or rank > len(results):
                jump.setText("")
                jump.setPlaceholderText(f"1-{len(results)}")
                return
            table.selectRow(rank - 1)
            table.scrollToItem(table.item(rank - 1, 0), QAbstractItemView.ScrollHint.PositionAtCenter)

        def on_double_clicked(row, col):
            if 0 <= row < len(results):
                self._record_ranking_double_click(results[row])
            use_row(row, col)

        table.cellDoubleClicked.connect(on_double_clicked)
        use_btn.clicked.connect(lambda: use_row())
        jump_btn.clicked.connect(jump_to_rank)
        jump.returnPressed.connect(jump_to_rank)
        export_btn.clicked.connect(self.export_results)
        close_btn.clicked.connect(dlg.reject)
        current_rank = min(max(1, self.rank_select_spin.value()), len(results))
        table.selectRow(current_rank - 1)
        dlg.exec()

    def _on_manual_done(self, state):
        self._apply_run_state(state)

    def _reset_gpu_perf_stats(self):
        self._gpu_perf_samples = []
        self._gpu_perf_prev_centers = 0
        self._gpu_perf_prev_work_ns = 0
        self._gpu_perf_total_centers = 0
        self._gpu_perf_total_work_ns = 0

    def _sample_gpu_perf(self, lib):
        if not lib:
            return None
        try:
            centers = max(0, int(lib.get_processed_centers()))
            work_ns = max(0, int(lib.get_gpu_scan_work_ns()))
            prev_centers = self._gpu_perf_prev_centers
            prev_work_ns = self._gpu_perf_prev_work_ns
            delta_centers = centers - prev_centers
            delta_work_ns = work_ns - prev_work_ns
            self._gpu_perf_prev_centers = centers
            self._gpu_perf_prev_work_ns = work_ns
            self._gpu_perf_total_centers = centers
            self._gpu_perf_total_work_ns = work_ns
            if delta_centers > 0 and delta_work_ns > 0:
                rate_b = (delta_centers / (delta_work_ns / 1e9)) / 1e9
                if rate_b > 0:
                    self._gpu_perf_samples.append(rate_b)
                    return rate_b
        except Exception:
            return None
        return None

    def _finish_gpu_perf_stats(self, lib):
        self._sample_gpu_perf(lib)
        samples = self._gpu_perf_samples
        total_centers = self._gpu_perf_total_centers
        total_work_ns = self._gpu_perf_total_work_ns
        if not samples or total_centers <= 0 or total_work_ns <= 0:
            return None
        peak_b = max(samples)
        low_b = min(samples)
        avg_b = (total_centers / (total_work_ns / 1e9)) / 1e9
        return low_b, avg_b, peak_b

    def _set_native_scan_state(self, active, label, started, base_pct, total_seeds, lib):
        self._native_scan_active = bool(active)
        self._native_scan_label = label or "原生"
        self._native_scan_started = float(started or time.time())
        self._native_scan_base_pct = float(base_pct or 0.0)
        self._native_scan_total_seeds = max(1, int(total_seeds or 1))
        self._native_scan_lib = lib
        if active:
            self._native_pause_accum = 0.0
            self._pause_started_at = 0.0
            if label == "GPU":
                self._reset_gpu_perf_stats()
            self._set_progress_busy(True)
        else:
            self._set_progress_busy(False)
            if label == "GPU" and not self._search_cancelled:
                stats = self._finish_gpu_perf_stats(lib)
                gpu_short_name = GPU_DEVICE_NAME.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").strip()
                if stats:
                    low_b, avg_b, peak_b = stats
                    self._set_gpu_perf_text(f"{gpu_short_name} · {avg_b:.1f} B/s")
                    self.upd_log(
                        f"GPU速度统计：峰值 {peak_b:.2f} B/s | 最低 {low_b:.2f} B/s | 平均 {avg_b:.2f} B/s")
            done_value = int(min(95, self._native_scan_base_pct + 35 / max(1, self._native_scan_total_seeds)))
            if done_value > self.progress.value():
                self.progress.setValue(done_value)

    def poll_native_progress(self):
        """Main-thread liveness progress for long searches.

        This watchdog runs while a search is in progress even before the native
        state signal arrives. It only raises the bar inside the first scan stage
        and never claims final completion.
        """
        active = self._native_scan_active
        if not active and not self._search_in_progress:
            return
        if self._search_paused:
            self.time_label.setText(f"{self._native_scan_label} 已暂停 · 点击“继续”恢复")
            return

        if active:
            started = self._native_scan_started
            base_pct = self._native_scan_base_pct
            total_seeds = float(self._native_scan_total_seeds)
            label = self._native_scan_label
            lib = self._native_scan_lib
        else:
            started = self._search_started_at
            base_pct = 0.0
            total_seeds = 1.0
            label = "搜索"
            lib = None

        elapsed = max(0.001, time.time() - started - self._native_pause_accum)
        native_pct = None
        if lib:
            try:
                raw_pct = int(lib.get_progress())
                if 0 <= raw_pct <= 100:
                    native_pct = raw_pct
            except Exception:
                native_pct = None

        if native_pct is not None and native_pct > 0:
            phase = 2 + int(min(33, native_pct * 33 / 100))
        else:
            phase = 2 + int((1.0 - math.exp(-elapsed / 45.0)) * 31)
            if elapsed >= 1.0:
                phase = max(3, phase)
            phase = min(self._search_soft_ceiling, max(2, phase))

        value = int(max(0, min(95, base_pct + phase / total_seeds)))
        if elapsed >= 1.0 and self.progress.value() < 35:
            value = max(value, min(34, phase))
        if not self._progress_busy and value > self.progress.value():
            self.progress.setValue(value)

        if label == "GPU":
            gpu_short_name = GPU_DEVICE_NAME.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").strip()
            rate_b = self._sample_gpu_perf(lib)
            if rate_b is not None and rate_b > 0:
                self._set_gpu_perf_text(f"{gpu_short_name} · {rate_b:.1f} B/s")

        elapsed_text = format_elapsed(elapsed)
        if native_pct is not None and native_pct > 0:
            self.time_label.setText(f"{label} 扫描中：{native_pct}% | 已用时 {elapsed_text}")
        else:
            self.time_label.setText(f"{label} 扫描中：已用时 {elapsed_text}")

    def initUI(self):
        self.setWindowTitle(f'查找史莱姆区块 {APP_VERSION}')
        self.resize(1200, 780)
        self.setMinimumSize(960, 640)
        self.setStyleSheet("""
            QWidget { background: #1a1a1a; color: #e0e0e0; font-family: 'Microsoft YaHei', Arial; }
            QLineEdit, QTextEdit, QSpinBox, QComboBox { background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 4px; padding: 6px; color: #ffffff; font-size: 12px; }
            QPushButton { background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 4px; padding: 8px; color: #e0e0e0; font-size: 12px; }
            QPushButton:hover { background: #3a3a3a; border: 1px solid #4a4a4a; }
            QPushButton:pressed { background: #1a1a1a; }
            QProgressBar { border: 1px solid #3a3a3a; border-radius: 4px; text-align: center; background: #2a2a2a; color: white; }
            QProgressBar::chunk { background: #4a4a4a; border-radius: 3px; }
            QScrollArea, QListWidget { background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 4px; }
            QGroupBox { border: 1px solid #3a3a3a; border-radius: 4px; margin-top: 10px; padding-top: 10px; font-weight: bold; }
            QTabBar::tab { background: #1a1a1a; border: 1px solid #3a3a3a; padding: 8px 20px; color: #aaa; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #2a2a2a; color: white; border-bottom-color: #2a2a2a; font-weight: bold; }
            QScrollBar:vertical { background: #1a1a1a; width: 12px; margin: 0px; }
            QScrollBar::handle:vertical { background: #444; min-height: 20px; border-radius: 6px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar:horizontal { height: 0px; }
            QMenu { background-color: #2a2a2a; color: white; border: 1px solid #3a3a3a; }
            QMenu::item { padding: 8px 20px; }
            QMenu::item:selected { background-color: #3a3a3a; }
        """)

        global_layout = QHBoxLayout(self)
        global_layout.setContentsMargins(0, 0, 0, 0)
        global_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("""
            QFrame { background-color: #1a1a1a; border-right: 1px solid #2a2a2a; }
            QPushButton {
                background: transparent; border: none; color: #cccccc; font-size: 13px;
                padding: 12px 0px; text-align: left; padding-left: 18px;
                border-left: 4px solid transparent;
            }
            QPushButton:hover { background-color: #2d2d2d; color: #ffffff; }
            QPushButton:checked {
                background-color: #333333; color: #ffffff; font-weight: bold;
                border-left: 4px solid #0078d4;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 10, 0, 10)
        sidebar_layout.setSpacing(5)

        self.btn_hamburger = QPushButton()
        self.btn_hamburger.setIcon(create_burger_icon())
        self.btn_hamburger.setIconSize(QSize(24, 24))
        self.btn_hamburger.setCheckable(False)
        self.btn_hamburger.clicked.connect(self.toggle_sidebar)
        sidebar_layout.addWidget(self.btn_hamburger)

        icon_slime = create_slime_icon()
        icon_shared = create_fluent_icon()
        icon_history = create_history_icon()
        icon_gear = create_gear_icon()

        self.btn_nav_search = QPushButton()
        self.btn_nav_search.setIcon(icon_slime)
        self.btn_nav_search.setIconSize(QSize(24, 24))
        self.btn_nav_search.setText("  搜索界面")

        self.btn_nav_floor = QPushButton()
        self.btn_nav_floor.setIcon(icon_shared)
        self.btn_nav_floor.setIconSize(QSize(24, 24))
        self.btn_nav_floor.setText("  地板生成")

        self.btn_history = QPushButton()
        self.btn_history.setIcon(icon_history)
        self.btn_history.setIconSize(QSize(24, 24))
        self.btn_history.setText("  历史记录")

        self.btn_nav_settings = QPushButton()
        self.btn_nav_settings.setIcon(icon_gear)
        self.btn_nav_settings.setIconSize(QSize(24, 24))
        self.btn_nav_settings.setText("  高级设置")

        for btn in [self.btn_nav_search, self.btn_nav_floor]:
            btn.setCheckable(True)
            sidebar_layout.addWidget(btn)

        self.nav_group = QButtonGroup(self)
        self.nav_group.addButton(self.btn_nav_search, 0)
        self.nav_group.addButton(self.btn_nav_floor, 1)
        self.btn_nav_search.setChecked(True)

        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self.btn_history)
        sidebar_layout.addWidget(self.btn_nav_settings)
        self.btn_history.clicked.connect(self.show_history)
        self.btn_nav_settings.clicked.connect(self.open_settings)

        global_layout.addWidget(self.sidebar)
        self.stacked = QStackedWidget(self)
        global_layout.addWidget(self.stacked)

        self.setup_search_page()
        self.setup_floor_page()
        self.nav_group.idClicked.connect(self.on_nav_changed)

    def toggle_sidebar(self):
        now = time.monotonic()
        self._hamburger_click_times = [t for t in self._hamburger_click_times if now - t <= 4.0]
        self._hamburger_click_times.append(now)
        if len(self._hamburger_click_times) >= 8:
            self._hamburger_click_times.clear()
            self.btn_hamburger.setToolTip("门没坏")
            try:
                QToolTip.showText(
                    self.btn_hamburger.mapToGlobal(self.btn_hamburger.rect().bottomRight()),
                    "门没坏", self.btn_hamburger)
            except Exception:
                pass
            QTimer.singleShot(3000, lambda: self.btn_hamburger.setToolTip(""))

        self.is_sidebar_expanded = not self.is_sidebar_expanded
        start_w = self.sidebar.width()
        end_w = 200 if self.is_sidebar_expanded else 60

        self.sidebar_anim = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_anim.setDuration(180)
        self.sidebar_anim.setStartValue(start_w)
        self.sidebar_anim.setEndValue(end_w)

        self.sidebar_anim_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.sidebar_anim_max.setDuration(180)
        self.sidebar_anim_max.setStartValue(start_w)
        self.sidebar_anim_max.setEndValue(end_w)

        if self.is_sidebar_expanded:
            self.btn_nav_search.setText("  搜索界面")
            self.btn_nav_floor.setText("  地板生成")
            self.btn_history.setText("  历史记录")
            self.btn_nav_settings.setText("  高级设置")
        else:
            self.btn_nav_search.setText("")
            self.btn_nav_floor.setText("")
            self.btn_history.setText("")
            self.btn_nav_settings.setText("")

        self.sidebar_anim.start()
        self.sidebar_anim_max.start()

    def on_nav_changed(self, page_id):
        self.stacked.setCurrentIndex(page_id)

    def setup_search_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left_panel = QWidget()
        left_panel.setFixedWidth(350)
        left_panel.setStyleSheet("background-color: #141517;")
        left_v = QVBoxLayout(left_panel)

        left_v.addWidget(QLabel("搜索参数", styleSheet="font-size: 14px; font-weight: bold; padding: 5px;"))

        left_v.addWidget(QLabel("种子 (多个用逗号分隔):"))
        self.seed_text_edit = QTextEdit()
        self.seed_text_edit.setMaximumHeight(60)
        self.seed_text_edit.setText(self.config.last_seed)
        left_v.addWidget(self.seed_text_edit)

        rad_h = QHBoxLayout()
        self.rad_min_v = QVBoxLayout()
        self.rad_min_label = QLabel("最小搜索半径:")
        self.r_inner = QLineEdit(str(self.config.min_search_radius))
        self.rad_min_v.addWidget(self.rad_min_label)
        self.rad_min_v.addWidget(self.r_inner)
        rad_h.addLayout(self.rad_min_v)

        rad_max_v = QVBoxLayout()
        rad_max_v.addWidget(QLabel("最大搜索半径 (区块):"))
        self.radius_input = QLineEdit(self.config.last_radius)
        rad_max_v.addWidget(self.radius_input)
        rad_h.addLayout(rad_max_v)
        left_v.addLayout(rad_h)

        center_h = QHBoxLayout()
        center_x_v = QVBoxLayout()
        center_x_v.addWidget(QLabel("搜索中心 X (方块):"))
        self.search_center_x_input = QLineEdit(str(self.config.search_center_x))
        center_x_v.addWidget(self.search_center_x_input)
        center_h.addLayout(center_x_v)
        center_z_v = QVBoxLayout()
        center_z_v.addWidget(QLabel("搜索中心 Z (方块):"))
        self.search_center_z_input = QLineEdit(str(self.config.search_center_z))
        center_z_v.addWidget(self.search_center_z_input)
        center_h.addLayout(center_z_v)
        left_v.addLayout(center_h)

        self.rad_min_label.setVisible(self.config.use_min_radius)
        self.r_inner.setVisible(self.config.use_min_radius)

        size_h = QHBoxLayout()
        min_v = QVBoxLayout()
        min_v.addWidget(QLabel("最小规模:"))
        self.m_min = QLineEdit(str(self.config.min_size))
        min_v.addWidget(self.m_min)
        size_h.addLayout(min_v)

        self.max_v = QVBoxLayout()
        self.max_label = QLabel("最大规模:")
        self.m_max = QLineEdit(str(self.config.max_size))
        self.max_v.addWidget(self.max_label)
        self.max_v.addWidget(self.m_max)
        size_h.addLayout(self.max_v)
        left_v.addLayout(size_h)

        self.max_label.setVisible(self.config.use_range)
        self.m_max.setVisible(self.config.use_range)

        self.chk_dd = QCheckBox(" 检测是否有深谙之域")
        self.chk_dd.setChecked(bool(cb))
        self.cubiomes_download_btn = QPushButton("下载噪声组件 · 支持 1.19 ～ 26.2")
        self.cubiomes_download_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CUBIOMES_DOWNLOAD_URL)))
        self.cubiomes_download_btn.setVisible(not bool(cb))
        if not cb:
            self.chk_dd.setEnabled(False)
            self.chk_dd.setText("噪声/群系检查未安装")
            self.chk_dd.setToolTip(DLL_ERROR_MSG + "\n下载 ZIP，解压 cubiomes.dll 到程序目录。")
        left_v.addWidget(self.chk_dd)
        left_v.addWidget(self.cubiomes_download_btn)

        self.chk_precise_afk = QCheckBox(" 精准挂机点")
        self.chk_precise_afk.setChecked(self.config.precise_afk)
        left_v.addWidget(self.chk_precise_afk)

        self.chk_scan_y = QCheckBox(" 扫描挂机Y")
        self.chk_scan_y.setChecked(self.config.scan_y)
        self.chk_scan_y.setEnabled(self.chk_precise_afk.isChecked())
        self.chk_precise_afk.toggled.connect(self.chk_scan_y.setEnabled)
        left_v.addWidget(self.chk_scan_y)

        engine_h = QHBoxLayout()
        engine_h.addWidget(QLabel("模式选择："))
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Auto")
        if gpu_algorithm_available():
            self.engine_combo.addItem("GPU (CUDA)")
        if cpu_algorithm_available():
            self.engine_combo.addItem("CPU (AVX2/OpenMP)")

        idx = self.engine_combo.findText(self.config.selected_engine)
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)
        engine_h.addWidget(self.engine_combo)
        left_v.addLayout(engine_h)

        btn_h = QHBoxLayout()
        self.start_button = QPushButton("开始搜索")
        self.start_button.setFixedHeight(35)
        self.start_button.clicked.connect(self.start_work)
        self.cancel_btn = QPushButton("暂停")
        self.cancel_btn.setFixedHeight(35)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.toggle_pause_search)
        btn_h.addWidget(self.start_button)
        btn_h.addWidget(self.cancel_btn)
        left_v.addLayout(btn_h)

        self.time_label = QLabel("准备就绪")
        self.time_label.setStyleSheet("color: #888;")
        left_v.addWidget(self.time_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        left_v.addWidget(self.log)

        progress_h = QHBoxLayout()
        progress_h.setSpacing(8)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(15)
        progress_h.addWidget(self.progress, 1)
        gpu_short_name = GPU_DEVICE_NAME.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").strip()
        self.gpu_perf_label = QPushButton(f"{gpu_short_name} · -- B/s")
        self.gpu_perf_label.setFlat(True)
        self.gpu_perf_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.gpu_perf_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gpu_perf_label.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0; color: #7f8a96; font-size: 10px; }"
            "QPushButton:hover { color: #9aa5b1; }")
        self.gpu_perf_label.clicked.connect(self._on_gpu_perf_click)
        self.gpu_perf_label.setVisible(gpu_algorithm_available())
        progress_h.addWidget(self.gpu_perf_label, 0)
        left_v.addLayout(progress_h)

        layout.addWidget(left_panel)

        right_panel = QWidget()
        right_v = QVBoxLayout(right_panel)
        right_v.setContentsMargins(15, 15, 15, 15)

        # 排名功能默认收起，避免破坏主界面的简洁感；需要时再展开完整控件。
        result_group = QGroupBox("排名结果")
        result_v = QVBoxLayout(result_group)
        result_top = QHBoxLayout()
        self.result_status_label = QLabel("尚未产生排名结果")
        self.result_status_label.setStyleSheet("font-weight: bold; color: #aeb7c2;")
        result_top.addWidget(self.result_status_label, 1)

        self.rank_toggle_btn = QPushButton("查看排名")
        self.rank_toggle_btn.setEnabled(False)
        self.rank_toggle_btn.setFixedWidth(92)
        self.rank_toggle_btn.clicked.connect(self._toggle_rank_panel)
        result_top.addWidget(self.rank_toggle_btn)
        result_v.addLayout(result_top)

        self.rank_panel = QWidget()
        rank_panel_v = QVBoxLayout(self.rank_panel)
        rank_panel_v.setContentsMargins(0, 6, 0, 0)
        rank_panel_v.setSpacing(6)

        rank_actions = QHBoxLayout()
        rank_actions.addWidget(QLabel("使用第"))
        self.rank_select_spin = QSpinBox()
        self.rank_select_spin.setRange(1, 1)
        self.rank_select_spin.setValue(1)
        self.rank_select_spin.setEnabled(False)
        self.rank_select_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.rank_select_spin.setFixedWidth(82)
        rank_actions.addWidget(self.rank_select_spin)
        rank_actions.addWidget(QLabel("名"))

        self.rank_apply_btn = QPushButton("使用该排名")
        self.rank_list_btn = QPushButton("排名列表")
        self.rank_export_btn = QPushButton("导出 CSV")
        for b in (self.rank_apply_btn, self.rank_list_btn, self.rank_export_btn):
            b.setEnabled(False)
        self.rank_apply_btn.clicked.connect(self._apply_rank_from_button)
        self.rank_list_btn.clicked.connect(self.show_rankings_dialog)
        self.rank_export_btn.clicked.connect(self.export_results)
        self.rank_select_spin.valueChanged.connect(self.preview_ranked_result)
        rank_actions.addWidget(self.rank_apply_btn)
        rank_actions.addWidget(self.rank_list_btn)
        rank_actions.addWidget(self.rank_export_btn)
        rank_actions.addStretch(1)
        rank_panel_v.addLayout(rank_actions)

        self.rank_detail_label = QLabel("搜索完成后，这里会显示第 1～N 名；排名可直接切换成当前坐标和地板投影中心。")
        self.rank_detail_label.setStyleSheet("color: #7f8a96; font-size: 11px;")
        self.rank_detail_label.setWordWrap(True)
        rank_panel_v.addWidget(self.rank_detail_label)
        self.rank_panel.setVisible(False)
        result_v.addWidget(self.rank_panel)
        right_v.addWidget(result_group)

        verify_group = QGroupBox("验证坐标")
        verify_layout = QHBoxLayout(verify_group)
        verify_layout.setContentsMargins(10, 5, 10, 5)
        verify_layout.setSpacing(10)

        self.manual_seed = QLineEdit()
        self.manual_seed.setPlaceholderText("验证种子")
        self.manual_x = QLineEdit()
        self.manual_x.setPlaceholderText("方块坐标 X")
        self.manual_z = QLineEdit()
        self.manual_z.setPlaceholderText("方块坐标 Z")

        self.manual_btn = QPushButton("生成图片")
        self.manual_btn.clicked.connect(self.manual_generate)
        self.test_dd_btn = QPushButton("验证深谙之域")
        self.test_dd_btn.clicked.connect(self.test_dd_manual)

        verify_layout.addWidget(self.manual_seed)
        verify_layout.addWidget(self.manual_x)
        verify_layout.addWidget(self.manual_z)
        verify_layout.addWidget(self.manual_btn)
        verify_layout.addWidget(self.test_dd_btn)
        right_v.addWidget(verify_group)

        self.sc = QScrollArea()
        self.v = QLabel()
        self.v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sc.setWidget(self.v)
        self.sc.setWidgetResizable(True)
        right_v.addWidget(self.sc)

        bottom_layout = QHBoxLayout()
        self.info = QLabel("等待搜索...")
        self.info.setStyleSheet("padding: 5px; font-weight: bold;")
        bottom_layout.addWidget(self.info, 1)

        self.copy_btn = QPushButton("复制坐标")
        self.copy_btn.setFixedWidth(150)
        self.copy_btn.setFixedHeight(35)
        self.copy_menu = QMenu(self)

        action_main = QAction("复制最优挂机点坐标 (主世界)", self)
        action_nether = QAction("复制挂机点地狱坐标 (地狱)", self)
        action_main.triggered.connect(lambda: self.copy_tp("main"))
        action_nether.triggered.connect(lambda: self.copy_tp("nether"))

        self.copy_menu.addAction(action_main)
        self.copy_menu.addAction(action_nether)
        self.copy_btn.setMenu(self.copy_menu)
        bottom_layout.addWidget(self.copy_btn)

        right_v.addLayout(bottom_layout)
        layout.addWidget(right_panel)

        self.stacked.addWidget(page)

    # ===== 投影界面 =====
    def setup_floor_page(self):
        tab_gen = QWidget()
        gen_layout = QHBoxLayout(tab_gen)
        gen_layout.setContentsMargins(0, 0, 0, 0)
        gen_layout.setSpacing(0)

        left_scroll = QScrollArea()
        left_scroll.setFixedWidth(380)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_container = QWidget()
        left_v = QVBoxLayout(left_container)
        left_v.setContentsMargins(15, 15, 15, 15)
        left_v.setSpacing(10)

        basic_group = QGroupBox("基础参数")
        basic_form = QFormLayout(basic_group)
        basic_form.setSpacing(10)

        self.proj_manual_seed = QLineEdit()
        self.proj_manual_seed.setPlaceholderText("默认使用搜索界面的种子")
        self.proj_manual_x = QLineEdit()
        self.proj_manual_x.setPlaceholderText("默认使用最优坐标 X")
        self.proj_manual_z = QLineEdit()
        self.proj_manual_z.setPlaceholderText("默认使用最优坐标 Z")
        self.proj_manual_y = QLineEdit()
        self.proj_manual_y.setPlaceholderText("默认使用扫描到的挂机Y；无结果时 -64")
        self.px = QLineEdit("280")
        self.pz = QLineEdit("280")

        self.glass_options = {
            "普通玻璃": "glass",
            "白色染色玻璃": "white_stained_glass",
            "橙色染色玻璃": "orange_stained_glass",
            "品红色染色玻璃": "magenta_stained_glass",
            "淡蓝色染色玻璃": "light_blue_stained_glass",
            "黄色染色玻璃": "yellow_stained_glass",
            "黄绿色染色玻璃": "lime_stained_glass",
            "粉红色染色玻璃": "pink_stained_glass",
            "灰色染色玻璃": "gray_stained_glass",
            "淡灰色染色玻璃": "light_gray_stained_glass",
            "青色染色玻璃": "cyan_stained_glass",
            "紫色染色玻璃": "purple_stained_glass",
            "蓝色染色玻璃": "blue_stained_glass",
            "棕色染色玻璃": "brown_stained_glass",
            "绿色染色玻璃": "green_stained_glass",
            "红色染色玻璃": "red_stained_glass",
            "黑色染色玻璃": "black_stained_glass"}
        self.proj_glass = QComboBox()
        self.proj_glass.addItems(list(self.glass_options.keys()))
        self.proj_custom_block = QLineEdit()
        self.proj_custom_block.setPlaceholderText("格式：minecraft:stone 或 stone")
        self.proj_custom_block.setToolTip("只填写方块ID，不要填写方块状态。示例：minecraft:tinted_glass、stone、deepslate_tiles")
        self.proj_glass_stack = QStackedWidget()
        self.proj_glass_stack.addWidget(self.proj_glass)
        self.proj_glass_stack.addWidget(self.proj_custom_block)
        self.chk_custom_floor_material = QCheckBox("手动输入材质")
        self.chk_custom_floor_material.toggled.connect(self._toggle_floor_material_input)
        self.wither_base_combo = QComboBox()
        self.wither_base_combo.addItems(["跟随投影生成的地板 (默认)", "灵魂沙 (soul_sand)"])

        basic_form.addRow("世界种子:", self.proj_manual_seed)
        basic_form.addRow("中心坐标 X:", self.proj_manual_x)
        basic_form.addRow("中心坐标 Z:", self.proj_manual_z)
        basic_form.addRow("挂机坐标 Y:", self.proj_manual_y)
        basic_form.addRow("总宽度 (X):", self.px)
        basic_form.addRow("总长度 (Z):", self.pz)
        basic_form.addRow("非史莱姆区材质:", self.proj_glass_stack)
        basic_form.addRow("", self.chk_custom_floor_material)
        basic_form.addRow("凋零玫瑰垫块:", self.wither_base_combo)
        left_v.addWidget(basic_group)

        feature_group = QGroupBox("自定义选项")
        feature_v = QVBoxLayout(feature_group)
        feature_v.setSpacing(10)

        self.chk_magma = QCheckBox(" 是否生成岩浆块")
        self.chk_magma.setChecked(True)
        self.chk_wither = QCheckBox(" 是否生成凋零玫瑰")
        self.chk_wither.setChecked(True)
        self.chk_rod = QCheckBox(" 是否生成避雷针")
        self.chk_rod.setChecked(True)

        portal_layout = QHBoxLayout()
        self.chk_portal_array = QCheckBox(" 是否生成地狱门")
        self.chk_portal_array.setChecked(True)
        self.portal_axis_combo = QComboBox()
        self.portal_axis_combo.addItems(["南北朝向 (X轴)", "东西朝向 (Z轴)"])
        portal_layout.addWidget(self.chk_portal_array)
        portal_layout.addWidget(self.portal_axis_combo)

        feature_v.addWidget(self.chk_magma)
        feature_v.addWidget(self.chk_wither)
        feature_v.addWidget(self.chk_rod)
        feature_v.addLayout(portal_layout)
        left_v.addWidget(feature_group)

        gen_btn = QPushButton("一键生成地板投影 (.litematic)")
        gen_btn.setFixedHeight(40)
        gen_btn.setStyleSheet("background-color: #2e5a3b; font-size: 13px; font-weight: bold; border-radius: 4px;")
        gen_btn.clicked.connect(self.export_proj)
        left_v.addWidget(gen_btn)

        left_v.addStretch()

        # 底部开关阵列
        self.chk_show_slime = QCheckBox(" 显示史莱姆区块 (高亮绿色)")
        self.chk_show_slime.setChecked(True)
        self.chk_show_slime.setStyleSheet("font-weight: bold; color: #10d472; padding-top: 5px; border-top: 1px solid #2d2d2d;")
        left_v.addWidget(self.chk_show_slime)

        self.chk_show_radius = QCheckBox(" 显示 128格 挂机半径 (红色虚线)")
        self.chk_show_radius.setChecked(True)
        self.chk_show_radius.setStyleSheet("font-weight: bold; color: #ff3232; padding-top: 2px;")
        left_v.addWidget(self.chk_show_radius)

        left_scroll.setWidget(left_container)
        gen_layout.addWidget(left_scroll)

        right_preview_panel = QWidget()
        right_preview_v = QVBoxLayout(right_preview_panel)
        right_preview_v.setContentsMargins(15, 15, 15, 15)

        self.floor_preview_title = QPushButton("地板俯视范围动态预演")
        self.floor_preview_title.setCursor(Qt.CursorShape.PointingHandCursor)
        self.floor_preview_title.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0; text-align: left; font-size: 13px; font-weight: bold; color: #aaa; } QPushButton:hover { color: #bbb; }")
        self._projection_title_click_times = []
        self.floor_preview_title.clicked.connect(self._on_projection_title_click)
        right_preview_v.addWidget(self.floor_preview_title)

        self.floor_scroller = QScrollArea()
        self.floor_scroller.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.floor_scroller.setWidgetResizable(False)
        self.floor_preview_label = QLabel("正在根据左侧参数绘制动态范围阵列...")
        self.floor_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.floor_preview_label.setScaledContents(False)
        self.floor_scroller.setWidget(self.floor_preview_label)
        right_preview_v.addWidget(self.floor_scroller)

        gen_layout.addWidget(right_preview_panel, 1)

        # 绑定触发机制
        for w in [self.proj_manual_seed, self.proj_manual_x, self.proj_manual_z, self.proj_manual_y, self.px, self.pz, self.proj_custom_block]:
            w.textChanged.connect(self.trigger_floor_preview_update)
        for w in [self.proj_glass, self.wither_base_combo, self.portal_axis_combo]:
            w.currentIndexChanged.connect(self.trigger_floor_preview_update)
        for w in [self.chk_magma, self.chk_wither, self.chk_rod, self.chk_portal_array, self.chk_custom_floor_material, self.chk_show_slime, self.chk_show_radius]:
            w.toggled.connect(self.trigger_floor_preview_update)

        self.stacked.addWidget(tab_gen)
        QTimer.singleShot(500, self.trigger_floor_preview_update)




    def collect_projection_settings(self):
        return {
            "schema": 1,
            "width_x": self.px.text().strip(),
            "length_z": self.pz.text().strip(),
            "afk_y": self.proj_manual_y.text().strip(),
            "glass_name": self.proj_glass.currentText(),
            "custom_material_enabled": self.chk_custom_floor_material.isChecked(),
            "custom_material": self.proj_custom_block.text().strip(),
            "floor_material_id": self.get_floor_material_id(),
            "wither_base_index": self.wither_base_combo.currentIndex(),
            "magma": self.chk_magma.isChecked(),
            "wither_rose": self.chk_wither.isChecked(),
            "lightning_rod": self.chk_rod.isChecked(),
            "portal_array": self.chk_portal_array.isChecked(),
            "portal_axis_index": self.portal_axis_combo.currentIndex(),
            "show_slime": self.chk_show_slime.isChecked(),
            "show_radius": self.chk_show_radius.isChecked(),
        }

    def apply_projection_settings(self, settings):
        if not isinstance(settings, dict) or not settings:
            return
        if settings.get("width_x") not in (None, ""):
            self.px.setText(str(settings["width_x"]))
        if settings.get("length_z") not in (None, ""):
            self.pz.setText(str(settings["length_z"]))
        if settings.get("afk_y") not in (None, ""):
            self.proj_manual_y.setText(str(settings["afk_y"]))
        glass_name = settings.get("glass_name")
        if glass_name:
            idx = self.proj_glass.findText(str(glass_name))
            if idx >= 0:
                self.proj_glass.setCurrentIndex(idx)
        self.proj_custom_block.setText(str(settings.get("custom_material", "")))
        self.chk_custom_floor_material.setChecked(bool(settings.get("custom_material_enabled", False)))
        self.wither_base_combo.setCurrentIndex(clamp_int(settings.get("wither_base_index", 0), 0, 0, self.wither_base_combo.count() - 1))
        self.portal_axis_combo.setCurrentIndex(clamp_int(settings.get("portal_axis_index", 0), 0, 0, self.portal_axis_combo.count() - 1))
        for key, widget, default in (
            ("magma", self.chk_magma, True),
            ("wither_rose", self.chk_wither, True),
            ("lightning_rod", self.chk_rod, True),
            ("portal_array", self.chk_portal_array, True),
            ("show_slime", self.chk_show_slime, True),
            ("show_radius", self.chk_show_radius, True),
        ):
            widget.setChecked(bool(settings.get(key, default)))
        self.trigger_floor_preview_update()

    # ===== 历史记录 =====
    def _save_search_history(self, state):
        timestamp = state.get("history_timestamp")
        if not timestamp:
            return
        try:
            os.makedirs(os.path.join(APP_DIR, "history"), exist_ok=True)
            x, z = state["main_pos"]
            nx, nz = state["nether_pos"]
            payload = {
                "history_schema": 2,
                "app_version": APP_VERSION,
                "timestamp": timestamp,
                "seed": state.get("current_seed"),
                "size": state.get("current_size"),
                "obs_count": state.get("current_obs_count"),
                "x": x, "y": state.get("current_afk_y"), "z": z,
                "nether_x": nx, "nether_z": nz,
                "image": state.get("history_image", ""),
                "algorithm": state.get("current_algorithm", "未知算法"),
                "search_params": state.get("search_params", {}),
                "ranked_results": state.get("ranked_results", []),
                "projection": self.collect_projection_settings(),
            }
            path = os.path.join(APP_DIR, "history", f"search_{timestamp}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.upd_log(f"历史记录保存失败：{e}")

    def trigger_floor_preview_update(self):
        if hasattr(self, '_floor_timer'): self._floor_timer.stop()
        self._floor_timer = QTimer()
        self._floor_timer.setSingleShot(True)
        self._floor_timer.timeout.connect(self.generate_floor_preview_bitmap)
        self._floor_timer.start(250)

    def _projection_seed_easter_egg_active(self, seed_input=None):
        seed_input = self.proj_manual_seed.text().strip() if seed_input is None else str(seed_input).strip()
        if not seed_input or not is_minecraft_text_seed(seed_input):
            return False
        return not any(w.text().strip() for w in (
            self.proj_manual_x, self.proj_manual_z, self.proj_manual_y))

    def _on_projection_title_click(self):
        now = time.monotonic()
        self._projection_title_click_times = [
            t for t in self._projection_title_click_times if now - t <= 2.5]
        self._projection_title_click_times.append(now)
        if len(self._projection_title_click_times) >= 7:
            self._projection_title_click_times.clear()
            self.upd_log("这也能被你找到？")

    def _reject_world_border_radius(self, radius):
        if radius <= WORLD_BORDER_RADIUS_CHUNKS:
            return False

        first = QMessageBox(self)
        first.setIcon(QMessageBox.Icon.Warning)
        first.setWindowTitle("你在干什么？？？")
        first.setText(
            f"搜索半径是 {radius:,} 个区块。\n\n"
            f"这已经超过 {WORLD_BORDER_RADIUS_CHUNKS:,} 区块的世界边界尺度。"
        )
        first.addButton("……", QMessageBox.ButtonRole.AcceptRole)
        first.exec()

        second = QMessageBox(self)
        second.setIcon(QMessageBox.Icon.Critical)
        second.setWindowTitle("不对劲")
        second.setText(
            "这个范围对正常主世界搜索没有实际意义，继续执行只会浪费大量时间和资源。"
        )
        second.addButton("我知道了", QMessageBox.ButtonRole.AcceptRole)
        second.exec()

        third = QMessageBox(self)
        third.setIcon(QMessageBox.Icon.Information)
        third.setWindowTitle("拒绝执行")
        third.setText(
            f"请把最大搜索半径改到 {WORLD_BORDER_RADIUS_CHUNKS:,} 区块以内。"
        )
        third.addButton("行吧", QMessageBox.ButtonRole.AcceptRole)
        third.exec()
        return True

    def _show_projection_seed_easter_egg(self, resolved_seed):
        QTimer.singleShot(0, lambda seed=resolved_seed: self._render_projection_seed_easter_egg(seed))

    def _render_projection_seed_easter_egg(self, resolved_seed):
        current = self.proj_manual_seed.text().strip()
        if not self._projection_seed_easter_egg_active(current):
            return
        if normalize_java_seed(current) != resolved_seed:
            return

        viewport_w = max(1, self.floor_scroller.viewport().width() - 12)
        img_w = max(520, viewport_w)
        img_h = 310
        block = 4
        chars = "何意味"
        gap = 18
        char_w = max(120, min(190, (img_w - 64 - gap * 2) // 3))
        char_h = 190
        total_w = len(chars) * char_w + (len(chars) - 1) * gap
        left = max(10, (img_w - total_w) // 2)
        top = 12

        img = QImage(img_w, img_h, QImage.Format.Format_ARGB32)
        img.fill(QColor(24, 24, 26))
        painter = QPainter(img)
        fill = self.get_floor_block_color("minecraft:lime_stained_glass")
        edge = QColor(fill)
        edge.setAlpha(90)

        glyph_font = QFont("Microsoft YaHei", max(88, int(char_w * 0.82)), QFont.Weight.Normal)
        for index, char in enumerate(chars):
            mask = QImage(char_w, char_h, QImage.Format.Format_Grayscale8)
            mask.fill(0)
            mp = QPainter(mask)
            mp.setPen(QColor(255, 255, 255))
            mp.setFont(glyph_font)
            mp.drawText(mask.rect(), Qt.AlignmentFlag.AlignCenter, char)
            mp.end()

            base_x = left + index * (char_w + gap)
            for gy in range(0, char_h, block):
                for gx in range(0, char_w, block):
                    hits = 0
                    samples = 0
                    for sy in range(gy, min(gy + block, char_h)):
                        for sx in range(gx, min(gx + block, char_w)):
                            samples += 1
                            if mask.pixelColor(sx, sy).value() > 96:
                                hits += 1
                    if hits * 5 < samples:
                        continue
                    x = base_x + gx
                    y = top + gy
                    painter.fillRect(x + 1, y + 1, block - 1, block - 1, fill)
                    painter.setPen(edge)
                    painter.drawRect(x + 1, y + 1, block - 2, block - 2)

        painter.setPen(QColor(145, 145, 150))
        painter.setFont(QFont("Microsoft YaHei UI", 11))
        painter.drawText(
            20, 244, img_w - 40, 42,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            f"文本种子 · Minecraft 会自动转换为数字种子：{resolved_seed}")
        painter.end()

        self.floor_preview_label.clear()
        self.floor_preview_label.setFixedSize(img_w, img_h)
        self.floor_preview_label.setPixmap(QPixmap.fromImage(img))

    def generate_floor_preview_bitmap(self):
        try:
            seed_input = self.proj_manual_seed.text().strip()
            if self._projection_seed_easter_egg_active(seed_input):
                self._show_projection_seed_easter_egg(normalize_java_seed(seed_input))
                return
            active_seed = normalize_java_seed(seed_input) if seed_input else self.current_seed
            if active_seed is None:
                self.floor_preview_label.setText("主世界未完成检索且未手动覆盖种子，无法绘制演练蓝图")
                return

            x_input = self.proj_manual_x.text().strip()
            z_input = self.proj_manual_z.text().strip()
            y_input = self.proj_manual_y.text().strip()
            oy = int(y_input) if y_input else -64
            if not x_input and not z_input:
                if not self.main_pos:
                    self.floor_preview_label.setText("请输入中心坐标以初始化范围渲染")
                    return
                ox, oz = self.main_pos
            else:
                base_x, base_z = self.main_pos if self.main_pos else (None, None)
                if not x_input and base_x is None:
                    self.floor_preview_label.setText("中心 X 为空，且没有可用的最优坐标")
                    return
                if not z_input and base_z is None:
                    self.floor_preview_label.setText("中心 Z 为空，且没有可用的最优坐标")
                    return
                ox = int(x_input) if x_input else int(base_x)
                oz = int(z_input) if z_input else int(base_z)

            sx, sz = validate_projection_dimensions(self.px.text().strip(), self.pz.text().strip())
            glass = self.get_floor_material_id()
        except ValueError as e:
            try:
                self.floor_preview_label.clear()
                self.floor_preview_label.setText(str(e))
            except Exception:
                pass
            return

        painter = None
        try:
            # Each axis is cropped independently so rectangular exports stay
            # rectangular in preview. A square canvas is retained, with equal
            # X/Z scale and letterboxing instead of stretching blocks.
            render_limit = 280
            render_sx = max(16, min(sx, render_limit))
            render_sz = max(16, min(sz, render_limit))
            viewport = self.floor_scroller.viewport().size()
            viewport_w = max(1, viewport.width() - 6)
            viewport_h = max(1, viewport.height() - 6)
            side = max(280, min(viewport_w, viewport_h))
            img_w = img_h = side
            img = QImage(img_w, img_h, QImage.Format.Format_ARGB32)
            img.fill(QColor(24, 24, 26))
            painter = QPainter(img)
            scale_x = scale_z = min(img_w / render_sx, img_h / render_sz)
            draw_width = render_sx * scale_x
            draw_height = render_sz * scale_z
            draw_offset_x = (img_w - draw_width) / 2.0
            draw_offset_z = (img_h - draw_height) / 2.0

            use_magma = self.chk_magma.isChecked()
            use_wither = self.chk_wither.isChecked()
            use_rod = self.chk_rod.isChecked()
            use_portal_array = self.chk_portal_array.isChecked()
            show_slime_highlight = self.chk_show_slime.isChecked()
            show_radius = self.chk_show_radius.isChecked()
            is_axis_x = self.portal_axis_combo.currentIndex() == 0
            wither_base_soul = self.wither_base_combo.currentIndex() == 1

            wither_base = "minecraft:soul_sand" if wither_base_soul else glass

            chunk_cache = {}
            def is_slime_cached(cx, cz):
                key = (cx, cz)
                if key not in chunk_cache:
                    chunk_cache[key] = is_slime_chunk(active_seed, cx, cz)
                return chunk_cache[key]

            _, _, start_x, start_z, distance_field = build_floor_distance_field(
                ox, oz, render_sx, render_sz, is_slime_cached,
                afk_y=oy, platform_y=-64)

            def distance_to_slime(wx, wz):
                return floor_distance_at(
                    distance_field, render_sx, render_sz, start_x, start_z, wx, wz)

            def is_portal_position(wx, wz):
                return is_floor_portal_position(
                    wx, wz, distance_to_slime(wx, wz), use_portal_array, is_axis_x)

            def is_valid_bait(wx, wz):
                return is_floor_bait_position(
                    distance_field, render_sx, render_sz, start_x, start_z,
                    wx, wz, use_wither)

            for x in range(render_sx):
                wx = start_x + x
                rect_x = int(draw_offset_x + x * scale_x)
                rect_w = max(1, int(math.ceil(scale_x)))
                for z in range(render_sz):
                    wz = start_z + z
                    rect_y = int(draw_offset_z + z * scale_z)
                    rect_h = max(1, int(math.ceil(scale_z)))

                    dist = distance_field[x * render_sz + z]
                    if wx == ox and wz == oz:
                        painter.fillRect(rect_x, rect_y, rect_w, rect_h, self.get_floor_block_color("minecraft:composter"))
                        if use_rod:
                            marker_w = max(2, rect_w // 2)
                            marker_h = max(2, rect_h // 2)
                            painter.fillRect(rect_x + (rect_w - marker_w) // 2, rect_y + (rect_h - marker_h) // 2, marker_w, marker_h, self.get_floor_block_color("minecraft:lightning_rod"))
                        continue

                    if dist == 0:
                        painter.fillRect(rect_x, rect_y, rect_w, rect_h, self.get_floor_block_color("minecraft:nether_portal")if is_portal_position(wx, wz) else self.get_floor_block_color("minecraft:obsidian"))
                    elif dist == 1:
                        painter.fillRect(rect_x, rect_y, rect_w, rect_h, self.get_floor_block_color("minecraft:magma_block") if use_magma else self.get_floor_block_color(glass))
                    elif is_valid_bait(wx, wz):
                        painter.fillRect(rect_x, rect_y, rect_w, rect_h, self.get_floor_block_color(wither_base))
                        rose_w = max(1, rect_w // 2)
                        rose_h = max(1, rect_h // 2)
                        painter.fillRect(rect_x + (rect_w - rose_w) // 2, rect_y + (rect_h - rose_h) // 2, rose_w, rose_h, self.get_floor_block_color("minecraft:wither_rose"))
                    else:
                        painter.fillRect(rect_x, rect_y, rect_w, rect_h, self.get_floor_block_color(glass))

                    if show_slime_highlight and is_slime_cached(wx >> 4, wz >> 4):
                        painter.fillRect(rect_x, rect_y, rect_w, rect_h, QColor(16, 212, 114, 30))
                        if dist == 0: painter.fillRect(rect_x, rect_y, rect_w, rect_h, QColor(16, 212, 114, 55))

            painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
            grid_start_x = ((start_x + 15) // 16) * 16
            gx = grid_start_x
            while gx < start_x + render_sx:
                lx = int(draw_offset_x + (gx - start_x) * scale_x)
                painter.drawLine(lx, int(draw_offset_z), lx, int(draw_offset_z + draw_height))
                gx += 16
            grid_start_z = ((start_z + 15) // 16) * 16
            gz = grid_start_z
            while gz < start_z + render_sz:
                lz = int(draw_offset_z + (gz - start_z) * scale_z)
                painter.drawLine(int(draw_offset_x), lz, int(draw_offset_x + draw_width), lz)
                gz += 16

            if show_radius:
                painter.setPen(QPen(QColor(255, 50, 50, 230), 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                cx_pix = draw_offset_x + (ox - start_x + 0.5) * scale_x
                cz_pix = draw_offset_z + (oz - start_z + 0.5) * scale_z
                dy = -64 - oy
                outer_rem = SPAWN_OUTER_SQ - dy * dy
                if outer_rem >= 0:
                    horizontal_radius = math.sqrt(outer_rem)
                    painter.drawEllipse(
                        QPointF(cx_pix, cz_pix),
                        horizontal_radius * scale_x,
                        horizontal_radius * scale_z)

            painter.end()
            self.floor_preview_label.setFixedSize(img_w, img_h)
            self.floor_preview_label.setPixmap(QPixmap.fromImage(img))
        except Exception as e:
            try:
                self.floor_preview_label.clear()
                self.floor_preview_label.setText("地板预览生成失败: {}".format(e))
            except Exception:
                pass
        finally:
            try:
                if painter is not None and painter.isActive():
                    painter.end()
            except Exception:
                pass

    def manual_generate(self):
        try:
            seed = normalize_java_seed(self.manual_seed.text().strip())
            x = int(self.manual_x.text().strip())
            z = int(self.manual_z.text().strip())
            self.upd_log("开始生成手动验证图片...")
            threading.Thread(target=generate_manual_image, args=(self, seed, x, z), daemon=True).start()
        except ValueError:
            self.upd_log("手动验证输入错误：种子和坐标必须是整数。")
            QMessageBox.warning(self, "输入错误", "种子和坐标必须是整数。")

    def export_proj(self):
        seed_input = self.proj_manual_seed.text().strip()
        if self._projection_seed_easter_egg_active(seed_input):
            self.upd_log("何意味")
            self._show_projection_seed_easter_egg(normalize_java_seed(seed_input))
        if not HAS_LITEMAPY:
            QMessageBox.warning(self, "错误", "需要安装环境 litemapy")
            return
        try:
            active_seed = normalize_java_seed(seed_input) if seed_input else self.current_seed
            if active_seed is None:
                QMessageBox.warning(self, "缺少参数", "请先搜索出结果，或手动填写世界种子。")
                return
            x_i, z_i = self.proj_manual_x.text().strip(), self.proj_manual_z.text().strip()
            y_i = self.proj_manual_y.text().strip()
            oy = int(y_i) if y_i else -64
            if not x_i and not z_i:
                if not self.main_pos:
                    QMessageBox.warning(self, "缺少参数", "请先搜索出最优坐标，或手动填写中心坐标 X/Z。")
                    return
                ox, oz = self.main_pos
            else:
                base_x, base_z = self.main_pos if self.main_pos else (None, None)
                if not x_i and base_x is None:
                    raise ValueError("中心坐标 X 为空，且没有可用的最优坐标。")
                if not z_i and base_z is None:
                    raise ValueError("中心坐标 Z 为空，且没有可用的最优坐标。")
                ox = int(x_i) if x_i else int(base_x)
                oz = int(z_i) if z_i else int(base_z)
            sx, sz = validate_projection_dimensions(self.px.text().strip(), self.pz.text().strip())
            selected_floor_id = self.get_floor_material_id()
        except ValueError as e:
            QMessageBox.warning(self, "输入错误", str(e))
            return

        fn, _ = QFileDialog.getSaveFileName(self, "保存地板投影", f"SlimePerimeter_{ox}_{oz}.litematic", "Litematica (*.litematic)")
        if not fn:
            self._projection_save_cancel_count += 1
            if self._projection_save_cancel_count >= 5:
                self._projection_save_cancel_count = 0
                self.upd_log("你到底生不生成")
            return
        self._projection_save_cancel_count = 0
        fn = ensure_litematic_extension(fn)

        use_magma = self.chk_magma.isChecked()
        use_wither = self.chk_wither.isChecked()
        use_rod = self.chk_rod.isChecked()
        use_portal_array = self.chk_portal_array.isChecked()
        is_axis_x = (self.portal_axis_combo.currentIndex() == 0)
        wither_base_soul = (self.wither_base_combo.currentIndex() == 1)
        sender_btn = self.sender()
        original_btn_text = sender_btn.text() if sender_btn else None
        if sender_btn:
            sender_btn.setEnabled(False)
            sender_btn.setText("正在后台生成...")

        def async_export_worker():
            try:
                schem = create_slime_floor_schematic(
                    active_seed, ox, oz, sx, sz, selected_floor_id,
                    use_magma=use_magma,
                    use_wither=use_wither,
                    use_rod=use_rod,
                    use_portal_array=use_portal_array,
                    portal_axis_x=is_axis_x,
                    wither_base_soul=wither_base_soul,
                    afk_y=oy,
                    platform_y=-64)
                schem.save(fn)
                self.c.msg_box.emit("information", "导出成功", f"✅ 投影已生成！\n\n【放置方法】\n进游戏站到主世界坐标 ({ox}, {oz})\n直接按加载投影")
            except Exception as e:
                self.c.msg_box.emit("critical", "导出错误", f"生成时出现异常:\n{e}")
            finally:
                if sender_btn:
                    self.c.widget_enabled.emit(sender_btn, True)
                    if original_btn_text is not None:
                        self.c.widget_text.emit(sender_btn, original_btn_text)

        threading.Thread(target=async_export_worker, daemon=True).start()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Return"), self, self.start_work)
        QShortcut(QKeySequence("Ctrl+C"), self, lambda: self.copy_tp("main"))
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, lambda: self.copy_tp("nether"))

    def test_dd_manual(self):
        try:
            cx, cz = int(self.manual_x.text().strip()) // 16, int(self.manual_z.text().strip()) // 16
            seed = normalize_java_seed(self.manual_seed.text().strip())
            if not cb: return
            if check_deep_dark_fast(get_local_generator(seed), cx, cz, seed): self.upd_log("🚨 警告！附近检测到受深谙影响的史莱姆区块！")
            else: self.upd_log("✅ 安全！周遭无深谙之域干扰史莱姆区块。")
        except ValueError: pass


    def show_history(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("历史记录")
        dlg.resize(900, 540)
        dlg.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        files = sorted(glob.glob(os.path.join(APP_DIR, "history", "*.json")), reverse=True)
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                params = data.get("search_params", {})
                radius = params.get("radius")
                obs = data.get("obs_count")
                details = [f"种子 {data.get('seed')}", f"规模 {data.get('size')}"]
                if obs is not None:
                    details.append(f"刷怪格数 {obs}")
                if radius is not None:
                    details.append(f"半径 {radius}")
                item = QListWidgetItem(f"{data.get('timestamp', '')}  ·  " + "  ·  ".join(details))
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(data.get("algorithm", ""))
                list_widget.addItem(item)
            except Exception:
                continue
        if list_widget.count() == 0:
            self._empty_history_open_count += 1
            empty_text = "真的没有。" if self._empty_history_open_count == 5 else "暂无历史记录"
            if self._empty_history_open_count >= 6:
                self._empty_history_open_count = 0
                empty_text = "暂无历史记录"
            empty = QListWidgetItem(empty_text)
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(empty)
        else:
            self._empty_history_open_count = 0
        layout.addWidget(list_widget, 1)

        actions = QHBoxLayout()
        load_btn = QPushButton("加载")
        delete_btn = QPushButton("删除")
        close_btn = QPushButton("关闭")
        load_btn.setObjectName("Primary")
        actions.addWidget(delete_btn)
        actions.addStretch()
        actions.addWidget(close_btn)
        actions.addWidget(load_btn)
        layout.addLayout(actions)

        def selected_path():
            item = list_widget.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def load_selected():
            path = selected_path()
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.main_pos = (int(data["x"]), int(data["z"]))
                self.nether_pos = (int(data.get("nether_x", self.main_pos[0] // 8)), int(data.get("nether_z", self.main_pos[1] // 8)))
                self.current_seed = normalize_java_seed(data["seed"])
                self.current_size = int(data.get("size", 0))
                self.current_obs_count = data.get("obs_count")
                self.current_afk_y = data.get("y")
                self.current_algorithm = data.get("algorithm", "历史记录")

                params = data.get("search_params", {})
                history_mc_version = params.get("minecraft_version")
                if history_mc_version == "1.21 WD":
                    history_mc_version = "1.21.4"
                if history_mc_version in SUPPORTED_MC_VERSIONS:
                    self.config.minecraft_version = history_mc_version
                    set_cubiomes_mc_version(history_mc_version)
                seeds = params.get("seeds")
                self.seed_text_edit.setPlainText(",".join(str(v) for v in seeds) if seeds else str(self.current_seed))
                if params.get("radius") is not None:
                    self.radius_input.setText(str(params["radius"]))
                if params.get("center_x") is not None:
                    self.search_center_x_input.setText(str(params["center_x"]))
                if params.get("center_z") is not None:
                    self.search_center_z_input.setText(str(params["center_z"]))
                if params.get("min_radius") is not None:
                    self.config.use_min_radius = int(params["min_radius"]) > 0
                    self.r_inner.setText(str(params["min_radius"]))
                    self.rad_min_label.setVisible(self.config.use_min_radius)
                    self.r_inner.setVisible(self.config.use_min_radius)
                if params.get("min_size") is not None:
                    self.m_min.setText(str(params["min_size"]))
                self.config.use_range = bool(params.get("use_range", False))
                self.max_label.setVisible(self.config.use_range)
                self.m_max.setVisible(self.config.use_range)
                if params.get("max_size") is not None:
                    self.m_max.setText(str(params["max_size"]))
                if "precise_afk" in params:
                    self.chk_precise_afk.setChecked(bool(params["precise_afk"]))
                if "scan_y" in params:
                    self.chk_scan_y.setChecked(bool(params["scan_y"]))
                if params.get("result_limit") is not None:
                    self.config.result_limit = clamp_int(params["result_limit"], DEFAULT_RESULT_LIMIT, 1, MAX_RESULT_LIMIT)
                saved_engine = params.get("engine")
                if saved_engine:
                    idx = self.engine_combo.findText(str(saved_engine))
                    if idx >= 0:
                        self.engine_combo.setCurrentIndex(idx)

                self.top_50_results = data.get("ranked_results", [])
                self._refresh_rank_controls()
                self.apply_projection_settings(data.get("projection", {}))
                self.proj_manual_seed.setText(str(self.current_seed))
                self.proj_manual_x.setText(str(self.main_pos[0]))
                self.proj_manual_z.setText(str(self.main_pos[1]))
                self.proj_manual_y.setText("" if self.current_afk_y is None else str(self.current_afk_y))
                image_path = data.get("image", "")
                if image_path and not os.path.isabs(image_path):
                    image_path = os.path.join(APP_DIR, image_path)
                if image_path and os.path.exists(image_path):
                    self.sw(image_path)
                self.trigger_floor_preview_update()
                self.info.setText(
                    f"历史记录 | 种子: {self.current_seed} | 规模: {self.current_size} | "
                    f"主世界: {self.main_pos} | 地狱: {self.nether_pos}")
                dlg.accept()
            except Exception as e:
                QMessageBox.warning(dlg, "加载失败", str(e))

        def delete_selected():
            path = selected_path()
            item = list_widget.currentItem()
            if not path or item is None:
                return
            if QMessageBox.question(dlg, "删除历史", "确认删除这条历史记录？") != QMessageBox.StandardButton.Yes:
                return
            try:
                os.remove(path)
                list_widget.takeItem(list_widget.row(item))
            except Exception as e:
                QMessageBox.warning(dlg, "删除失败", str(e))

        load_btn.clicked.connect(load_selected)
        delete_btn.clicked.connect(delete_selected)
        close_btn.clicked.connect(dlg.reject)
        list_widget.itemDoubleClicked.connect(lambda _item: load_selected())
        dlg.exec()

    def export_results(self):
        if not self.top_50_results: return
        if filename := QFileDialog.getSaveFileName(self, "导出CSV", "", "CSV Files (*.csv)")[0]:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("排名,种子,规模,最优挂机格数,主世界X,主世界Y,主世界Z,地狱X,地狱Z\n")
                    for r in self.top_50_results:
                        f.write(f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[6] if r[6] is not None else ''},{r[5]},{r[4]//8},{r[5]//8}\n")
            except Exception: pass

    def toggle_pause_search(self):
        if not self._search_in_progress:
            return

        now = time.monotonic()
        self._pause_click_times = [t for t in self._pause_click_times if now - t <= 5.0]
        self._pause_click_times.append(now)
        if len(self._pause_click_times) >= 6:
            self._pause_click_times.clear()
            self.upd_log("你是在测试暂停按钮吗？")

        paused = self._search_paused
        engine = self.active_engine
        if is_gpu_engine(engine):
            native_lib = sc_gpu_lib
        elif engine == "CPU (AVX2/OpenMP)":
            native_lib = sc_cpu_lib
        else:
            native_lib = None

        if not paused:
            self._search_paused = True
            self._pause_started_at = time.time()
            self.c.pause = True
            if native_lib:
                try:
                    native_lib.request_pause()
                except Exception as e:
                    self.upd_log(f"暂停原生任务失败: {e}")
            self.cancel_btn.setText("继续")
            self.time_label.setText("已暂停 · 点击“继续”恢复")
            self.upd_log("搜索已暂停，当前进度与候选结果已保留。")
        else:
            self._native_pause_accum += max(0.0, time.time() - self._pause_started_at)
            self._search_paused = False
            self.c.pause = False
            if native_lib:
                try:
                    native_lib.resume_search()
                except Exception as e:
                    self.upd_log(f"继续原生任务失败: {e}")
            self.cancel_btn.setText("暂停")
            self.time_label.setText("正在继续搜索...")
            self.upd_log("搜索已继续。")


    def update_time(self, t): self.time_label.setText(t if t else "准备就绪")

    def update_btns(self, s):
        self.start_button.setEnabled(s); self.cancel_btn.setEnabled(not s)
        if s:
            self.cancel_btn.setText("暂停")
            self._search_paused = False
            self.c.pause = False
            self._native_scan_active = False
            self._search_in_progress = False
            self.native_progress_timer.stop()
            self._set_progress_busy(False)
            if self._search_cancelled:
                self.progress.setValue(0)
            elif self.progress.value() >= 96:
                self.progress.setValue(100)

    def cleanup_runtime(self):
        self.c.cancel = True
        self.c.pause = False
        self._search_paused = False
        for t in ['native_progress_timer', '_floor_timer']:
            if hasattr(self, t): getattr(self, t).stop()
        cleanup_native_resources()
        QPixmapCache.clear()
        gc.collect()

    def closeEvent(self, event):
        self.config.last_seed, self.config.last_radius = self.seed_text_edit.toPlainText().strip(), self.radius_input.text().strip()
        self.config.selected_engine = self.engine_combo.currentText()
        self.config.precise_afk = self.chk_precise_afk.isChecked()
        self.config.scan_y = self.chk_scan_y.isChecked()
        try:
            self.config.min_size = int(self.m_min.text())
            self.config.search_center_x = int(self.search_center_x_input.text())
            self.config.search_center_z = int(self.search_center_z_input.text())
            if self.config.use_range: self.config.max_size = int(self.m_max.text())
            if self.config.use_min_radius: self.config.min_search_radius = int(self.r_inner.text())
        except ValueError: pass
        self.config.save()
        if QMessageBox.question(self, '确认', '确认退出？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.cleanup_runtime()
            event.accept()
        else: event.ignore()

    def copy_tp(self, mode):
        if self.main_pos is None: return
        p = self.main_pos if mode == "main" else self.nether_pos
        y = self.current_afk_y if mode == "main" and self.current_afk_y is not None else "~"
        QApplication.clipboard().setText(f"/tp @s {p[0]} {y} {p[1]}")
        self._copy_easter_count += 1
        if self._copy_easter_count >= 10:
            self._copy_easter_count = 0
            self.upd_log("复制一次其实就够了")

    def _confirm_low_scale_large_search(self, min_size, radius):
        """One-time three-step warning for very broad low-threshold searches."""
        if min_size >= 40 or radius <= 10000:
            return True

        flag_path = os.path.join(APP_DIR, "data", "low_scale_search_warning_acknowledged.txt")
        if os.path.exists(flag_path):
            return True

        first = QMessageBox(self)
        first.setIcon(QMessageBox.Icon.Warning)
        first.setWindowTitle("先提醒一下")
        first.setText(
            "当前最小规模低于 40。\n\n"
            "这种条件会产生非常多的候选结果，真正耗时的部分可能不再是 GPU 扫描，"
            "而是后续的结果整理、排名和精准比对。"
        )
        continue_1 = first.addButton("我知道了，继续", QMessageBox.ButtonRole.AcceptRole)
        first.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        first.exec()
        if first.clickedButton() is not continue_1:
            return False

        second = QMessageBox(self)
        second.setIcon(QMessageBox.Icon.Question)
        second.setWindowTitle("你真的确定吗？")
        second.setText(
            f"你现在的搜索半径是 {radius:,}。\n\n"
            "范围越大，低规模条件产生的候选数量就可能越夸张，"
            "最后的比对和排名时间也会跟着变长。\n\n"
            "你真的确定要这样搜吗？"
        )
        continue_2 = second.addButton("确定，继续", QMessageBox.ButtonRole.AcceptRole)
        second.addButton("我再想想", QMessageBox.ButtonRole.RejectRole)
        second.exec()
        if second.clickedButton() is not continue_2:
            return False

        third = QMessageBox(self)
        third.setIcon(QMessageBox.Icon.Information)
        third.setWindowTitle("好吧……")
        third.setText(
            "好吧，你执意如此。\n\n"
            "那就开始吧。以后只要确认文件还在，这三段提示就不会再出现；"
            "如果哪天想把它们找回来，删除那个确认文件即可。"
        )
        start_btn = third.addButton("开始搜索", QMessageBox.ButtonRole.AcceptRole)
        third.addButton("算了", QMessageBox.ButtonRole.RejectRole)
        third.exec()
        if third.clickedButton() is not start_btn:
            return False

        try:
            os.makedirs(os.path.dirname(flag_path), exist_ok=True)
            with open(flag_path, "w", encoding="utf-8") as f:
                f.write(
                    "Low-scale large-radius search warning acknowledged.\n"
                    "Delete this file to show the three-step warning again.\n"
                )
        except Exception as e:
            self.upd_log(f"无法保存低规模搜索确认标记，下次仍会提示: {e}")
        return True

    def start_work(self):
        seed_text = self.seed_text_edit.toPlainText().strip()
        if not seed_text:
            self.upd_log("请输入至少一个世界种子。")
            return
        try:
            seeds = [normalize_java_seed(s.strip()) for s in seed_text.replace('，', ',').split(',') if s.strip()]
            if not seeds:
                self.upd_log("没有可用的种子。")
                return
            ms = int(self.m_min.text())
            max_s = int(self.m_max.text()) if self.config.use_range else 9999
            rd_max = int(self.radius_input.text())
            rd_min = int(self.r_inner.text()) if self.config.use_min_radius else 0
            center_block_x = int(self.search_center_x_input.text().strip() or "0")
            center_block_z = int(self.search_center_z_input.text().strip() or "0")
            center_cx = center_block_x >> 4
            center_cz = center_block_z >> 4
            if rd_max <= 0:
                raise ValueError("最大搜索半径必须大于 0。")
            if self._reject_world_border_radius(rd_max):
                return
            if rd_max > MAX_SEARCH_RADIUS:
                raise ValueError(f"最大搜索半径不能超过 {MAX_SEARCH_RADIUS:,} 个区块。")
            if rd_min < 0:
                raise ValueError("最小搜索半径不能小于 0。")
            if rd_min > rd_max:
                raise ValueError("最小搜索半径不能大于最大搜索半径。")
            if (center_cx - rd_max - 8 < -2147483648 or center_cx + rd_max + 8 > 2147483647 or
                center_cz - rd_max - 8 < -2147483648 or center_cz + rd_max + 8 > 2147483647):
                raise ValueError("搜索中心与半径组合超出当前算法支持的区块坐标范围。")
            if ms <= 0:
                raise ValueError("最小规模必须大于 0。")
            if ms > 221:
                raise ValueError("最小规模不能超过 221。")
            if self.config.use_range and max_s < ms:
                raise ValueError("最大规模不能小于最小规模。")
            if self.config.use_range and max_s > 221:
                raise ValueError("最大规模不能超过 221。")
            if not self._confirm_low_scale_large_search(ms, rd_max):
                return
            self.config.min_size = ms
            self.config.max_size = max_s
            self.config.last_seed = seed_text
            self.config.last_radius = str(rd_max)
            self.config.search_center_x = center_block_x
            self.config.search_center_z = center_block_z
            self.config.min_search_radius = rd_min
            self.config.precise_afk = self.chk_precise_afk.isChecked()
            self.config.scan_y = self.chk_scan_y.isChecked()
            self.config.result_limit = clamp_int(getattr(self.config, 'result_limit', DEFAULT_RESULT_LIMIT), DEFAULT_RESULT_LIMIT, 1, MAX_RESULT_LIMIT)
            self.config.selected_engine = self.engine_combo.currentText()
            self.config.save()
            choice = self.engine_combo.currentText()
            engine, engine_reason = resolve_engine_choice(choice)
            self._set_progress_busy(False)
            self.progress.setValue(0)
            self.time_label.setText("准备启动...")
            self.active_engine = engine
            self._native_scan_total_centers = int(2 * rd_max + 1) ** 2
            if hasattr(self, "gpu_perf_label"):
                gpu_short_name = GPU_DEVICE_NAME.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").strip()
                self.gpu_perf_label.setVisible(is_gpu_engine(engine))
                if is_gpu_engine(engine):
                    self._set_gpu_perf_text(f"{gpu_short_name} · -- B/s")
            self._search_cancelled = False
            self._search_paused = False
            self._pause_started_at = 0.0
            self._native_pause_accum = 0.0
            self._search_in_progress = True
            self._search_started_at = time.time()
            self.c.cancel = False
            self.c.pause = False
            self.start_button.setEnabled(False)
            self.cancel_btn.setText("暂停")
            self.cancel_btn.setEnabled(True)
            self.upd_log(f"准备启动搜索，实际引擎：{engine}")
            self.upd_log(engine_reason)
            # Use a main-thread timer as the visible heartbeat for native CPU/GPU
            # scans. run_full_logic updates these fields for each seed before it
            # enters the blocking DLL call.
            self._native_scan_active = False
            self._native_scan_started = time.time()
            self._native_scan_base_pct = 0.0
            self._native_scan_total_seeds = max(1, len(seeds))
            self._native_scan_label = "GPU" if engine == "GPU (CUDA)" else ("CPU" if engine == "CPU (AVX2/OpenMP)" else "原生")
            self._native_scan_lib = sc_gpu_lib if is_gpu_engine(engine) else (sc_cpu_lib if engine == "CPU (AVX2/OpenMP)" else None)
            if is_gpu_engine(engine) or engine == "CPU (AVX2/OpenMP)":
                self._set_progress_busy(True)
            if self.native_progress_timer.isActive():
                self.native_progress_timer.stop()
            self.native_progress_timer.start()
            is_dd_checked = self.chk_dd.isChecked()
            threading.Thread(
                target=run_full_logic,
                args=(self, seeds, rd_max, ms, max_s, self.config.use_range, rd_min,
                      engine, self.config.precise_afk, self.config.scan_y,
                      self.config.result_limit, is_dd_checked, center_cx, center_cz),
                daemon=True).start()
        except ValueError as e:
            self.upd_log(f"输入错误: {e}")
            QMessageBox.warning(self, "输入错误", str(e))
        except Exception as e:
            self.upd_log(f"启动失败: {e}")
            QMessageBox.critical(self, "启动失败", str(e))

    def sw(self, p):
        if os.path.exists(p):
            px = QPixmap(p)
            if not px.isNull():
                self.current_image = p
                try:
                    target_width = max(100, int((self.sc.width() - 50) * 0.85))
                except Exception:
                    target_width = 512
                self.v.setPixmap(px.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation))


def run_app():
    """Application entry point.

    Keep this separate from the __main__ block so packaged builds and direct
    python runs both go through the same startup path. Any unexpected startup
    crash is written to crash.log instead of silently closing.
    """
    app = QApplication(sys.argv)
    ex = SlimeApp()
    app.aboutToQuit.connect(ex.cleanup_runtime)
    ex.show()
    return app.exec()


if __name__ == '__main__':
    try:
        sys.exit(run_app())
    except SystemExit:
        raise
    except Exception as e:
        try:
            import traceback
            with open(os.path.join(APP_DIR, 'crash.log'), 'a', encoding='utf-8') as f:
                f.write('\n===== STARTUP CRASH {} =====\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                traceback.print_exc(file=f)
        except Exception:
            pass
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, '启动失败', '程序启动时发生错误：\n{}\n\n详细信息已写入 crash.log'.format(e))
        except Exception:
            pass
        raise
