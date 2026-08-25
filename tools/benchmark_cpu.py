"""Exactness check and benchmark for the native CPU search core."""

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
    ctypes.c_int64, ctypes.c_int64, ctypes.c_int32, ctypes.c_int32,
    ctypes.c_int64, ctypes.POINTER(Result), ctypes.c_int32,
    ctypes.c_int32, ctypes.c_int32,
]


def bind(path: Path):
    dll = ctypes.CDLL(str(path.resolve()))
    fn = dll.search_slime_clusters
    fn.argtypes = SIGNATURE
    fn.restype = ctypes.c_int64
    return dll, fn


def run(
    fn, seed: int, radius: int, threshold: int, capacity: int, threads: int,
    max_size: int = 289, rd_min: int = 0,
):
    buf = (Result * capacity)()
    start = time.perf_counter()
    count = int(fn(seed, radius, threshold, max_size, rd_min, buf, capacity, threads, 0))
    elapsed = time.perf_counter() - start
    copied = min(max(count, 0), capacity)
    values = {(buf[i].size, buf[i].center_x, buf[i].center_z) for i in range(copied)}
    return count, values, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", type=Path, default=Path(__file__).parents[1] / "slimecore.dll")
    parser.add_argument("--reference-dll", type=Path)
    parser.add_argument("--seed", type=int, default=123456789)
    parser.add_argument("--radius", type=int, default=5000)
    parser.add_argument("--threshold", type=int, default=45)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--capacity", type=int, default=200000)
    args = parser.parse_args()
    threads = args.threads or (__import__("os").cpu_count() or 1)
    _, fn = bind(args.dll)
    if args.reference_dll:
        _, ref = bind(args.reference_dll)
        cases = (
            (0, 511, 25, 289, 0),
            (-987654321, 537, 45, 289, 200),
            (2**63 - 1, 593, 42, 60, 197),
            (-2**63, 617, 43, 289, 300),
        )
        for seed, radius, threshold, max_size, rd_min in cases:
            a = run(ref, seed, radius, threshold, args.capacity, threads, max_size, rd_min)[:2]
            b = run(fn, seed, radius, threshold, args.capacity, threads, max_size, rd_min)[:2]
            print(f"verify seed={seed} radius={radius}: counts={a[0]},{b[0]} exact={a == b}")
            if a != b:
                raise SystemExit(1)
    rates = []
    centers = (2 * args.radius + 1) ** 2
    for _ in range(args.cycles):
        count, _, elapsed = run(fn, args.seed, args.radius, args.threshold, args.capacity, threads)
        rate = centers / elapsed / 1e6
        rates.append(rate)
        print(f"count={count} time={elapsed:.6f}s throughput={rate:.3f} Mcenter/s")
    print(f"median={statistics.median(rates):.3f} Mcenter/s best={max(rates):.3f} Mcenter/s threads={threads}")


if __name__ == "__main__":
    main()
