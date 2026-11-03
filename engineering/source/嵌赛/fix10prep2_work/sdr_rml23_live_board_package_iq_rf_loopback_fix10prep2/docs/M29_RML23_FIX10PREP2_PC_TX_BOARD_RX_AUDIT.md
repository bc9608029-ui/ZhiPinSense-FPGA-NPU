# M29 RML23 — fix10prep2 PC-TX / Board-RX 真实双 SDR 拓扑 审计

> 状态：**`M29-RML23-FIX10-PC-TX-BOARD-RX-PREP-READY-FOR-BOARD-TEST`**（最高允许）
> 本任务是**离线交付**，板端烟测由用户执行；作者不碰板。
> 禁止写：`RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE / FINAL_* /
> ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`。

---

## 1. 为什么做

现有 fix10-prep 的「板端单进程同时开两台 SDR」是**错误拓扑**。真实硬件是两台
ADALM-Pluto（AD9364, Rev.C, 1T1R）：

- **Windows PC 控 TX SDR**：周期发冻结 CI16 帧，过 50Ω 同轴；
- **板端 Linux 控 RX SDR**：捕获 → CFO/同步/增益恢复 → NPU24 → 24→23 合并。

两端**只通过 TCP 交换控制消息 + 样本身份 + SHA**，**不经网络传实时 IQ**。
纯数字 IQ 路径、单 SDR 已通过的恢复核心/模型链**完全不变**。

命名：本任务 = `fix10prep2`（`fix10prep1` 已被 clean-IQ 张量诊断占用，避免两补丁同名）。

---

## 2. 拓扑

```
 Windows PC (radioconda Python)                     板端 Linux (FMQL30TAI)
 ┌────────────────────────────┐                    ┌────────────────────────────┐
 │ pc_tx_sdr_fix10.py         │                    │ run_gate9_rml23.sh         │
 │  · TX SDR open/config      │   TCP control       │  --phase=iq-pc-tx-board-  │
 │  · burst build (WSL C++)   │◄───────────────────►│   rx-23class-fix10        │
 │  · cyclic TX (仅 START)     │  + identity + SHA  │  · RX SDR open (NO TX API)│
 │  · 独立 watchdog ≤2s        │   (无 IQ 数据)       │  · 复用 h5 恢复核心        │
 └────────────┬───────────────┘                    │  · NPU24 → 24→23 merge    │
              │ 50Ω 同轴                              └────────────┬───────────────┘
              └────────────── TX ────────────────────────────► RX ┘
```

---

## 3. 基线

- 权威基线 = **累计到 h5**（已通过真实板端 46 样本回归）：
  `F:\嵌赛\fix9r2g1_work\sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g1`
  （目录名仍叫 fix9r2g1，内容已累计到 h5）。
- **不是** fix10-prep 的 h2 基线（h2 的 `iq_rf_training_frame.hpp` 是 64、
  `iq_rf_sync_recovery.hpp`/`iq_digital_loopback.hpp` 是 h2 旧版，会回退 h3~h5 修复）。
- 四条红线头与 h5 **字节一致**（打包器 fail-closed 校验）：
  - `iq_rf_sync_recovery.hpp`  `a8b3b6039d87ee5c1b08a79f8e5d8ae8cbf16aafa1844929efd7f84266d07a98`
  - `iq_rf_training_frame.hpp` `d702cb58…`
  - `iq_digital_loopback.hpp` `b4f2a96c…`
  - `iq_rf_fix9r_baseline.hpp` `8051f78d…`

帧布局（h5，本任务不改变）：`kPayloadComplex=53760, kTotalBurstComplex=59904,
kPayloadStart=3072, kPayloadTrainingOffset=2048, kPayloadTrainingSamplesPerSymbol=32,
kFs=2560000, kTrainAmp=2048`。ZC 前导 1024 → settling-zero 1024 → payload 训练 1024
→ payload 53760 → guard 2048 → tail 1024。

---

## 4. 变更文件清单（patch = 31 文件 = 18 fix10prep2 + 13 fix10-prep 基线增量）

### 新增（13）
| 文件 | 作用 |
|---|---|
| `host_tools/pc_tx_sdr_fix10.py` | PC TX 服务主程序（DLL 猴子补丁 + `import iio`；TX 打开/配置/cyclic burst/停止/状态恢复；TCP 服务端；独立 watchdog） |
| `host_tools/fix10_tx_protocol.py` | PC 侧 TCP 协议（版本化 JSON + uint32 BE 长度前缀；HELLO/ACK；逐样本状态机） |
| `host_tools/build_burst_cli.cpp` | WSL g++ burst 生成器，`#include` h5 `iq_rf_training_frame.hpp` |
| `host_tools/build_burst_cli.sh` | WSL 编译脚本（compile-once + SHA 缓存） |
| `sdr_adapter/tcp_control_client.hpp` | 树内首个 AF_INET socket 客户端（uint32 BE 长度前缀 JSON 收发） |
| `board_package/iq_pc_tx_board_rx_transfer_fix10.hpp` | 板端逐样本状态机 + provenance 校验 + JSON 编解码 |
| `board_package/iq_pc_tx_board_rx_23class_fix10.hpp` | RX-only 23 类 runner（无任何 TX API） |
| `host_tests/test_pc_tx_protocol_fix10.cpp` | C++ 协议测试 |
| `host_tests/test_pc_tx_protocol_fix10.py` | Python unittest（stdlib，`spec_from_file_location` 加载协议模块） |
| `host_tests/test_pc_tx_board_rx_fix10.cpp` | 板端 RX-only runner 测试（含「不含 TX API」编译断言） |
| `host_tests/test_pc_tx_provenance_fix10.cpp` | provenance 逐字节一致 + READY 11 字段逐项比对测试 |
| `scripts/package_pc_tx_board_rx_fix10prep2.py` | 打包器 |
| `docs/M29_RML23_FIX10PREP2_PC_TX_BOARD_RX_AUDIT.md` | 本文档 |

### 修改（5，增量接线到 h5 版，不整文件覆盖）
| 文件 | 改动 |
|---|---|
| `board_package/gate9_phase.hpp` | `valid_phase()` 加 `iq-pc-tx-board-rx-23class-fix10` |
| `board_package/board_gate9_full_chain_rml23.cpp` | `run_iq_pc_tx_board_rx_23class_fix10(...)` + 分发；`--tx-control/--max-files/--out-dir` 解析；旧 phase 板端拒绝 |
| `host_tests/build_host_tests.sh` | 接 3 个新 C++ 测试 |
| `host_tests/run_tests.sh` | 接 3 个新 C++ 测试 + Python unittest |
| `scripts/run_gate9_rml23.sh` | 仅补 `--phase=iq-pc-tx-board-rx-23class-fix10` 文档注释 |

### 基线增量（fix10-prep 13 新增文件，入 patch——issue #2 修复）

fix10prep2 的 **full 包 = h5 + fix10-prep 已验证 17 文件增量 + 上表 18 文件**。fix10-prep
增量从 h2 树逐字提取、叠加到 h5 后产生 **3 处 h2→h5 API 漂移**（计划 §5 预估仅 1 处，
实际 3 处，均已修复并通过全量回归）。

其中 **13 个新增文件**必须随 patch 一起交付：fix10prep2 的 C++ 文件 `#include` 它们、
接线 host 测试脚本驱动它们，否则 patch 无法独立叠加到声明的 h5 基线（issue #2，原打包器
只对 full 跑 dependency closure 而漏掉 patch 独立性）。这 13 个文件：

| 文件 | 作用 |
|---|---|
| `sdr_adapter/pluto_dual_air_link.hpp` | fix10-prep 双 SDR 空口链路抽象 |
| `board_package/iq_dual_sdr_transfer_fix10.hpp` | fix10-prep 双 SDR 传输 |
| `board_package/iq_dual_sdr_coarse_cfo_recovery.hpp` | coarse CFO 恢复（本任务 RX-only runner 复用） |
| `board_package/iq_dual_sdr_23class_fix10.hpp` | fix10-prep 双 SDR 23 类 runner |
| `board_package/iq_clean_baseline.hpp` | clean-IQ 基线 |
| `board_package/iq_clean_iq_23class_fix10.hpp` | clean-IQ 23 类 runner |
| `scripts/gen_generated_clean_23.py` | clean CI16 生成器 |
| `scripts/predict_clean_baseline.py` | clean 冻结预测 |
| `host_tests/test_iq_dual_sdr_fix10.cpp` | 双 SDR 测试 |
| `host_tests/test_iq_dual_sdr_23class_fix10.cpp` | 双 SDR 23 类测试 |
| `host_tests/test_clean_iq_23class_fix10.cpp` | clean-IQ 测试 |
| `scripts/package_dual_sdr_clean_iq_fix10prep.py` | fix10-prep 打包器（历史存档） |
| `docs/M29_RML23_FIX10_DUAL_SDR_CLEAN_IQ_PREP_AUDIT.md` | fix10-prep 审计（历史存档） |

4 个接线文件（`gate9_phase.hpp`/`board_gate9_full_chain_rml23.cpp`/`build_host_tests.sh`/
`run_tests.sh`）已把 fix10-prep 增量合并进 fix10prep2 的修改版（见上表「修改」），随
fix10prep2 修改文件入 patch。3 处 h2→h5 漂移修复落在以下文件上，均在 patch 中：

| 文件 | 漂移 | 修复 |
|---|---|---|
| `board_package/iq_dual_sdr_23class_fix10.hpp` | 基线 sha 列存原始 RadioML SHA，旧码比 `fz.sha256`（量化 ci16 SHA）恒不匹配 | 改比 `fz.original_sha256`（计划预估的那 1 处） |
| `host_tests/test_iq_dual_sdr_fix10.cpp` | h5 32-sps 训练块比 h2 64-sps 更 SRO 敏感：20 ppm 的 `payload_training_residual=0.0523` 越过 estimator 默认 `max_residual=0.05` | `recover()` 改用 runner 的 `EstimateConfig`（`max_residual=kPayloadTrainingResidualMax=0.10`、`min_corr=0.9`、`max_cfo_hz=30`、`max_sro_ppm=30`、`search_limit=0`） |
| `scripts/gen_generated_clean_23.py` | h5 `load_d2_sidecar` 现要求 `original_sha256` 为 64-hex，clean 旧生成器写空串 | clean 无 HDF5 原档，`original_sha256` 填 ci16 自身 `q_sha`（诚实：clean CI16 即其源） |

---

## 5. TCP 协议（版本化 JSON + uint32 大端长度前缀）

- **长度前缀 = uint32 网络字节序（大端）**；`max_message_bytes = 1 MiB`，超限断连 fail-closed。
- 每消息含 `protocol_version=1 / session_id / run_nonce / manifest_sha256`；
  **session_id + run_nonce 每次运行唯一**，重复/乱序一律拒绝。
- 超时：`connect_timeout`、`message_timeout`、`watchdog_timeout ≤ 2 s`（显式配置，host 测试断言）。
- **未知字段 fail-closed**（含未知字段的消息拒绝）。
- 样本身份 = **`source_index + file_name + payload_sha_pre`**（禁序号/模糊文件名/标签匹配）。

### 消息
- **HELLO**（板→PC）：`{type, protocol=1, session_id, run_nonce, input_kind,
  manifest_sha256, sample_rate=2560000, center_hz, target_rms=2048}`
- **HELLO_ACK**（PC→板）：`{type, protocol=1, session_id, run_nonce, tx_serial, tx_uri,
  tx_atten_db, configuration_verified=true}`

### 逐样本状态机（严格单向，含 START）
```
STOP → STOPPED → 板端负对照 → PREPARE(样本身份)
  → PREPARED（PC 仅构建+校验 burst，绝不创建 cyclic TX）
  → START（板端明确授权发射）
  → READY（PC 已启动 cyclic TX 且全部配置读回通过）
  → 板端校验 READY provenance → 捕获/恢复/模型
  → CAPTURED → PC 停 TX → STOPPED → 下一样本
```

- **硬要求**：PREPARE/PREPARED 绝不创建 cyclic TX；只有合法 START 才发射；READY 只在
  TX 已运行且全部配置读回通过后发送；重复 START、未 PREPARE 就 START、CAPTURED 前
  STOPPED 一律拒绝；START→READY 超时也必须停 TX。
- READY 携带 **11 字段**：`source_index, file_name, payload_sha_pre, payload_sha_post,
  burst_sha, tx_scale, sample_rate_readback, tx_lo_readback, tx_bw_readback,
  tx_atten_readback, tx_running`。板端逐项比对 `payload_sha_pre/payload_sha_post/
  burst_sha/tx_scale`，任一不一致即停。
- **PC 独立 watchdog（≤2s）**：断线/协议错误/进程异常后独立停 TX，不依赖板端再发 STOP。

---

## 6. CFO 捕获范围（用户新增硬要求）

板端 runner 打印 + host 测试显式覆盖（每样本 + 聚合各一次）：

| 字段 | 口径 |
|---|---|
| `coarse_cfo_search_min_hz` / `coarse_cfo_search_max_hz` | coarse CFO 搜索范围 |
| `coarse_cfo_unambiguous_range_hz` | **约 ±625 Hz** = `kFs / (2*2048)` @ 2.56 MHz |
| `fine_cfo_range_hz` | 约 ±21.7 Hz |
| `total_cfo_hz` | coarse + fine |

- host 测试注入 CFO **在/越界各一例**，断言 search 范围、无歧义范围、越界 fail-closed。
- **双 SDR 独立晶振 → CFO 可能远超单 SDR**：不假设 CFO=0、不套单 SDR 结论；
  **首次真实板测 CFO 超 `coarse_cfo_unambiguous_range_hz` 必须停止**，不猜修、不放宽门限，
  只报真实失败项。

---

## 7. 红线（逐条不破）

不改模型/权重/标签/预处理/24→23 映射；不重训；不降 corr/residual/clip/CFO/SRO 门限；
不加固定 2.5× 补偿；不用标签估计同步/CFO/增益/训练参数；不把 TCP 传的 IQ 当真实 RF
接收；不让电脑与板端同时控同一台 SDR；不要求板端枚举电脑 USB 上的 SDR；不覆盖已通过的
fix9r2h5 目录；不直接跑 720 样本；未验证断线停止 TX 前不得上真实 RF。

24→23 映射：`SOURCE_TO_DEPLOYED = [0..16, 17, 17, 18..22]`；source 17 (AM-SSB-WC) &
18 (AM-SSB-SC) → deployed 17 (AM-SSB)；`kSourceClassCount=24, kDeployedClassCount=23,
kNpuOutputDim=24`。frozen baseline pred 须真实 24 类 logits 经 24→23 合并 argmax。

---

## 8. 交付物（用户检查后板端烟测）

① **PC TX 服务命令**（radioconda python，`-I` 隔离）：
```
D:\radioconda\python.exe -I host_tools\pc_tx_sdr_fix10.py --listen 0.0.0.0:39010 \
  --tx-uri "<PC_TX_URI>" --frozen-dir "<FROZEN_DIR>" \
  --input-kind radioml-d2-2p56m --center 2400000000 --sample-rate 2560000 \
  --tx-bw 18000000 --tx-atten -40 --rf-path direct-cable --rf-tx-target-rms 2048
```

② **板端 RX 服务命令**：
```bash
./scripts/run_gate9_rml23.sh \
  --phase=iq-pc-tx-board-rx-23class-fix10 \
  --tx-control=tcp://<PC_IP>:39010 \
  --rx-uri="<BOARD_RX_URI>" \
  --input-kind=radioml-d2-2p56m --frozen-dir="$D2_SMOKE_DIR" \
  --baseline=route_f_fix9r_exact_baseline.tsv \
  --center=2400000000 --rx-gain=30 --rf-path=direct-cable \
  --rf-tx-target-rms=2048 \
  --diagnostic-classes=BPSK,4ASK --diagnostic-per-class=1 \
  --out-dir=/root/fix10_pc_tx_board_rx_smoke
```

③ **设备 URI/序列号映射**：两端各一台 Pluto；PC 只枚举自己 USB 上的 TX SDR，板端只枚举
板端 RX SDR（`--tx-uri` 与 `--rx-uri` 分别显式给定；`usb:1.2.3.4` / `ip:192.168.2.1`）。

④ **防火墙端口**：TCP **39010**（PC 侧监听；板端出站连 `tcp://<PC_IP>:39010`）。

⑤ **frozen dir SHA256**：打包后记录（见 §9 结果）。

⑥ **BPSK + 4ASK 两样本验收字段**：
`scored=2 / rf_excluded=0 / prediction_agreement=2/2 / tx_restore_ok=1 /
rx_restore_ok=1 / negative_control=PASS / CFO finite·in-range / training estimate valid`。
B 通过 → 才开放 RadioML 46 样本；失败 → 停止并报唯一失败项，不自动新增诊断版本。

---

## 9. 已知风险 / 遗留（不阻塞 2 样本交付）

- **GMSK/OQPSK 潜伏 bug（继承 fix10-prep Path B）**：`scripts/gen_generated_clean_23.py:391`
  把 `source_class==22`（真实 GMSK）误调 `_oqpsk_signal`，`_gmsk_signal`(:333) 成死代码；
  source 23 才是 OQPSK(:406 正确)。影响 clean-23 source 22 标签正确性，**不影响 2 样本
  （BPSK/4ASK）**，且修 = 重生成 clean 数据 + 重冻结 SHA = 违反 §11 红线。**本次不修**，
  待用户后续拍板。
- **clean-IQ 验收 BLOCKED**（22/24 + Python 24→23 合并错误 + `scored>0` 即 PASS 门禁漏洞 +
  `MODEL_DOMAIN_NOT_PROVEN`），不属本任务，独立 clean 诊断热修处理。

---

## 10. 验证记录（离线）

- 四红线头 vs h5 字节一致：通过（见 §3 SHA）。
- h2→h5 漂移修复（§4「基线增量」3 处）：`test_iq_dual_sdr_fix10` 36/0、
  `test_clean_iq_23class_fix10` 26/0 单独复测通过。
- host 全套测试（含 3 新 C++ + Python unittest + 既有单 SDR h5 全套 + dual/clean 无新增
  回归）：`run_tests.sh: ALL HOST TESTS PASSED`（exit 0）。
- `D:\radioconda\python.exe -I host_tools\pc_tx_sdr_fix10.py --self-test`：14/14（radioconda
  libiio 0.26 backends xml/ip/usb、协议模块来自包内 host_tools、无同名误加载、WSL burst 工具
  帧身份 == h5、serve 参数校验 5 项——覆盖 serve 路径 `args.tx_atten` 崩溃）。
- **第二轮复核热修（2 项，用户复核后追加）**：① `recv_prepared`
  （`iq_pc_tx_board_rx_transfer_fix10.hpp`）原先只查 `configuration_verified` 的 `is_bool()`
  类型、不查 `==true`，板端会接受 `false` 后仍发 START → 新增 `if (!cv->as_bool())` 值校验
  fail-closed，并新增 host 测试 `test_reject_prepared_unverified` 断言 `recv_prepared()`
  拒绝 `false` 且不进入 START；② `pc_tx_sdr_fix10.py` `main()` 原先任何路径都返回 0 →
  `ProtocolError`/`TxEngineError`/`ManifestError` 返回 1、`KeyboardInterrupt` 返回 130、
  正常 `board_done` 返回 0。
- 打包器：red-line/protected/dependency-closure/**complete-delta**/**patch
  self-containment**/old-fix10 六审计全过（issue #2 新增后两项：patch 独立叠加 h5 的
  依赖闭合 + patch + h5 基线 == full 树的完整增量证明）；确定性两跑 SHA 一致（patch 31 文件
  / full 635 文件）。**最终 patch + full 的 64-hex SHA 记录在交付消息与记忆条目中，不硬编码
  于此文档** —— 本文档自身入包，若在此写 SHA 会自指循环、每次打包 SHA 都变。

### frozen dir SHA256（交付物 ⑤，外部数据，板测前由用户记录）

`--frozen-dir` 指向的 `radioml-d2-2p56m` 冻结 D2 工件**不在本包内**（它是 fix9r Route D2
流水线 `build_route_d2_rf_artifacts.py` 产出的冻结数据，本任务只复用，不重生成）。两样本
烟测前，用户在 PC 与板端各就位同一份冻结 D2 目录后，用以下命令记录其 SHA 供核对：

```bash
cd "$D2_SMOKE_DIR" && sha256sum -b route_d2_rf_manifest.tsv *.ci16 2>/dev/null \
  | sha256sum   # 或对整目录递归 sha256sum -b 后对清单再哈希
```

PC 侧 `--frozen-dir` 与板端 `--frozen-dir` 必须指向同一批字节（SHA 一致），否则 provenance
校验 fail-closed。
