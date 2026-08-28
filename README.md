# Slime Finder V1

Minecraft Java Edition 史莱姆区块聚集搜索器。支持 CUDA / AVX2、精准挂机点与 Y 扫描、排名、历史记录和 Litematica 地板投影。

史莱姆搜索使用精确 Java LCG 与精确圆形统计，不使用概率近似。

## 下载

主程序：[Releases](https://github.com/OvOliziOvO/slime/releases/latest)

统一 EXE：`SlimeFinder_NVIDIA_10_50.exe`，覆盖 GTX 10 / RTX 20 / RTX 30 / RTX 40 / RTX 50 系。

## GPU 性能

测试设备：RTX 3060 Laptop GPU。

**GPU速度统计：全图：峰值 140.71 B/s | 最低 91.00 B/s | 平均 104.06 B/s**

`B/s` 表示每秒检查十亿个候选中心。

## V1 算法

- 32 行共享内存压缩位图，Warp ballot 直接生成史莱姆结果。
- 17×17 滚动方形计数作为严格上界。
- 精确圆形使用 `289 - 68 = 221`，只扣除圆外角落。
- 完整保留 Java `nextInt(10)` rejection 语义。
- Native / Limb32 / Truncated 三条精确 RNG 路径自动短测。
- 128×8 / 256×4 / 256×8 / 512×4 四种 CUDA 线程形状自动选择。
- GPU 负责大范围扫描与 Top-K，CPU/Python 负责后处理和可选世界生成检查。

调试环境变量：

```powershell
$env:SLIME_GPU_V1_SHAPE = "256x4"
$env:SLIME_GPU_V1_RNG = "native"
```

## 噪声 / 群系检查

史莱姆区块搜索本身不需要 `cubiomes.dll`。深谙之域、蘑菇岛等检查需要外置噪声组件。

| 版本 | Minecraft 支持范围 | 下载 |
|---|---|---|
| 旧版 | 1.19 ～ 1.21.4 | [cubiomes_legacy_1.21.4.zip](downloads/cubiomes_legacy_1.21.4.zip) |
| 新版 | 1.19 ～ 26.2 | [cubiomes_latest_26.2.zip](downloads/cubiomes_latest_26.2.zip) |

下载后解压，把 `cubiomes.dll` 放到 EXE 或 `SlimeFinder.py` 同目录。两个 ZIP 都附带 cubiomes 的 MIT License。

### 为什么噪声检查比 GPU 搜索慢？

GPU 主扫描主要是整数 RNG、位图和 popcount；噪声检查则要在 CPU 上运行 Minecraft 世界生成与群系逻辑，并对候选周围多个 Y 和完整 quart 位置进行验证，所以单个候选的成本高很多。

当前流程会先完成 V1 精准排名，再从高到低做群系检查，凑够最终 Top-N 后立即停止。

## 正确性

当前回归覆盖 CPU/GPU 结果集合、三条 GPU RNG、Y 精准评分、候选缓冲、深谙/蘑菇岛过滤、投影坐标与保存/重载。

最近完整回归：

```text
ACCURACY_AUDIT_OK
CPU_GPU_MATRIX_OK
MUSHROOM_FAST_MISMATCH 0
DEEP_FAST_MISMATCH 0
BUFFER_INTEGRITY_OK
PROJECTION_ROUNDTRIP_OK
```

## 源码

- `SlimeCoreGPU.cu`：V1 CUDA 搜索核心。
- `SlimeCore.cpp`：AVX2/OpenMP CPU 核心。
- `SlimeFinder.py`：PyQt6 前端、排名、群系检查与投影。

从源码运行：

```powershell
python -m pip install -r requirements.txt
python .\SlimeFinder.py
```

`cubiomes.dll` 不打包进 Release EXE；其源码与许可归对应上游项目所有。
