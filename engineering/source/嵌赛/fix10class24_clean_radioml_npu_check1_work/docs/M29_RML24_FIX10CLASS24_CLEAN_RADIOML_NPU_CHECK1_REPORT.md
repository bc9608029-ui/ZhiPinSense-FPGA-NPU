# fix10class24-clean-radioml-npu-check1 — 纯净 RadioML 板端 NPU 对照（就绪待上板）

## 状态

**`M29-RML24-FIX10CLASS24-CLEAN-RADIOML-NPU-CHECK1-READY-FOR-BOARD-RUN`**

- 本环境**无板端访问通道**（无 SSH/串口/MCP 板端工具），故**尚未执行板端 NPU 推理**。
- 已完成的只有**离线只读核验**（主机侧）+ **核验后的用户执行命令** + **fail-closed 判读脚本**。
- **不得报告「已测过」**。下表「本次纯净 RadioML 板端 NPU」一行留空，等真实板端输出回填。

## 任务问题

同样的模型、样本与分类前处理，去掉实际 RF 收发与恢复环节后，板端能否正确识别 24 个
纯净 RadioML 样本？（Host BF16 基线 24/24 已确认，但**不能**用它冒充板端 NPU 实测。）

## 离线只读核验（主机侧，全部 PASS）

核验对象 = 当前板端部署树 `fix10class24_tx_rms_sweep1_work/sdr_rml24_fix10class24_tx_rms_sweep1`
（板端目录 `/root/fix10class24_tx_rms_sweep1_test_1773372720`）。

| # | 核验项 | 结果 |
|---|---|---|
| 1 | 模型 JSON SHA = `28272abc…`（冻结值） | ✅ `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` |
| 2 | 模型 RAW SHA = `c1781aec…`（冻结值） | ✅ `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` |
| 3 | manifest 24 行、source_index=0,500,…,11500、raw24_class 0…23 | ✅ 25 行（1 表头+24），覆盖 0…23 |
| 4 | baseline 24 行、`frozen_bf16_raw24_pred`==raw24_class（Host 24/24）、model_sha=`28272abc…` | ✅ |
| 5 | 无类别筛选/文件筛选/数量截断（`--max-files=0` 不截断、`--file-filter=""` 不筛） | ✅ runner 源码确认 |
| 6 | phase `iq-clean-iq-24class-bf16-fix10` 已接线 | ✅ `gate9_phase.hpp:23` + `board_gate9_full_chain_rml23.cpp:3730` |
| 7 | 模型按命令行 `--model-json/--model-raw` 加载（`main()` → `NpuClassifier24(model_json, model_raw)`） | ✅ `board_gate9_full_chain_rml23.cpp:3687` |
| 8 | 命令行显式模型参数**覆盖** `common_rml23.sh` 旧默认 `model_rml23/model_24class_ZG.*` | ✅ `board::get_opt` 末次出现胜出（`board_common.hpp:93-107`） |
| 9 | 分类路径 = 冻结 CI16 → PreprocessChain → D2 restore → `select_classification_window` → BF16 NPU ×2 → `raw24_predict` | ✅ `iq_clean_iq_24class_bf16_fix10.hpp` |
| 10 | **不做 24→23 合并**（`chain::contract_24()`，非 `contract_23()`）；**不用旧 mixed 模型** | ✅ |
| 11 | nco-offset=0；参考 tensor 仅用于窗口对齐，分类输入是 `cw.aligned_tensor`（非参考 tensor） | ✅ |
| 12 | 两次推理判 repeat_deterministic；excluded 仅 `CLEAN_NO_VALID_WINDOW`，不丢 24 分母 | ✅ |

**关键点确认**：`run_gate9_rml23.sh` 先注入旧模型默认参数、后拼 `"$@"`，而
`board::get_opt` 取**最后一个** `--key=`；任务书命令显式传入
`--model-json=model_rml24_bf16/… --model-sha=c1781aec…`，故板端实际加载当前 BF16 模型，
不是旧 23 类合并模型。✅

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
echo "== manifest/baseline 行数（期望各 25）=="
wc -l clean24_smoke/route_d2_rf_manifest.tsv \
      baselines/clean24_smoke_raw24_bf16_baseline.tsv
echo "== source_index 覆盖（期望 0 500 … 11500）=="
tail -n +2 clean24_smoke/route_d2_rf_manifest.tsv | cut -f2 | sort -n | tr '\n' ' '; echo
echo "== raw24_class 覆盖（期望 0…23）=="
tail -n +2 clean24_smoke/route_d2_rf_manifest.tsv | cut -f3 | sort -n | tr '\n' ' '; echo
```

### Step 2 — 跑一次完整 24 类（在板端项目根目录）

```bash
cd "$PROJ" || exit 1
OUT="/root/rml24_clean_radioml_npu_$(date +%s)"
mkdir -p "$OUT"

bash scripts/run_gate9_rml23.sh \
  --phase=iq-clean-iq-24class-bf16-fix10 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --input-kind=radioml-d2-2p56m \
  --frozen-dir=clean24_smoke \
  --baseline=baselines/clean24_smoke_raw24_bf16_baseline.tsv \
  --nco-offset=0 \
  --max-files=0 \
  --file-filter= \
  --out-dir="$OUT" \
  2>&1 | tee "$OUT/run.log"

RUN_RC=${PIPESTATUS[0]}
printf 'RUN_RC=%s\nOUT=%s\n' "$RUN_RC" "$OUT"
```

- 该 runner 已对每个输入执行**两次**推理查重复一致性，先跑这一轮即可，无需额外三轮。
- `--file-filter=`（空值）与 `--max-files=0` 已由源码确认不筛不截断；必须从**项目根目录**执行
  （相对路径 `model_rml24_bf16/…`、`clean24_smoke`、`baselines/…` 相对 cwd 解析）。

## 结果核验（回传 $OUT 后，主机侧独立重算）

回传整个 `$OUT` 目录（含 `route_f_fix10class24_bf16_clean_iq_results.tsv` +
`route_f_fix10class24_bf16_clean_iq_summary.json` + `run.log`），然后：

```bash
python -I scripts/audit_fix10class24_clean_radioml_npu_check1.py \
  --out-dir    <回传的 $OUT> \
  --frozen-dir <clean24_smoke> \
  --baseline   <baselines/clean24_smoke_raw24_bf16_baseline.tsv>
```

该脚本**从逐样本 TSV 独立重算**（不信 GATE_RESULT result=PASS），硬门禁 fail-closed：

- 24 个唯一 source_index、类别覆盖 0…23、`scored + excluded == 24`（**excluded 不丢分母**）；
- baseline_pred 与冻结 baseline 逐 source_index 一致（防 baseline 被替换）；
- `summary.json` 的 model_sha/input_kind/holdout_files/baseline_identity_ok 与逐样本交叉一致；
- `nan_or_inf == 0`、`repeat_deterministic == scored`（任何一次非有限/两次推理不一致 → 测量无效，rc=1）；
- 独立重算 `label_correct/24`、`baseline_agreement/24`、`repeat_deterministic`、`excluded`、`错误明细`、
  `窗口 corr/nmse/delay`。

自测（真实冻结 manifest/baseline + 合成结果夹具）**10/10**：clean24/24、1 错误、合法 1 excluded
均 rc=0；从分母删行、source_index 篡改、baseline_pred 篡改、NaN、非确定、summary 数值/模型 SHA
不符均 rc=1。

## 对照表（待回填）

| 证据 | 结果 |
|---|---|
| 既有纯净 RadioML Host BF16 | 24/24 |
| 本次纯净 RadioML 板端 NPU | **待实测回填**（scored/excluded/正确数） |
| 既有双 SDR RMS2048 诊断合并结果 | 19/24（板端过门＋Host 门拒强制分类） |

> 末行证据层级不同，不能直接当作纯板端 NPU 对照。
> 注：我先前 full24-accuracy1 审计记录的双 SDR 门旁路强制是 **18/24**；任务书此处写 **19/24**
> （「RMS2048 诊断合并」口径），来源待你确认——回填时请一并确认这 19/24 是哪次运行/口径。

## 判读与停止条件

- 若本次 **24/24**：这 24 个纯净样本在当前板端数字分类链上全部正确，支持进一步聚焦 RF 收发/恢复
  带来的输入变化；**不能**据此认定某硬件或某补偿是唯一原因。
- 若存在错误：先保留原始记录，定位板端数字链与 Host 基线的差异，**不直接归因 RF**。
- 完成实测、身份核验、结果回传后暂停。

## 红线（未越）

不改生产配置、不自动训练、不写 RF_PASS / PROJECT_COMPLETE 或任何超出本次测量的通过结论。
本次只用现有已构建程序（phase `iq-clean-iq-24class-bf16-fix10`），**未新增/未修改任何板端程序**；
新增的只有主机侧判读脚本（`scripts/audit_*.py` + 自测），不进入板端。
