# Slime Finder V1.1

**English** | [简体中文](README.zh-CN.md)

High-performance Minecraft Java Edition slime farm site-selection tool.

A CUDA / AVX2-accelerated slime chunk finder for large-area and full-world slime farm searches.

The new search algorithms are now available on GTX 10 / RTX 20 / RTX 30 / RTX 40 / RTX 50. The program automatically selects an implementation for the current GPU. The speed examples below were measured on an RTX 3060 Laptop GPU; performance on other models still requires real-device verification.

Designed to search for slime-chunk clusters across large areas or even the entire Java world, then perform exact AFK-range statistics, AFK Y scanning, final candidate ranking, and biome filtering.

- NVIDIA CUDA / AVX2
- Exact Java 48-bit LCG
- Exact 221-chunk AFK-circle statistics
- Top-N final candidate ranking
- Deep Dark / Mushroom Fields biome filtering
- Litematica floor projection
- Automatic GPU shape / RNG selection

> The slime-search core preserves the full Java `nextInt(10)` rejection semantics. It does not trade correctness for speed through probabilistic approximation or sampling.

Windows x64 download: [Slime Finder V1.1](https://github.com/OvOliziOvO/slime/releases/tag/V1.1).

The universal search core is built with `build_gpu_universal_x64.bat` / CUDA 12.9 and includes machine code for GTX 10, RTX 20, RTX 30, RTX 40, and RTX 50 (`sm_61 / 75 / 86 / 89 / 120`), plus compatible PTX. The GPU biome component also retains compatible PTX. A working NVIDIA CUDA driver is required. If no usable CUDA GPU is available, including systems with only AMD / Intel graphics, Auto mode defaults to the native CPU search.

CPU biome checks require installing `cubiomes_latest_26.2.zip` separately from the release page and placing `cubiomes.dll` next to the program. CPU slime search itself does not depend on this component.

## Performance

Test device: **RTX 3060 Laptop GPU, 6 GB, Windows x64**. The numbers below are actual measurements from the V1.1 universal release DLL.

Common conditions: seed `123456789`, radius **1,000,000 chunks**, a complete scan of **4,000,004,000,001 (4.000 T) candidate centers**, maximum size `221`, candidate buffer `20,000`, and automatic shape / RNG selection. Timing uses the complete native search API after sustained warm-up; GUI, biome filtering, later precise ranking, Y scanning, and image generation are not included.

Here, “size” means the **minimum number of slime chunks (`min_size`) inside the 221-chunk AFK circle**. It is not the search radius or the area of the overall search region.

### Algorithm differences from 40 to 60

| Minimum size | Local large-range automatic path | How candidates are eliminated quickly |
|---|---|---|
| **40 (default)** | **Scalar Guard4, 128×8** | A rolling 17×17 square is used as a strict upper bound; 4 RNG outputs share the rejection check; dense hit counting and candidate completion are retained. |
| **41–54** | **General fused rolling path, automatically selected as 512×4 / native RNG on this machine** | Uses a bitmap and a rolling 17×17 upper bound, subtracting the 68 cells outside the circle when needed; the size-40 special path and the size-55–60 special paths are not enabled. |
| **55–59** | **Strip272, 256×8 / native RNG** | Shares 20×20 / 20×17 upper bounds, then rejects whole groups using the **272-cell union** of four horizontally adjacent exact circles; surviving candidates are still evaluated individually with the exact 221-cell circle. |
| **60** | **Early272, 256×8 / native RNG** | Uses the same strict 272-cell upper bound with staged corner subtraction; if the group is already below 60 partway through the check, the whole group exits early. |

The specialized paths are available on GTX 10 / RTX 20 / RTX 30 / RTX 40 / RTX 50 and are no longer restricted to CC 8.6. The program checks whether the current GPU can launch the relevant kernels and selects the thread shape and RNG according to measurements on that machine; the search log shows the algorithm actually used. If GPU resources, search conditions, or measured parameters are not suitable for a specialized path, the corresponding exact general path is selected instead. **The speeds in the table are measurements from an RTX 3060 Laptop only and do not represent the performance of other GPUs.**

Search area also participates in dispatch. On this machine, sizes 55–60 use the accepted MidScale path when `1,000,000 ≤ area < 100,000,000,000` candidate centers; smaller areas retain the short-search path. The specialized size-40 path requires an area of at least `100,000,000,000`. **The same size can use a different algorithm and achieve different throughput at different radii.**

### Speed examples under the same conditions

| Minimum size | Actual path on this machine | Full API time | Full API throughput | Full-scan hit count |
|---|---|---:|---:|---:|
| 40 | Scalar Guard4 · 128×8 | **35.562 s** | **112.480 B/s** | 703,428,148 |
| 45 | Fused rolling · 512×4 | **29.783 s** | **134.307 B/s** | 14,384,329 |
| 50 | Fused rolling · 512×4 | **28.362 s** | **141.036 B/s** | 164,644 |
| 54 | Fused rolling · 512×4 | **28.138 s** | **142.159 B/s** | 3,065 |
| 55 | Strip272 · 256×8 | **16.508 s** | **242.309 B/s** | 1,067 |
| 56 | Strip272 · 256×8 | **16.204 s** | **246.855 B/s** | 362 |
| 57 | Strip272 · 256×8 | **15.916 s** | **251.318 B/s** | 116 |
| 58 | Strip272 · 256×8 | **15.795 s** | **253.250 B/s** | 38 |
| 59 | Strip272 · 256×8 | **15.651 s** | **255.573 B/s** | 5 |
| 60 | Early272 · 256×8 | **15.437 s** | **259.118 B/s** | 1 |

`B/s` means **billions of candidate centers checked per second**. The throughput denominator is the number of unique search centers; candidate-completion rescans at low thresholds are included in the elapsed time. The total hit count and the “return at most 20,000 candidates” buffer are separate quantities; the return buffer does not truncate the main scan region.

Sizes 55 / 60 use four fixed AB/BA paired measurements and were checked against the complete results of the previous actually released DLL. The other sizes in the table are the mean of two complete scans after warm-up. Sizes 41–54 are represented by 45, 50, and 54; values inside that interval are not guaranteed to have identical speed. **Sizes 55–60 can be faster than the default size 40, but this does not mean every size or every GPU can reach 250 B/s.** Actual speed depends on the GPU, power limit, temperature, seed, hit count, and search conditions.

## Main features

### Large-area search

Supports center / radius searches and full-map scans across the Java world-border range.

The GPU main scan processes the complete search region and does not reduce the search space through random sampling.

### Exact AFK range

The general path uses a 17×17 square as a strict upper bound. The specialized 55–60 paths first share rectangular and circle-union upper bounds. All final results use the same exact circle:

```text
17 × 17 = 289
outside-corner cells = 68
exact circle = 221
```

The square is therefore used only for fast rejection and never replaces the final exact-circle result.

### Precise scoring and Y scan

Compares candidate farm locations using the actual spawnable-cell count, shows the Top-N ranking, and allows switching between results to help select a more suitable AFK point.

A further search for a better AFK Y level is supported. Progress and estimated remaining time are shown during computation so the user can follow task completion.

### Biome filtering

The slime-chunk RNG search itself does not depend on cubiomes.

The biome backend and Slime search mode are selected separately:

- **CPU mode default**: only the external `cubiomes.dll` is called; GPU noise is not invoked automatically.
- **CPU mode optional**: the advanced setting “Use GPU biome noise in CPU search mode” is off by default. When enabled and a usable CUDA GPU is detected, CPU search can be paired with GPU biome filtering. If no CUDA GPU is available, CPU noise is still used.
- **GPU mode default**: the built-in CUDA noise backend is used.
- **If a GPU-noise call fails**: when a CPU noise component is available, the program asks whether to fall back to CPU noise for this run. After confirmation, filtering restarts from the first candidate for the current seed. If the user declines, checking stops and no result that has not passed complete filtering is emitted. The selected Slime search engine does not change.
- **If no CPU noise component is available**: the program asks the user to install the component; it does not assume the check passed.

These rules apply both to post-search biome filtering and manual Deep Dark checks. Backends are never switched silently.

The GPU backend performs exact Deep Dark / Mushroom Fields filtering and adjusts candidate batch size according to occupancy on the current GPU.

Current biome-version range: **Minecraft Java 1.19 – 26.2**.

### Litematica projection

Supports generating floor / structure helper projections from the final AFK point and filtering results for in-game positioning and construction.

## Correctness

Performance optimizations do not change results through approximate RNG, probabilistic models, or sampling.

Current regression coverage includes:

- 4 CUDA shapes
- 3 exact RNG paths
- Positive / negative Java seeds
- Signed 64-bit boundaries
- Exact-circle statistics
- Precise Y scoring
- Candidate-buffer growth
- Deep Dark / Mushroom Fields
- CPU / GPU result sets
- Projection coordinates and 3D bounds

The current full regression includes:

```text
ACCURACY_AUDIT_OK
CPU_GPU_MATRIX_OK
GPU_NOISE_MATRIX_EXACT 57344
GPU_NOISE_VERSION_FILTER_OK
FRONTEND_SMOKE_OK
```

## Algorithm source

The public repository keeps only the algorithm core, build scripts, and necessary licenses / data tables. It does not include the GUI frontend source, test logs, benchmark records, or local experiment files.

Main source files:

- `SlimeCoreGPU.cu` — CUDA slime-search core
- `build_gpu_universal_x64.bat` — CUDA 12.9 / Windows x64 universal search-core build script
- `SlimeCore.cpp` — AVX2 / OpenMP slime-search core
- `gpu_noise/MinecraftGPUNoise.cu` — CUDA Deep Dark / Mushroom Fields noise-filtering core
- `gpu_noise/mcgpu.h` — GPU noise interface / public definitions
- `gpu_noise/spline_generated.cuh` — GPU world-generation spline data
- `gpu_noise/tables/` — biome decision-tree data

## Third-party components and licenses

CPU biome mode uses the external `cubiomes.dll`. This component belongs to a third-party project, is not bundled into this repository's source, and is not claimed as original code of this project.

The GPU biome backend is a CUDA implementation in this project, but it contains / adapts some biome decision-tree data and related implementation references from cubiomes. Parts originating from cubiomes or adapted from its content continue to follow the cubiomes MIT license and original copyright notices; this project does not claim copyright over those third-party portions.

The corresponding license is retained at:

```text
gpu_noise/LICENSE.cubiomes
```

Except for the third-party content described above, the project's own CUDA integration, scheduling, and optimization code is released as shown in this repository.

---

# Why is it so fast?

## 1. Warp ballot builds a compressed slime bitmap

The 32 threads of a CUDA warp each evaluate one chunk, then `ballot` packs those 32 results directly into one 32-bit bitmap.

Later window statistics operate on the bitmap instead of storing each chunk result as an ordinary integer / bool and reading them back one by one.

## 2. Warp-contiguous shared layout

Multiple ballots generated by the same warp are stored contiguously in shared memory.

When a horizontal 17-bit window needs an adjacent word, lanes in the same warp preferentially reuse ballot values already held in registers; shared memory is read only when crossing a warp boundary.

This reduces shared-memory round trips on the hot path without increasing the number of RNG evaluations or CTA barriers.

## 3. Reuse rolling windows and exact unions by size

The ranges of adjacent candidate centers overlap heavily.

When the window moves horizontally by one cell, most columns are reused completely. Only the part leaving the window and the newly entering part are updated instead of recounting all 289 cells.

The square score is still a strict upper bound for the exact circle, so a candidate below the threshold can be rejected immediately.

Dense threshold 40 keeps the single-circle square path. Sizes 55–59 and 60 instead share most of the data between adjacent circles and apply 20×20, 20×17, and exact 272-cell-union upper bounds in sequence. Size 60 checks the remaining upper bound earlier and exits when it can already prove the whole group cannot reach 60. Every stage is a strict upper bound, and retained candidates still satisfy the same exact 221-cell-circle definition.

## 4. Exact circle subtracts only 68 corner cells

The exact circle contains 221 cells:

```text
circle = square_score - outside_corners
221 = 289 - 68
```

Candidates that pass the square upper bound do not recount the 221 cells inside the circle. Instead, the cells outside the circle are subtracted from the existing square score.

Corner subtraction is staged. As soon as the intermediate result can strictly prove that the candidate cannot reach the requirement, evaluation stops early.

## 5. Multiple exact Java RNG paths

The CUDA core provides three paths at the same time:

- Native 48-bit
- Limb32
- Truncated first-output

All three preserve the same Java RNG semantics and retain the extremely rare rejection fallback.

Integer-operation costs differ across NVIDIA architectures, so the program automatically selects a more suitable implementation for the current GPU.

## 6. Automatic GPU thread-shape selection

The current search core can automatically select among these CUDA shapes:

```text
128×8
256×4
256×8
512×4
```

It does not assume that one thread shape is fastest on every GPU.

## 7. Reduce PCIe and Python transfers

Low thresholds can produce a very large number of hits, while the final workflow usually needs only Top-N.

The GPU performs exact statistics and materializes only candidates that genuinely have a chance to enter the final results, avoiding the transfer of large numbers of coordinates over PCIe to Python just to sort them there.

The search is also processed in segments to reduce candidate-buffer pressure and host-side data movement.

## 8. Final biome filtering can use the GPU

Deep Dark / Mushroom Fields world-generation noise and the slime RNG are two completely different computations, so they use separate CUDA backends.

The GPU biome kernel first identifies the slime chunks that actually need to be checked in the exact range, then compacts valid chunks into a contiguous work list so CUDA blocks can focus on the noise queries that really matter.

This reduces the number of inactive lanes within warps.

Compact scheduling concentrates valid queries and reduces wasted work. GPU biome results have been cross-checked against the cubiomes reference implementation. CPU mode follows its own default CPU backend; the noise backend changes only when the relevant setting is explicitly enabled or when the user confirms the fallback prompt after a GPU failure.

## 9. Parallel precise AFK scoring and ranking pruning

At a fixed Y level, precise scoring distributes each candidate's 81 AFK points across multiple CUDA threads, shares the required chunk data, and selects results using the existing score and tie-breaking rules. The frontend uses an equivalent integer pre-sort for candidates awaiting scoring and retains safe upper-bound pruning to reduce unnecessary full spawnable-cell calculations.

The main scan, candidate scoring, and biome noise are optimized and timed separately. Speed is not gained by changing the ranking rules.

---

The performance primarily comes from **result reuse, bitmap compression, rolling statistics, strict-upper-bound early rejection, continuous GPU work scheduling, and reduced data movement**, rather than sacrificing search accuracy.
