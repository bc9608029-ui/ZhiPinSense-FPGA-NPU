# fix10class24-original-radioml-singlesdr-ab1 — 原始 RadioML 单 SDR 四臂对照（就绪待上板）

## 状态

**`M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-SINGLESDR-AB1-READY-FOR-BOARD-TEST`**

- 本环境**无板端访问通道**（无 SSH/串口/MCP 板端工具），故**尚未执行任何板端 RF 收发/推理**。
- 已完成：**单 SDR 板端 producer**（新增 phase + loader + runner + gate9 接线）、
  主机侧 4 臂判定器、板端编排脚本、**离线只读核验 10/10**。
- **不得报告「已测过」**。下表「arm S 单 SDR 480 帧」一行留空，等真实板端输出回填。

## 任务问题（四臂对照，同一批 480 帧原始 RadioML）

同一批 480 帧（同一 `hdf5_row_index`、同一 `X[row].T` 合同、同一 `model_input_sha256`）走四条链：

| 臂 | 链 | 回答 |
|---|---|---|
| **A** | 原始输入 → 冻结 BF16（Host/板端，npu-ab1 已完成） | 参考基线 419/480 = 87.29% |
| **D** | 原始输入 → 数字 TX/RX（无 RF）→ 同模型 | 量化/适配损失 vs RF 损失 |
| **C** | 原始输入 → PC SDR TX → 板 SDR RX 恢复 → 同模型 | 双 SDR 准确率变化（dualsdr 分支） |
| **S** | 原始输入 → **单 SDR 本地 TX → 50Ω 同轴 → 同一 SDR RX 恢复** → 同模型 | 单 SDR 准确率变化；哪些类/SNR 稳定 vs 退化 |

这是**测量**，不是新模型优化：不训练、不改模型、不改预处理/恢复器/门限。

## 冻结身份（逐字节不变）

| 身份 | 冻结值 |
|---|---|
| 模型 JSON / RAW / CKPT | `28272abc…` / `c1781aec…` / `96cd25f8…` |
| 训练输入合同 | `ascontiguousarray(X[row].T).astype(float32)` → `[2,1024]` f32 LE |
| 24 类标签序 | `rml24::kLabelOrder24`，AM-SSB WC=17/SC=18 独立 |
| 480 帧选择 | 与 npu-ab1 逐字节一致（selection_id/hri/类/SNR/input_sha256） |
| TX 派生契约 | `contract/tx_derived_conversion_contract.{md,json}`（dualsdr 分支单一权威） |
| RF 契约 | 2.56 Msps、中心 2.4 GHz、RX/TX BW 18 MHz、RX 手动 35 dB、TX ≤ −40 dB、RMS2048 |
| 恢复/门限 | 生产 `recover_payload_with_coarse_cfo` + 0.100 门 + 至多 3 次重捕 + 末次选择 |

## 离线只读核验（主机侧，全部 PASS）

`host_tests/test_radioml_singlesdr_ab1.py` **10/10**：

| # | 核验项 | 结果 |
|---|---|---|
| 1 | 480 帧主键唯一（hri/file/sha 唯一）+ 身份 + 5 帧/类/SNR | ✅ |
| 2 | short24 固定选取（每类 1 帧 @30dB 最小 selection_id） | ✅ |
| 3 | 适配确定性 + 类无关 + 循环铺排近似保 RMS | ✅ |
| 4 | TX payload 与 dualsdr `results/tx_payload` 逐字节一致（契约 VENDOR 无漂移） | ✅ |
| 5 | loader 契约常量与导出逐字一致（adaptation/18 列表头/480/53760/clip==0） | ✅ |
| 6 | runner 红线源码审计（单 SDR 本地 TX 非 PC-TX/生产恢复/35dB/−40/2.56M/direct-cable/反覆盖/末次重捕/绝不强制/窗口=payload[:1024]*unscale） | ✅ |
| 7 | 冻结模型 SHA | ✅ |
| 8 | run 脚本源码审计（显式 `--rx-gain=35` 覆盖/`--rf-path`/phase/24 类模型覆盖） | ✅ |
| 9 | 四臂判定器自测（gate-reject 分母不剔除/hard_invalid 绝不强制/C 缺席=PENDING） | ✅ |
| 10 | 门拒 + hard-invalid 样本同样落盘原始捕获 + 恢复诊断（源码审计，落盘在过门分支之前） | ✅ |

## 板端执行（用户串口执行；本环境无法连接板端）

前置：单 SDR 的 **TX 与 RX 用 50Ω 同轴直连（loopback=0，无天线无放大器）**。

### Step 1 — 只读核验基线项目（优先用现有目录，找不到才列候选，不覆盖）

```bash
PROJ=/root/fix10class24_tx_rms_sweep1_test_1773372720   # 例；以实际部署目录为准
if [ ! -d "$PROJ" ]; then echo "MISSING $PROJ — 候选:"; ls -d /root/fix10class24* 2>/dev/null; fi
cd "$PROJ" || exit 1
echo "== 二进制存在 ==";          ls -l bin/board_gate9_full_chain_rml23
echo "== 模型 SHA（须等于冻结值）=="
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.json \
          model_rml24_bf16/rml24_adamrv11_bf16.raw
# 期望: 28272abc…  .json / c1781aec…  .raw
```

### Step 2 — 解压本 PATCH 到项目根，校验包 SHA

```bash
cd "$PROJ" || exit 1
tar -xzf sdr_rml24_fix10class24_original_radioml_singlesdr_ab1_patch.tar.gz
sha256sum -c FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_PATCH_SHA256SUMS.txt
# 期望: 15 个内容文件全部 OK
```

> 注：PATCH 包内含 `FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_PATCH_SHA256SUMS.txt`，
> 解压到项目根后可用 `sha256sum -c` 对整包内容做逐项校验（包内路径相对项目根）。
> PATCH tar.gz **整体** SHA 见回传记录（不写入本文档以免自引用）。

> 本 PATCH 是「扁平相对路径」内容，直接解压到项目根，新增/改动：
> `board_package/radioml_singlesdr_ab_{loader,runner}.hpp`（新增）、
> `board_package/gate9_phase.hpp` + `board_package/board_gate9_full_chain_rml23.cpp`（四点接线）、
> `scripts/judge_radioml_singlesdr.py` / `run_radioml_singlesdr_ab.sh` / `package_radioml_singlesdr_ab1.py`、
> 契约 + 4 个 vendored dualsdr 脚本、`host_tests/test_radioml_singlesdr_ab1.py`、本文档。

### Step 3 — 准备 TX payload 数据包（板端 `--input-dir`，不在本 PATCH 内）

本任务**复用** dualsdr 分支已导出的 TX 派生 payload（同一契约、同一字节，逐帧 SHA 已由
主机测试 t04 证实），已打成独立于 PATCH 的 INPUTS 数据包（照 npu-ab1 输入包模式：PATCH 与
数据包分开、各自 SHA）：

- 数据包 tar.gz 整体 SHA256 = `e5430a3e70465877d4a75550c731fa4465f3aa019cbdbebfd58a2d33f9be5026`
- 内容：480 个 `<sid>.i16` + `tx_manifest.tsv` + `FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_INPUTS_SHA256SUMS.txt`（481 内容文件）

```bash
# 板端（解压到全新目录作为 --input-dir）:
IN_DIR=/root/rml24_singlesdr_ab_inputs
mkdir -p "$IN_DIR" && cd "$IN_DIR"
sha256sum sdr_rml24_fix10class24_original_radioml_singlesdr_ab1_inputs.tar.gz
# 期望: e5430a3e70465877d4a75550c731fa4465f3aa019cbdbebfd58a2d33f9be5026
tar -xzf sdr_rml24_fix10class24_original_radioml_singlesdr_ab1_inputs.tar.gz
sha256sum -c FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_INPUTS_SHA256SUMS.txt
# 期望: 480 个 .i16 + tx_manifest.tsv 全部 OK
```

> 若数据包缺失，可按共享契约重新导出（输出必须为**全新目录**，绝不重造 TX 派生规则）：
> `python -I scripts/export_radioml_dualsdr_tx_payload.py --input-package <npu-ab1 input_package> --out-dir <fresh dir>`

### Step 4 — 构建 producer（仅 producer 改动，UI 服务器不变）

```bash
cd "$PROJ" || exit 1
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 \
ICRAFT_CMAKE_DIR=/usr/cmake \
  ./board_package/build_npu_on_board.sh --gate9-rml23
# 期望: NPU_BUILD_RESULT result=PASS
ls -l bin/board_gate9_full_chain_rml23
```

### Step 5 — short24 烟测（只验证传输/身份/输出完整性，非准确率测量）

```bash
cd "$PROJ" || exit 1
bash scripts/run_radioml_singlesdr_ab.sh \
  --mode=short24 \
  --input-dir="<Step 3 拷入的 tx payload 目录>" \
  --rx-uri="<单 SDR URI，TX+RX 同一设备>" \
  --out-dir="/root/rml24_singlesdr_ab_short24_$(date +%s)"
```

- 期望打印 `ROUTE_F_RADIOML_ORIGINAL_SINGLESDR_AB mode=short24 frames=24 …`，
  `ROUTE_F_RADIOML_ORIGINAL_SINGLESDR_AB_MEASUREMENT_COMPLETE`（`board_summary.json`
  的 `measurement_token`）。
- 若打印 `…_INCOMPLETE` 或 `result=FAIL`（`device_not_found` 退码 2），先保留原始记录，
  回传后再判读；不要覆盖 `$OUT_DIR`。

### Step 6 — full480 完整测量

```bash
cd "$PROJ" || exit 1
bash scripts/run_radioml_singlesdr_ab.sh \
  --mode=full480 \
  --input-dir="<Step 3 拷入的 tx payload 目录>" \
  --rx-uri="<单 SDR URI，TX+RX 同一设备>" \
  --out-dir="/root/rml24_singlesdr_ab_full480_$(date +%s)"
```

### Step 7 — 回传整个 $OUT

回传整个 `$OUT_DIR`（含 `board_results.tsv` 19 列 + `board_logits.tsv` +
`recovered/<sid>.raw.i16`（**每样本**原始捕获，含门拒/hard-invalid）+
`recovered/<sid>.diag.json`（**每样本**恢复诊断，含门拒/hard-invalid）+
`recovered/*.bin`（过门样本模型输入）+ `board_summary.json` + `run.log`）。

> **诊断保存**（任务书要求「保存所有样本的原始捕获+恢复诊断+模型输入+24 logits」）：
> runner 在过门分支**之前**无条件落盘 `<sid>.raw.i16` 与 `<sid>.diag.json`，因此
> gate-reject / hard-invalid / 不可恢复样本同样落盘原始捕获 + 恢复诊断，离线可复查而非
> 重新采集；这些样本**仍计入分母，绝不剔除**。

## 结果核验（回传 $OUT 后，主机侧独立重算）

```bash
python -I scripts/judge_radioml_singlesdr.py \
  --input-package <npu-ab1 input_package> \
  --digital <dualsdr results/digital_roundtrip/digital_roundtrip.tsv> \
  [--board-dualsdr <dualsdr 回传的 board_results.tsv>] \
  --board-singlesdr <本任务回传的 board_results.tsv> \
  --out-dir <fresh judge dir>
```

判定器从逐样本 TSV 独立重算（不信汇总行），输出四臂 coverage/准确率口径/翻转/混淆/
per-class/per-SNR/residual+corr 统计；**hard_invalid 绝不强制为成功；gate-reject =
端到端失败（分母不剔除）**。arm C / arm S 未回传时该臂标 PENDING，不虚构数字。

## 对照表（待回填）

| 证据 | 结果 |
|---|---|
| arm A Host BF16 原始 RadioML 480 帧（参考） | 419/480 = 87.29%（0dB 68/120、10-30dB ≥ 96.7%） |
| arm D 数字无 RF 回环（dualsdr） | corr≈0.99999998、nmse 4.2e-8、byte_identical=0/480（诚实） |
| arm C 双 SDR 480 帧（dualsdr） | 待回填 |
| **arm S 单 SDR 480 帧（本任务）** | **待实测回填**（coverage/gated/e2e/每类/每SNR/翻转） |

## 判读与停止条件

- arm S 未回传前，**不**下任何关于单 SDR 准确率的结论。
- 完成离线核验、身份核验、结果回传后暂停。
- 单 SDR 与双 SDR（arm C）的差异 = 单/双设备拓扑差异（同一时钟/LO vs 独立 PC-TX），
  仅当两臂均回传后才可比较。

## 红线（未越）

不训练、不重量化、不改模型/预处理/恢复器/门限（0.100 本任务不改）；旧 phase 行为逐字节
不变；输出目录不覆盖；板端绝不强制分类；TX 衰减不高于 −40 dB；RX 手动 35 dB；中心 2.4 GHz、
采样 2.56 Msps、RX/TX 带宽 18 MHz；不按类修改参数、不按标签挑选捕获或补偿结果。
本任务新增板端程序仅一个 phase 入口（loader + runner + 接线），未改动任何既有 runner。
