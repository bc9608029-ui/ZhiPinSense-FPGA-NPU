# M29 RML23 — fix10clean2b-smoke 纯净 IQ 双 SDR 发射/接收/识别（2 样本烟测）审计

> 状态：**`M29-RML23-FIX10CLEAN2B-DUAL-SDR-CLEAN-IQ-READY-FOR-BOARD-TEST`**（最高允许）
> 本任务是**离线交付**，Step 0/3/6 板测由用户执行；作者不碰板。
> 仅当用户 Step 6 双 SDR 板测通过（`scored=2 / prediction_agreement=2/2 / …`）后，才写
> `M29-RML23-FIX10CLEAN2B-DUAL-SDR-CLEAN-IQ-SMOKE-PASS`。
> 禁止写：`RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE / FINAL_* /
> ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`。

---

## 1. 为什么做

fix10clean2a 已证明：按本地 RadioML 数据域构造的**纯净 IQ**（formal12000，raw24 0.99325 /
deployed23 0.99450）能被冻结 PyTorch 模型（ADAMRV11Net，checkpoint `96cd25f8…`）准确识别。
fix10prep2 已搭好 **PC 控 TX SDR / 板端控 RX SDR** 的真实双 SDR 拓扑。本任务把两者接起来，
回答：「纯净 IQ payload 经 **PC-TX → 50Ω 同轴 → 板端 RX → 同步/CFO/SRO/增益恢复 → 板端
NPU**，预测是否与冻结 PyTorch baseline 一致？」。**只做 2 个样本**：

- **BPSK**：`source_index=1500`，seed `2001500`，`frozen_deployed23_pred=3`，`correct=1`
- **4ASK**：`source_index=500`，seed `2000500`，`frozen_deployed23_pred=1`，`correct=1`

两样本均为每类固定第 1 个 k=0（非置信挑选），冻结召回均 1.0。

## 2. 拓扑

```
 Windows PC (radioconda Python)                     板端 Linux (FMQL30TAI)
 ┌────────────────────────────┐                    ┌────────────────────────────┐
 │ pc_tx_sdr_fix10.py         │                    │ run_gate9_rml23.sh         │
 │  · TX SDR open/config      │   TCP control       │  --phase=iq-pc-tx-board-  │
 │  · clean ci16 burst build  │◄───────────────────►│   rx-23class-fix10        │
 │  · cyclic TX (仅 START)     │  + identity + SHA  │  · RX SDR open (NO TX API)│
 │  · 独立 watchdog ≤2s        │   (无 IQ 数据)       │  · 复用 h5 恢复核心        │
 └────────────┬───────────────┘                    │  · NPU24 → 24→23 merge    │
              │ 50Ω 同轴                              └────────────┬──────────────┘
              └────────────── TX ────────────────────────────► RX ┘
```

两端**只通过 TCP(39010) 交换控制消息 + 样本身份 + SHA**，**不经网络传实时 IQ**。纯数字 IQ
路径、单 SDR 恢复核心、模型/权重/标签/预处理/24→23 映射、TCP 状态机**完全不变**。

## 3. 基线

- 权威基线 = **fix10prep2**（累计到 h5、已 READY-FOR-BOARD-TEST）：
  `F:\嵌赛\fix10prep2_work\sdr_rml23_live_board_package_iq_rf_loopback_fix10prep2`。
- clean2b 工作树 = 整树复制 fix10prep2 + 下述增量；**fix10prep2 原树只读不动**（Step 0 仍用
  原树跑）。
- 六红线头与 fix10prep2 **字节一致**（打包器 fail-closed 校验）：
  `iq_rf_sync_recovery.hpp`、`iq_rf_training_frame.hpp`、`iq_digital_loopback.hpp`、
  `iq_rf_fix9r_baseline.hpp`、`iq_clean_baseline.hpp`、`iq_pc_tx_board_rx_transfer_fix10.hpp`。
- 帧布局（fix10prep2 h5，本任务不改变）：`kPayloadComplex=53760, kTotalBurstComplex=59904,
  kPayloadStart=3072, kPayloadTrainingOffset=2048, kPayloadTrainingSamplesPerSymbol=32,
  kFs=2560000, kTrainAmp=2048`。ZC 前导 1024 → settling-zero 1024 → payload 训练 1024
  → payload 53760 → guard 2048 → tail 1024。
- 新输入类型字符串 = `radioml-compatible-clean-d2-2p56m`（任务书 §8 原文）。既有
  `radioml-d2-2p56m` 继续用于 Step 0/3 的既有 D2 路径。

## 4. 变更文件清单（patch = 11 源码/树文件 + clean2b_smoke/ 12 文件）

### 新增（7）
| 文件 | 作用 |
|---|---|
| `board_package/iq_clean2b_sidecar.hpp` | 新输入类型侧车：`clean2b::load_clean2b_sidecar`（27 列 manifest，前 24 列逐字段镜像 `load_d2_sidecar`，后 3 列 `tx_scale/frozen_raw24_pred/frozen_deployed23_pred` fail-closed）+ `manifest_name_for_kind`/`manifest_path_for_kind`（未知 kind throw）+ 重复 source_index 检测 |
| `host_tests/test_clean2b_smoke_d2.cpp` | 27 列 sidecar 解析/门禁/fail-closed 主机测试（37 断言） |
| `host_tests/test_clean2b_smoke_protocol.cpp` | runner 门禁 + dispatch + 两份 6 列 baseline 接线主机测试（18 断言） |
| `scripts/build_clean2b_smoke_d2.py` | Step 1：clean2a 源样本 → D2 重建 → clean2b_smoke/ 12 文件（import `reconstruct`/`recovered_tensor_1024`，不 Python 复刻） |
| `scripts/verify_clean2b_smoke_roundtrip.py` | Step 2：冻结模型往返验证 → `results/clean2b_smoke_roundtrip_report.{json,md}` |
| `scripts/package_clean2b_smoke.py` | 本打包器（确定性两跑 + 独立解包 + 六审计） |
| `docs/M29_RML23_FIX10CLEAN2B_DUAL_SDR_CLEAN_IQ_SMOKE_AUDIT.md` | 本文档 |

### 修改（4，增量，非整文件覆盖）
| 文件 | 改动 |
|---|---|
| `board_package/iq_pc_tx_board_rx_23class_fix10.hpp` | **仅 4 处**：①`#include "iq_clean2b_sidecar.hpp"`；②387-390 门禁放行两种 input_kind；③422-423 加载 dispatch 三元（clean2b kind → `clean2b::load_clean2b_sidecar`）；④535-536 manifest 哈希改用 `clean2b::manifest_path_for_kind`。其余一律不动 |
| `host_tools/pc_tx_sdr_fix10.py` | `manifest_name_for_kind()`（未知 kind `raise ManifestError`）、`ManifestIndex.__init__(frozen_dir, input_kind)`、`on_hello` 传 `self.input_kind`、`_validate_serve_args` 增 input_kind 校验、`run_self_test` 增 input_kind 检查 |
| `host_tests/build_host_tests.sh` | 加 2 个新 C++ 测试的编译块 |
| `host_tests/run_tests.sh` | 加 2 个新 C++ 测试的运行行 |

### frozen-dir 工件（clean2b_smoke/ 12 文件，Step 1 产出，字节冻结）
2 ci16（`clean_bpsk_4713bc2e.ci16`/`clean_4ask_a413e2d4.ci16`，各 215040 B）+ 4 f32
（`source_clean_*.f32`/`recovered_tensor_clean_*.f32`，各 8192 B）+ 4 TSV
（`route_d2_rf_manifest.tsv` 24 列 / `clean2b_smoke_manifest.tsv` 27 列 /
`clean2b_smoke_clean_baseline.tsv` 6 列 / `clean2b_smoke_baseline.tsv` 6 列）+ 1 json
（`clean2b_smoke_build_report.json`）+ 1 SHA sidecar（`clean2b_smoke_SHA256SUMS.txt`）。

## 5. Step 1/2 离线产物（已完成）

- **Step 1**：`F:\嵌赛\fix10clean2b_work\clean2b_smoke\` 12 文件（`clip_count==0`、
  `label_correct=2/2`、`source_float_sha256 != quantized_sha256`、f32/ci16 连续小端、
  预测 TSV 精确键查、确定性两跑一致）。
- **Step 2**：`F:\嵌赛\fix10clean2b_work\results\clean2b_smoke_roundtrip_report.{json,md}`
  —— `prediction_agreement=2/2`、`label_correct=2/2`、`checkpoint_sha256=96cd25f8…`、
  corr≈1 / NMSE≈1e-4 / rms_scale_error≈1e-3（见 §10 roundtrip 一致性）。

## 6. 板端编译命令（无占位符 · make -j1 · 1GB Swap）

> **要求 1**：给出实际可执行的编译命令，`make -j1`（单作业，避免 4×A53 板上 iCraft NPU
> 并行链接 OOM），并含 1GB Swap 准备。

部署目录为 `/root/fix10_clean2b_$TS`（`TS` 见 §7）。生产者
`board_gate9_full_chain_rml23` 的标准构建入口 `build_npu_on_board.sh --gate9-rml23` 内写死
`make -j"$(nproc)"`；板上 `nproc`=4，并行链接易 OOM，故此处给出**等效的 `make -j1` 直编
命令**（`cmake` 参数与 `build_npu_on_board.sh --gate9-rml23` 完全一致），不修改任何构建脚本。

```bash
# ---- 1GB Swap（板载内存受限，iCraft NPU 链接需要；已存在则跳过）----
if ! swapon --show | grep -q /swapfile1g; then
  dd if=/dev/zero of=/swapfile1g bs=1M count=1024
  chmod 600 /swapfile1g
  mkswap /swapfile1g
  swapon /swapfile1g
fi

# ---- 生产者 board_gate9_full_chain_rml23（make -j1，等效 --gate9-rml23）----
cd /root/fix10_clean2b_$TS/board_package
rm -rf build_gate9_rml23
mkdir -p build_gate9_rml23
cd build_gate9_rml23
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_GATE9_RML23=ON \
  -DLIBIIO_ROOT=/opt/sdr/libiio-0.26 \
  -DCMAKE_PREFIX_PATH=/usr/cmake
make -j1 board_gate9_full_chain_rml23
cp board_gate9_full_chain_rml23 /root/fix10_clean2b_$TS/bin/

# ---- UI 服务 board_ui_live_rml23（纯 g++，无 make；2 样本烟测可不编，如需实时 UI 再编）----
cd /root/fix10_clean2b_$TS
./board_package/build_ui_live_rml23.sh
```

编译成功判据：`make -j1` 退出码 0 且 `/root/fix10_clean2b_$TS/bin/board_gate9_full_chain_rml23`
存在（`build_npu_on_board.sh` 的等价 PASS 即 `NPU_BUILD_RESULT gate=9R result=PASS`）。
`LIBIIO_ROOT=/opt/sdr/libiio-0.26`、`ICRAFT_CMAKE_DIR=/usr/cmake`、`LD_LIBRARY_PATH` 的
ModelZoo 依赖（`/home/fmsh/ModelZoo/Deps/so`）为板上实际路径（沿用 fix9r2d 板测口径）。

## 7. 部署（新时间戳目录 · 不得 rm -rf 覆盖历史目录）

> **要求 2**：部署使用新时间戳目录，**不得 `rm -rf` 覆盖历史目录**。

主交付物 = 自包含 full 包（含整树 + clean2b_smoke/）。在 **PC** 侧执行 scp 后，**板端**：

```bash
# PC（Windows PowerShell 或 cmd）：
scp F:\嵌赛\fix10clean2b_work\dist\fix10clean2b_smoke_boardtest_full.tar.gz root@<板IP>:/root/

# 板端（root）：新时间戳目录，绝不 rm -rf 历史目录
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p /root/fix10_clean2b_$TS
tar xzf /root/fix10clean2b_smoke_boardtest_full.tar.gz -C /root/fix10_clean2b_$TS
cd /root/fix10_clean2b_$TS
# 然后按 §6 编译；解压后 clean2b_smoke/ 位于 /root/fix10_clean2b_$TS/clean2b_smoke/
```

**覆盖式 patch 备选路径**（先把 fix10prep2 完整基线目录复制一份，再覆盖 patch，同样新目录、
不 rm -rf）：

```bash
# PC：scp F:\嵌赛\fix10clean2b_work\dist\fix10clean2b_smoke_patch.tar.gz root@<板IP>:/root/
# 板端：
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p /root/fix10_clean2b_$TS
cp -a /root/<fix10prep2_board_tree> /root/fix10_clean2b_$TS/tree
tar xzf /root/fix10clean2b_smoke_patch.tar.gz -C /root/fix10_clean2b_$TS/tree
cd /root/fix10_clean2b_$TS/tree
# 然后按 §6 编译（把 /root/fix10_clean2b_$TS 换成 /root/fix10_clean2b_$TS/tree）
```

`clean2b_smoke/` **同时部署到板端 `--frozen-dir` 与 PC 侧 `--frozen-dir`**（同一份字节，
`clean2b_smoke_SHA256SUMS.txt` 逐文件核对一致）；板端用 `tar xzf` 后自带，PC 侧直接用
`F:\嵌赛\fix10clean2b_work\clean2b_smoke`（§8）。两端 SHA 一致，否则 provenance fail-closed。

## 8. PC 命令（可直接执行的 PowerShell 版本）

> **要求 3**：PC 命令另给 PowerShell 版本，用反引号续行 + `$env:` 变量。

```powershell
# 一次性设置（PowerShell）：
$env:PC_TX_URI      = "usb:1.2.3.4"   # ← 换成 PC 侧 TX SDR 实际 USB 或 ip URI
$env:CLEAN2B_SMOKE_DIR = "F:\嵌赛\fix10clean2b_work\clean2b_smoke"

D:\radioconda\python.exe -I host_tools\pc_tx_sdr_fix10.py `
  --listen 0.0.0.0:39010 `
  --tx-uri $env:PC_TX_URI `
  --frozen-dir $env:CLEAN2B_SMOKE_DIR `
  --input-kind radioml-compatible-clean-d2-2p56m `
  --center 2400000000 --sample-rate 2560000 --tx-bw 18000000 --tx-atten -40 `
  --rf-path direct-cable --rf-tx-target-rms 2048
```

对应 bash 等价命令（供对照，Step 6 用同参数）：`D:\radioconda\python.exe -I
host_tools\pc_tx_sdr_fix10.py --listen 0.0.0.0:39010 --tx-uri "<PC_TX_URI>" --frozen-dir
"F:\嵌赛\fix10clean2b_work\clean2b_smoke" --input-kind radioml-compatible-clean-d2-2p56m
--center 2400000000 --sample-rate 2560000 --tx-bw 18000000 --tx-atten -40 --rf-path
direct-cable --rf-tx-target-rms 2048`。TCP 监听 `0.0.0.0:39010`，板端出站连 `tcp://<PC_IP>:39010`。

## 9. Step 0/3/6 板测命令（baseline 一律绝对路径）

> **要求 4**：Step 3/6 的 baseline（`--frozen-dir` 与 `--baseline`）全部使用明确绝对路径。

### Step 0（基线拓扑，fix10prep2 原树，RadioML D2）—— fix10prep2 交付命令，不改
```bash
# PC（radioconda）：
D:\radioconda\python.exe -I host_tools\pc_tx_sdr_fix10.py --listen 0.0.0.0:39010 \
  --tx-uri "<PC_TX_URI>" --frozen-dir "$D2_SMOKE_DIR" --input-kind radioml-d2-2p56m \
  --center 2400000000 --sample-rate 2560000 --tx-bw 18000000 --tx-atten -40 \
  --rf-path direct-cable --rf-tx-target-rms 2048
# 板端：
./scripts/run_gate9_rml23.sh --phase=iq-pc-tx-board-rx-23class-fix10 \
  --tx-control=tcp://<PC_IP>:39010 --rx-uri="<BOARD_RX_URI>" \
  --input-kind=radioml-d2-2p56m --frozen-dir="$D2_SMOKE_DIR" \
  --baseline=route_f_fix9r_exact_baseline.tsv --center=2400000000 --rx-gain=30 \
  --rf-path=direct-cable --rf-tx-target-rms=2048 --diagnostic-classes=BPSK,4ASK \
  --out-dir=/root/fix10_pc_tx_board_rx_smoke
```
门禁：`scored=2 / rf_excluded=0 / prediction_agreement=2/2 / tx_restore_ok / rx_restore_ok /
negative_control=PASS`；失败即停，报唯一失败项。

### Step 3（clean 数字 NPU 直注 2 ci16，无 PC/无 TX/无 RF）
```bash
LIBIIO_ROOT=/opt/sdr/libiio-0.26 \
LD_LIBRARY_PATH=/opt/sdr/libiio-0.26/lib:/home/fmsh/ModelZoo/Deps/so \
./scripts/run_gate9_rml23.sh \
  --phase=iq-clean-iq-23class-fix10 \
  --input-kind=radioml-d2-2p56m \
  --frozen-dir=/root/fix10_clean2b_$TS/clean2b_smoke \
  --baseline=/root/fix10_clean2b_$TS/clean2b_smoke/clean2b_smoke_clean_baseline.tsv \
  --max-files=2 \
  --out-dir=/root/fix10_clean2b_smoke_direct
```
门禁：`scored=2 / excluded=0 / prediction_agreement=2/2 / label_correct=2/2`。该 phase 无
`--diagnostic-classes`，用 `--max-files=2` 取唯一 2 个 holdout 样本。

### Step 6（真实双 SDR clean IQ 烟测）
```bash
LIBIIO_ROOT=/opt/sdr/libiio-0.26 \
LD_LIBRARY_PATH=/opt/sdr/libiio-0.26/lib:/home/fmsh/ModelZoo/Deps/so \
./scripts/run_gate9_rml23.sh \
  --phase=iq-pc-tx-board-rx-23class-fix10 \
  --tx-control=tcp://<PC_IP>:39010 \
  --rx-uri="<BOARD_RX_URI>" \
  --input-kind=radioml-compatible-clean-d2-2p56m \
  --frozen-dir=/root/fix10_clean2b_$TS/clean2b_smoke \
  --baseline=/root/fix10_clean2b_$TS/clean2b_smoke/clean2b_smoke_baseline.tsv \
  --center=2400000000 --rx-gain=30 --rf-path=direct-cable \
  --rf-tx-target-rms=2048 \
  --diagnostic-classes=BPSK,4ASK --diagnostic-per-class=1 \
  --out-dir=/root/fix10_clean2b_smoke_rf
```
门禁：`scored=2 / rf_excluded=0 / prediction_agreement=2/2 / tx_restore_ok=1 /
rx_restore_ok=1 / negative_control=PASS / CFO finite·in-range / training estimate valid`。
PC 端与板端 `--frozen-dir` 必须是同一份 `clean2b_smoke/`（§7 SHA 一致）。

## 10. roundtrip 两个报告一致性（要求 5）

| 项 | `clean2b_smoke_roundtrip_report.json` | `clean2b_smoke_roundtrip_report.md` |
|---|---|---|
| 路径 | `F:\嵌赛\fix10clean2b_work\results\clean2b_smoke_roundtrip_report.json` | `F:\嵌赛\fix10clean2b_work\results\clean2b_smoke_roundtrip_report.md` |
| 是否入包 | **不入包**（离线验证产物，板测 bundle 之外的独立报告） | **不入包**（同上，与 json 同路径同目录） |
| 样本数 | `n_samples=2`，`samples[]` 2 条（4ASK 500 / BPSK 1500） | 2 行（4ASK 500 / BPSK 1500） |
| 结论 | `prediction_agreement="2/2"`、`label_correct="2/2"` | `prediction_agreement = 2/2`、`label_correct = 2/2` |

两报告**路径同级同目录、均不入包、最终文件数一致（各 2 样本）**；`checkpoint_sha256` 均为
`96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d`。

## 11. 红线（逐条不破）

- §5：不 Python 复刻重采样数学（只 import `reconstruct`/`recovered_tensor_1024`）；不改纯净
  信号调制参数；不加噪声/CFO/SRO/多径；不用标签调幅度/恢复参数；`tx_scale` 口径与 C++
  `build_tx_burst_from_frozen` 逐字节一致。
- §8：不改 `iq_rf_sync_recovery.hpp`、帧布局+训练块、模型/权重、预处理、24→23 映射、
  corr/residual/clip/CFO/SRO 门限、TCP 状态机（`iq_pc_tx_board_rx_transfer_fix10.hpp`）、
  `iq_digital_loopback.hpp`（含 `load_frozen_iq`/`load_d2_sidecar`）、`iq_rf_fix9r_baseline.hpp`、
  `iq_clean_baseline.hpp`。
- §12：失败后不降门限/不固定补偿 CFO/不改 baseline prediction/不挑高置信样本/不直接扩 24 类。

## 12. 验证记录（离线）

- **host 全套**：`build_host_tests.sh` + `run_tests.sh` → `ALL HOST TESTS PASSED`（exit 0）；
  含 2 个新测试 `test_clean2b_smoke_d2`（37/0）与 `test_clean2b_smoke_protocol`（18/0），
  fix10prep2 既有全套（PC-TX/Board-RX 协议/状态机/CFO 边界/clean 路径）无回归。
- **Step 1 确定性**：`build_clean2b_smoke_d2.py` 两跑 12 文件 SHA 全一致；`clip_count==0`；
  `label_correct=2/2`；`source_float_sha256 != quantized_sha256`；f32/ci16 连续小端断言过；
  预测 TSV 精确键、缺失/重复 fail-closed。
- **Step 2 往返**：`prediction_agreement=2/2`、`label_correct=2/2`、corr≈1 / NMSE≈1e-4 /
  rms_scale_error≈1e-3。
- **红线校验**：六红线头 vs fix10prep2 字节一致；`iq_pc_tx_board_rx_23class_fix10.hpp` 改动
  仅限 §4 所列 4 处（打包器 red-line + complete-delta 审计）。
- **确定性 bundle**：full / patch 两包两跑字节一致 + 独立解包逐文件 SHA 全过；`SHA256SUMS`
  齐全（§13 工件）。最终两包 64-hex SHA 记录于交付消息与记忆条目，**不硬编码于此文档**
  （本文档自身入包，若在此写 SHA 会自指循环）。

## 13. 工件（打包器产出，dist/ 下）

| 工件 | 路径 |
|---|---|
| 自包含 full 包 | `F:\嵌赛\fix10clean2b_work\dist\fix10clean2b_smoke_boardtest_full.tar.gz` |
| 覆盖式 patch | `F:\嵌赛\fix10clean2b_work\dist\fix10clean2b_smoke_patch.tar.gz` |
| full 逐文件+包 SHA | `F:\嵌赛\fix10clean2b_work\dist\fix10clean2b_smoke_boardtest_full_SHA256SUMS.txt` |
| patch 逐文件+包 SHA | `F:\嵌赛\fix10clean2b_work\dist\fix10clean2b_smoke_patch_SHA256SUMS.txt` |

两包均为**平铺（无顶层包裹目录）**：full 包解压后 `board_package/`、`clean2b_smoke/` 等直接
落盘；patch 包解压到已复制的 fix10prep2 树后原位覆盖。确定性：uid/gid 0、mtime 0、排序条目、
gzip level 9 mtime 0。

## 14. 已知风险 / 遗留

- Step 3 用 `iq-clean-iq-23class-fix10`（评审 #1 指定）。该路径此前对**完整 23 类**曾有
  22/24 类历史缺陷；本任务**只判 BPSK/4ASK 两样本**，失败即如实上报，不修、不绕过、不放宽。
- 双 SDR 独立晶振 → CFO 可能超单 SDR 无歧义范围（±625 Hz）；首次板测超范围即停、报真实失败
  项，不放宽/不猜修（沿用 fix10prep2 §8 硬要求）。
- `original_sha256` 采用 `source_float_sha256`（原始 clean 源样本字节），与
  `gen_generated_clean_23.py` 的 `original==quantized` 约定不同（clean2b 有独立 clean2a 源
  样本，故分开），已在 manifest 注释中明确，防与 RadioML D2 路径混淆。
