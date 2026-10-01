# Slime Finder

Minecraft Java Edition 高性能史莱姆农场选址工具。

用于在大范围乃至整个 Java 世界中搜索史莱姆区块聚集区域，并进一步执行精确挂机范围统计、挂机 Y 扫描、最终候选排名与群系过滤。

- NVIDIA CUDA / AVX2
- 精确 Java 48-bit LCG
- 精确 221 区块挂机圆形统计
- Top-N 最终候选排名
- Deep Dark / Mushroom Fields 群系过滤
- Litematica 地板投影
- GPU shape / RNG 自动选择

> 史莱姆搜索核心完整保留 Java `nextInt(10)` rejection 语义，不使用概率近似或抽样换速度。

## 性能

测试设备：**RTX 3060 Laptop GPU**

测试条件：`threshold=60`，CUDA shape / RNG 自动选择。

| 搜索范围 | 候选中心 | 端到端时间 | 端到端吞吐 | 纯 GPU 平均 |
|---|---:|---:|---:|---:|
| 半径 500,000 | 1.000 T | **7.705 s** | **129.794 B/s** | **151.056 B/s** |
| Java 全图 | 14.063 T | **95.961 s** | **146.544 B/s** | **148.394 B/s** |

`B/s` 表示每秒检查十亿个候选中心。

该设备的全图持续扫描区间约为 **147 ～ 151 B/s**。实际速度会受 GPU 型号、功耗限制、温度和搜索条件影响。

## 主要功能

### 大范围搜索

支持指定中心 / 半径搜索，也支持 Java 世界边界范围的全图扫描。

GPU 主扫描完整处理搜索区域，不通过随机抽样缩小搜索空间。

### 精确挂机范围

候选首先使用 17×17 方形作为严格上界，最终结果使用精确圆形：

```text
17 × 17 = 289
圆外角落 = 68
精确圆形 = 221
```

因此方形只用于快速淘汰，不会代替最终圆形结果。

### 精准评分与 Y 扫描

可对高排名候选继续进行精准挂机点评分，并搜索更优的挂机 Y。

GPU 最终精准评分使用大批量原生计算，默认可一次处理最多 20,000 个候选，减少 Python / CUDA 往返。

末尾阶段会显示当前批次的：

```text
候选数量 / 批次耗时 / 候选每秒 / ETA
```

进度显示会进行节流刷新，避免高速批处理时产生过多 UI 更新，同时保留当前批次耗时、候选数量、候选吞吐与 ETA。

### 群系过滤

史莱姆区块 RNG 搜索本身不依赖 cubiomes。

群系过滤根据当前运行模式分开：

- **CPU 模式**：调用外置 `cubiomes.dll`
- **GPU 模式**：调用内置 CUDA 噪声后端

两条路径不会静默互相回退。

GPU 后端可执行 Deep Dark / Mushroom Fields 精确过滤，并根据当前 GPU 的 occupancy 调整候选批次。

当前群系版本范围：**Minecraft Java 1.19 ～ 26.2**。

### Litematica 投影

支持根据最终挂机点与筛选结果生成地板 / 结构辅助投影，用于游戏内定位和建造。

## 正确性

性能优化不通过近似 RNG、概率模型或抽样改变结果。

当前回归覆盖：

- 4 种 CUDA shape
- 3 条精确 RNG 路径
- 正 / 负 Java seed
- signed 64-bit 边界
- 精确圆形统计
- Y 精准评分
- 候选缓冲扩容
- Deep Dark / Mushroom Fields
- CPU / GPU 结果集合
- 投影坐标与 3D 范围

当前完整回归包括：

```text
ACCURACY_AUDIT_OK
CPU_GPU_MATRIX_OK
GPU_NOISE_MATRIX_EXACT 57344
GPU_NOISE_VERSION_FILTER_OK
FRONTEND_SMOKE_OK
```

## 算法源码

公开仓库只保留算法核心与必要的许可证 / 数据表，不包含 GUI 前端源码、测试日志、benchmark 记录或本地实验文件。

主要源码：

- `SlimeCoreGPU.cu` — CUDA 史莱姆搜索核心
- `SlimeCore.cpp` — AVX2 / OpenMP 史莱姆搜索核心
- `gpu_noise/MinecraftGPUNoise.cu` — CUDA Deep Dark / Mushroom Fields 噪声过滤核心
- `gpu_noise/mcgpu.h` — GPU 噪声接口 / 公共定义
- `gpu_noise/spline_generated.cuh` — GPU 世界生成 spline 数据
- `gpu_noise/tables/` — 群系 decision-tree 数据

## 第三方组件与许可证

CPU 群系模式使用外置 `cubiomes.dll`。该组件属于第三方项目，不打包进本仓库源码，也不作为本项目原创代码声明。

GPU 群系后端是本项目中的 CUDA 实现，但其中包含 / 改编了来自 cubiomes 的部分群系 decision-tree 数据及相关实现参考。凡来源于 cubiomes 或由其内容改编的部分，继续遵循 cubiomes 的 MIT 许可证与原版权声明；本项目不主张这些第三方部分的版权。

对应许可证保留在：

```text
gpu_noise/LICENSE.cubiomes
```

除上述第三方内容外，其余本项目自有的 CUDA 集成、调度与优化代码按本仓库所示源码发布。

---

# 为什么这么快？

## 1. Warp ballot 生成压缩史莱姆位图

CUDA Warp 的 32 个线程分别判断 32 个区块，再通过 `ballot` 直接压成一个 32-bit 位图。

后续窗口统计操作位图，而不是把每个区块结果存成普通整数 / bool 再逐项读取。

## 2. Warp-contiguous shared layout

同一 Warp 生成的多个 ballot 连续存放在 shared memory 中。

横向 17-bit 窗口需要相邻 word 时，同 Warp 内优先直接复用寄存器中的 ballot；只有跨 Warp 边界才读取 shared memory。

这减少了热路径中的共享内存往返，同时不增加 RNG 次数或 CTA barrier。

## 3. 17×17 rolling window

相邻候选中心的范围高度重叠。

当窗口横向移动一格时，大部分列完全复用，只更新离开窗口和新进入窗口的部分，而不是重新统计全部 289 格。

方形分数还是精确圆形的严格上界，因此低于阈值时可以立即淘汰。

## 4. 精确圆形只扣 68 个角落

精确圆形共有 221 格：

```text
circle = square_score - outside_corners
221 = 289 - 68
```

通过方形上界的候选不重新计算圆内 221 格，只从已有方形分数中扣除圆外角落。

角落分阶段计算，只要中途已经能严格证明候选无法达到要求，就提前结束。

## 5. 精确 Java RNG 多路径

CUDA 核心同时提供：

- Native 48-bit
- Limb32
- Truncated first-output

三条路径保持相同 Java RNG 语义，并保留极低概率 rejection fallback。

不同 NVIDIA 架构的整数运算代价不同，因此程序会根据当前 GPU 自动选择更合适的实现。

## 6. GPU 自动选择线程形状

当前搜索核心可在以下 CUDA shape 中自动选择：

```text
128×8
256×4
256×8
512×4
```

不会假设某一个线程形状在所有显卡上都最快。

## 7. 减少 PCIe 与 Python 搬运

低阈值下可能出现大量命中，但最终通常只需要 Top-N。

GPU 会完成精确统计，同时只物化真正有机会进入最终结果的候选，避免把大量坐标全部通过 PCIe 传回 Python 再排序。

搜索也采用分段处理，降低候选缓冲与主机端数据搬运压力。

## 8. 最终群系过滤也使用 GPU

Deep Dark / Mushroom Fields 的世界生成噪声和史莱姆 RNG 是两类完全不同的计算，因此使用独立 CUDA 后端。

GPU 群系 kernel 会先找出精确范围内真正需要检查的史莱姆区块，再把有效区块压紧成连续工作列表，让 CUDA block 集中处理实际需要的噪声查询。

这样可以减少 Warp 中大量无效 lane。

在 RTX 3060 Laptop GPU 的测试中，新的 compact 调度对不同过滤组合有明显收益；GPU 群系结果同时与 cubiomes 参考实现进行了交叉验证。

---

速度主要来自 **结果复用、位图压缩、滚动统计、严格上界提前淘汰、连续 GPU 工作调度和减少数据搬运**，而不是牺牲搜索准确性。
