#!/usr/bin/env bash
set -euo pipefail

app=SlimeFinder_V1.2.1_Linux_x86_64
libs="$app/release/universal"
mkdir -p "$libs"
g++-13 -std=c++17 -O3 -fPIC -fopenmp -shared -o "$libs/libslimecore.so" linux-native-source/SlimeCore.cpp

cuda="$PWD/cuda-12.9"
mkdir "$cuda"
python3 - "$cuda" <<'PY'
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest
from pathlib import Path
import subprocess
import sys

toolkit = Path(sys.argv[1])
url = "https://developer.download.nvidia.com/compute/cuda/redist"
packages = [
    ("cuda_nvcc", "12.9.86", "7a1a5b652e5ef85c82b721d10672fc9a2dbaab44e9bd3c65a69517bf53998c35"),
    ("cuda_cudart", "12.9.79", "1f6ad42d4f530b24bfa35894ccf6b7209d2354f59101fd62ec4a6192a184ce99"),
    ("cuda_cccl", "12.9.27", "8b1a5095669e94f2f9afd7715533314d418179e9452be61e2fde4c82a3e542aa"),
    ("cuda_cuobjdump", "12.9.82", "ee0de40e8c18068bfcc53e73510e7e7a1a80555205347940df67fa525d24452f"),
]

def fetch(item):
    component, version, expected = item
    name = f"{component}-linux-x86_64-{version}-archive.tar.xz"
    archive = toolkit / name
    subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--retry", "2", "--location",
         f"{url}/{component}/linux-x86_64/{name}", "--output", str(archive)],
        check=True,
    )
    with archive.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != expected:
            raise ValueError(f"Unexpected checksum for {name}")
    return archive

with ThreadPoolExecutor(max_workers=4) as pool:
    archives = list(pool.map(fetch, packages))
for archive in archives:
    subprocess.run(["tar", "xf", str(archive), "-C", str(toolkit), "--strip-components=1"], check=True)
    archive.unlink()
PY
ln -s lib "$cuda/lib64"
flags=()
for arch in 61 75 86 89; do
  flags+=(-gencode "arch=compute_$arch,code=sm_$arch")
done
flags+=(-gencode arch=compute_61,code=compute_61 -gencode arch=compute_89,code=compute_89)
nvcc=("$cuda/bin/nvcc" --compiler-bindir /usr/bin/g++-13 -O3 -std=c++17 --threads 2 -Xcompiler=-fPIC -Xcompiler=-pthread --shared "${flags[@]}")
"${nvcc[@]}" -o "$libs/libslimecore_gpu.so" linux-native-source/SlimeCoreGPU.cu > search-build.log 2>&1 &
search=$!
"${nvcc[@]}" -o "$libs/libminecraft_gpu_modern.so" linux-native-source/gpu_noise/MinecraftGPUNoise.cu > noise-build.log 2>&1 &
noise=$!
result=0
wait "$search" || result=$?
wait "$noise" || result=$?
cat search-build.log noise-build.log
test "$result" = 0
for lib in "$libs"/lib*gpu*.so; do
  "$cuda/bin/cuobjdump" -lelf "$lib" > gpu-images.txt
  for arch in 61 75 86 89; do grep -q "sm_$arch.cubin" gpu-images.txt; done
  "$cuda/bin/cuobjdump" -lptx "$lib" | grep 'sm_89.ptx'
done

install -m 755 release-build/run_linux.sh "$app/run_linux.sh"
install -m 644 release-build/linux-readme.md "$app/README.md"
printf '%s\n' numpy PyQt6 > "$app/requirements-linux.txt"
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 - "$app" <<'PY'
import ctypes
import importlib.util
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
for filename in ("libslimecore.so", "libslimecore_gpu.so", "libminecraft_gpu_modern.so"):
    ctypes.CDLL(str(root / "release" / "universal" / filename))
spec = importlib.util.spec_from_file_location("SlimeFinder", root / "SlimeFinder.pyc")
finder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = finder
spec.loader.exec_module(finder)
assert finder.APP_VERSION == "V1.2.1"
from cuda_x2_z15.app_scan import is_eligible
assert is_eligible(393216, 55, 221, 0, True, 0, 0)
qt = finder.QApplication([])
window = finder.SlimeApp()
window.show()
qt.processEvents()
assert window.isVisible() and "V1.2.1" in window.windowTitle()
rows, count = finder.run_cpu_scan(123456789, 32, 17, 221, 0, 128, 2, True)[:2]
assert count >= 0 and len(rows) == min(count, 128)
print("Linux GUI and CPU search smoke test passed", flush=True)
PY

mkdir -p linux-dist
tar -czf "linux-dist/$app.tar.gz" "$app"
tar -tzf "linux-dist/$app.tar.gz" | awk '/[.]cubin$/{count++} END {print "Packaged CUDA modules",count; exit count!=155}'
(cd linux-dist && sha256sum "$app.tar.gz" > linux-sha256.txt)
