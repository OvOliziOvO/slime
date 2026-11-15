"""Assemble and verify the signed transfer files before publishing."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen
import json
import sys


CHUNK_BYTES = 2 * 1024 * 1024


def fetch_range(url, start, end, asset_size):
    request = Request(url, headers={"Range": f"bytes={start}-{end}"})
    expected_size = end - start + 1
    for attempt in range(3):
        try:
            with urlopen(request, timeout=55) as response:
                if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{asset_size}":
                    raise ValueError("Server did not return the requested range")
                data = response.read(expected_size + 1)
            if len(data) != expected_size:
                raise ValueError("Incomplete asset range")
            return data
        except (OSError, ValueError) as exc:
            print(f"Retrying asset range {start}-{end} ({type(exc).__name__})", file=sys.stderr, flush=True)
            if attempt == 2:
                raise RuntimeError(f"Could not fetch asset range {start}-{end}") from None
            sleep(2 ** attempt)


def main():
    manifest = json.loads(Path("release-build/asset-urls.json").read_bytes())
    dist = Path("dist")
    dist.mkdir()
    sums = []
    for asset in manifest["assets"]:
        size = asset["size"]
        target = dist / asset["name"]
        print(f"Downloading {target.name} ({size} bytes)", flush=True)
        starts = list(range(0, size, CHUNK_BYTES))
        with ThreadPoolExecutor(max_workers=12) as pool, target.open("wb") as output:
            for chunk in pool.map(
                lambda start: fetch_range(asset["url"], start, min(start + CHUNK_BYTES, size) - 1, size),
                starts,
            ):
                output.write(chunk)
        with target.open("rb") as stream:
            digest = file_digest(stream, "sha256").hexdigest()
        if digest != asset["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {target.name}")
        sums.append(f"{digest}  {target.name}\n")
        print(f"Verified {target.name}", flush=True)
    (dist / "SHA256SUMS.txt").write_text("".join(sums))


if __name__ == "__main__":
    main()
