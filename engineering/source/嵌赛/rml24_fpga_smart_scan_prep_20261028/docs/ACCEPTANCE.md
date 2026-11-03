# 验收门

- Golden与RTL窗乘逐样本一致；FFT输出在冻结缩放口径下逐bin一致或在明确容差内。
- 极值模平方`2^51`不溢出，32帧累加使用u57。
- 随机backpressure、复位、跨帧、overflow、超时均fail-closed。
- 软件/FPGA同帧检测的目标数、中心频率和带宽满足冻结容差。
- 模型输入SHA保持不变；定频/扫频识别率不得低于冻结基线。
- 测得CPU占用、频谱处理延迟、吞吐、LUT/DSP/BRAM、WNS/TNS。
- 保留旧位流与software/auto回退；新候选通过前不得替换自启动。
