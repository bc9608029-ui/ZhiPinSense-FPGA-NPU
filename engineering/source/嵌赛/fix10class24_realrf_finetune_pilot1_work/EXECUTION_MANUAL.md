# M29-RML24-REALRF-FINETUNE-PILOT1 — 执行手册（EXECUTION_MANUAL）

> 目标：用最小但可信的真实 RF 数据（960 帧 = 4 会话 × 24 类 × 10）判断现有 RadioML
> 预训练模型是否值得微调。离线准备阶段**不上板、不发射、不训练**；板端采集由用户串口
> COM12 执行。本手册已按评审（id=39e5）三轮整改收口——一轮 9 项（集成完整性）、
> 二轮 4 阻塞（独立性 fix2）、三轮 2 阻塞（runner 编译 + 接收端真值隔离），离线侧全部
> 补齐并复验通过。

## 1. 四线结构与离线状态

| 线 | 目录 | 职责 | 状态 |
|---|---|---|---|
| 主线程 | `contract/` + 根目录 | 冻结共享合同、协调、一致性核验、集成 | ✅ 一致 18/18 |
| A | `line_a/` | 源数据/训练资产 + 960 选样（S1–S4 输入包） | ✅ `TRAINABLE_CHECKPOINT_FOUND` |
| B | `line_b/` | 采集链（TX payload S1–S4 + 32 字段 schema + 24 帧 e2e 模拟 + runbook） | ✅ `READY_FOR_BOARD_CAPTURE` |
| C | `line_c/` | 数字基线 + 判读器 + E0–E3 训练框架 + 评估入口 | ✅ 框架+自测通过 |

**六选一终态**（禁止写 RF_PASS/PROJECT_COMPLETE/FINETUNE_SUCCESS）：
`FINETUNE_PROMISING` / `FINETUNE_MARGINAL` / `FINETUNE_NO_GENERALIZATION` /
`DATA_PIPELINE_INVALID` / `BLOCKED_NO_TRAINABLE_CHECKPOINT`（已排除）/
`READY_FOR_BOARD_CAPTURE`（当前离线终态）。

## 2. 冻结身份（核验已 PASS）

| 工件 | SHA256 |
|---|---|
| 模型 json / raw | `28272abc…` / `c1781aec…` |
| 训练 checkpoint best.pt | `96cd25f8…`（合同已修正笔误，`96cd25f87d6f6f8…`） |
| HDF5 | `e3dd0bef…` |

## 3. 离线交付物

```
contract/shared_contract.py + SHARED_CONTRACT.md   # 32 字段 + 冻结身份 + 红线
consistency_check.py                               # 主线程一致性核验（18/18 PASS）
requirements.txt + ENVIRONMENT.md                  # 环境锁定（评审 #9：torch 在用户 site）
line_a/  select_960_sources.py + source_manifest_960.tsv + inputs/S{1..4}/*.bin
         trainable_asset_inventory.json + DATA_PROVENANCE.md
line_b/  export_finetune_tx_payload.py + radioml_dualsdr_common.py
         tx_payload/S{1..4}/*.i16                  # S1–S4 四会话 TX payload 全齐
         CAPTURE_SCHEMA.md + BOARD_CAPTURE_RUNBOOK.md + selftest_capture_schema.py
         run_e2e_sim.py                            # 24 帧端到端模拟（评审 #8 干净目录验证）
line_c/  run_digital_baseline.py + judge_realrf_pilot.py + audit_split.py
         train_finetune_pilot.py + evaluate_finetune_pilot.py + selftest_line_c.py
         METRIC_CONTRACT.md + TRAINING_PROTOCOL.md
```

**板端单一部署包**（评审 #2，位于板端树 `sdr_rml24_fix10class24_dualsdr_rf_adapt_prep1`
的 `dist/`）：

```
sdr_rml24_fix10class24_realrf_finetune_pilot1_patch.tar.gz          # 18 文件（10 新 + 8 改）
sdr_rml24_fix10class24_realrf_finetune_pilot1_patch_SHA256SUMS.txt
# HELLO fixed-scale 修复后 SHA256 = d9fe89704032a004de71bddc7733f7e86080f147182ddb71112aa204810e3e66
# 旧 945322c7d4a4a2cce583862dd5c003bde939d29873767111f3fdc2f57471284d 作废。
```

该 PATCH 在「rxrecovery1 FULL + singlesdr-ab1 PATCH + scalarwl-4way PATCH +
rf-adapt-prep1 PATCH」四层已部署板上叠加；含真实 PC-TX 服务
（`host_tools/pc_tx_radioml_dualsdr.py`）、板端采集 runner
（`board_package/pilot1_capture_runner.hpp`）、32 字段 schema/manifest 头、
host 测试（`test_pilot1_capture` + `pilot1_e2e_sim` + `pilot1_capture_runner_syntax`）与
运行脚本（`scripts/run_pilot1_capture.sh`）。三轮新增/变更两处关键收口：`syntax_check.sh`
接入 full-runner `-fsyntax-only` TU（评审 39e5 Blocker 1）；`host_tools/build_burst_cli.cpp`
把 `--target-rms 0` 由「拒绝」改为「原样透传」（固定公开幅度 S，independence fix2），使 PC TX
服务 `--rf-tx-target-rms 0` 路径真正可用（`tx_scale=1.0`、`payload_sha_post==pre`，已通过
WSL g++ `-Werror` 编译 + `--self-check` 复验）。

现场首次 HELLO 进一步发现共用 `fix10_tx_protocol.py` 仍保留旧的 `target_rms > 0`
校验；现已按 input_kind 隔离修复：`radioml-finetune-pilot1` 只接受有限的 `target_rms == 0`，
旧 input_kind 仍只接受有限正数。协议正反例 41/41、24 帧端到端模拟及确定性打包均通过。
打包器 `scripts/package_fix10class24_realrf_finetune_pilot1.py` 已过红线头/受保护目录/
依赖闭包/完整增量/自包含/确定性/独立解包全审计。

## 4. 执行流程

### 4.1 离线核验（已做，可复跑；解释器分工见 §7）

```sh
cd /d F:\嵌赛\fix10class24_realrf_finetune_pilot1_work
python -I consistency_check.py                                  # 主线程 18/18
python -I line_b/scripts/selftest_capture_schema.py             # 线 B 全 PASS
python -I line_c/scripts/selftest_line_c.py                     # 线 C 全 PASS（契约级）
python -I line_b/scripts/run_e2e_sim.py                         # 24 帧 e2e 模拟 PASS
python   line_c/scripts/train_finetune_pilot.py --selftest      # 训练循环可达（需 torch）
```

### 4.2 数字基线（主机，离线）

```sh
python -I line_c/scripts/run_digital_baseline.py --limit 0   # 960 样本 Host BF16（可续跑）
# 产出 line_c/results/digital_baseline_960.tsv（数字基线错误不删除）
```

### 4.3 板端采集（用户，串口 COM12，按 line_b/BOARD_CAPTURE_RUNBOOK.md）

在板上按 §3 的 base 链叠加 `realrf_finetune_pilot1_patch.tar.gz` 后，**先在部署树根目录
跑 aarch64 构建**（评审 39e5 Blocker 1；脚本在 `scripts/` 下）：

```sh
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 \
ICRAFT_CMAKE_DIR=/usr/cmake \
taskset -c 0 bash scripts/build_on_board.sh
# 构建成功必须看到以下两行，才允许进入四会话采集：
#   NPU_BUILD_RESULT gate=9R result=PASS
#   RML23_BUILD_RESULT result=PASS
```

再跑四个会话 S1/S2/S3/S4 各 240 帧（`bash scripts/run_pilot1_capture.sh ...`，见
BOARD_CAPTURE_RUNBOOK §2.2）；save-before-gate，门拒/失败/hard-invalid 不剔分母；S4
密封。板端只持 3 列公共 manifest（身份 + TX payload SHA），真值列离线回填。回传 `$OUT`
（32 字段 capture TSV + raw_rx/model_input/logits + run.log）。

### 4.4 判读（离线，回传后）

```sh
python -I line_c/scripts/judge_realrf_pilot.py \
    --capture-tsv <32字段TSV> --baseline-tsv line_c/results/digital_baseline_960.tsv \
    --ground-truth line_a/results/source_manifest_960.tsv
# 出六选一判级（METRIC_CONTRACT §2）；先验身份/SHA/四轮重叠，任一违例 DATA_PIPELINE_INVALID
# --ground-truth 按 source_id 离线回填真值列，并 fail-closed 断言板端未带回真值（39e5 Blocker 2）
```

### 4.5 （可选）微调（仅在判级 PROMISING/MARGINAL 之后，TRAINING_PROTOCOL.md）

E0–E3 从原 checkpoint 初始化，S3 选模，S4 密封一次评估；Host 候选显著优于 E0 之前不转
NPU、不上板、不替换生产链。训练/评估入口均已可达（`--train` / `--unseal-s4`）。

## 5. 红线（全程）

不训练（采集前）/ 不碰板 / 不操作 SDR / 不发射 / 不改生产恢复·门·协议 / 不从 NPU RAW
反推权重 / 960 分母固定不剔 / 接收端不读类别·原始载荷 IQ·oracle 参数 / Ethernet 只传
整轮控制与文件 / S4 密封 / 主指标只用原始 RadioML 实例 / 四轮零重叠 / 不写三个禁写终态。

## 6. 交付状态与下一步

**一轮评审（9 项）已全部收口**：S2–S4 输入包、真实 PC-TX + 板端 RX runner、单一部署包、
正式训练循环、可达评估入口、判读器 960 分母、S4 封存、环境锁定、干净目录 24 帧端到端
模拟（均复验通过）。

**二轮评审（NEEDS-INDEPENDENCE-FIX2，4 阻塞）已全部收口**：
1. **板端输入合同**：删 `--input-dir`、不读 `.i16` 逐样本 `tx_scale`，用**固定公开幅度
   S**（`TX_DIGITAL_SCALE=68.46059377833956`、`TX_TARGET_RMS=0`）；TX manifest 拆三份——
   板端公共 3 列（`session_id`/`source_id`/`tx_payload_sha256`，绝不含类别真值）、PC 私有
   5 列（`seq`/`session_id`/`source_id`/`tx_payload_file`/`tx_payload_sha256`）、主机真值
   9 列（`line_a/results/source_manifest_960.tsv`，采集后离线按 source_id 关联），
   `line_b/tx_payload/*` 已重导出。
2. **保存条件三态分离**：`recovery_computed && tensor_finite` / `gate_pass` /
   `hard_invalid|no_sync|non_finite` 各自独立，门拒但 tensor 有限仍落盘。
3. **训练样本选择双臂**：`RF_ALL_FINITE`（默认）与 `RF_GATE_PASS_ONLY`
   （`--train-rf-arm`）。
4. **S4 缺失 tensor**：pred=-1 记错、保留 240 固定分母（`merge_predictions` 填 -1）。

24 帧 e2e 反例已验证口径：1 个「门拒但有限 tensor」与 1 个「hard-invalid 无 tensor」
均按正确口径进入结果。

**三轮评审（39e5，2 阻塞）已全部收口**：
1. **runner 编译**：`pilot1_capture_runner.hpp` 的 `ok_pred()` 原在 `emit_capture_row()`
   之后声明、之前调用（板上才会触发）。已把 `ok_pred()` 移到 `emit_capture_row()` 前面，
   并新增 `host_tests/pilot1_capture_runner_syntax.cpp`（`-fsyntax-only` 完整编译 runner TU，
   接进 `syntax_check.sh`，在 gate9_rml23 之前跑）。WSL 复验 `pilot1_capture_runner:
   syntax OK`（**仅 runner TU 通过**；`syntax_check.sh` 整体因后段旧 scalarwl 文件
   `-Werror=sign-compare` 返回 rc=1，见下方「已知越界问题」，不宣称全脚本 PASS）。板端
   aarch64 构建由用户在串口 `LIBIIO_ROOT=… ICRAFT_CMAKE_DIR=/usr/cmake taskset -c 0 bash
   scripts/build_on_board.sh` 执行（§4.3，须看到 `NPU_BUILD_RESULT gate=9R result=PASS`
   与 `RML23_BUILD_RESULT result=PASS`）。
2. **接收端真值隔离**：板端公共 manifest 由 9 列改为 3 列（身份 + TX payload SHA，不含
   class_index/class_name/dataset_index/split/source_iq_sha256）；runner 把真值列
   （class_index/class_name/dataset_index/split/source_iq_sha256/label）与
   digital_pred/digital_label_correct 一律置空；PC 私有 5 列 manifest 保存 tx_payload_file
   （板端不可见）；主机真值 9 列 manifest 离线保存。判读/训练/评估统一经
   `line_c/scripts/gt_join.py::backfill_truth()` 按 source_id 离线回填，并 fail-closed
   断言板端确实未带回任何真值（反例自测通过）。

**已知越界问题（非本任务变更集，如实记录）**：板端树 `host_tests/` 全套构建
`build_host_tests.sh` 与 `syntax_check.sh` 均会在
`iq_rf_loopback_24class_bf16_scalarwl_core.hpp:352` 处因 `-Werror=sign-compare`
（`const long long int` vs `uint64_t`）中断——这是上一任务 scalarwl-4way 遗留，不在
realrf-finetune-pilot1 的变更集内。因此 **`syntax_check.sh` 整体返回 rc=1（不宣称全 PASS）**，
但本轮新增的 `pilot1_capture_runner` TU 检查排在 gate9_rml23 之前、已单独打印
`pilot1_capture_runner: syntax OK`；板端 CMake 构建（`scripts/build_on_board.sh`）**未启用
`-Werror`**，故该 warning 不升级为板端编译失败，板端 aarch64 构建不受此 host 测试残留影响
（以 `NPU_BUILD_RESULT gate=9R result=PASS` / `RML23_BUILD_RESULT result=PASS` 为准）。
本任务两个 host 目标可独立编译运行：`test_pilot1_capture`（34/0 PASS）与
`pilot1_e2e_sim`（PASS）。

> **板端 aarch64 构建（评审 39e5 Blocker 1 收口项，用户串口执行）**：在本轮重打包的 PATCH
> 解压到板端树之后，于部署树根目录跑
> `LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ICRAFT_CMAKE_DIR=/usr/cmake
> taskset -c 0 bash scripts/build_on_board.sh`，确认 `pilot1_capture_runner.hpp` 的
> `ok_pred()` 顺序修正能在 aarch64 目标下链接通过（host `-fsyntax-only` 已先验证语法，
> 但不能替代板端真实 aarch64 构建）。**仅当看到 `NPU_BUILD_RESULT gate=9R result=PASS`
> 与 `RML23_BUILD_RESULT result=PASS` 两行后**，才恢复四会话正式采集授权；当前阶段只
> 上传 + 尝试构建，**不直接开始 S1–S4 正式采集**。

下一步 = 用户先上传 PATCH 并按上述命令尝试板端 aarch64 构建（**只构建，不采集**）；看到
`NPU_BUILD_RESULT gate=9R result=PASS` + `RML23_BUILD_RESULT result=PASS` 两行后再按
`line_b/BOARD_CAPTURE_RUNBOOK.md` 开始四会话采集；回传后离线跑数字基线 + 判读器。

## 7. 环境锁定与解释器分工（评审 #9）

三套解释器各司其职，精确版本/路径见 `ENVIRONMENT.md`：

| 段 | 脚本 | 正确调用 |
|---|---|---|
| 一致性核验 | `consistency_check.py` | `python -I` |
| 线 B schema 自测 | `line_b/scripts/selftest_capture_schema.py` | `python -I` |
| 线 C 自测 | `line_c/scripts/selftest_line_c.py` | `python -I`（契约级；torch 环跳过） |
| 24 帧 e2e 模拟 | `line_b/scripts/run_e2e_sim.py` | `python -I`（内部调 WSL g++） |
| 数字基线 | `line_c/scripts/run_digital_baseline.py` | `python -I` |
| 判读器 | `line_c/scripts/judge_realrf_pilot.py` | `python -I` |
| 训练 / 评估 / 训练自测 | `train_finetune_pilot.py` / `evaluate_finetune_pilot.py` | **`python`**（不带 `-I`，需 torch） |
| PC TX 服务 | `host_tools/pc_tx_radioml_dualsdr.py` | `D:\radioconda\python.exe -I`（板端树） |
| C++ host 测试 | `host_tests/build_host_tests.sh` / `run_tests.sh` | WSL `bash` |

> 教训：任何 `import torch` 的脚本都不许标 `python -I`（torch 在用户 site-packages，
> `-I` 看不到）；numpy-only 脚本一律 `python -I`（更干净，防 CWD 内植 `json.py`）。
