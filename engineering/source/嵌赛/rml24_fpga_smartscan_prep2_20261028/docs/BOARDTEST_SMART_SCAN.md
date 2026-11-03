# FPGA 辅助智能扫频：目标构建与板测顺序

## 0. 不变项

现有 two-DC、重复平均、冻结 NPU、定频/扫频参数、五页 UI 和当前正式位流均不修改。
新功能必须支持 `software`、`fpga`、`auto` 三种后端；默认仍是 `software`。

## 1. Procise FFT 核冻结

使用已冻结的 Vivado 2018.3 + FMSH ip_patch 5.3.1.8 XFFT 9.1 生成物迁移到目标
Procise 工程，必须复核工具版本、IP 版本和完整配置：

- 1024 点复数前向 FFT；输入 I/Q 各 signed 16 bit；
- 自然顺序输出并提供 0..1023 bin index；
- 无缩放，输出 I/Q 各 signed 27 bit；AXI 数据宽 64 bit；不得静默截断；
- 流式 ready/valid/last；连续帧间不得混帧；
- 明确 rounding、overflow 和 block exponent 配置。

把生成核连接到 `procise_fft_axis_boundary.sv`，再连接
`fft_psd_stream_writer.sv`。后者输出 fftshift 顺序的 1024 个 u54 功率值。

## 2. 独立仿真与综合门

1. 运行 `tb_smart_scan_boundary.sv`。
2. 运行 `tb_fft_psd_stream_writer.sv`，必须 2048/2048 写入、跨两帧 bank 正确、
   随机 backpressure 下无丢 bin、`protocol_error=0`。
3. 用厂商 FFT 的仿真模型回放四个 `vectors/*.iq.i16`。
4. 后级 u54 写入必须与厂商模型的 I/Q 输出逐 bin 精确一致；FFT 本身与 NumPy
   Golden 比较峰值 bin、幅度误差和溢出，不在未知 rounding 下伪称 bit-exact。
5. Procise 完成 synth/P&R/STA，保存资源、关键路径、warning、时钟和功耗报告。

任何一步失败均不得生成上板候选。

## 3. PS/PL 接口

- 两个 1024×64 对齐缓冲区保存 u54 PSD（高 10 bit 必须为零）。
- PL 仅在完整帧写完后翻转 bank 并递增 frame_id。
- PS 读取前检查版本、frame_id、`protocol_error`、overflow 和 bank ownership。
- 超时、版本不符、帧号不连续或任一错误时，`auto` 后端必须切回软件 FFT，且 UI
  显示真实后端，不得继续展示旧 FPGA 数据。

## 4. 板上 A/B

对同一保存 IQ 依次运行软件和 FPGA 后端：零输入、单音、双音、边界频点、随机噪声、
跨帧和连续 1000 帧。比较峰值 bin、功率谱误差、候选频率、漏检/误检、单帧延迟、
CPU 占用、PL 资源和恢复行为。

最后再做真实 RF 定频 24、扫频 24 的 smoke，然后做 240+240 正式回归。固定分母，
不得删除漏项。识别准确率不得低于主链候选定频 233/240、扫频 237/240，且扫频漏项
必须为 0。否则保留软件后端和旧位流。
