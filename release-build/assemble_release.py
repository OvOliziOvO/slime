"""Assemble the checked Windows release from the preceding public executable."""
import base64
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile
import zlib


ROOT = Path(__file__).resolve().parent
BASE_URL = "https://github.com/OvOliziOvO/slime/releases/download/V1.1/SlimeFinder_NVIDIA_10_50.exe"
SOURCE_REF = "1bbcd79c3908276b9c317c4990540314e0d15146"
SOURCE_URL = f"https://raw.githubusercontent.com/OvOliziOvO/slime/{SOURCE_REF}/cuda_x2_z15"
SOURCE_FILES = (
    "README.md", "__init__.py", "app_scan.py", "bitmap_layout.py", "build_cubin.py",
    "cuda_compile.py", "generate_slime_rare_tables.py", "quad_history.py", "tensor_cold.py",
    "x_phase.py", "xp_scan.py", "xp_support.py",
)


def main():
    payload = json.loads(zlib.decompress((ROOT / "release-delta.bin").read_bytes()))
    with urlopen(BASE_URL, timeout=90) as response:
        base = response.read()
    assert sha256(base).hexdigest() == payload["base_sha256"]
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    exe = output / "SlimeFinder_V1.2_Windows_x64.exe"
    with exe.open("wb") as handle:
        for op in payload["operations"]:
            if "copy" in op:
                offset, count = op["copy"]
                handle.write(base[offset:offset + count])
            else:
                handle.write(base64.b64decode(op["literal"], validate=True))
    assert sha256(exe.read_bytes()).hexdigest() == payload["exe_sha256"]
    sources = output / "SlimeFinder_V1.2_CUDA_Source.zip"
    with ZipFile(sources, "w", ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            with urlopen(f"{SOURCE_URL}/{name}", timeout=30) as response:
                archive.writestr(f"cuda_x2_z15/{name}", response.read())
    (output / "SHA256SUMS.txt").write_text("\n".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in (exe, sources)
    ) + "\n", encoding="ascii")
    print("Verified release EXE and CUDA source ZIP")


if __name__ == "__main__":
    main()
