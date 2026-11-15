"""Rebuild the measured sm_86 support and search modules."""
import argparse
from hashlib import sha256
from pathlib import Path

from .cuda_compile import compile_cubin
from .xp_scan import scan_program
from .xp_support import support_program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ptxas", type=Path, help="Optional path to NVIDIA ptxas")
    parser.add_argument("--emit-ptx", type=Path, help="Write PTX here instead of assembling")
    args = parser.parse_args()
    out = args.emit_ptx or Path(__file__).resolve().with_name("cubin")
    out.mkdir(parents=True, exist_ok=True)
    programs=[support_program(15)]
    programs.extend(
        scan_program(phases,bands,6,4,
                     z_bands=15,packed_counts=True,fuse=True,swap=True,rowloop=False,gate=True,split=True,
                     quad=True,reduce_cold=True,merge_orphan=True,ring_rows=24,vector_bitmaps=True)
        for phases in (1,2) for bands in range(1,16)
    )
    for pt in programs:
        image=pt.encode()
        stem = sha256(image).hexdigest()
        if args.emit_ptx is not None:
            (out / f"{stem}.ptx").write_bytes(image)
            continue
        path = out / f"{stem}.cubin"
        if not path.is_file():
            tmp = path.with_suffix(".new")
            tmp.write_bytes(compile_cubin(image, args.ptxas))
            tmp.replace(path)
    kind = "PTX programs" if args.emit_ptx is not None else "CUDA modules"
    print(f"{len(programs)} {kind} for SM 8.6", flush=True)


if __name__=="__main__":
    main()

