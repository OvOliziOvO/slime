#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cstdint>
#include <iostream>
#include <algorithm>
#include <cstring>
#include <vector>
#include <array>
#include <cmath>
#include <cstdlib>
#include <thread>
#include <chrono>
#include <atomic>

static std::atomic<int> g_cancel_requested{0};
static std::atomic<int> g_pause_requested{0};
static std::atomic<int> g_progress{0};
static std::atomic<int64_t> g_processed_centers{0};
static std::atomic<int64_t> g_gpu_scan_work_ns{0};
static int g_y_scan_enabled = 0;
static int32_t g_platform_y = -64;
static int32_t g_y_min = -64;
static int32_t g_y_max = 64;
static int32_t g_y_step = 4;
static int32_t g_y_count = 1;
static int32_t* g_d_y_values = nullptr;
static int16_t* g_d_outer_radius_table = nullptr;
static int16_t* g_d_inner_radius_table = nullptr;
static int g_gpu_y_tables_ready = 0;
// 1=128x8, 2=256x4, 3=256x8, 4=512x4.
static int32_t g_v1_last_shape = 0;
// 0=native 48-bit LCG, 1=32-bit limbs, 2=truncated first-output LCG.
static int32_t g_v1_last_rng = 0;
static int32_t g_v1_rng_override = -1;

constexpr int32_t DX_TABLE_MIN = -128;
constexpr int32_t DX_TABLE_MAX = 128;
constexpr int32_t DX_TABLE_COUNT = DX_TABLE_MAX - DX_TABLE_MIN + 1;
constexpr int32_t REFINE_BLOCK_THREADS = 128;

__host__ __device__ __forceinline__ int32_t pack_obs_y(int32_t obs, int32_t y) {
    return obs | ((y + 1024) << 20);
}

__host__ __device__ __forceinline__ int64_t floor_div16(int64_t v) {
    const int64_t q = v / 16;
    return q - ((v < 0 && v % 16 != 0) ? 1 : 0);
}

__host__ __device__ __forceinline__ bool java_next_int_10_reject(uint32_t bits, uint32_t value) {
    return bits - value + 9U > 0x7FFFFFFFU;
}

static int32_t isqrt_floor_host(int32_t v) {
    if (v < 0) return -1;
    int32_t r = (int32_t)std::sqrt((double)v);
    while ((r + 1) * (r + 1) <= v) ++r;
    while (r * r > v) --r;
    return r;
}

static void release_gpu_y_tables() {
    if (g_d_y_values) cudaFree(g_d_y_values);
    if (g_d_outer_radius_table) cudaFree(g_d_outer_radius_table);
    if (g_d_inner_radius_table) cudaFree(g_d_inner_radius_table);
    g_d_y_values = nullptr;
    g_d_outer_radius_table = nullptr;
    g_d_inner_radius_table = nullptr;
    g_gpu_y_tables_ready = 0;
}

static void rebuild_gpu_y_tables() {
    release_gpu_y_tables();

    int32_t y_start = g_y_scan_enabled ? g_y_min : g_platform_y;
    int32_t y_end = g_y_scan_enabled ? g_y_max : g_platform_y;
    int32_t y_step = g_y_scan_enabled ? g_y_step : 1;
    if (y_step <= 0) y_step = 1;
    if (y_end < y_start) std::swap(y_start, y_end);

    g_y_count = ((y_end - y_start) / y_step) + 1;
    if (g_y_count <= 0) g_y_count = 1;

    std::vector<int32_t> y_values(g_y_count);
    std::vector<int16_t> outer((size_t)g_y_count * DX_TABLE_COUNT, -1);
    std::vector<int16_t> inner((size_t)g_y_count * DX_TABLE_COUNT, -1);

    for (int32_t yi = 0; yi < g_y_count; ++yi) {
        int32_t y = y_start + yi * y_step;
        y_values[yi] = y;
        int32_t dy = g_platform_y - y;
        int32_t dy_sq = dy * dy;
        for (int32_t dx = DX_TABLE_MIN; dx <= DX_TABLE_MAX; ++dx) {
            size_t idx = (size_t)yi * DX_TABLE_COUNT + (dx - DX_TABLE_MIN);
            int32_t outer_rem = 16384 - dy_sq - dx * dx;
            if (outer_rem >= 0) outer[idx] = (int16_t)isqrt_floor_host(outer_rem);
            int32_t inner_rem = 576 - dy_sq - dx * dx;
            if (inner_rem >= 0) inner[idx] = (int16_t)isqrt_floor_host(inner_rem);
        }
    }

    if (cudaMalloc(&g_d_y_values, (size_t)g_y_count * sizeof(int32_t)) != cudaSuccess) {
        release_gpu_y_tables();
        return;
    }
    if (cudaMalloc(&g_d_outer_radius_table, outer.size() * sizeof(int16_t)) != cudaSuccess) {
        release_gpu_y_tables();
        return;
    }
    if (cudaMalloc(&g_d_inner_radius_table, inner.size() * sizeof(int16_t)) != cudaSuccess) {
        release_gpu_y_tables();
        return;
    }
    if (cudaMemcpy(g_d_y_values, y_values.data(), (size_t)g_y_count * sizeof(int32_t), cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(g_d_outer_radius_table, outer.data(), outer.size() * sizeof(int16_t), cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(g_d_inner_radius_table, inner.data(), inner.size() * sizeof(int16_t), cudaMemcpyHostToDevice) != cudaSuccess) {
        release_gpu_y_tables();
        return;
    }
    g_gpu_y_tables_ready = 1;
}

__device__ __forceinline__ int32_t isqrt_floor_device(int32_t v) {
    if (v < 0) return -1;
    int32_t r = (int32_t)sqrtf((float)v);
    while ((r + 1) * (r + 1) <= v) ++r;
    while (r * r > v) --r;
    return r;
}

__device__ __forceinline__ int32_t interval_len_device(int32_t a, int32_t b) {
    return b >= a ? (b - a + 1) : 0;
}

struct ExtChunkResult {
    int32_t size;
    int32_t center_x;
    int32_t center_z;
    int32_t obs_count;
    int32_t afk_x;
    int32_t afk_z;
};

struct CompactChunkResult {
    int32_t size;
    int32_t center_x;
    int32_t center_z;
};

struct ResultGreater {
    __host__ __device__
    bool operator()(const ExtChunkResult& a, const ExtChunkResult& b) const {
        if (a.size != b.size) return a.size > b.size;
        if (a.center_x != b.center_x) return a.center_x < b.center_x;
        return a.center_z < b.center_z;
    }
};

__host__ __device__ __forceinline__ uint64_t calc_x_part(uint32_t ux) {
    uint64_t p1 = (uint64_t)(int64_t)(int32_t)(ux * ux * 0x4c1906U);
    uint64_t p2 = (uint64_t)(int64_t)(int32_t)(ux * 0x5ac0dbU);
    return p1 + p2;
}

__host__ __device__ __forceinline__ uint64_t calc_z_part(uint32_t uz) {
    uint64_t p3 = (uint64_t)(int64_t)(int32_t)(uz * uz) * 0x4307a7ULL;
    uint64_t p4 = (uint64_t)(int64_t)(int32_t)(uz * 0x5f24fU);
    return p3 + p4;
}

__device__ __forceinline__ bool is_slime_fast_math(int64_t seed, uint64_t x_part, uint64_t z_part) {
    uint64_t s = seed + x_part + z_part;
    uint64_t rnd = ((s ^ 0x3ad8025fLL) ^ 0x5DEECE66DULL) & 0xFFFFFFFFFFFFULL;
    rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
    uint32_t bits = (uint32_t)(rnd >> 17);

    if (__builtin_expect(bits < 2147483640U, 1)) {
        return ((bits & 1) == 0) && (bits * 3435973837U <= 858993459U);
    } else {
        uint32_t b = bits, v = b % 10U;
        while (java_next_int_10_reject(b, v)) {
            rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
            b = (uint32_t)(rnd >> 17);
            v = b % 10U;
        }
        return (v == 0);
    }
}

// V1 hot path. The host folds the world seed into every Z term once, so
// each chunk needs only one 64-bit addition here.  The mask before the first
// LCG multiply is intentionally omitted: the low 48 bits of a product depend
// only on the low 48 bits of its inputs.  The post-multiply mask still creates
// the exact java.util.Random state used by the rare rejection path.
__device__ __forceinline__ bool is_slime_fast_math_seeded_z(
    uint64_t x_part, uint64_t seeded_z_part
) {
    uint64_t rnd = (x_part + seeded_z_part) ^
                   (0x3ad8025fULL ^ 0x5DEECE66DULL);
    rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
    const uint32_t bits = (uint32_t)(rnd >> 17);

    if (__builtin_expect(bits < 2147483640U, 1)) {
        // Exact divisibility-by-10 test without a parity branch.  Odd and even
        // lanes now execute the same instruction stream.
        uint32_t q = bits * 0xCCCCCCCDU;
        q = (q >> 1) | (q << 31);
        return q <= 0x19999999U;
    }

    uint32_t b = bits;
    uint32_t v = b % 10U;
    while (java_next_int_10_reject(b, v)) {
        rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
        b = (uint32_t)(rnd >> 17);
        v = b % 10U;
    }
    return v == 0;
}

// Advance java.util.Random's 48-bit state using only 32-bit multiplies.  The
// low limb needs the low/high halves of lo * 0xDEECE66D; the high 16 bits also
// receive lo * 5 and hi * 0xDEECE66D.  Terms starting at bit 48 are discarded,
// exactly matching the Java LCG mask.
__device__ __forceinline__ void lcg48_step_limb32(uint32_t& lo, uint32_t& hi) {
    constexpr uint32_t MUL_LO = 0xDEECE66DU;
    const uint32_t product_lo = lo * MUL_LO;
    uint32_t carry = __umulhi(lo, MUL_LO);
    const uint32_t next_lo = product_lo + 0xBU;
    carry += next_lo < product_lo;
    hi = (carry + lo * 5U + hi * MUL_LO) & 0xFFFFU;
    lo = next_lo;
}

__device__ __forceinline__ bool is_slime_fast_math_seeded_z_limb32(
    uint64_t x_part, uint64_t seeded_z_part
) {
    const uint64_t initial = (x_part + seeded_z_part) ^
                             (0x3ad8025fULL ^ 0x5DEECE66DULL);
    uint32_t lo = (uint32_t)initial;
    uint32_t hi = (uint32_t)(initial >> 32) & 0xFFFFU;
    lcg48_step_limb32(lo, hi);
    uint32_t bits = (hi << 15) | (lo >> 17);

    if (__builtin_expect(bits < 2147483640U, 1)) {
        uint32_t q = bits * 0xCCCCCCCDU;
        q = (q >> 1) | (q << 31);
        return q <= 0x19999999U;
    }

    uint32_t b = bits;
    uint32_t v = b % 10U;
    while (java_next_int_10_reject(b, v)) {
        lcg48_step_limb32(lo, hi);
        bits = (hi << 15) | (lo >> 17);
        b = bits;
        v = b % 10U;
    }
    return v == 0;
}

// nextInt(10) normally consumes only bits 17..47 of the first LCG state. Compute
// exactly those bits with 32-bit products; reconstruct the full state only for
// Java's 8-in-2^31 rejection tail. Let initial = lo17 + (hi31 << 17):
// high31(initial*A+11) = high(lo17*A+11, 17) + hi31*(A mod 2^31).
__device__ __forceinline__ bool is_slime_fast_math_seeded_z_truncated(
    uint64_t x_part, uint64_t seeded_z_part
) {
    constexpr uint32_t MUL_LO = 0xDEECE66DU;
    constexpr uint32_t MUL_MOD31 = 0x5EECE66DU;
    const uint64_t initial = (x_part + seeded_z_part) ^
                             (0x3ad8025fULL ^ 0x5DEECE66DULL);
    const uint32_t lo17 = (uint32_t)initial & 0x1FFFFU;
    const uint32_t hi31 = (uint32_t)(initial >> 17) & 0x7FFFFFFFU;
    const uint32_t product_lo = lo17 * MUL_LO;
    const uint32_t plus_lo = product_lo + 0xBU;
    const uint32_t product_hi = __umulhi(lo17, MUL_LO) +
                                (plus_lo < product_lo);
    uint32_t bits = (plus_lo >> 17) | (product_hi << 15);
    bits += (lo17 * 5U) << 15;
    bits += hi31 * MUL_MOD31;
    bits &= 0x7FFFFFFFU;

    if (__builtin_expect(bits < 2147483640U, 1)) {
        uint32_t q = bits * 0xCCCCCCCDU;
        q = (q >> 1) | (q << 31);
        return q <= 0x19999999U;
    }

    // Cold path: recover the complete Java state before advancing again.
    uint64_t rnd = (initial * 0x5DEECE66DULL + 0xBULL) &
                   0xFFFFFFFFFFFFULL;
    uint32_t b = bits;
    uint32_t v = b % 10U;
    while (java_next_int_10_reject(b, v)) {
        rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
        b = (uint32_t)(rnd >> 17);
        v = b % 10U;
    }
    return v == 0;
}

template <int RNG_MODE>
__device__ __forceinline__ bool is_slime_fast_math_seeded_z_variant(
    uint64_t x_part, uint64_t seeded_z_part
) {
    if constexpr (RNG_MODE == 1)
        return is_slime_fast_math_seeded_z_limb32(x_part, seeded_z_part);
    if constexpr (RNG_MODE == 2)
        return is_slime_fast_math_seeded_z_truncated(x_part, seeded_z_part);
    return is_slime_fast_math_seeded_z(x_part, seeded_z_part);
}


template <int STRIDE, bool NO_UPPER>
__device__ __forceinline__ int32_t circle_from_shared_ring(
    const uint32_t* rows, int32_t current_row,
    int32_t word, int32_t lane, int32_t square_score,
    int32_t min_size, int32_t max_size
) {
    // The rolling 17x17 square score is already exact. The circle differs by
    // only 68 corner cells on 12 rows, so subtract those instead of recounting
    // all 221 included cells. Largest corner slices run first, allowing most
    // false square survivors to stop after only a few popcounts.
    int32_t exact = square_score;
    #define V1_OUT_OF_RANGE(REM) (exact < min_size || (!NO_UPPER && exact - (REM) > max_size))
    #define V1_SUB_CORNERS(I, MDX) do { \
        const uint32_t* src = rows + (((current_row - 16 + (I)) & 31) * STRIDE); \
        const uint32_t bits17 = __funnelshift_r(src[word], src[word + 1], lane) & 0x1FFFFU; \
        constexpr uint32_t inside = ((1U << (2 * (MDX) + 1)) - 1U) << (8 - (MDX)); \
        constexpr uint32_t corners = 0x1FFFFU ^ inside; \
        exact -= __popc(bits17 & corners); \
    } while (0)
    V1_SUB_CORNERS( 0, 2); V1_SUB_CORNERS(16, 2); // 24 cells
    if (V1_OUT_OF_RANGE(44)) return exact;
    V1_SUB_CORNERS( 1, 4); V1_SUB_CORNERS(15, 4); // 16 cells
    if (V1_OUT_OF_RANGE(28)) return exact;
    V1_SUB_CORNERS( 2, 5); V1_SUB_CORNERS(14, 5); // 12 cells
    if (V1_OUT_OF_RANGE(16)) return exact;
    V1_SUB_CORNERS( 3, 6); V1_SUB_CORNERS(13, 6); // 8 cells
    if (V1_OUT_OF_RANGE(8)) return exact;
    V1_SUB_CORNERS( 4, 7); V1_SUB_CORNERS( 5, 7);
    V1_SUB_CORNERS(11, 7); V1_SUB_CORNERS(12, 7); // 8 cells
    #undef V1_SUB_CORNERS
    #undef V1_OUT_OF_RANGE
    return exact;
}

template <int TPB, int CPT, bool DENSE_COUNT, int RNG_MODE,
          bool HAS_OLD, bool EMIT, bool FULL_X, bool NO_UPPER>
__device__ __forceinline__ void fused_sparse_v1_row(
    uint32_t* rows,
    const uint64_t* __restrict__ seeded_z_terms,
    int32_t z_base, int32_t r, int32_t lane, int32_t warp,
    const uint64_t (&xt)[CPT], const bool (&input_active)[CPT],
    const bool (&output_active)[CPT], int32_t (&square_score)[CPT],
    int32_t min_size, int32_t max_size, int32_t emit_min_size, int64_t rd_min_sq,
    int32_t search_center_x, int32_t search_center_z,
    int32_t base_x, int32_t slab_base_z, int32_t x_base,
    ExtChunkResult* d_results, int32_t max_gpu_buffer,
    uint32_t& thread_found_count, unsigned long long* d_emitted_count
) {
    constexpr int WARPS = TPB / 32;
    constexpr int WORDS = WARPS * CPT;
    constexpr int STRIDE = WORDS + 1;
    const int32_t slot = r & 31;
    const uint64_t zt = seeded_z_terms[z_base + r];
    uint32_t ballots[CPT];
    #pragma unroll
    for (int k = 0; k < CPT; ++k) {
        const bool slime = (FULL_X || input_active[k]) &&
                           is_slime_fast_math_seeded_z_variant<RNG_MODE>(xt[k], zt);
        ballots[k] = __ballot_sync(0xFFFFFFFFU, slime);
        if (lane == 0) rows[slot * STRIDE + k * WARPS + warp] = ballots[k];
    }
    __syncthreads();

    const uint32_t* new_row = rows + slot * STRIDE;
    const uint32_t* old_row = rows + ((r + 15) & 31) * STRIDE;
    #pragma unroll
    for (int k = 0; k < CPT; ++k) {
        if (!output_active[k]) continue;
        const int32_t word = k * WARPS + warp;
        const uint32_t newest = __funnelshift_r(
            ballots[k], new_row[word + 1], lane) & 0x1FFFFU;
        int32_t square = square_score[k] + __popc(newest);
        if (HAS_OLD) {
            const uint32_t expired = __funnelshift_r(
                old_row[word], old_row[word + 1], lane) & 0x1FFFFU;
            square -= __popc(expired);
        }
        square_score[k] = square;

        if (EMIT && square >= min_size && (NO_UPPER || square <= max_size + 68)) {
            const int32_t cx = base_x + x_base + (int32_t)threadIdx.x + k * TPB;
            const int32_t cz = slab_base_z + z_base + (r - 16);
            const int64_t dx64 = (int64_t)cx - (int64_t)search_center_x;
            const int64_t dz64 = (int64_t)cz - (int64_t)search_center_z;
            if (rd_min_sq != 0 && dx64 * dx64 + dz64 * dz64 < rd_min_sq)
                continue;
            const int32_t exact = circle_from_shared_ring<STRIDE, NO_UPPER>(
                rows, r, word, lane, square, min_size, max_size);
            if (exact >= min_size && (NO_UPPER || exact <= max_size)) {
                if constexpr (!DENSE_COUNT) {
                    const unsigned long long out = atomicAdd(d_emitted_count, 1ULL);
                    if (out < (unsigned long long)max_gpu_buffer) {
                        d_results[out].size = exact;
                        d_results[out].center_x = cx * 16 + 8;
                        d_results[out].center_z = cz * 16 + 8;
                    }
                } else {
                    ++thread_found_count;
                    if (exact >= emit_min_size) {
                        const unsigned long long out = atomicAdd(d_emitted_count, 1ULL);
                        if (out < (unsigned long long)max_gpu_buffer) {
                            d_results[out].size = exact;
                            d_results[out].center_x = cx * 16 + 8;
                            d_results[out].center_z = cz * 16 + 8;
                        }
                    }
                }
            }
        }
    }
}

template <int TPB, int CPT, int BAND_H, bool DENSE_COUNT, int RNG_MODE, bool NO_UPPER>
__global__ __launch_bounds__(TPB) void search_slime_fused_sparse_v1_kernel(
    const uint64_t* __restrict__ x_terms,
    const uint64_t* __restrict__ seeded_z_terms,
    int32_t search_center_x, int32_t search_center_z,
    int32_t base_x, int32_t slab_base_z,
    int32_t out_width, int32_t out_height,
    int32_t tiles_x, int32_t tiles_z,
    int32_t min_size, int32_t max_size, int32_t emit_min_size, int64_t rd_min_sq,
    ExtChunkResult* d_results, int32_t max_gpu_buffer,
    unsigned long long* d_found_count, unsigned long long* d_emitted_count
) {
    constexpr int TILE_W = TPB * CPT;
    constexpr int OUT_W = TILE_W - 16;
    constexpr int WARPS = TPB / 32;
    constexpr int WORDS = WARPS * CPT;
    constexpr int STRIDE = WORDS + 1;
    __shared__ uint32_t rows[32 * STRIDE];
    __shared__ uint32_t block_found_count;

    const int32_t tx = (int32_t)threadIdx.x;
    const int32_t lane = tx & 31;
    const int32_t warp = tx >> 5;
    uint32_t thread_found_count = 0U;
    if (tx == 0) block_found_count = 0U;
    if (tx < 32) rows[tx * STRIDE + WORDS] = 0U;
    __syncthreads();

    const int64_t total_tiles = (int64_t)tiles_x * (int64_t)tiles_z;
    for (int64_t tile = (int64_t)blockIdx.x; tile < total_tiles;
         tile += (int64_t)gridDim.x) {
        const int32_t tile_x = (int32_t)(tile % tiles_x);
        const int32_t tile_z = (int32_t)(tile / tiles_x);
        const int32_t x_base = tile_x * OUT_W;
        const int32_t z_base = tile_z * BAND_H;
        const int32_t tile_out_w = min(OUT_W, out_width - x_base);
        const int32_t tile_out_h = min(BAND_H, out_height - z_base);
        const int32_t tile_in_w = tile_out_w + 16;
        const int32_t tile_in_h = tile_out_h + 16;

        uint64_t xt[CPT];
        bool input_active[CPT];
        bool output_active[CPT];
        int32_t square_score[CPT];
        #pragma unroll
        for (int k = 0; k < CPT; ++k) {
            const int32_t x_local = tx + k * TPB;
            input_active[k] = x_local < tile_in_w;
            output_active[k] = x_local < tile_out_w;
            xt[k] = x_terms[x_base + (input_active[k] ? x_local : 0)];
            square_score[k] = 0;
        }
        // No barrier is needed here: the previous tile ends with a block barrier,
        // and each row synchronizes immediately after publishing its ballots.
        if (tile_out_w == OUT_W) {
            for (int32_t r = 0; r < 16; ++r)
                fused_sparse_v1_row<TPB,CPT,DENSE_COUNT,RNG_MODE,false,false,true,NO_UPPER>(
                    rows, seeded_z_terms, z_base, r, lane, warp,
                    xt, input_active, output_active, square_score,
                    min_size, max_size, emit_min_size, rd_min_sq, search_center_x, search_center_z,
                    base_x, slab_base_z, x_base,
                    d_results, max_gpu_buffer, thread_found_count, d_emitted_count);
            fused_sparse_v1_row<TPB,CPT,DENSE_COUNT,RNG_MODE,false,true,true,NO_UPPER>(
                rows, seeded_z_terms, z_base, 16, lane, warp,
                xt, input_active, output_active, square_score,
                min_size, max_size, emit_min_size, rd_min_sq, search_center_x, search_center_z,
                base_x, slab_base_z, x_base,
                d_results, max_gpu_buffer, thread_found_count, d_emitted_count);
            for (int32_t r = 17; r < tile_in_h; ++r)
                fused_sparse_v1_row<TPB,CPT,DENSE_COUNT,RNG_MODE,true,true,true,NO_UPPER>(
                    rows, seeded_z_terms, z_base, r, lane, warp,
                    xt, input_active, output_active, square_score,
                    min_size, max_size, emit_min_size, rd_min_sq, search_center_x, search_center_z,
                    base_x, slab_base_z, x_base,
                    d_results, max_gpu_buffer, thread_found_count, d_emitted_count);
        } else {
            for (int32_t r = 0; r < 16; ++r)
                fused_sparse_v1_row<TPB,CPT,DENSE_COUNT,RNG_MODE,false,false,false,NO_UPPER>(
                    rows, seeded_z_terms, z_base, r, lane, warp,
                    xt, input_active, output_active, square_score,
                    min_size, max_size, emit_min_size, rd_min_sq, search_center_x, search_center_z,
                    base_x, slab_base_z, x_base,
                    d_results, max_gpu_buffer, thread_found_count, d_emitted_count);
            fused_sparse_v1_row<TPB,CPT,DENSE_COUNT,RNG_MODE,false,true,false,NO_UPPER>(
                rows, seeded_z_terms, z_base, 16, lane, warp,
                xt, input_active, output_active, square_score,
                min_size, max_size, emit_min_size, rd_min_sq, search_center_x, search_center_z,
                base_x, slab_base_z, x_base,
                d_results, max_gpu_buffer, thread_found_count, d_emitted_count);
            for (int32_t r = 17; r < tile_in_h; ++r)
                fused_sparse_v1_row<TPB,CPT,DENSE_COUNT,RNG_MODE,true,true,false,NO_UPPER>(
                    rows, seeded_z_terms, z_base, r, lane, warp,
                    xt, input_active, output_active, square_score,
                    min_size, max_size, emit_min_size, rd_min_sq, search_center_x, search_center_z,
                    base_x, slab_base_z, x_base,
                    d_results, max_gpu_buffer, thread_found_count, d_emitted_count);
        }
        __syncthreads();
    }
    __syncthreads();
    if constexpr (DENSE_COUNT) {
        #pragma unroll
        for (int offset = 16; offset > 0; offset >>= 1)
            thread_found_count += __shfl_down_sync(0xFFFFFFFFU, thread_found_count, offset);
        if (lane == 0) atomicAdd(&block_found_count, thread_found_count);
        __syncthreads();
        if (tx == 0 && block_found_count != 0U)
            atomicAdd(d_found_count, (unsigned long long)block_found_count);
    }
}


__device__ bool checkSlimeDevice(int64_t seed, int64_t global_x, int64_t global_z) {
    uint64_t p_x = calc_x_part((uint32_t)(int32_t)global_x);
    uint64_t p_z = calc_z_part((uint32_t)(int32_t)global_z);
    return is_slime_fast_math(seed, p_x, p_z);
}

__device__ void build_chunk_cache_device(int64_t seed, int64_t ox, int64_t oz, uint32_t chunk_cache[21], int64_t& base_cx, int64_t& base_cz) {
    base_cx = floor_div16(ox) - 10;
    base_cz = floor_div16(oz) - 10;
    for (int i = 0; i < 21; ++i) {
        uint32_t row_mask = 0;
        for (int j = 0; j < 21; ++j) {
            if (checkSlimeDevice(seed, base_cx + i, base_cz + j)) {
                row_mask |= (1U << j);
            }
        }
        chunk_cache[i] = row_mask;
    }
}

__device__ int32_t count_spawnable_cached_device(
    const uint32_t chunk_cache[21], int64_t base_cx, int64_t base_cz,
    int64_t ox, int64_t oz, int32_t platform_y, int32_t afk_y
) {
    int32_t dy = platform_y - afk_y;
    int32_t dy_sq = dy * dy;
    if (dy_sq > 16384) return 0;
    int32_t count = 0;

    for (int32_t i = 0; i < 21; ++i) {
        uint32_t row = chunk_cache[i];
        if (!row) continue;
        int64_t chunk_x0 = (base_cx + i) * 16;
        int32_t rel_x0_raw = (int32_t)(chunk_x0 - ox);
        int32_t rel_x1_raw = (int32_t)(chunk_x0 + 15 - ox);
        int32_t rel_x0 = rel_x0_raw < -128 ? -128 : rel_x0_raw;
        int32_t rel_x1 = rel_x1_raw > 128 ? 128 : rel_x1_raw;
        if (rel_x0 > rel_x1) continue;

        while (row) {
            int32_t j = __ffs(row) - 1;
            row &= row - 1;
            int64_t chunk_z0 = (base_cz + j) * 16;
            int32_t rel_z0_raw = (int32_t)(chunk_z0 - oz);
            int32_t rel_z1_raw = (int32_t)(chunk_z0 + 15 - oz);
            int32_t rel_z0 = rel_z0_raw < -128 ? -128 : rel_z0_raw;
            int32_t rel_z1 = rel_z1_raw > 128 ? 128 : rel_z1_raw;
            if (rel_z0 > rel_z1) continue;

            for (int32_t dx = rel_x0; dx <= rel_x1; ++dx) {
                int32_t outer_rem = 16384 - dy_sq - dx * dx;
                if (outer_rem < 0) continue;
                int32_t outer = isqrt_floor_device(outer_rem);
                int32_t zl = rel_z0 > -outer ? rel_z0 : -outer;
                int32_t zr = rel_z1 < outer ? rel_z1 : outer;
                int32_t add = interval_len_device(zl, zr);
                if (add == 0) continue;

                int32_t inner_rem = 576 - dy_sq - dx * dx;
                if (inner_rem >= 0) {
                    int32_t inner = isqrt_floor_device(inner_rem);
                    int32_t il = zl > -inner ? zl : -inner;
                    int32_t ir = zr < inner ? zr : inner;
                    add -= interval_len_device(il, ir);
                }
                count += add;
            }
        }
    }
    return count;
}

__device__ int32_t count_spawnable_cached_table_device(
    const uint32_t chunk_cache[21], int64_t base_cx, int64_t base_cz,
    int64_t ox, int64_t oz, const int16_t* outer_radius, const int16_t* inner_radius
) {
    int32_t count = 0;

    for (int32_t i = 0; i < 21; ++i) {
        uint32_t row = chunk_cache[i];
        if (!row) continue;
        int64_t chunk_x0 = (base_cx + i) * 16;
        int32_t rel_x0_raw = (int32_t)(chunk_x0 - ox);
        int32_t rel_x1_raw = (int32_t)(chunk_x0 + 15 - ox);
        int32_t rel_x0 = rel_x0_raw < DX_TABLE_MIN ? DX_TABLE_MIN : rel_x0_raw;
        int32_t rel_x1 = rel_x1_raw > DX_TABLE_MAX ? DX_TABLE_MAX : rel_x1_raw;
        if (rel_x0 > rel_x1) continue;

        while (row) {
            int32_t j = __ffs(row) - 1;
            row &= row - 1;
            int64_t chunk_z0 = (base_cz + j) * 16;
            int32_t rel_z0_raw = (int32_t)(chunk_z0 - oz);
            int32_t rel_z1_raw = (int32_t)(chunk_z0 + 15 - oz);
            int32_t rel_z0 = rel_z0_raw < DX_TABLE_MIN ? DX_TABLE_MIN : rel_z0_raw;
            int32_t rel_z1 = rel_z1_raw > DX_TABLE_MAX ? DX_TABLE_MAX : rel_z1_raw;
            if (rel_z0 > rel_z1) continue;

            for (int32_t dx = rel_x0; dx <= rel_x1; ++dx) {
                int32_t table_idx = dx - DX_TABLE_MIN;
                int32_t outer = outer_radius[table_idx];
                if (outer < 0) continue;
                int32_t zl = rel_z0 > -outer ? rel_z0 : -outer;
                int32_t zr = rel_z1 < outer ? rel_z1 : outer;
                int32_t add = interval_len_device(zl, zr);
                if (add == 0) continue;

                int32_t inner = inner_radius[table_idx];
                if (inner >= 0) {
                    int32_t il = zl > -inner ? zl : -inner;
                    int32_t ir = zr < inner ? zr : inner;
                    add -= interval_len_device(il, ir);
                }
                count += add;
            }
        }
    }
    return count;
}

// Same calculation as count_spawnable_cached_table_device(), but reads a
// 23x23 union cache.  All 81 X/Z refinement positions around a chunk center
// fit inside this union, so the expensive slime-chunk hash is evaluated once
// per candidate instead of once per refinement position.
__device__ int32_t count_spawnable_union_table_device(
    const uint32_t union_cache[23], int64_t union_base_cx, int64_t union_base_cz,
    int64_t base_cx, int64_t base_cz, int64_t ox, int64_t oz,
    const int16_t* outer_radius, const int16_t* inner_radius
) {
    int32_t count = 0;
    int32_t x_offset = (int32_t)(base_cx - union_base_cx);
    int32_t z_shift = (int32_t)(base_cz - union_base_cz);
    if (x_offset < 0 || x_offset > 2 || z_shift < 0 || z_shift > 2) return 0;

    for (int32_t i = 0; i < 21; ++i) {
        uint32_t row = union_cache[x_offset + i] >> z_shift;
        row &= 0x1FFFFFu; // 21 chunks in the local window
        if (!row) continue;
        int64_t chunk_x0 = (base_cx + i) * 16;
        int32_t rel_x0_raw = (int32_t)(chunk_x0 - ox);
        int32_t rel_x1_raw = (int32_t)(chunk_x0 + 15 - ox);
        int32_t rel_x0 = rel_x0_raw < DX_TABLE_MIN ? DX_TABLE_MIN : rel_x0_raw;
        int32_t rel_x1 = rel_x1_raw > DX_TABLE_MAX ? DX_TABLE_MAX : rel_x1_raw;
        if (rel_x0 > rel_x1) continue;

        while (row) {
            int32_t j = __ffs(row) - 1;
            row &= row - 1;
            int64_t chunk_z0 = (base_cz + j) * 16;
            int32_t rel_z0_raw = (int32_t)(chunk_z0 - oz);
            int32_t rel_z1_raw = (int32_t)(chunk_z0 + 15 - oz);
            int32_t rel_z0 = rel_z0_raw < DX_TABLE_MIN ? DX_TABLE_MIN : rel_z0_raw;
            int32_t rel_z1 = rel_z1_raw > DX_TABLE_MAX ? DX_TABLE_MAX : rel_z1_raw;
            if (rel_z0 > rel_z1) continue;

            for (int32_t dx = rel_x0; dx <= rel_x1; ++dx) {
                int32_t table_idx = dx - DX_TABLE_MIN;
                int32_t outer = outer_radius[table_idx];
                if (outer < 0) continue;
                int32_t zl = rel_z0 > -outer ? rel_z0 : -outer;
                int32_t zr = rel_z1 < outer ? rel_z1 : outer;
                int32_t add = interval_len_device(zl, zr);
                if (add == 0) continue;
                int32_t inner = inner_radius[table_idx];
                if (inner >= 0) {
                    int32_t il = zl > -inner ? zl : -inner;
                    int32_t ir = zr < inner ? zr : inner;
                    add -= interval_len_device(il, ir);
                }
                count += add;
            }
        }
    }
    return count;
}

__global__ void refine_afk_kernel(
    int64_t seed, ExtChunkResult* d_top_results, int32_t count,
    int32_t y_scan_enabled, int32_t platform_y, int32_t y_min, int32_t y_max, int32_t y_step
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= count) return;

    int64_t bx = d_top_results[idx].center_x;
    int64_t bz = d_top_results[idx].center_z;
    int32_t best_obs = 0;
    int64_t best_ax = bx, best_az = bz;
    int32_t best_y = platform_y;

    for (int32_t dx = -16; dx <= 16; dx += 4) {
        for (int32_t dz = -16; dz <= 16; dz += 4) {
            int64_t ox = bx + dx;
            int64_t oz = bz + dz;
            int64_t base_cx, base_cz;
            uint32_t chunk_cache[21];
            build_chunk_cache_device(seed, ox, oz, chunk_cache, base_cx, base_cz);

            for (int32_t y = y_scan_enabled ? y_min : platform_y; y <= (y_scan_enabled ? y_max : platform_y); y += (y_scan_enabled ? y_step : 1)) {
                int32_t cur_obs = count_spawnable_cached_device(chunk_cache, base_cx, base_cz, ox, oz, platform_y, y);
                if (cur_obs > best_obs) {
                    best_obs = cur_obs;
                    best_ax = ox;
                    best_az = oz;
                    best_y = y;
                }
            }
        }
    }
    d_top_results[idx].obs_count = y_scan_enabled ? pack_obs_y(best_obs, best_y) : best_obs;
    d_top_results[idx].afk_x = (int32_t)best_ax;
    d_top_results[idx].afk_z = (int32_t)best_az;
}

__global__ void refine_afk_block_kernel(
    int64_t seed, ExtChunkResult* d_top_results, int32_t count,
    int32_t platform_y, int32_t y_count, const int32_t* y_values,
    const int16_t* outer_radius_table, const int16_t* inner_radius_table
) {
    int idx = blockIdx.x;
    int tid = threadIdx.x;
    if (idx >= count) return;

    int64_t bx = d_top_results[idx].center_x;
    int64_t bz = d_top_results[idx].center_z;

    int32_t local_best_obs = -1;
    int32_t local_best_order = 0x7fffffff;
    int32_t local_best_x = (int32_t)bx;
    int32_t local_best_z = (int32_t)bz;
    int32_t local_best_y = platform_y;

    __shared__ uint32_t union_cache[23];
    __shared__ int64_t union_base_cx_s;
    __shared__ int64_t union_base_cz_s;
    __shared__ int32_t s_best_obs[REFINE_BLOCK_THREADS];
    __shared__ int32_t s_best_order[REFINE_BLOCK_THREADS];
    __shared__ int32_t s_best_x[REFINE_BLOCK_THREADS];
    __shared__ int32_t s_best_z[REFINE_BLOCK_THREADS];
    __shared__ int32_t s_best_y[REFINE_BLOCK_THREADS];

    int32_t safe_y_count = y_count > 0 ? y_count : 1;

    // Build the complete chunk window needed by all 81 refinement positions.
    // The old kernel rebuilt a 21x21 hash cache for every position.
    if (tid == 0) {
        union_base_cx_s = floor_div16(bx) - 11;
        union_base_cz_s = floor_div16(bz) - 11;
    }
    __syncthreads();
    if (tid < 23) {
        uint32_t row_mask = 0;
        for (int32_t j = 0; j < 23; ++j) {
            if (checkSlimeDevice(seed, union_base_cx_s + tid, union_base_cz_s + j)) {
                row_mask |= (1U << j);
            }
        }
        union_cache[tid] = row_mask;
    }
    __syncthreads();

    for (int32_t off = 0; off < 81; ++off) {
        int32_t dx = -16 + (off / 9) * 4;
        int32_t dz = -16 + (off % 9) * 4;
        int64_t ox = bx + dx;
        int64_t oz = bz + dz;

        int64_t base_cx = floor_div16(ox) - 10;
        int64_t base_cz = floor_div16(oz) - 10;

        for (int32_t yi = tid; yi < safe_y_count; yi += blockDim.x) {
            const int16_t* outer = outer_radius_table + (size_t)yi * DX_TABLE_COUNT;
            const int16_t* inner = inner_radius_table + (size_t)yi * DX_TABLE_COUNT;
            int32_t obs = count_spawnable_union_table_device(
                union_cache, union_base_cx_s, union_base_cz_s,
                base_cx, base_cz, ox, oz, outer, inner);
            int32_t order = off * safe_y_count + yi;
            if (obs > local_best_obs || (obs == local_best_obs && order < local_best_order)) {
                local_best_obs = obs;
                local_best_order = order;
                local_best_x = (int32_t)ox;
                local_best_z = (int32_t)oz;
                local_best_y = y_values[yi];
            }
        }
        __syncthreads();
    }

    s_best_obs[tid] = local_best_obs;
    s_best_order[tid] = local_best_order;
    s_best_x[tid] = local_best_x;
    s_best_z[tid] = local_best_z;
    s_best_y[tid] = local_best_y;
    __syncthreads();

    for (int32_t stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            int32_t other_obs = s_best_obs[tid + stride];
            int32_t other_order = s_best_order[tid + stride];
            if (other_obs > s_best_obs[tid] || (other_obs == s_best_obs[tid] && other_order < s_best_order[tid])) {
                s_best_obs[tid] = other_obs;
                s_best_order[tid] = other_order;
                s_best_x[tid] = s_best_x[tid + stride];
                s_best_z[tid] = s_best_z[tid + stride];
                s_best_y[tid] = s_best_y[tid + stride];
            }
        }
        __syncthreads();
    }

    if (tid == 0) {
        d_top_results[idx].obs_count = pack_obs_y(s_best_obs[0], s_best_y[0]);
        d_top_results[idx].afk_x = s_best_x[0];
        d_top_results[idx].afk_z = s_best_z[0];
    }
}

extern "C" {
    __declspec(dllexport) int32_t get_cuda_device_count() {
        int count = 0;
        cudaError_t status = cudaGetDeviceCount(&count);
        if (status != cudaSuccess) {
            // Clear the sticky runtime error so later real scans start cleanly.
            cudaGetLastError();
            return 0;
        }
        return count;
    }

    __declspec(dllexport) int32_t get_cuda_device_name(char* buffer, int32_t buffer_size) {
        if (!buffer || buffer_size <= 1) return 0;
        int device = 0;
        cudaDeviceProp prop{};
        if (cudaGetDevice(&device) != cudaSuccess ||
            cudaGetDeviceProperties(&prop, device) != cudaSuccess) {
            cudaGetLastError();
            buffer[0] = '\0';
            return 0;
        }
        const size_t n = std::min((size_t)buffer_size - 1U, std::strlen(prop.name));
        std::memcpy(buffer, prop.name, n);
        buffer[n] = '\0';
        return (int32_t)n;
    }


    __declspec(dllexport) int32_t get_gpu_v1_shape() {
        return g_v1_last_shape;
    }

    __declspec(dllexport) int32_t get_gpu_v1_rng() {
        return g_v1_last_rng;
    }

    __declspec(dllexport) void set_gpu_v1_rng_override(int32_t value) {
        g_v1_rng_override = (value >= 0 && value <= 2) ? value : -1;
    }

    // Legacy ABI aliases for older frontends.
    __declspec(dllexport) int32_t get_gpu_v34_shape() { return get_gpu_v1_shape(); }
    __declspec(dllexport) int32_t get_gpu_v34_rng() { return get_gpu_v1_rng(); }
    __declspec(dllexport) void set_gpu_v34_rng_override(int32_t value) { set_gpu_v1_rng_override(value); }

    __declspec(dllexport) void request_cancel() {
        g_cancel_requested.store(1, std::memory_order_relaxed);
        g_pause_requested.store(0, std::memory_order_relaxed);
    }

    __declspec(dllexport) void request_pause() {
        g_pause_requested.store(1, std::memory_order_relaxed);
    }

    __declspec(dllexport) void resume_search() {
        g_pause_requested.store(0, std::memory_order_relaxed);
    }

    __declspec(dllexport) void reset_cancel() {
        g_cancel_requested.store(0, std::memory_order_relaxed);
        g_pause_requested.store(0, std::memory_order_relaxed);
        g_progress.store(0, std::memory_order_relaxed);
        g_processed_centers.store(0, std::memory_order_relaxed);
        g_gpu_scan_work_ns.store(0, std::memory_order_relaxed);
    }

    __declspec(dllexport) int32_t get_progress() {
        return g_progress.load(std::memory_order_relaxed);
    }

    __declspec(dllexport) int64_t get_processed_centers() {
        return g_processed_centers.load(std::memory_order_relaxed);
    }

    __declspec(dllexport) int64_t get_gpu_scan_work_ns() {
        return g_gpu_scan_work_ns.load(std::memory_order_relaxed);
    }

    __declspec(dllexport) void cleanup_gpu_resources() {
        release_gpu_y_tables();
        cudaDeviceReset();
    }

    __declspec(dllexport) void set_y_scan_config(int32_t enabled, int32_t platform_y, int32_t y_min, int32_t y_max, int32_t y_step) {
        g_y_scan_enabled = enabled ? 1 : 0;
        g_platform_y = platform_y;
        g_y_min = y_min;
        g_y_max = y_max;
        g_y_step = y_step > 0 ? y_step : 4;
        rebuild_gpu_y_tables();
    }

    __declspec(dllexport) bool is_slime_chunk_c(int64_t seed, int64_t cx, int64_t cz) {
        uint32_t ux = (uint32_t)(int32_t)cx;
        uint32_t uz = (uint32_t)(int32_t)cz;
        uint64_t p1 = (uint64_t)(int64_t)(int32_t)(ux * ux * 0x4c1906U);
        uint64_t p2 = (uint64_t)(int64_t)(int32_t)(ux * 0x5ac0dbU);
        uint64_t p3 = (uint64_t)(int64_t)(int32_t)(uz * uz) * 0x4307a7ULL;
        uint64_t p4 = (uint64_t)(int64_t)(int32_t)(uz * 0x5f24fU);

        uint64_t s = seed + p1 + p2 + p3 + p4;
        uint64_t rnd = ((s ^ 0x3ad8025fLL) ^ 0x5DEECE66DULL) & 0xFFFFFFFFFFFFULL;
        rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
        uint32_t bits = (uint32_t)(rnd >> 17);
        uint32_t b = bits, v = b % 10U;
        while (java_next_int_10_reject(b, v)) {
            rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
            b = (uint32_t)(rnd >> 17);
            v = b % 10U;
        }
        return v == 0;
    }


    static int64_t search_slime_clusters_gpu_v1_impl(
        int64_t seed, int64_t rd_max, int32_t min_size, int32_t max_size, int64_t rd_min,
        int32_t search_center_x, int32_t search_center_z,
        ExtChunkResult* results_buffer, int32_t max_results, int32_t precise_afk
    ) {
        if (!results_buffer || max_results <= 0 || rd_max < 0 ||
            rd_max > (INT32_MAX - 17LL) / 2LL || rd_min < 0 || rd_min > rd_max ||
            min_size < 0 || min_size > 221 || max_size < min_size) return -1;
        if ((int64_t)search_center_x - rd_max - 8LL < INT32_MIN ||
            (int64_t)search_center_x + rd_max + 8LL > INT32_MAX ||
            (int64_t)search_center_z - rd_max - 8LL < INT32_MIN ||
            (int64_t)search_center_z + rd_max + 8LL > INT32_MAX) return -1;
        if (!g_gpu_y_tables_ready) rebuild_gpu_y_tables();
        g_progress.store(1, std::memory_order_relaxed);

        const int32_t width = (int32_t)(rd_max * 2 + 1);
        const int32_t height = width;
        const int32_t base_x = (int32_t)((int64_t)search_center_x - rd_max);
        const int32_t base_z = (int32_t)((int64_t)search_center_z - rd_max);
        const int64_t rd_min_sq = rd_min * rd_min;
        const size_t term_count = (size_t)width + 16U;

        std::vector<uint64_t> h_x_terms(term_count);
        std::vector<uint64_t> h_z_terms(term_count);
        for (size_t i = 0; i < term_count; ++i) {
            const int32_t coordinate_x = (int32_t)((int64_t)base_x - 8LL + (int64_t)i);
            const int32_t coordinate_z = (int32_t)((int64_t)base_z - 8LL + (int64_t)i);
            h_x_terms[i] = calc_x_part((uint32_t)coordinate_x);
            h_z_terms[i] = calc_z_part((uint32_t)coordinate_z) + (uint64_t)seed;
        }

        const int32_t hard_buffer_cap = std::max(1500000, max_results);
        const int32_t min_buffer = std::max(1, max_results);
        int32_t gpu_buffer_cap = hard_buffer_cap;
        size_t free_mem = 0, total_mem = 0;
        if (cudaMemGetInfo(&free_mem, &total_mem) == cudaSuccess && free_mem > 0) {
            size_t term_bytes = term_count * sizeof(uint64_t) * 2U;
            size_t usable = free_mem > term_bytes ? free_mem - term_bytes : 0;
            int64_t by_memory = (int64_t)((usable * 55ULL / 100ULL) / sizeof(ExtChunkResult));
            gpu_buffer_cap = (int32_t)std::min<int64_t>(gpu_buffer_cap, by_memory);
            gpu_buffer_cap = std::max(gpu_buffer_cap, min_buffer);
        }

        uint64_t* d_x_terms = nullptr;
        uint64_t* d_z_terms = nullptr;
        ExtChunkResult* d_results = nullptr;
        unsigned long long* d_found_count = nullptr;
        unsigned long long* d_emitted_count = nullptr;
        auto release_v1 = [&]() {
            if (d_emitted_count) cudaFree(d_emitted_count);
            if (d_found_count) cudaFree(d_found_count);
            if (d_results) cudaFree(d_results);
            if (d_z_terms) cudaFree(d_z_terms);
            if (d_x_terms) cudaFree(d_x_terms);
        };

        if (cudaMalloc(&d_x_terms, term_count * sizeof(uint64_t)) != cudaSuccess ||
            cudaMalloc(&d_z_terms, term_count * sizeof(uint64_t)) != cudaSuccess ||
            cudaMemcpy(d_x_terms, h_x_terms.data(), term_count * sizeof(uint64_t), cudaMemcpyHostToDevice) != cudaSuccess ||
            cudaMemcpy(d_z_terms, h_z_terms.data(), term_count * sizeof(uint64_t), cudaMemcpyHostToDevice) != cudaSuccess) {
            release_v1();
            cudaGetLastError();
            g_progress.store(0, std::memory_order_relaxed);
            return -1;
        }
        // Release the large pageable host buffers before starting a long scan.
        std::vector<uint64_t>().swap(h_x_terms);
        std::vector<uint64_t>().swap(h_z_terms);

        while (gpu_buffer_cap >= min_buffer) {
            if (cudaMalloc(&d_results, (size_t)gpu_buffer_cap * sizeof(ExtChunkResult)) == cudaSuccess) break;
            d_results = nullptr;
            if (gpu_buffer_cap == min_buffer) break;
            gpu_buffer_cap = std::max(min_buffer, gpu_buffer_cap / 2);
        }
        if (!d_results || cudaMalloc(&d_found_count, sizeof(unsigned long long)) != cudaSuccess ||
            cudaMalloc(&d_emitted_count, sizeof(unsigned long long)) != cudaSuccess ||
            cudaMemset(d_found_count, 0, sizeof(unsigned long long)) != cudaSuccess ||
            cudaMemset(d_emitted_count, 0, sizeof(unsigned long long)) != cudaSuccess) {
            release_v1();
            cudaGetLastError();
            g_progress.store(0, std::memory_order_relaxed);
            return -1;
        }

        constexpr int32_t BAND_H = 2048;
        int32_t v1_shape = 2; // portable short-search default: 256x4
        int32_t v1_rng = 0;   // portable exact baseline
        int32_t v1_tpb = 256;
        int32_t v1_cpt = 4;
        int32_t out_tile_width = v1_tpb * v1_cpt - 16;
        // Target roughly 100 billion centers per persistent launch.  Narrow
        // scans get tall batches that amortize synchronization/tail waves;
        // full-width scans keep a 2-3 second progress/cancellation cadence.
        constexpr int64_t TARGET_BATCH_CENTERS = 100000000000LL;
        constexpr int32_t MIN_SLAB_H = 8192;
        constexpr int32_t MAX_SLAB_H = 262144;
        int64_t desired_slab_h = TARGET_BATCH_CENTERS / std::max<int32_t>(1, width);
        int32_t slab_height = (int32_t)std::max<int64_t>(
            MIN_SLAB_H, std::min<int64_t>(MAX_SLAB_H, desired_slab_h));
        slab_height = std::max(BAND_H, (slab_height / BAND_H) * BAND_H);
        auto launch_v1 = [&](int32_t shape, int32_t rng_variant,
                              int32_t launch_z_offset,
                              int32_t launch_width, int32_t launch_height,
                              int32_t launch_tiles_x, int32_t launch_tiles_z,
                              int32_t launch_blocks, int32_t emit_min_size) -> cudaError_t {
            #define LAUNCH_V1_SHAPE_IMPL(T, C, R, N) do { \
                if (emit_min_size > min_size) \
                    search_slime_fused_sparse_v1_kernel<T, C, BAND_H, true, R, N><<<launch_blocks, T>>>( \
                        d_x_terms, d_z_terms + launch_z_offset, \
                        search_center_x, search_center_z, \
                        base_x, base_z + launch_z_offset, launch_width, launch_height, \
                        launch_tiles_x, launch_tiles_z, min_size, max_size, emit_min_size, rd_min_sq, \
                        d_results, gpu_buffer_cap, d_found_count, d_emitted_count); \
                else \
                    search_slime_fused_sparse_v1_kernel<T, C, BAND_H, false, R, N><<<launch_blocks, T>>>( \
                        d_x_terms, d_z_terms + launch_z_offset, \
                        search_center_x, search_center_z, \
                        base_x, base_z + launch_z_offset, launch_width, launch_height, \
                        launch_tiles_x, launch_tiles_z, min_size, max_size, emit_min_size, rd_min_sq, \
                        d_results, gpu_buffer_cap, d_found_count, d_emitted_count); \
            } while (0)
            #define LAUNCH_V1_SHAPE(T, C, R) do { \
                if (max_size >= 221) LAUNCH_V1_SHAPE_IMPL(T, C, R, true); \
                else LAUNCH_V1_SHAPE_IMPL(T, C, R, false); \
            } while (0)
            if (rng_variant == 2) {
                if (shape == 1) LAUNCH_V1_SHAPE(128, 8, 2);
                else if (shape == 3) LAUNCH_V1_SHAPE(256, 8, 2);
                else if (shape == 4) LAUNCH_V1_SHAPE(512, 4, 2);
                else LAUNCH_V1_SHAPE(256, 4, 2);
            } else if (rng_variant == 1) {
                if (shape == 1) LAUNCH_V1_SHAPE(128, 8, 1);
                else if (shape == 3) LAUNCH_V1_SHAPE(256, 8, 1);
                else if (shape == 4) LAUNCH_V1_SHAPE(512, 4, 1);
                else LAUNCH_V1_SHAPE(256, 4, 1);
            } else {
                if (shape == 1) LAUNCH_V1_SHAPE(128, 8, 0);
                else if (shape == 3) LAUNCH_V1_SHAPE(256, 8, 0);
                else if (shape == 4) LAUNCH_V1_SHAPE(512, 4, 0);
                else LAUNCH_V1_SHAPE(256, 4, 0);
            }
            #undef LAUNCH_V1_SHAPE
            #undef LAUNCH_V1_SHAPE_IMPL
            return cudaGetLastError();
        };

        int32_t device = 0;
        cudaDeviceProp prop{};
        bool have_prop = cudaGetDevice(&device) == cudaSuccess &&
                         cudaGetDeviceProperties(&prop, device) == cudaSuccess;
        const char* forced = std::getenv("SLIME_GPU_V1_SHAPE");
        if (!forced) forced = std::getenv("SLIME_GPU_V34_SHAPE");
        if (forced && std::strcmp(forced, "128x8") == 0) v1_shape = 1;
        else if (forced && std::strcmp(forced, "256x4") == 0) v1_shape = 2;
        else if (forced && std::strcmp(forced, "256x8") == 0) v1_shape = 3;
        else if (forced && std::strcmp(forced, "512x4") == 0 &&
                 (!have_prop || prop.maxThreadsPerBlock >= 512)) v1_shape = 4;
        else {
            static uint8_t tuned_v1[32][2] = {};
            int32_t slot = std::max(0, std::min(31, device));
            int32_t bucket = min_size <= 45 ? 0 : 1;
            if (tuned_v1[slot][bucket]) {
                v1_shape = tuned_v1[slot][bucket];
            } else if ((int64_t)width * height >= 100000000000LL) {
                // Use a saturated multi-wave sample. The older ~536M-center
                // sample launched too few blocks and could select 512x4 even
                // when it was much slower on a full-width world scan.
                const int32_t sample_width = std::min(width, 262144);
                const int32_t sample_height = std::min(height, BAND_H * 8);
                cudaEvent_t start = nullptr, stop = nullptr;
                bool events_ok = cudaEventCreate(&start) == cudaSuccess &&
                                 cudaEventCreate(&stop) == cudaSuccess;
                auto shape_geometry = [](int32_t shape, int32_t& tpb, int32_t& cpt) {
                    if (shape == 1) { tpb = 128; cpt = 8; }
                    else if (shape == 3) { tpb = 256; cpt = 8; }
                    else if (shape == 4) { tpb = 512; cpt = 4; }
                    else { tpb = 256; cpt = 4; }
                };
                auto time_shape = [&](int32_t shape, float& ms) -> bool {
                    int32_t stpb = 0, scpt = 0;
                    shape_geometry(shape, stpb, scpt);
                    int32_t sw = stpb * scpt - 16;
                    int32_t sx = (sample_width + sw - 1) / sw;
                    int32_t sz = (sample_height + BAND_H - 1) / BAND_H;
                    int32_t blocks = std::max(1, std::min(8192, sx * sz));
                    if (!events_ok || cudaMemset(d_found_count, 0, sizeof(unsigned long long)) != cudaSuccess ||
                        cudaMemset(d_emitted_count, 0, sizeof(unsigned long long)) != cudaSuccess ||
                        cudaEventRecord(start) != cudaSuccess) return false;
                    constexpr int repeats = 2;
                    for (int i = 0; i < repeats; ++i) {
                        if (launch_v1(shape, 0, 0, sample_width, sample_height,
                                       sx, sz, blocks, std::max(min_size, 45)) != cudaSuccess) return false;
                    }
                    if (cudaEventRecord(stop) != cudaSuccess ||
                        cudaEventSynchronize(stop) != cudaSuccess ||
                        cudaEventElapsedTime(&ms, start, stop) != cudaSuccess) return false;
                    ms /= repeats;
                    return true;
                };
                float best_ms = 1.0e30f;
                int32_t best_shape = 2;
                const int32_t shapes[4] = {1, 2, 3, 4};
                for (int32_t shape : shapes) {
                    if (shape == 4 && have_prop && prop.maxThreadsPerBlock < 512) continue;
                    float ignored = 0.0f;
                    time_shape(shape, ignored); // warm this variant
                }
                for (int32_t shape : shapes) {
                    if (shape == 4 && have_prop && prop.maxThreadsPerBlock < 512) continue;
                    float ms = 0.0f;
                    if (time_shape(shape, ms) && ms < best_ms) {
                        best_ms = ms;
                        best_shape = shape;
                    }
                }
                if (start) cudaEventDestroy(start);
                if (stop) cudaEventDestroy(stop);
                cudaGetLastError();
                v1_shape = best_shape;
                tuned_v1[slot][bucket] = (uint8_t)v1_shape;
            } else if (min_size < 42) {
                // Keep a low-overhead dense default for small searches; large
                // searches above use the real device measurement.
                v1_shape = 1;
            }
        }
        if (v1_shape == 1) { v1_tpb = 128; v1_cpt = 8; }
        else if (v1_shape == 3) { v1_tpb = 256; v1_cpt = 8; }
        else if (v1_shape == 4) { v1_tpb = 512; v1_cpt = 4; }
        else { v1_tpb = 256; v1_cpt = 4; }
        out_tile_width = v1_tpb * v1_cpt - 16;
        g_v1_last_shape = v1_shape;

        // The exact RNG implementations can trade places across GPU
        // generations.  Benchmark them locally on a saturated sample and
        // cache independently for dense/sparse thresholds.  A 3% margin
        // keeps the compiler-native baseline when results are effectively
        // tied.  Matching exact/stored counts are a runtime safety gate.
        const char* forced_rng = std::getenv("SLIME_GPU_V1_RNG");
        if (!forced_rng) forced_rng = std::getenv("SLIME_GPU_V34_RNG");
        if (g_v1_rng_override >= 0) {
            v1_rng = g_v1_rng_override;
        } else if (forced_rng && (std::strcmp(forced_rng, "truncated") == 0 ||
                                  std::strcmp(forced_rng, "trunc") == 0 ||
                                  std::strcmp(forced_rng, "2") == 0)) {
            v1_rng = 2;
        } else if (forced_rng && (std::strcmp(forced_rng, "limb32") == 0 ||
                           std::strcmp(forced_rng, "1") == 0)) {
            v1_rng = 1;
        } else if (forced_rng && (std::strcmp(forced_rng, "native") == 0 ||
                                  std::strcmp(forced_rng, "baseline") == 0 ||
                                  std::strcmp(forced_rng, "0") == 0)) {
            v1_rng = 0;
        } else {
            static uint8_t tuned_rng[32][2] = {};
            const int32_t slot = std::max(0, std::min(31, device));
            const int32_t bucket = min_size <= 45 ? 0 : 1;
            if (tuned_rng[slot][bucket] != 0) {
                v1_rng = (int32_t)tuned_rng[slot][bucket] - 1;
            } else if ((int64_t)width * height >= 100000000000LL) {
                const int32_t sample_width = std::min(width, 262144);
                const int32_t sample_height = std::min(height, BAND_H * 8);
                const int32_t sample_tiles_x =
                    (sample_width + out_tile_width - 1) / out_tile_width;
                const int32_t sample_tiles_z =
                    (sample_height + BAND_H - 1) / BAND_H;
                const int32_t sample_blocks = std::max(
                    1, std::min(8192, sample_tiles_x * sample_tiles_z));
                const int32_t tune_emit_min = min_size < 45
                    ? std::max(min_size, 50) : min_size;
                cudaEvent_t start = nullptr, stop = nullptr;
                const bool events_ok = cudaEventCreate(&start) == cudaSuccess &&
                                       cudaEventCreate(&stop) == cudaSuccess;
                auto time_rng = [&](int32_t rng, float& ms,
                                    unsigned long long& exact_count,
                                    unsigned long long& stored_count) -> bool {
                    exact_count = 0ULL;
                    stored_count = 0ULL;
                    if (!events_ok ||
                        cudaMemset(d_found_count, 0, sizeof(unsigned long long)) != cudaSuccess ||
                        cudaMemset(d_emitted_count, 0, sizeof(unsigned long long)) != cudaSuccess ||
                        cudaEventRecord(start) != cudaSuccess ||
                        launch_v1(v1_shape, rng, 0, sample_width, sample_height,
                                   sample_tiles_x, sample_tiles_z, sample_blocks,
                                   tune_emit_min) != cudaSuccess ||
                        cudaEventRecord(stop) != cudaSuccess ||
                        cudaEventSynchronize(stop) != cudaSuccess ||
                        cudaEventElapsedTime(&ms, start, stop) != cudaSuccess ||
                        cudaMemcpy(&exact_count, d_found_count, sizeof(unsigned long long),
                                   cudaMemcpyDeviceToHost) != cudaSuccess ||
                        cudaMemcpy(&stored_count, d_emitted_count, sizeof(unsigned long long),
                                   cudaMemcpyDeviceToHost) != cudaSuccess)
                        return false;
                    return true;
                };

                float warm_ms = 0.0f;
                unsigned long long warm_exact = 0ULL, warm_stored = 0ULL;
                const bool warm_ok =
                    time_rng(0, warm_ms, warm_exact, warm_stored) &&
                    time_rng(1, warm_ms, warm_exact, warm_stored) &&
                    time_rng(2, warm_ms, warm_exact, warm_stored);
                float native_a = 0.0f, native_b = 0.0f;
                float limb_a = 0.0f, limb_b = 0.0f;
                float trunc_a = 0.0f, trunc_b = 0.0f;
                unsigned long long native_exact_a = 0ULL, native_exact_b = 0ULL;
                unsigned long long native_stored_a = 0ULL, native_stored_b = 0ULL;
                unsigned long long limb_exact_a = 0ULL, limb_exact_b = 0ULL;
                unsigned long long limb_stored_a = 0ULL, limb_stored_b = 0ULL;
                unsigned long long trunc_exact_a = 0ULL, trunc_exact_b = 0ULL;
                unsigned long long trunc_stored_a = 0ULL, trunc_stored_b = 0ULL;
                const bool measured = warm_ok &&
                    time_rng(0, native_a, native_exact_a, native_stored_a) &&
                    time_rng(1, limb_a, limb_exact_a, limb_stored_a) &&
                    time_rng(2, trunc_a, trunc_exact_a, trunc_stored_a) &&
                    time_rng(2, trunc_b, trunc_exact_b, trunc_stored_b) &&
                    time_rng(1, limb_b, limb_exact_b, limb_stored_b) &&
                    time_rng(0, native_b, native_exact_b, native_stored_b);
                const bool exact_match = measured &&
                    native_exact_a == native_exact_b &&
                    native_exact_a == limb_exact_a &&
                    native_exact_a == limb_exact_b &&
                    native_exact_a == trunc_exact_a &&
                    native_exact_a == trunc_exact_b &&
                    native_stored_a == native_stored_b &&
                    native_stored_a == limb_stored_a &&
                    native_stored_a == limb_stored_b &&
                    native_stored_a == trunc_stored_a &&
                    native_stored_a == trunc_stored_b;
                if (exact_match) {
                    const float native_avg = (native_a + native_b) * 0.5f;
                    const float limb_avg = (limb_a + limb_b) * 0.5f;
                    const float trunc_avg = (trunc_a + trunc_b) * 0.5f;
                    float best_alt = limb_avg;
                    int32_t best_mode = 1;
                    if (trunc_avg < best_alt) {
                        best_alt = trunc_avg;
                        best_mode = 2;
                    }
                    v1_rng = best_alt < native_avg * 0.97f ? best_mode : 0;
                } else {
                    v1_rng = 0;
                }
                if (start) cudaEventDestroy(start);
                if (stop) cudaEventDestroy(stop);
                cudaGetLastError();
                tuned_rng[slot][bucket] = (uint8_t)(v1_rng + 1);
            }
        }
        g_v1_last_rng = v1_rng;

        const int32_t tiles_x = (width + out_tile_width - 1) / out_tile_width;
        bool failed = false;
        int64_t absolute_found_count = 0;
        int32_t emit_min_size = min_size;
        const int64_t search_area = (int64_t)width * (int64_t)height;
        // Dense low thresholds can contain hundreds of millions of valid
        // centers. Count every exact hit, but initially materialize only score
        // 45+ candidates; those are sufficient for the usual global Top-K on
        // world-scale searches. If they are not, the host lowers this gate and
        // performs an exact completion pass.
        if (min_size < 45 && max_size >= 45 &&
            search_area >= 100000000000LL) {
            emit_min_size = (max_size >= 46 && max_results <= 1000000 &&
                             search_area >= 500000000000LL) ? 46 : 45;
        }
        const int32_t initial_slab_height = slab_height;
        constexpr int32_t SCORE_BUCKETS = 290;
        std::array<std::vector<ExtChunkResult>, SCORE_BUCKETS> score_buckets;
        std::vector<ExtChunkResult> slab_results;


        for (;;) {
            failed = false;
            absolute_found_count = 0;
            slab_height = initial_slab_height;
            for (auto& bucket : score_buckets) bucket.clear();

            for (int32_t z_offset = 0; z_offset < height;) {
                while (g_pause_requested.load(std::memory_order_relaxed) &&
                       !g_cancel_requested.load(std::memory_order_relaxed))
                    std::this_thread::sleep_for(std::chrono::milliseconds(20));
                if (g_cancel_requested.load(std::memory_order_relaxed)) break;
                int32_t out_height = std::min(slab_height, height - z_offset);
                if (cudaMemset(d_found_count, 0, sizeof(unsigned long long)) != cudaSuccess ||
                    cudaMemset(d_emitted_count, 0, sizeof(unsigned long long)) != cudaSuccess) {
                    failed = true;
                    break;
                }
                int32_t tiles_z = (out_height + BAND_H - 1) / BAND_H;
                int64_t total_tiles = (int64_t)tiles_x * tiles_z;
                int32_t blocks = (int32_t)std::min<int64_t>(8192, total_tiles);
                cudaError_t launch_status = cudaSuccess;
                const auto scan_begin = std::chrono::steady_clock::now();
                launch_status = launch_v1(v1_shape, v1_rng, z_offset, width, out_height,
                                           tiles_x, tiles_z, blocks, emit_min_size);
                cudaError_t sync_status = cudaDeviceSynchronize();
                const auto scan_end = std::chrono::steady_clock::now();
                if (launch_status != cudaSuccess || sync_status != cudaSuccess) {
                    failed = true;
                    break;
                }
                const int64_t scan_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(scan_end - scan_begin).count();
                g_processed_centers.fetch_add((int64_t)out_height * (int64_t)width, std::memory_order_relaxed);
                g_gpu_scan_work_ns.fetch_add(std::max<int64_t>(1, scan_ns), std::memory_order_relaxed);
                unsigned long long slab_found_count = 0ULL;
                unsigned long long slab_stored_count = 0ULL;
                if (cudaMemcpy(&slab_stored_count, d_emitted_count, sizeof(unsigned long long),
                               cudaMemcpyDeviceToHost) != cudaSuccess) {
                    failed = true;
                    break;
                }
                if (emit_min_size == min_size) {
                    slab_found_count = slab_stored_count;
                } else if (cudaMemcpy(&slab_found_count, d_found_count, sizeof(unsigned long long),
                                      cudaMemcpyDeviceToHost) != cudaSuccess) {
                    failed = true;
                    break;
                }

                // A slab must fit completely so no materialized candidate can
                // disappear before ranking. Dense lower scores are counted but
                // intentionally do not consume result-buffer space.
                if (slab_stored_count > (unsigned long long)gpu_buffer_cap) {
                    if (out_height <= BAND_H) {
                        failed = true;
                        break;
                    }
                    slab_height = std::max(BAND_H, ((out_height / 2) / BAND_H) * BAND_H);
                    continue;
                }

                absolute_found_count += (int64_t)slab_found_count;
                if (slab_stored_count > 0) {
                    slab_results.resize((size_t)slab_stored_count);
                    if (cudaMemcpy(slab_results.data(), d_results,
                                   (size_t)slab_stored_count * sizeof(ExtChunkResult),
                                   cudaMemcpyDeviceToHost) != cudaSuccess) {
                        failed = true;
                        break;
                    }
                    for (const ExtChunkResult& candidate : slab_results) {
                        int32_t score = std::max(0, std::min(SCORE_BUCKETS - 1, candidate.size));
                        score_buckets[(size_t)score].push_back(candidate);
                    }

                    // Scores dominate the ordering. Keep every higher-score bucket
                    // and trim only the boundary bucket by coordinates. Discarded
                    // lower scores can never re-enter the global Top-K later.
                    size_t remaining = (size_t)max_results;
                    for (int32_t score = SCORE_BUCKETS - 1; score >= 0; --score) {
                        auto& bucket = score_buckets[(size_t)score];
                        if (remaining == 0) {
                            bucket.clear();
                        } else if (bucket.size() > remaining) {
                            std::nth_element(bucket.begin(), bucket.begin() + remaining,
                                             bucket.end(), ResultGreater());
                            bucket.resize(remaining);
                            remaining = 0;
                        } else {
                            remaining -= bucket.size();
                        }
                    }
                }
                z_offset += out_height;
                g_progress.store(
                    1 + (int32_t)(((int64_t)z_offset * 79) / std::max(1, height)),
                    std::memory_order_relaxed);
            }

            if (failed || g_cancel_requested.load(std::memory_order_relaxed) || emit_min_size <= min_size) break;
            size_t retained = 0;
            for (const auto& bucket : score_buckets) retained += bucket.size();
            const size_t needed = (size_t)std::min<int64_t>(absolute_found_count, max_results);
            if (retained >= needed) break;
            --emit_min_size;
        }

        if (failed) {
            release_v1();
            cudaGetLastError();
            g_progress.store(0, std::memory_order_relaxed);
            return -1;
        }

        std::vector<ExtChunkResult> global_top;
        global_top.reserve((size_t)max_results);
        for (int32_t score = SCORE_BUCKETS - 1; score >= 0; --score) {
            auto& bucket = score_buckets[(size_t)score];
            global_top.insert(global_top.end(), bucket.begin(), bucket.end());
        }
        int32_t total_to_rank = (int32_t)global_top.size();
        if (total_to_rank > 0) {
            int32_t copy_to_python = std::min(total_to_rank, max_results);
            std::vector<ExtChunkResult> ranked = std::move(global_top);
            if (copy_to_python < total_to_rank) {
                std::partial_sort(ranked.begin(), ranked.begin() + copy_to_python, ranked.end(), ResultGreater());
            } else {
                std::sort(ranked.begin(), ranked.end(), ResultGreater());
            }
            for (int32_t i = 0; i < copy_to_python; ++i) {
                ranked[i].obs_count = 0;
                ranked[i].afk_x = ranked[i].center_x;
                ranked[i].afk_z = ranked[i].center_z;
            }
            memcpy(results_buffer, ranked.data(), (size_t)copy_to_python * sizeof(ExtChunkResult));

            int32_t eval_count = 0;
            if (precise_afk != 0 && !g_cancel_requested.load(std::memory_order_relaxed)) {
                eval_count = std::min(copy_to_python, 100);
                ExtChunkResult* d_top = nullptr;
                if (eval_count > 0 && cudaMalloc(&d_top, (size_t)eval_count * sizeof(ExtChunkResult)) == cudaSuccess) {
                    if (cudaMemcpy(d_top, results_buffer, (size_t)eval_count * sizeof(ExtChunkResult),
                                   cudaMemcpyHostToDevice) == cudaSuccess) {
                        if (g_y_scan_enabled && g_gpu_y_tables_ready) {
                            refine_afk_block_kernel<<<eval_count, REFINE_BLOCK_THREADS>>>(
                                seed, d_top, eval_count, g_platform_y, g_y_count, g_d_y_values,
                                g_d_outer_radius_table, g_d_inner_radius_table);
                        } else {
                            int32_t blocks = (eval_count + 127) / 128;
                            refine_afk_kernel<<<blocks, 128>>>(
                                seed, d_top, eval_count, g_y_scan_enabled,
                                g_platform_y, g_y_min, g_y_max, g_y_step);
                        }
                        cudaError_t refine_launch = cudaGetLastError();
                        cudaError_t refine_sync = cudaDeviceSynchronize();
                        if (refine_launch == cudaSuccess && refine_sync == cudaSuccess) {
                            cudaMemcpy(results_buffer, d_top, (size_t)eval_count * sizeof(ExtChunkResult),
                                       cudaMemcpyDeviceToHost);
                        }
                    }
                    cudaFree(d_top);
                }
            }
        }

        release_v1();
        g_progress.store(90, std::memory_order_relaxed);
        return absolute_found_count;
    }


    __declspec(dllexport) int64_t search_slime_clusters_gpu_v1(
        int64_t seed, int64_t rd_max, int32_t min_size, int32_t max_size, int64_t rd_min,
        ExtChunkResult* results_buffer, int32_t max_results, int32_t precise_afk
    ) {
        return search_slime_clusters_gpu_v1_impl(
            seed, rd_max, min_size, max_size, rd_min, 0, 0,
            results_buffer, max_results, precise_afk);
    }

    __declspec(dllexport) int64_t search_slime_clusters_gpu_v1_centered(
        int64_t seed, int64_t rd_max, int32_t min_size, int32_t max_size, int64_t rd_min,
        int32_t search_center_x, int32_t search_center_z,
        ExtChunkResult* results_buffer, int32_t max_results, int32_t precise_afk
    ) {
        return search_slime_clusters_gpu_v1_impl(
            seed, rd_max, min_size, max_size, rd_min, search_center_x, search_center_z,
            results_buffer, max_results, precise_afk);
    }

    // Legacy ABI aliases for older frontends.
    __declspec(dllexport) int64_t search_slime_clusters_gpu_v34(
        int64_t seed, int64_t rd_max, int32_t min_size, int32_t max_size, int64_t rd_min,
        ExtChunkResult* results_buffer, int32_t max_results, int32_t precise_afk
    ) {
        return search_slime_clusters_gpu_v1(
            seed, rd_max, min_size, max_size, rd_min,
            results_buffer, max_results, precise_afk);
    }

    __declspec(dllexport) int64_t search_slime_clusters_gpu_v34_centered(
        int64_t seed, int64_t rd_max, int32_t min_size, int32_t max_size, int64_t rd_min,
        int32_t search_center_x, int32_t search_center_z,
        ExtChunkResult* results_buffer, int32_t max_results, int32_t precise_afk
    ) {
        return search_slime_clusters_gpu_v1_centered(
            seed, rd_max, min_size, max_size, rd_min, search_center_x, search_center_z,
            results_buffer, max_results, precise_afk);
    }


    __declspec(dllexport) void refine_candidates_y(int64_t seed, ExtChunkResult* results_buffer, int32_t count) {
        if (!results_buffer || count <= 0) return;
        if (!g_gpu_y_tables_ready) rebuild_gpu_y_tables();
        g_progress.store(90, std::memory_order_relaxed);
        ExtChunkResult* d_top_results = nullptr;
        if (cudaMalloc(&d_top_results, count * sizeof(ExtChunkResult)) != cudaSuccess) return;
        if (cudaMemcpy(d_top_results, results_buffer, count * sizeof(ExtChunkResult), cudaMemcpyHostToDevice) != cudaSuccess) {
            cudaFree(d_top_results);
            return;
        }
        if (g_gpu_y_tables_ready) {
            refine_afk_block_kernel<<<count, REFINE_BLOCK_THREADS>>>(
                seed, d_top_results, count,
                g_platform_y, g_y_count, g_d_y_values,
                g_d_outer_radius_table, g_d_inner_radius_table
            );
        } else {
            int threads_per_block = 128;
            int blocks = (count + threads_per_block - 1) / threads_per_block;
            refine_afk_kernel<<<blocks, threads_per_block>>>(
                seed, d_top_results, count,
                1, g_platform_y, g_y_min, g_y_max, g_y_step
            );
        }
        cudaError_t launch_status = cudaGetLastError();
        cudaError_t sync_status = cudaDeviceSynchronize();
        if (launch_status == cudaSuccess && sync_status == cudaSuccess) {
            cudaMemcpy(results_buffer, d_top_results, count * sizeof(ExtChunkResult), cudaMemcpyDeviceToHost);
        }
        cudaFree(d_top_results);
        g_progress.store(99, std::memory_order_relaxed);
    }
}
