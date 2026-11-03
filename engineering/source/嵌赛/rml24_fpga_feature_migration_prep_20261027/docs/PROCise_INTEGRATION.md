# Procise 集成边界

目标器件以现有资料中的 `JFMQL30TAI676H` 为候选，但在工程内必须重新从板卡资料确认完整 part/package/speed grade。

首轮只加入 `qam_feature_pipeline.sv` 与 `frame_statistics.sv` 做 OOC/独立综合，检查：

- 所有 16×16 乘法和 32/33/42 位加法未被静默截断；
- 单时钟域、低有效复位语义正确；
- II=1，输出 backpressure 时 payload 稳定；
- 保存 utilization、关键路径、clock、warning、CDC/reset 报告。

不得把 Vivado/Xilinx 器件的结果当作 FMQL30TAI 资源或时序证据。PS→PL、DDR/DMA、cache coherency 和启动固化必须基于当前板 BSP/官方工程连接，不在电脑侧臆造端口。
