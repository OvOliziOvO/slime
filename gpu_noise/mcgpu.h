#pragma once
#include <stdint.h>

#ifdef _WIN32
#define MCGPU_API __declspec(dllexport)
#else
#define MCGPU_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum {
    MCGPU_OK = 0,
    MCGPU_ERR_ARG = -1,
    MCGPU_ERR_CUDA = -2,
    MCGPU_ERR_ALLOC = -3
};

MCGPU_API int mcgpu_api_version(void);
MCGPU_API const char* mcgpu_build_name(void);

// Modern Minecraft Xoroshiro128++ primitive.
// For each input seed, xSetSeed-compatible state is created and "steps"
// consecutive xNextLong values are written to out[i*steps + j].
MCGPU_API int mcgpu_xoroshiro_nextlong_batch(
    const uint64_t* seeds,
    int32_t count,
    int32_t steps,
    uint64_t* out);

// Correctness-stage primitive for modern xPerlinInit + samplePerlin.
// One seed and one coordinate triple per query.
MCGPU_API int mcgpu_xperlin_sample_batch(
    const uint64_t* seeds,
    const double* xs,
    const double* ys,
    const double* zs,
    int32_t count,
    double* out);

// Production-shaped path: one world/noise seed, many coordinates.
// The permutation/noise state is initialized once on the GPU and reused by
// the entire query batch.
MCGPU_API int mcgpu_xperlin_sample_fixed_seed(
    uint64_t seed,
    const double* xs,
    const double* ys,
    const double* zs,
    int32_t count,
    double* out);

#ifdef __cplusplus
}
#endif
