# Fix4 结果（FIX4_RESULTS）

任务：`M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4`
状态：`…-FIX4-RESULTS-COMPLETE`（纯离线，不碰板/不训练/不发射）

**最终判决：`NO_IMPROVEMENT`**
（`results/fix4_verdict.json`，由 `judge_fix4.py` 按 §8 阶梯输出；
两条会话最佳跟踪器端到端均 = 2/24，与 fix3-R1 基线 C1=2/24 完全相同，
未超过 2/24，故判 `NO_IMPROVEMENT`；`board_patch_allowed=False`。）

---

## 1. Phase 0 基线复现（确认 fix3-R1）

| 跟踪器 | rf_fix2_target | old_rf_session |
|---|---|---|
| T0_baseline（无 DC） | 1/24（门 23/24） | 1/24（门 23/24） |
| C1_settle_dc_constant | **2/24（门 24/24）** | **2/24（门 24/24）** |

两条会话的 M0=1/24、C1=2/24 与 fix3-R1 记录**逐字节一致**；T0 恢复张量
与板端 `recovered.tensor.bin` 逐字节一致（`test_m0_byterepro` 3/3）。

---

## 2. Phase 2 全量重估（8 跟踪器 × 24 帧 × 2 会话）

每帧重跑完整 fix2 恢复链（timing/CFO/tau/a/b/residual）+ Host BF16 分类。

### rf_fix2_target（最新捕获）

| 跟踪器 | 门过 | 门内正确 | 端到端 e2e |
|---|---|---|---|
| T0_baseline | 23/24 | 1/23 | 1/24 |
| C1_settle_dc_constant | 24/24 | 2/24 | **2/24** |
| T1_blockwise_linear | 0/24 | — | 0/24 |
| T2_exp_transient | 24/24 | 2/24 | **2/24** |
| T3_hermite | 0/24 | — | 0/24 |
| T4_kalman（常速度 LS 线） | 24/24 | 2/24 | **2/24** |
| T5_kalman_crossframe | 16/24 | 1/16 | 1/24 |
| T6_best_alternate | 24/24 | 2/24 | **2/24** |

### old_rf_session（旧捕获）

| 跟踪器 | 门过 | 门内正确 | 端到端 e2e |
|---|---|---|---|
| T0_baseline | 23/24 | 1/23 | 1/24 |
| C1_settle_dc_constant | 24/24 | 2/24 | **2/24** |
| T1_blockwise_linear | 0/24 | — | 0/24 |
| T2_exp_transient | 0/24 | — | 0/24 |
| T3_hermite | 0/24 | — | 0/24 |
| T4_kalman（常速度 LS 线） | 24/24 | 2/24 | **2/24** |
| T5_kalman_crossframe | 20/24 | 1/20 | 1/24 |
| T6_best_alternate | 24/24 | 2/24 | **2/24** |

---

## 3. 关键观察

1. **无任何跟踪器超过 2/24**。最好的 C1/T2/T4/T6 与 fix3-R1 的
   settle-DC 常量完全打平；T4（常速度 LS 线）与最简单的 C1 常量等价。
2. **内插器更差而非更好**：T1（分块线性）与 T3（三次 Hermite）把门拒
   打成 0/24（target 与 old 均如此），即注入的错误 DC 形状使
   `training_residual_rel` 反而 >0.100。
3. **T2（指数暂态）会话依赖**：target=2/24、old=0/24 —— 指数暂态假设
   只在最新捕获上成立，说明其「漂移形态」不是跨会话稳定信号。
4. **T5 跨帧先验无益**：上一帧 tail DC 作先验使门过降到 16/24（target）
   /20/24（old），端到端仍 1/24 —— LO 直流帧间不相关（时变）。
5. **坍缩模式不变**：C1 门内 24/24 帧中，除 AM-SSB-WC(sid18)、
   AM-SSB-SC(sid19) 两帧正确外，其余 22 帧坍缩到 pred=17(AM-SSB-WC) /
   18(AM-SSB-SC) / 2(8ASK)；256QAM(sid17) 与 OQPSK(sid24) 被误判为
   8ASK。这与 fix3-R1 的「20/24 坍缩到 SSB」一致。

---

## 4. 结果工件（`results/`）

| 文件 | 内容 |
|---|---|
| `reestimate_fix4_summary.json` | 8 跟踪器 × 2 会话汇总（gate/e2e/gated） |
| `reestimate_fix2_target_comparison.tsv` | target 会话逐帧逐跟踪器表（192 行） |
| `reestimate_old_rf_v1v2_comparison.tsv` | old 会话逐帧逐跟踪器表（192 行） |
| `reestimate_fix2_target_dc_trajectory.tsv` | target 各跟踪器 DC 轨迹 7 关键点 |
| `reestimate_old_rf_v1v2_dc_trajectory.tsv` | old 各跟踪器 DC 轨迹 7 关键点 |
| `fix4_verdict.json` | 最终判决（`NO_IMPROVEMENT`） |
| `fix4_candidate_summary.tsv` | 候选汇总（2 会话 × 8 跟踪器） |
| `fix4_confusion_matrix.tsv` | 最佳跟踪器 + T0 参考的 pred×true 混淆 |
| `fix4_tensor_sha.tsv` | 最佳跟踪器每帧恢复张量 SHA256（byte 锚） |
| `observability_summary.json` | Phase 1 可观测性（非单调/散点/漂移跨度） |
| `observability_*_observations.tsv` | Phase 1 每帧 4 公共块观测 |

---

## 5. 数字回归（无新增翻转）

Fix4 只改 RF 恢复路径，不触碰数字回放；T0 与冻结 fix2 链字节级一致
（`test_m0_byterepro`），故数字侧「23/24 无新增翻转」由构造保证。
`test_digital_clean_noop.py` 进一步证明：在干净数据（零均值公共块、无
漂移）上，各跟踪器 DC 估计 ≈0（|dc|_rms < 0.1×signal_rms），减法退化为
近似恒等，不可能引入新翻转。数字基线 23/24（v2 回放唯一 AM-DSB-SC→
256QAM 已知错）保持不变。

---

## 6. 诚实负结论

- Fix4 在红线内（不训练 / 不改 0.100 门 / 只用 4 公共块 / 不读载荷）**无法
  提升两条真实 RF 会话的端到端正确率**，最高仍为 2/24。
- 根因（Phase 1 + 本结果）：RF 时变 LO 直流在载荷区间（3072:56832）对
  4 个公共参考块**不可观测**（real 非单调 22/24、24/24；scatter≈锚点幅度）。
- 这支持 §9-1（公共参考不可观测）为主因，并连同 fix3-R1 的
  `STATIC_DC_MARGINAL_NO_RECOVERY` 指向 §9-5（冻结模型需 RF 域适配）。
- **不构成 RF_PASS / PROJECT_COMPLETE；不生成 BOARDTEST_FIX4.md**
  （§8 仅 BOARD_CANDIDATE 起才允许板端 C++ 补丁准备）。

详见 `LIMITATIONS.md`（§9 逐条归因）。
