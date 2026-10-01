#pragma once

__device__ __forceinline__ double spline_lerp_d(double t, double a, double b)
{ return a + t * (b - a); }

__device__ __forceinline__ float spline_0(const float* v);
__device__ __forceinline__ float spline_1(const float* v);
__device__ __forceinline__ float spline_2(const float* v);
__device__ __forceinline__ float spline_3(const float* v);
__device__ __forceinline__ float spline_4(const float* v);
__device__ __forceinline__ float spline_5(const float* v);
__device__ __forceinline__ float spline_6(const float* v);
__device__ __forceinline__ float spline_7(const float* v);
__device__ __forceinline__ float spline_8(const float* v);
__device__ __forceinline__ float spline_9(const float* v);
__device__ __forceinline__ float spline_10(const float* v);
__device__ __forceinline__ float spline_11(const float* v);
__device__ __forceinline__ float spline_12(const float* v);
__device__ __forceinline__ float spline_13(const float* v);
__device__ __forceinline__ float spline_14(const float* v);
__device__ __forceinline__ float spline_15(const float* v);
__device__ __forceinline__ float spline_16(const float* v);
__device__ __forceinline__ float spline_17(const float* v);
__device__ __forceinline__ float spline_18(const float* v);
__device__ __forceinline__ float spline_19(const float* v);
__device__ __forceinline__ float spline_20(const float* v);
__device__ __forceinline__ float spline_21(const float* v);
__device__ __forceinline__ float spline_22(const float* v);
__device__ __forceinline__ float spline_23(const float* v);
__device__ __forceinline__ float spline_24(const float* v);
__device__ __forceinline__ float spline_25(const float* v);
__device__ __forceinline__ float spline_26(const float* v);
__device__ __forceinline__ float spline_27(const float* v);
__device__ __forceinline__ float spline_28(const float* v);
__device__ __forceinline__ float spline_29(const float* v);
__device__ __forceinline__ float spline_30(const float* v);
__device__ __forceinline__ float spline_31(const float* v);
__device__ __forceinline__ float spline_32(const float* v);
__device__ __forceinline__ float spline_33(const float* v);
__device__ __forceinline__ float spline_34(const float* v);
__device__ __forceinline__ float spline_35(const float* v);
__device__ __forceinline__ float spline_36(const float* v);
__device__ __forceinline__ float spline_37(const float* v);
__device__ __forceinline__ float spline_38(const float* v);
__device__ __forceinline__ float spline_39(const float* v);
__device__ __forceinline__ float spline_40(const float* v);

__device__ __forceinline__ float spline_0(const float* v)
{
    const float f = v[0];
    if (f <= -1.10000002f) {
        const float n = 0.0439999998f;
        return n + 0.0f * (f - -1.10000002f);
    }
    if (f <= -1.01999998f) {
        const float g = -1.10000002f;
        const float h = -1.01999998f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0439999998f;
        const float o = -0.222200006f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.50999999f) {
        const float g = -1.01999998f;
        const float h = -0.50999999f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.222200006f;
        const float o = -0.222200006f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.439999998f) {
        const float g = -0.50999999f;
        const float h = -0.439999998f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.222200006f;
        const float o = -0.119999997f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.180000007f) {
        const float g = -0.439999998f;
        const float h = -0.180000007f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.119999997f;
        const float o = -0.119999997f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.159999996f) {
        const float g = -0.180000007f;
        const float h = -0.159999996f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.119999997f;
        const float o = spline_10(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.150000006f) {
        const float g = -0.159999996f;
        const float h = -0.150000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_10(v);
        const float o = spline_10(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.100000001f) {
        const float g = -0.150000006f;
        const float h = -0.100000001f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_10(v);
        const float o = spline_20(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.25f) {
        const float g = -0.100000001f;
        const float h = 0.25f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_20(v);
        const float o = spline_30(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.25f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_30(v);
        const float o = spline_40(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = spline_40(v);
    return n + 0.0f * (f - 1.0f);
}

__device__ __forceinline__ float spline_1(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0888018608f;
        return n + 0.389400959f * (f - -1.0f);
    }
    if (f <= 1.0f) {
        const float g = -1.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.389400959f;
        const float m = 0.389400959f;
        const float n = -0.0888018608f;
        const float o = 0.690000057f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.690000057f;
    return n + 0.389400959f * (f - 1.0f);
}

__device__ __forceinline__ float spline_2(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.115760356f;
        return n + 0.377880216f * (f - -1.0f);
    }
    if (f <= 1.0f) {
        const float g = -1.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.377880216f;
        const float m = 0.377880216f;
        const float n = -0.115760356f;
        const float o = 0.640000105f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.640000105f;
    return n + 0.377880216f * (f - 1.0f);
}

__device__ __forceinline__ float spline_3(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.222200006f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.75f) {
        const float g = -1.0f;
        const float h = -0.75f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.222200006f;
        const float o = -0.222200006f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.649999976f) {
        const float g = -0.75f;
        const float h = -0.649999976f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.222200006f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.595454693f) {
        const float g = -0.649999976f;
        const float h = 0.595454693f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 2.98023224e-08f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.605454683f) {
        const float g = 0.595454693f;
        const float h = 0.605454683f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.253456295f;
        const float n = 2.98023224e-08f;
        const float o = 2.98023224e-08f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.605454683f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.253456295f;
        const float m = 0.253456295f;
        const float n = 2.98023224e-08f;
        const float o = 0.100000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000024f;
    return n + 0.253456295f * (f - 1.0f);
}

__device__ __forceinline__ float spline_4(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.300000012f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.300000012f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0500000007f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0500000007f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.00700000115f;
        const float n = 0.0500000007f;
        const float o = 0.0600000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0600000024f;
    return n + 0.00700000115f * (f - 1.0f);
}

__device__ __forceinline__ float spline_5(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.150000006f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.150000006f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.100000001f;
        const float n = 0.0f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.100000001f;
        const float m = 0.00700000115f;
        const float n = 0.0500000007f;
        const float o = 0.0600000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0600000024f;
    return n + 0.00700000115f * (f - 1.0f);
}

__device__ __forceinline__ float spline_6(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.150000006f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.150000006f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0f;
    return n + 0.0f * (f - 1.0f);
}

__device__ __forceinline__ float spline_7(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.150000006f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.150000006f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0f;
    return n + 0.0f * (f - 1.0f);
}

__device__ __forceinline__ float spline_8(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.150000006f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.150000006f;
        const float o = spline_6(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_6(v);
        const float o = 0.0700000003f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0700000003f;
    return n + 0.0f * (f - 0.0f);
}

__device__ __forceinline__ float spline_9(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0199999996f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.0199999996f;
        const float o = -0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.0299999993f;
        const float o = -0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0599999987f;
        const float n = -0.0299999993f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0599999987f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0f;
    return n + 0.0f * (f - 1.0f);
}

__device__ __forceinline__ float spline_10(const float* v)
{
    const float f = v[1];
    if (f <= -0.850000024f) {
        const float n = spline_1(v);
        return n + 0.0f * (f - -0.850000024f);
    }
    if (f <= -0.699999988f) {
        const float g = -0.850000024f;
        const float h = -0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_1(v);
        const float o = spline_2(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.400000006f) {
        const float g = -0.699999988f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_2(v);
        const float o = spline_3(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.349999994f) {
        const float g = -0.400000006f;
        const float h = -0.349999994f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_3(v);
        const float o = spline_4(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.100000001f) {
        const float g = -0.349999994f;
        const float h = -0.100000001f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_4(v);
        const float o = spline_5(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.200000003f) {
        const float g = -0.100000001f;
        const float h = 0.200000003f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_5(v);
        const float o = spline_6(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.699999988f) {
        const float g = 0.200000003f;
        const float h = 0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_6(v);
        const float o = spline_9(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = spline_9(v);
    return n + 0.0f * (f - 0.699999988f);
}

__device__ __forceinline__ float spline_11(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0888018608f;
        return n + 0.389400959f * (f - -1.0f);
    }
    if (f <= 1.0f) {
        const float g = -1.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.389400959f;
        const float m = 0.389400959f;
        const float n = -0.0888018608f;
        const float o = 0.690000057f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.690000057f;
    return n + 0.389400959f * (f - 1.0f);
}

__device__ __forceinline__ float spline_12(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.115760356f;
        return n + 0.377880216f * (f - -1.0f);
    }
    if (f <= 1.0f) {
        const float g = -1.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.377880216f;
        const float m = 0.377880216f;
        const float n = -0.115760356f;
        const float o = 0.640000105f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.640000105f;
    return n + 0.377880216f * (f - 1.0f);
}

__device__ __forceinline__ float spline_13(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.222200006f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.75f) {
        const float g = -1.0f;
        const float h = -0.75f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.222200006f;
        const float o = -0.222200006f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.649999976f) {
        const float g = -0.75f;
        const float h = -0.649999976f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.222200006f;
        const float o = 0.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.595454693f) {
        const float g = -0.649999976f;
        const float h = 0.595454693f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0f;
        const float o = 2.98023224e-08f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.605454683f) {
        const float g = 0.595454693f;
        const float h = 0.605454683f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.253456295f;
        const float n = 2.98023224e-08f;
        const float o = 2.98023224e-08f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.605454683f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.253456295f;
        const float m = 0.253456295f;
        const float n = 2.98023224e-08f;
        const float o = 0.100000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000024f;
    return n + 0.253456295f * (f - 1.0f);
}

__device__ __forceinline__ float spline_14(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.25f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.25f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0500000007f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.0500000007f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.00700000115f;
        const float n = 0.0500000007f;
        const float o = 0.0600000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0600000024f;
    return n + 0.00700000115f * (f - 1.0f);
}

__device__ __forceinline__ float spline_15(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.00999999978f;
        const float n = -0.100000001f;
        const float o = 0.00100000005f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.00999999978f;
        const float m = 0.00999999978f;
        const float n = 0.00100000005f;
        const float o = 0.00300000003f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.00999999978f;
        const float m = 0.0940000042f;
        const float n = 0.00300000003f;
        const float o = 0.0500000007f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0940000042f;
        const float m = 0.00700000115f;
        const float n = 0.0500000007f;
        const float o = 0.0600000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.0600000024f;
    return n + 0.00700000115f * (f - 1.0f);
}

__device__ __forceinline__ float spline_16(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.100000001f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.00999999978f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0399999991f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0399999991f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_17(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.100000001f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.00999999978f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0399999991f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0399999991f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_18(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.100000001f;
        const float o = spline_16(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_16(v);
        const float o = 0.170000002f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.170000002f;
    return n + 0.0f * (f - 0.0f);
}

__device__ __forceinline__ float spline_19(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0199999996f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.0199999996f;
        const float o = -0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.0299999993f;
        const float o = -0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.119999997f;
        const float n = -0.0299999993f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.119999997f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_20(const float* v)
{
    const float f = v[1];
    if (f <= -0.850000024f) {
        const float n = spline_11(v);
        return n + 0.0f * (f - -0.850000024f);
    }
    if (f <= -0.699999988f) {
        const float g = -0.850000024f;
        const float h = -0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_11(v);
        const float o = spline_12(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.400000006f) {
        const float g = -0.699999988f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_12(v);
        const float o = spline_13(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.349999994f) {
        const float g = -0.400000006f;
        const float h = -0.349999994f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_13(v);
        const float o = spline_14(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.100000001f) {
        const float g = -0.349999994f;
        const float h = -0.100000001f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_14(v);
        const float o = spline_15(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.200000003f) {
        const float g = -0.100000001f;
        const float h = 0.200000003f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_15(v);
        const float o = spline_16(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.699999988f) {
        const float g = 0.200000003f;
        const float h = 0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_16(v);
        const float o = spline_19(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = spline_19(v);
    return n + 0.0f * (f - 0.699999988f);
}

__device__ __forceinline__ float spline_21(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = 0.202350214f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= 0.0f) {
        const float g = -1.0f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.51382488f;
        const float n = 0.202350214f;
        const float o = 0.716175139f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.51382488f;
        const float m = 0.51382488f;
        const float n = 0.716175139f;
        const float o = 1.23000002f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 1.23000002f;
    return n + 0.51382488f * (f - 1.0f);
}

__device__ __forceinline__ float spline_22(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = 0.200000003f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= 0.0f) {
        const float g = -1.0f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.433179736f;
        const float n = 0.200000003f;
        const float o = 0.446820259f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.433179736f;
        const float m = 0.433179736f;
        const float n = 0.446820259f;
        const float o = 0.879999995f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.879999995f;
    return n + 0.433179736f * (f - 1.0f);
}

__device__ __forceinline__ float spline_23(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = 0.200000003f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= 0.0f) {
        const float g = -1.0f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.391705096f;
        const float n = 0.200000003f;
        const float o = 0.308294952f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.391705096f;
        const float m = 0.391705096f;
        const float n = 0.308294952f;
        const float o = 0.700000048f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.700000048f;
    return n + 0.391705096f * (f - 1.0f);
}

__device__ __forceinline__ float spline_24(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.25f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.25f;
        const float o = 0.349999994f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.349999994f;
        const float o = 0.349999994f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.349999994f;
        const float o = 0.349999994f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0490000136f;
        const float n = 0.349999994f;
        const float o = 0.420000017f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.420000017f;
    return n + 0.0490000136f * (f - 1.0f);
}

__device__ __forceinline__ float spline_25(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0700000003f;
        const float n = -0.100000001f;
        const float o = 0.00699999975f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0700000003f;
        const float m = 0.0700000003f;
        const float n = 0.00699999975f;
        const float o = 0.0209999997f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0700000003f;
        const float m = 0.657999992f;
        const float n = 0.0209999997f;
        const float o = 0.349999994f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.657999992f;
        const float m = 0.0490000136f;
        const float n = 0.349999994f;
        const float o = 0.420000017f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.420000017f;
    return n + 0.0490000136f * (f - 1.0f);
}

__device__ __forceinline__ float spline_26(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.100000001f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.00999999978f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0399999991f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0399999991f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_27(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.100000001f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.00999999978f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0399999991f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0399999991f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_28(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.100000001f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.100000001f;
        const float o = spline_26(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_26(v);
        const float o = 0.170000002f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.170000002f;
    return n + 0.0f * (f - 0.0f);
}

__device__ __forceinline__ float spline_29(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0199999996f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.0199999996f;
        const float o = -0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.0299999993f;
        const float o = -0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.119999997f;
        const float n = -0.0299999993f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.119999997f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_30(const float* v)
{
    const float f = v[1];
    if (f <= -0.850000024f) {
        const float n = spline_21(v);
        return n + 0.0f * (f - -0.850000024f);
    }
    if (f <= -0.699999988f) {
        const float g = -0.850000024f;
        const float h = -0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_21(v);
        const float o = spline_22(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.400000006f) {
        const float g = -0.699999988f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_22(v);
        const float o = spline_23(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.349999994f) {
        const float g = -0.400000006f;
        const float h = -0.349999994f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_23(v);
        const float o = spline_24(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.100000001f) {
        const float g = -0.349999994f;
        const float h = -0.100000001f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_24(v);
        const float o = spline_25(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.200000003f) {
        const float g = -0.100000001f;
        const float h = 0.200000003f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_25(v);
        const float o = spline_26(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.200000003f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_26(v);
        const float o = spline_27(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.449999988f) {
        const float g = 0.400000006f;
        const float h = 0.449999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_27(v);
        const float o = spline_28(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.550000012f) {
        const float g = 0.449999988f;
        const float h = 0.550000012f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_28(v);
        const float o = spline_28(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.579999983f) {
        const float g = 0.550000012f;
        const float h = 0.579999983f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_28(v);
        const float o = spline_27(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.699999988f) {
        const float g = 0.579999983f;
        const float h = 0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_27(v);
        const float o = spline_29(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = spline_29(v);
    return n + 0.0f * (f - 0.699999988f);
}

__device__ __forceinline__ float spline_31(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = 0.347926259f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= 0.0f) {
        const float g = -1.0f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.57603687f;
        const float n = 0.347926259f;
        const float o = 0.92396313f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.57603687f;
        const float m = 0.57603687f;
        const float n = 0.92396313f;
        const float o = 1.5f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 1.5f;
    return n + 0.57603687f * (f - 1.0f);
}

__device__ __forceinline__ float spline_32(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = 0.200000003f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= 0.0f) {
        const float g = -1.0f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.460829496f;
        const float n = 0.200000003f;
        const float o = 0.539170504f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.460829496f;
        const float m = 0.460829496f;
        const float n = 0.539170504f;
        const float o = 1.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 1.0f;
    return n + 0.460829496f * (f - 1.0f);
}

__device__ __forceinline__ float spline_33(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = 0.200000003f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= 0.0f) {
        const float g = -1.0f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.460829496f;
        const float n = 0.200000003f;
        const float o = 0.539170504f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.0f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.460829496f;
        const float m = 0.460829496f;
        const float n = 0.539170504f;
        const float o = 1.0f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 1.0f;
    return n + 0.460829496f * (f - 1.0f);
}

__device__ __forceinline__ float spline_34(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.200000003f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.200000003f;
        const float o = 0.5f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.5f;
        const float o = 0.5f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.5f;
        const float o = 0.5f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0700000152f;
        const float n = 0.5f;
        const float o = 0.600000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.600000024f;
    return n + 0.0700000152f * (f - 1.0f);
}

__device__ __forceinline__ float spline_35(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0500000007f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.099999994f;
        const float n = -0.0500000007f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.099999994f;
        const float m = 0.099999994f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.099999994f;
        const float m = 0.939999998f;
        const float n = 0.0299999993f;
        const float o = 0.5f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.939999998f;
        const float m = 0.0700000152f;
        const float n = 0.5f;
        const float o = 0.600000024f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.600000024f;
    return n + 0.0700000152f * (f - 1.0f);
}

__device__ __forceinline__ float spline_36(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0500000007f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.0500000007f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.00999999978f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0399999991f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0399999991f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_37(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0500000007f;
        return n + 0.5f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.5f;
        const float m = 0.0f;
        const float n = -0.0500000007f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.00999999978f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0399999991f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0399999991f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_38(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0500000007f;
        return n + 0.0f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = -0.0500000007f;
        const float o = spline_36(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_36(v);
        const float o = 0.170000002f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.170000002f;
    return n + 0.0f * (f - 0.0f);
}

__device__ __forceinline__ float spline_39(const float* v)
{
    const float f = v[2];
    if (f <= -1.0f) {
        const float n = -0.0199999996f;
        return n + 0.0149999997f * (f - -1.0f);
    }
    if (f <= -0.400000006f) {
        const float g = -1.0f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0149999997f;
        const float m = 0.0f;
        const float n = -0.0199999996f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.0f) {
        const float g = -0.400000006f;
        const float h = 0.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = 0.00999999978f;
        const float o = 0.00999999978f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.0f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0399999991f;
        const float n = 0.00999999978f;
        const float o = 0.0299999993f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 1.0f) {
        const float g = 0.400000006f;
        const float h = 1.0f;
        const float k = (f - g) / (h - g);
        const float l = 0.0399999991f;
        const float m = 0.0489999987f;
        const float n = 0.0299999993f;
        const float o = 0.100000001f;
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = 0.100000001f;
    return n + 0.0489999987f * (f - 1.0f);
}

__device__ __forceinline__ float spline_40(const float* v)
{
    const float f = v[1];
    if (f <= -0.850000024f) {
        const float n = spline_31(v);
        return n + 0.0f * (f - -0.850000024f);
    }
    if (f <= -0.699999988f) {
        const float g = -0.850000024f;
        const float h = -0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_31(v);
        const float o = spline_32(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.400000006f) {
        const float g = -0.699999988f;
        const float h = -0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_32(v);
        const float o = spline_33(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.349999994f) {
        const float g = -0.400000006f;
        const float h = -0.349999994f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_33(v);
        const float o = spline_34(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= -0.100000001f) {
        const float g = -0.349999994f;
        const float h = -0.100000001f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_34(v);
        const float o = spline_35(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.200000003f) {
        const float g = -0.100000001f;
        const float h = 0.200000003f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_35(v);
        const float o = spline_36(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.400000006f) {
        const float g = 0.200000003f;
        const float h = 0.400000006f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_36(v);
        const float o = spline_37(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.449999988f) {
        const float g = 0.400000006f;
        const float h = 0.449999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_37(v);
        const float o = spline_38(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.550000012f) {
        const float g = 0.449999988f;
        const float h = 0.550000012f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_38(v);
        const float o = spline_38(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.579999983f) {
        const float g = 0.550000012f;
        const float h = 0.579999983f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_38(v);
        const float o = spline_37(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    if (f <= 0.699999988f) {
        const float g = 0.579999983f;
        const float h = 0.699999988f;
        const float k = (f - g) / (h - g);
        const float l = 0.0f;
        const float m = 0.0f;
        const float n = spline_37(v);
        const float o = spline_39(v);
        const float p = l * (h - g) - (o - n);
        const float q = -m * (h - g) + (o - n);
        const double a0 = spline_lerp_d((double)k, (double)n, (double)o);
        const float kk = k * (1.0f - k);
        const double b0 = spline_lerp_d((double)k, (double)p, (double)q);
        return (float)(a0 + (double)kk * b0);
    }
    const float n = spline_39(v);
    return n + 0.0f * (f - 0.699999988f);
}

__device__ __forceinline__ float mcgpu_depth_spline(const float* v)
{ return spline_0(v); }
