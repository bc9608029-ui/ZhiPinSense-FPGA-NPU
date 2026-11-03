# M29 RML23 Stage H-F / Route F — fix9r2a 审计（R8 2 样本诊断选择器 + 接受门）

状态：**`M29-RML23-IQ-RF-LOOPBACK-FIX9R2-READY-FOR-BOARD-TEST`**（host 完成后；上板仍须先 R8 2 样本，再 R9 46 样本）
fix9r2a 只把「R8 2 样本」这一步从**无法执行**变成**可执行且 fail-closed**；RF 数学、模型、标签、预处理、RTL/XDC/位流/Flash **一律未动**。

关联状态（§12）：
- `FIX9R2_WORK=DELIVERED`（基线，fix9r2 全量 `ac9ed0b8…` 不变）
- `FIX9R2A_WORK=DELIVERED`（本增量）
- `FIX9R2_BOARD_TEST=PENDING`（R8 + R9 仍待用户上板）
- `FIX10_DUAL_SDR=BLOCKED`（`BLOCKED_BY_FIX9R2`，不变）
- `FORMAL_690_RF_RUN=BLOCKED`（不变）

---

## 1. Task A 审计结论（为什么 fix9r2 的 R8 步骤选不出「1 BPSK + 1 4ASK」）

fix9r2 交付里 R8 用 `--file-filter=<文件名字串>` 或 `--max-files=2` 来「选 1 个 BPSK + 1 个 4ASK」。对 fix9r2 运行器的实际语义逐条核对（`iq_rf_loopback_23class_fix9r.hpp`）：

| 选择手段 | 实际语义（代码级） | 对 R8 目标集「1 BPSK + 1 4ASK」 | 结论 |
|---|---|---|---|
| `--file-filter=X` | 对 `FrozenIq::file_name` 做**子串**匹配（`find()!=npos`） | 文件名是 `quantized_d2_2p56m_%06d.ci16`，**不含调制名**；`--file-filter=BPSK` 匹配 0 个 → `STAGE_G_FROZEN_IQ_REQUIRED` fail-closed | 选不出 |
| `--max-files=2` | holdout 枚举顺序**截断前 2 个** | 前 2 个是 `000000 OOK, 000001 OOK`（部署类 0），不是 BPSK/4ASK | 选不出（选错样本） |
| `--smoke` | 只留 4 个 smoke 类（deployed 1/3/4/12 = 4ASK/BPSK/QPSK/16QAM） | 4 类 ×2 = 8 文件，非 2 文件，且含 QPSK/16QAM | 数量与集合都不对 |

**结论**：fix9r2 没有任何一个现有参数能表达「1 BPSK + 1 4ASK」。因此 R8 必须**新增一个按调制类选择 holdout 的机制**，而不是靠截断文件号（`--max-files`）或猜文件名（`--file-filter`）。→ **Option 2（加参数 + fix9r2a 全量重打包）**，不静默覆盖 fix9r2。

holdout 枚举顺序（46 样本 smoke 布局，部署类 0..22 各 2）：`0,1=OOK, 2,3=4ASK, 6,7=BPSK`。`--diagnostic-classes=BPSK,4ASK --diagnostic-per-class=1` 应命中 index 6（BPSK）与 index 2（4ASK）。

## 2. fix9r2a 变更（Task B/C/D/G，全部离线可验）

| Task | 内容 | 落点 |
|---|---|---|
| B | `--diagnostic-classes=BPSK,4ASK --diagnostic-per-class=1`：按 manifest `modulation` 列在 **holdout-only** 子集上选样本；与 `--max-files`/`--smoke`/`--file-filter` **互斥**（fail-closed），校准子集不动；类缺失/欠配 fail-closed（`DIAGNOSTIC_SELECTION_FAILED`） | `iq_rf_fix9r2a_diagnostic.hpp::select_diagnostic_holdout` + runner |
| C | 诊断模式每样本输出 `ROUTE_F_FIX9R2_DIAGNOSTIC`（23 字段）+ 汇总 token `ROUTE_F_FIX9R2_DIAGNOSTIC_PASS/_FAIL`；**绝不输出回归 PASS**（2 样本 run 不评估 46 样本回归，`ROUTE_F_23CLASS_ACCURACY_REGRESSION token=NOT_EVALUATED`） | runner |
| D | R8 接受门（**低于** 46 样本回归的放宽门槛）：`selected==requested`、`holdout_files==requested_count`、每文件 `estimate_computed/valid`、`frame/training/payload_exact_match`、`tx_push_ok` 全 `==holdout_files`、`tx_clipped==0`、`rx_clipped==0`、`training_corr_min>=0.90`、`training_residual_max<=0.10`、`restore_ok` | `iq_rf_fix9r2a_diagnostic.hpp::evaluate_diagnostic_gate` + runner（`kDiagnosticTrainingResidualMax=0.10` vs 回归 0.05） |
| G | host 测试 13 场景 / 38 断言（选择器 + 门，纯函数，无 NPU/设备/libiio） | `test_iq_rf_loopback_23class_fix9r2a.cpp` |

诊断门**只能**证明「训练帧搜索 + 恢复链通了」（corr≥0.90、residual≤0.10、TX 帧验证器 + push 干净、无削顶、restore OK）。它**永远不能**携带 `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`（该 token 仅由 R9 46 样本合法复测建立）。

## 3. 红线（§2 严禁，不变）

不降训练帧 corr 门、不升 residual 门（回归仍 0.05）、不绕过 fidelity gate、不把 `RF_DISTORTS_IQ` 强行送入模型、不用标签选同步/CFO/相位/增益/窗口、不改模型/标签/映射/预处理/RTL/XDC/位流/Flash、不静默覆盖 fix9r2（fix9r2 包 SHA 不变）。诊断模式**不得**输出回归 PASS。RF 安全上限 `kSafeTxCeilingDb=-40.0`/`kSafeTxAttenDb=-89.75` 不变。R8/R9 固定条件：center=2.4 GHz、TX atten=-40 dB、RX gain=30 dB、50Ω 同轴、无天线无放大。

## 4. 交付（§20 第一交付，host 已完成）

`fix9r2a_patch.tar.gz` + `fix9r2a_full.tar.gz` + `FIX9R2A_AUDIT.md`（本文档）+ `FIX9R2A_DELIVERY.txt` + 两份 `SHA256SUMS`。**各工件最终 SHA / 字节 / 文件数见交付清单**（`dist/RML23_IQ_RF_LOOPBACK_FIX9R2A_DELIVERY.txt`，不写入本文档以免自引用）。交付后停止，等 R8 2 样本 + R9 46 样本板测。

基线（fix9r2 全量，不变）：`sdr_rml23_live_board_package_iq_rf_loopback_fix9r2.tar.gz` = `ac9ed0b8ad979fe84818f447a9e8465444191e8595c5c19b9ab143b49a12d583`（578 内容文件）。

工件构成：补丁 7 内容文件（4 新增 + 3 修改）；全量 582 内容文件（575 fix9r2 字节一致 + 3 改 + 4 新，`SHA256SUMS.txt` 重生成）。

打包权限（§21，审计两包均 bad=0）：目录 0755 / `*.sh` 0755 / 其余 0644；禁 0666/0777；两跑确定性 + 独立解包 `sha256sum -c` + dependency closure + 无历史包覆盖 + fix10 零残留（两份接线脚本经 `_FIX10_REMOVAL` 剥离为 fix9r2a-only）+ 模型/标签/预处理/RTL/XDC/位流/Flash 未变。

R8（先）2 样本诊断与 R9（后）46 样本回归命令见 `dist/RML23_IQ_RF_LOOPBACK_FIX9R2A_DELIVERY.txt` §4（12 步）。
