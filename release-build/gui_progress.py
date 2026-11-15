"""Source for the functions updated in the shipped Python 3.13 entry point."""


def wrap_heartbeat(app, emit_progress):
    def run_native_scan_with_heartbeat(label, seed, scan_callable, native_lib,
                                       seed_base_pct, total_seeds, start_time):
        def original(label, seed, scan_callable, native_lib,
                     seed_base_pct, total_seeds, start_time):
            # The build inserts the shipped heartbeat here with these closure cells.
            return app, emit_progress

        if native_lib is None or not label.startswith("GPU"):
            return original(label, seed, scan_callable, native_lib,
                            seed_base_pct, total_seeds, start_time)

        from cuda_x2_z15.app_scan import ScanTelemetry

        telemetry = ScanTelemetry(native_lib)
        controls = app.c
        controls._scan_telemetry = telemetry
        try:
            return original("GPU", seed, scan_callable, telemetry,
                            seed_base_pct, total_seeds, start_time)
        finally:
            controls._scan_telemetry = None

    return run_native_scan_with_heartbeat


def _sample_gpu_perf(self, lib):
    if not lib:
        return None
    try:
        if hasattr(lib, "speed_sample"):
            backend, centers, work_ns = lib.speed_sample()
        else:
            backend = "native"
            centers = lib.get_processed_centers()
            work_ns = lib.get_gpu_scan_work_ns()
        if getattr(self, "_gpu_perf_backend", None) != backend:
            self._reset_gpu_perf_stats()
            self._gpu_perf_backend = backend

        centers, work_ns = max(0, int(centers)), max(0, int(work_ns))
        delta_centers = centers - self._gpu_perf_prev_centers
        delta_work_ns = work_ns - self._gpu_perf_prev_work_ns
        self._gpu_perf_prev_centers = self._gpu_perf_total_centers = centers
        self._gpu_perf_prev_work_ns = self._gpu_perf_total_work_ns = work_ns
        if delta_centers > 0 and delta_work_ns > 0:
            # Centers per nanosecond equals billions of centers per second.
            speed = delta_centers / delta_work_ns
            self._gpu_perf_samples.append(speed)
            return speed
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    return None
