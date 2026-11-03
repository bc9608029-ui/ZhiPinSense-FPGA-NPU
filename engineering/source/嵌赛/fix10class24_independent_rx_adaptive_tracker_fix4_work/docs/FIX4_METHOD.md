# FIX4_METHOD — 公共参考自适应 DC/LO 漂移跟踪方法

**任务** `M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4`
**状态** 纯离线方法文档（未达板测门槛前不生成 BOARDTEST_FIX4.md）
**日期** 2026-10-21

---

## 1. 问题

Fix3-R1 已定位因果链：RF 前端时变 LO 直流（载荷内实部/虚部漂移，如 `+7.9j → −6.8j`）经广线性逆偏置增益 `≈ 1/|a| ≈ 32`（归一化域，矩阵良态 `cond ≈ 1.1`）放大为模型输入上的 `~3.5j` 虚假直流，模型「见强直流 → AM-SSB」坍缩到 2 个 SSB 类。

Fix3 试过 M1–M5 静态/线性去直流，仅 `1 → 2/24`（`STATIC_DC_MARGINAL_NO_RECOVERY`）。根因是**漂移随时间变化**，静态单值去直流无法在载荷内追踪。

Fix4 目标：用**公共参考块**（前导/settle/train/guard/tail，**绝不读未知载荷**）估计一条**逐样本时变 DC 轨迹** `d[n]`，从对齐后的 burst 减去，再重估 fix2 恢复链，看能否**同时**改善门内残差与分类正确率。

## 2. 公共参考块（唯一合法观测）

burst 59904 复样本，对齐坐标：

| 块 | 区间 | 内容 | 观测 |
|---|---|---|---|
| preamble | 0:1024 | ZC chirp | （不用于 DC 观测） |
| settle | 1024:2048 | 静默 | 块均值 ≈ DC@t=1536 |
| train | 2048:3072 | 已知 16QAM | 块均值 ≈ DC@t=2560 |
| payload | 3072:56832 | **未知载荷（禁用）** | — |
| guard | 56832:58880 | 静默 | 块均值 ≈ DC@t=57856 |
| tail | 58880:59904 | ZC chirp | 块均值 ≈ DC@t=59392 |

4 个公共 DC 观测 = `public_dc_observations()` 返回的 `(块中心时刻 t, 复块均值 z)`。settle/train/guard/tail 内容近似零均值（16QAM 对称 / ZC chirp / 静默），故块均值逼近该时刻 DC。

**红线**：跟踪器只读这 4 个块；绝不读 payload、class、label、logits。类别无关，无逐类规则。

## 3. DC 轨迹模型

每个跟踪器把 4 个观测 `(t_k, z_k)` 映射为全长 59904 的复轨迹 `d[n]`（对齐坐标）。减去轨迹后重估 fix2 链（DC 减法是逐点线性，与去 CFO 旋转可交换）。

## 4. 跟踪器

| 名称 | 模型 | 说明 |
|---|---|---|
| `T0_baseline` | 无 DC | `d[n] ≡ 0`，即 fix2 原链（Phase 0 基准） |
| `C1_settle_dc_constant` | 常数 | `d[n] ≡ settle 块均值`（fix3-R1 M1 锚，交叉核对用） |
| `T1_blockwise_linear` | 分段线性 | 4 观测间 `np.interp`（实/虚分别） |
| `T2_exp_transient` | 常数+指数启动瞬态 | `c + A·e^{−t/τ}`，τ 在 logspace(256, 200000, 48) 网格上按公共观测拟合残差选 |
| `T3_hermite` | 三次 Hermite (Catmull-Rom) | C¹ 光滑，端点单侧切线，观测区间外平延 |
| `T4_kalman` | 常速度 LS 直线 | 单全局速率 = 4 观测最小二乘直线（见 §5） |
| `T5_kalman_crossframe` | 跨帧常速度 | T4 + 用上一帧 tail 处 DC 值钉住本帧 settle 处（权重 `W_PRIOR=1.0`） |
| `T6_best_alternate` | 择优+交替重估 | T1–T4 中取公共训练残差最小者，然后 ≤3 轮交替累积 DC 精化 |

## 5. T4/T5 为何是「LS 直线」而非 Kalman RTS

最初实现为 2 状态（dc+rate）高斯平滑器（二阶差分罚的 MAP，Whittaker 型），用 pentadiagonal banded solve。验证证明求解器**数值正确**（小 n 稠密/带状逐位一致，残差 7e-8），但真解在载荷内过冲到 `-106`。

根因是**病态而非 bug**：4 个稀疏、非单调观测下，二阶差分先验的「线性趋势模」与「最低曲率模」近简并（`cond ~ 6e8`），有限 q 的 MAP 解在 55296 样本空隙上无界外推。

因此 T4/T5 取 **q→0 的精确极限 = 常速度 LS 线性拟合**（`np.polyfit` 意义上的最小二乘直线）。它是有界、鲁棒、良态的「单一速率」估计，且诚实反映一个事实：4 个稀疏散落观测**不足以**约束一个真正随载荷内时变的非单调漂移——这正是 Fix4 §9 失败分类里「公共参考对载荷内部漂移不可观测」的候选根因。

## 6. 管线（`reestimate_fix4.py`）

对每帧 × 每跟踪器：

```
load raw → est0 = estimate_public_reference_fix2(raw)   # 对齐/CFO/tau/a/b
→ aligned = roll(raw, -timing0)
→ d[n] = tracker(aligned, prior)                        # 只读公共块
→ d_raw = roll(d, +timing0)                             # 修 fix3「DC 未 roll 回 raw」潜缺陷
→ est2 = estimate_public_reference_fix2(raw - d_raw)    # 门内残差重估
→ rec  = recover_v2(raw - d_raw, est2)
→ gated = est2.training_residual_rel ≤ 0.100
→ pred  = argmax(Host BF16 logits)                      # 仅 gated 且未 --no-infer
→ correct = (pred == class_index)
```

输出：逐帧对比表 `reestimate_<session>_comparison.tsv`、DC 轨迹表 `reestimate_<session>_dc_trajectory.tsv`、汇总 `reestimate_fix4_summary.json`。

## 7. 红线合规

- 不训练、不微调、不改冻结模型（SHA `28272abc…`/`c1781aec…` 加载期校验 fail-closed）。
- 不修改 0.100 门限；门拒样本不剔出 24 分母。
- 跟踪器**只读** 4 个公共块；不读载荷/标签/logits 选参。
- 不碰板、不发射、不改生产链；不把两轮回顾性结果称为独立盲测。

## 8. 判定等级（§8）

见任务书 §8：`NO_IMPROVEMENT`(≤2/24) / `MARGINAL_ONLY`(3–5) / `PARTIAL_RECOVERY`(≥6) / `BOARD_CANDIDATE`(≥12 且数字回归无新增翻转) / `STRONG_CANDIDATE`(≥18 且无逐类规则)。仅 `BOARD_CANDIDATE` 允许准备板端 C++ patch。
