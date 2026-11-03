# M29 RML24 FIX10CLASS24 DUALSDR2 — RX 前端带宽扫描审计（fix10class24-rxfrontend1）

- 任务：fix10class24-rxfrontend1（39e5 第二阶段）—— 24 类 BF16 最终接收端 RF 前端带宽/增益稳定性收口
- 工作树：`fix10class24_dualsdr2`（基线 = canonical replay full，见 §7）
- 最高允许状态：**`M29-RML24-FIX10CLASS24-RXFRONTEND-SWEEP-READY-FOR-BOARD-TEST`**
- 禁写：`SMOKE-PASS / RF-PASS / 24CLASS-PASS / RXONLY-PASS / PROJECT_COMPLETE / FINAL_*`；**API 不碰板**

---

## 1. 背景与结论

真实双 SDR 两样本板测（BPSK source_index=1500 / 4ASK source_index=500）在 RF 恢复门反复
边际失败，且固定 RX-gain 扫描（30/35/40 dB）证明**增益提升无法稳定改善归一化残差**（信号与
噪声同幅放大）。本任务（Phase A，API 不碰板）交付**单变量 RX 带宽扫描工具链**：

1. 在 24 类双 SDR 生产 RX 路径补齐 `--rx-bw` 透传 + 写后读回（fail-closed）。
2. 交付板端扫描脚本（TX 固定 `-40 dB`、RX gain 固定 `35 dB`、唯一变量 `--rx-bw`
   `18/10/5/3 MHz`，每档 3 轮）。
3. 交付主机 fail-closed 判读检查器（逐字段解析、重推 §八 每轮 PASS/FAIL、选最宽 3/3 档）。
4. 交付 12 项主机测试（§十一 逐条覆盖）+ 全套回归。
5. 确定性打包（full + patch + SHA256SUMS）。

**不改**：24 类 BF16 模型 JSON/RAW、labels、baseline、0.10 `payload_training_residual` 门限、
sync/CFO/SRO/gain 估计/恢复数学、14 红线头、canonical 3 CI16 组件、PC/板 TCP 状态机、24→23
合并合同。**禁止**修改或绕过 TX `-40 dB` 安全上限。**不**把某个 `--rx-bw` 写进生产默认值
（Phase C 才有，且须板端证据）。

---

## 2. 代码变更集（相对 canonical replay full）

> 基线 = dualsdr2 canonical replay full（`dist/sdr_rml24_fix10class24_bf16_dualsdr2_canonical_full.tar.gz`）。
> 本批次对基线做派生 diff（`scripts/package_fix10class24_bf16_dualsdr2_rxfrontend.py` 逐字节 walk）。

**改动（3）**：

| 文件 | 修改 |
|---|---|
| `board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp` | 24 类双 SDR runner：`--rx-bw` 透传 + RX 带宽/增益写后读回（fail-closed），默认字节等价 |
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_RF_SWEEP_PLAN.md` | 前一批（21:30，未打包）已从「TX -40/-35/-30 三档」改为「RX-gain 30/35/40 扫描」；本批**冻结为基线，不再执行** |
| `host_tests/run_tests.sh` | 增 `python3 ./test_fix10class24_rx_frontend_sweep.py || rc=1` |

**新增（7）**：

| 文件 | 内容 |
|---|---|
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_RF_SWEEP_ERRATA.md` | 累计勘误：废止 TX -35/-30（勘误 1）+ 废止 RX-gain 扫描（勘误 2），指向 RX 带宽方向 |
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_RX_BW_SWEEP_PLAN.md` | 板端执行手册（RX 带宽方向） |
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_RX_FRONTEND_SWEEP_AUDIT.md` | 本文档 |
| `host_tests/test_fix10class24_rx_frontend_sweep.py` | 12 项主机测试（§十一） |
| `scripts/check_fix10class24_rx_frontend_sweep.py` | 主机 fail-closed 判读检查器 |
| `scripts/run_fix10class24_rx_frontend_sweep.sh` | 板端一键扫描脚本（唯一变量 `--rx-bw`） |
| `scripts/package_fix10class24_bf16_dualsdr2_rxfrontend.py` | 本批次打包器 |

精确计数以 §8 打包器输出为准（**7 new + 3 changed = 10 patch 文件 + 0 删除**）。

> 注：`RF_SWEEP_ERRATA.md`（new）与 `RF_SWEEP_PLAN.md`（changed）是 canonical replay full
> （21:16）打包后才落盘的勘误批次（21:30）遗留，当时未单独打包；本批一并纳入并对勘误做
> 「勘误 2」修订。

---

## 3. §一(1) 审查：RX 参数调用链 + 写后读回

### 3.1 RX 采样率（既有，未改）

`iq_pc_tx_board_rx_24class_bf16_fix10.hpp:594-609`：`dev->set_sample_rate(2560000)` 后
`dev->get_rx_sample_rate()` 读回，`sample_rate_ok = llabs(rx_rate - requested) <= 5`，
不一致即 `sample_rate_mismatch` fail-closed（既有行为，本批未改）。

### 3.2 RX 带宽（本批新增）

**调用链**：

- 抽象签名（`sdr_adapter/pluto_device.hpp`，未改）：
  `virtual long long set_rx_bw(long long hz) = 0;`（:213）、`virtual long long get_rx_bw() const = 0;`（:222）。
- 实现 `wr_ll`（`sdr_adapter/pluto_device_libiio.cpp`，未改）写后读回并返回读回值。
- runner CLI：`iq_pc_tx_board_rx_24class_bf16_fix10.hpp:361-362`
  `const long long rx_bw = static_cast<long long>(board::opt_u64(argc, argv, "--rx-bw", 0));`。
- runner RX 配置块：`iq_pc_tx_board_rx_24class_bf16_fix10.hpp:617-624`
  ```cpp
  rep.requested_rx_bw = rx_bw;
  if (rx_bw != 0) {
      rep.rx_bw_readback = dev->set_rx_bw(rx_bw);
      rep.rx_bw_ok = rf_fix::rf_readback_close(rep.rx_bw_readback, rx_bw, 1000LL, 0.05);
  } else {
      rep.rx_bw_readback = dev->get_rx_bw();
  }
  ```
  语义：`--rx-bw==0`（缺省）=「不写，保持设备默认」，**保持本批之前的旧行为**；`--rx-bw!=0`
  = 写后读回并 fail-closed。因此默认路径字节等价。
- 容差函数（`board_package/rf_fix_helpers.hpp:40-48`，新增 include 于 runner :43）：
  `rf_fix::rf_readback_close(got, want, abs_tol, rel_frac)`：`want==0 → got==0`；否则
  `tol = max(abs_tol, llround(|want|*rel_frac))`，`|got-want| <= tol`。对 18 MHz：tol =
  max(1000, 900000)=900000 Hz（5%）；对 3 MHz：tol=max(1000,150000)=150000 Hz（5%）。

### 3.3 RX 增益（本批新增读回，增益档已有）

- 抽象签名（未改）：`virtual double set_rx_gain(double db) = 0;`（:216）、
  `virtual std::string set_rx_gain_mode(const std::string&) = 0;`（:215）。
- runner：`iq_pc_tx_board_rx_24class_bf16_fix10.hpp:625-628`
  ```cpp
  dev->set_rx_gain_mode("manual");
  rep.requested_rx_gain = gain_db;
  rep.rx_gain_readback = dev->set_rx_gain(gain_db);
  rep.rx_gain_ok = std::fabs(rep.rx_gain_readback - gain_db) <= 0.5;
  ```
  `gain_db` 来自 `--rx-gain`（默认 30.0，:360）；扫描脚本显式传 `35`。

### 3.4 读回证据打印 + fail-closed

`iq_pc_tx_board_rx_24class_bf16_fix10.hpp:630-652` 打印
`FIX10CLASS24_BF16_RX_FRONTEND requested_rx_bw=… rx_bw_readback=… requested_rx_gain=…
rx_gain_readback=… rx_bw_ok=… rx_gain_ok=…`，`rx_bw_ok`/`rx_gain_ok` 任一为 0 即打印
`FIX10CLASS24_BF16_ERROR …` 并 `return rep`（fail-closed）。JSON 摘要（:1278-1283）与
`infra_ok`（:1375）与 detail 串（:1426-1429）同步纳入这 6 个字段。

---

## 4. §一(2)-(6) 工具链

### 4.1 板端扫描脚本 `scripts/run_fix10class24_rx_frontend_sweep.sh`

- 常量与 §十一 合同一致：`BANDWIDTHS_HZ=(18000000 10000000 5000000 3000000)`（widest first）、
  `ROUNDS=3`、`RX_GAIN_DB=35`、`DIAGNOSTIC_CLASSES="BPSK,4ASK"`。
- **唯一变量是 `--rx-bw`**：`run_round()` 里只有 `--rx-bw="$hz"` 由 `$hz` 驱动，其余参数逐字
  固定（`--rx-gain="$RX_GAIN_DB"`、`--center=…`、`--rf-tx-target-rms=2048`、`--rf-path=direct-cable`、
  `--diagnostic-classes=…`）。
- PC TX 命令只含 `--tx-atten -40`（硬安全上限）；`prompt_pc()` 每轮打印
  `START_PC_TX_AND_WAIT_FOR_LISTENING` 并阻塞等待回车（`SWEEP_NO_PROMPT=1` 跳过）。
- 每轮产物落 `/tmp/rml24_rxbw_<hz>_run<r>_<ts>/run.log`。

### 4.2 主机判读检查器 `scripts/check_fix10class24_rx_frontend_sweep.py`

- 合同常量与扫描脚本一一对应（带宽列表/轮数/RX gain 35/TX atten -40/残差门限 0.10/
  BPSK=1500/4ASK=500）。
- `parse_log_text()` fail-closed 解析每个关键字段；`judge_round()` **独立**评估 §八 全部条件
  （不短路），`GATE_RESULT=PASS` 是**派生**结论而非信任单一 token。
- `select_candidate()` 按降序 Hz 选 `pass_rounds==ROUNDS` 的最宽档。
- 缺日志/重复样本/错 source_index/非有限/读回不一致 → 全部 fail（`CheckError` 或 FAIL）。

### 4.3 主机测试 `host_tests/test_fix10class24_rx_frontend_sweep.py`

加载**同一份**检查器模块 + 静态检查**同一份**扫描脚本，12 项逐条覆盖 §十一（见 §6）。

---

## 5. 红线核验（打包器 fail-closed，全过）

见 `scripts/package_fix10class24_bf16_dualsdr2_rxfrontend.py`，与 canonical replay 批同套：

- **14 红线头**逐字节一致（同 canonical replay 批清单：`iq_rf_sync_recovery.hpp` /
  `iq_rf_training_frame.hpp` / `iq_digital_loopback.hpp` / `iq_pc_tx_board_rx_transfer_fix10.hpp` /
  `iq_rf_fix9r_baseline.hpp` / `iq_clean_baseline.hpp` / `iq_dual_sdr_coarse_cfo_recovery.hpp` /
  `iq_pc_tx_board_rx_23class_fix10.hpp` / `iq_fix10_canonical_frame.hpp` /
  `iq_fix10_canonical_frame_data.hpp` / `rml23_merged.hpp` / `rml24_raw.hpp` /
  `rml24_bf16_baseline.hpp` / `iq_clean_iq_24class_bf16_fix10.hpp`）。
- **红线合同**（merged + raw24）字节一致。
- **protected 目录**（model/labels/baseline/clean24_smoke/contracts）字节一致。
- **canonical 3 CI16 + manifest** 字节一致（aarch64 权威，未动）。
- **依赖闭包** + **complete-delta** + **patch-over-base overlay == full** 全过。
- 允许改动的 runner `iq_pc_tx_board_rx_24class_bf16_fix10.hpp` **不在红线清单内**（这正是本任务
  唯一可改的生产文件）。

---

## 6. 主机测试结果

### 6.1 新 12 项（§十一 逐条）

`python3 test_fix10class24_rx_frontend_sweep.py` → **12/12 PASS（0 fail）**：

| # | §十一 条款 | 测试 | 结果 |
|---|---|---|---|
| 1 | 扫描严格 18/10/5/3 | `test_01_sweep_strictly_18_10_5_3` | PASS |
| 2 | TX 恒 -40（-35/-30 拒绝） | `test_02_tx_atten_always_minus40` | PASS |
| 3 | RX gain 恒 35 | `test_03_rx_gain_always_35` | PASS |
| 4 | 仅 rx-bw 逐字可变 | `test_04_all_params_verbatim_except_rx_bw` | PASS |
| 5 | 仅 3/3 为候选 | `test_05_three_of_three_required` | PASS |
| 6 | 2 PASS+1 FAIL 不合格 | `test_06_two_pass_one_fail_not_qualified` | PASS |
| 7 | residual 0.10 边界 | `test_07_residual_boundary` | PASS |
| 8 | 削顶/NaN/读回不一致即失败 | `test_08_clipping_nan_readback_mismatch_fail` | PASS |
| 9 | 缺日志/重复样本/错 index 失败 | `test_09_missing_log_duplicate_sample_wrong_index` | PASS |
| 10 | 选最宽不选最窄 | `test_10_choose_widest_passing` | PASS |
| 11 | 无候选 → NO_STABLE | `test_11_no_candidate_is_no_stable` | PASS |
| 12 | 新测试已接入全套 | `test_12_new_test_wired_into_full_suite` | PASS |

### 6.2 编译验证

`bash host_tests/syntax_check.sh` → `gate9_rml23: syntax OK`（`-fsyntax-only -Wall -Wextra
-Werror`，经 `board_gate9_full_chain_rml23.cpp` 传递编译 runner 头，含新增 `--rx-bw` 代码）。

### 6.3 全套回归

`bash host_tests/run_tests.sh` → **`ALL HOST TESTS PASSED`**（exit 0）。既有全套
（12 类 / 23 类 / 24 类 / fix9/fix10 全系列 + 3 个 build 测试脚本）无回归。

---

## 7. §十五 最终报告（9 项）

1. **RX 带宽参数调用链 + 读回证据**：见 §3.2（`pluto_device.hpp` 抽象 → `pluto_device_libiio.cpp`
   `wr_ll` 写后读回 → runner `--rx-bw` 透传 → `rf_readback_close` 容差 fail-closed →
   `FIX10CLASS24_BF16_RX_FRONTEND` 打印）。
2. **生产代码是否改动（确切文件 + 理由）**：仅 `board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp`
   （唯一可改的双 SDR runner），理由=补齐 `--rx-bw` 透传与写后读回；默认 `--rx-bw==0` 字节等价，
   不改恢复数学/门限。14 红线头零触碰。
3. **主机测试结果**：新 12/12 PASS + `syntax_check.sh` 全 OK + 全套 `ALL HOST TESTS PASSED`（§6）。
4. **红线一致性**：14 红线头 + 合同 + protected + canonical 全字节一致（§5）。
5. **full/patch SHA**：见交付消息 + 项目 memory（tar SHA 不自引用入包；sidecar
   `*_SHA256SUMS.txt` 随包提供逐文件哈希）。
6. **PC 固定 -40 dB 完整命令**：见 `M29_RML24_FIX10CLASS24_DUALSDR2_RX_BW_SWEEP_PLAN.md` §3。
7. **板端 18/10/5/3 MHz 逐档命令**：见同文档 §4.0（一键）与 §4.1–§4.4（手工逐档）。
8. **日志判读命令**：见同文档 §5（`check_fix10class24_rx_frontend_sweep.py <sweep_root>`）。
9. **当前状态 + 停点**：`M29-RML24-FIX10CLASS24-RXFRONTEND-SWEEP-READY-FOR-BOARD-TEST`，
   **停下等待用户板端扫描**；API 不碰板、不写 SMOKE-PASS/RF-PASS/24CLASS-PASS/RXONLY-PASS。

---

## 8. 打包（确定性）

以 canonical replay full 为基线，产出 rxfrontend 新包（不覆盖旧包）：

| 包 | 内容文件 | 说明 |
|---|---|---|
| `dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxfrontend_full.tar.gz` | 785（+根 SHA256SUMS.txt） | 单顶层目录 |
| `dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxfrontend_patch.tar.gz` | 10 | 平铺，覆盖 canonical full 即得 rxfrontend full |

sidecar：`…_rxfrontend_full_SHA256SUMS.txt` / `…_rxfrontend_patch_SHA256SUMS.txt`
（`HASH *relpath`）。确定性：每包两跑字节一致；独立解包 + `sha256sum -c` 全 `OK`。
**打包中不含可复制执行的危险/无效命令**：扫描脚本只含 `--tx-atten -40`，无 `-35/-30`；
旧 RF_SWEEP_PLAN 中无 `-35/-30` 可执行命令（原方案从未落入可执行脚本，只落文档并已勘误废止）。
无 `host_tests/bin` / `__pycache__` / `.build_burst_cache` / `results` / 构建日志入包。

---

## 9. 状态与停点

本轮 Phase A 离线交付完成：RX 参数审查 + 单变量带宽扫描工具 + 12 项主机测试全过 + 全套无回归
+ 红线零触碰 + 确定性打包全过。状态推进为
**`M29-RML24-FIX10CLASS24-RXFRONTEND-SWEEP-READY-FOR-BOARD-TEST`**（最高允许）。

**后续（用户执行，API 不碰板）**：按
`M29_RML24_FIX10CLASS24_DUALSDR2_RX_BW_SWEEP_PLAN.md` 跑四档带宽 × 3 轮 → 检查器选出最宽 3/3 档
→ 仅当选出并通过后才进入 Phase C（把该 `--rx-bw` 接入生产默认 + 两样本复测确认）。若四档均无
3/3 → `NO_STABLE_RX_BANDWIDTH`，停止并进入物理链路审计，**不**改算法/门限/模型。
