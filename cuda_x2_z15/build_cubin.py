"""Build the CUDA support and search modules for the selected GPU targets."""
import argparse
from pathlib import Path

from .cuda_compile import RELEASE_ARCHS, compile_cubin, cubin_path, target_program
from .xp_scan import scan_program
from .xp_support import support_program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ptxas", type=Path, help="Optional path to NVIDIA ptxas")
    parser.add_argument("--emit-ptx", type=Path, help="Write PTX here instead of assembling")
    parser.add_argument("--arch", type=int, nargs="+", choices=RELEASE_ARCHS, default=RELEASE_ARCHS)
    args = parser.parse_args()
    programs=[support_program(15)]
    programs.extend(
        scan_program(phases,bands,6,4,
                     z_bands=15,packed_counts=True,fuse=True,swap=True,rowloop=False,gate=True,split=True,
                     quad=True,reduce_cold=True,merge_orphan=True,ring_rows=24,vector_bitmaps=True)
        for phases in (1,2) for bands in range(1,16)
    )
    for arch in args.arch:
        for program in programs:
            image = target_program(program, arch)
            path = cubin_path(image, arch)
            if args.emit_ptx is not None:
                path = args.emit_ptx / path.parent.name / path.with_suffix(".ptx").name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(image)
            elif not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".new")
                tmp.write_bytes(compile_cubin(image, arch, args.ptxas))
                tmp.replace(path)
        kind = "PTX programs" if args.emit_ptx is not None else "CUDA modules"
        print(f"{len(programs)} {kind} for SM {arch}", flush=True)


if __name__ == "__main__":
    main()
