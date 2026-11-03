# M29 RML23 FIX10 三路径审计（双 SDR 空口 + 纯净 IQ + 同源对拍）

- 状态：**M29-RML23-FIX10-DUAL-SDR-CLEAN-IQ-PREP-READY-FOR-BOARD-TEST**（最高允许；禁写
  `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS / FIX10_READY / RF_PASS / RF_PATH_PROVEN /
  PROJECT_COMPLETE / FINAL_*`）
- 日期：2026-10-15
- 工作树：`F:\嵌赛\fix10prep_work\sdr_rml23_live_board_package_iq_rf_loopback_fix9r2h2`
- 我禁碰板；板端命令由用户执行。

---

## 0. 基线更正（重要）

本 fix10-prep 工作树的真实基线是 **fix9r2h2**，不是早期 memory 里记录的 fix9r2g1。

依据：把 fix10-prep 工作树对 fix9r2g1 manifest（`e3db0872…`，602 文件）求差，工作树既包含
fix9r2h / fix9r2h1 / fix9r2h2 的 Route F 变更（narrower payload training、共享 residual
gate、tx-scale 合同），又包含本 fix10-prep 增量。`fix9r2g1_work` 树后来被继续推进到
fix9r2h3 / h3a / h4 / h5（Route F 延续），故早期「`diff -rq` 一致」的注记只在分支时刻成立，
现已过期。

因此：**fix10-prep patch = 对 fix9r2h2 基线的增量**（13 新增 + 4 接线修改，见 §2）；
**full = 完整 fix9r2h2 + fix10-prep 树**。fix9r2h* 的 3 份审计文档与 7 个 Route F 头是
fix9r2h2 基线的一部分，**不属于** fix10-prep patch（它们随 full 一起打包，不随 patch 变更）。

---

## 1. 三条独立可审计路径

在 **不改模型/权重/标签/24→23 映射/门禁** 的前提下，新增三条独立路径，用同一个部署模型
做交叉验证：

- **Path A（RadioML 双 SDR）**：RadioML CI16 → TX SDR → 同轴/RF → RX SDR → 共享恢复核心 →
  部署模型。
  - `sdr_adapter/pluto_dual_air_link.hpp`（N1，双设备空口抽象）
  - `board_package/iq_dual_sdr_transfer_fix10.hpp`（N2，双 SDR 传输）
  - `board_package/iq_dual_sdr_coarse_cfo_recovery.hpp`（coarse-CFO 修复）
  - `board_package/iq_dual_sdr_23class_fix10.hpp`（N3，双 SDR 23 类 runner）

- **Path B（generated-clean 数字基线）**：受控干净调制 → CI16 → 既有 PreprocessChain →
  D2 恢复 → 部署模型。
  - `board_package/iq_clean_baseline.hpp`（N4a，clean 基线加载器，host 可测）
  - `board_package/iq_clean_iq_23class_fix10.hpp`（N4，clean 数字 runner）
  - `scripts/gen_generated_clean_23.py`（N5，干净 CI16 生成器）
  - `scripts/predict_clean_baseline.py`（N6，冻结离线基线）

- **Path C（generated-clean 双 SDR）**：同一干净 CI16 → TX SDR → 同轴/RF → RX SDR → 恢复 →
  同一部署模型 → 逐样本对拍（复用 Path B 工件 + Path A 传输机制）。

---

## 2. fix10-prep 变更集（对 fix9r2h2 基线的精确增量）

### 新增（13）

| 文件 | 说明 |
|---|---|
| `sdr_adapter/pluto_dual_air_link.hpp` | N1 双设备空口抽象 |
| `board_package/iq_dual_sdr_transfer_fix10.hpp` | N2 双 SDR 传输 |
| `board_package/iq_dual_sdr_coarse_cfo_recovery.hpp` | coarse-CFO 修复 |
| `board_package/iq_dual_sdr_23class_fix10.hpp` | N3 双 SDR 23 类 runner |
| `board_package/iq_clean_baseline.hpp` | N4a clean 基线加载器（host 可测，无 NPU 后端依赖） |
| `board_package/iq_clean_iq_23class_fix10.hpp` | N4 clean 数字 runner |
| `scripts/gen_generated_clean_23.py` | N5 干净 CI16 生成器 |
| `scripts/predict_clean_baseline.py` | N6 冻结离线基线 |
| `host_tests/test_iq_dual_sdr_fix10.cpp` | N7 双 SDR 25 用例 |
| `host_tests/test_iq_dual_sdr_23class_fix10.cpp` | Stage 2 双 SDR runner 测试 |
| `host_tests/test_clean_iq_23class_fix10.cpp` | N8 纯净 IQ E2E |
| `scripts/package_dual_sdr_clean_iq_fix10prep.py` | N9 打包器 |
| `docs/M29_RML23_FIX10_DUAL_SDR_CLEAN_IQ_PREP_AUDIT.md` | N10 本文档 |

### 修改（4，仅接线，不碰模型/标签/预处理）

| 文件 | 说明 |
|---|---|
| `board_package/gate9_phase.hpp` | 新增 `iq-dual-sdr-23class-fix10`、`iq-clean-iq-23class-fix10` |
| `board_package/board_gate9_full_chain_rml23.cpp` | 新增两条 phase dispatch + wrapper |
| `host_tests/build_host_tests.sh` | 编译两个新测试 |
| `host_tests/run_tests.sh` | 运行两个新测试 |

---

## 3. 关键口径

### AM-SSB（#17）—— 已拍板，两者都纳入

- R9 的部署类 17 使用 **1× AM-SSB-WC（raw24=17）+ 1× AM-SSB-SC（raw24=18）**，二者均映射
  到 deployed23=17。
- `SOURCE_TO_DEPLOYED = [0..16, 17, 17, 18..22]`；`kSourceClassCount=24`、`kDeployedClassCount=23`、
  `kNpuOutputDim=24`。
- 保留 `source_class=17/18` 用于审计。
- **`frozen_baseline_pred` 必须由真实 24 类模型 logits 经既有 24→23 合并后 argmax 得到**，
  **禁止用 `deployed_class` 回填**（否则「预测一致」退化成「分类正确」，语义造假）。
- R8 仅含 BPSK / 4ASK，不涉及 AM-SSB 选择。

### 干净生成器（N5）参数

- `BASE_SEED=0x5EEDC1E4`；24 raw source 类 × 30 = **720 文件**（AM-SSB 两者都包含）。
- `FS_BASE=128000`、`SPS=8`、`SYMBOL_RATE=16000`、`ROLLOFF=0.35`、`SPAN=8`、`GLOBAL_K=2048`、
  `GUARD=832`；splitmix64 确定性种子。

### 纯净 IQ 数字链（Path B）恢复契约

- `chain::PreprocessChain`：int16 → ÷2048.0f → NCO mix → polyphase StreamResampler
  （2.56 MHz → 128 kHz）→ frame 1024 → `[2,1024]` fp32 × rec_scale。
- `load_frozen_iq(dir,"radioml-d2-2p56m")`、`load_d2_sidecar`（24 列 manifest，fail-closed）、
  `load_ci16`、`apply_d2_restore_to_stream`、`select_classification_window`。
- **N8 实证**：24 个干净文件逐文件全链 corr=1.000000 / nmse=0.000000 / delay=263 ——
  C++ 数字链与 Python 生成器恢复张量逐位一致。

### coarse-CFO 修复（Path A）—— 已完成（τ0 分数采样偏移偏置根因）

- **根因**：差分 CFO（`differential_cfo_hz`）被循环采集下前导**任意分数采样偏移 τ0** 偏置，
  偏置 = −τ0·fs/N（τ0∈[−0.5,0.5] → 最高 ±1250 Hz；实测 full-impairment 下 357.5 Hz vs 真
  200 Hz）。τ0 不可知（rx_stream_pos 累积 + SRO + CFO 峰移；抛物线相关峰拟合也被 CFO 非对称
  位移破坏；双根差分消偏 D_tail 因 CFO 峰移 r-dependent 也失败）。
  （先排除了 SRO：实测 20 ppm 仅 +0.23 Hz。）
- **修复**：改用**前导(ZC root1) vs payload 训练块(16QAM) LS 增益相位差**（baseline
  `kPayloadTrainingOffset=2048`，±625 Hz 无歧义）作 coarse CFO，替换 raw 差分——每个 LS 增益
  各自吸收自身 τ0，CFO 相位展宽在两 1024 块相同而相消。
- **实测**：medium_cfo=197.45（vs 真 200），rec.valid=1、pay_res=0.0346（原 0.1547）。
- 改 `iq_dual_sdr_coarse_cfo_recovery.hpp`；**未改 `iq_rf_sync_recovery.hpp` 同步数学**（红线，
  禁碰）。差分 CFO 仍记录于 `rec1.coarse_cfo_hz` 供审计，仅不再作 applied coarse。

---

## 4. 验证结果（host，不碰板）

| 项 | 结果 |
|---|---|
| `test_clean_iq_23class_fix10`（N8） | **pass=26 fail=0**（基线加载 8 fail-closed 拒绝 + 全链 corr 实证 + phase surface） |
| `test_iq_dual_sdr_fix10`（N7） | 36/0 |
| `test_iq_dual_sdr_23class_fix10`（Stage 2） | 23/0 |
| 语法检查 | 4/4 |
| 全量 build + run_tests | ALL PASSED |

---

## 5. 红线（NOT changed）

- 不改模型 / 权重 / 标签 / 24→23 映射（`rml23_merged.hpp` 未动）/ 门禁。
- 不改 `iq_rf_sync_recovery.hpp` 同步数学。
- 不碰 Phase 2 / 46 样本 / 690 / clean-23 正式运行。
- 不写任何 `PASS / PROVEN / READY` 之外的红线 token。

## 6. 打包产物

见 `scripts/package_dual_sdr_clean_iq_fix10prep.py`（N9）：patch + full 两工件，§21 全项
（确定性两跑、独立解包 SHA、依赖闭包 fail-closed、fix9r1/旧 fix10 零残留、模型/标签/预处理
字节一致、权限 0755/0644）。
