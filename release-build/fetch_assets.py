"""Assemble and verify the release files."""
from base64 import b64decode
from hashlib import file_digest, sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import subprocess
import zlib


DIST = Path("dist")
STAGE = Path("release-build")
WINDOWS = "SlimeFinder_V1.2.1_Windows_x64.exe"
LINUX = "SlimeFinder_V1.2.1_Linux_x86_64.tar.gz"
SOURCE = "SlimeFinder_V1.2.1_CUDA_Source.zip"
PATCH_SHA256 = "a23408ac779181c7de93ce85c63822c69b324d37d5f5149728b0bf95a216b985"
WINDOWS_SHA256 = "a6dfc1c26687ecf1ca5d8f455dc5f2c61b3bda40b48804a1c18b164a4e333119"


def assemble_windows():
    patch = b"".join(part.read_bytes() for part in sorted((STAGE / "windows").glob("*.bin")))
    if sha256(patch).hexdigest() != PATCH_SHA256:
        raise ValueError("Windows patch SHA-256 mismatch")
    document = json.loads(zlib.decompress(patch))
    base_name = "SlimeFinder_V1.2_Windows_x64.exe"
    with TemporaryDirectory() as work:
        subprocess.run(
            ["gh", "release", "download", "V1.2", "--repo", os.environ["GITHUB_REPOSITORY"],
             "--dir", work, "--pattern", base_name],
            check=True,
        )
        base = (Path(work) / base_name).read_bytes()
    if sha256(base).hexdigest() != document["base_sha256"]:
        raise ValueError("Published Windows base SHA-256 mismatch")
    with (DIST / WINDOWS).open("wb") as output:
        for operation in document["operations"]:
            if "copy" in operation:
                offset, count = operation["copy"]
                output.write(base[offset:offset + count])
            else:
                output.write(b64decode(operation["literal"], validate=True))
    verify(DIST / WINDOWS, WINDOWS_SHA256)


def verify(path, expected=None):
    with path.open("rb") as data:
        digest = file_digest(data, "sha256").hexdigest()
    if expected is not None and digest != expected:
        raise ValueError(f"SHA-256 mismatch for {path.name}")
    print(f"Verified {path.name} {digest}", flush=True)
    return f"{digest}  {path.name}\n"


def main():
    DIST.mkdir()
    assemble_windows()
    sums = [verify(DIST / WINDOWS, WINDOWS_SHA256)]
    linux = STAGE / "linux"
    if linux.is_dir():
        with (DIST / LINUX).open("wb") as target:
            for part in sorted(linux.glob("*.bin")):
                target.write(part.read_bytes())
        sums.append(verify(DIST / LINUX, (linux / "sha256").read_text().strip()))

    subprocess.run(
        ["git", "archive", "--format=zip", f"--output={DIST / SOURCE}", "HEAD", "cuda_x2_z15"],
        check=True,
    )
    sums.append(verify(DIST / SOURCE))
    (DIST / "SHA256SUMS.txt").write_text("".join(sums))


if __name__ == "__main__":
    main()
