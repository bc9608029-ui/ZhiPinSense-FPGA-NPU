# M29 RML23 Route F — fix9r2g1 baseline 生产/消费合同修复审计与验收记录

状态：**`M29-RML23-FIX9R2G1-BASELINE-CONTRACT-READY-FOR-R8-BOARD-TEST`**（状态上限）
基线：fix9r2g 全量 `sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g.tar.gz`
（SHA `feb30403e08924e83945ec23d75a2d6bb46213bba9bb15a7ef96ebd2c55e808e`）

> 本文档记录 fix9r2g1 的最小热修：**只修 baseline 的生产/消费合同**（Python 生成器
> 5 列 → 6 列 + 真实冻结模型预测 TSV + 端到端测试）。**不改** fix9r2g 的 RF 算法、
> 训练块、模型、门限或 R8 条件。红线：**我禁碰板**；禁止 `RF_PASS / RF_PATH_PROVEN /
> ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS / FIX10_READY / PROJECT_COMPLETE / FINAL_*`；
> 标签/`deployed_class` 不得充当 `frozen_baseline_pred`。

---

## 1. 根因（fix9r2g 交付缺陷，R8 在 RF 启动前必然失败）

fix9r2g 全量包内 `scripts/build_route_f_fix9r_exact_baseline.py` 是**旧 5 列版**
（10068 字节）：

```
BASELINE_HEADER = ["source_index", "original_sha256", "deployed_class",
                   "modulation", "split_role"]          # 无 frozen_baseline_pred
```

- 无 `--predictions` 参数、无 `frozen_baseline_pred` 列；docstring 明确写着
  「`deployed_class` 就是 baseline prediction，模型不重跑」——即**用真值标签冒充
  冻结预测**（被红线禁止）。
- 而 C++ 解析器 `board_package/iq_rf_fix9r_baseline.hpp` 的 `load_baseline()` 要求
  **6 列**且逐行 fail-closed（`p.size() < 6 → throw`）。5 列输出在 R8 读 baseline
  时**必然抛异常**，发生在任何 RF 启动之前。

本热修（fix9r2g1）只补这一合同缺口：交付 **6 列生成器** + **每个 holdout 的真实
离线模型预测** + **端到端测试**（Python 生成器 → C++ `load_baseline()` 读回）。

---

## 2. 6 列生成器（`scripts/build_route_f_fix9r_exact_baseline.py`）

- 大小 16492 字节，SHA `086a72e021f4a81080ead4b87f44b674ed9f006ff987abdd11cc758fb36b56a8`。
- `BASELINE_HEADER = ["source_index", "original_sha256", "deployed_class", "modulation",
  "split_role", "frozen_baseline_pred"]`（6 列）。
- `PRED_HEADER = ["source_index", "file_name", "frozen_baseline_pred"]`（3 列预测 TSV）。
- 新增 `--predictions`（**必填**：API 机不能离线跑模型）、`parse_predictions()`、
  `attach_predictions()`（按 `source_index` **精确键**匹配，缺失/多余/重复/越界 → fail-closed）。
- `--self-test` 11/11 通过（含「frozen != deployed」与「缺失/重复预测 fail-closed」）。

## 3. 真实冻结模型预测（`scripts/route_f_fix9r_predictions.tsv`）

- 大小 1983 字节，SHA `9e9349dce2962d5c6f48a84a56bba153d870f2a647322de13f465a4ba4f360ac`；
  3 列 46 行（46 个 holdout）。
- 由 `scripts/predict_fix9r_frozen_baseline.py`（6936 字节，SHA
  `0bf70176adaaa98cf6ad92dd546021288983821c677b1e4cba8038e320bf8797`）**确定性推理**
  生成：载入冻结 checkpoint `96cd25f8…`（epoch=50，`class_names == LABEL_ORDER_24`），
  构建 24 类 `ADAMRV11Net`（`load_state_dict(strict=True)` + `.eval()` + `inference_mode`），
  对 46 个 D2 recovered tensor（`[2,1024]` fp32 平面实/虚，RMS≈1.0）各跑一次前向，
  取 `frozen_baseline_pred = SOURCE_TO_DEPLOYED[argmax_24class_logits]`。
- **不是 `deployed_class` 填充**：预测由真实前向推理产生；AM 合并已验（raw24=17/18
  均 → deployed 17）。该映射恒成立（`rml23_merged.hpp` 的 `merge_logits_23` logaddexp
  单调折叠，argmax 保持 24→23 映射）。

**为什么这 46 个预测恰与 `deployed_class` 全部一致**：46 个 holdout 均在 SNR 20/22 dB，
冻结模型在高 SNR 闭集准确率接近 100%，故 `frozen_baseline_pred == deployed_class`
对全部 46 个成立是**模型高精度所致**，而非标签回填。端到端测试（§4）用合成样本
令 `frozen_baseline_pred != deployed_class` 对全部 46 个成立，证明生成器**逐字节
透传**给定预测、绝不回退标签。

## 4. 端到端测试（`host_tests/test_iq_rf_loopback_fix9r2g1_baseline_e2e.cpp`）

- SHA `a9a93fdcade70b5f3f972a5369215c0b8b72508d62c53cd8417538acb8105e86`（10435 字节）。
- 流程：真实格式 24 列 D2 manifest（46 holdout + 184 calib）+ 真实格式 3 列预测 TSV
  → `python3 -I <正式生成器> --d2-manifest … --predictions … --out …` → 正式 C++
  `iqrffix9r::load_baseline()` 读回。
- 断言：生成器退出 0；baseline 头 6 列；46 行；每行 6 列；`load_baseline()` 返回 46
  行且 `frozen_baseline_pred` 对全部 46 源精确保留；`frozen != deployed`（不回退）。
- 缺失预测（丢 1 个 source_index）→ 生成器非零退出（fail-closed）；重复预测
  （source_index 重复）→ 生成器非零退出（fail-closed）。
- 结果：**pass=9 fail=0**（WSL g++ `-std=gnu++17 -Wall -Wextra -Werror` 编译通过）。

## 5. 板端 R8 命令（我禁碰板，由用户执行；本热修不要求重跑已失败 RF）

与 fix9r2g §8 相同，但 `--baseline` 现在由 6 列生成器产出：

```bash
python3 -I scripts/build_route_f_fix9r_exact_baseline.py \
  --d2-manifest "$D2_SMOKE_DIR/route_d2_rf_manifest.tsv" \
  --predictions scripts/route_f_fix9r_predictions.tsv \
  --out route_f_fix9r_exact_baseline.tsv --expect-holdout 46

./scripts/run_gate9_rml23.sh \
  --phase=iq-rf-loopback-23class-fix9r \
  --input-kind=radioml-d2-2p56m \
  --frozen-dir="$D2_SMOKE_DIR" \
  --baseline=route_f_fix9r_exact_baseline.tsv \
  --diagnostic-classes=BPSK,4ASK \
  --diagnostic-per-class=1 \
  --center=2400000000 --rx-gain=30 --tx-atten=-40 \
  --rf-path=direct-cable --rf-tx-target-rms=2048
```

## 6. 明确 NOT changed（红线）

- **不改** `iq_rf_training_frame.hpp` / `iq_rf_sync_recovery.hpp` /
  `iq_rf_tx_provenance.hpp` / `iq_rf_loopback_23class_fix9r.hpp` / 诊断头 / 门限 /
  模型 / 预处理 / NPU / 均衡器 / R8 条件；不碰 fix10/46 样本/690/clean-23。
- 本热修仅 4 类内容文件：6 列生成器（MODIFIED）、预测推理脚本 + 预测 TSV（NEW）、
  端到端测试（NEW）、build/run 接线（MODIFIED）、本文档（NEW）、打包器（NEW）。
