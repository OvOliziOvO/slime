#include "mcgpu.h"
#include <cuda_runtime.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include "spline_generated.cuh"
#include "tables/btree18.h"
#include "tables/btree192.h"
#include "tables/btree19.h"
#include "tables/btree20.h"
#include "tables/btree21wd.h"
#include "tables/btree215.h"
#include "tables/btree262.h"

struct Xoroshiro128PP {
    uint64_t lo;
    uint64_t hi;
};

__host__ __device__ __forceinline__ uint64_t rotl64_exact(uint64_t x, unsigned b)
{
    return (x << b) | (x >> (64U - b));
}

__host__ __device__ __forceinline__ Xoroshiro128PP xoroshiro_from_seed(uint64_t value)
{
    constexpr uint64_t XL = 0x9e3779b97f4a7c15ULL;
    constexpr uint64_t XH = 0x6a09e667f3bcc909ULL;
    constexpr uint64_t A  = 0xbf58476d1ce4e5b9ULL;
    constexpr uint64_t B  = 0x94d049bb133111ebULL;

    uint64_t l = value ^ XH;
    uint64_t h = l + XL;
    l = (l ^ (l >> 30)) * A;
    h = (h ^ (h >> 30)) * A;
    l = (l ^ (l >> 27)) * B;
    h = (h ^ (h >> 27)) * B;
    l ^= l >> 31;
    h ^= h >> 31;
    return {l, h};
}

__host__ __device__ __forceinline__ uint64_t xoroshiro_next_long(Xoroshiro128PP& s)
{
    const uint64_t l = s.lo;
    uint64_t h = s.hi;
    const uint64_t n = rotl64_exact(l + h, 17) + l;
    h ^= l;
    s.lo = rotl64_exact(l, 49) ^ h ^ (h << 21);
    s.hi = rotl64_exact(h, 28);
    return n;
}

__host__ __device__ __forceinline__ uint32_t xoroshiro_next_int(
    Xoroshiro128PP& s, uint32_t n)
{
    uint64_t r = (xoroshiro_next_long(s) & 0xFFFFFFFFULL) * (uint64_t)n;
    if ((uint32_t)r < n) {
        const uint32_t threshold = (~n + 1U) % n;
        while ((uint32_t)r < threshold)
            r = (xoroshiro_next_long(s) & 0xFFFFFFFFULL) * (uint64_t)n;
    }
    return (uint32_t)(r >> 32);
}

__host__ __device__ __forceinline__ double xoroshiro_next_double(Xoroshiro128PP& s)
{
    return (double)(xoroshiro_next_long(s) >> 11) *
        1.1102230246251565E-16;
}

struct PerlinState {
    uint8_t d[257];
    uint8_t h2;
    double a, b, c;
    double d2, t2;
};

__device__ __forceinline__ void xperlin_init_from_xr(
    PerlinState& p, Xoroshiro128PP xr)
{
    p.a = xoroshiro_next_double(xr) * 256.0;
    p.b = xoroshiro_next_double(xr) * 256.0;
    p.c = xoroshiro_next_double(xr) * 256.0;

    #pragma unroll 1
    for (int i = 0; i < 256; ++i)
        p.d[i] = (uint8_t)i;
    #pragma unroll 1
    for (int i = 0; i < 256; ++i) {
        const int j = (int)xoroshiro_next_int(xr, (uint32_t)(256 - i)) + i;
        const uint8_t t = p.d[i];
        p.d[i] = p.d[j];
        p.d[j] = t;
    }
    p.d[256] = p.d[0];

    const double i2 = floor(p.b);
    const double d2 = p.b - i2;
    p.h2 = (uint8_t)(int)i2;
    p.d2 = d2;
    p.t2 = d2*d2*d2 * (d2 * (d2*6.0 - 15.0) + 10.0);
}

__device__ __forceinline__ void xperlin_init(PerlinState& p, uint64_t seed)
{
    xperlin_init_from_xr(p, xoroshiro_from_seed(seed));
}

__device__ __forceinline__ double grad16(
    uint8_t idx, double a, double b, double c)
{
    switch (idx & 0x0F) {
    case 0:  return  a + b;
    case 1:  return -a + b;
    case 2:  return  a - b;
    case 3:  return -a - b;
    case 4:  return  a + c;
    case 5:  return -a + c;
    case 6:  return  a - c;
    case 7:  return -a - c;
    case 8:  return  b + c;
    case 9:  return -b + c;
    case 10: return  b - c;
    case 11: return -b - c;
    case 12: return  a + b;
    case 13: return -b + c;
    case 14: return -a + b;
    default: return -b - c;
    }
}

__device__ __forceinline__ double lerp_exact(double t, double a, double b)
{
    return a + t * (b - a);
}

__device__ __forceinline__ double xperlin_sample(
    const PerlinState& p, double x, double y, double z)
{
    uint8_t h2;
    double t2;
    if (y == 0.0) {
        y = p.d2;
        h2 = p.h2;
        t2 = p.t2;
    } else {
        y += p.b;
        const double iy = floor(y);
        y -= iy;
        h2 = (uint8_t)(int)iy;
        t2 = y*y*y * (y * (y*6.0 - 15.0) + 10.0);
    }

    x += p.a;
    z += p.c;
    const double ix = floor(x);
    const double iz = floor(z);
    x -= ix;
    z -= iz;
    const uint8_t h1 = (uint8_t)(int)ix;
    const uint8_t h3 = (uint8_t)(int)iz;
    const double t1 = x*x*x * (x * (x*6.0 - 15.0) + 10.0);
    const double t3 = z*z*z * (z * (z*6.0 - 15.0) + 10.0);

    const uint8_t* idx = p.d;
    const uint8_t a1 = (uint8_t)(idx[h1]   + h2);
    const uint8_t b1 = (uint8_t)(idx[h1+1] + h2);
    const uint8_t a2 = (uint8_t)(idx[a1]   + h3);
    const uint8_t b2 = (uint8_t)(idx[b1]   + h3);
    const uint8_t a3 = (uint8_t)(idx[a1+1] + h3);
    const uint8_t b3 = (uint8_t)(idx[b1+1] + h3);

    double l1 = grad16(idx[a2],   x,     y,     z);
    double l2 = grad16(idx[b2],   x-1.0, y,     z);
    double l3 = grad16(idx[a3],   x,     y-1.0, z);
    double l4 = grad16(idx[b3],   x-1.0, y-1.0, z);
    double l5 = grad16(idx[a2+1], x,     y,     z-1.0);
    double l6 = grad16(idx[b2+1], x-1.0, y,     z-1.0);
    double l7 = grad16(idx[a3+1], x,     y-1.0, z-1.0);
    double l8 = grad16(idx[b3+1], x-1.0, y-1.0, z-1.0);

    l1 = lerp_exact(t1, l1, l2);
    l3 = lerp_exact(t1, l3, l4);
    l5 = lerp_exact(t1, l5, l6);
    l7 = lerp_exact(t1, l7, l8);
    l1 = lerp_exact(t2, l1, l3);
    l5 = lerp_exact(t2, l5, l7);
    return lerp_exact(t3, l1, l5);
}

struct PerlinOctaveState {
    PerlinState p;
    double amplitude;
    double lacunarity;
};

struct DoublePerlinState18 {
    int32_t countA;
    int32_t countB;
    double amplitude;
    PerlinOctaveState oct[18];
};

__device__ __constant__ uint64_t kMd5Octave[17][2] = {
    {0xc613bf766619f992ULL, 0x954753f86691b86aULL},
    {0x7eee475a921c6cf5ULL, 0xf2bd39426f8da413ULL},
    {0xfc0027cef9683114ULL, 0xb758d3954dcbfdd3ULL},
    {0xd1fc8a05be565ecaULL, 0xdc2a3915cbdda25bULL},
    {0xb198de63a8012672ULL, 0x7b84cad43ef7b5a8ULL},
    {0x0fd787bfbc403ec3ULL, 0x74a4a31ca21b48b8ULL},
    {0x36d326eed40efeb2ULL, 0x5be9ce18223c636aULL},
    {0x082fe255f8be6631ULL, 0x4e96119e22dedc81ULL},
    {0x0ef68ec68504005eULL, 0x48b6bf93a2789640ULL},
    {0xf11268128982754fULL, 0x257a1d670430b0aaULL},
    {0xe51c98ce7d1de664ULL, 0x5f9478a733040c45ULL},
    {0x6d7b49e7e429850aULL, 0x2e3063c622a24777ULL},
    {0xbd90d5377ba1b762ULL, 0xc07317d419a7548dULL},
    {0x53d39c6752dac858ULL, 0xbcd1c5a80ab65b3eULL},
    {0xb4a24d7a84e7677bULL, 0x023ff9668e89b5c4ULL},
    {0xdffa22b534c5f608ULL, 0xb9b67517d3665ca9ULL},
    {0xd50708086cef4d7cULL, 0x6e1651ecc7f43309ULL},
};

__device__ __constant__ double kLacunaInit[17] = {
    1.0, 0.5, 0.25, 1.0/8.0, 1.0/16.0, 1.0/32.0,
    1.0/64.0, 1.0/128.0, 1.0/256.0, 1.0/512.0,
    1.0/1024.0, 1.0/2048.0, 1.0/4096.0, 1.0/8192.0,
    1.0/16384.0, 1.0/32768.0, 1.0/65536.0
};

__device__ __constant__ double kPersistInit[17] = {
    0.0, 1.0, 2.0/3.0, 4.0/7.0, 8.0/15.0, 16.0/31.0,
    32.0/63.0, 64.0/127.0, 128.0/255.0, 256.0/511.0,
    512.0/1023.0, 1024.0/2047.0, 2048.0/4095.0,
    4096.0/8191.0, 8192.0/16383.0, 16384.0/32767.0,
    32768.0/65535.0
};

__device__ __constant__ double kContinentalnessAmp[9] = {
    1.0, 1.0, 2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0
};
__device__ __constant__ double kShiftAmp[4] = {1.0, 1.0, 1.0, 0.0};
__device__ __constant__ double kTemperatureAmp[6] = {1.5, 0.0, 1.0, 0.0, 0.0, 0.0};
__device__ __constant__ double kHumidityAmp[6] = {1.0, 1.0, 0.0, 0.0, 0.0, 0.0};
__device__ __constant__ double kErosionAmp[5] = {1.0, 1.0, 0.0, 1.0, 1.0};
__device__ __constant__ double kWeirdnessAmp[6] = {1.0, 2.0, 1.0, 0.0, 0.0, 0.0};
__device__ __constant__ double kDoubleAmp[17] = {
    0.0, 5.0/6.0, 10.0/9.0, 15.0/12.0, 20.0/15.0, 25.0/18.0,
    30.0/21.0, 35.0/24.0, 40.0/27.0, 45.0/30.0, 50.0/33.0,
    55.0/36.0, 60.0/39.0, 65.0/42.0, 70.0/45.0, 75.0/48.0,
    80.0/51.0
};

__device__ __forceinline__ int xoctave_init_profile(
    PerlinOctaveState* out,
    Xoroshiro128PP& parent,
    const double* amplitudes,
    int omin,
    int len)
{
    double lacuna = kLacunaInit[-omin];
    double persist = kPersistInit[len];
    const uint64_t xlo = xoroshiro_next_long(parent);
    const uint64_t xhi = xoroshiro_next_long(parent);
    int n = 0;
    for (int i = 0; i < len; ++i, lacuna *= 2.0, persist *= 0.5) {
        const double amp = amplitudes[i];
        if (amp == 0.0)
            continue;
        const int md5i = 16 + omin + i;
        Xoroshiro128PP pxr = {
            xlo ^ kMd5Octave[md5i][0],
            xhi ^ kMd5Octave[md5i][1]
        };
        xperlin_init_from_xr(out[n].p, pxr);
        out[n].amplitude = amp * persist;
        out[n].lacunarity = lacuna;
        ++n;
    }
    return n;
}

__device__ __forceinline__ void init_continentalness_state(
    DoublePerlinState18& dp, uint64_t world_seed)
{
    Xoroshiro128PP base = xoroshiro_from_seed(world_seed);
    const uint64_t xlo = xoroshiro_next_long(base);
    const uint64_t xhi = xoroshiro_next_long(base);
    Xoroshiro128PP climate = {
        xlo ^ 0x83886c9d0ae3a662ULL,
        xhi ^ 0xafa638a61b42e8adULL
    };
    dp.countA = xoctave_init_profile(
        dp.oct, climate, kContinentalnessAmp, -9, 9);
    dp.countB = xoctave_init_profile(
        dp.oct + dp.countA, climate, kContinentalnessAmp, -9, 9);
    dp.amplitude = 45.0 / 30.0;
}

__device__ __forceinline__ double sample_octaves(
    const PerlinOctaveState* oct, int count,
    double x, double y, double z)
{
    double v = 0.0;
    for (int i = 0; i < count; ++i) {
        const double lf = oct[i].lacunarity;
        const double pv = xperlin_sample(
            oct[i].p, x * lf, y * lf, z * lf);
        v += oct[i].amplitude * pv;
    }
    return v;
}

__device__ __forceinline__ double sample_double_perlin(
    const DoublePerlinState18& dp, double x, double y, double z)
{
    const double f = 337.0 / 331.0;
    double v = sample_octaves(dp.oct, dp.countA, x, y, z);
    v += sample_octaves(
        dp.oct + dp.countA, dp.countB, x*f, y*f, z*f);
    return v * dp.amplitude;
}

struct ClimateDesc {
    int32_t offset;
    int32_t countA;
    int32_t countB;
    int32_t _pad;
    double amplitude;
};

struct ClimateState {
    ClimateDesc desc[6];
    PerlinOctaveState oct[46];
};

enum {
    C_SHIFT = 0,
    C_TEMPERATURE = 1,
    C_HUMIDITY = 2,
    C_CONTINENTALNESS = 3,
    C_EROSION = 4,
    C_WEIRDNESS = 5
};

__device__ __forceinline__ int init_compact_dp(
    ClimateState& st, int slot, int offset,
    Xoroshiro128PP xr, const double* amplitudes, int omin, int len)
{
    ClimateDesc& d = st.desc[slot];
    d.offset = offset;
    d.countA = xoctave_init_profile(st.oct + offset, xr, amplitudes, omin, len);
    d.countB = xoctave_init_profile(
        st.oct + offset + d.countA, xr, amplitudes, omin, len);

    int trimmed = len;
    while (trimmed > 0 && amplitudes[trimmed - 1] == 0.0)
        --trimmed;
    int leading = 0;
    while (leading < trimmed && amplitudes[leading] == 0.0) {
        ++leading;
        --trimmed;
    }
    d.amplitude = kDoubleAmp[trimmed];
    return d.countA + d.countB;
}

__device__ __forceinline__ void init_climate_state_mode(
    ClimateState& st, uint64_t world_seed, int large)
{
    Xoroshiro128PP base = xoroshiro_from_seed(world_seed);
    const uint64_t xlo = xoroshiro_next_long(base);
    const uint64_t xhi = xoroshiro_next_long(base);
    int off = 0;

    off += init_compact_dp(
        st, C_SHIFT, off,
        {xlo ^ 0x080518cf6af25384ULL, xhi ^ 0x3f3dfb40a54febd5ULL},
        kShiftAmp, -3, 4);
    off += init_compact_dp(
        st, C_TEMPERATURE, off,
        {xlo ^ (large ? 0x944b0073edf549dbULL : 0x5c7e6b29735f0d7fULL),
         xhi ^ (large ? 0x4ff44347e9d22b96ULL : 0xf7d86f1bbc734988ULL)},
        kTemperatureAmp, large ? -12 : -10, 6);
    off += init_compact_dp(
        st, C_HUMIDITY, off,
        {xlo ^ (large ? 0x71b8ab943dbd5301ULL : 0x81bb4d22e8dc168eULL),
         xhi ^ (large ? 0xbb63ddcf39ff7a2bULL : 0xf1c8b4bea16303cdULL)},
        kHumidityAmp, large ? -10 : -8, 6);
    off += init_compact_dp(
        st, C_CONTINENTALNESS, off,
        {xlo ^ (large ? 0x9a3f51a113fce8dcULL : 0x83886c9d0ae3a662ULL),
         xhi ^ (large ? 0xee2dbd157e5dcdadULL : 0xafa638a61b42e8adULL)},
        kContinentalnessAmp, large ? -11 : -9, 9);
    off += init_compact_dp(
        st, C_EROSION, off,
        {xlo ^ (large ? 0x8c984b1f8702a951ULL : 0xd02491e6058f6fd8ULL),
         xhi ^ (large ? 0xead7b1f92bae535fULL : 0x4792512c94c17a80ULL)},
        kErosionAmp, large ? -11 : -9, 5);
    off += init_compact_dp(
        st, C_WEIRDNESS, off,
        {xlo ^ 0xefc8ef4d36102b34ULL, xhi ^ 0x1beeeb324a0f24eaULL},
        kWeirdnessAmp, -7, 6);
}

__device__ __forceinline__ void init_climate_state(
    ClimateState& st, uint64_t world_seed)
{
    init_climate_state_mode(st, world_seed, 0);
}

__device__ __forceinline__ double sample_compact_dp(
    const ClimateState& st, int slot, double x, double y, double z)
{
    const ClimateDesc& d = st.desc[slot];
    const PerlinOctaveState* base = st.oct + d.offset;
    const double f = 337.0 / 331.0;
    double v = sample_octaves(base, d.countA, x, y, z);
    v += sample_octaves(base + d.countA, d.countB, x*f, y*f, z*f);
    return v * d.amplitude;
}

__global__ void xoroshiro_batch_kernel(
    const uint64_t* __restrict__ seeds,
    int32_t count,
    int32_t steps,
    uint64_t* __restrict__ out)
{
    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i >= count)
        return;

    Xoroshiro128PP s = xoroshiro_from_seed(seeds[i]);
    uint64_t* dst = out + (size_t)i * (size_t)steps;

    // Common initialization workloads consume only a handful of values.
    // Keep the loop simple so ptxas can unroll small constant-like trip counts
    // when this primitive is later inlined into specialized kernels.
    for (int32_t j = 0; j < steps; ++j)
        dst[j] = xoroshiro_next_long(s);
}

__global__ void xperlin_sample_batch_kernel(
    const uint64_t* __restrict__ seeds,
    const double* __restrict__ xs,
    const double* __restrict__ ys,
    const double* __restrict__ zs,
    int32_t count,
    double* __restrict__ out)
{
    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i >= count)
        return;

    PerlinState p;
    xperlin_init(p, seeds[i]);
    out[i] = xperlin_sample(p, xs[i], ys[i], zs[i]);
}

__global__ void xperlin_init_kernel(uint64_t seed, PerlinState* state)
{
    if (blockIdx.x == 0 && threadIdx.x == 0)
        xperlin_init(*state, seed);
}

__global__ __launch_bounds__(256) void xperlin_sample_fixed_kernel(
    const PerlinState* __restrict__ state,
    const double* __restrict__ xs,
    const double* __restrict__ ys,
    const double* __restrict__ zs,
    int32_t count,
    double* __restrict__ out)
{
    __shared__ PerlinState p;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&p);
    for (int i = (int)threadIdx.x; i < (int)sizeof(PerlinState);
         i += (int)blockDim.x)
        dst[i] = src[i];
    __syncthreads();

    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i < count)
        out[i] = xperlin_sample(p, xs[i], ys[i], zs[i]);
}

__global__ void continentalness_init_kernel(
    uint64_t world_seed, DoublePerlinState18* state)
{
    if (blockIdx.x == 0 && threadIdx.x == 0)
        init_continentalness_state(*state, world_seed);
}

__global__ __launch_bounds__(256) void continentalness_sample_kernel(
    const DoublePerlinState18* __restrict__ state,
    const double* __restrict__ xs,
    const double* __restrict__ zs,
    int32_t count,
    double* __restrict__ out)
{
    __shared__ DoublePerlinState18 dp;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&dp);
    for (int i = (int)threadIdx.x; i < (int)sizeof(DoublePerlinState18);
         i += (int)blockDim.x)
        dst[i] = src[i];
    __syncthreads();

    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i < count)
        out[i] = sample_double_perlin(dp, xs[i], 0.0, zs[i]);
}

__global__ void climate_init_kernel(uint64_t world_seed, ClimateState* state)
{
    if (blockIdx.x == 0 && threadIdx.x == 0)
        init_climate_state(*state, world_seed);
}

__global__ void climate_init_mode_kernel(
    uint64_t world_seed, int32_t large, ClimateState* state)
{
    if (blockIdx.x == 0 && threadIdx.x == 0)
        init_climate_state_mode(*state, world_seed, large != 0);
}

__global__ __launch_bounds__(256) void climate5_sample_kernel(
    const ClimateState* __restrict__ state,
    const double* __restrict__ xs,
    const double* __restrict__ zs,
    int32_t count,
    double* __restrict__ out5)
{
    __shared__ ClimateState st;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&st);
    for (int i = (int)threadIdx.x; i < (int)sizeof(ClimateState);
         i += (int)blockDim.x)
        dst[i] = src[i];
    __syncthreads();

    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i >= count)
        return;

    const double x = xs[i];
    const double z = zs[i];
    const double px =
        x + sample_compact_dp(st, C_SHIFT, x, 0.0, z) * 4.0;
    const double pz =
        z + sample_compact_dp(st, C_SHIFT, z, x, 0.0) * 4.0;

    double* o = out5 + (size_t)i * 5;
    o[2] = sample_compact_dp(st, C_CONTINENTALNESS, px, 0.0, pz);
    o[3] = sample_compact_dp(st, C_EROSION, px, 0.0, pz);
    o[4] = sample_compact_dp(st, C_WEIRDNESS, px, 0.0, pz);
    o[0] = sample_compact_dp(st, C_TEMPERATURE, px, 0.0, pz);
    o[1] = sample_compact_dp(st, C_HUMIDITY, px, 0.0, pz);
}

__global__ __launch_bounds__(256) void climate5_quant_kernel(
    const ClimateState* __restrict__ state,
    const double* __restrict__ xs,
    const double* __restrict__ zs,
    int32_t count,
    int32_t* __restrict__ out5)
{
    __shared__ ClimateState st;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&st);
    for (int i = (int)threadIdx.x; i < (int)sizeof(ClimateState);
         i += (int)blockDim.x)
        dst[i] = src[i];
    __syncthreads();

    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i >= count)
        return;

    const double x = xs[i];
    const double z = zs[i];
    const double px =
        x + sample_compact_dp(st, C_SHIFT, x, 0.0, z) * 4.0;
    const double pz =
        z + sample_compact_dp(st, C_SHIFT, z, x, 0.0) * 4.0;

    int32_t* o = out5 + (size_t)i * 5;
    const float c = (float)sample_compact_dp(
        st, C_CONTINENTALNESS, px, 0.0, pz);
    o[2] = (int32_t)(10000.0F * c);
    const float e = (float)sample_compact_dp(
        st, C_EROSION, px, 0.0, pz);
    o[3] = (int32_t)(10000.0F * e);
    const float w = (float)sample_compact_dp(
        st, C_WEIRDNESS, px, 0.0, pz);
    o[4] = (int32_t)(10000.0F * w);
    const float t = (float)sample_compact_dp(
        st, C_TEMPERATURE, px, 0.0, pz);
    o[0] = (int32_t)(10000.0F * t);
    const float h = (float)sample_compact_dp(
        st, C_HUMIDITY, px, 0.0, pz);
    o[1] = (int32_t)(10000.0F * h);
}

__global__ __launch_bounds__(256) void climate5_i32_kernel(
    const ClimateState* __restrict__ state,
    const int32_t* __restrict__ xs,
    const int32_t* __restrict__ zs,
    int32_t count,
    int32_t* __restrict__ out5)
{
    __shared__ ClimateState st;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&st);
    for (int i = (int)threadIdx.x; i < (int)sizeof(ClimateState);
         i += (int)blockDim.x)
        dst[i] = src[i];
    __syncthreads();

    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i >= count)
        return;

    const double x = (double)xs[i];
    const double z = (double)zs[i];
    const double px =
        x + sample_compact_dp(st, C_SHIFT, x, 0.0, z) * 4.0;
    const double pz =
        z + sample_compact_dp(st, C_SHIFT, z, x, 0.0) * 4.0;

    int32_t* o = out5 + (size_t)i * 5;
    const float c = (float)sample_compact_dp(
        st, C_CONTINENTALNESS, px, 0.0, pz);
    o[2] = (int32_t)(10000.0F * c);
    const float e = (float)sample_compact_dp(
        st, C_EROSION, px, 0.0, pz);
    o[3] = (int32_t)(10000.0F * e);
    const float w = (float)sample_compact_dp(
        st, C_WEIRDNESS, px, 0.0, pz);
    o[4] = (int32_t)(10000.0F * w);
    const float t = (float)sample_compact_dp(
        st, C_TEMPERATURE, px, 0.0, pz);
    o[0] = (int32_t)(10000.0F * t);
    const float h = (float)sample_compact_dp(
        st, C_HUMIDITY, px, 0.0, pz);
    o[1] = (int32_t)(10000.0F * h);
}

__device__ __forceinline__ float mcgpu_peaks_and_valleys(float weirdness)
{
    return -(fabsf(fabsf(weirdness) - 0.6666667F) - 0.33333334F) * 3.0F;
}

__device__ __forceinline__ uint64_t btree20_np_dist(
    const int32_t np[6],
    const uint64_t* __restrict__ nodes,
    const int32_t* __restrict__ param,
    int idx)
{
    const uint64_t node = nodes[idx];
    uint64_t ds = 0;
    #pragma unroll
    for (int i = 0; i < 6; ++i) {
        const int pi = (int)((node >> (8 * i)) & 0xFFULL);
        const int64_t lo = (int64_t)param[2 * pi + 0];
        const int64_t hi = (int64_t)param[2 * pi + 1];
        const int64_t v = (int64_t)np[i];
        int64_t d = 0;
        if (v > hi)
            d = v - hi;
        else if (v < lo)
            d = lo - v;
        ds += (uint64_t)(d * d);
    }
    return ds;
}

template <int DEPTH>
__device__ __forceinline__ int btree20_search(
    const int32_t np[6],
    const uint64_t* __restrict__ nodes,
    const int32_t* __restrict__ param,
    int len,
    int idx,
    int alt,
    uint64_t ds)
{
    if constexpr (DEPTH >= 5) {
        return idx;
    } else {
        constexpr uint32_t steps[5] = {1555U, 259U, 43U, 7U, 1U};
        constexpr uint32_t step = steps[DEPTH];

        // Matches cubiomes' depth-skip loop when a coarse step would leave
        // the compact tail of the tree.
        if (idx + (int)step >= len)
            return btree20_search<DEPTH + 1>(
                np, nodes, param, len, idx, alt, ds);

        const uint64_t node = nodes[idx];
        int inner = (int)((node >> 48) & 0xFFFFULL);
        int leaf = alt;

        #pragma unroll
        for (int k = 0; k < 6; ++k) {
            if (inner >= len)
                break;
            const uint64_t ds_inner =
                btree20_np_dist(np, nodes, param, inner);
            if (ds_inner < ds) {
                const int leaf2 = btree20_search<DEPTH + 1>(
                    np, nodes, param, len, inner, leaf, ds);
                const uint64_t ds_leaf2 =
                    (inner == leaf2)
                    ? ds_inner
                    : btree20_np_dist(np, nodes, param, leaf2);
                if (ds_leaf2 < ds) {
                    ds = ds_leaf2;
                    leaf = leaf2;
                }
            }
            inner += (int)step;
        }
        return leaf;
    }
}

__device__ __forceinline__ int btree20_biome(
    const int32_t np[6],
    const uint64_t* __restrict__ nodes,
    const int32_t* __restrict__ param,
    int len)
{
    const int idx = btree20_search<0>(
        np, nodes, param, len, 0, 0, ~0ULL);
    return (int)((nodes[idx] >> 48) & 0xFFULL);
}

template <int DEPTH>
__device__ __forceinline__ int btree18_search(
    const int32_t np[6],
    const uint64_t* __restrict__ nodes,
    const int32_t* __restrict__ param,
    int len,
    int idx,
    int alt,
    uint64_t ds)
{
    if constexpr (DEPTH >= 4) {
        return idx;
    } else {
        constexpr uint32_t steps[4] = {1111U, 111U, 11U, 1U};
        constexpr uint32_t step = steps[DEPTH];
        if (idx + (int)step >= len)
            return btree18_search<DEPTH + 1>(
                np, nodes, param, len, idx, alt, ds);

        const uint64_t node = nodes[idx];
        int inner = (int)((node >> 48) & 0xFFFFULL);
        int leaf = alt;
        #pragma unroll
        for (int k = 0; k < 10; ++k) {
            if (inner >= len)
                break;
            const uint64_t ds_inner =
                btree20_np_dist(np, nodes, param, inner);
            if (ds_inner < ds) {
                const int leaf2 = btree18_search<DEPTH + 1>(
                    np, nodes, param, len, inner, leaf, ds);
                const uint64_t ds_leaf2 =
                    (inner == leaf2)
                    ? ds_inner
                    : btree20_np_dist(np, nodes, param, leaf2);
                if (ds_leaf2 < ds) {
                    ds = ds_leaf2;
                    leaf = leaf2;
                }
            }
            inner += (int)step;
        }
        return leaf;
    }
}

__device__ __forceinline__ int btree_modern_biome(
    const int32_t np[6],
    const uint64_t* __restrict__ nodes,
    const int32_t* __restrict__ param,
    int len,
    int family)
{
    int idx;
    if (family == 0) {
        idx = btree18_search<0>(
            np, nodes, param, len, 0, 0, ~0ULL);
    } else {
        idx = btree20_search<0>(
            np, nodes, param, len, 0, 0, ~0ULL);
    }
    return (int)((nodes[idx] >> 48) & 0xFFULL);
}

__global__ __launch_bounds__(256) void climate6_i32_kernel(
    const ClimateState* __restrict__ state,
    const int32_t* __restrict__ xs,
    const int32_t* __restrict__ ys,
    const int32_t* __restrict__ zs,
    int32_t count,
    int32_t* __restrict__ out6)
{
    __shared__ ClimateState st;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&st);
    for (int i = (int)threadIdx.x; i < (int)sizeof(ClimateState);
         i += (int)blockDim.x)
        dst[i] = src[i];
    __syncthreads();

    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i >= count)
        return;

    const double x = (double)xs[i];
    const double z = (double)zs[i];
    const double px =
        x + sample_compact_dp(st, C_SHIFT, x, 0.0, z) * 4.0;
    const double pz =
        z + sample_compact_dp(st, C_SHIFT, z, x, 0.0) * 4.0;

    int32_t* o = out6 + (size_t)i * 6;
    const float c = (float)sample_compact_dp(
        st, C_CONTINENTALNESS, px, 0.0, pz);
    o[2] = (int32_t)(10000.0F * c);
    const float e = (float)sample_compact_dp(
        st, C_EROSION, px, 0.0, pz);
    o[3] = (int32_t)(10000.0F * e);
    const float w = (float)sample_compact_dp(
        st, C_WEIRDNESS, px, 0.0, pz);
    o[5] = (int32_t)(10000.0F * w);

    const float vals[4] = {
        c, e, mcgpu_peaks_and_valleys(w), w
    };
    const float off_f = mcgpu_depth_spline(vals) + 0.015F;
    const double d0 =
        1.0 - ((double)(ys[i] * 4)) / 128.0 - 83.0 / 160.0 +
        (double)off_f;
    const float d = (float)d0;
    o[4] = (int32_t)(10000.0F * d);

    const float t = (float)sample_compact_dp(
        st, C_TEMPERATURE, px, 0.0, pz);
    o[0] = (int32_t)(10000.0F * t);
    const float h = (float)sample_compact_dp(
        st, C_HUMIDITY, px, 0.0, pz);
    o[1] = (int32_t)(10000.0F * h);
}

__device__ __forceinline__ int biome_modern_at(
    const ClimateState& st,
    const uint64_t* __restrict__ tree_nodes,
    const int32_t* __restrict__ tree_param,
    int32_t tree_len,
    int32_t tree_family,
    int32_t xi, int32_t yi, int32_t zi)
{
    const double x = (double)xi;
    const double z = (double)zi;
    const double px =
        x + sample_compact_dp(st, C_SHIFT, x, 0.0, z) * 4.0;
    const double pz =
        z + sample_compact_dp(st, C_SHIFT, z, x, 0.0) * 4.0;

    int32_t np[6];
    const float c = (float)sample_compact_dp(
        st, C_CONTINENTALNESS, px, 0.0, pz);
    np[2] = (int32_t)(10000.0F * c);
    const float e = (float)sample_compact_dp(
        st, C_EROSION, px, 0.0, pz);
    np[3] = (int32_t)(10000.0F * e);
    const float w = (float)sample_compact_dp(
        st, C_WEIRDNESS, px, 0.0, pz);
    np[5] = (int32_t)(10000.0F * w);

    const float vals[4] = {
        c, e, mcgpu_peaks_and_valleys(w), w
    };
    const float off_f = mcgpu_depth_spline(vals) + 0.015F;
    const double d0 =
        1.0 - ((double)(yi * 4)) / 128.0 - 83.0 / 160.0 +
        (double)off_f;
    const float d = (float)d0;
    np[4] = (int32_t)(10000.0F * d);

    const float t = (float)sample_compact_dp(
        st, C_TEMPERATURE, px, 0.0, pz);
    np[0] = (int32_t)(10000.0F * t);
    const float h = (float)sample_compact_dp(
        st, C_HUMIDITY, px, 0.0, pz);
    np[1] = (int32_t)(10000.0F * h);

    return btree_modern_biome(
        np, tree_nodes, tree_param, tree_len, tree_family);
}

__global__ __launch_bounds__(256) void biome_modern_i32_kernel(
    const ClimateState* __restrict__ state,
    const uint64_t* __restrict__ tree_nodes,
    const int32_t* __restrict__ tree_param,
    int32_t tree_len,
    int32_t tree_family,
    const int32_t* __restrict__ xs,
    const int32_t* __restrict__ ys,
    const int32_t* __restrict__ zs,
    int32_t count,
    int32_t* __restrict__ biome_out)
{
    __shared__ ClimateState st;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&st);
    for (int i = (int)threadIdx.x; i < (int)sizeof(ClimateState);
         i += (int)blockDim.x)
        dst[i] = src[i];
    __syncthreads();

    const int32_t i =
        (int32_t)((int64_t)blockIdx.x * blockDim.x + threadIdx.x);
    if (i >= count)
        return;

    biome_out[i] = biome_modern_at(
        st, tree_nodes, tree_param, tree_len, tree_family,
        xs[i], ys[i], zs[i]);
}

__device__ __forceinline__ bool slime_chunk_exact(
    uint64_t world_seed, int32_t chunk_x, int32_t chunk_z)
{
    const uint32_t ux = (uint32_t)chunk_x;
    const uint32_t uz = (uint32_t)chunk_z;
    const uint64_t p1 =
        (uint64_t)(int64_t)(int32_t)(ux * ux * 0x4c1906U);
    const uint64_t p2 =
        (uint64_t)(int64_t)(int32_t)(ux * 0x5ac0dbU);
    const uint64_t p3 =
        (uint64_t)(int64_t)(int32_t)(uz * uz) * 0x4307a7ULL;
    const uint64_t p4 =
        (uint64_t)(int64_t)(int32_t)(uz * 0x5f24fU);

    const uint64_t mixed = world_seed + p1 + p2 + p3 + p4;
    uint64_t rnd =
        ((mixed ^ 0x3ad8025fULL) ^ 0x5DEECE66DULL) &
        0xFFFFFFFFFFFFULL;
    for (;;) {
        rnd = (rnd * 0x5DEECE66DULL + 0xBULL) & 0xFFFFFFFFFFFFULL;
        const uint32_t bits = (uint32_t)(rnd >> 17);
        const uint32_t value = bits % 10U;
        if (bits - value + 9U <= 0x7FFFFFFFU)
            return value == 0U;
    }
}

// Slime Finder biome-filter fast path.
// One CUDA block owns one slime candidate. The complete 17x17 chunk
// neighborhood is exactly a 68x68 quart grid. Deep Dark checks 17 quart-Y
// layers (-16..0); Mushroom Fields checks one layer (Y=16).
// Input flags: bit0=Deep Dark, bit1=Mushroom Fields.
// Output mask uses the same bits and is exact-equivalent to the CPU loops.
__global__ __launch_bounds__(256) void biome_filter_candidates_kernel(
    const ClimateState* __restrict__ state,
    const uint64_t* __restrict__ tree_nodes,
    const int32_t* __restrict__ tree_param,
    int32_t tree_len,
    int32_t tree_family,
    uint64_t world_seed,
    const int32_t* __restrict__ center_chunk_x,
    const int32_t* __restrict__ center_chunk_z,
    int32_t count,
    int32_t flags,
    int32_t* __restrict__ mask_out)
{
    const int32_t candidate = (int32_t)blockIdx.x;
    if (candidate >= count)
        return;

    __shared__ ClimateState st;
    __shared__ unsigned int hit_mask;
    __shared__ int eligible_count;
    __shared__ uint16_t eligible_chunks[221];

    const uint8_t* src = reinterpret_cast<const uint8_t*>(state);
    uint8_t* dst = reinterpret_cast<uint8_t*>(&st);
    for (int i = (int)threadIdx.x; i < (int)sizeof(ClimateState);
         i += (int)blockDim.x)
        dst[i] = src[i];
    if (threadIdx.x == 0) {
        hit_mask = 0U;
        eligible_count = 0;
    }
    __syncthreads();

    const int32_t ccx = center_chunk_x[candidate];
    const int32_t ccz = center_chunk_z[candidate];
    for (int ci = (int)threadIdx.x; ci < 17 * 17;
         ci += (int)blockDim.x) {
        const int dx = ci / 17 - 8;
        const int dz = ci % 17 - 8;
        if (dx * dx + dz * dz <= 68 &&
            slime_chunk_exact(world_seed, ccx + dx, ccz + dz)) {
            const int slot = atomicAdd(&eligible_count, 1);
            if (slot < 221)
                eligible_chunks[slot] = (uint16_t)ci;
        }
    }
    __syncthreads();

    constexpr int QUARTS_PER_CHUNK = 16;
    constexpr int DEEP_LAYERS = 17;
    const int compact_chunks = eligible_count;
    const int deep_work =
        (flags & 1) ? compact_chunks * DEEP_LAYERS * QUARTS_PER_CHUNK : 0;
    const int mushroom_work =
        (flags & 2) ? compact_chunks * QUARTS_PER_CHUNK : 0;
    const int total_work = deep_work + mushroom_work;

    for (int work = (int)threadIdx.x; work < total_work;
         work += (int)blockDim.x) {
        const bool mushroom = work >= deep_work;
        int local = mushroom ? (work - deep_work) : work;
        const int compact_index = mushroom
            ? (local / QUARTS_PER_CHUNK)
            : (local / (DEEP_LAYERS * QUARTS_PER_CHUNK));
        const int ci = (int)eligible_chunks[compact_index];

        int y_index = 0;
        int quart_index;
        if (mushroom) {
            quart_index = local % QUARTS_PER_CHUNK;
        } else {
            const int within =
                local % (DEEP_LAYERS * QUARTS_PER_CHUNK);
            y_index = within / QUARTS_PER_CHUNK;
            quart_index = within % QUARTS_PER_CHUNK;
        }

        const int dx = ci / 17 - 8;
        const int dz = ci % 17 - 8;
        const int nx = quart_index / 4;
        const int nz = quart_index % 4;
        const int qx = (ccx + dx) * 4 + nx;
        const int qz = (ccz + dz) * 4 + nz;
        const int qy = mushroom ? 16 : (-16 + y_index);

        const int biome = biome_modern_at(
            st, tree_nodes, tree_param, tree_len, tree_family,
            qx, qy, qz);
        if (!mushroom && biome == 183)
            atomicOr(&hit_mask, 1U);
        else if (mushroom && biome == 14)
            atomicOr(&hit_mask, 2U);
    }
    __syncthreads();
    if (threadIdx.x == 0)
        mask_out[candidate] = (int32_t)hit_mask;
}

extern "C" MCGPU_API int mcgpu_api_version(void)
{
    return 1;
}

extern "C" MCGPU_API int32_t mcgpu_modern_recommended_filter_batch(void)
{
    int device = 0;
    cudaDeviceProp prop = {};
    if (cudaGetDevice(&device) != cudaSuccess ||
        cudaGetDeviceProperties(&prop, device) != cudaSuccess)
        return 128;

    int active_blocks = 0;
    if (cudaOccupancyMaxActiveBlocksPerMultiprocessor(
            &active_blocks, biome_filter_candidates_kernel, 256, 0) != cudaSuccess ||
        active_blocks <= 0)
        active_blocks = 1;

    int32_t one_wave = (int32_t)prop.multiProcessorCount * active_blocks;
    one_wave = ((one_wave + 31) / 32) * 32;
    if (one_wave < 32) one_wave = 32;
    if (one_wave > 1024) one_wave = 1024;
    return one_wave;
}

extern "C" MCGPU_API const char* mcgpu_build_name(void)
{
    return "MinecraftGPU prototype 0.1 / xoroshiro128++";
}

extern "C" MCGPU_API int mcgpu_xoroshiro_nextlong_batch(
    const uint64_t* seeds,
    int32_t count,
    int32_t steps,
    uint64_t* out)
{
    if (!seeds || !out || count <= 0 || steps <= 0)
        return MCGPU_ERR_ARG;

    const size_t seed_bytes = (size_t)count * sizeof(uint64_t);
    const size_t out_count = (size_t)count * (size_t)steps;
    if (out_count / (size_t)steps != (size_t)count)
        return MCGPU_ERR_ARG;
    const size_t out_bytes = out_count * sizeof(uint64_t);
    if (out_count != 0 && out_bytes / sizeof(uint64_t) != out_count)
        return MCGPU_ERR_ARG;

    uint64_t* d_seeds = nullptr;
    uint64_t* d_out = nullptr;

    if (cudaMalloc(&d_seeds, seed_bytes) != cudaSuccess)
        return MCGPU_ERR_ALLOC;
    if (cudaMalloc(&d_out, out_bytes) != cudaSuccess) {
        cudaFree(d_seeds);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_seeds, seeds, seed_bytes, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        xoroshiro_batch_kernel<<<blocks, TPB>>>(d_seeds, count, steps, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out, d_out, out_bytes, cudaMemcpyDeviceToHost) != cudaSuccess) {
            rc = MCGPU_ERR_CUDA;
        }
    }

    cudaFree(d_out);
    cudaFree(d_seeds);
    return rc;
}

extern "C" MCGPU_API int mcgpu_xperlin_sample_batch(
    const uint64_t* seeds,
    const double* xs,
    const double* ys,
    const double* zs,
    int32_t count,
    double* out)
{
    if (!seeds || !xs || !ys || !zs || !out || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t n64 = (size_t)count * sizeof(uint64_t);
    const size_t nd = (size_t)count * sizeof(double);
    uint64_t* d_seeds = nullptr;
    double *d_x = nullptr, *d_y = nullptr, *d_z = nullptr, *d_out = nullptr;

    if (cudaMalloc(&d_seeds, n64) != cudaSuccess ||
        cudaMalloc(&d_x, nd) != cudaSuccess ||
        cudaMalloc(&d_y, nd) != cudaSuccess ||
        cudaMalloc(&d_z, nd) != cudaSuccess ||
        cudaMalloc(&d_out, nd) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_y) cudaFree(d_y);
        if (d_x) cudaFree(d_x);
        if (d_seeds) cudaFree(d_seeds);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_seeds, seeds, n64, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_x, xs, nd, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_y, ys, nd, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, nd, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        constexpr int TPB = 128;
        const int blocks = (count + TPB - 1) / TPB;
        xperlin_sample_batch_kernel<<<blocks, TPB>>>(
            d_seeds, d_x, d_y, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out, d_out, nd, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_y);
    cudaFree(d_x);
    cudaFree(d_seeds);
    return rc;
}

extern "C" MCGPU_API int mcgpu_xperlin_sample_fixed_seed(
    uint64_t seed,
    const double* xs,
    const double* ys,
    const double* zs,
    int32_t count,
    double* out)
{
    if (!xs || !ys || !zs || !out || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t nd = (size_t)count * sizeof(double);
    PerlinState* d_state = nullptr;
    double *d_x = nullptr, *d_y = nullptr, *d_z = nullptr, *d_out = nullptr;
    if (cudaMalloc(&d_state, sizeof(PerlinState)) != cudaSuccess ||
        cudaMalloc(&d_x, nd) != cudaSuccess ||
        cudaMalloc(&d_y, nd) != cudaSuccess ||
        cudaMalloc(&d_z, nd) != cudaSuccess ||
        cudaMalloc(&d_out, nd) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_y) cudaFree(d_y);
        if (d_x) cudaFree(d_x);
        if (d_state) cudaFree(d_state);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_x, xs, nd, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_y, ys, nd, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, nd, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        xperlin_init_kernel<<<1, 1>>>(seed, d_state);
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        xperlin_sample_fixed_kernel<<<blocks, TPB>>>(
            d_state, d_x, d_y, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out, d_out, nd, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_y);
    cudaFree(d_x);
    cudaFree(d_state);
    return rc;
}

extern "C" MCGPU_API int mcgpu_continentalness_noise_fixed_seed(
    uint64_t world_seed,
    const double* xs,
    const double* zs,
    int32_t count,
    double* out)
{
    if (!xs || !zs || !out || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t nd = (size_t)count * sizeof(double);
    DoublePerlinState18* d_state = nullptr;
    double *d_x = nullptr, *d_z = nullptr, *d_out = nullptr;
    if (cudaMalloc(&d_state, sizeof(DoublePerlinState18)) != cudaSuccess ||
        cudaMalloc(&d_x, nd) != cudaSuccess ||
        cudaMalloc(&d_z, nd) != cudaSuccess ||
        cudaMalloc(&d_out, nd) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_x) cudaFree(d_x);
        if (d_state) cudaFree(d_state);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_x, xs, nd, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, nd, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        continentalness_init_kernel<<<1, 1>>>(world_seed, d_state);
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        continentalness_sample_kernel<<<blocks, TPB>>>(
            d_state, d_x, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out, d_out, nd, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_x);
    cudaFree(d_state);
    return rc;
}


extern "C" MCGPU_API int mcgpu_climate5_fixed_seed(
    uint64_t world_seed,
    const double* xs,
    const double* zs,
    int32_t count,
    double* out5)
{
    if (!xs || !zs || !out5 || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t nd = (size_t)count * sizeof(double);
    const size_t no = (size_t)count * 5 * sizeof(double);
    ClimateState* d_state = nullptr;
    double *d_x = nullptr, *d_z = nullptr, *d_out = nullptr;
    if (cudaMalloc(&d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&d_x, nd) != cudaSuccess ||
        cudaMalloc(&d_z, nd) != cudaSuccess ||
        cudaMalloc(&d_out, no) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_x) cudaFree(d_x);
        if (d_state) cudaFree(d_state);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_x, xs, nd, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, nd, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        climate_init_kernel<<<1, 1>>>(world_seed, d_state);
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        climate5_sample_kernel<<<blocks, TPB>>>(
            d_state, d_x, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out5, d_out, no, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_x);
    cudaFree(d_state);
    return rc;
}


extern "C" MCGPU_API int mcgpu_climate5_quant_fixed_seed(
    uint64_t world_seed,
    const double* xs,
    const double* zs,
    int32_t count,
    int32_t* out5)
{
    if (!xs || !zs || !out5 || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t nd = (size_t)count * sizeof(double);
    const size_t no = (size_t)count * 5 * sizeof(int32_t);
    ClimateState* d_state = nullptr;
    double *d_x = nullptr, *d_z = nullptr;
    int32_t* d_out = nullptr;
    if (cudaMalloc(&d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&d_x, nd) != cudaSuccess ||
        cudaMalloc(&d_z, nd) != cudaSuccess ||
        cudaMalloc(&d_out, no) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_x) cudaFree(d_x);
        if (d_state) cudaFree(d_state);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_x, xs, nd, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, nd, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        climate_init_kernel<<<1, 1>>>(world_seed, d_state);
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        climate5_quant_kernel<<<blocks, TPB>>>(
            d_state, d_x, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out5, d_out, no, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_x);
    cudaFree(d_state);
    return rc;
}

extern "C" MCGPU_API int mcgpu_climate5_i32_fixed_seed(
    uint64_t world_seed,
    const int32_t* xs,
    const int32_t* zs,
    int32_t count,
    int32_t* out5)
{
    if (!xs || !zs || !out5 || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t ni = (size_t)count * sizeof(int32_t);
    const size_t no = (size_t)count * 5 * sizeof(int32_t);
    ClimateState* d_state = nullptr;
    int32_t *d_x = nullptr, *d_z = nullptr, *d_out = nullptr;
    if (cudaMalloc(&d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&d_x, ni) != cudaSuccess ||
        cudaMalloc(&d_z, ni) != cudaSuccess ||
        cudaMalloc(&d_out, no) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_x) cudaFree(d_x);
        if (d_state) cudaFree(d_state);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_x, xs, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, ni, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        climate_init_kernel<<<1, 1>>>(world_seed, d_state);
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        climate5_i32_kernel<<<blocks, TPB>>>(
            d_state, d_x, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out5, d_out, no, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_x);
    cudaFree(d_state);
    return rc;
}

struct McGpuClimateContext {
    ClimateState* d_state;
    int32_t* d_x;
    int32_t* d_z;
    int32_t* d_out;
    int32_t capacity;
};

extern "C" MCGPU_API void* mcgpu_climate_ctx_create(
    uint64_t world_seed, int32_t capacity)
{
    if (capacity <= 0)
        return nullptr;

    McGpuClimateContext* ctx =
        (McGpuClimateContext*)malloc(sizeof(McGpuClimateContext));
    if (!ctx)
        return nullptr;
    ctx->d_state = nullptr;
    ctx->d_x = nullptr;
    ctx->d_z = nullptr;
    ctx->d_out = nullptr;
    ctx->capacity = capacity;

    const size_t ni = (size_t)capacity * sizeof(int32_t);
    const size_t no = (size_t)capacity * 5 * sizeof(int32_t);
    if (cudaMalloc(&ctx->d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&ctx->d_x, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_z, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_out, no) != cudaSuccess) {
        if (ctx->d_out) cudaFree(ctx->d_out);
        if (ctx->d_z) cudaFree(ctx->d_z);
        if (ctx->d_x) cudaFree(ctx->d_x);
        if (ctx->d_state) cudaFree(ctx->d_state);
        free(ctx);
        return nullptr;
    }

    climate_init_kernel<<<1, 1>>>(world_seed, ctx->d_state);
    if (cudaGetLastError() != cudaSuccess ||
        cudaDeviceSynchronize() != cudaSuccess) {
        cudaFree(ctx->d_out);
        cudaFree(ctx->d_z);
        cudaFree(ctx->d_x);
        cudaFree(ctx->d_state);
        free(ctx);
        return nullptr;
    }
    return ctx;
}

extern "C" MCGPU_API int mcgpu_climate_ctx_query_i32(
    void* handle,
    const int32_t* xs,
    const int32_t* zs,
    int32_t count,
    int32_t* out5)
{
    McGpuClimateContext* ctx = (McGpuClimateContext*)handle;
    if (!ctx || !xs || !zs || !out5 || count <= 0 || count > ctx->capacity)
        return MCGPU_ERR_ARG;

    const size_t ni = (size_t)count * sizeof(int32_t);
    const size_t no = (size_t)count * 5 * sizeof(int32_t);
    if (cudaMemcpy(ctx->d_x, xs, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_z, zs, ni, cudaMemcpyHostToDevice) != cudaSuccess)
        return MCGPU_ERR_CUDA;

    constexpr int TPB = 256;
    const int blocks = (count + TPB - 1) / TPB;
    climate5_i32_kernel<<<blocks, TPB>>>(
        ctx->d_state, ctx->d_x, ctx->d_z, count, ctx->d_out);
    if (cudaGetLastError() != cudaSuccess ||
        cudaDeviceSynchronize() != cudaSuccess ||
        cudaMemcpy(out5, ctx->d_out, no, cudaMemcpyDeviceToHost) != cudaSuccess)
        return MCGPU_ERR_CUDA;
    return MCGPU_OK;
}

extern "C" MCGPU_API void mcgpu_climate_ctx_destroy(void* handle)
{
    McGpuClimateContext* ctx = (McGpuClimateContext*)handle;
    if (!ctx)
        return;
    if (ctx->d_out) cudaFree(ctx->d_out);
    if (ctx->d_z) cudaFree(ctx->d_z);
    if (ctx->d_x) cudaFree(ctx->d_x);
    if (ctx->d_state) cudaFree(ctx->d_state);
    free(ctx);
}

extern "C" MCGPU_API int mcgpu_climate6_i32_fixed_seed(
    uint64_t world_seed,
    const int32_t* xs,
    const int32_t* ys,
    const int32_t* zs,
    int32_t count,
    int32_t* out6)
{
    if (!xs || !ys || !zs || !out6 || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t ni = (size_t)count * sizeof(int32_t);
    const size_t no = (size_t)count * 6 * sizeof(int32_t);
    ClimateState* d_state = nullptr;
    int32_t *d_x = nullptr, *d_y = nullptr, *d_z = nullptr, *d_out = nullptr;
    if (cudaMalloc(&d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&d_x, ni) != cudaSuccess ||
        cudaMalloc(&d_y, ni) != cudaSuccess ||
        cudaMalloc(&d_z, ni) != cudaSuccess ||
        cudaMalloc(&d_out, no) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_y) cudaFree(d_y);
        if (d_x) cudaFree(d_x);
        if (d_state) cudaFree(d_state);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_x, xs, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_y, ys, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, ni, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        climate_init_kernel<<<1, 1>>>(world_seed, d_state);
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        climate6_i32_kernel<<<blocks, TPB>>>(
            d_state, d_x, d_y, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(out6, d_out, no, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_y);
    cudaFree(d_x);
    cudaFree(d_state);
    return rc;
}

extern "C" MCGPU_API int mcgpu_biome20_i32_fixed_seed(
    uint64_t world_seed,
    const int32_t* xs,
    const int32_t* ys,
    const int32_t* zs,
    int32_t count,
    int32_t* biome_out)
{
    if (!xs || !ys || !zs || !biome_out || count <= 0)
        return MCGPU_ERR_ARG;

    const size_t ni = (size_t)count * sizeof(int32_t);
    const size_t no = (size_t)count * sizeof(int32_t);
    const size_t nn = sizeof(btree20_nodes);
    const size_t npb = sizeof(btree20_param);
    const int32_t tree_len = (int32_t)(sizeof(btree20_nodes) / sizeof(btree20_nodes[0]));

    ClimateState* d_state = nullptr;
    uint64_t* d_nodes = nullptr;
    int32_t* d_param = nullptr;
    int32_t *d_x = nullptr, *d_y = nullptr, *d_z = nullptr, *d_out = nullptr;

    if (cudaMalloc(&d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&d_nodes, nn) != cudaSuccess ||
        cudaMalloc(&d_param, npb) != cudaSuccess ||
        cudaMalloc(&d_x, ni) != cudaSuccess ||
        cudaMalloc(&d_y, ni) != cudaSuccess ||
        cudaMalloc(&d_z, ni) != cudaSuccess ||
        cudaMalloc(&d_out, no) != cudaSuccess) {
        if (d_out) cudaFree(d_out);
        if (d_z) cudaFree(d_z);
        if (d_y) cudaFree(d_y);
        if (d_x) cudaFree(d_x);
        if (d_param) cudaFree(d_param);
        if (d_nodes) cudaFree(d_nodes);
        if (d_state) cudaFree(d_state);
        return MCGPU_ERR_ALLOC;
    }

    int rc = MCGPU_OK;
    if (cudaMemcpy(d_nodes, btree20_nodes, nn, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_param, btree20_param, npb, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_x, xs, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_y, ys, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(d_z, zs, ni, cudaMemcpyHostToDevice) != cudaSuccess) {
        rc = MCGPU_ERR_CUDA;
    } else {
        climate_init_kernel<<<1, 1>>>(world_seed, d_state);
        constexpr int TPB = 256;
        const int blocks = (count + TPB - 1) / TPB;
        biome_modern_i32_kernel<<<blocks, TPB>>>(
            d_state, d_nodes, d_param, tree_len, 1,
            d_x, d_y, d_z, count, d_out);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess ||
            cudaMemcpy(biome_out, d_out, no, cudaMemcpyDeviceToHost) != cudaSuccess)
            rc = MCGPU_ERR_CUDA;
    }

    cudaFree(d_out);
    cudaFree(d_z);
    cudaFree(d_y);
    cudaFree(d_x);
    cudaFree(d_param);
    cudaFree(d_nodes);
    cudaFree(d_state);
    return rc;
}

struct McGpuBiome20Context {
    ClimateState* d_state;
    uint64_t* d_nodes;
    int32_t* d_param;
    int32_t* d_x;
    int32_t* d_y;
    int32_t* d_z;
    int32_t* d_out;
    int32_t capacity;
    int32_t tree_len;
};

extern "C" MCGPU_API void* mcgpu_biome20_ctx_create(
    uint64_t world_seed, int32_t capacity)
{
    if (capacity <= 0)
        return nullptr;

    McGpuBiome20Context* ctx =
        (McGpuBiome20Context*)malloc(sizeof(McGpuBiome20Context));
    if (!ctx)
        return nullptr;
    memset(ctx, 0, sizeof(*ctx));
    ctx->capacity = capacity;
    ctx->tree_len = (int32_t)(sizeof(btree20_nodes) / sizeof(btree20_nodes[0]));

    const size_t ni = (size_t)capacity * sizeof(int32_t);
    const size_t nn = sizeof(btree20_nodes);
    const size_t npb = sizeof(btree20_param);

    if (cudaMalloc(&ctx->d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&ctx->d_nodes, nn) != cudaSuccess ||
        cudaMalloc(&ctx->d_param, npb) != cudaSuccess ||
        cudaMalloc(&ctx->d_x, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_y, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_z, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_out, ni) != cudaSuccess) {
        if (ctx->d_out) cudaFree(ctx->d_out);
        if (ctx->d_z) cudaFree(ctx->d_z);
        if (ctx->d_y) cudaFree(ctx->d_y);
        if (ctx->d_x) cudaFree(ctx->d_x);
        if (ctx->d_param) cudaFree(ctx->d_param);
        if (ctx->d_nodes) cudaFree(ctx->d_nodes);
        if (ctx->d_state) cudaFree(ctx->d_state);
        free(ctx);
        return nullptr;
    }

    if (cudaMemcpy(ctx->d_nodes, btree20_nodes, nn, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_param, btree20_param, npb, cudaMemcpyHostToDevice) != cudaSuccess) {
        cudaFree(ctx->d_out); cudaFree(ctx->d_z); cudaFree(ctx->d_y);
        cudaFree(ctx->d_x); cudaFree(ctx->d_param); cudaFree(ctx->d_nodes);
        cudaFree(ctx->d_state); free(ctx); return nullptr;
    }

    climate_init_kernel<<<1, 1>>>(world_seed, ctx->d_state);
    if (cudaGetLastError() != cudaSuccess || cudaDeviceSynchronize() != cudaSuccess) {
        cudaFree(ctx->d_out); cudaFree(ctx->d_z); cudaFree(ctx->d_y);
        cudaFree(ctx->d_x); cudaFree(ctx->d_param); cudaFree(ctx->d_nodes);
        cudaFree(ctx->d_state); free(ctx); return nullptr;
    }
    return ctx;
}

extern "C" MCGPU_API int mcgpu_biome20_ctx_query(
    void* handle,
    const int32_t* xs,
    const int32_t* ys,
    const int32_t* zs,
    int32_t count,
    int32_t* biome_out)
{
    McGpuBiome20Context* ctx = (McGpuBiome20Context*)handle;
    if (!ctx || !xs || !ys || !zs || !biome_out ||
        count <= 0 || count > ctx->capacity)
        return MCGPU_ERR_ARG;

    const size_t ni = (size_t)count * sizeof(int32_t);
    if (cudaMemcpy(ctx->d_x, xs, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_y, ys, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_z, zs, ni, cudaMemcpyHostToDevice) != cudaSuccess)
        return MCGPU_ERR_CUDA;

    constexpr int TPB = 256;
    const int blocks = (count + TPB - 1) / TPB;
    biome_modern_i32_kernel<<<blocks, TPB>>>(
        ctx->d_state, ctx->d_nodes, ctx->d_param, ctx->tree_len, 1,
        ctx->d_x, ctx->d_y, ctx->d_z, count, ctx->d_out);
    if (cudaGetLastError() != cudaSuccess ||
        cudaDeviceSynchronize() != cudaSuccess ||
        cudaMemcpy(biome_out, ctx->d_out, ni, cudaMemcpyDeviceToHost) != cudaSuccess)
        return MCGPU_ERR_CUDA;
    return MCGPU_OK;
}

extern "C" MCGPU_API void mcgpu_biome20_ctx_destroy(void* handle)
{
    McGpuBiome20Context* ctx = (McGpuBiome20Context*)handle;
    if (!ctx)
        return;
    if (ctx->d_out) cudaFree(ctx->d_out);
    if (ctx->d_z) cudaFree(ctx->d_z);
    if (ctx->d_y) cudaFree(ctx->d_y);
    if (ctx->d_x) cudaFree(ctx->d_x);
    if (ctx->d_param) cudaFree(ctx->d_param);
    if (ctx->d_nodes) cudaFree(ctx->d_nodes);
    if (ctx->d_state) cudaFree(ctx->d_state);
    free(ctx);
}

struct McGpuTreeView {
    const uint64_t* nodes;
    const int32_t* param;
    size_t node_bytes;
    size_t param_bytes;
    int32_t len;
    int32_t family; // 0: 1.18/1.19.2 shape, 1: 1.19.4+ shape
};

static bool mcgpu_select_modern_tree(int32_t version_code, McGpuTreeView* v)
{
    if (!v || version_code < 1180)
        return false;

    if (version_code >= 2602) {
        v->nodes = btree262_nodes; v->param = &btree262_param[0][0];
        v->node_bytes = sizeof(btree262_nodes); v->param_bytes = sizeof(btree262_param);
        v->len = (int32_t)(sizeof(btree262_nodes)/sizeof(btree262_nodes[0])); v->family = 1;
    } else if (version_code >= 1215) {
        v->nodes = btree215_nodes; v->param = &btree215_param[0][0];
        v->node_bytes = sizeof(btree215_nodes); v->param_bytes = sizeof(btree215_param);
        v->len = (int32_t)(sizeof(btree215_nodes)/sizeof(btree215_nodes[0])); v->family = 1;
    } else if (version_code >= 1214) {
        v->nodes = btree21wd_nodes; v->param = &btree21wd_param[0][0];
        v->node_bytes = sizeof(btree21wd_nodes); v->param_bytes = sizeof(btree21wd_param);
        v->len = (int32_t)(sizeof(btree21wd_nodes)/sizeof(btree21wd_nodes[0])); v->family = 1;
    } else if (version_code >= 1206) {
        v->nodes = btree20_nodes; v->param = &btree20_param[0][0];
        v->node_bytes = sizeof(btree20_nodes); v->param_bytes = sizeof(btree20_param);
        v->len = (int32_t)(sizeof(btree20_nodes)/sizeof(btree20_nodes[0])); v->family = 1;
    } else if (version_code >= 1194) {
        v->nodes = btree19_nodes; v->param = &btree19_param[0][0];
        v->node_bytes = sizeof(btree19_nodes); v->param_bytes = sizeof(btree19_param);
        v->len = (int32_t)(sizeof(btree19_nodes)/sizeof(btree19_nodes[0])); v->family = 1;
    } else if (version_code >= 1192) {
        v->nodes = btree192_nodes; v->param = &btree192_param[0][0];
        v->node_bytes = sizeof(btree192_nodes); v->param_bytes = sizeof(btree192_param);
        v->len = (int32_t)(sizeof(btree192_nodes)/sizeof(btree192_nodes[0])); v->family = 0;
    } else {
        v->nodes = btree18_nodes; v->param = &btree18_param[0][0];
        v->node_bytes = sizeof(btree18_nodes); v->param_bytes = sizeof(btree18_param);
        v->len = (int32_t)(sizeof(btree18_nodes)/sizeof(btree18_nodes[0])); v->family = 0;
    }
    return true;
}

struct McGpuModernContext {
    ClimateState* d_state;
    uint64_t* d_nodes;
    int32_t* d_param;
    int32_t* d_x;
    int32_t* d_y;
    int32_t* d_z;
    int32_t* d_out;
    int32_t capacity;
    int32_t tree_len;
    int32_t tree_family;
    int32_t version_code;
    uint64_t world_seed;
};

extern "C" MCGPU_API void* mcgpu_modern_ctx_create(
    int32_t version_code, uint64_t world_seed, int32_t capacity)
{
    if (capacity <= 0)
        return nullptr;
    McGpuTreeView tv = {};
    if (!mcgpu_select_modern_tree(version_code, &tv))
        return nullptr;

    McGpuModernContext* ctx =
        (McGpuModernContext*)malloc(sizeof(McGpuModernContext));
    if (!ctx)
        return nullptr;
    memset(ctx, 0, sizeof(*ctx));
    ctx->capacity = capacity;
    ctx->tree_len = tv.len;
    ctx->tree_family = tv.family;
    ctx->version_code = version_code;
    ctx->world_seed = world_seed;

    const size_t ni = (size_t)capacity * sizeof(int32_t);
    if (cudaMalloc(&ctx->d_state, sizeof(ClimateState)) != cudaSuccess ||
        cudaMalloc(&ctx->d_nodes, tv.node_bytes) != cudaSuccess ||
        cudaMalloc(&ctx->d_param, tv.param_bytes) != cudaSuccess ||
        cudaMalloc(&ctx->d_x, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_y, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_z, ni) != cudaSuccess ||
        cudaMalloc(&ctx->d_out, ni) != cudaSuccess) {
        if (ctx->d_out) cudaFree(ctx->d_out);
        if (ctx->d_z) cudaFree(ctx->d_z);
        if (ctx->d_y) cudaFree(ctx->d_y);
        if (ctx->d_x) cudaFree(ctx->d_x);
        if (ctx->d_param) cudaFree(ctx->d_param);
        if (ctx->d_nodes) cudaFree(ctx->d_nodes);
        if (ctx->d_state) cudaFree(ctx->d_state);
        free(ctx); return nullptr;
    }

    if (cudaMemcpy(ctx->d_nodes, tv.nodes, tv.node_bytes, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_param, tv.param, tv.param_bytes, cudaMemcpyHostToDevice) != cudaSuccess) {
        cudaFree(ctx->d_out); cudaFree(ctx->d_z); cudaFree(ctx->d_y);
        cudaFree(ctx->d_x); cudaFree(ctx->d_param); cudaFree(ctx->d_nodes);
        cudaFree(ctx->d_state); free(ctx); return nullptr;
    }

    climate_init_kernel<<<1, 1>>>(world_seed, ctx->d_state);
    if (cudaGetLastError() != cudaSuccess || cudaDeviceSynchronize() != cudaSuccess) {
        cudaFree(ctx->d_out); cudaFree(ctx->d_z); cudaFree(ctx->d_y);
        cudaFree(ctx->d_x); cudaFree(ctx->d_param); cudaFree(ctx->d_nodes);
        cudaFree(ctx->d_state); free(ctx); return nullptr;
    }
    return ctx;
}

extern "C" MCGPU_API int mcgpu_modern_ctx_query(
    void* handle,
    const int32_t* xs,
    const int32_t* ys,
    const int32_t* zs,
    int32_t count,
    int32_t* biome_out)
{
    McGpuModernContext* ctx = (McGpuModernContext*)handle;
    if (!ctx || !xs || !ys || !zs || !biome_out ||
        count <= 0 || count > ctx->capacity)
        return MCGPU_ERR_ARG;

    const size_t ni = (size_t)count * sizeof(int32_t);
    if (cudaMemcpy(ctx->d_x, xs, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_y, ys, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_z, zs, ni, cudaMemcpyHostToDevice) != cudaSuccess)
        return MCGPU_ERR_CUDA;

    constexpr int TPB = 256;
    const int blocks = (count + TPB - 1) / TPB;
    biome_modern_i32_kernel<<<blocks, TPB>>>(
        ctx->d_state, ctx->d_nodes, ctx->d_param,
        ctx->tree_len, ctx->tree_family,
        ctx->d_x, ctx->d_y, ctx->d_z, count, ctx->d_out);
    if (cudaGetLastError() != cudaSuccess ||
        cudaDeviceSynchronize() != cudaSuccess ||
        cudaMemcpy(biome_out, ctx->d_out, ni, cudaMemcpyDeviceToHost) != cudaSuccess)
        return MCGPU_ERR_CUDA;
    return MCGPU_OK;
}

extern "C" MCGPU_API int mcgpu_modern_ctx_filter_candidates(
    void* handle,
    const int32_t* center_chunk_x,
    const int32_t* center_chunk_z,
    int32_t count,
    int32_t flags,
    int32_t* mask_out)
{
    McGpuModernContext* ctx = (McGpuModernContext*)handle;
    if (!ctx || !center_chunk_x || !center_chunk_z || !mask_out ||
        count <= 0 || count > ctx->capacity || (flags & ~3) != 0 || flags == 0)
        return MCGPU_ERR_ARG;

    const size_t ni = (size_t)count * sizeof(int32_t);
    if (cudaMemcpy(ctx->d_x, center_chunk_x, ni, cudaMemcpyHostToDevice) != cudaSuccess ||
        cudaMemcpy(ctx->d_z, center_chunk_z, ni, cudaMemcpyHostToDevice) != cudaSuccess)
        return MCGPU_ERR_CUDA;

    biome_filter_candidates_kernel<<<count, 256>>>(
        ctx->d_state, ctx->d_nodes, ctx->d_param,
        ctx->tree_len, ctx->tree_family, ctx->world_seed,
        ctx->d_x, ctx->d_z, count, flags, ctx->d_out);
    if (cudaGetLastError() != cudaSuccess ||
        cudaDeviceSynchronize() != cudaSuccess ||
        cudaMemcpy(mask_out, ctx->d_out, ni, cudaMemcpyDeviceToHost) != cudaSuccess)
        return MCGPU_ERR_CUDA;
    return MCGPU_OK;
}

extern "C" MCGPU_API void mcgpu_modern_ctx_destroy(void* handle)
{
    McGpuModernContext* ctx = (McGpuModernContext*)handle;
    if (!ctx) return;
    if (ctx->d_out) cudaFree(ctx->d_out);
    if (ctx->d_z) cudaFree(ctx->d_z);
    if (ctx->d_y) cudaFree(ctx->d_y);
    if (ctx->d_x) cudaFree(ctx->d_x);
    if (ctx->d_param) cudaFree(ctx->d_param);
    if (ctx->d_nodes) cudaFree(ctx->d_nodes);
    if (ctx->d_state) cudaFree(ctx->d_state);
    free(ctx);
}

extern "C" MCGPU_API void* mcgpu_modern_ctx_create_ex(
    int32_t version_code, uint64_t world_seed,
    int32_t flags, int32_t capacity)
{
    if ((flags & ~1) != 0)
        return nullptr;
    void* handle = mcgpu_modern_ctx_create(
        version_code, world_seed, capacity);
    if (!handle)
        return nullptr;
    if (flags & 1) {
        McGpuModernContext* ctx = (McGpuModernContext*)handle;
        climate_init_mode_kernel<<<1, 1>>>(world_seed, 1, ctx->d_state);
        if (cudaGetLastError() != cudaSuccess ||
            cudaDeviceSynchronize() != cudaSuccess) {
            mcgpu_modern_ctx_destroy(handle);
            return nullptr;
        }
    }
    return handle;
}

extern "C" MCGPU_API int mcgpu_climate6_i32_fixed_seed_ex(
    uint64_t world_seed, int32_t large,
    const int32_t* xs, const int32_t* ys, const int32_t* zs,
    int32_t count, int32_t* out6)
{
    if (!xs || !ys || !zs || !out6 || count <= 0)
        return MCGPU_ERR_ARG;
    const size_t ni = (size_t)count * sizeof(int32_t);
    const size_t no = (size_t)count * 6 * sizeof(int32_t);
    ClimateState* d_state = nullptr;
    int32_t *d_x=nullptr,*d_y=nullptr,*d_z=nullptr,*d_out=nullptr;
    if (cudaMalloc(&d_state,sizeof(ClimateState))!=cudaSuccess ||
        cudaMalloc(&d_x,ni)!=cudaSuccess || cudaMalloc(&d_y,ni)!=cudaSuccess ||
        cudaMalloc(&d_z,ni)!=cudaSuccess || cudaMalloc(&d_out,no)!=cudaSuccess) {
        if(d_out)cudaFree(d_out); if(d_z)cudaFree(d_z); if(d_y)cudaFree(d_y);
        if(d_x)cudaFree(d_x); if(d_state)cudaFree(d_state); return MCGPU_ERR_ALLOC;
    }
    int rc=MCGPU_OK;
    if (cudaMemcpy(d_x,xs,ni,cudaMemcpyHostToDevice)!=cudaSuccess ||
        cudaMemcpy(d_y,ys,ni,cudaMemcpyHostToDevice)!=cudaSuccess ||
        cudaMemcpy(d_z,zs,ni,cudaMemcpyHostToDevice)!=cudaSuccess) rc=MCGPU_ERR_CUDA;
    else {
        climate_init_mode_kernel<<<1,1>>>(world_seed,large!=0,d_state);
        constexpr int TPB=256; const int blocks=(count+TPB-1)/TPB;
        climate6_i32_kernel<<<blocks,TPB>>>(d_state,d_x,d_y,d_z,count,d_out);
        if(cudaGetLastError()!=cudaSuccess || cudaDeviceSynchronize()!=cudaSuccess ||
           cudaMemcpy(out6,d_out,no,cudaMemcpyDeviceToHost)!=cudaSuccess) rc=MCGPU_ERR_CUDA;
    }
    cudaFree(d_out); cudaFree(d_z); cudaFree(d_y); cudaFree(d_x); cudaFree(d_state);
    return rc;
}
