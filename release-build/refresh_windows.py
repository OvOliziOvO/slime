"""Update the SlimeFinder V1.2.1 frozen Python entry point and CUDA adapter."""
import argparse
import dis
from hashlib import sha256
import marshal
from pathlib import Path
import struct
import sys
from types import CodeType
import zlib

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter

from gui_progress import _sample_gpu_perf, wrap_heartbeat


SCRIPT_SHA256 = "3586d67e629d94cb70d79ae6ba9a93fb9d1189c47e52166bedaf780770eb1442"
HEARTBEAT = "run_full_logic.<locals>.run_native_scan_with_heartbeat"
SAMPLER = "SlimeApp._sample_gpu_perf"


def preserve_startup_cancel(code):
    # start_work() clears the flag before starting the thread. Clearing it a
    # second time in run_full_logic() can discard a click during setup.
    instructions = list(dis.get_instructions(code))
    matches = [index for index in range(len(instructions) - 4)
               if [(ins.opname, ins.argval) for ins in instructions[index:index + 4]]
               == [("LOAD_CONST", False), ("LOAD_DEREF", "app"),
                   ("LOAD_ATTR", "c"), ("STORE_ATTR", "cancel")]]
    if len(matches) != 1:
        raise ValueError("Unexpected V1.2.1 cancellation assignment")
    index = matches[0]
    start, end = instructions[index].offset, instructions[index + 4].offset
    # Replace the assignment and its inline caches at the original offsets.
    padding = bytes((dis.opmap["NOP"], 0)) * ((end - start) // 2)
    return code.replace(co_code=code.co_code[:start] + padding + code.co_code[end:])


def update_entry_point(payload):
    if sys.version_info[:2] != (3, 13) or sha256(payload).hexdigest() != SCRIPT_SHA256:
        raise ValueError("Expected the original V1.2.1 Python 3.13 entry point")
    wrapper = wrap_heartbeat(None, None).__code__
    patched = set()

    def rewrite(code):
        if code.co_qualname == HEARTBEAT:
            placeholder, = [item for item in wrapper.co_consts if isinstance(item, CodeType)]
            if not (code.co_freevars == wrapper.co_freevars == placeholder.co_freevars
                    and code.co_argcount == wrapper.co_argcount == placeholder.co_argcount):
                raise ValueError("V1.2.1 heartbeat signature changed")
            patched.add(HEARTBEAT)
            wrapped_consts = tuple(code if item is placeholder else item for item in wrapper.co_consts)
            return wrapper.replace(co_consts=wrapped_consts, co_qualname=code.co_qualname)
        if code.co_qualname == SAMPLER:
            patched.add(SAMPLER)
            return _sample_gpu_perf.__code__.replace(co_qualname=code.co_qualname)
        rewritten = code.replace(co_consts=tuple(
            rewrite(item) if isinstance(item, CodeType) else item for item in code.co_consts
        ))
        if code.co_qualname == "run_full_logic":
            patched.add("run_full_logic")
            return preserve_startup_cancel(rewritten)
        return rewritten

    result = rewrite(marshal.loads(payload))
    if patched != {HEARTBEAT, SAMPLER, "run_full_logic"}:
        raise ValueError(f"Incomplete GUI update: {patched}")
    return marshal.dumps(result)


def refresh_windows(original, output):
    if original.resolve() == output.resolve():
        raise ValueError("Use a separate output file")
    archive = CArchiveReader(str(original))
    changes = {
        "SlimeFinder": update_entry_point(archive.extract("SlimeFinder")),
        **{f"cuda_x2_z15\\{name}": Path("cuda_x2_z15", name).read_bytes()
           for name in ("app_scan.py", "xp_scan.py")},
    }
    if not changes.keys() <= archive.toc.keys():
        raise ValueError("V1.2.1 executable is missing expected archive members")

    with original.open("rb") as source, output.open("wb") as target:
        target.write(source.read(archive._start_offset))
        source.seek(archive._end_offset - archive._COOKIE_LENGTH)
        magic, _, _, _, pyversion, pylib = struct.unpack(
            archive._COOKIE_FORMAT, source.read(archive._COOKIE_LENGTH)
        )
        if pyversion != 313 or source.read(1):
            raise ValueError("Unexpected Python version or data following the archive")

        start = target.tell()
        toc = []
        for option in archive.options:
            toc.append((0, 0, 0, 0, "o", option))
        for name, (offset, size, length, compressed, kind) in archive.toc.items():
            if name in changes:
                payload = changes[name]
                length = len(payload)
                data = zlib.compress(payload, 9) if compressed else payload
            else:
                source.seek(archive._start_offset + offset)
                data = source.read(size)
                if len(data) != size:
                    raise ValueError(f"Truncated archive member {name}")
            toc.append((target.tell() - start, len(data), length, compressed, kind, name))
            target.write(data)

        toc_offset = target.tell() - start
        toc_data = CArchiveWriter._serialize_toc(toc)
        target.write(toc_data)
        target.write(struct.pack(
            archive._COOKIE_FORMAT, magic, toc_offset + len(toc_data) + archive._COOKIE_LENGTH,
            toc_offset, len(toc_data), pyversion, pylib,
        ))

    result = CArchiveReader(str(output))
    if result.toc.keys() != archive.toc.keys() or result.options != archive.options:
        raise ValueError("Updated archive layout differs from the original")
    for name, expected in changes.items():
        if result.extract(name) != expected:
            raise ValueError(f"Updated archive member failed validation: {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    refresh_windows(args.original, args.output)
