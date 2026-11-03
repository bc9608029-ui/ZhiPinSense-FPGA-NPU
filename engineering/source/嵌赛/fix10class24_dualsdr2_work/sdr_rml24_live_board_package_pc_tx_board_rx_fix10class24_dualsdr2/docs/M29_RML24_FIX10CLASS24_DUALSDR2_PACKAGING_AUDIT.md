# M29 RML24 — fix10class24-dualsdr2 恢复诊断交付审计（Batch 1）

> 状态：**`M29-RML24-FIX10CLASS24-DUALSDR-RECOVERY-DIAGNOSTIC-READY-FOR-BOARD-CAPTURE`**（最高允许）
> 本档是 **Batch 1 离线诊断交付** 记录；作者不碰板，真实板端采集由用户执行。
> 禁止提前写：`SMOKE-PASS / RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE / FINAL_*`。
> 真实 BPSK 失败样本采集 + Phase D 根因定位完成前，本档状态**只能**停在
> `RECOVERY-DIAGNOSTIC-READY-FOR-BOARD-CAPTURE`。

---

## 1. 任务背景与结论

dualsdr1 的 24 类 BF16 双 SDR 交付（full `25659516…`，状态 `READY-FOR-BOARD-TEST`）
在真实两样本板测中**于 RF 恢复门（NPU 之前）两次失败**：

```text
BPSK payload_training_residual = 0.101856–0.112227  (> 0.10)  ->  PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH
4ASK recovered fine (~0.089–0.097)
```

而 24 类 clean IQ 数字直注全过、恢复路径在 23 类（已过板）与 24 类（失败）之间
**逐字节一致**（Phase A diff 审计结论，见 §5）。失败**不是** 23→24 同步缺口，而是
真实双 SDR 链路上 BPSK 样本的恢复残差恰好越过 `kPayloadTrainingResidualMax=0.10` 门限。

**本轮（Batch 1）只做诊断仪表化，不做任何修复**：给 24 类双 SDR runner 加
`--dump-failed-rx` + `--dump-recovery-diagnostics`（默认字节等价），并交付一个
**离线 C++ 重放器**，让用户把失败样本的 7 文件转储带回主机，逐字段复现板端恢复、
画出整数/分数定时候选曲线，供 Phase D 根因定位（D1/D2/D3）。**没有真实采集证据前，
不写任何根因、不做任何修复、不打包修复。**

## 2. 诊断交付物（7 文件转储 + 离线重放）

失败样本被 `--dump-failed-rx` 命中时，写入 `<out-dir>/failed_rx/<source_index>/`：

| 文件 | 内容 |
|---|---|
| `raw_rx_ci16le.bin` | RX 原始 int16 交织 IQ（小端，板端恢复的输入） |
| `expected_scaled_payload_ci16le.bin` | 期望缩放 payload（TX 侧参考） |
| `expected_full_burst_ci16le.bin` | 期望 full burst（59904 复） |
| `coarse_corrected_rx_cf64le.bin` | coarse CFO 去旋转后的 RX（复 double） |
| `recovered_payload_f32le.bin` | 恢复 payload（复 float，53760 复） |
| `recovery_diagnostics.json` | CoarseCfoRecovery + PerFileRecovery + EstimateConfig 全字段 |
| `SHA256SUMS.txt` | 上述二进制文件的 `HASH *name` 清单 |

离线重放器 `host_tools/replay_fix10class24_failed_rx.{hpp,cpp,sh}`（iCraft/libiio/NPU 全免，
主机/板端同一份 C++，**不复刻恢复数学**，直接调用未改动的生产函数
`iqdual23fix10::recover_payload_with_coarse_cfo`）：
- 默认重放：重跑恢复并打印与板端日志一致的一行 + 与 `recovery_diagnostics.json` 逐字段
  交叉核对（SHA / failure / timing / coarse+fine CFO / corr / residual）。
- `--curves`：整数定时 ±8 样本 + 分数定时全 `[-0.5,+0.5]` 网格，标出 production /
  min_residual / max_corr 三个候选。
- `--self-test`：干净单周期恢复必须 valid 且 corr>0.99 且 residual<1e-3。

## 3. 变更集（相对 dualsdr1 full `25659516…`）

基线 = dualsdr1 24 类 BF16 双 SDR full `25659516…`（764 文件）。dualsdr2 树对该基线做
**派生 diff**（`scripts/package_fix10class24_bf16_dualsdr2.py` 逐字节 walk）：

- **纯新增**（9）：`board_package/iq_fix10class24_failed_rx_dump.hpp`、
  `host_tools/replay_fix10class24_failed_rx.{hpp,cpp,sh}`、
  `host_tests/test_fix10class24_failed_rx_dump.cpp`、`host_tests/test_fix10class24_replay.cpp`、
  `docs/M29_RML24_FIX10CLASS24_DUALSDR2_PHASE_A_DIFF_AUDIT.md`、
  `scripts/package_fix10class24_bf16_dualsdr2.py`、本审计档。
- **改动**（4）：`board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp`（只加
  `--dump-failed-rx` / `--dump-recovery-diagnostics` 接线，默认字节等价）、
  `host_tests/build_host_tests.sh`、`host_tests/run_tests.sh`（测试接线）、
  `docs/M29_RML24_FIX10CLASS24_BF16_DUALSDR_AUDIT.md`（dualsdr1 审计档 §8 SHA 回填——
  dualsdr1 full tar 打包于其 §8 表填写前，dualsdr2 树继承的是磁盘上最终版，故该档被
  派生 diff 判为「改动」，把 dualsdr1 审计档补成最终 §8）。
- **删除**（0）：dualsdr2 对 dualsdr1 纯增量，无删除。
- **逐字节一致**（其余全部，含全部红线头 / 模型 / 权重 / 标签 / 预处理 / canonical
  训练组件 / 23 类合并合同 / raw24 合同 / 24 类 clean IQ 资产 / 冻结基线）。

精确计数见 §8 打包器输出（**9 new + 4 changed = 13 patch 文件 + 0 删除**）。

## 4. 唯一允许改动的 runner（红线边界）

24 类有两条 runner，本任务**只许改双 SDR 那条**（正是失败路径）：

- ✅ **可改**：`board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp`
  （`iq-pc-tx-board-rx-24class-bf16-fix10` phase；本轮只加诊断转储，不改恢复数学）。
- ❌ **禁改（红线，逐字节一致）**：`board_package/iq_clean_iq_24class_bf16_fix10.hpp`
  （clean IQ 直注，已过）——列入 `RED_LINE_HEADERS`。

## 5. Phase A diff 审计结论（已单独成档）

`docs/M29_RML24_FIX10CLASS24_DUALSDR2_PHASE_A_DIFF_AUDIT.md`：
23 类（过板）与 24 类（失败）之间，恢复路径逐字节一致；唯一差异是 23 类有
`--dump-failed-rx` + 5 个 fractional 字段而 24 类没有。故失败**不是**同步缺口；本轮
正是把这份 23 类已具备的诊断可观测性补齐到 24 类双 SDR runner。

## 6. 红线核验（全树递归 SHA diff）

打包器 fail-closed 审计（`scripts/package_fix10class24_bf16_dualsdr2.py`）全过：

- **14 个红线头**逐字节一致（dualsdr1 full 基线）：`iq_rf_sync_recovery.hpp`、
  `iq_rf_training_frame.hpp`、`iq_digital_loopback.hpp`、
  `iq_pc_tx_board_rx_transfer_fix10.hpp`、`iq_rf_fix9r_baseline.hpp`、
  `iq_clean_baseline.hpp`、`iq_dual_sdr_coarse_cfo_recovery.hpp`、
  `iq_pc_tx_board_rx_23class_fix10.hpp`、`iq_fix10_canonical_frame.hpp`、
  `iq_fix10_canonical_frame_data.hpp`、`rml23_merged.hpp`、`rml24_raw.hpp`、
  `rml24_bf16_baseline.hpp`、`iq_clean_iq_24class_bf16_fix10.hpp` ✅
- **合同**逐字节一致：`rml23_merged_contract.py/.json` + `rml24_raw_contract.py` ✅
- **protected 目录**（`model_rml23/`、`model_12class/`、`deployment_golden/`、
  `model_rml24_bf16/`、`baselines/`、`clean24_smoke/`、`contracts/` 既有文件）逐字节一致 ✅
- **canonical 训练组件**（3 CI16 + `manifest.tsv` + `SHA256SUMS.txt`）逐字节一致 ✅
- **依赖闭包**：每个 patch 内 C++ 文件的每个 quoted include 都能在树内解析 ✅
- **complete-delta**：base + patch == full tree（双向，无删除） ✅
- **literal overlay**：把 patch 覆盖到 dualsdr1 full 后，与 dualsdr2 full 树**逐字节一致** ✅
- **patch 自含**：patch 单独覆盖到 dualsdr1 full 即可解析全部 include ✅
- **旧 fix10 零残留**：`external_rf` / `pluto_external` 无任何文件泄漏 ✅

## 7. 主机回归

WSL（Ubuntu，g++ 15.2.0）执行 `bash host_tests/build_host_tests.sh` →
`bash host_tests/run_tests.sh`：

```text
BUILD_RC=0
run_tests.sh: ALL HOST TESTS PASSED
RUN_RC=0
```

新增 2 个诊断测试（全部 PASS，0 fail）：
- `test_fix10class24_failed_rx_dump`（36 pass：三个小端 writer roundtrip 含
  -32768/32767、cf64 双精度、f32 单精度；7 文件转储；raw_rx roundtrip；
  SHA256SUMS 5 行格式 + 首行哈希；JSON 逐字段 spot-check 含 `max_residual:0.1`）
- `test_fix10class24_replay`（10 pass：`self_test()==0`；dump→replay roundtrip 全部
  crosscheck 布尔 PASS + timing/valid 与原恢复一致；timing + fractional 曲线无抛异常）

新增重放器 self-test：`replay_fix10class24_failed_rx --self-test: PASS`。

既有全套（12 类 / 23 类 / 24 类 / fix9/fix10 全系列）无回归；`[DFB] FAIL:` 行是
display 测试的负对照断言，非回归失败。

## 8. 确定性打包

以 dualsdr1 full `25659516…`（764 文件）为基线，产出 dualsdr2 诊断新包
（**不覆盖 dualsdr1 旧包**；两套旧包原样保留）：

| 包 | 内容文件 | SHA256 |
|---|---|---|
| `dist/sdr_rml24_fix10class24_bf16_dualsdr2_diag_full.tar.gz` | 773（+根 `SHA256SUMS.txt`） | `097c6942a03873c9c05ed21ccab9713f76e5142d2ba088abb0c196dede80e557` |
| `dist/sdr_rml24_fix10class24_bf16_dualsdr2_diag_patch.tar.gz` | 13 | `57350773b8cd280522b3fe3fcd53f0f6b1e7e28f424308b6b4bf43b3475a57d6` |

sidecar：`…_diag_full_SHA256SUMS.txt` / `…_diag_patch_SHA256SUMS.txt`（`HASH *relpath`）。

打包器 fail-closed 审计全过（见 §6）；确定性：每包两次构建字节一致（uid/gid 0、
mtime 0、排序条目、gzip -9 mtime 0）。包外独立解包验证（`sha256sum -c`）全 `OK`；
无 `host_tests/bin` / `__pycache__` / `.build_burst_cache` / `results` / 构建日志入包。

> 注：§8 的 SHA 为打包后回填；本档自身在 patch 内，故重跑打包器会因本档内容变化而
> 产生新 SHA（自引用）。本档以首次确定性打包输出为准，不再重跑。

## 9. 板端命令（用户执行；作者不碰板）

### Gate A — 上传 / 解包 / 构建

```bash
# 板端（FMQL30TAI Linux 镜像，libiio 已装 /opt/sdr/libiio-0.26）
mkdir -p /opt/sdr/rml24 && tar -xzf sdr_rml24_fix10class24_bf16_dualsdr2_diag_full.tar.gz \
    -C /opt/sdr/rml24
cd /opt/sdr/rml24/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2
export LIBIIO_ROOT=/opt/sdr/libiio-0.26
export ICRAFT_CMAKE_DIR=/usr/cmake
bash board_package/build_npu_on_board.sh --gate9-rml23
# 期望：NPU_BUILD_RESULT gate=9R result=PASS binary=.../bin/board_gate9_full_chain_rml23
```

### Gate B — clean IQ 24 类 NPU 直注（可选复测，证明模型 24 类仍正确）

```bash
bash scripts/run_gate9_rml23.sh \
  --phase=iq-clean-iq-24class-bf16-fix10 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --frozen-dir=clean24_smoke \
  --baseline=baselines/clean24_smoke_raw24_bf16_baseline.tsv \
  --out-dir=/tmp/rml24_clean_iq
# 期望：24/24 raw24 正确；WC=17 / SC=18 独立
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

### Gate C2 — 板端 24 类真实双 SDR（两样本 BPSK+4ASK，**带失败转储**）

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
  --dump-failed-rx --dump-recovery-diagnostics \
  --out-dir=/tmp/rml24_dualsdr_diag
```

关键差异（相对 dualsdr1 §9）：新增 `--dump-failed-rx --dump-recovery-diagnostics`
（`--out-dir` 必填）。失败样本转储落 `/tmp/rml24_dualsdr_diag/failed_rx/1500/`
（BPSK source_index=1500），4ASK 若也失败则另有 `/failed_rx/500/`。

判读：`FIX10CLASS24_BF16_*` token 是**测量**，不是回归 PASS。BPSK 仍会打
`PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`（这正是要转储的失败），同时打印
`FIX10CLASS24_BF16_CFO_FRACTIONAL`（`--dump-recovery-diagnostics` 打开的 5 个
fractional 字段）与 `FIX10CLASS24_BF16_FAILED_RX_DUMP`（转储成功标记）。

### Gate D — 主机离线重放（作者可执行，等用户回传转储）

```bash
# 主机（WSL），回传的失败样本目录 <dump>/failed_rx/1500
bash host_tools/replay_fix10class24_failed_rx.sh --dump-dir <dump>/failed_rx/1500 --curves --fractional-den 64
# 期望：FIX10CLASS24_REPLAY ... crosscheck=PASS（重放与板端日志逐字段一致）
#      + TIMING / FRAC 曲线，标出 production vs min_residual vs max_corr 候选
```

## 10. 状态推进与后续

本轮 Batch 1 离线诊断交付完成：Phase A（diff 审计）+ Phase B（失败转储）+ Phase C
（离线重放器）+ Phase E（主机测试全过）+ 确定性打包全过，红线零触碰。状态推进为
**`M29-RML24-FIX10CLASS24-DUALSDR-RECOVERY-DIAGNOSTIC-READY-FOR-BOARD-CAPTURE`**
（最高允许，未真实采集）。

**后续（等用户回传 BPSK 失败样本转储后才可进行）：**
- Phase D：从真实转储定位根因 D1/D2/D3（**没有转储不写根因**）。
- 之后才是最小修复（Batch 2，`RECOVERY-FIX-READY-FOR-BOARD-RETEST`），再两样本稳定通过
  才写 `2SAMPLE-STABLE-PASS`，全量 24 类 BF16 双 SDR 烟测通过才写
  `BF16-DUALSDR-SMOKE-PASS`。**任何一步都不得在真实证据到位前提前推进。**

---

## 附录 A（板端证据归档，待回传）

```text
BOARD_LOG_CONTENT_CONFIRMED_FROM_USER_TRANSCRIPT
BOARD_DUMP_ARCHIVE_SHA_PENDING_IMPORT
```

收到板端压缩日志 + `failed_rx/1500/` 转储后补记此处，不伪造。
