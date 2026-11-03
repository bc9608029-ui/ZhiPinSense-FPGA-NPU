# M29-RML24-V2-SAME-CAPTURE-ORACLE-ABLATION1 — 方法

状态：`…-METHOD-COMPLETE`（纯离线，不训练、不碰板、不发射）

> 本文件为 2026-10-21 复审修正后版本。修正点：O0 口径分离（生产 e2e vs 强制 O0）、
> O1/O2/O3 改为**独立**单一修正（非累积）、O2 明示为 payload-oracle 复标量（非 manifest
> 尺度）、O5 改为真正交叉验证、残差统一 NMSE/NRMSE（不可与生产门直接比较）、H5 不排除。

## 1. 目的

用**同一批**当前 v2 公共协议真实双 SDR RX 捕获（两会话各 24 帧），逐帧施加 oracle
修正，区分 5 个假设哪个是低准确率的根因：

- H1 载荷窗/定时估计误差
- H2 逐样本尺度缺失
- H3 原始合法直流不可恢复
- H4 其他非仿射/时变 RF 失真（固定仿射修正不足）
- H5 冻结模型真实 RF 域失配

## 2. 数据与会话（独立，禁止合并）

| 会话 | 恢复链 | 门(0.100) | 生产 e2e 事实 |
|---|---|---|---|
| rf_fix2_target | fix2（联合 cfo/τ + frac_delay） | 过门 23/24 | 标签 1/24、坍缩 17/18 |
| rf_independent_v2 | old（前导 CFO，无 τ） | 过门 0/24 | 标签 0/24，全门拒 |

两会话使用同一组 24 个 v2 源波形（`source_index=class_index+1`）。数字基线（无 RF）
冻结为 23/24：唯一误分类 source 21 (AM-DSB-SC)→16 (256QAM)，属数字 v2 域固有误分类。

## 3. 指标

- **主**：与 v2 数字基线预测一致 /24（`agree`）。`DIGITAL_BASELINE_PRED
  = 0..19, 16, 21, 22, 23`。
- **次**：标签正确 /24（`label`），上界 23/24（source 21 数字域即误分类）。
- oracle 不得要求超过数字基线上界（23/24）。

**O0 口径分离（不混淆）**：

- **生产 e2e**：板端门控实际输出 `gate_pass / label_correct / agree`（用 `board_pred`，
  门拒帧输出非该类）。这是部署真实行为。
- **强制 O0**：主机 BF16 **强制分类** `z0`（无视门）。这是消融基线，与 O1–O5 同口径
  （均强制分类）。二者**分别报告**，不得互代。

**残差统一输出**：NMSE = |z-x|²/|x|²、NRMSE = sqrt(NMSE)（参考归一化，相对数字真值
`x`）。生产门 `training_residual_rel ≤ 0.100` 是**训练段、接收能量归一化**
（sqrt(|e|²/|r_train|²)），与载荷窗 NMSE/NRMSE **定义不同，不可直接比较**；本消融只把
NRMSE 用于 oracle 级间相对比较。

## 4. 阶段

- **Phase 0**：`inventory_same_capture.py` → `results/provenance.tsv`（逐帧溯源：
  raw/burst/payload/生产张量 SHA + 门/残差/预测 + 数字基线预测）。
- **Phase 1**：`replay_o0_production.py` → `results/o0_replay.tsv`。完整重放生产恢复，
  张量 SHA 与原保存逐字节一致；任何一帧不符 → `INVALID_ANALYSIS_PRODUCTION_REPLAY_MISMATCH`。
- **Phase 2**：`run_oracle_ablation.py` + `judge_oracle_ablation.py`。

## 5. 生产恢复正向模型（O0，逐字节复现）

`locate_preamble → slice 59904 → align(roll -timing) → derot(exp(-j2πcfo·n/FS)) →
payload[3072:3072+53760] → wide_linear_inverse(a,b) → [fix2: frac_delay_sinc(-τ)] →
[:1024] × 1/S_v2`，其中 `S_v2 = 71.609111379029812`。

- fix2：`a,b,cfo,τ` 来自 `estimate_public_reference_fix2`（训练块联合 (cfo,τ) 网格）。
- old：`a,b,cfo` 来自 `estimate_public_reference`（前导两半 CFO，无 τ）。

## 6. Oracle 级别（**各自独立**对 z0 施加单一修正，非累积；均匀施加，禁止按标签择优）

令 `z0` = O0 输出（1024 复），`x` = 原始载荷 `generate_waveform_v2(ci)`（数字真值）。

- **O0**：`z0`（生产盲恢复，强制分类）。
- **O1（只改窗）**：`z1 = roll(z0, Δ)`，`Δ = argmax_d |vdot(roll(z0,d), x)|`（循环窗
  对齐，等价于「精确载荷窗」）。仅此一项，不叠加尺度/直流。
- **O2（只改尺度，payload-oracle 复标量）**：`z2 = z0 / s`，`s = vdot(x,z0)/vdot(x,x)`
  （对原始载荷的复数 LS 标量）。**不是** manifest 发送尺度；manifest 尺度 `S_v2` 已在
  生产 `×1/S_v2` 中施加，故「纯 manifest 尺度」oracle 与 O0 退化等价。仅此一项。
- **O3（只改直流）**：`z3 = z0 - (mean(z0)-mean(x))`（去除虚假直流，保留合法直流）。
  仅此一项，不叠加窗/尺度。
- **O4（窗+尺度+直流组合）**：先循环对齐，再联合拟合 `x ≈ s·z1 + c`（尺度与直流一次
  LS，避免顺序 scale→dc 的直流污染尺度）。`z4 = s·z1 + c`。
- **O5（真正交叉验证仿射）**：`x ≈ p·z + q·conj(z) + c`，**前 512 点用「后 512 点拟合」
  的参数修正、后 512 点用「前 512 点拟合」的参数修正，拼接成 1024**；残差仅计算各自
  未参与拟合的半段。`z5 = [p₂·z0[:512]+q₂·conj(z0[:512])+c₂,
  p₁·z0[512:]+q₁·conj(z0[512:])+c₁]`。

各级张量送冻结 BF16 主机推理（`icraft-run --backends Host`，模型 RAW `c1781aec…`），
记录预测/agree/label 与 NMSE/NRMSE。

## 7. 红线

不训练/不碰板/不 SDR/不发射/不改生产恢复·门·协议；24 分母不剔；oracle 只用于离线诊断
不进入生产恢复；不按标签挑选逐帧最优 oracle；C0(18/24) 旧链不并入 v2 统计。
