# fix10class24-original-radioml-npu-ab1 — 原始 RadioML 480 帧板端 NPU 对照（就绪待上板）

## 状态

**`M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-NPU-AB1-READY-FOR-BOARD-TEST`**

- 本环境**无板端访问通道**（无 SSH/串口/MCP 板端工具），故**尚未执行板端 NPU 推理**。
- 已完成的只有**离线只读核验**（主机侧）+ **新增板端入口的编译/测试准备** +
  **核验后的用户执行命令** + **fail-closed 判读脚本**。
- **不得报告「已测过」**。下表「本次板端 NPU 480 帧」一行留空，等真实板端输出回填。

## 任务问题

把 Host 已测过的**同一批 480 帧**原始 RadioML test 集（同一 `hdf5_row_index`、同一训练
合同输入 `X[row].T`、同一 `model_input_sha256`）送进**板端真 NPU**（BF16 模型，非 Host
回退、非 mock），逐帧比对 NPU vs Host 的 raw-24 预测与 24 维 logits，判断二者是否一致。
Host 参考基线：0dB 68/120、10dB 118/120、20dB 117/120、30dB 116/120，合计 **419/480 =
87.29%**。

这是**一致性测量**，不是新模型优化任务：不训练、不改模型、不改预处理/恢复器/门限。

## 冻结身份（逐字节不变）

| 身份 | 冻结值 |
|---|---|
| 模型 JSON | `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` |
| 模型 RAW | `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` |
| 训练输入合同 | `ascontiguousarray(X[row].T).astype(float32)` → `[2,1024]` f32 LE，无 DC/归一化/重采样/滤波 |
| 冻结 test 选择 | `frozen_test_selection.tsv` LF-归一化 SHA `35b3a32c…` |
| 24 类标签序 | `rml24::kLabelOrder24`，不合并 AM-SSB（WC=17 / SC=18 独立） |

## 离线只读核验（主机侧，全部 PASS）

核验对象 = 本工作树 `fix10class24_original_radioml_npu_ab1_work/sdr_rml24_fix10class24_original_radioml_npu_ab1`。

| # | 核验项 | 结果 |
|---|---|---|
| 1 | 新增 phase `radioml-original-npu-ab-24class-bf16-fix10` 已接线（`gate9_phase.hpp::valid_phase()` + `board_gate9_full_chain_rml23.cpp` include/wrapper/dispatch/error-text 四点） | ✅ |
| 2 | 板端 runner 走真 NPU（`chain::NpuClassifier24`）+ `raw24_predict`，`set_input_audit(true)`；无 SDR/CFO/wide-linear/D2/恢复/window/0.100 门 | ✅ `radioml_npu_ab_runner.hpp` |
| 3 | loader fail-closed：8 列表头精确、480 行、selection_id 连续、hri/file/sha 唯一、raw24_class∈0..23、每 .bin 8192B 且 SHA==manifest | ✅ `radioml_npu_ab_loader.hpp` |
| 4 | 输出目录 fail-closed 不覆盖（已存在即 throw）；两次推理判 repeat_deterministic；NaN/Inf 计数 | ✅ runner |
| 5 | 模型按命令行 `--model-json/--model-raw` 加载，`board::get_opt` 末次胜出 → 覆盖 `common_rml23.sh` 旧 23 类默认 | ✅ `board_common.hpp:93-107` |
| 6 | 480 帧输入包已由 `export_radioml_npu_ab_inputs.py` 生成，逐帧 SHA == Host `model_input_sha256` | ✅ `input_package/`（480 .bin + manifest + SHA256SUMS） |
| 7 | host 测试 `test_radioml_npu_ab_loader.cpp` 已注册 `build_host_tests.sh`/`run_tests.sh` | ✅ |
| 8 | PATCH 包 + 输入包生成脚本 `package_radioml_npu_ab.py`：红线头/受保护目录/合同/规范 CI16 逐字节不变 | ✅ |

## 板端执行（用户串口执行；本环境无法连接板端）

### Step 1 — 只读核验（优先用现有目录，找不到才列候选，不覆盖）

```bash
PROJ=/root/fix10class24_tx_rms_sweep1_test_1773372720
if [ ! -d "$PROJ" ]; then
  echo "MISSING $PROJ — 候选:"; ls -d /root/fix10class24* 2>/dev/null
  # 找到实际部署目录后把它赋给 PROJ，再继续；不要猜/覆盖其他目录
fi
cd "$PROJ" || exit 1

echo "== 二进制存在 ==";          ls -l bin/board_gate9_full_chain_rml23
echo "== 模型 SHA（须等于冻结值）=="
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.json \
          model_rml24_bf16/rml24_adamrv11_bf16.raw
# 期望: 28272abc…  .json / c1781aec…  .raw
```

### Step 2 — 解压 PATCH + 输入包到项目根，校验两包 SHA

```bash
cd "$PROJ" || exit 1
# 把两个 tar.gz + 两个 _SHA256SUMS.txt 拷到板端项目根后：
tar -xzf sdr_rml24_fix10class24_original_radioml_npu_ab1_patch.tar.gz
tar -xzf sdr_rml24_fix10class24_original_radioml_npu_ab1_inputs.tar.gz

# 校验 PATCH 包内容（在包内相对路径下）——解压后逐项比对：
grep -q radioml_npu_ab_runner.hpp \
  FIX10CLASS24_ORIGINAL_RADIOML_NPU_AB1_PATCH_SHA256SUMS.txt \
  && echo "PATCH SUMS present"
# 校验输入包（480 .bin + manifest + SHA256SUMS）：
cd sdr_rml24_fix10class24_original_radioml_npu_ab1_inputs 2>/dev/null \
  && sha256sum -c FIX10CLASS24_ORIGINAL_RADIOML_NPU_AB1_INPUTS_SHA256SUMS.txt \
  && cd "$PROJ"
# 注意：PATCH 包是「扁平相对路径」内容，直接解压到项目根；输入包是自含目录，
# 其 --input-dir 指向该目录本身。
```

> 注：PATCH 包内含 `FIX10CLASS24_ORIGINAL_RADIOML_NPU_AB1_PATCH_SHA256SUMS.txt`，
> 解压到项目根后可用 `sha256sum -c` 对整包内容做逐项校验（包内路径相对项目根）。

### Step 3 — 构建 producer（仅 producer 改动，UI 服务器不变）

```bash
cd "$PROJ" || exit 1
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 \
ICRAFT_CMAKE_DIR=/usr/cmake \
  ./board_package/build_npu_on_board.sh --gate9-rml23
# 期望: NPU_BUILD_RESULT result=PASS
ls -l bin/board_gate9_full_chain_rml23
```

### Step 4 — 跑一次完整 480 帧（在板端项目根目录）

```bash
cd "$PROJ" || exit 1
bash scripts/run_radioml_npu_ab.sh \
  --input-dir="$PROJ/sdr_rml24_fix10class24_original_radioml_npu_ab1_inputs" \
  --out-dir="/root/rml24_npu_ab_$(date +%s)"
```

- runner 对每个输入执行**两次**推理查重复一致性（`repeat_deterministic`）。
- `--out-dir` 必须是不存在的全新目录（runner 拒绝覆盖）；`run.log` 由脚本在 runner
  创建目录后移入 `$OUT_DIR/run.log`。
- 期望打印 `ROUTE_F_RADIOML_ORIGINAL_NPU_AB token=ROUTE_F_RADIOML_ORIGINAL_NPU_AB_MEASUREMENT_COMPLETE ...`。
- 若打印 `..._MEASUREMENT_INCOMPLETE` 或 `result=FAIL`，先保留原始记录，回传后再判读。

### Step 5 — 回传整个 $OUT

回传整个 `$OUT_DIR`（含 `radioml_npu_ab_results.tsv` + `radioml_npu_ab_logits.tsv` +
`radioml_npu_ab_summary.json` + `run.log`）。

## 结果核验（回传 $OUT 后，主机侧独立重算）

```bash
python -I scripts/audit_radioml_npu_ab.py \
  --out-dir <回传的 $OUT_DIR> \
  --host-results F:/嵌赛/fix10class24_original_radioml_accuracy1_work/results
```

该脚本**从逐样本 TSV 独立重算**（不信 GATE_RESULT 行），硬门禁 fail-closed：

- 480 行、selection_id 连续 1..480、hri 唯一、`finite==1`、`repeat_deterministic==1`、
  `result_layer==NPU_BF16`、logits 全有限、logits argmax == `npu_pred_pass1`；
- board `host_pred` 与 Host `per_sample_results.pred_pass1` 逐 hri 一致（防替换）；
- 独立重算总体/4-SNR/每类/每类×SNR 准确率、24×24 混淆、NPU-Host 一致率、
  不一致样本的 logits/top1/top2/margin、logit 最大绝对差。

判定（`radioml_npu_ab_host_audit.json` 内 `verdict`）：
- `MEASUREMENT_COMPLETE_HOST_MATCH`（rc=0）：480 全有限+确定+与 Host argmax 一致；
- `MEASUREMENT_COMPLETE_HOST_DISAGREEMENT`（rc=0）：全有限+确定但有分歧（列明细）；
- `MEASUREMENT_INCOMPLETE`（rc=1）：缺行/重复/NaN/不确定/表头列数错/host_pred 不一致。

自测（合成夹具）**5/5**：match/disagree 均 rc=0 且判定正确；missing/NaN/nondet 均 rc=1。

## 对照表（待回填）

| 证据 | 结果 |
|---|---|
| Host BF16 原始 RadioML 480 帧（参考） | 419/480 = 87.29%（0dB 68/120、10-30dB ≥ 96.7%） |
| 本次板端 NPU 480 帧 | **待实测回填**（scored/nan_or_inf/repeat_deterministic/正确数/NPU-Host 一致率） |

## 判读与停止条件

- 若 NPU 与 Host **全帧一致**：证明同一批输入在 Host 与板端真 NPU 上的预测逐帧吻合，
  支持「之前双 SDR 误分类差异来自输入（RF 收发/恢复），而非板端 NPU 推理本身」。
- 若存在分歧：先列分歧明细（SNR/类/logit/margin），**不直接归因**任何单一硬件环节。
- 完成实测、身份核验、结果回传后暂停。

## 红线（未越）

不训练、不重量化、不改模型/预处理/恢复器/门限（0.100 本任务不使用且不改）；
旧 phase（尤其 `iq-clean-iq-24class-bf16-fix10`）行为逐字节不变；输出目录不覆盖；
真 NPU 无 Host 回退/mock；不写 RF_PASS / PROJECT_COMPLETE 或任何超过本次测量的结论。
本任务新增板端程序仅一个 phase 入口（runner + loader + 接线），未改动任何既有 runner。
