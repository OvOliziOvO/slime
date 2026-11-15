"""Adapter for the GUI's large, high-threshold exact searches."""
from time import perf_counter_ns, sleep

from .xp_scan import ExactScan, ScanDriver

ALGORITHM_NAME = "CUDA 双 X Phase · 15 Z Band"


def is_eligible(radius, minimum, maximum, inner_radius, precise, x, z):
    return (
        precise
        and inner_radius == 0
        and 393_216 <= radius
        and max(abs(x), abs(z)) + radius <= 1_875_000
        and 55 <= minimum <= 60
        and maximum >= 221
    )


class ScanTelemetry:
    """Per-search progress shared between the scan worker and Qt polling."""

    def __init__(self, native_lib):
        self._native_lib = native_lib
        self._ptx = None

    def begin_ptx(self, total):
        self._ptx = (total, 0, 0, False)

    def report_ptx(self, centers, work_ns, complete):
        total = self._ptx[0]
        self._ptx = (total, centers, work_ns, complete)

    def use_native(self):
        self._ptx = None

    def get_progress(self):
        ptx = self._ptx
        if ptx is None:
            return self._native_lib.get_progress()
        total, centers, _, complete = ptx
        return 100 if complete else min(99, 100 * centers // total)

    def speed_sample(self):
        ptx = self._ptx
        if ptx is None:
            return "native", self._native_lib.get_processed_centers(), self._native_lib.get_gpu_scan_work_ns()
        _, centers, work_ns, _ = ptx
        return "ptx", centers, work_ns

    def request_cancel(self):
        self._native_lib.request_cancel()


def scan_candidates(seed, radius, minimum, x, z, controls):
    telemetry = getattr(controls, "_scan_telemetry", None)
    width = 2 * radius + 1
    paused_ns = 0

    def checkpoint():
        nonlocal paused_ns
        if controls.pause and not controls.cancel:
            paused_at = perf_counter_ns()
            while controls.pause and not controls.cancel:
                sleep(0.05)
            paused_ns += perf_counter_ns() - paused_at
        if controls.cancel:
            raise InterruptedError("Search cancelled")

    driver = None
    if telemetry is not None:
        telemetry.begin_ptx(width * width)
    try:
        checkpoint()
        driver = ScanDriver()
        scan = ExactScan(6, 4, driver=driver, verbose=False)
        scan.prepare(width, True, checkpoint=checkpoint)
        checkpoint()
        paused_ns = 0
        started = perf_counter_ns()

        def report(centers, complete):
            telemetry.report_ptx(centers, perf_counter_ns() - started - paused_ns, complete)

        hits, _elapsed = scan.scan(
            seed, radius, minimum, x, z, True,
            checkpoint=checkpoint, progress=report if telemetry is not None else None,
        )
        return sorted(hits, key=lambda row: (-row[0], row[1], row[2]))
    except (OSError, RuntimeError, MemoryError):
        # The GUI may continue on the native CUDA path after an eligible
        # PTX search fails. Its counters belong to that new scan.
        if telemetry is not None and not controls.cancel:
            telemetry.use_native()
        raise
    finally:
        if driver is not None:
            driver.close()
