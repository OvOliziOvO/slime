# Contributing

## 正确性红线

任何性能优化都必须保持 Minecraft Java Edition 的史莱姆区块判定和圆形窗口结果逐位一致。提交前至少完成：

1. 用固定测试向量、CPU 精确路径及 Native/Limb32/Truncated 比较多个正负种子。
2. 覆盖非完整 Tile、内圈过滤和分数上下限。
3. 比较候选总数以及 `(score, center_x, center_z)` 集合。
4. 保留 `java.util.Random.nextInt(10)` 的 rejection 路径。

## 性能报告

- 使用交错顺序测试旧版和新版，避免 GPU Boost 与温度偏差。
- 报告中位数、最好值、半径、阈值、GPU 型号和 Compute Capability。
- 同时报告 ptxas registers、spill 和 shared memory。
- 不使用不同工作量之间的吞吐数字直接比较。

## 代码来源

请提交原创实现。可以引用论文、硬件文档和公开算法思想，但不得从许可证不兼容或来源不明的仓库复制代码。若实现受到外部资料启发，请在提交说明或 `THIRD_PARTY.md` 中注明资料链接和借鉴的概念。
