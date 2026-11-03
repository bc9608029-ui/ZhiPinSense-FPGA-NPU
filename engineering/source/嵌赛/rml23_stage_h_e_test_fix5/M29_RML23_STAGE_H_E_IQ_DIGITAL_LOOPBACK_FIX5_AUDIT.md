# M29 RML23 Stage H-E / Route E fix5 — 任意 cyclic IQ 同步与保真判定审计

- 状态：`M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST`
- 基线：fix4 全量 `sdr_rml23_live_board_package_iq_digital_loopback_fix4.tar.gz`（SHA `48334de2…`）
- 范围：只改 Route E 判责仪表（同步 + 保真）+ host 镜像 + 日志 + 测试 + 打包/文档
- 红线不变：不改模型/标签/正式预处理/RTL/XDC/位流/Flash；不调 rec-scale/RX gain/TX
  attenuation 掩盖同步问题；tx_atten 上限 -40 dB；loopback=1；不碰真实 RF；不把 sweep
  PASS 写成回环保真 PASS；不覆盖 fix4 及更早包；本轮不碰板；不写任何 `*_PASS /
  PROJECT_COMPLETE / FINAL_* / BOARD_TEST_PASS`；`DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN /
  RF_LEAKAGE_NOT_PROVEN` 不因 host 测试改 PROVEN。

---

## §1 Phase 1 — 官方 ADALM-Pluto / AD936x 资料审计（A–H）

依据：ADI AD9361 Linux 驱动（`ad9361.c`）、AXI AD9361 HDL（`axi_ad9361` 核）、libiio
理论文档与 `channel.c`、以及本项目实际锁定的 libiio 0.26 源码。每条结论都标注
**官方明确说明** 或 **根据代码推断**，二者严格分开。

### A. 数字回环的位置与涉及的模块

- **官方明确说明**：AD9361 的数字回环（`loopback` 位，寄存器 0x3F5 `BBPLL`/数字回环选择）
  在 **BBP（Baseband Processor）数字域** 内闭合，位于 TX FIR 之后、DAC 之前，直接回送到
  RX 的 BBP 数字域、RX FIR 之前。即回环路径为
  `TX BBP(插值/FIR/增益) → 数字回环 → RX BBP(FIR/抽取)`，**不经过** DAC/ADC 模拟域、也不经过
  RF 混频器。
- **根据代码推断**：本项目 `pluto::PlutoTx::prepare()` 写 `loopback=1`，对应 AD9361 的数字
  回环；由于 1T1R 且回环在 BBP 数字域，TX 与 RX 共享同一样本时钟（`BBPLL`），因此
  **没有** 模拟域/时钟漂移；样本速率强制 2 560 000 SPS（`--phase=iq-digital-loopback`）。

### B. TX 16→12-bit：MSB / shift / truncate / round

- **官方明确说明**：AD9361 DAC 为 12-bit；libiio TX 通道的 16-bit 容器在
  `iio_channel_convert` 之后，写入 AXI 前，由 HDL 取 **最高有效 12-bit**（`shift` 决定对齐；
  shift=0 时取低 12-bit 之外的……）——官方资料对“取哪 12 bit”的权威表述是 **`shift` 字段
  指定的位对齐**，缺省（`length=16, bits=16, shift=0, is_fully_defined=true`）下 16-bit 容器
  的数值即被当作满量程 16-bit 交给 HDL，HDL 端按 DAC 位宽截取。
- **根据代码推断（本项目板端格式）**：板端 TX 格式审计为 `16b/16b shift+0 signed
  fully-defined`（见 fix4 板测 `IQ_DIGITAL_LOOPBACK_FORMAT dir=tx`）。因此 TX 侧 16-bit 容器
  的整数就是发送逻辑值；DAC 位宽截断发生在 HDL，**不是** 在 `iio_channel_convert` 里做的
  `/16` 或移位。fix5 的 `tx_dma_payload_sha`（见 §3）正是为此而加：它证明交给
  `iio_buffer_push` 的字节就是缩放后的 16-bit 字节，从而把“DAC 位宽截断”这一无法从主机
  侧观察的行为与“主机侧格式错误”分离。

### C. RX 12→16-bit 容器

- **官方明确说明**：AD9361 ADC 为 12-bit；libiio RX 通道把 12-bit 样本放入 16-bit 容器，
  对齐由 `shift` 决定。`is_fully_defined=false` 时 libiio 才按 `bits` 做符号扩展/高位掩码；
  `is_fully_defined=true` 时不额外掩码。
- **根据代码推断**：板端 RX 格式为 `16b/12b shift+0 signed fully-defined`（fix4 板测
  `dir=rx`），故 RX 原始容器即 12-bit 右对齐的有符号值（`-2048..+2047`），不符号扩展。
  fix4 已修复 host 镜像 `format_convert_raw_to_host`（先限定容器宽、逻辑右移、再按
  `is_fully_defined/is_signed/bits` 处理），fix5 不改该镜像语义。

### D. TX/RX FIR / sample-rate / AXI IQ 校正（mode1 下）

- **官方明确说明**：AD9361 默认（mode1）下 TX/RX FIR 均可配置；本项目的 2.56 MSPS 复用
  Stage G 的 `PreprocessChain`，数字回环两端的 FIR 会引入**群延迟**（FIR 抽头数决定）与
  **带内幅度/相位波纹**。AXI 级 IQ 校正（`axi_ad9361` 的 DC/正交校正）在回环内，若使能会
  叠加一个慢变的 IQ 不平衡。
- **根据代码推断**：fix5 **不依赖** FIR 群延迟的具体值——它用 FFT 全周期圆相关（§3）把任意
  cyclic 相位对齐到 sample-0，FIR 群延迟表现为一个固定 circular shift，被圆相关一并吸收；
  FIR 波纹与 IQ 不平衡则表现为最优复增益 `a` 之外的残差，由 scale-independent NMSE/EVM 度量。

### E. cyclic TX 起始相位 vs RX 缓冲起始的同步

- **官方明确说明**：`iio_buffer_push` 触发 DMA 循环发送，**不提供** 与 RX 捕获起点的绝对相位
  对齐；RX `iio_buffer_refill` 返回的样本是从 refill 触发时刻起连续捕获的流，**没有** 内建的
  “TX sample-0 对齐 RX buffer sample-0”的保证。因此 cyclic TX 的起始相位对 RX 而言是**未知的
  任意相位**。
- **根据代码推断（本项目）**：fix4 的 `find_correct_rx_shift` 在有界窗口 `[0, delay_margin)` 内
  搜整数延迟，**无法** 覆盖 53760-sample 周期内的任意相位 → 这是 fix5 缺陷 #1（§2）。

### F. destroy/recreate buffer 的 sample-0 语义 + RX refill 触发

- **官方明确说明**：libiio RX buffer 由 `iio_device_create_buffer` 创建；同一 buffer 上的多次
  `iio_buffer_refill` 返回**连续**的流（sample-0 只在创建时出现一次）。要重新对齐到“新 TX 的
  sample-0”，必须销毁并重建 buffer；重建后的第一次 refill 才从新的 sample-0 开始。
- **根据代码推断（本项目）**：`transfer_one_file` 每个文件创建/销毁一次 TX buffer（`PlutoTx`
  RAII），并 `recreate_rx_buffer()` 重建 RX buffer 再 refill（fix2 req3），与官方语义一致。
  fix5 不改这段，只把捕获长度改为 `2P + delay_margin`（§3）。

### G. `iio_buffer_push` / `refill` 的时间戳与触发

- **官方明确说明**：`iio_buffer_push` 是“把当前 buffer 内容提交给 DMA 循环发送”的同步调用，
  不返回时间戳；`iio_buffer_refill` 阻塞到该 refill 的样本数就绪，返回样本数。二者之间没有
  精确的相位/时间戳契约——这是 libiio 的通用语义。
- **根据代码推断**：fix5 的 `tx_dma_payload_sha` 在 `tx_start_cyclic` 内、`iio_buffer_push`
  **之前** 读回 TX buffer 的实字节并 SHA（§3），从而把“交给 push 的字节”这一事实锚定在
  push 之前，而不是依赖 libiio 的时间戳。

### H. 本项目实际 TX/RX DMA / scan / IQ 顺序 / repeat / shift / signed / fully_defined

- **根据代码推断（唯一来源，因为这是项目私有实现）**：
  - TX：`tx_start_cyclic` 用 `iio_buffer_first(txbuf, tx_i_ch/q_ch)` + `iio_buffer_step` 逐复数
    写 I/Q；`iio_buffer_push` 循环发送；`iio_buffer_destroy` 由 `PlutoTx` 析构完成。
  - RX：`read_rx` 单次 `iio_buffer_refill` 读连续复数，I/Q 交错。
  - 格式：TX `16b/16b shift0 signed fully_defined`；RX `16b/12b shift0 signed fully_defined`
    （fix4 板测确认，非本次推断新增）。
  - 这三点 fix5 不改变；fix5 只在 TX 写循环后**新增** DMA 字节 SHA 证据。

---

## §2 Phase 2 — 当前实现审计（fix4 遗留的三个已确认缺陷）

### 缺陷 #1：有界整数延迟搜索无法覆盖全周期任意 cyclic 相位

- **证据**：`iq_digital_loopback_sweep.hpp::find_correct_rx_shift`（fix4）在
  `[0, delay_margin)` 内搜整数延迟；`iq_digital_loopback_runner.hpp`（fix4）把 `fid.delay`
  作为对齐起点。
- **后果**：53760-sample 周期内的任意起始相位（cyclic shift 可到 53759）远大于
  `delay_margin`（默认 4096/16384），正确延迟搜不到 → corr 塌到 ~0.095，与板测
  “corr=0 / rms_rx≈0 / 分类 1/8”一致。
- **修复（fix5）**：全周期 FFT 圆相关，搜 **全部 P 个** circular shift（§3）。

### 缺陷 #2：NMSE/EVM 分母用 TX 能量，把低相关掩盖成低 EVM

- **证据**：fix4 NMSE 分母为 `sum|x|²`（TX 能量），而非 `sum|y|²`（RX 能量）。当 RX 是 TX 的
  1/16（能量 /256）时，`err / sum|x|² ~ 0.004`，即使 corr ~ 0.095 也显示 NMSE ~ 0.004 /
  EVM ~ 6.6%。
- **修复（fix5）**：scale-independent `normalized_residual = ||y − a·x||² / ||y||²`，与
  `1 − |corr|²` 一致（`nmse_evm_consistent` 门禁），低相关**不可能**再显示低 EVM。

### 缺陷 #3：无“实际交给 DMA 的字节”证据，无法区分 stale-leak 与调制失真

- **证据**：fix4 只证明“加载并校验了冻结文件 + 启动了 cyclic TX”，未证明
  `iio_buffer_push` 实际推送的 DMA 字节等于缩放后字节。
- **修复（fix5）**：`tx_dma_payload_sha`（push 前读回 TX buffer 字节 SHA），
  `TX_DMA_PAYLOAD_MISMATCH` 门禁。

---

## §3 要求 → 实现映射（fix5）

| 要求 | 实现 | 位置 |
|---|---|---|
| 全周期 FFT 圆相关，搜全部 P 个 circular shift | `circular_cross_corr` + `circular_sync` | `iq_digital_loopback_sync.hpp` |
| 输出 `linear_delay / circular_shift / wrap_count / peak_corr / second_peak_corr / peak_ratio / aligned_start / compared_samples / transient_discard_samples` | `CircularSyncResult` | 同上 |
| RX 循环重排到 TX sample-0 | `measure_fidelity_fix5` 的 `aligned_rx`（mod-P wrap） | 同上 |
| 双域比较（count TX16/RX12 分开 + normalized） | `gain_count / gain_db / gain_normalized / gain_normalized_db` | 同上 |
| 最优复增益 `y ≈ a·x` 输出 gain/phase/residual | `a = cc/ex`，`phase_deg`，`normalized_residual` | 同上 |
| scale-independent NMSE/EVM，与 `1−|corr|²` 一致 | `normalized_residual / evm_pct / nmse_evm_consistent` | 同上 |
| full-period / active-region / DC-preserved / DC-removed | `nmse_full_period / nmse_active_region / nmse_dc_preserved / nmse_dc_removed` | 同上 |
| tone / ramp / PRBS 角色 | host 测试 `tone` 多峰歧义 / `prbs` 唯一峰 | `test_iq_digital_loopback_sync.cpp` |
| 新判定 token | `TX_DMA_PAYLOAD_MISMATCH / CAPTURE_TOO_SHORT / CIRCULAR_SYNC_AMBIGUOUS / DIGITAL_LOOPBACK_DISTORTS_IQ / DIGITAL_LOOPBACK_PRESERVES_IQ / DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN` | `fidelity_verdict_fix5` |
| 全部达 PRESERVES_IQ 才跑分类，否则 `INVALID_DUE_TO_FIDELITY_GATE` | runner `all_preserves` + `classification_verdict` | `iq_digital_loopback_runner.hpp` |
| 捕获 ≥ 2P + pipeline guard | `transfer_one_file` 捕获长度 `2*(tx.size()/2)+delay_margin` | `iq_digital_loopback_transfer.hpp` |
| TX DMA payload SHA（push 前）fail-closed | `tx_dma_payload_sha` / `tx_dma_payload_ok` | `transfer.hpp` + `pluto_device.hpp/.cpp` |

### 判定优先级（`fidelity_verdict_fix5`，严格顺序）

1. `INSUFFICIENT_EVIDENCE`（rx_complex < 1024）
2. `CAPTURE_TOO_SHORT`（捕获短于 transient + P）
3. `RX_ALL_ZERO`
4. `RX_LOW_AMPLITUDE`（rms_rx < 2 counts）
5. `CIRCULAR_SYNC_AMBIGUOUS`（peak_ratio < 2.0）
6. `DIGITAL_LOOPBACK_DISTORTS_IQ`（corr < 0.9）
7. `DIGITAL_LOOPBACK_PRESERVES_IQ`（corr ≥ 0.9 且无削顶且 normalized_gain 在 ±3 dB 且
   nmse_evm_consistent）
8. `DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN`（其余）

`TX_DMA_PAYLOAD_MISMATCH` 由 runner 在 `tx_dma_payload_ok == false` 时直接覆盖判定。

---

## §4 核心代码

### 4.1 FFT 圆相关（`iq_digital_loopback_sync.hpp`）

```
c[k] = | h[k] + h[nfft − P + k] |,  h = IFFT( FFT(x_pad) · conj(FFT(y_pad)) )
nfft = next_pow2(2P)
c[k] = | Σ_j x[j] · conj(y[(j − k) mod P]) |          （精确，P 不必是 2 的幂）
```

- 方向/shift 定义（host 测试 O(P²) 参考逐点验证）：
  `rx[j] = tx[(j − d) mod P]  ⇒  circular_shift == d`。
- `circular_sync`：丢弃 `transient_discard` 个样本 → 选一个完整周期 → argmax `|c[k]|` over
  全部 P 个 shift → 第二峰（排除 circular guard `max(1, P/64)`）→ `aligned_start =
  transient_discard + best`。捕获不足时返回 `compared_samples == 0`（fail-closed，映射到
  `CAPTURE_TOO_SHORT`）。

### 4.2 scale-independent 保真（`measure_fidelity_fix5`）

- 循环重排：`aligned[m] = rx[transient + ((circular_shift + m) mod P)]`（**mod-P wrap**，
  不是连续 `rx[start+m]` 读——后者在捕获恰好 transient+P 时越界，且与“周期信号循环重排”语义不符）。
- 最优复增益：`a = Σ y·conj(x) / Σ |x|²`。
- normalized 增益：`gain_normalized = |a| · 2^(tx_bits−1) / 2^(rx_bits−1)`（TX16/RX12 ⇒ ×16，
  把 count 域 1/16 = −24 dB 正确归一到 ~0 dB，**不算衰减**）。
- 残差：`normalized_residual = Σ|y − a·x|² / Σ|y|²`（分母是 **RX** 能量）。
- 一致性：`nmse_evm_consistent = |normalized_residual − (1 − corr²)| ≤ 1e-6`。
- 输出 `aligned_rx`（长度 2P）供 runner 分类直接消费（不再连续读 `rx[d..]`）。

### 4.3 TX DMA payload 证据（`transfer.hpp` + `pluto_device.hpp/.cpp`）

- `LibiioDevice::tx_start_cyclic` 在写循环后、`iio_buffer_push` 前，从 `iio_buffer_first`
  读回 TX buffer 实际字节并 `Sha256::hex` 到 `tx_dma_payload_sha_`。
- `FakePlutoDevice` 同样计算（用 `format_convert_host_to_raw` 镜像），并加
  `corrupt_tx_dma_payload` 注入点（翻转一个 DMA 位）供负例测试。
- `transfer_one_file` 记录 `tx_dma_payload_ok = (sha == tx_sha_post_scale)`，**记录不抛出**；
  runner 在 `tx_dma_payload_ok == false` 时判定 `TX_DMA_PAYLOAD_MISMATCH`。

---

## §5 文件差异（相对 fix4 全量 `48334de2…` 基线）

- 新增 4：`board_package/iq_digital_loopback_sync.hpp`、
  `host_tests/test_iq_digital_loopback_sync.cpp`、`scripts/package_iq_digital_loopback_fix5.py`、
  `docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX5_AUDIT.md`（+ 交付文档在 dist/）。
- 修改 6：`sdr_adapter/pluto_device.hpp`、`sdr_adapter/pluto_device_libiio.cpp`、
  `board_package/iq_digital_loopback_transfer.hpp`、`board_package/iq_digital_loopback_runner.hpp`、
  `host_tests/build_host_tests.sh`、`host_tests/run_tests.sh`。
- **不改**：模型 json/raw、标签、`PreprocessChain`、RTL/XDC、位流、Flash、`read_rx` 生产
  libiio 路径、`find_correct_rx_shift`（sweep 仪表）、sweep 判责 A→G。

---

## §6 离线验证（本轮不碰板）

- `host_tests/build_host_tests.sh` + `run_tests.sh` 全套 ALL PASSED（含新增 sync 测试 51 项 +
  既有 sweep/sequence/route_e/board_build/cli_override/rml23_build 无回归）。
- 打包器 dependency-closure fail-closed OK；两份 tarball 确定性重打包一致；独立解包
  `sha256sum -c` 全 OK。
- 模型/标签/预处理/RTL/XDC/位流/Flash 与基线逐字节一致（历史包未覆盖）。

---

## §7 板端复测（用户执行；本轮不写死 ip）

```
第一步：./scripts/run_gate9_rml23.sh --phase=iq-digital-loopback --center=2400000000 \
  --rx-gain=10 --tx-atten=-40 --frozen-dir=DIR --input-kind=radioml-reconstructed-2p56m \
  > /root/rml23_route_e_fix5_loopback.log 2>&1
```
预期：`IQ_DIGITAL_LOOPBACK_FORMAT dir=tx 16b/16b shift0 …`、`dir=rx 16b/12b shift0 …`；
`IQ_DIGITAL_LOOPBACK_TX_DMA_PAYLOAD ok=1`；`fidelity=` 为 `TX_DMA_PAYLOAD_MISMATCH /
CAPTURE_TOO_SHORT / CIRCULAR_SYNC_AMBIGUOUS / DISTORTS_IQ / PRESERVES_IQ / NOT_PROVEN` 之一
（不再是 fix4 的 `SYNC_OR_WRAP_INCONCLUSIVE`）；`gain_db` 为 count 域 −24.08 dB、
`gain_normalized_db` 为 ~0 dB（TX16/RX12 尺度，非衰减）；`corr` 与 `evm_pct` 满足
`nmse_evm_consistent=1`。仅当**全部**冻结文件达 `PRESERVES_IQ` 才允许扩展 24 类分类。

回环保真 `PRESERVES_IQ` 只在板端出现；host 测试不产生、也不声称 `DIGITAL_LOOPBACK_CAPABILITY`
已 PROVEN。
