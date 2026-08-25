# Third-party and research references

本项目的 V34 CUDA 代码为独立实现。优化过程中参考了公开资料中的通用算法思想，没有直接复制下列仓库的源代码。V34 的安全方形上界、稀疏精确圆形复核、分 Slab 全局 Top-K 和设备运行时选型均针对本项目结果定义实现。

## Research references

- NVIDIA CUDA Programming Guide and Best Practices Guide：Warp vote、shared memory、同步、寄存器与 occupancy。
- `EDDxample/cuda-slime-finder`：公开的 ballot/popcount、热循环分阶段和基准记录，用于比较通用优化方向。该项目的任务是固定 16×16 方窗最佳值，与本项目的精确圆形全候选输出不同。
- `minelogy-dev/slime-calculator`：行前缀和与矩形滑窗方案，用于评估两阶段全局显存路线。
- `silversquirl/slimy`、`CITYWIDESIGN/SlimeRadar`：用于结果定义和不同 CPU/GPU 架构的交叉研究。

## Runtime dependencies

- PyQt6
- litemapy
- nbtlib
- NVIDIA CUDA Runtime（GPU 构建）
- Microsoft Visual C++ Runtime（Windows 原生核心）

`cubiomes.dll`、`libwinpthread-1.dll` 和其他第三方二进制不应在未核对各自许可证与再分发条款前加入 GitHub Release。本仓库的 `.gitignore` 默认排除这些二进制。
