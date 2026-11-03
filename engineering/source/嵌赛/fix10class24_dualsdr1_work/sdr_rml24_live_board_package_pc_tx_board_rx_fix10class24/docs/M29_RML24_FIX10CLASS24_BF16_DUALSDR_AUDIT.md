# M29 RML24 — fix10class24-dualsdr1 24 类 BF16 双 SDR 交付审计（Phase C）

> 状态：**`M29-RML24-FIX10CLASS24-BF16-DUALSDR-READY-FOR-BOARD-TEST`**（最高允许）
> 本档是 **Phase C 离线交付**记录；作者不碰板，真实 24 类板测由用户执行。
> 禁止提前写：`SMOKE-PASS / RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE / FINAL_*`。
> 真实 24 类板测通过前，本档状态**只能**停在 `READY-FOR-BOARD-TEST`。

---

## 1. 交付结论（离线）

24 类（RadioML2018 全 24 类，**未合并** AM-SSB-WC/SC）双 SDR 集成已完成离线交付。
它建立在 fix10prep3 post-smoke 板测基线上（`26bb1241…` full + `ba2cb426…` patch，见 §8），
**只携带可审计的 24 类增量**，共享恢复/TX 控制实现全部来自 Phase B 实际板测版本
（红线头逐字节一致，见 §6）。

本轮交付为**离线就绪**：主机 BF16 推理 24/24、变更集逐字节审计、确定性打包全过。
**尚未真实上板**；板端命令见 §9，等待用户执行。

## 2. 24 类模型与合同（BF16 全网络）

| 项 | 值 |
|---|---|
| 模型 | 冻结 full-network BF16，checkpoint `96cd25f875…`（与 23 类同一冻结源） |
| JSON SHA256 | `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` |
| RAW SHA256 | `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` |
| 标签合同 SHA256 | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` |
| 拓扑 | 1 Input + **122 HardOp** + 1 Output；**122 → @zhuget(330) NPU** + 2 → @hostt |
| int8 张量 | **0**（零 int8 存储） |
| 输入 | `[1,2,1024]` fp32 @hostt（plane0=I，plane1=Q，C 序） |
| 输出 | `[1,24]` fp32 @hostt（raw logits，无 softmax） |
| 部署模式 | `RAW24_UNMERGED`（WC=17 / SC=18 保持独立，**无 24→23 合并**） |
| iCraft | v3.39.0，verdict `DEPLOYABLE_FULL_NETWORK_BF16` |

`model_rml24_bf16/` 内 `network_mapping_report.json` / `compiler_metadata.json` /
`model_SHA256SUMS.txt` 是权威证据；`scripts/audit_rml24_bf16_network.py` 可离线重生成
报告并 fail-closed 校验上述 SHA 与 census。

## 3. 24 类标签序 + 24 固定样本

`contracts/rml24_raw_contract.py` 冻结的标签序（index 0..23）：

```text
0 OOK   1 4ASK   2 8ASK   3 BPSK   4 QPSK    5 8PSK    6 16PSK   7 32PSK
8 16APSK  9 32APSK  10 64APSK  11 128APSK  12 16QAM  13 32QAM  14 64QAM  15 128QAM
16 256QAM  17 AM-SSB-WC  18 AM-SSB-SC  19 AM-DSB-WC  20 AM-DSB-SC  21 FM  22 GMSK  23 OQPSK
```

24 个固定 holdout 样本（`source_index 0..11500 step 500`，每类 1 个），全部
`frozen_bf16_raw24_pred == raw24_class`，model_sha256 列统一为 JSON SHA：

| source_index | raw24_class | modulation |
|---|---|---|
| 0 | 0 | OOK |
| 500 | 1 | 4ASK |
| 1000 | 2 | 8ASK |
| 1500 | 3 | BPSK |
| 2000 | 4 | QPSK |
| 2500 | 5 | 8PSK |
| 3000 | 6 | 16PSK |
| 3500 | 7 | 32PSK |
| 4000 | 8 | 16APSK |
| 4500 | 9 | 32APSK |
| 5000 | 10 | 64APSK |
| 5500 | 11 | 128APSK |
| 6000 | 12 | 16QAM |
| 6500 | 13 | 32QAM |
| 7000 | 14 | 64QAM |
| 7500 | 15 | 128QAM |
| 8000 | 16 | 256QAM |
| 8500 | 17 | AM-SSB-WC |
| 9000 | 18 | AM-SSB-SC |
| 9500 | 19 | AM-DSB-WC |
| 10000 | 20 | AM-DSB-SC |
| 10500 | 21 | FM |
| 11000 | 22 | GMSK |
| 11500 | 23 | OQPSK |

`baselines/clean24_smoke_raw24_bf16_baseline.tsv`（7 列：
`source_index, original_sha256, raw24_class, modulation, split_role, frozen_bf16_raw24_pred, model_sha256`）。
基线加载器 `rml24_bf16_baseline.hpp` 容忍 CRLF、fail-closed（短行/非 64-hex SHA/
越界类号/非 holdout/重复 source_index 全抛错）。

## 4. 主机 BF16 基线（24/24）

`baselines/clean24_smoke_raw24_bf16_report.json`（backend `icraft-host-bf16`）：

```text
correct_raw24=24  match_frozen_pytorch=24  nan_or_inf=0
wc_separate_ok=true  sc_separate_ok=true  verdict=PASS
```

AM-SSB-WC（source_index 8500，raw 17）与 AM-SSB-SC（source_index 9000，raw 18）
在 24 类模式下**保持独立、分别正确**，未走 24→23 合并（合并只在 23 类路径
`rml23_merged.hpp`，红线未动）。

## 5. 24 类增量变更集（相对 post-smoke fix10prep3 基线）

基线 = fix10prep3 post-smoke full `26bb1241…`（660 文件）+ patch `ba2cb426…`（10 文件）。
24 类树对该基线做**派生 diff**（`scripts/package_fix10class24_bf16_dualsdr.py` 逐字节
walk），变更集分四类：

- **纯新增**（new）：24 类模型、raw24 合同、24 类 runner 头、baseline/clean24_smoke 资产、
  24 类测试、本审计档、本打包脚本。
- **改动**（changed）：`board_gate9_full_chain_rml23.cpp`（24 类 phase 注册 + 包装）、
  `chain_common.hpp`（`fill_result_rml24` + `contract_24()`）、`gate9_phase.hpp`
  （phase 枚举）、`sdr_adapter/ui_report.hpp`（`emit_frame_rml24`）、
  `host_tests/build_host_tests.sh` / `run_tests.sh`（24 类测试接线）。
- **删除**（deleted，仅 2 项，fix10prep3 内部产物，被本轮审计档+打包脚本取代）：
  `docs/M29_RML23_FIX10PREP3_SMOKE_CLOSEOUT_AUDIT.md`、`scripts/package_fix10prep3_smoke_closeout.py`。
- **逐字节一致**（unchanged）：其余全部（含全部红线头、模型、权重、标签、预处理、
  canonical 训练组件、23 类合并合同）。

精确计数（打包器输出）：**106 new + 6 changed = 112 patch 文件 + 2 删除项**。
delete-list 审计断言「只有这 2 项被删除」。full 内容文件数 = 660 − 2 + 106 = **764**。

## 6. 红线核验（全树递归 SHA diff）

打包器 fail-closed 审计（`scripts/package_fix10class24_bf16_dualsdr.py`）全过：

- **11 个红线头**逐字节一致（smoke-closeout full 基线）：`iq_rf_sync_recovery.hpp`、
  `iq_rf_training_frame.hpp`、`iq_digital_loopback.hpp`、
  `iq_pc_tx_board_rx_transfer_fix10.hpp`、`iq_rf_fix9r_baseline.hpp`、
  `iq_clean_baseline.hpp`、`iq_dual_sdr_coarse_cfo_recovery.hpp`、
  `iq_pc_tx_board_rx_23class_fix10.hpp`、`iq_fix10_canonical_frame.hpp`、
  `iq_fix10_canonical_frame_data.hpp`、`rml23_merged.hpp` ✅
- **23 类合并合同**逐字节一致：`contracts/rml23_merged_contract.py` /
  `contracts/rml23_merged_contract.json` ✅
- **protected 目录**（`model_rml23/`、`model_12class/`、`deployment_golden/`、
  `contracts/` 既有文件）逐字节一致 ✅
- **canonical 训练组件**（3 CI16 + `manifest.tsv` + `SHA256SUMS.txt`）逐字节一致 ✅
- **依赖闭包**：每个 patch 内 C++ 文件的每个 quoted include 都能在树内解析 ✅
- **complete-delta**：base − DELETE_LIST + patch == full tree（双向） ✅
- **literal overlay**：把 patch 覆盖到（base − DELETE_LIST）后，与 full 树**逐字节一致** ✅
- **patch 自含**：patch 单独覆盖到 smoke-closeout full 即可解析全部 include ✅
- **旧 fix10 零残留**：`external_rf` / `pluto_external` 无任何文件泄漏 ✅

## 7. 主机回归

WSL（Ubuntu，g++ 15.2.0）执行 `bash host_tests/build_host_tests.sh` →
`bash host_tests/run_tests.sh`：

```text
BUILD_RC=0
run_tests.sh: ALL HOST TESTS PASSED
RUN_RC=0
```

新增 24 类主机测试（全部 PASS，0 fail）：
- `test_rml24_raw_contract`（50 pass，24 类标签序/合同 SHA/部署模式）
- `test_rml24_bf16_baseline`（28 pass，7 列基线解析 + CRLF 容忍 + fail-closed）
- `test_clean_iq_24class_bf16_fix10`（15 pass，24 类 clean IQ NPU 直注全部
  corr=1.000000/nmse=0.000000，WC=17/SC=18 独立）
- `test_pc_tx_board_rx_24class_bf16_fix10`（13 pass，24 类双 SDR 闭环 + provenance）
- `test_rml24_prewarm_plan.py`（5 tests OK，24 样本 prewarm 计划生成 + 确定性两跑）
- `test_rml24_bf16_network_audit.py`（3 tests OK，BF16 网络审计 1+122+1 / 122@zhuget / 0 int8）

既有测试无回归：`test_pc_tx_protocol_fix10.py`（38 OK）、`test_pc_tx_iio_attr_parse.py`
（15 OK）、`test_pc_tx_burst_cache.py`（10 OK）、`test_board_build.sh`（24 passed）、
`test_cli_override.sh`（PASSED）、`test_rml23_build.sh`（7 passed）、
`replay_fix10_failed_rx self-test: PASS`，其余 12 类/23 类全套 PASS。

板端源 `-fsyntax-only`（`host_tests/syntax_check.sh`，对 iCraft 3.39 头，主机侧仅语法、
不链接/不跑板）：`gate7 / gate9 / gate10 / gate9_rml23` 全部 `syntax OK`（`gate9_rml23`
即 `board_gate9_full_chain_rml23.cpp`，含 24 类两个 phase 包装）。**主机语法验证不是板端
构建通过**；真实板端构建/链接/运行见 §9 Gate A。

> 注：`[DFB] FAIL:` 行是 `test_display_integrity`/`test_display_diagnostic` 的**负对照断言**
> （帧缓冲越界/未初始化必须失败），属预期失败注入，对应测试仍 PASS，非回归失败。

## 8. 确定性打包

以 post-smoke fix10prep3 full `26bb1241…`（660 文件）+ patch `ba2cb426…`（10 文件）为
基线，产出 24 类新包（**不覆盖旧包**；fix10prep3 两套旧包原样保留）：

| 包 | 内容文件 | SHA256 |
|---|---|---|
| `dist/sdr_rml24_fix10class24_bf16_dualsdr_boardtest_full.tar.gz` | 764（+根 `SHA256SUMS.txt`） | `25659516b96695e813f8d6be07c601d63c64635dc7e18cf190161a96f4edc676` |
| `dist/sdr_rml24_fix10class24_bf16_dualsdr_patch.tar.gz` | 112 | `7b63871c085654e7d8f2687b83062cac43fe079d0dfa2b84b5fae23ae3b1ac1a` |

sidecar：`…_boardtest_full_SHA256SUMS.txt` / `…_patch_SHA256SUMS.txt`（`HASH *relpath` 约定）。

打包器 fail-closed 审计全过（见 §6）；确定性：每包两次构建字节一致（uid/gid 0、
mtime 0、排序条目、gzip -9 mtime 0）。包外独立解包验证（`sha256sum -c`）全 `OK`；
无 `host_tests/bin` / `__pycache__` / `.build_burst_cache` / `results` / 构建日志入包。

## 9. 板端命令（用户执行；作者不碰板）

### Gate A — 上传 / 解包 / 构建

```bash
# 板端（FMQL30TAI Linux 镜像，libiio 已装 /opt/sdr/libiio-0.26）
mkdir -p /opt/sdr/rml24 && tar -xzf sdr_rml24_fix10class24_bf16_dualsdr_boardtest_full.tar.gz \
    -C /opt/sdr/rml24
cd /opt/sdr/rml24/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24
export LIBIIO_ROOT=/opt/sdr/libiio-0.26
export ICRAFT_CMAKE_DIR=/usr/cmake
bash board_package/build_npu_on_board.sh --gate9-rml23
# 期望：NPU_BUILD_RESULT gate=9R result=PASS binary=.../bin/board_gate9_full_chain_rml23
```

### Gate B — clean IQ 24 类 NPU 直注（无 RF，先证明模型 24 类正确）

```bash
bash scripts/run_gate9_rml23.sh \
  --phase=iq-clean-iq-24class-bf16-fix10 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --frozen-dir=clean24_smoke \
  --baseline=baselines/clean24_smoke_raw24_bf16_baseline.tsv \
  --out-dir=/tmp/rml24_clean_iq
# 期望：24/24 raw24 正确；WC=17 / SC=18 独立；无 nan/inf
```

### Gate C1 — PC 侧（Windows radioconda）prewarm + TX 服务

```bash
# PC（Windows，radioconda python + pylibiio 0.26；先自测）
D:\radioconda\python.exe -I host_tools\pc_tx_sdr_fix10.py --self-test

# 启动 TX 服务（两样本 BPSK=1500 / 4ASK=500 prewarm；target-rms 必须 == 板端 HELLO 的 2048）
D:\radioconda\python.exe -I host_tools\pc_tx_sdr_fix10.py --listen 0.0.0.0:39010 ^
    --tx-uri "<PC_TX_URI>" --frozen-dir "clean24_smoke" ^
    --input-kind radioml-d2-2p56m --center 2400000000 --sample-rate 2560000 ^
    --tx-bw 18000000 --tx-atten -40 --rf-path direct-cable --rf-tx-target-rms 2048 ^
    --prewarm-source-index 1500 --prewarm-source-index 500
```

### Gate C2 — 板端 24 类真实双 SDR（两样本 BPSK+4ASK）

```bash
bash scripts/run_gate9_rml23.sh \
  --phase=iq-pc-tx-board-rx-24class-bf16-fix10 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --frozen-dir=clean24_smoke \
  --baseline=baselines/clean24_smoke_raw24_bf16_baseline.tsv \
  --tx-control=tcp://<PC_IP>:39010 \
  --rx-uri=<BOARD_RX_URI> \
  --input-kind=radioml-d2-2p56m --center=2400000000 --rx-gain=30 \
  --rf-tx-target-rms=2048 --rf-path=direct-cable \
  --diagnostic-classes=BPSK,4ASK --diagnostic-per-class=1 \
  --out-dir=/tmp/rml24_dualsdr
```

判读：`FIX10CLASS24_BF16_*` token 是**测量**，不是回归 PASS；`final_gate_pass` 判定
`functional_pass && m22_ok`。两样本（BPSK/4ASK）prediction_agreement=2/2 + 负对照 PASS +
CFO 有限且在 ±625 Hz 内 + TX/RX restore ok，才可视为两样本烟测通过。

## 10. 状态推进

本轮 Phase C 离线交付完成：模型 24 类正确（主机 24/24）、变更集逐字节审计、红线零触碰、
确定性打包 + 独立解包全过。状态由 Phase C 起始推进为
**`M29-RML24-FIX10CLASS24-BF16-DUALSDR-READY-FOR-BOARD-TEST`**（最高允许，未真实上板）。

**仅在用户真实 24 类板测通过后**才写 `M29-RML24-FIX10CLASS24-BF16-DUALSDR-SMOKE-PASS`。

---

## 附录 A（板端证据归档，待回传）

```text
BOARD_LOG_CONTENT_CONFIRMED_FROM_USER_TRANSCRIPT
BOARD_ARCHIVE_SHA_PENDING_IMPORT
```

收到板端压缩日志/SHA 后补记此处，不伪造。
