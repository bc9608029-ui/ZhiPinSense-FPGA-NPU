# M29 RML23 Stage H-F / Route F — fix9r2 审计（训练帧搜索窗口根因 + 修复计划）

状态：**`M29-RML23-IQ-RF-LOOPBACK-FIX9R2-READY-FOR-BOARD-TEST`**（host 完成后；上板须先 2 样本 R8，再 46 样本 R9）

关联状态（§12 Task G0）：
- `FIX9R1_BOARD_TEST=FAIL`（权威板测，见下）
- `FIX9R2_WORK=IN_PROGRESS`
- `FIX10_TASK_A=COMPLETE`（保留，不重做）
- `FIX10_IMPLEMENTATION=BLOCKED_BY_FIX9R2`

---

## 1. 板端实测（权威，必须写死，不得再写 PENDING）

```
FIX9R1_BOARD_TEST=FAIL

rx_gain=10:
  scored=0
  rf_excluded=46
  fidelity=RF_DISTORTS_IQ 46/46

rx_gain=30:
  scored=0
  rf_excluded=46
  training_corr_avg=0.110172
  training_corr_min=0.053861
  training_residual_avg=10.958594
  training_residual_max=18.539289

baseline_accuracy=99.34%
M22_RUNTIME_RESULT=PASS
restore_result=PASS
```

已排除（用户确认）：模型损坏、Route A 数据损坏、单纯 RX gain 过低、板端资源未恢复、4ASK 单类问题。故障在分类之前 = 训练帧发送 / 组帧 / 搜索 / 恢复参考不一致。

## 2. 根因（代码级定位，已核实）

`board_package/iq_rf_loopback_transfer_fix9r.hpp` 用 `tx.start_cyclic(burst)` 发射一个 **59904 复采样**的循环 burst（`[前导 1024][guard 2048][payload 53760][guard 2048][尾 1024]`，`kTotalBurstComplex=59904`），随后 `capture = kTotalBurstComplex + delay_margin = 59904 + 8192 = 68096` 抓一帧连续 RX。

`board_package/iq_rf_per_frame_recovery.hpp` 的 `estimate(rx, search_limit=4096)` 只在 **前 4096 样本**内搜前导（`search = min(4096, rx.size()-1024+1)`）。

由于 TX 是 **cyclic**，RX 捕获起点相对循环帧**任意**（前导在循环流里的相位均匀分布在 `[0, 59904)`）。前导落在前 4096 样本内的概率 = 4096/59904 ≈ **6.8%**。其余 ~93% 的情况，搜索锁在噪声上。

噪声对 1024 样本 ZC 在 4096 个候选位置上的**最大归一化相关**期望 ≈ `sqrt(2·ln(M)/N)` = `sqrt(2·ln(4096)/1024)` ≈ `sqrt(0.0162)` ≈ **0.127** —— 与实测 `training_corr_avg=0.110172` 完全吻合。锁到噪声后 LS 增益非零（`valid=true`，这正是 §8 指出的「valid=1 表示函数返回了数值」缺陷），`training_corr<0.9` → `RF_DISTORTS_IQ` → 全 46 文件被 fidelity gate 排除，`scored=0`。

**根因结论**：搜索窗口（4096）远小于循环周期（59904）+ 捕获长度（1.14 周期）不足以保证完整 burst 落入捕获 → 前导 93% 概率被漏搜。

## 3. fix9r2 修复计划（Task R1–R9 映射）

| Task | 内容 | 落点 |
|---|---|---|
| R1 | 字节溯源：payload_source / training_reference / framed_logical_iq / formatted_tx_container / submitted_iio_buffer 的 SHA/RMS/peak/clip/I-Q 顺序/位宽/signed/endianness；`iio_buffer_push` 记录 requested_bytes/returned_bytes/ok | `iq_rf_tx_provenance.hpp` + `pluto_device_libiio.cpp`/`pluto_device.hpp` |
| R2 | TX 帧验证器：从 submitted_iio_buffer 反解析，训练帧/载荷逐样本比对 → `training_exact_match/payload_exact_match/frame_layout_match`，任一≠1 禁止 push | `iq_rf_tx_provenance.hpp` |
| R3 | 训练帧设计审计：version/seed/length/RMS(缩放前后)/peak/clip/自相关主旁瓣比 | `iq_rf_training_frame.hpp` + audit |
| R4 | 显式循环帧布局 + **捕获 ≥2 周期** + **全周期搜索**（不假定捕获从帧头开始） | `iq_rf_frame_layout.hpp` + transfer |
| R5 | 正确处理顺序（格式→DC→粗 CFO→时序→精 CFO→增益/相位→漂移→SRO→载荷窗）；共享核心 `iq_rf_sync_recovery.hpp`；数学符号约定 | `iq_rf_sync_recovery.hpp` |
| R6 | `estimate_computed` vs `estimate_valid`；valid=1 须满足 9 条件；失败枚举 token（10 种） | `iq_rf_sync_recovery.hpp` + runner |
| R7 | host 测试：字节级/理想闭环/合成网格/负对照 | `test_iq_rf_loopback_23class_fix9r2.cpp` |
| R8 | 2 样本板端诊断门（1 BPSK + 1 4ASK） | 板端（我禁碰板） |
| R9 | 46 样本回归门 → `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS` | 板端（我禁碰板） |

## 4. 红线（§2 严禁，不变）

不降 `training_corr` 门、不升 `residual` 门、不绕过 fidelity gate、不把 `RF_DISTORTS_IQ` 强行送入模型、不用标签选同步/CFO/相位/增益/窗口、不改模型/标签/映射/预处理、不用 valid=1 表示「返回了数值」、不把 host buffer SHA 冒充 DMA readback SHA、不直接重跑 46 样本、不在 fix9r2 通过前打包 fix10 可上板版本。RF 安全上限 `kSafeTxCeilingDb=-40.0`/`kSafeTxAttenDb=-89.75` 不变。R8 固定条件：center=2.4 GHz、TX atten=-40 dB、RX gain=30 dB、50Ω 同轴、无天线无放大。

## 5. 交付（§20 第一交付，host 已完成）

`fix9r2_patch.tar.gz` + `fix9r2_full.tar.gz` + `FIX9R2_AUDIT.md`（本文档）+ `FIX9R2_DELIVERY.txt` + 两份 `SHA256SUMS`。**各工件最终 SHA / 字节 / 文件数见交付清单**（`dist/RML23_IQ_RF_LOOPBACK_FIX9R2_DELIVERY.txt`，不写入本文档以免自引用）。交付后停止，等 R8 2 样本 + R9 46 样本板测。fix10 第二交付只在 fix9r2 板端 `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS` 后。

基线（fix9r1 全量，不变）：`sdr_rml23_live_board_package_iq_rf_loopback_fix9r1.tar.gz` = `306873e100a8238e0adfe8c38b8a202be4adc4a542144f3b966ee91c50b0a93d`（572 内容文件）。

工件构成：补丁 14 内容文件（6 新增 + 8 修改）；全量 578 内容文件（564 fix9r1 字节一致 + 8 改 + 6 新，`SHA256SUMS.txt` 重生成）。

打包权限（§21，已审计，两包均 bad=0）：目录 0755 / `*.sh` 0755 / 其余 0644；禁 0666/0777；两跑确定性（patch/full 两次运行 sha256 逐字节一致）+ 独立解包 `sha256sum -c`（patch 14/14、full 578/578 OK）+ dependency closure（OK）+ 无历史包覆盖 + 无 fix9r1 旧包残留 + 模型/标签/预处理/RTL/XDC/位流/Flash 未变（content-consistency 564 fix9r1 文件字节一致）。

R8（先）2 样本诊断（1 BPSK + 1 4ASK）与 R9（后）46 样本回归命令见 `dist/RML23_IQ_RF_LOOPBACK_FIX9R2_DELIVERY.txt` §4。
