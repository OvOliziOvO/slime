# SlimeFinder V1.2.1 · Linux x86-64

需要 Python 3.13。原生库在 Ubuntu 24.04 构建。使用 NVIDIA GPU 时需要支持当前显卡的驱动。

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-linux.txt
PYTHON=.venv/bin/python ./run_linux.sh
```

Ubuntu 上需要 `libgomp1`。如果 Qt 找不到 X11 的 xcb 插件依赖，可以安装 `libxcb-cursor0`。导出 Litematica 投影需另装 `litemapy`。CPU 群系筛选需要在启动脚本所在目录放置兼容的 `libcubiomes.so`。
