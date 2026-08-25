"""V34 RNG exactness check and interleaved GPU benchmark."""

from __future__ import annotations

import argparse
import ctypes
import statistics
import time
from pathlib import Path


class Result(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_int32),
        ("center_x", ctypes.c_int32),
        ("center_z", ctypes.c_int32),
        ("obs_count", ctypes.c_int32),
        ("afk_x", ctypes.c_int32),
        ("afk_z", ctypes.c_int32),
    ]


SIGNATURE = [
    ctypes.c_int64,
    ctypes.c_int64,
    ctypes.c_int32,
    ctypes.c_int32,
    ctypes.c_int64,
    ctypes.POINTER(Result),
    ctypes.c_int32,
    ctypes.c_int32,
]


def bind(dll: ctypes.CDLL):
    fn = dll.search_slime_clusters_gpu_v34
    fn.argtypes = SIGNATURE
    fn.restype = ctypes.c_int64
    set_rng = dll.set_gpu_v34_rng_override
    set_rng.argtypes = [ctypes.c_int32]
    set_rng.restype = None
    return fn, set_rng


def run(fn, set_rng, rng: int, seed: int, radius: int, threshold: int, capacity: int):
    buffer = (Result * capacity)()
    set_rng(rng)
    start = time.perf_counter()
    count = int(fn(seed, radius, threshold, 289, 0, buffer, capacity, 0))
    elapsed = time.perf_counter() - start
    copied = min(max(count, 0), capacity)
    values = {
        (buffer[i].size, buffer[i].center_x, buffer[i].center_z)
        for i in range(copied)
    }
    return count, values, elapsed


def verify(fn, set_rng, radius: int, capacity: int) -> None:
    cases = [
        (0, radius, 42, 289, 0),
        (123456789, radius + 37, 45, 289, 0),
        (-987654321, radius + 91, 50, 289, radius // 2),
        (2**63 - 1, radius + 113, 42, 60, radius // 3),
        (-2**63, radius + 171, 43, 289, radius // 2),
    ]
    for case in cases:
        seed, rd_max, min_size, max_size, rd_min = case
        outputs = []
        for rng in (0, 1, 2):
            buffer = (Result * capacity)()
            set_rng(rng)
            count = int(
                fn(
                    seed,
                    rd_max,
                    min_size,
                    max_size,
                    rd_min,
                    buffer,
                    capacity,
                    0,
                )
            )
            if count > capacity:
                raise RuntimeError(
                    f"verification buffer too small: {count} > {capacity}"
                )
            values = {
                (buffer[i].size, buffer[i].center_x, buffer[i].center_z)
                for i in range(max(count, 0))
            }
            outputs.append((count, values))
        exact = outputs[0] == outputs[1] == outputs[2]
        print(f"verify {case}: counts={[x[0] for x in outputs]} exact={exact}")
        if not exact:
            raise SystemExit(1)


def benchmark(fn, set_rng, seed: int, radius: int, threshold: int, capacity: int, cycles: int):
    centers = (2 * radius + 1) ** 2
    rates = {0: [], 1: [], 2: []}
    for rng in (0, 1, 2):
        set_rng(rng)
        fn(seed, 1000, threshold, 289, 0, (Result * 1)(), 1, 0)

    for _ in range(cycles):
        for rng in (0, 1, 2, 2, 1, 0):
            count, _, elapsed = run(
                fn, set_rng, rng, seed, radius, threshold, capacity
            )
            rate = centers / elapsed / 1e9
            rates[rng].append(rate)
            name = {0: "Native", 1: "Limb32", 2: "Truncated"}[rng]
            print(
                f"{name} count={count} time={elapsed:.6f}s "
                f"throughput={rate:.3f} B/s"
            )

    native = statistics.median(rates[0])
    limb32 = statistics.median(rates[1])
    truncated = statistics.median(rates[2])
    delta = (truncated / native - 1.0) * 100.0
    print(
        f"median: Native={native:.3f} B/s Limb32={limb32:.3f} B/s "
        f"Truncated={truncated:.3f} B/s trunc_delta={delta:+.2f}% "
        f"V34_best={max(max(v) for v in rates.values()):.3f} B/s"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", type=Path, default=Path(__file__).parents[1] / "slimecore_gpu.dll")
    parser.add_argument("--seed", type=int, default=123456789)
    parser.add_argument("--radius", type=int, default=80000)
    parser.add_argument("--threshold", type=int, default=45)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--capacity", type=int, default=200000)
    parser.add_argument("--verify-radius", type=int, default=1000)
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    dll = ctypes.CDLL(str(args.dll.resolve()))
    fn, set_rng = bind(dll)
    if not args.skip_verify:
        verify(fn, set_rng, args.verify_radius, args.capacity)
    benchmark(
        fn,
        set_rng,
        args.seed,
        args.radius,
        args.threshold,
        args.capacity,
        args.cycles,
    )


if __name__ == "__main__":
    main()
