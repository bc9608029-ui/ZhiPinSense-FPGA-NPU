# M23 P0 — 集成阶段硬门禁清单（Integration Hard Gates）

> 状态：`M23-P0-OFFLINE-MODULES-READY`（本清单随离线预研交付，门禁在**正式 M23 集成阶段**执行，本轮不执行）。
> 下列四项在 M23 正式接入 M22（Gate 9/Gate 10）主链**之前必须逐项通过**，任一未通过不得接线、不得写集成 PASS。这是硬门禁，不是待办项。

## HG-1 占用带宽算法替换（occupied bandwidth）

- **现状**：`sdr::DspMeasure` 的 occupied-BW 是「跨度定义」`max_bin − min_bin + 1`，带外一个噪声/量化谱线即可使跨度横跨整段谱（实测 tone+BPSK+AWGN 出现 `occ_bins=898` 而非 ~1）。
- **门禁**：集成前必须把 occupied-BW 改为 **99% 功率带宽** 或 **最大连通区域** 算法，并给出单音/双音/宽带调制三类合成信号的误差验收。
- **禁止**：继续沿用 `DspMeasure` 跨度定义作为正式输出口径。当前实现仅作离线参考，不得进入 M23 集成。

## HG-2 CFO 阶数自动选择（CFO order）

- **现状**：CFO 阶数 `cfo_order` 由调用方/用户传入（1/2/4）。
- **门禁**：阶数**不得由用户随意选择**；必须由**已知调制类型**自动选择（单音→1、BPSK→2、QPSK→4、…），调制类型**未知时返回「不确定」**（`cfo_hz.valid=false`，UI 显示 `--`，绝不猜测一个阶数）。
- **禁止**：未知调制类型下返回一个看似有效但阶数存疑的 CFO 值。

## HG-3 宽带调制 SNR 标注近似（SNR approximation label）

- **现状**：`snr_db` 谱域口径对窄带单音/双音最准（+1.66 dB），对宽带调制是近似值。
- **门禁**：宽带调制下的 SNR 估计必须**明确标注为近似值**（例如输出带 `approximate` 标志或 UI 显示 `~`），不得作为绝对 SNR 读数/门限依据。

## HG-4 OOD-U 保持默认关闭直至真实 NPU logits 对齐（OOD-U gating）

- **现状**：`M23OodSwitch` 默认关闭；阈值 `-0.15274411201477073` 来自 M20 fp32 checkpoint + int8 仿真，**未取真实 NPU logits**。
- **门禁**：OOD-U 必须**保持默认关闭**，直到真实 NPU logits 捕获并对齐、阈值经真实 NPU logits 重新校准**之后**才允许默认启用；在此之前任何显示都只允许 `UNKNOWN_EXPERIMENTAL`，不得宣传为可靠功能，near/far 拒识率（约 6.03%/10.33%）不得作为验收指标。

## 执行方式

以上四项门禁的验证用例与真实 NPU logits 捕获，随 M23 集成阶段另行开展。本离线预研阶段只登记门禁，不执行、不写 PASS、不改状态红线（最高仍 `M23-P0-OFFLINE-MODULES-READY`）。
