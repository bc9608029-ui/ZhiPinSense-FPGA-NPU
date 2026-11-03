# M29 RML23 Stage H-F / Route F — fix9r2b 审计（R8 诊断波形捕获 + 汇总/token 语义修复，Phase 1 只加诊断）

状态：**`M29-RML23-IQ-RF-LOOPBACK-FIX9R2B-READY-FOR-BOARD-TEST`**（host 完成后；上板仍须先重跑同一 R8 2 样本，拿到 5 个波形 → 离线定量根因 → 才允许最小修复）
fix9r2b **第一阶段只增加诊断保存 + 汇总/token 语义修复**，**不引入均衡算法**（用户红线）。RF 数学、模型、标签、预处理、RTL/XDC/位流/Flash **一律未动**。

关联状态（§12）：
- `FIX9R2_WORK=DELIVERED`（fix9r2 全量 `ac9ed0b8…` 不变）
- `FIX9R2A_WORK=DELIVERED`（fix9r2a 全量 `611623af…` 不变，作为 fix9r2b 唯一基线）
- `FIX9R2B_WORK=DELIVERED`（本增量，Phase 1）
- `FIX9R2A_R8=FAIL`（两次真实 R8 板测：BPSK/4ASK corr≈0.974、residual≈0.23、estimate_valid=0/2）
- `FIX9R2B_REQUIRED` / `R9_46_SAMPLE=BLOCKED` / `FIX10_DUAL_SDR=BLOCKED` / `FORMAL_690_RF_RUN=BLOCKED`

---

## 1. Task A 定量分析结论（为什么只加诊断，不碰 RF 数学）

R8 板测证据（`phase=iq-rf-loopback-23class-fix9r classes=BPSK,4ASK per_class=1 center=2400000000 rx_gain=30 tx_atten=-40 rf_path=direct-cable`）：

| 样本 | target RMS | corr | residual | timing | gain_mag | phase_deg | estimate_valid |
|---|---|---|---|---|---|---|---|
| BPSK (`000006`) | 2048 | 0.972940 | 0.237482 | 29007 | 0.013976 | -83.772 | 0（`TRAINING_RESIDUAL_TOO_HIGH`） |
| 4ASK (`000002`) | 2048 | 0.975894 | 0.223639 | 23189 | — | — | 0（`TRAINING_RESIDUAL_TOO_HIGH`） |
| 4ASK (`000002`) | 4096 | ≈0.97 | ≈0.232 | — | — | — | 0（`TRAINING_RESIDUAL_TOO_HIGH`） |

**四条定量结论**：
1. **`TRAINING_FOUND`（非未找到）**：corr≈0.974 ≫ 0.90 门，前导已锁定（timing_offset 有值、gain_mag/phase_deg 有值），失败仅发生在 residual 门（回归 0.05 / 诊断 0.10 都不过）。
2. **`AMPLITUDE_LIMITATION_REJECTED`**：TX target RMS 从 2048 翻倍到 4096，residual 仍在 0.223639~0.237482，**几乎不变**（且 gain_mag 随幅度同步缩放）→ 残余不是幅度受限/量化噪声，而是**线性、幅度无关**的确定性失真。
3. **corr ↔ residual 严格自洽**：对标量模型 `rx = a·ref + e`（e⊥ref），`residual² = (1−corr²)/corr²`。代入 corr=0.974 → residual≈0.232，与实测 0.223~0.237 吻合 → 残余就是「标量拟合后的正交残差」，不涉及 CFO/SRO/削顶（CFO≈0、SRO≈0、无削顶，均已确认）。
4. **corr/residual 本身不能定因**：一个纯分数采样时延 ≈0.13 采样就能给出 scalar residual≈0.24（self-test 注入 +0.130 采样 → scalar=0.2400，与板测 0.23 一致）；但幅度/相位纹波、I/Q 不平衡、边界瞬态都能给出同量级 residual。**必须拿到对齐后的原始训练波形才能区分**。

**两个已确认的仪表缺陷**（fix9r2a 埋下）：
- (a) 汇总行报 `training_corr_min=0` / `training_residual_max=0`，尽管逐文件 corr≈0.974 / residual≈0.23 —— 因为旧聚合只在 `rec.valid` 文件上求 min/max，而 R8 两个文件都因 residual 失败 → valid=0 → 空聚合报 0。
- (b) 诊断行输出 `regression token=NOT_EVALUATED`，但最终 `GATE_RESULT` 却输出 `ROUTE_F_23CLASS_ACCURACY_REGRESSION_FAIL` —— 诊断模式本不该评估 46 样本回归，却在结果里泄漏了一个回归 FAIL token（自相矛盾）。

→ **fix9r2b Phase 1 只修这两处仪表缺陷 + 新增 5 个波形捕获**，供离线分析器定量判因。**不引入均衡/分数时延校正/保护带改动**（Phase 2 待定量根因后才允许选最小修复）。

## 2. fix9r2b 变更（全部离线可验；不碰 RF 数学）

| 任务 | 内容 | 落点 |
|---|---|---|
| §2 | 诊断模式逐文件保存 **5 个波形**：`expected_training` / `aligned_rx_training` / `training_error` / `expected_payload` / `provisional_recovered_payload`（interleaved float32，manifest 记录 `file_name/kind/path/sha256/complex_samples/rms/format`） | `iq_rf_fix9r2b_diagnostic.hpp` + runner |
| §5 | **provisional 标量恢复**：`provisional_apply_scalar` 复刻 `iqrfrec::apply` 的数学但**不受 `rec.valid` 门禁**（residual 失败的文件也能算出真实 payload corr/nmse）；DIAGNOSTIC_ONLY，**绝不喂给模型** | `iq_rf_fix9r2b_diagnostic.hpp` + runner |
| §6 | **汇总语义修复**：corr_min/residual_max 在「前导已找到（measured）」文件上聚合，不再只统计 valid 文件（修缺陷 a）；**token 语义修复**：诊断模式 regression token 恒为 `NOT_EVALUATED`、accuracy 字段为 `null`/`NOT_EVALUATED`（修缺陷 b） | `iq_rf_fix9r2b_diagnostic.hpp::aggregate_training_summary`/`gate_tokens` + runner |
| G | host 测试 9 场景 / 47 断言（stem/往返/provisional==apply/provisional residual 失败仍恢复/metrics/非零汇总/mixed 汇总/token 语义/结构隔离） | `test_iq_rf_fix9r2b.cpp` |
| A | 离线分析器 `analyze_fix9r2b_residuals.py`（numpy，`--self-test` 注入 5 因 + identity 负对照；`--manifest` 读波形 manifest 定量判因） | `scripts/analyze_fix9r2b_residuals.py` |

诊断波形/汇总**永远不能**携带 `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`（该 token 仅由 R9 46 样本合法复测建立）。诊断 token `ROUTE_F_FIX9R2_DIAGNOSTIC_PASS/_FAIL` 只证明「搜索 + 恢复链 + 波形捕获」通了。

## 3. 红线（§2 严禁，不变）

不降训练帧 corr 门、不升 residual 门（回归仍 0.05）、不绕过 fidelity gate、不把 `RF_DISTORTS_IQ` 强行送入模型、**Phase 1 不引入任何均衡/分数时延/保护带算法**、不用标签选同步/CFO/相位/增益/窗口、不改模型/标签/映射/预处理/RTL/XDC/位流/Flash、不静默覆盖 fix9r2 / fix9r2a（两基线包 SHA 不变）。诊断模式**不得**输出回归 PASS/FAIL。RF 安全上限 `kSafeTxCeilingDb=-40.0`/`kSafeTxAttenDb=-89.75` 不变。R8 固定条件：center=2.4 GHz、TX atten=-40 dB、RX gain=30 dB、50Ω 同轴、无天线无放大。

## 4. 交付（§20，host 已完成）

`fix9r2b_patch.tar.gz` + `fix9r2b_full.tar.gz` + `FIX9R2B_AUDIT.md`（本文档）+ `FIX9R2B_DELIVERY.txt` + 两份 `SHA256SUMS`。**各工件最终 SHA / 字节 / 文件数见交付清单**（`dist/RML23_IQ_RF_LOOPBACK_FIX9R2B_DELIVERY.txt`，不写入本文档以免自引用）。交付后停止，等用户上板重跑 R8 2 样本（这次会落盘 5 个波形），再离线定量判因 → 选最小修复。

基线（fix9r2a 全量，不变）：`sdr_rml23_live_board_package_iq_rf_loopback_fix9r2a.tar.gz` = `611623afcf40583748ef7b8a035db9261d51bede036312afb6f34b85fe0fb9c1`（582 内容文件）。

工件构成：补丁 8 内容文件（5 新增 + 3 修改）；全量 587 内容文件（579 fix9r2a 字节一致 + 3 改 + 5 新，`SHA256SUMS.txt` 重生成）。详见交付清单。

打包权限（§21）：目录 0755 / `*.sh` 0755 / 其余 0644；禁 0666/0777；两跑确定性 + 独立解包 `sha256sum -c` + dependency closure + 无历史包覆盖 + fix10 零残留（两份接线脚本经 `_FIX10_REMOVAL` 剥离为 fix9r2b-only）+ 模型/标签/预处理/RTL/XDC/位流/Flash 未变。

R8（重跑 2 样本诊断，落盘波形）命令见 `dist/RML23_IQ_RF_LOOPBACK_FIX9R2B_DELIVERY.txt` §4。
