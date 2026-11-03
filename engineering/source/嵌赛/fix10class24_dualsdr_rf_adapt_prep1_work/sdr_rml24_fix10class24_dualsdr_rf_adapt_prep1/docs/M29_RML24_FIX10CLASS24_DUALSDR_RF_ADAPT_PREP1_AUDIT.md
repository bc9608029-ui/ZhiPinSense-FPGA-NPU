# M29 fix10class24-dualsdr-rf-adapt-prep1 — 双 SDR 真实 RF 域适配准备（Phase A–H 全阶段脚手架）

最终状态：**`M29-RML24-FIX10CLASS24-DUALSDR-RF-ADAPT-PREP1-READY-FOR-DATA-CAPTURE`**

> 本状态令牌只出现在本文档。含义：**全阶段脚手架已就绪，等待真实 RF 采集**；不是 RF_PASS、
> 不是 SMOKE_PASS、不是 PROJECT_COMPLETE。本任务**未采集、未训练、未量化、未生成生产替换模型**。

---

## 0. 红线确认（全部遵守）

| 红线 | 处置 |
|---|---|
| 不碰板 / 不碰 SDR / 不碰 NPU | 遵守（全部 host-only、纯 stdlib；无任何板端/IQ 采集动作） |
| 不改 0.100 残差门 | 遵守（门 `GATE_*` 仅被**读取**为采集 gate_status，门值/阈值未改） |
| 不改恢复器 | 遵守（未触及任何恢复核心头文件/实现） |
| 不改标签 | 遵守（24 类标签序 SHA `3e1382d1…` 自测逐字节通过） |
| 不生成生产替换模型 | 遵守（无 `model_rml24_bf16/` 覆盖；编译脚本门禁在 go/no-go 且 fail-closed） |
| 不自动训练/量化 | 遵守（train/export/compile 均为 torch 门禁脚手架；本环境无 torch，实跑即拒绝） |

无 `board_package/`、`model_rml24_bf16/`、`model_rml24_tf32/` 等既有文件的任何改动。

## 1. 交付物清单（Phase A–H）

所有文件在 `sdr_rml24_fix10class24_dualsdr_rf_adapt_prep1/` 工作树下。

| Phase | 交付物 | 路径 |
|---|---|---|
| A 源/数据资产清单 | 11 行资产分层 | `results/rf_adapt_prep1/asset_inventory.tsv` |
| B 数据合同（机器可读） | 冻结身份/标签/计划/划分/门禁/训练规格 | `contracts/rml24_dualsdr_rf_dataset_v1.py` |
| B 数据合同（人类可读） | 字段级 schema §1–§8 | `contracts/rml24_dualsdr_rf_dataset_v1.md` |
| C 采集计划 | 960 行 TSV（Pilot 240 + Formal 720） | `plans/rml24_dualsdr_rf_capture_plan_v1.tsv` |
| D 数据集生成 + 防泄漏划分 | fail-closed builder | `scripts/build_fix10class24_dualsdr_rf_dataset.py` |
| E 训练脚本 | 36 组合预注册训练（torch 门禁） | `scripts/train_fix10class24_rf_adapt.py` |
| E 训练配置 | 预注册 pilot 规格 YAML | `training/configs/fix10class24_rf_adapt_pilot.yaml` |
| F 评估脚本 | F1/F2/F3/F4 | `scripts/evaluate_fix10class24_rf_adapt.py` |
| F 导出脚本 | ONNX opset17 导出 | `scripts/export_fix10class24_rf_adapt_onnx.py` |
| F 编译脚本 | BF16/TF32 编译（go/no-go 门禁） | `scripts/compile_fix10class24_rf_adapt_{bf16,tf32}.py` + `scripts/rfadapt_compile_common.py` |
| G 合成/已有数据流水自测 | selftest 生成器 + 真跑 | `scripts/build_fix10class24_rf_adapt_prep1_selftest.py` |
| H 单/双 SDR 验证计划 | F2(单SDR)/F3(双SDR) 冻结集 + 采集手册 | `results/rf_adapt_prep1/frozen_evaluation_sets.tsv` + `docs/…_CAPTURE_GUIDE.md` |
| 自测 | 两个 host 测试 | `host_tests/test_fix10class24_rf_dataset.py`、`host_tests/test_fix10class24_rf_training_contract.py` |
| 静态产物 | 计划摘要 / 自测结果 | `results/rf_adapt_prep1/dataset_plan_summary.json`、`results/rf_adapt_prep1/pipeline_selftest.json` |

## 2. 冻结身份（合同 `FROZEN`，逐字节不变）

| 字段 | SHA256 |
|---|---|
| FP32 checkpoint（适配初始化点） | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` |
| ONNX opset17 | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` |
| 24 类标签合同 | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` |
| 生产 BF16 json / raw | `28272abc…` / `c1781aec…`（**永不被覆盖**） |
| TF32 A/B json / raw | `8d00a1c3…` / `f8366a10…`（**永不被覆盖**） |

全合同身份戳 `dataset_contract_sha256()` = `89175c2140b593c7a4592fee2308a8adf364bd5a29dab5fad14f2c88b71218d2`。

## 3. 关键设计（source_index 隔离 + 防泄漏）

- `source_index = raw24_class_index * 500 + intra_class_offset`，全局唯一。
- Pilot offset 0..9，Formal offset 10..39；Formal 按 offset 确定性划分
  `train=10..27 / val=28..33 / test=34..39`（三组互不相交且覆盖 Formal）。
- 防泄漏：物理捕获（source_index）只出现在一个 split；clean24_smoke 是冻结回归集，
  **永不**进入 train/val/test；clean 回放池与 clean24_smoke 按 SHA 判不相交，否则 fail-closed。
- 门禁：train/val/test 只收 `PASSED`；`DIAGNOSTIC_PROVISIONAL` 仅进 pilot；`REJECTED` 丢弃并记录。

## 4. 自测结果（真实执行，非声明）

### 4.1 流水自测 `python -I scripts/build_fix10class24_rf_adapt_prep1_selftest.py`

```
contract_consistent=true
plan_row_count=960 (pilot 240 / formal 720)
plan_source_indices_unique=true
split_leakfree=true
config_yaml_matches_spec=true
builder_accepted=5  builder_rejected=1  builder_manifest_rows=5
builder_split_counts={train:2, val:1, test:1, pilot:1}
builder_contract_sha_matches=true  builder_report_written=true
all_passed=true  (EXIT=0)
```

### 4.2 host 测试（`python -I`，纯 stdlib）

| 测试 | 结果 |
|---|---|
| `host_tests/test_fix10class24_rf_dataset.py` | **15 passed / 0 failed** |
| `host_tests/test_fix10class24_rf_training_contract.py` | **11 passed / 0 failed** |

合计 **26 passed / 0 failed**。训练契约测试覆盖：预注册规格、36 组合枚举、validate_run 接受/拒绝、
checkpoint SHA 门禁（错文件/缺失两路拒绝）、F4 三种子统计、go/no-go 编译门禁三例、
`--enumerate` 子进程在无 torch 下可跑（证明脚本纯 stdlib 路径可用）。

## 5. 门禁与 fail-closed 语义

- `train_fix10class24_rf_adapt.py`：`verify_checkpoint()` 先 SHA 校验 FP32 checkpoint 才允许
  训练；`load_dataset()` 是**故意留空**的 fail-closed stub——真实 loader 在训练仓库按冻结划分契约
  接线，杜绝半接线 loader 静默用 test 训练。
- `compile_…_bf16.py` / `compile_…_tf32.py`：`check_go_gate()` 要求 `go=true` 且
  `candidate_test_accuracy > baseline_test_accuracy`，否则拒绝编译；无 `--sdk-compile` hook 时
  只打印 iCraft 手动流程，不产模型。
- 输出目录 `model_rml24_rfadapt_bf16/`、`model_rml24_rfadapt_tf32/`、`model_rml24_rfadapt_fp32/`
  全部是**新目录**，绝不覆盖生产 `model_rml24_bf16/` 或兄弟 `model_rml24_tf32/`。

## 6. 打包与 SHA

新增文件打补丁包 `dist/sdr_rml24_fix10class24_dualsdr_rf_adapt_prep1_patch.tar.gz`，
其 sha256 与逐文件清单见 `dist/SHA256SUMS.txt`（包内含全部 20 个本任务新增文件，不含任何
既有 baseline/board_package 文件）。

## 7. 后续（不在本任务范围）

1. 用户按 `docs/M29_RML24_FIX10CLASS24_DUALSDR_RF_ADAPT_PREP1_CAPTURE_GUIDE.md` 执行 Pilot/Formal
   真实 RF 采集（碰板/碰 SDR 动作由用户执行）。
2. 采集后跑 builder 生成 `datasets/rml24_dualsdr_rf_v1/`，读 `build_report.json`。
3. 训练环境跑预注册 36 组合（仅 val 选模），评估 F1–F4，产出 go/no-go JSON。
4. 仅当候选在独立 test 上超原模型才允许 export + compile（BF16/TF32）。
