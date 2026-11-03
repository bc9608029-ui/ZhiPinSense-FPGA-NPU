# Fix4 REVIEW-R1 方法 — 公共参考残差定义修正

任务：`M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4-REVIEW-R1`
状态：`…-REVIEW-R1-METHOD-COMPLETE`（纯离线，不碰板/不训练/不发射）

## 0. 审查结论（承认缺陷）

Fix4 R1 把接收 train/tail 的**块均值**当 DC。这是错的：train（16QAM）与 tail（ZC
root-3）是**已知的非零均值序列**，块均值会把「已知序列自身的均值」与「LO 直流」混在一起。

实测（`fix4_residual_ref.reference_mean`）：

| 公共块 | 参考 | 复均值 | |mean| |
|---|---|---|---|---|
| settle | 0（静默） | 0 | 0 |
| train | 16QAM（amp 2896.309） | **-276.1 - 276.0j** | **390.4** |
| guard | 0（静默） | 0 | 0 |
| tail | ZC root-3（amp 2048） | **-45.2 - 45.2j** | **64.0** |

R1 的「train 块均值」≈ 16QAM 参考均值 + 真实 DC ≈ 390 + DC，因此把 ~390 的常数
当成 DC 轨迹的一部分注入，是根本性错误。R1 的 `fix4_verdict.json` 已标 `superseded`
（未删除，保留原工件）。

## 1. 修正后的定义（需求 3/4/5）

公共参考残差 = 实际接收公共块 − 经恢复模型预测的公共参考：

```
public_residual[n] = aligned[start+n] - pred[n]

pred[n] = ( a * frac_delay_sinc(x_ref, tau)[n]
          + b * conj(frac_delay_sinc(x_ref, tau)[n]) )
        * exp(+j * 2*pi * cfo * (n + start) / FS)
```

- `x_ref` = 冻结公共参考：settle/guard = 0（静默，参考即 0）；train = 真实 16QAM 序列
  （含其真实非零均值）；tail = 真实 ZC root-3 序列（含其真实非零均值）。**不允许用
  合成随机公共块替代**（需求 7）。
- `a`/`b`/`tau`/`cfo` = fix2 公共参考估计（`estimate_public_reference_fix2`）冻结参数；
  `a`/`b` 已吸收 TX→RX 增益，无需额外尺度项（需求 3 的「尺度」在 a/b 内）。
- 逐样本相减在**原始（对齐）域**完成，预测携带 CFO 旋转（需求 3 字面「经
  timing/CFO/a/b/尺度模型预测」）。
- 逐样本相减**之后**，才把每个公共块划分为子块（sub_len=256），计算每子块的复残差
  均值作为残差锚点（需求 5）：settle 4 + train 4 + guard 8 + tail 4 = **20 个锚点**。

## 2. 数字域自洽性（需求 7 的前半）

无 RF 时（接收 == 参考，est 给出 a≈1/b≈0/τ≈0/cfo≈0），`pred == x_ref`，故
`public_residual == 0`。实测数字域残差锚点 = **0.000**（`test_fix4_r1_reference_means`、
`fix4_residual_ref` 自测 R2）。而 R1 的块均值在同样场景下会报告 ~390（泄漏）。

## 3. 跟踪器 T0-T6（需求 6）

`trackers_fix4_r1.dc_trajectory(name, aligned, est, prior)`：

- `T0_baseline`：无 DC（0）。
- `C1_settle_dc_constant`：settle 参考为 0 → settle 残差均值 = DC（fix3-R1 M1 交叉对照）。
- `T1..T5`：对 20 个残差锚点做内插（复用 R1 的内插器 `_linear`/`_catmull_rom`/
  `_exp_transient`/`_constant_velocity`，纯「过锚点内插」数学，不含错误块均值定义）。
- `T6`：best-of(T1..T4) by 公共训练残差 + ≤3 轮交替重估。

DC 轨迹纯由公共残差锚点导出，不读载荷/标签/logits（`test_fix4_r1_no_leak`）。

## 4. 实现文件

| 文件 | 作用 |
|---|---|
| `scripts/fix4_residual_ref.py` | 核心：冻结参考 + `predict_public_block`/`public_residual`/`residual_anchors` |
| `scripts/trackers_fix4_r1.py` | 修正 T0-T6（残差锚点内插） |
| `scripts/reestimate_fix4_r1.py` | 修正重估（锚点→DC 减→完整重估 timing/CFO/tau/a/b/residual→门→推理） |
| `scripts/observability_fix4_r1.py` | 修正可观测性（20 锚点 scatter/非单调/帧间相关实测） |
| `scripts/digital_counterexample_r1.py` | 需求 7：真实 burst.i16 + 实测 no-new-flips |
| `scripts/judge_fix4_r1.py` | 需求 11：修正判决（读实测 digital_no_new_flips，不硬编码） |
| `host_tests/test_fix4_r1_*.py` | 参考均值/无泄漏/数字无操作 三套回归 |

旧 R1 工件（`trackers_fix4.py`/`reestimate_fix4.py`/`observability_fix4.py`/
`judge_fix4.py`/`fix4_verdict.json`）**全部保留**，仅 `fix4_verdict.json` 加
`superseded` 字段。
