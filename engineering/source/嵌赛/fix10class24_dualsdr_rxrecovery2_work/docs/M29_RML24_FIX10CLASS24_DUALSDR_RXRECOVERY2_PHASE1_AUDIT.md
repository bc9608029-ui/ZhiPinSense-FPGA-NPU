# fix10class24-dualsdr-rxrecovery2 — Phase 1 离线可行性硬门禁审计

状态：**`M29-RML24-FIX10CLASS24-DUALSDR-RXRECOVERY2-SOFTWARE-COMPENSATION-NOT-PROVEN`**

## 0. 结论（先行）

Phase 1 的 90 分钟离线可行性硬门禁 **未通过**。最新 4ASK 失败样本
(`clean_4ask_a413e2d4.ci16`) 的复现**精确成功**（6 项字段与板端一致到 6 位小数），
但 5 个固定候选补偿方案**无一**能把第二半验证残差压到 ≤ 0.100：

| 候选 | 第二半验证残差 | ≤0.100? |
|---|---|---|
| 1 scalar（rxrecovery1 标量基线） | 0.124185 | ✗ |
| 2 wide-linear（rxrecovery1 广线性） | 0.107171 | ✗ |
| 3 residual linear phase drift | 0.116900 | ✗ |
| 4 fixed 5-tap complex FIR（ridge） | 0.120886 | ✗ |
| 5 wide-linear + 5-tap FIR joint | **0.103533**（最优） | ✗ |

继续条件第 1 条「最新 4ASK 验证残差 ≤ 0.100」失败 → **停止，不进入 Phase 2/3**。
结论 token：**`RXRECOVERY2_SOFTWARE_COMPENSATION_NOT_PROVEN`**。

## 1. 证据与基线

- 最新失败证据：`F:\嵌赛\board_capture\rxrecovery1_run2\rml24_rxrecovery1_run2_failed_dump.tar.gz`
  （解包到 `evidence_run2/rml24_rxrecovery1_short2_run2_1773373740/failed_rx/500/`）。
- 关键板端字段（`recovery_diagnostics.json`）：`timing_offset=42252`、
  `coarse_cfo_hz=-79.6837`、`fine_cfo_hz=-10.1649`、`payload_training_corr=0.993258`、
  `payload_training_residual=0.116713`、`wide_linear scalar_validation_residual=0.124185`、
  `wide_linear validation_residual=0.107171`、`fidelity=RF_DISTORTS_IQ`。
- 基线 = rxrecovery1 FULL `6fd93f78…`；本任务在**独立新目录**
  `F:\嵌赛\fix10class24_dualsdr_rxrecovery2_work\` 下做离线重放，**未修改任何生产代码**，
  未碰板 / 未开 SDR。

## 2. 复现（必须达到 canonical 重放容差）

用 NumPy 精确移植 `iqrfrec::estimate` step 6.5/6.6（含 Lanczos-sinc 分数时移
`ft=-0.435547`、fine-CFO 去斜坡、canonical payload-training 参考
`f06e9b3d…`，该参考从 `expected_full_burst_ci16le.bin[2048:3072]` 读得并 SHA 校验
= canonical）。逐字段与板端一致（容差 1e-6，优于 canonical 重放的 1e-5）：

| 字段 | 复现 | 板端 | 一致 |
|---|---|---|---|
| payload_gain_mag | 0.030909775 | 0.0309098 | ✓ |
| payload_training_corr | 0.993257896 | 0.993258 | ✓ |
| payload_training_residual | 0.116712517 | 0.116713 | ✓ |
| scalar_validation_residual | 0.124185207 | 0.124185 | ✓ |
| wide-linear validation_residual | 0.107171242 | 0.107171 | ✓ |
| image_ratio | 0.067622700 | 0.067623 | ✓ |

复现脚本：`scripts/phase1_reproduce.py`。复现成功 → 不触发「复现失败立即停止」。

## 3. 5 候选补偿比较（前半 512 拟合 / 后半 512 验证）

全部在 fine-CFO 去斜坡后的 payload-training 块（`xc[k]`, 参考 `rk[k]`）上进行，
**拟合只碰前半、验证只碰后半、不用标签、不用 filtfilt、FIR 阶数固定 5、
带条件数/有限/系数界检查**：

| # | 候选 | 前半拟合残差 | 后半验证残差 | 说明 |
|---|---|---|---|---|
| 1 | scalar | 0.113304 | 0.124185 | 基线 |
| 2 | wide-linear `y=a·x+b·conj(x)` | 0.090824 | 0.107171 | image_ratio=0.0676 |
| 3 | residual linear phase drift | 0.113061 | 0.116900 | f_res≈21.4 Hz，改善可忽略 |
| 4 | 5-tap complex FIR（ridge λ∈{1e-6,1e-4,1e-2}·tr/N） | 0.110–0.115 | 0.120886 | 条件数 ~3e2 |
| 5 | wide-linear + 5-tap FIR joint | 0.087115 | **0.103533** | 条件数 ~3e2 |

所有系数有限；FIR 条件数 ~3e2（病态不严重）。最优候选 5 验证残差 0.103533 仍 > 0.100。

## 4. 残差结构（为什么 5 个候选都过不了 0.10）

对 wide-linear 全块拟合后的残差 `e` 做归因（`scripts/phase1_residual_structure.py`）：

- `corr(e, rk)=0.000`、`corr(e, conj(rk))=0.000` —— 线性 + 镜像项已完全移除。
- **`corr(e, rk²)=0.204`、`corr(e, conj(rk)²)=0.204`** —— 残差含显著的**二阶（非线性）分量**，
  这是 mixer 二阶互调/压缩类失真，5 个候选（全为线性/广线性/FIR/相位模型）**不在其模型类内**。
- `corr(e, rk>>1)=0.052`、`corr(e, rk>>2)=0.005` —— 相邻样本记忆（ISI）很弱。
- `corr(e, |rk|²·rk)=0.030` —— 三阶分量弱。
- 残差能量 80.4% 在 ±80 kHz 带内（窄带在带），但**时变**（四段 RMS 7.99→9.58→8.38→9.20），
  说明失真非平稳，前/后半不可由同一组固定系数统一拟合。
- 诊断：FIR 加到 9/17 tap 仅 0.1035→0.1034（**加 tap 无益**→非频率选择性多径）；
  WL+quadratic 反而 0.324→0.398（二阶基病态，`|rk|²·rk` 与 `rk` 强相关）。

结论：残差主因是**二阶非线性 + 时变非平稳 RF 失真**，超出本任务限定的 5 个
线性/广线性/FIR/相位候选的可表达范围；靠固定（时不变）系数补偿无法稳定把验证残差
压到 0.10 以下而不引入过拟合。

## 5. 继续条件逐条判定

| 条件 | 判定 | 依据 |
|---|---|---|
| 1 最新 4ASK 验证残差 ≤ 0.100 | **FAIL** | 最优候选 5 = 0.103533 |
| 2 BF16 raw24 pred 正确且与 baseline 一致 | 未达到（moot） | 无候选过残差门；历史强制分类已证失败样本不可靠 |
| 3 候选改善独立验证 | PASS（仅部分候选） | WL -13.7%、WL+FIR5 -16.6%，但改善不足以过门 |
| 4 系数有限/有界 | PASS | 全有限、条件数 ~3e2 |

条件 1 失败 → 整体 NO-GO。

## 6. 停止与后续

按任务书「否则报 `RXRECOVERY2_SOFTWARE_COMPENSATION_NOT_PROVEN` 并停止」，本任务在
Phase 1 停止，**未做** Phase 2 历史安全审计、Phase 3 生产集成、14 项测试、打包。

诚实结论（供后续决策）：
1. 0.10 门是**正确拒绝了一个真实 RF 失真**的捕获（`fidelity=RF_DISTORTS_IQ`），
   不是阈值设错——5/20 历史失败样本强制分类会误分类（前序任务已证），放宽门会引入误分类。
2. 广线性方向有效（0.124→0.107）但不足以过门，且补偿发生在生产门之后、无法救 `valid=0`，
   这是 rxrecovery1 已确认的架构事实。
3. 剩余 ~0.103 残差为二阶非线性 + 时变失真，属 RF 硬件域问题；软件补偿在
   不触碰 0.10 门、不引入已知误分类样本的前提下**不可证明能稳定过门**。

禁碰板/禁 SDR 保持；未写任何 `RF_PASS/SMOKE_PASS/…/NEW_PRODUCTION_THRESHOLD`。
