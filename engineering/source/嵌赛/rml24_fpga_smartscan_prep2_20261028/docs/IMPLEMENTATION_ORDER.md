# FPGA智能扫频实施顺序

1. 行为仿真：Q15 Hann、FFT适配器、u54模平方、双缓冲和backpressure。
2. Procise独立综合：先window+FFT+power；保存资源、时序、warning，不改正式位流。
3. Python/RTL固定向量逐bin对照；缩放或指数必须可重建。
4. PS离线回放同一IQ，对比CPU与FPGA频谱、候选中心频率和带宽。
5. 实时旁路模式，只观测不控制NPU；失败自动使用软件频谱。
6. 接入UI多目标列表和拼接瀑布；回归现有定频/扫频准确率。
7. 最后才评估是否把噪声估计/CFAR迁入FPGA。

Pluto调谐和锁定仍可能主导总扫频时间，FFT加速不等于整轮扫描自动达到毫秒级。
