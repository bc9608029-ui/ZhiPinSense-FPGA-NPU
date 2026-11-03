# fix10class24-original-radioml-dc-ab1 — 双 SDR 最小 DC 适配对照（集成，就绪待上板）

## 状态

**`M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DC-AB1-DUALSDR-READY-FOR-BOARD-TEST`**

- 本环境**无板端访问通道**（无 SSH/串口/MCP 板端工具），故**尚未执行任何板端 RF 收发/推理**；
  板端 C++ 在 aarch64 编译，本环境 g++ 不可用，**未实际编译板端二进制**。
- 已完成：**集成 PATCH**（单 + 双 SDR 相位与 DC 在 `gate9_phase.hpp` + `main()` 共存，无手工合并）、
  **双 SDR arm C producer 的 `--adaptation=direct|dc-transport` 支持**（input_kind 由
  adaptation 派生，双端 HELLO 立即 fail-closed 校验一致）、两套**带 `route_d2_rf_manifest.tsv`**
  的输入包、五臂判定器、板端编排脚本、**离线只读核验 13/13**。
- **不得报告「已测过」**。下方「C-direct / C-dc」两行留空，等真实板端输出回填。

## 与单 SDR 交付的关系（不冲突，本交付是超集）

- 单 SDR DC PATCH（`package_radioml_dc_singlesdr_ab1.py` 产物）**已交付且在板测中，本任务不动**。
- 本集成 PATCH 是它的**超集**：单 SDR DC 文件（`radioml_singlesdr_ab_{loader,runner}.hpp`、
  `radioml_dc_adapt.hpp`、DC 契约、DC 脚本）逐字节一致；`gate9_phase.hpp` 与
  `board_gate9_full_chain_rml23.cpp` 由「2 相位（npu + singlesdr）」升级为「**3 相位
  （npu + dualsdr + singlesdr）**」——这是本集成 PATCH 的唯一结构性差异，其余单 SDR 内容不变。
- 一条集成 PATCH 覆盖在 **npu-ab1 FULL 树**之上，即同时得到单 + 双 SDR + DC 的全部 producer。

## 任务问题（同一批 frozen 原始 RadioML，双 SDR 两条适配路径对照）

同一批 480 帧（同一 `hdf5_row_index`、同一 `X[row].T` 合同、同一 `model_input_sha256`）
走同一条**双 SDR** 链（PC 控 TX 循环 canonical burst → 50Ω 同轴 → 板控 RX 捕获 →
coarse CFO → fine sync/gain → wide-linear → 0.100 门 → NPU24 → RAW-24 argmax，无合并），
仅切换 `--adaptation`：

| 路径 | 链 | 回答 |
|---|---|---|
| **direct** | iq → cyclic tile 1024→53760 → CI16(RMS2048) → 恢复 → 前 1024 × unscale | 现有行为，**逐字节不变**（基准） |
| **dc-transport** | dc=mean(iq) → ac=iq−dc → CI16(ac,2048/ac_rms) → 恢复 → ac[:1024]×inverse_scale + dc | 移除 DC 只传 AC 后，双 SDR RF 链准确率是否变化 |

三条铁律（契约 `contract/dc_transport_adaptation_contract.{md,json}` 是单一权威）：
**direct 逐字节不变**；**DC 数学只有一份**（`radioml_dc_adapt.{py,hpp}`，双 SDR 与单 SDR
runner 都 include 它）；**三段式不双重还原**（阶段 1 RF 增益 / 阶段 2 TX 尺度 / 阶段 3 DC
加回）。DC 参数绑定 **input SHA**，绝不绑定类别/识别结果。

双 SDR 特有：适配模式由 `--adaptation` **单一来源**决定，`input_kind` 由它派生
（direct = `radioml-original-dualsdr-ab-2p56m`；dc = 该串 + `-dc-transport`）。PC TX 服务
与板端 HELLO 都校验 `input_kind` + `manifest_sha256`，双端适配不一致在 HELLO 立即拒绝。

这是**测量**，不是新模型优化：不训练、不改模型、不改预处理/恢复器/门限。

## 冻结身份（逐字节不变）

| 身份 | 冻结值 |
|---|---|
| 模型 JSON / RAW / CKPT | `28272abc…` / `c1781aec…` / `96cd25f8…` |
| 训练输入合同 | `ascontiguousarray(X[row].T).astype(float32)` → `[2,1024]` f32 LE |
| 24 类标签序 | `rml24::kLabelOrder24`，AM-SSB WC=17/SC=18 独立 |
| 480/24 帧身份 | 与 npu-ab1 逐字节一致（selection_id/hri/类/SNR/input_sha256） |
| direct 18 列 / dc 22 列清单 | `contract/tx_derived_conversion_contract.*`（direct）＋`contract/dc_transport_adaptation_contract.*`（dc 增量） |
| RF 契约 | 2.56 Msps、中心 2.4 GHz、RX/TX BW 18 MHz、RX 手动 35 dB、TX ≤ −40 dB、RMS2048 |
| 恢复/门限 | 生产 `recover_payload_with_coarse_cfo` + 0.100 门 + 至多 3 次重捕 + 末次选择 |
| 双 SDR 控制通道 | `iq_pc_tx_board_rx_transfer_fix10.hpp`（红绳，不改）；只传控制消息 + 身份 + SHA，不传实时 IQ |

## 基线层（哪些冻结文件**假定已在板端**，本 PATCH 不携带）

本 PATCH 是**纯增量**，覆盖在 **npu-ab1 FULL 树**之上（tx-rms-sweep1 + npu-ab1 PATCH +
scalarwl-4way PATCH 已应用）；解压时**只新增/替换下列文件**，绝不手工合并其它文件：

- 17 个恢复/runner 生产头（`chain_common.hpp`、`npu_classifier24.hpp`、
  `iq_rf_per_frame_recovery.hpp`、`iq_dual_sdr_coarse_cfo_recovery.hpp`、
  `iq_pc_tx_board_rx_transfer_fix10.hpp`、`iq_fix10_canonical_frame.hpp`、`rml24_raw.hpp`、
  `sdr_adapter/*` 等）；
- `model_rml24_bf16/rml24_adamrv11_bf16.{json,raw}`（冻结 BF16 模型）；
- `scripts/run_gate9_rml23.sh`、`scripts/common_rml23.sh`、
  `board_package/build_npu_on_board.sh`、`bin/board_gate9_full_chain_rml23`（旧版）。

本 PATCH 新增/替换：`radioml_dc_adapt.hpp`（新增共享 DC 头）、
`radioml_singlesdr_ab_{loader,runner}.hpp`（DC 版，与单 SDR PATCH 逐字节一致）、
`radioml_dualsdr_ab_{loader,runner}.hpp`（DC 版）、`gate9_phase.hpp` +
`board_gate9_full_chain_rml23.cpp`（**3 相位集成版**）、DC 契约 + DC 脚本 +
双 SDR producer/judger/run 脚本 + 本文档。

## 离线只读核验（主机侧，全部 PASS）

`host_tests/test_radioml_dc_dualsdr.py` **13/13**：

| # | 核验项 | 结果 |
|---|---|---|
| 1 | 480 帧主键唯一 + 身份（与 npu-ab1 逐字节一致） | ✅ |
| 2 | short24 固定选取（每类 1 帧 @30dB 最小 selection_id = 361,366,…,476） | ✅ |
| 3 | DC 适配确定性 + 类无关 + 去 DC 后 AC 循环铺排近似保 RMS | ✅ |
| 4 | DC 数字理想往返还原原始 IQ（corr>0.999999, 无裁剪/非有限） | ✅ |
| 5 | dc-transport 22 列清单：表头逐字 == 契约、DC 参数逐帧复算一致 | ✅ |
| 6 | dualsdr loader 契约 + DC 参数绑定 input SHA（源码审计） | ✅ |
| 7 | dualsdr runner 红线（--adaptation 门 + input_kind 派生 + DC 分支 + direct 分支逐字不变 + RX-only + HELLO manifest_sha256） | ✅ |
| 8 | 共享 DC 头单一实现（单/双 runner 均 include radioml_dc_adapt.hpp） | ✅ |
| 9 | 冻结模型 SHA + 契约 JSON token | ✅ |
| 10 | PC-TX producer DC-aware（input_kind 派生 / direct·dc 24 列映射 / route_d2 表头 / TX −40）+ --self-test PASS | ✅ |
| 11 | 集成 gate9_phase + board_gate9 三相位共存（npu + dualsdr + singlesdr） | ✅ |
| 12 | 数字验证 24 帧：original 复现 arm A 24/24、direct/dc 全对、dc 与 direct 24/24 | ✅ |
| 13 | direct route_d2_rf_manifest.tsv 逐字节 == dualsdr-ab1 fork 权威值（direct 逐字节不变） | ✅ |

## PATCH / 输入包清单与完整 SHA256

> 三件 tar.gz 的**完整 64 hex SHA256** 见 `dist/` 内的 `*_SHA256SUMS.txt` 同目录回传记录
> 与交付报文；此处不写入以避免自引用。板端解压后用 `sha256sum -c` 对包内文件逐项校验。

| 包 | 内容 | 说明 |
|---|---|---|
| 集成 PATCH `sdr_rml24_fix10class24_original_radioml_dc_ab1_dualsdr_patch.tar.gz` | 全部 producer 文件 + `…_DUALSDR_PATCH_SHA256SUMS.txt` | 单 + 双 SDR + DC 集成 |
| dualsdr direct 输入包 `…_dualsdr_direct_inputs.tar.gz` | 480 × `<sid>.i16` + 18 列 `tx_manifest.tsv` + **`route_d2_rf_manifest.tsv`** + sidecar | direct 逐字节不变 |
| dualsdr dc 输入包 `…_dualsdr_dc_inputs.tar.gz` | 480 × `<sid>.i16` + 22 列 `tx_manifest.tsv` + **`route_d2_rf_manifest.tsv`** + sidecar | dc-transport |

> 双 SDR 输入包的 `.i16` 与单 SDR 输入包**逐字节相同**（同一导出源）；唯一差异是双 SDR
> 额外携带 `route_d2_rf_manifest.tsv`（HELLO `manifest_sha256` 所需）。同一
> input+mode 下单/双 SDR 的 burst 逐字节一致。

## 板端执行（用户串口 COM12 执行；本环境无法连接板端）

前置：PC 与板端 TX/RX 用 **50Ω 同轴直连**（无天线无放大器）；PC 侧 TX SDR、板端 RX SDR
各一；PC 是控制通道 SERVER（39010），板端是 CLIENT。

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

### Step 2 — 串口 COM12 上传三个 tar.gz，校验整体 SHA

用你既有的串口文件传输方式（ZMODEM `rz`/`sz` 或 base64 粘贴）把 `dist/` 下三个 tar.gz
传到板端（建议 `/root/`），然后**逐个校验整体 SHA256**（期望值见交付报文）：

```bash
cd /root
sha256sum sdr_rml24_fix10class24_original_radioml_dc_ab1_dualsdr_patch.tar.gz
sha256sum sdr_rml24_fix10class24_original_radioml_dc_ab1_dualsdr_direct_inputs.tar.gz
sha256sum sdr_rml24_fix10class24_original_radioml_dc_ab1_dualsdr_dc_inputs.tar.gz
# 三者必须与交付报文给的三条 64 hex 完全一致；任一不符立即停，不要继续。
```

### Step 3 — 解压集成 PATCH 到项目根，校验包内 SHA

```bash
cd "$PROJ" || exit 1
tar -xzf /root/sdr_rml24_fix10class24_original_radioml_dc_ab1_dualsdr_patch.tar.gz
sha256sum -c FIX10CLASS24_ORIGINAL_RADIOML_DC_AB1_DUALSDR_PATCH_SHA256SUMS.txt
# 期望: 全部内容文件 OK
```

> PATCH 是「扁平相对路径」内容，直接解压到项目根。`gate9_phase.hpp` +
> `board_gate9_full_chain_rml23.cpp` 升级为 3 相位集成版（npu + dualsdr + singlesdr），
> 覆盖旧 2 相位版；`radioml_singlesdr_ab_{loader,runner}.hpp` 为 DC 版（与单 SDR PATCH
> 逐字节一致），`radioml_dualsdr_ab_{loader,runner}.hpp` 为 DC 版，`radioml_dc_adapt.hpp`
> 为新增。

### Step 4 — 解压两套双 SDR 输入包（板端 `--input-dir`，各自全新目录）

```bash
# dualsdr direct 输入包（18 列 + route_d2）:
DIRECT_IN=/root/rml24_dc_ab1_dualsdr_direct_inputs
mkdir -p "$DIRECT_IN" && cd "$DIRECT_IN"
tar -xzf /root/sdr_rml24_fix10class24_original_radioml_dc_ab1_dualsdr_direct_inputs.tar.gz
sha256sum -c FIX10CLASS24_ORIGINAL_RADIOML_DC_AB1_DUALSDR_DIRECT_INPUTS_SHA256SUMS.txt
# 期望: 480 个 .i16 + tx_manifest.tsv + route_d2_rf_manifest.tsv 全部 OK

# dualsdr dc-transport 输入包（22 列 + route_d2）:
DC_IN=/root/rml24_dc_ab1_dualsdr_dc_inputs
mkdir -p "$DC_IN" && cd "$DC_IN"
tar -xzf /root/sdr_rml24_fix10class24_original_radioml_dc_ab1_dualsdr_dc_inputs.tar.gz
sha256sum -c FIX10CLASS24_ORIGINAL_RADIOML_DC_AB1_DUALSDR_DC_INPUTS_SHA256SUMS.txt
# 期望: 480 个 .i16 + tx_manifest.tsv + route_d2_rf_manifest.tsv 全部 OK
```

### Step 5 — 构建 producer（**单线程**；板端内存受限，不要并行 make）

`build_npu_on_board.sh` 内部是 `make -j$(nproc)`（并行），本步骤改用手动 **`make -j1`**
单线程，避免板端内存不足：

```bash
cd "$PROJ/board_package" || exit 1
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64
ICRAFT_CMAKE_DIR=/usr/cmake
BUILD_DIR=build_gate9_rml23
TARGET=board_gate9_full_chain_rml23

rm -f "$PROJ/bin/$TARGET"                 # 先删旧二进制（失败不留旧品）
rm -rf "$BUILD_DIR" && mkdir -p "$BUILD_DIR" && cd "$BUILD_DIR"
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_GATE9_RML23=ON \
  -DLIBIIO_ROOT="$LIBIIO_ROOT" -DCMAKE_PREFIX_PATH="$ICRAFT_CMAKE_DIR"
make -j1 "$TARGET"                        # 单线程, 不要并行 make
[ -f "$TARGET" ] && mkdir -p "$PROJ/bin" && cp "$TARGET" "$PROJ/bin/$TARGET" \
  && echo "NPU_BUILD_RESULT gate=9R result=PASS binary=$PROJ/bin/$TARGET"
```

- 期望打印 `NPU_BUILD_RESULT gate=9R result=PASS`；随后 `ls -l "$PROJ/bin/$TARGET"`。
- 若构建失败（`result=FAIL`），保留 `$BUILD_DIR` 与日志，回传后再判读，不要重复覆盖。

### Step 6 — PC 侧先启动 TX 服务（两条各一次，**--adaptation 必须与板端一致**）

在 Windows PC（radioconda）上，先启动与板端 `--adaptation` **一致**的 TX 服务：

```bash
# (a) direct（input_kind = radioml-original-dualsdr-ab-2p56m）
D:\radioconda\python.exe -I scripts/pc_tx_radioml_dualsdr.py launch \
  --tx-payload <DIRECT_IN> --adaptation=direct --tx-uri "<PC_TX_URI>"

# (b) dc-transport（input_kind = …-dc-transport）
D:\radioconda\python.exe -I scripts/pc_tx_radioml_dualsdr.py launch \
  --tx-payload <DC_IN> --adaptation=dc-transport --tx-uri "<PC_TX_URI>"
```

- 服务 `exec` 后监听 `0.0.0.0:39010`，只传控制消息 + 身份 + SHA，**绝不传实时 IQ**。
- 板端 HELLO 会带 `input_kind` + `manifest_sha256`；若双端 `--adaptation` 不一致，
  服务在 HELLO 阶段**立即 fail-closed 拒绝**（不静默、不事后发现）。

### Step 7 — 两条 short24 运行命令（板端，direct / dc-transport）

short24 = 每类 1 帧 @30dB（selection_id 361,366,…,476），**不做 480**。

```bash
cd "$PROJ" || exit 1

# (a) --adaptation=direct（逐字节不变基准）
bash scripts/run_radioml_dc_dualsdr.sh \
  --mode=short24 --adaptation=direct \
  --input-dir="$DIRECT_IN" \
  --tx-control="tcp://<PC_IP>:39010" \
  --rx-uri="<板端 RX SDR URI>" \
  --out-dir="/root/rml24_dc_dualsdr_direct_$(date +%s)"

# (b) --adaptation=dc-transport
bash scripts/run_radioml_dc_dualsdr.sh \
  --mode=short24 --adaptation=dc-transport \
  --input-dir="$DC_IN" \
  --tx-control="tcp://<PC_IP>:39010" \
  --rx-uri="<板端 RX SDR URI>" \
  --out-dir="/root/rml24_dc_dualsdr_dc_$(date +%s)"
```

- 期望打印 `RADIOML_ORIGINAL_DC_DUALSDR_START … adaptation=direct|dc-transport …`，
  与测量完成标记（`board_summary.json` 的 `measurement_token`）。
- 若 `device_not_found` 退码 2 或 HELLO 失败，保留原始记录回传，不要覆盖 `$OUT_DIR`。

### Step 8 — 回传整个 $OUT

每条命令回传整个 `$OUT_DIR`（含 `board_results.tsv` 19 列 + `board_logits.tsv` +
`recovered/<sid>.raw.i16`（**每样本**原始捕获，含门拒/hard-invalid）+
`recovered/<sid>.diag.json`（**每样本**恢复诊断）+
`recovered/*.bin`（过门样本模型输入）+ `board_summary.json` + `run.log`）。

> runner 在过门分支**之前**无条件落盘 `<sid>.raw.i16` 与 `<sid>.diag.json`，因此
> gate-reject / hard-invalid / 不可恢复样本同样落盘原始捕获 + 恢复诊断；这些样本
> **仍计入分母，绝不剔除**。

## 结果核验（回传两个 $OUT 后，主机侧独立重算）

```bash
python -I scripts/judge_radioml_dc_dualsdr.py \
  --input-package <npu-ab1 input_package> \
  --digital <results/digital_roundtrip_dc/digital_predictions_dc.tsv> \
  --board-direct <direct 回传的 board_results.tsv> \
  --board-dc <dc-transport 回传的 board_results.tsv> \
  --out-dir <fresh judge dir>
```

五臂 A / D-direct / D-dc / C-direct / C-dc 从逐样本 TSV 独立重算（不信汇总行），输出
coverage/准确率口径/翻转（含核心 `C_direct_to_C_dc`）/混淆/per-class/residual+corr；
**hard_invalid 绝不强制为成功；gate-reject = 端到端失败（分母不剔除）**；board_results.tsv
未回传时该臂标 PENDING，不虚构数字。

## 对照表（待回填）

| 证据 | 结果 |
|---|---|
| arm A Host BF16 原始 RadioML（参考） | 419/480 = 87.29%（0dB 68/120、10-30dB ≥ 96.7%） |
| D-direct / D-dc 数字无 RF 回环（本任务，24 帧） | 全对 24/24，dc 与 direct 24/24 一致（诚实：数字域，不声明生产恢复等效） |
| **C-direct 双 SDR short24（本任务 direct）** | **待实测回填** |
| **C-dc 双 SDR short24（本任务 dc-transport）** | **待实测回填** |

## 判读与停止条件

- C-direct / C-dc 未回传前，**不**下任何关于 dc-transport RF 准确率的结论。
- 核心判读：`C_direct_to_C_dc` 翻转 + 两臂 e2e 准确率差 + residual/corr 分布差；
  与单 SDR 的 `S_direct_to_S_dc` 对照（同一 24 帧、同一适配数学、同一 `.i16`）。
- 完成离线核验、身份核验、结果回传后暂停，等待回填判读。

## 红线（未越）

不训练、不重量化、不改模型/预处理/恢复器/门限（0.100 本任务不改）；direct 行为逐字节
不变（direct route_d2_rf_manifest.tsv 与 `.i16` 均逐字节 == dualsdr-ab1 权威值，无秘密改
尺度）；DC 数学只有一份（`radioml_dc_adapt.{py,hpp}`）；三段式不双重还原；DC 参数绑定
input SHA；控制通道头 `iq_pc_tx_board_rx_transfer_fix10.hpp` 不改；输出目录不覆盖；板端
绝不强制分类；TX 衰减不高于 −40 dB（PC TX 服务/producer 侧）；RX 手动 35 dB；中心 2.4 GHz、
采样 2.56 Msps、RX/TX 带宽 18 MHz；不按类修改参数、不按标签挑选捕获或补偿结果。
