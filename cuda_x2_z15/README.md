# CUDA 双 X Phase / 十五 Z Band

这是 SlimeFinder 的 GTX 10 至 RTX 50 高阈值 GPU 搜索实现。Python 在构建时展开各组内核的 PTX 模板。NVIDIA 工具链将 PTX 编译为 `.cubin`，运行时由 CUDA 驱动加载。现有的 CUDA C++ 通用路径仍位于根目录的 `SlimeCoreGPU.cu`。

## 从哪里读

| 文件 | 负责的工作 |
|---|---|
| `app_scan.py` | 从界面进入专用路径的条件、CUDA 设备检查、暂停和取消检查。 |
| `xp_scan.py` | 把地图切成两条 X Phase 和多条 Z Band，启动位图扫描、候选队列、精确计数与重抽补算。 |
| `x_phase.py` | 坐标项、首抽奇偶分组、位图生成和 CUDA Driver API 封装。 |
| `bitmap_layout.py` | 每四行的交错布局，成对位图的向量读取。 |
| `quad_history.py`、`tensor_cold.py` | 打包更新滑动上界，按条件对矩形去角。 |
| `scalar_mma.py` | 为 GTX 10、GTX 16 和 RTX 20 将二值矩阵指令展开成 CUDA shuffle、AND 和 popcount，保留相同的位图片段布局。 |
| `xp_support.py` | 坐标项预计算、Java 完整重抽、221 格精算。 |
| `generate_slime_rare_tables.py`、`build_cubin.py` | 生成稀有重抽表，导出 PTX 或构建 CUDA 模块。 |

X 或 Z 跨 `131072` 区块会翻转 Java 首抽的奇偶位，两轴各跨一次时相消。相邻组共用低位运算，仍分别保留每个实际搜索位置。上界筛出的候选按 `dx² + dz² ≤ 68` 的 221 格精确计数。对首抽被拒后可能命中的区块，还会反查坐标并补算相关候选。

## 生成和验证

在仓库根目录运行。导出 PTX 只需 Python 和 NumPy。构建所有架构请使用 CUDA Toolkit 12.9 的 `ptxas`，同时支持 Pascal 和 Blackwell。

```text
python -m pip install numpy
python -m cuda_x2_z15.build_cubin --emit-ptx generated-ptx
python -m cuda_x2_z15.build_cubin --ptxas /path/to/ptxas
python -m cuda_x2_z15.build_cubin --ptxas /path/to/ptxas --arch 61 120
```

每个目标包含 31 个模块。缓存按目标架构和 PTX 的 SHA-256 索引，放在 `cuda_x2_z15/cubin/sm_<架构>/`。发布包已包含这批模块。缺少对应的模块时，运行时将兼容 PTX 交给 CUDA 驱动即时编译。

| GeForce 系列 | 预编译目标 | 位计数 |
| --- | --- | --- |
| GTX 10 | `sm_61` | CUDA shuffle、AND 和 popcount |
| GTX 16 / RTX 20 | `sm_75` | CUDA shuffle、AND 和 popcount |
| RTX 30 | `sm_86` | Tensor Core 二值矩阵指令 |
| RTX 40 | `sm_89` | Tensor Core 二值矩阵指令 |
| RTX 50 | `sm_120` | Tensor Core 二值矩阵指令 |

装有兼容 NVIDIA 驱动及受支持的显卡时可运行独立扫描测试。

```text
python -m cuda_x2_z15.xp_scan --radius 1875000 --x 0 --z 0 --lo 60 --repeat 3
```

Windows 和 Linux 界面的专用路径适用于大范围、阈值 55–60、开启精准挂机点、内半径为零、最高规模覆盖完整圆的搜索。界面版将搜索划分为有界的 GPU 批次，在每批之间检查暂停和取消。其他搜索参数沿用通用 CUDA / CPU 调度。

实时速度以每秒十亿个候选中心（B/s）计，进度按已经扫描的实际坐标范围更新。暂停时间不计入速度，队列扩容重试的计算时间计入速度，但同一坐标只计一次。搜索结束后界面显示扫描阶段平均速度，并在日志中记录采样范围。
