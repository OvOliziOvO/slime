"""Adapter for the GUI's large, high-threshold exact searches."""
from time import sleep

from .xp_scan import ExactScan, ScanDriver
from .x_phase import UnsupportedDevice

ALGORITHM_NAME = "CUDA 双 X Phase · 15 Z Band · Tensor Core"


def is_eligible(radius, minimum, maximum, inner_radius, precise, x, z):
    return (
        precise
        and inner_radius == 0
        and 393_216 <= radius
        and max(abs(x), abs(z)) + radius <= 1_875_000
        and 55 <= minimum <= 60
        and maximum >= 221
    )


def scan_candidates(seed, radius, minimum, x, z, controls):
    def checkpoint():
        while controls.pause and not controls.cancel:
            sleep(0.05)
        if controls.cancel:
            raise InterruptedError("Search cancelled")

    checkpoint()
    driver = ScanDriver(required_capability=(8, 6))
    try:
        scan = ExactScan(6, 4, driver=driver, verbose=False)
        scan.prepare(2 * radius + 1, True)
        hits, _elapsed = scan.scan(seed, radius, minimum, x, z, True, checkpoint=checkpoint)
        return sorted(hits, key=lambda row: (-row[0], row[1], row[2]))
    finally:
        driver.close()
