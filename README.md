# Slime Finder V1

Minecraft Java Edition 史莱姆区块聚集搜索器。支持 CUDA / AVX2、精准挂机点与 Y 扫描、排名、历史记录和 Litematica 地板投影。

史莱姆搜索使用精确 Java LCG 与精确圆形统计，不使用概率近似。

## 下载

主程序：[Releases](https://github.com/OvOliziOvO/slime/releases/latest)

统一 EXE：`SlimeFinder_NVIDIA_10_50.exe`，覆盖 GTX 10 / RTX 20 / RTX 30 / RTX 40 / RTX 50 系。

## GPU 性能

测试设备：RTX 3060 Laptop GPU。

**GPU速度统计：全图：峰值 140.71 B/s | 最低 91.00 B/s | 平均 104.06 B/s**

`B/s` 表示每秒检查十亿个候选中心。

## V1 算法

- 32 行共享内存压缩位图，Warp ballot 直接生成史莱姆结果。
- 17×17 滚动方形计数作为严格上界。
- 精确圆形使用 `289 - 68 = 221`，只扣除圆外角落。
- 完整保留 Java `nextInt(10)` rejection 语义。
- Native / Limb32 / Truncated 三条精确 RNG 路径自动短测。
- 128×8 / 256×4 / 256×8 / 512×4 四种 CUDA 线程形状自动选择。
- GPU 负责大范围扫描与 Top-K，CPU/Python 负责后处理和可选世界生成检查。

调试环境变量：

```powershell
$env:SLIME_GPU_V1_SHAPE = "256x4"
$env:SLIME_GPU_V1_RNG = "native"
```

## 噪声 / 群系检查

史莱姆区块搜索本身不需要 `cubiomes.dll`。深谙之域、蘑菇岛等检查需要外置噪声组件。

| Minecraft 支持范围 | 下载 |
|---|---|
| 1.19 ～ 26.2 | [cubiomes_latest_26.2.zip](https://github.com/OvOliziOvO/slime/releases/latest/download/cubiomes_latest_26.2.zip) |

下载后解压，把 `cubiomes.dll` 放到 EXE 或 `SlimeFinder.py` 同目录。ZIP 内附 cubiomes 的 MIT License。当前新版 DLL 只依赖 Windows 系统库，不需要额外的 `libwinpthread-1.dll`。

### 为什么噪声检查比 GPU 搜索慢？

GPU 主扫描主要是整数 RNG、位图和 popcount；噪声检查则要在 CPU 上运行 Minecraft 世界生成与群系逻辑，并对候选周围多个 Y 和完整 quart 位置进行验证，所以单个候选的成本高很多。

当前流程会先完成 V1 精准排名，再从高到低做群系检查，凑够最终 Top-N 后立即停止。

## 正确性

当前回归覆盖 CPU/GPU 结果集合、三条 GPU RNG、Y 精准评分、候选缓冲、深谙/蘑菇岛过滤、投影坐标与保存/重载。

最近完整回归：

```text
ACCURACY_AUDIT_OK
CPU_GPU_MATRIX_OK
MUSHROOM_FAST_MISMATCH 0
DEEP_FAST_MISMATCH 0
BUFFER_INTEGRITY_OK
PROJECTION_ROUNDTRIP_OK
```

## 源码

- `SlimeCoreGPU.cu`：V1 CUDA 搜索核心。
- `SlimeCore.cpp`：AVX2/OpenMP CPU 核心。
- `SlimeFinder.py`：PyQt6 前端、排名、群系检查与投影。

从源码运行：

```powershell
python -m pip install -r requirements.txt
python .\SlimeFinder.py
```

`cubiomes.dll` 不打包进 Release EXE；其源码与许可归对应上游项目所有。

---

## 为什么这么快？

最直接的史莱姆密集区搜索会对每一个候选中心重新判断周围圆形范围内的 221 个区块。相邻两个中心的范围却几乎完全重叠，所以这种写法会把同一批 Java Random / LCG 判定重复计算很多次。

V1 的核心思路不是让一次 LCG 神奇地快几百倍，而是尽量让**每一个底层区块只计算一次，然后把结果复用给附近所有候选中心**。

### 1. 先生成压缩史莱姆位图

CUDA Warp 的 32 个线程分别判断 32 个区块是否为史莱姆区块，然后用 `ballot` 直接压成一个 32 位整数。后续窗口统计处理的是位图，而不是一大堆普通整数或布尔数组。

最近 32 行位图保存在 CUDA Block 的共享内存环中。相邻候选使用的大部分数据都已经在共享内存和寄存器里，因此不需要把整张地图写进显存后再反复读取。

### 2. 17×17 方形滚动，不重新数 289 格

圆形有效范围位于 17×17 方形之内。候选中心横向移动一格时，旧窗口和新窗口有 16 列完全重合，所以程序只更新离开的那一列和新进入的那一列。

这样可以快速得到 17×17 方形分数。因为圆形一定不可能比方形更多，所以如果方形分数都低于用户要求，该中心可以直接淘汰，而且不会漏掉任何正确结果。

### 3. 精确圆形只扣 68 个角落

17×17 方形共有 289 格，而程序定义的精确圆形共有 221 格，因此：

```text
圆形分数 = 289 格方形分数 - 68 格圆外角落分数
```

通过方形上界的候选不需要重新统计圆内 221 格，只需要从已经得到的方形分数中扣掉角落。角落还是分批计算的，只要中途已经可以证明最终结果不可能进入用户要求的范围，就提前结束。

### 4. Java RNG 仍然是精确语义

史莱姆区块判定保持 Java 48 位 LCG 与 `nextInt(10)` 的行为。常见路径做了整数化和不变量预计算，但极低概率出现的 rejection 分支没有删除。

V1 同时编译 Native 48 位、Limb32 和 Truncated 三条等价 RNG 路径。不同 NVIDIA 架构对整数运算的代价不同，所以大范围搜索时会在当前设备上短测并选择更快的一条，而不是硬编码“某一种永远最快”。

### 5. 不把海量候选全传回 CPU

低阈值搜索可能命中非常多的中心，但最终用户通常只需要 Top-N。GPU 会精确统计命中，同时只物化真正可能进入最终排名的候选，避免把几千万甚至更多坐标经过 PCIe 全部传给 Python 再排序。

地图还会按 Slab 分段处理。某一段候选过多时可以缩小分段或降低物化门槛后重新精确补扫，因此省掉的是无意义的数据传输和排序，不是省掉搜索区域。

### 6. 为什么 GPU 搜索能比噪声检查快很多？

史莱姆主扫描的大部分工作最终都变成规则的整数运算、位运算、`ballot` 和 `popcount`，非常适合 GPU 大规模并行。

深谙之域和蘑菇岛检查则不同：它们要在 CPU 上运行 Minecraft 世界生成的噪声和群系逻辑，还需要针对候选周围多个高度和完整 quart 位置进行验证。两者虽然都显示在同一个程序里，但计算性质完全不同，所以出现“GPU 主扫描几秒、群系检查反而更久”并不矛盾。

### 7. 快速路径没有牺牲结果准确性

- 方形阶段只是严格上界筛选。
- 圆形阶段使用 `square - corners` 的精确恒等关系。
- Java `nextInt(10)` rejection 仍然保留。
- CPU、GPU 三条 RNG、Y 精准评分和群系过滤都有交叉回归测试。

因此 V1 的速度主要来自**复用、压缩、滚动统计、提前淘汰和减少数据搬运**，而不是用抽样或近似换速度。
