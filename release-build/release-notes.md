## 下载

- **Windows x64** · 便携 EXE，双击启动。
- **Linux x86-64** · 解压后按包内 README 配置 Python 3.13，再运行 `run_linux.sh`。
- **CUDA 源码** · 包含双 X Phase / 15 Z Band 搜索和多架构构建说明。

## GPU 兼容性

新版精确搜索覆盖 GTX 10、GTX 16、RTX 20、RTX 30、RTX 40 和 RTX 50。预编译目标为 `sm_61`、`sm_75`、`sm_86`、`sm_89` 和 `sm_120`。RTX 30 至 50 使用二值 Tensor Core 指令，GTX 10、GTX 16 和 RTX 20 使用 CUDA 位计数。在 RTX 3060 Laptop 上复核，两条路径在三组搜索的命中坐标和计数一致。

用 `SHA256SUMS.txt` 校验下载文件。Windows 可选的 CPU 群系组件与 V1.2 相同。
