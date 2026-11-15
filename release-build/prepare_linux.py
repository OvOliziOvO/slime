"""Use the verified V1.2.1 app entry point and cubins in a Linux package."""
from importlib.util import MAGIC_NUMBER
from pathlib import Path, PureWindowsPath
import marshal
import re
import shutil
import struct
import sys

from PyInstaller.archive.readers import CArchiveReader


app = Path("SlimeFinder_V1.2.1_Linux_x86_64")
exe = Path("dist/SlimeFinder_V1.2.1_Windows_x64.exe")
archive = CArchiveReader(str(exe))
script = archive.extract("SlimeFinder")
marshal.loads(script)
app.mkdir()
(app / "SlimeFinder.pyc").write_bytes(MAGIC_NUMBER + struct.pack("<III", 0, 0, 0) + script)
(app / "color_card").write_bytes(archive.extract("color_card"))
shutil.copytree("cuda_x2_z15", app / "cuda_x2_z15")
shutil.copyfile("gpu_noise/LICENSE.cubiomes", app / "LICENSE.cubiomes")

counts = {arch: 0 for arch in ("61", "75", "86", "89", "120")}
for name in archive.toc:
    path = PureWindowsPath(name)
    match = re.fullmatch(r"cuda_x2_z15/cubin/sm_(61|75|86|89|120)/[0-9a-f]{64}\.cubin", path.as_posix())
    if match:
        target = app.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.extract(name))
        counts[match.group(1)] += 1
if set(counts.values()) != {31}:
    sys.exit(f"Unexpected CUDA module counts: {counts}")

native = Path("linux-native-source")
native.mkdir()
for name in ("SlimeCore.cpp", "SlimeCoreGPU.cu"):
    source = Path(name).read_text(encoding="utf-8-sig")
    (native / name).write_text(source.replace("__declspec(dllexport)", ""))
shutil.copytree("gpu_noise", native / "gpu_noise")
noise = native / "gpu_noise/MinecraftGPUNoise.cu"
noise.write_text(noise.read_text(encoding="utf-8-sig").replace("__declspec(dllexport)", ""))
