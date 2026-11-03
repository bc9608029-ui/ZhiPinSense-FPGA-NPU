# M29-RML24-FIX10CLASS24-CLASSIFICATION-GATE-SEPARATION1 — 板测手册 (Part B 诊断旁路)

**状态 token** `M29-RML24-FIX10CLASS24-CLASSIFICATION-GATE-SEPARATION1-READY-FOR-BOARD-TEST`
**性质** 纯离线 BOARD-PREP。板端 C++ 未在本环境编译（无 aarch64 g++），未上板实测。

---

## 1. 本任务做什么

把「保真门」(0.100 残差) 与「分类门」(NPU24 argmax) 分离：新增 `--diagnostic-force-classify`
(默认 OFF)，对**仅因残差在 (0.100, 0.30] 被拒**、但对齐/恢复/负控仍有效的捕获，做一次**诊断**
分类，写入**独立** `board_diagnostic_results.tsv`（`classification_layer=NPU_BF16_DIAGNOSTIC`,
`diagnostic_gate_bypass=1`）。生产 19 列 `board_results.tsv` 与 0.100 门**逐字节不变**。

## 2. 交付物（PATCH，叠加在 dc-ab1 integrated PATCH 之上）

- `board_package/radioml_diagnostic_classify.hpp`（新，单一权威：旁路条件 + 诊断再恢复）
- `board_package/radioml_singlesdr_ab_runner.hpp` / `radioml_dualsdr_ab_runner.hpp`（改：加 flag + 诊断分类分支）
- `contract/classification_gate_separation_contract.{md,json}`
- `scripts/judge_radioml_gate_separation.py`（统一判定器）+ `scripts/run_radioml_gate_separation.sh`
- `host_tests/test_radioml_gate_separation.py`（7/7）

## 3. 板测步骤

### 3.1 基线（诊断 OFF，应逐字节复现 dc-ab1）

```bash
# single-SDR direct（生产基线，诊断 OFF 默认）
bash scripts/run_radioml_gate_separation.sh \
    --sdr=single --mode=short24 --adaptation=direct \
    --input-dir=<DIRECT tx payload pkg> --rx-uri="<SDR uri TX+RX>" \
    --out-dir=/root/rml24_gs_single_direct_$(date +%s)
```

断言：`board_results.tsv` 与 dc-ab1 单 SDR direct 运行一致（无 `board_diagnostic_results.tsv`）。

### 3.2 诊断 ON

```bash
bash scripts/run_radioml_gate_separation.sh \
    --sdr=single --mode=short24 --adaptation=direct --diagnostic-force-classify \
    --input-dir=<DIRECT tx payload pkg> --rx-uri="<SDR uri TX+RX>" \
    --out-dir=/root/rml24_gs_single_direct_diag_$(date +%s)
```

断言：`board_results.tsv` 仍与 3.1 **逐字节一致**；`board_diagnostic_results.tsv` 出现
（仅 (0.100,0.30] 残差且对齐/负控有效的帧）；`summary.json` 六项统计一致。

dual / dc-transport 同理（dual 需先起 PC TX 服务 `pc_tx_radioml_dualsdr.py launch
--adaptation=<同板端>`）。

### 3.3 主机判定（拷回 $OUT_DIR 后）

```bash
python -I scripts/judge_radioml_gate_separation.py \
    --input-package <npu-ab1 input_package> \
    --board-single-direct <board_results.tsv> \
    --diag-single-direct <board_diagnostic_results.tsv> \
    --runner-summary-single-direct <summary.json> \
    [--blind-single-direct <Part A 盲 board_results.tsv>] \
    --out-dir <fresh judge dir>
```

## 4. 板测红线

- 诊断 OFF 时生产行为**不得**有任何变化（19 列、0.100 门、board_pred 语义全不变）。
- `hard_invalid` 帧**绝不**被旁路到成功；`board_diagnostic_results.tsv` 绝无 `hard_invalid` 帧。
- 旁路仅当 7 条显式条件全真；`apply()` 安全 guard 拒绝即 `diagnostic_bypass_apply_failed`。
- 板端构建 `make -j1`（冻结 scalarwl 头 sign-compare `-Werror` 坑，见 npu-ab1 备注）。
- `run_gate9_rml23.sh` 默认 23 类 `--rx-gain=10`；本脚本已显式 24 类 BF16 + `--rx-gain=35`。
