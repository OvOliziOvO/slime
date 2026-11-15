# SlimeFinder algorithm optimizations

[English README](../README.md) · [简体中文](algorithm-optimizations.zh-CN.md)

Each candidate AFK spot needs an exact count over **221 chunks**. At world scale, many candidates share the same chunks. SlimeFinder reuses their counts, shares parts of Java's random-number calculation across distant coordinates, and batches the counting on the GPU.

## Most Java first draws need no division

Slime chunks still follow Java's coordinate formula and `Random.nextInt(10)`. The X and Z terms are precomputed separately and combined with the world seed. The 32-bit products follow Java's overflow rules, and the LCG retains the low 48 bits, including for negative and distant coordinates.

Almost every chunk needs only the first draw. Outside Java's rejection range, a multiplication and threshold comparison replace division by 10; only an even result can be a hit. The mask before the first LCG multiplication can also be omitted because the product's low 48 bits do not depend on higher input bits. The rare rejected draws still follow Java's full rules.

## Rolling windows reject most candidates early

Neighboring AFK spots have heavily overlapping footprints. As the square window moves, the scanner subtracts the counts that leave and adds the counts that enter. The square includes every chunk in the circle, so a square count below the threshold rules out the candidate before the exact circle count.

The general GPU path first shares an **18×18** bound across a **2×2 group of centers**, then extends the grouping to four centers per row and **4×4** groups. The large, high-threshold path covers 16 centers with one **20×20** bounding box. For groups that pass, it subtracts **40 cells** on four outer rows that lie outside every candidate circle.

A **20×17** strip bound then rejects individual rows within the group. High-threshold kernels tighten the bound again by removing pairs of outer corners, checking between steps whether the remaining count is already too small. At threshold 60, many groups can stop after the first three corner pairs. Bounds only reject impossible candidates; surviving centers still receive the exact 221-chunk count.

## Bitmaps and Tensor Cores count several rows together

Each of a warp's 32 GPU threads evaluates one chunk. A `ballot` packs their results into a 32-bit word. Intersecting that bitmap with a window mask and counting set bits gives the number of hits inside the mask. The general kernel keeps these bitmaps in a shared-memory ring, updating rolling counts as new rows arrive instead of rereading each complete window.

Later kernels generate four rows together, combining synchronization and updates. For the **20×20** bound, each batch retains its incoming **20×4** count and subtracts the batch that leaves five steps later. High-threshold kernels also use binary Tensor Core instructions to perform several `AND + popcount` operations together and feed the results into the rolling totals. Four-row generation, cached history, and matrix counting reduce repeated bitmap reads.

## Six Z bands share RNG work and pair by parity

Java's coordinate formula gives the Z seed term the same low 16 bits every **65,536 chunks**. The early six-band kernel reused the low multiplication across those bands. At a spacing of **131,072 chunks**, paired positions have opposite parity on Java's first draw. Only the even first draw needs the remaining divisibility check for a first-draw hit.

Three band pairs also share one bitmap that identifies the parity side. Each pair stores one more bitmap for hits. This reduces six bitmaps to four in the six-band design and cuts bitmap generation and reads.

## Two X phases use the same relation along both axes

A shift of **131,072 chunks** along X also flips the first-draw parity. Shifting along both X and Z cancels the flips. One low-bit calculation can therefore serve two X phases and multiple Z bands. The dual-X path reached eight Z bands first, moved to twelve with packed rolling totals and fused Tensor counts, and reached fifteen by grouping full and partial bands more efficiently.

The dual-X kernel first swaps the two phases according to the parity result, so one parity bitmap decides which side can match. Two paired Z bands and both X phases can then share a binary Tensor count. For the final unpaired Z band, the kernel reuses the parity selection rather than generating an unnecessary second bitmap.

## Packed bounds leave detailed checks to fewer groups

The rolling totals of two Z bands first share the two halves of a 32-bit word, updating incoming and outgoing counts together. A later version packs four bounds—two X phases by two Z bands—into four bytes. Each byte carries compact history and a threshold bias; its high bit indicates whether that bound might pass.

Most groups leave at this point. Only the remaining groups enter a separate cold path, where Tensor Cores remove invalid cells on four outer rows together before further corner clipping. If a packed count cannot safely represent the full value, the kernel reconstructs the complete count and uses the original clipping path. Keeping the common rolling updates on the hot path reduces branches, register pressure, and detailed checks.

## Four-row interleaving reduces reads and barriers

The fifteen-band kernel interleaves four rows of bitmaps by warp. A **24-row** ring holds the 20 active rows and leaves four slots for incoming writes. Paired bitmaps occupy adjacent locations; the producer writes each two-column pair as soon as it is ready, and the counter reads both bitmaps with a vector load.

Full bands and partial tails are grouped by their actual height, with the last unpaired band handled separately. Near full-world width, the scanner can also split the full section into two fourteen-band groups to avoid leaving an unmatched band in both. Sharing more work across bands and reducing synchronization and memory reads within each batch contributed to the last speedups.

## The final count follows Java's exact rules

Candidates that clear the bound are evaluated with the exact 221-chunk circle mask on the GPU. Java's `nextInt(10)` sometimes rejects the first draw. The hot path handles ordinary first draws; a separate pass uses a precomputed list of rejected states whose later draws produce a hit.

The correction first narrows those states by their high bits, then uses a modulo-256 inverse table and successive corrections to recover possible X coordinates. It verifies the complete coordinate term and rechecks only affected candidates. The results are merged and deduplicated, and partial Z bands and tile edges are clipped to their actual bounds. This removes rare redraw work from the main scan without changing Java's result.

V1.2 uses the dual-X, fifteen-band path on SM 8.6 GPUs for eligible large, precise searches with thresholds 55–60. Other searches use the general engine. [CUDA source and build instructions](../cuda_x2_z15/README.md)

## Development milestones

![SlimeFinder optimization history from approximately 270 B/s](optimization-history.en.svg)

Each point shows a development milestone. B/s means billion candidate centers per second.
