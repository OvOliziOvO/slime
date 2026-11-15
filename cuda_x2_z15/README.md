# CUDA 双 X Phase / 十五 Z Band

这是 SlimeFinder 的 SM 8.6 高阈值 GPU 搜索实现。Python 在构建时展开各组内核的 PTX 模板。NVIDIA 工具链将 PTX 编译为 `.cubin`，运行时由 CUDA 驱动加载。现有的 CUDA C++ 通用路径仍位于根目录的 `SlimeCoreGPU.cu`。

## 从哪里读

| 文件 | 负责的工作 |
|---|---|
| `app_scan.py` | 从界面进入专用路径的条件、CUDA 设备检查、暂停和取消检查。 |
| `xp_scan.py` | 把地图切成两条 X Phase 和多条 Z Band，启动位图扫描、候选队列、精确计数与重抽补算。 |
| `x_phase.py` | 坐标项、首抽奇偶分组、位图生成和 CUDA Driver API 封装。 |
| `bitmap_layout.py` | 每四行的交错布局，成对位图的向量读取。 |
| `quad_history.py`、`tensor_cold.py` | 打包更新滑动上界，按条件对矩形去角。 |
| `xp_support.py` | 坐标项预计算、Java 完整重抽、221 格精算。 |
| `generate_slime_rare_tables.py`、`build_cubin.py` | 生成稀有重抽表，导出 PTX 或构建 CUDA 模块。 |

X 或 Z 跨 `131072` 区块会翻转 Java 首抽的奇偶位，两轴各跨一次时相消。相邻组共用低位运算，仍分别保留每个实际搜索位置。上界筛出的候选按 `dx² + dz² ≤ 68` 的 221 格精确计数。对首抽被拒后可能命中的区块，还会反查坐标并补算相关候选。

## 生成和验证

在仓库根目录运行。导出 PTX 只需 Python 和 NumPy。构建 `.cubin` 时可使用 CUDA Toolkit 的 `ptxas`。在 Linux 上还支持用 NVIDIA 驱动提供的 PTX 编译器构建。

```text
python -m pip install numpy
python -m cuda_x2_z15.build_cubin --emit-ptx generated-ptx
python -m cuda_x2_z15.build_cubin --ptxas /path/to/ptxas
```

生成器使用 PTX 的 SHA-256 作为每个 `.cubin` 的缓存键。默认生成 31 个 SM 8.6 模块。编译后的缓存位于 `cuda_x2_z15/cubin/`。Windows 源码运行时如果缺少缓存，会把 PTX 交给已安装的 NVIDIA 驱动加载。

装有兼容 NVIDIA 驱动和 RTX 3060 等 SM 8.6 显卡时可运行独立扫描测试。

```text
python -m cuda_x2_z15.xp_scan --radius 1875000 --x 0 --z 0 --lo 60 --repeat 3
```

Windows 界面的专用路径适用于大范围、阈值 55–60、开启精准挂机点、内半径为零、最高规模覆盖完整圆的搜索。界面版将搜索划分为有界的 GPU 批次，在每批之间检查暂停和取消。其他参数或显卡沿用 V1.1 的通用 CUDA / CPU 调度。
