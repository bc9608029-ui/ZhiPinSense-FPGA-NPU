# fix10class24-original-radioml-dualsdr-ab1 — 原始 RadioML 双 SDR 三臂对照（就绪待上板）

## 状态

**`M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DUALSDR-AB1-READY-FOR-BOARD-TEST`**

- 本环境**无板端访问通道**（无 SSH/串口/MCP 板端工具），**尚未执行任何板端 RF 收发/推理**。
- 已完成：**主机侧三臂准备**（arm A 参考、arm D 数字无 RF 回环、arm C 板端 producer + TX payload 契约），
  全部离线只读核验 PASS，主机测试 **15/15**、pc_tx 自检 **12/12**。
- **arm C 板端 producer 已包含在本 PATCH**（新 phase `radioml-original-dualsdr-ab-24class-bf16-fix10`
  + runner `radioml_dualsdr_ab_runner.hpp` + loader + gate9_phase 接线 + main() 分发，见 §6）。
- **不得报告「已测过」**。下表「arm C 双 SDR 480 帧」一行留空，等真实板端输出回填。

## 任务问题（三臂对照，同一批 480 帧原始 RadioML）

同一批 480 帧（同一 `hdf5_row_index`、同一 `X[row].T` 合同、同一 `model_input_sha256`）走三条链：

| 臂 | 链 | 回答 |
|---|---|---|
| **A** | 原始输入 → 冻结 BF16（Host/板端，npu-ab1 已完成） | 参考基线 419/480 = 87.29% |
| **D** | 原始输入 → 数字 TX/RX（无 RF）→ 同模型 | 量化/适配损失 vs RF 损失 |
| **C** | 原始输入 → PC SDR TX → 板 SDR RX 恢复 → 同模型 | 双 SDR 准确率变化；哪些类/SNR 稳定 vs 退化 |

这是**测量**，不是新模型优化：不训练、不改模型、不改预处理/恢复器/门限。

## 冻结身份（逐字节不变）

| 身份 | 冻结值 |
|---|---|
| 模型 JSON / RAW / CKPT | `28272abc…` / `c1781aec…` / `96cd25f8…` |
| 训练输入合同 | `ascontiguousarray(X[row].T).astype(float32)` → `[2,1024]` f32 LE |
| 24 类标签序 | `rml24::kLabelOrder24`，AM-SSB WC=17/SC=18 独立 |
| 480 帧选择 | 与 npu-ab1 逐字节一致（selection_id/hri/类/SNR/input_sha256） |

Phase A 结论（**本任务不修改生产恢复/训练帧/窗口规则**）：原始 1024 复样本 vs 生产 payload 53760 复
不可直接兼容 → 确定性类无关适配 = 循环铺排 1024→53760 + CI16(RMS2048) + unscale=`native_rms/2048`
+ 模型窗口 = 恢复后 payload 前 1024 复样本。**权威契约见
`contract/tx_derived_conversion_contract.{md,json}`**（含 canonical burst SHA/scale 与 short24 规则）。
量化用 `lround`（半远离零，逐字匹配 C++ `std::llround`），非 `numpy.rint`（半到偶）。

## 离线只读核验（主机侧，全部 PASS）

| # | 核验项 | 结果 |
|---|---|---|
| 1 | 480 帧主键唯一（hri/file/sha 唯一）+ 身份 + 5 帧/类/SNR | ✅ |
| 2 | short24 固定选取（每类 1 帧 @30dB 最小 selection_id） | ✅ |
| 3 | 适配确定性 + 类无关 + 循环铺排近似保 RMS | ✅ |
| 4 | RMS 上限 2048 / TX 衰减 −40 / 0.100 门 / 至多 3 重捕 | ✅ |
| 5 | out-dir 反覆盖 | ✅ |
| 6 | gate-reject/hard-invalid 不从 e2e 分母剔除；hard_invalid 绝不强制 | ✅ |
| 7 | 每帧 TX payload / 恢复输入有 SHA（可追溯） | ✅ |
| 8 | 数字回环非 byte-identical（corr≈1, nmse 4.2e-8）→ 不把量化差误归因 RF | ✅ |
| 9 | lround 半远离零 + burst 逐字重实现 + canonical 包装块 SHA 稳定 | ✅ |
| 10 | loader 契约常量（kFrameCount=480/kClassCount=24/kPayloadComplex=53760/adaptation 标签） | ✅ |
| 11 | runner 红线来源审计（0.100 门/hard_invalid 天花板/模型窗口=direct 路径/19 列头） | ✅ |
| 12 | 板端 producer 接线（gate9_phase.hpp 谓词 + main() include/wrapper/dispatch） | ✅ |
| 13 | 两个 run 脚本源审计（显式 24 类 BF16 + `--rx-gain=35` + phase 集成门禁） | ✅ |
| 14 | gate-reject 帧仍无条件落盘 raw_capture + diag.json（过门分支之前） | ✅ |
| 15 | 结果行生存到 capture_try 作用域外（arm D/C 共用行语义） | ✅ |

- 主机测试 `host_tests/test_radioml_dualsdr_ab1.py` **15/15**（t01–t09 原有 + t10–t15 新增）。
- pc_tx 自检 `scripts/pc_tx_radioml_dualsdr.py` **12/12**。
- 输出：`results/tx_payload/`（480 个 `<sid>.i16` + tx_manifest.tsv + route_d2_rf_manifest.tsv + SHA256SUMS）、
  `results/digital_roundtrip/`（arm D）、`results/judge/`（arm C 待板端回传）。

## 交付包（新 PATCH + INPUTS，两包分开）

| 包 | 文件 | SHA256 |
|---|---|---|
| **PATCH** | `dist/sdr_rml24_fix10class24_original_radioml_dualsdr_ab1_patch.tar.gz`（17 内容文件） | 逐文件校验见包内 `sdr_rml24_fix10class24_original_radioml_dualsdr_ab1_patch_SHA256SUMS.txt`（tar.gz 整体 SHA 由主会话在交付台账记录） |
| **INPUTS** | `dist/sdr_rml24_fix10class24_original_radioml_dualsdr_ab1_inputs.tar.gz`（482 内容文件） | `fa3ae73c567d7baace507e73bf16c06a54472eb7172151b62e01a40dbb447c44` |

PATCH 内容：`board_package/`（runner + loader + gate9_phase + board_gate9 共 4）、`contract/`（2）、
`docs/`（1）、`host_tests/`（1）、`scripts/`（9）。INPUTS 内容：480 个 `<sid>.i16` + `tx_manifest.tsv` +
`route_d2_rf_manifest.tsv` + `SHA256SUMS.txt`。

## 板端执行（用户串口执行；本环境无法连接板端）

### Step 1 — 只读核验基线项目（优先用现有目录，找不到才列候选，不覆盖）

```bash
PROJ=/root/fix10class24_tx_rms_sweep1_test_1773372720   # 例；以实际部署目录为准
if [ ! -d "$PROJ" ]; then echo "MISSING $PROJ — 候选:"; ls -d /root/fix10class24* 2>/dev/null; fi
cd "$PROJ" || exit 1
echo "== 模型 SHA（须等于冻结值）=="
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.json model_rml24_bf16/rml24_adamrv11_bf16.raw
# 期望: 28272abc…  / c1781aec…
```

### Step 2 — 解压本 PATCH 到项目根，校验包 SHA

```bash
cd "$PROJ" || exit 1
tar -xzf sdr_rml24_fix10class24_original_radioml_dualsdr_ab1_patch.tar.gz
sha256sum -c sdr_rml24_fix10class24_original_radioml_dualsdr_ab1_patch_SHA256SUMS.txt
```

> 本 PATCH 含**板端 producer C++**（`board_package/radioml_dualsdr_ab_runner.hpp`、
> `radioml_dualsdr_ab_loader.hpp`、`gate9_phase.hpp`、`board_gate9_full_chain_rml23.cpp`）
> + 主机侧脚本/文档/契约。板上 C++ 编译由既有构建链完成（无需本环境 g++）。

### Step 3 — 解压 INPUTS 到板端可读目录（TX payload 包，板端只读）

```bash
mkdir -p /root/rml24_dualsdr_ab_inputs
cd /root/rml24_dualsdr_ab_inputs
tar -xzf sdr_rml24_fix10class24_original_radioml_dualsdr_ab1_inputs.tar.gz
sha256sum -c sdr_rml24_fix10class24_original_radioml_dualsdr_ab1_inputs_SHA256SUMS.txt
```

### Step 4 — 主机侧 PC-TX 服务（先在 Windows 侧启动，板端是控制通道 CLIENT）

```bash
# Windows 侧（radioconda）：
D:\radioconda\python.exe -I scripts/pc_tx_radioml_dualsdr.py launch \
    --tx-payload results/tx_payload --tx-uri "<PC_TX_URI>"
```

### Step 5 — 板端 arm C（两阶段：short24 烟测 → full480 完整）

```bash
cd "$PROJ" || exit 1
# 阶段一：short24 烟测（每类 1 帧 @30dB，只验证传输/身份/输出完整性，非准确率）
bash scripts/run_radioml_dualsdr_short24.sh \
    --input-dir=/root/rml24_dualsdr_ab_inputs \
    --tx-control=tcp://<PC_IP>:39010 \
    --rx-uri="<board RX SDR URI>" \
    --out-dir=/root/rml24_dualsdr_ab_smoke_$(date +%s)

# 阶段二：full480 完整测量（480 帧全量）
bash scripts/run_radioml_dualsdr_full480.sh \
    --input-dir=/root/rml24_dualsdr_ab_inputs \
    --tx-control=tcp://<PC_IP>:39010 \
    --rx-uri="<board RX SDR URI>" \
    --out-dir=/root/rml24_dualsdr_ab_$(date +%s)
```

> 两个 run 脚本已显式传 `--rx-gain=35.0`（`run_gate9_rml23.sh` 默认 `--rx-gain=10`，runner 取
> **末次**出现，省略会静默跑 10dB）、`--center=2400000000 --sample-rate=2560000
> --rx-bw=18000000 --rf-tx-target-rms=2048.0 --rf-path=direct-cable
> --input-kind=radioml-original-dualsdr-ab-2p56m`，并校验模型 SHA + phase 在 gate9_phase.hpp。

## §6 板端 producer 集成（已在本 PATCH 落地）

arm C producer = phase `radioml-original-dualsdr-ab-24class-bf16-fix10`，复用
`iq-pc-tx-board-rx-24class-bf16-fix10` 的双 SDR 拓扑（PC 控 TX + 板控 RX，仅 TCP39010 传控制/身份/SHA）
与生产恢复（广线性 + coarse/fine CFO + 分数定时 + payload 增益训练 + 0.100 门 + ≤3 重捕 + last-capture），
**唯一差异**（与 canonical 训练帧版）：

1. **payload 来源** = `results/tx_payload/<sid>.i16`（53760 复 CI16，RMS2048），非 canonical 训练帧；
2. **模型窗口** = 恢复后 payload 的**前 1024 复样本** × unscale（`native_rms/2048`），非 payload-training 窗口；
3. **报告 19 列** board_results.tsv（列定义见契约 §4）。

### 接线证据（四处）

- **phase 谓词** `board_package/gate9_phase.hpp` 末行：
  `p == "radioml-original-npu-ab-24class-bf16-fix10" || p == "radioml-original-dualsdr-ab-24class-bf16-fix10"`。
- **include** `board_package/board_gate9_full_chain_rml23.cpp`：`#include "radioml_dualsdr_ab_runner.hpp"`。
- **wrapper**：`run_radioml_original_dualsdr_ab(...)` 调 `rmldsab::run_radioml_original_dualsdr_ab(...)`，
  接 `emit_frame_rml24` + `finish_m22_runtime` + `final_gate_pass`，device_not_found→2、error→1。
- **dispatch**：`else if (phase == "radioml-original-dualsdr-ab-24class-bf16-fix10") rc = run_radioml_original_dualsdr_ab(...)`。

### fail-closed（runner 内建）

gate-reject/hard-invalid **不**从分母剔除；hard_invalid **绝不**强制为成功；finite==0 → `board_pred=-1`；
输出目录已存在 → 拒绝覆盖；`--sample-rate`/`--rf-path`/`--input-kind` 与契约不符 → 拒绝运行。

### DC 适配 hook（供 dc-ab1 fork 复用）

`board_package/radioml_dualsdr_ab_runner.hpp` 两处注释标注了 dc-ab1 扩展点：(a) 头部 docstring
（L38–44）：fail-closed `--input-kind` 门 + 模型窗口分支（`direct` vs `dc-transport`）；
(b) gated 分支内模型窗口填 tensor 处（L930–933）：`payload[k] * fr.unscale` 即 `direct` 路径，
`dc-transport` 在此分支。manifest 逐帧 `adaptation` 标签见 `radioml_dualsdr_ab_loader.hpp::kAdaptation()`。

### phase 共存（与 singlesdr fork）

合并 singlesdr-ab1 与 dualsdr-ab1 两个 PATCH 到 rxrecovery1/npu-ab1 基线时，以下两个 phase 名必须在
`gate9_phase.hpp::valid_phase()` 与 `board_gate9_full_chain_rml23.cpp::main()` **同时存在**：

- singlesdr：`radioml-original-singlesdr-ab-24class-bf16-fix10`
- dualsdr（本任务）：`radioml-original-dualsdr-ab-24class-bf16-fix10`

## 结果核验（回传 $OUT 后，主机侧独立重算）

```bash
python -I scripts/judge_radioml_dualsdr.py \
  --input-package <npu-ab1 input_package> \
  --digital results/digital_roundtrip/digital_roundtrip.tsv \
  --board <回传的 board_results.tsv> \
  --out-dir <fresh judge dir>
```

判定器从逐样本 TSV 独立重算（不信汇总行），输出三臂 coverage/准确率口径/翻转/混淆/per-class/per-SNR；
hard_invalid 绝不强制为成功；gate-reject = e2e 失败。arm C 未回传时该臂标 PENDING，不虚构数字。

## 对照表（arm C 待回填）

| 证据 | 结果 |
|---|---|
| arm A Host BF16 原始 RadioML 480 帧（参考） | 419/480 = 87.29%（0dB 68/120、10dB 118/120、20dB 117/120、30dB 116/120） |
| arm D 数字无 RF 回环（本任务） | **预测一致率 419/480 = 87.29%，diverge_vs_arm_A = 0**（corr≈0.99999998、nmse 4.2e-8、byte_identical=0/480 诚实）；per-SNR/per-class 与 arm A 逐帧一致 |
| arm C 双 SDR 480 帧 | **待实测回填**（coverage/gated/e2e/每类/每SNR/翻转） |

## 判读与停止条件

- arm D 预测与 arm A **逐帧零分歧**（diverge=0）→ 量化/适配/数字回环不改变任何预测；RF 损失仅 arm C 能测。
- arm D corr≈1 且 byte_identical=0 → 量化差是「诚实非同一」，不误归因 RF。
- arm C 未回传前，**不**下任何关于双 SDR 准确率的结论。
- 完成离线核验、身份核验、结果回传后暂停。

## 红线（未越）

不训练、不重量化、不改模型/预处理/恢复器/门限（0.100 本任务不改）；旧 phase 行为逐字节不变；
输出目录不覆盖；不写 RF_PASS / PROJECT_COMPLETE / HOST_MATCH 或任何超过本次测量的结论；
共享契约 `tx_derived_conversion_contract.{md,json}` 与 singlesdr 树 byte-identical；无 TX、无训练。
