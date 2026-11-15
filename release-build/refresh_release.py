"""Stage and verify replacement files before updating the existing V1.2.1 release."""
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


TAG = "V1.2.1"
NAMES = (
    "SlimeFinder_V1.2.1_Windows_x64.exe",
    "SlimeFinder_V1.2.1_Linux_x86_64.tar.gz",
    "SlimeFinder_V1.2.1_CUDA_Source.zip",
    "SHA256SUMS.txt",
)
DIST = Path("dist")


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def release_assets(repo):
    release = json.loads(gh("api", f"repos/{repo}/releases/tags/{TAG}"))
    if release["tag_name"] != TAG or release["draft"] or release.get("immutable"):
        raise RuntimeError(f"The existing {TAG} release must be published and editable")
    return {asset["name"]: asset for asset in release["assets"]}


def rename(repo, asset, name):
    gh("api", "-X", "PATCH", f"repos/{repo}/releases/assets/{asset['id']}",
       "-f", f"name={name}")


def delete(repo, asset):
    gh("api", "-X", "DELETE", f"repos/{repo}/releases/assets/{asset['id']}")


def refresh(repo, suffix):
    from hashlib import file_digest

    manifest = dict(line.split(maxsplit=1)[::-1]
                    for line in (DIST / "SHA256SUMS.txt").read_text().splitlines())
    with (DIST / "SHA256SUMS.txt").open("rb") as stream:
        manifest["SHA256SUMS.txt"] = file_digest(stream, "sha256").hexdigest()
    original = release_assets(repo)
    for name, digest in manifest.items():
        if name not in NAMES and original[name]["digest"] != f"sha256:{digest}":
            raise RuntimeError(f"Existing asset digest mismatch: {name}")
    changed = [name for name in NAMES if original[name]["digest"] != f"sha256:{manifest[name]}"]
    if not changed:
        print(f"{TAG} already has all expected assets")
        return

    staged_names = {name: f"{name}.staged-{suffix}" for name in changed}
    backup_names = {name: f"{name}.previous-{suffix}" for name in changed}
    if set(staged_names.values()) & original.keys() or set(backup_names.values()) & original.keys():
        raise RuntimeError("A previous attempt already used these staging names")

    try:
        with TemporaryDirectory(dir=DIST) as tmp:
            staged = []
            for name in changed:
                path = Path(tmp, staged_names[name])
                os.link(DIST / name, path)
                staged.append(str(path))
            gh("release", "upload", TAG, "--repo", repo, *staged)

        current = release_assets(repo)
        for name in changed:
            asset = current[staged_names[name]]
            if asset["state"] != "uploaded" or asset["digest"] != f"sha256:{manifest[name]}":
                raise RuntimeError(f"Staged asset failed verification: {name}")
            if current[name]["id"] != original[name]["id"]:
                raise RuntimeError(f"Existing asset changed during staging: {name}")

        for name in changed:
            rename(repo, original[name], backup_names[name])
            rename(repo, current[staged_names[name]], name)

        refreshed = release_assets(repo)
        for name, digest in manifest.items():
            if refreshed[name]["digest"] != f"sha256:{digest}":
                raise RuntimeError(f"Published asset digest mismatch: {name}")
    except Exception:
        current = release_assets(repo)
        for name in reversed(changed):
            previous = current.get(backup_names[name])
            if previous:
                if name in current:
                    rename(repo, current[name], staged_names[name])
                rename(repo, previous, name)
        current = release_assets(repo)
        for staged in staged_names.values():
            if staged in current:
                delete(repo, current[staged])
        raise

    for name in changed:
        delete(repo, original[name])
        print(f"Verified {name} sha256:{manifest[name]}", flush=True)


if __name__ == "__main__":
    refresh(os.environ["GITHUB_REPOSITORY"],
            f"{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}")
