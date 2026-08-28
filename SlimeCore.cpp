#include <cstdint>
#include <vector>
#include <algorithm>
#include <omp.h>
#include <queue>
#include <atomic>
#include <cmath>
#include <cstring>
#if defined(_MSC_VER)
#include <intrin.h>
#include <immintrin.h>
#endif

static std::atomic<int> g_cancel_requested{0};
static std::atomic<int> g_progress{0};
static std::atomic<int> g_y_scan_enabled{0};
static int32_t g_platform_y = -64;
static int32_t g_y_min = -64;
static int32_t g_y_max = 64;
static int32_t g_y_step = 4;
static std::vector<int32_t> g_y_values;
static std::vector<int16_t> g_outer_radius_table;
static std::vector<int16_t> g_inner_radius_table;
static int32_t g_y_table_count = 0;

constexpr int32_t DX_TABLE_MIN = -128;
constexpr int32_t DX_TABLE_MAX = 128;
constexpr int32_t DX_TABLE_COUNT = DX_TABLE_MAX - DX_TABLE_MIN + 1;

inline int32_t pack_obs_y(int32_t obs, int32_t y) {
    return obs | ((y + 1024) << 20);
}

inline int32_t isqrt_floor(int32_t v) {
    if (v < 0) return -1;
    int32_t r = (int32_t)std::sqrt((double)v);
    while ((r + 1) * (r + 1) <= v) ++r;
    while (r * r > v) --r;
    return r;
}

inline int32_t interval_len(int32_t a, int32_t b) {
    return b >= a ? (b - a + 1) : 0;
}

inline int32_t ctz32(uint32_t v) {
#if defined(_MSC_VER)
    unsigned long idx = 0;
    _BitScanForward(&idx, v);
    return (int32_t)idx;
#else
    return __builtin_ctz(v);
#endif
}

inline bool slime_from_first_lcg(uint64_t rnd) {
    uint32_t bits = (uint32_t)(rnd >> 17);
    if (bits < 2147483640U) {
        return ((bits & 1) == 0) && (bits * 3435973837U <= 858993459U);
    }
    int32_t b = (int32_t)bits, v = b % 10;
    while (b - v + 9 < 0) {
        rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
        b = (int32_t)(rnd >> 17);
        v = b % 10;
    }
    return v == 0;
}

#if defined(__AVX2__) || (defined(_MSC_VER) && defined(_M_AVX2))
static constexpr uint64_t PREFIX4_LUT[16] = {
    0x0000000000000000ULL, 0x0001000100010001ULL,
    0x0001000100010000ULL, 0x0002000200020001ULL,
    0x0001000100000000ULL, 0x0002000200010001ULL,
    0x0002000200010000ULL, 0x0003000300020001ULL,
    0x0001000000000000ULL, 0x0002000100010001ULL,
    0x0002000100010000ULL, 0x0003000200020001ULL,
    0x0002000100000000ULL, 0x0003000200010001ULL,
    0x0003000200010000ULL, 0x0004000300020001ULL,
};

inline void append_prefix4(short* dst, short& row_sum, int32_t mask) {
    const uint64_t inc = PREFIX4_LUT[mask & 15];
    const uint64_t base = (uint64_t)(uint16_t)row_sum * 0x0001000100010001ULL;
    const uint64_t packed = base + inc;
    std::memcpy(dst, &packed, sizeof(packed));
    row_sum += (short)(inc >> 48);
}

inline __m256i lcg_first4(__m256i state) {
    // Low 64 bits of a 64x64 multiply by the 35-bit Java LCG constant,
    // assembled from AVX2's four parallel 32x32->64 multiplies.
    const __m256i mul_lo = _mm256_set1_epi64x(0xDEECE66DULL);
    const __m256i mul_hi = _mm256_set1_epi64x(5ULL);
    __m256i low_product = _mm256_mul_epu32(state, mul_lo);
    __m256i high32 = _mm256_srli_epi64(state, 32);
    __m256i cross = _mm256_add_epi64(
        _mm256_mul_epu32(high32, mul_lo),
        _mm256_mul_epu32(state, mul_hi));
    __m256i product = _mm256_add_epi64(low_product, _mm256_slli_epi64(cross, 32));
    return _mm256_and_si256(
        _mm256_add_epi64(product, _mm256_set1_epi64x(0xBULL)),
        _mm256_set1_epi64x(0xFFFFFFFFFFFFULL));
}

inline int32_t slime_mask4_from_lcg(__m256i rnd) {
    const __m256i bits = _mm256_srli_epi64(rnd, 17);
    const __m256i products = _mm256_and_si256(
        _mm256_mul_epu32(bits, _mm256_set1_epi64x(3435973837ULL)),
        _mm256_set1_epi64x(0xFFFFFFFFULL));
    const __m256i in_range = _mm256_cmpgt_epi64(
        _mm256_set1_epi64x(2147483640ULL), bits);
    const __m256i product_ok = _mm256_xor_si256(
        _mm256_cmpgt_epi64(products, _mm256_set1_epi64x(858993459ULL)),
        _mm256_set1_epi64x(-1LL));
    const __m256i even = _mm256_cmpeq_epi64(
        _mm256_and_si256(bits, _mm256_set1_epi64x(1ULL)),
        _mm256_setzero_si256());
    const int32_t valid_mask = _mm256_movemask_pd(_mm256_castsi256_pd(in_range));
    int32_t slime_mask = _mm256_movemask_pd(
        _mm256_castsi256_pd(_mm256_and_si256(
            in_range, _mm256_and_si256(product_ok, even))));
    if (valid_mask != 15) {
        alignas(32) uint64_t rnd4[4];
        _mm256_store_si256((__m256i*)rnd4, rnd);
        for (int32_t lane = 0; lane < 4; ++lane) {
            if ((valid_mask & (1 << lane)) == 0 && slime_from_first_lcg(rnd4[lane])) {
                slime_mask |= 1 << lane;
            }
        }
    }
    return slime_mask;
}
#endif

void rebuild_y_radius_tables() {
    int32_t y_start = g_y_scan_enabled.load(std::memory_order_relaxed) ? g_y_min : g_platform_y;
    int32_t y_end = g_y_scan_enabled.load(std::memory_order_relaxed) ? g_y_max : g_platform_y;
    int32_t y_step = g_y_scan_enabled.load(std::memory_order_relaxed) ? g_y_step : 1;
    if (y_step <= 0) y_step = 1;
    if (y_end < y_start) std::swap(y_start, y_end);

    int32_t y_count = ((y_end - y_start) / y_step) + 1;
    if (y_count <= 0) y_count = 1;

    g_y_values.resize(y_count);
    g_outer_radius_table.assign((size_t)y_count * DX_TABLE_COUNT, -1);
    g_inner_radius_table.assign((size_t)y_count * DX_TABLE_COUNT, -1);

    for (int32_t yi = 0; yi < y_count; ++yi) {
        int32_t y = y_start + yi * y_step;
        g_y_values[yi] = y;
        int32_t dy = g_platform_y - y;
        int32_t dy_sq = dy * dy;
        for (int32_t dx = DX_TABLE_MIN; dx <= DX_TABLE_MAX; ++dx) {
            size_t idx = (size_t)yi * DX_TABLE_COUNT + (dx - DX_TABLE_MIN);
            int32_t outer_rem = 16384 - dy_sq - dx * dx;
            if (outer_rem >= 0) {
                g_outer_radius_table[idx] = (int16_t)isqrt_floor(outer_rem);
            }
            int32_t inner_rem = 576 - dy_sq - dx * dx;
            if (inner_rem >= 0) {
                g_inner_radius_table[idx] = (int16_t)isqrt_floor(inner_rem);
            }
        }
    }
    g_y_table_count = y_count;
}

struct ExtChunkResult {
    int32_t size;
    int32_t center_x;
    int32_t center_z;
    int32_t obs_count;
    int32_t afk_x;
    int32_t afk_z;
};

struct ChunkResult {
    int32_t size;
    int64_t center_x;
    int64_t center_z;
    bool operator<(const ChunkResult& other) const {
        if (size != other.size) return size > other.size;
        if (center_x != other.center_x) return center_x < other.center_x;
        return center_z < other.center_z;
    }
};

inline bool betterChunk(const ChunkResult& a, const ChunkResult& b) {
    if (a.size != b.size) return a.size > b.size;
    if (a.center_x != b.center_x) return a.center_x < b.center_x;
    return a.center_z < b.center_z;
}

inline bool checkSlime(int64_t seed, int64_t x, int64_t z) {
    uint32_t ux = (uint32_t)(int32_t)x;
    uint32_t uz = (uint32_t)(int32_t)z;
    uint64_t p1 = (uint64_t)(int32_t)(ux * ux * 0x4c1906U);
    uint64_t p2 = (uint64_t)(int32_t)(ux * 0x5ac0dbU);
    uint64_t p3 = (uint64_t)(int32_t)(uz * uz) * 0x4307a7LL;
    uint64_t p4 = (uint64_t)(int32_t)(uz * 0x5f24fU);
    uint64_t s = seed + p1 + p2 + p3 + p4;

    uint64_t rnd = ((s ^ 0x3ad8025fLL) ^ 0x5DEECE66DULL) & 0xFFFFFFFFFFFFULL;
    rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
    uint32_t bits = (uint32_t)(rnd >> 17);

    if (bits < 2147483640U) {
        return ((bits & 1) == 0) && (bits * 3435973837U <= 858993459U);
    } else {
        int32_t b = bits, v = b % 10;
        while (b - v + 9 < 0) {
            rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
            b = (int32_t)(rnd >> 17);
            v = b % 10;
        }
        return (v == 0);
    }
}

void build_chunk_cache(int64_t seed, int64_t ox, int64_t oz, uint32_t chunk_cache[21], int64_t& base_cx, int64_t& base_cz) {
    base_cx = (ox >> 4) - 10;
    base_cz = (oz >> 4) - 10;
    for (int32_t i = 0; i < 21; ++i) chunk_cache[i] = 0;

    for (int32_t i = 0; i < 21; ++i) {
        for (int32_t j = 0; j < 21; ++j) {
            if (checkSlime(seed, base_cx + i, base_cz + j)) {
                chunk_cache[i] |= (1U << j);
            }
        }
    }
}

int32_t count_spawnable_cached(const uint32_t chunk_cache[21], int64_t base_cx, int64_t base_cz, int64_t ox, int64_t oz, int32_t afk_y) {
    int32_t dy = g_platform_y - afk_y;
    int32_t dy_sq = dy * dy;
    if (dy_sq > 16384) return 0;
    int32_t count = 0;

    for (int32_t i = 0; i < 21; ++i) {
        uint32_t row = chunk_cache[i];
        if (!row) continue;
        int64_t chunk_x0 = (base_cx + i) << 4;
        int32_t rel_x0 = (int32_t)std::max<int64_t>(-128, chunk_x0 - ox);
        int32_t rel_x1 = (int32_t)std::min<int64_t>(128, chunk_x0 + 15 - ox);
        if (rel_x0 > rel_x1) continue;

        while (row) {
            int32_t j = ctz32(row);
            row &= row - 1;
            int64_t chunk_z0 = (base_cz + j) << 4;
            int32_t rel_z0 = (int32_t)std::max<int64_t>(-128, chunk_z0 - oz);
            int32_t rel_z1 = (int32_t)std::min<int64_t>(128, chunk_z0 + 15 - oz);
            if (rel_z0 > rel_z1) continue;

            for (int32_t dx = rel_x0; dx <= rel_x1; ++dx) {
                int32_t outer_rem = 16384 - dy_sq - dx * dx;
                if (outer_rem < 0) continue;
                int32_t outer = isqrt_floor(outer_rem);
                int32_t zl = std::max(rel_z0, -outer);
                int32_t zr = std::min(rel_z1, outer);
                int32_t add = interval_len(zl, zr);
                if (add == 0) continue;

                int32_t inner_rem = 576 - dy_sq - dx * dx;
                if (inner_rem >= 0) {
                    int32_t inner = isqrt_floor(inner_rem);
                    add -= interval_len(std::max(zl, -inner), std::min(zr, inner));
                }
                count += add;
            }
        }
    }
    return count;
}

int32_t count_spawnable_cached_table(
    const uint32_t chunk_cache[21], int64_t base_cx, int64_t base_cz,
    int64_t ox, int64_t oz, const int16_t* outer_radius, const int16_t* inner_radius
) {
    int32_t count = 0;

    for (int32_t i = 0; i < 21; ++i) {
        uint32_t row = chunk_cache[i];
        if (!row) continue;
        int64_t chunk_x0 = (base_cx + i) << 4;
        int32_t rel_x0 = (int32_t)std::max<int64_t>(DX_TABLE_MIN, chunk_x0 - ox);
        int32_t rel_x1 = (int32_t)std::min<int64_t>(DX_TABLE_MAX, chunk_x0 + 15 - ox);
        if (rel_x0 > rel_x1) continue;

        while (row) {
            int32_t j = ctz32(row);
            row &= row - 1;
            int64_t chunk_z0 = (base_cz + j) << 4;
            int32_t rel_z0 = (int32_t)std::max<int64_t>(DX_TABLE_MIN, chunk_z0 - oz);
            int32_t rel_z1 = (int32_t)std::min<int64_t>(DX_TABLE_MAX, chunk_z0 + 15 - oz);
            if (rel_z0 > rel_z1) continue;

            for (int32_t dx = rel_x0; dx <= rel_x1; ++dx) {
                int32_t table_idx = dx - DX_TABLE_MIN;
                int32_t outer = outer_radius[table_idx];
                if (outer < 0) continue;
                int32_t zl = std::max(rel_z0, -outer);
                int32_t zr = std::min(rel_z1, outer);
                int32_t add = interval_len(zl, zr);
                if (add == 0) continue;

                int32_t inner = inner_radius[table_idx];
                if (inner >= 0) {
                    add -= interval_len(std::max(zl, -inner), std::min(zr, inner));
                }
                count += add;
            }
        }
    }
    return count;
}

int32_t calc_spawnable_spaces(int64_t seed, int64_t ox, int64_t oz, int32_t afk_y = -64) {
    uint32_t chunk_cache[21];
    int64_t base_cx, base_cz;
    build_chunk_cache(seed, ox, oz, chunk_cache, base_cx, base_cz);
    return count_spawnable_cached(chunk_cache, base_cx, base_cz, ox, oz, afk_y);
}

extern "C" {
    __declspec(dllexport) void request_cancel() {
        g_cancel_requested.store(1, std::memory_order_relaxed);
    }

    __declspec(dllexport) void reset_cancel() {
        g_cancel_requested.store(0, std::memory_order_relaxed);
        g_progress.store(0, std::memory_order_relaxed);
    }

    __declspec(dllexport) int32_t get_progress() {
        return g_progress.load(std::memory_order_relaxed);
    }

    __declspec(dllexport) void set_y_scan_config(int32_t enabled, int32_t platform_y, int32_t y_min, int32_t y_max, int32_t y_step) {
        g_y_scan_enabled.store(enabled ? 1 : 0, std::memory_order_relaxed);
        g_platform_y = platform_y;
        g_y_min = y_min;
        g_y_max = y_max;
        g_y_step = y_step > 0 ? y_step : 4;
        rebuild_y_radius_tables();
    }

    __declspec(dllexport) int64_t search_slime_clusters(
        int64_t seed, int64_t rd_max, int32_t min_size, int32_t max_size, int64_t rd_min,
        ExtChunkResult* results_buffer, int32_t max_results, int32_t threads, int32_t precise_afk
    ) {
        if (!results_buffer || max_results <= 0 || rd_max < 0) return 0;
        if (threads <= 0) threads = 1;
        rebuild_y_radius_tables();
        g_progress.store(1, std::memory_order_relaxed);
        omp_set_num_threads(threads);
        const int64_t SUBGRID = 256;
        const int64_t grid_width = rd_max * 2 + 1;
        const int64_t num_tasks_x = (grid_width + SUBGRID - 1) / SUBGRID;
        const int64_t num_tasks_z = (grid_width + SUBGRID - 1) / SUBGRID;
        const int64_t total_tasks = num_tasks_x * num_tasks_z;

        int32_t z_bounds[17];
        for (int32_t dx = -8; dx <= 8; ++dx) {
            int32_t max_dz = 0;
            while (dx * dx + (max_dz + 1) * (max_dz + 1) <= 68) max_dz++;
            z_bounds[dx + 8] = max_dz;
        }

        std::priority_queue<ChunkResult> global_top;
        int64_t absolute_total_found = 0;
        int64_t rd_min_sq = rd_min * rd_min;
        const bool use_square_prefilter = min_size >= 25;

        #pragma omp parallel
        {
            std::priority_queue<ChunkResult> local_heap;
            int64_t local_total_found = 0;
            std::vector<short> z_prefix((SUBGRID + 16) * (SUBGRID + 16));
            std::vector<uint32_t> square_prefix((SUBGRID + 17) * (SUBGRID + 17));
            std::vector<int64_t> z_components(SUBGRID + 16);

            #pragma omp for schedule(dynamic, 1)
            for (int64_t task_idx = 0; task_idx < total_tasks; ++task_idx) {
                if (g_cancel_requested.load(std::memory_order_relaxed)) continue;
                if ((task_idx & 15) == 0) {
                    int32_t pct = 1 + (int32_t)((task_idx * 79) / std::max<int64_t>(1, total_tasks));
                    int32_t old = g_progress.load(std::memory_order_relaxed);
                    if (pct > old) g_progress.store(pct, std::memory_order_relaxed);
                }
                int64_t cx_start = -rd_max + (task_idx % num_tasks_x) * SUBGRID;
                int64_t cz_start = -rd_max + (task_idx / num_tasks_x) * SUBGRID;
                int64_t cx_end = std::min(cx_start + SUBGRID - 1, rd_max);
                int64_t cz_end = std::min(cz_start + SUBGRID - 1, rd_max);

                int64_t px_start = cx_start - 8;
                int64_t pz_start = cz_start - 8;
                int64_t px_end = cx_end + 8;
                int64_t pz_end = cz_end + 8;
                int64_t W = px_end - px_start + 1;
                int64_t H = pz_end - pz_start + 1;

                for (int64_t j = 0; j < H; ++j) {
                    uint32_t uz = (uint32_t)(int32_t)(pz_start + j);
                    z_components[j] = (uint64_t)(int32_t)(uz * uz) * 0x4307a7ULL + (uint64_t)(int32_t)(uz * 0x5f24fU);
                }

                for (int64_t i = 0; i < W; ++i) {
                    uint32_t ux = (uint32_t)(int32_t)(px_start + i);
                    uint64_t x_part = seed + (uint64_t)(int32_t)(ux * ux * 0x4c1906U) + (uint64_t)(int32_t)(ux * 0x5ac0dbU);
                    short row_sum = 0;
                    int64_t j = 0;
#if defined(__AVX2__) || (defined(_MSC_VER) && defined(_M_AVX2))
                    const __m256i vx = _mm256_set1_epi64x((long long)x_part);
                    const __m256i scramble = _mm256_set1_epi64x(0x3ad8025fULL ^ 0x5DEECE66DULL);
                    for (; j + 8 <= H; j += 8) {
                        __m256i z4a = _mm256_loadu_si256((const __m256i*)(z_components.data() + j));
                        __m256i z4b = _mm256_loadu_si256((const __m256i*)(z_components.data() + j + 4));
                        __m256i rnd_a = lcg_first4(_mm256_xor_si256(_mm256_add_epi64(vx, z4a), scramble));
                        __m256i rnd_b = lcg_first4(_mm256_xor_si256(_mm256_add_epi64(vx, z4b), scramble));
                        int32_t slime_mask_a = slime_mask4_from_lcg(rnd_a);
                        int32_t slime_mask_b = slime_mask4_from_lcg(rnd_b);
                        short* out = z_prefix.data() + i * H + j;
                        append_prefix4(out, row_sum, slime_mask_a);
                        append_prefix4(out + 4, row_sum, slime_mask_b);
                    }
                    for (; j + 4 <= H; j += 4) {
                        __m256i z4 = _mm256_loadu_si256((const __m256i*)(z_components.data() + j));
                        __m256i states = _mm256_xor_si256(_mm256_add_epi64(vx, z4), scramble);
                        __m256i rnd = lcg_first4(states);
                        int32_t slime_mask = slime_mask4_from_lcg(rnd);
                        append_prefix4(z_prefix.data() + i * H + j, row_sum, slime_mask);
                    }
#endif
                    for (; j < H; ++j) {
                        uint64_t s = x_part + z_components[j];
                        // The initial 48-bit mask is redundant: the following
                        // multiply is reduced modulo 2^48.
                        uint64_t rnd = (s ^ 0x3ad8025fLL) ^ 0x5DEECE66DULL;
                        rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
                        row_sum += (short)slime_from_first_lcg(rnd);
                        z_prefix[i * H + j] = row_sum;
                    }
                }

                int64_t prefix_stride = H + 1;
                if (use_square_prefilter) {
                    std::fill_n(square_prefix.data(), prefix_stride, 0U);
                    for (int64_t i = 0; i < W; ++i) {
                        uint32_t* current = square_prefix.data() + (i + 1) * prefix_stride;
                        const uint32_t* previous = square_prefix.data() + i * prefix_stride;
                        current[0] = 0;
                        for (int64_t j = 0; j < H; ++j) {
                            current[j + 1] = previous[j + 1] + (uint32_t)z_prefix[i * H + j];
                        }
                    }
                }

                for (int64_t cx = cx_start; cx <= cx_end; ++cx) {
                    if (g_cancel_requested.load(std::memory_order_relaxed)) break;
                    int64_t xi = cx - px_start;
                    for (int64_t cz = cz_start; cz <= cz_end; ++cz) {
                        if (rd_min > 0 && cx*cx + cz*cz < rd_min_sq) continue;
                        int64_t zi = cz - pz_start;

                        if (use_square_prefilter) {
                            int64_t x0 = xi - 8, x1 = xi + 9;
                            int64_t z0 = zi - 8, z1 = zi + 9;
                            uint32_t square_count =
                                square_prefix[x1 * prefix_stride + z1]
                                - square_prefix[x0 * prefix_stride + z1]
                                - square_prefix[x1 * prefix_stride + z0]
                                + square_prefix[x0 * prefix_stride + z0];
                            if (square_count < (uint32_t)min_size) continue;
                            // The 17x17 square has exactly 68 cells outside the
                            // radius-squared <= 68 scan mask.
                            if (square_count > (uint32_t)(max_size + 68)) continue;
                        }

                        int32_t total = 0;

                        for (int32_t dx = -8; dx <= 8; ++dx) {
                            int64_t rx = xi + dx;
                            int32_t mdz = z_bounds[dx+8];
                            int64_t zl = zi - mdz - 1, zr = zi + mdz;
                            total += (int32_t)z_prefix[rx * H + zr] - (zl >= 0 ? (int32_t)z_prefix[rx * H + zl] : 0);
                        }

                        if (total >= min_size && total <= max_size) {
                            local_total_found++;
                            ChunkResult candidate{total, cx * 16 + 8, cz * 16 + 8};
                            if (local_heap.size() < (size_t)max_results) {
                                local_heap.push(candidate);
                            } else if (betterChunk(candidate, local_heap.top())) {
                                local_heap.pop();
                                local_heap.push(candidate);
                            }
                        }
                    }
                }
            }

            #pragma omp critical
            {
                absolute_total_found += local_total_found;
                while (!local_heap.empty()) {
                    if (global_top.size() < (size_t)max_results) {
                        global_top.push(local_heap.top());
                    } else if (betterChunk(local_heap.top(), global_top.top())) {
                        global_top.pop();
                        global_top.push(local_heap.top());
                    }
                    local_heap.pop();
                }
            }
        }

        std::vector<ChunkResult> temp_top;
        while (!global_top.empty()) {
            temp_top.push_back(global_top.top());
            global_top.pop();
        }
        std::reverse(temp_top.begin(), temp_top.end());

        int32_t actual_extract = (int32_t)temp_top.size();
        int32_t precise_eval_limit = actual_extract;
        if (precise_afk != 0) {
            precise_eval_limit = g_y_scan_enabled.load(std::memory_order_relaxed)
                ? std::min(actual_extract, 100)
                : std::min(actual_extract, 500);
        }
        #pragma omp parallel for schedule(dynamic)
        for(int32_t i = 0; i < actual_extract; ++i) {
            if (g_cancel_requested.load(std::memory_order_relaxed)) continue;
            int64_t bx = temp_top[i].center_x, bz = temp_top[i].center_z;
            int32_t best_obs = 0;
            int64_t best_ax = bx, best_az = bz;
            int32_t best_y = g_platform_y;

            if (precise_afk != 0 && i < precise_eval_limit) {
                bool scan_y = g_y_scan_enabled.load(std::memory_order_relaxed) != 0;
                int32_t y_count = scan_y ? g_y_table_count : 1;
                if (y_count <= 0) y_count = 1;
                for (int32_t dx = -16; dx <= 16; dx += 4) {
                    for (int32_t dz = -16; dz <= 16; dz += 4) {
                        uint32_t chunk_cache[21];
                        int64_t base_cx, base_cz;
                        int64_t ox = bx + dx;
                        int64_t oz = bz + dz;
                        build_chunk_cache(seed, ox, oz, chunk_cache, base_cx, base_cz);

                        if (scan_y) {
                            for (int32_t yi = 0; yi < y_count; ++yi) {
                                const int16_t* outer = g_outer_radius_table.data() + (size_t)yi * DX_TABLE_COUNT;
                                const int16_t* inner = g_inner_radius_table.data() + (size_t)yi * DX_TABLE_COUNT;
                                int32_t obs = count_spawnable_cached_table(chunk_cache, base_cx, base_cz, ox, oz, outer, inner);
                                if (obs > best_obs) {
                                    best_obs = obs;
                                    best_ax = ox;
                                    best_az = oz;
                                    best_y = g_y_values[yi];
                                }
                            }
                        } else {
                            const int16_t* outer = g_outer_radius_table.data();
                            const int16_t* inner = g_inner_radius_table.data();
                            int32_t obs = count_spawnable_cached_table(chunk_cache, base_cx, base_cz, ox, oz, outer, inner);
                            if (obs > best_obs) {
                                best_obs = obs;
                                best_ax = ox;
                                best_az = oz;
                            }
                        }
                    }
                }
            }
            results_buffer[i].size = temp_top[i].size;
            results_buffer[i].center_x = (int32_t)bx;
            results_buffer[i].center_z = (int32_t)bz;
            results_buffer[i].obs_count = (precise_afk != 0 && g_y_scan_enabled.load(std::memory_order_relaxed)) ? pack_obs_y(best_obs, best_y) : best_obs;
            results_buffer[i].afk_x = (int32_t)best_ax;
            results_buffer[i].afk_z = (int32_t)best_az;
        }
        g_progress.store(90, std::memory_order_relaxed);
        return absolute_total_found;
    }



    __declspec(dllexport) void score_candidates_precise(
        int64_t seed, ExtChunkResult* results_buffer, int32_t count, int32_t threads, int32_t scan_xz
    ) {
        if (!results_buffer || count <= 0) return;
        if (threads <= 0) threads = 1;
        omp_set_num_threads(threads);
        rebuild_y_radius_tables();
        bool scan_y = g_y_scan_enabled.load(std::memory_order_relaxed) != 0;
        int32_t y_count = scan_y ? g_y_table_count : 1;
        if (y_count <= 0) y_count = 1;
        g_progress.store(90, std::memory_order_relaxed);

        #pragma omp parallel for schedule(dynamic)
        for (int32_t i = 0; i < count; ++i) {
            if (g_cancel_requested.load(std::memory_order_relaxed)) continue;

            int64_t bx = results_buffer[i].center_x;
            int64_t bz = results_buffer[i].center_z;
            int32_t best_obs = 0;
            int64_t best_ax = bx, best_az = bz;
            int32_t best_y = g_platform_y;

            int32_t min_dx = scan_xz ? -16 : 0;
            int32_t max_dx = scan_xz ? 16 : 0;
            int32_t min_dz = scan_xz ? -16 : 0;
            int32_t max_dz = scan_xz ? 16 : 0;
            int32_t step = scan_xz ? 4 : 1;

            for (int32_t dx = min_dx; dx <= max_dx; dx += step) {
                for (int32_t dz = min_dz; dz <= max_dz; dz += step) {
                    uint32_t chunk_cache[21];
                    int64_t base_cx, base_cz;
                    int64_t ox = bx + dx;
                    int64_t oz = bz + dz;
                    build_chunk_cache(seed, ox, oz, chunk_cache, base_cx, base_cz);

                    if (scan_y) {
                        for (int32_t yi = 0; yi < y_count; ++yi) {
                            const int16_t* outer = g_outer_radius_table.data() + (size_t)yi * DX_TABLE_COUNT;
                            const int16_t* inner = g_inner_radius_table.data() + (size_t)yi * DX_TABLE_COUNT;
                            int32_t obs = count_spawnable_cached_table(chunk_cache, base_cx, base_cz, ox, oz, outer, inner);
                            if (obs > best_obs) {
                                best_obs = obs;
                                best_ax = ox;
                                best_az = oz;
                                best_y = g_y_values[yi];
                            }
                        }
                    } else {
                        const int16_t* outer = g_outer_radius_table.data();
                        const int16_t* inner = g_inner_radius_table.data();
                        int32_t obs = count_spawnable_cached_table(chunk_cache, base_cx, base_cz, ox, oz, outer, inner);
                        if (obs > best_obs) {
                            best_obs = obs;
                            best_ax = ox;
                            best_az = oz;
                        }
                    }
                }
            }

            results_buffer[i].obs_count = scan_y ? pack_obs_y(best_obs, best_y) : best_obs;
            results_buffer[i].afk_x = (int32_t)best_ax;
            results_buffer[i].afk_z = (int32_t)best_az;

            if ((i & 127) == 0) {
                int32_t pct = 90 + (int32_t)(((int64_t)(i + 1) * 9) / count);
                int32_t old = g_progress.load(std::memory_order_relaxed);
                if (pct > old) g_progress.store(pct, std::memory_order_relaxed);
            }
        }
        g_progress.store(99, std::memory_order_relaxed);
    }

    __declspec(dllexport) void refine_candidates_y(int64_t seed, ExtChunkResult* results_buffer, int32_t count, int32_t threads) {
        if (!results_buffer || count <= 0) return;
        if (threads <= 0) threads = 1;
        omp_set_num_threads(threads);
        rebuild_y_radius_tables();
        int32_t y_count = g_y_table_count;
        if (y_count <= 0) return;
        g_progress.store(90, std::memory_order_relaxed);
        #pragma omp parallel for schedule(dynamic)
        for (int32_t i = 0; i < count; ++i) {
            if (g_cancel_requested.load(std::memory_order_relaxed)) continue;
            int64_t bx = results_buffer[i].center_x;
            int64_t bz = results_buffer[i].center_z;
            int32_t best_obs = 0;
            int64_t best_ax = bx, best_az = bz;
            int32_t best_y = g_platform_y;

            for (int32_t dx = -16; dx <= 16; dx += 4) {
                for (int32_t dz = -16; dz <= 16; dz += 4) {
                    uint32_t chunk_cache[21];
                    int64_t base_cx, base_cz;
                    int64_t ox = bx + dx;
                    int64_t oz = bz + dz;
                    build_chunk_cache(seed, ox, oz, chunk_cache, base_cx, base_cz);
                    for (int32_t yi = 0; yi < y_count; ++yi) {
                        const int16_t* outer = g_outer_radius_table.data() + (size_t)yi * DX_TABLE_COUNT;
                        const int16_t* inner = g_inner_radius_table.data() + (size_t)yi * DX_TABLE_COUNT;
                        int32_t obs = count_spawnable_cached_table(chunk_cache, base_cx, base_cz, ox, oz, outer, inner);
                        if (obs > best_obs) {
                            best_obs = obs;
                            best_ax = ox;
                            best_az = oz;
                            best_y = g_y_values[yi];
                        }
                    }
                }
            }
            results_buffer[i].obs_count = pack_obs_y(best_obs, best_y);
            results_buffer[i].afk_x = (int32_t)best_ax;
            results_buffer[i].afk_z = (int32_t)best_az;
            int32_t pct = 90 + (int32_t)(((int64_t)(i + 1) * 9) / count);
            int32_t old = g_progress.load(std::memory_order_relaxed);
            if (pct > old) g_progress.store(pct, std::memory_order_relaxed);
        }
        g_progress.store(99, std::memory_order_relaxed);
    }
}
