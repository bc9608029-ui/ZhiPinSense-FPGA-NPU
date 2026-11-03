# M29 RML24 FIX10CLASS24 DUALSDR2 — Batch 2 Canonical Replay 审计

- 任务：39e5（fix10class24-dualsdr2 Batch 2）
- 交付：canonical 重放 patch + 新测试 + RF 扫描方案 + 审计报告 + full/patch 包 + SHA256SUMS
- 最高允许状态：**`M29-RML24-FIX10CLASS24-DUALSDR2-CANONICAL-REPLAY-READY-FOR-BOARD-RF-SWEEP`**
- 禁写：`SMOKE-PASS / RF-PASS / 24CLASS-PASS / PROJECT_COMPLETE / FINAL_*`；**API 不碰板**

---

## 1. 目的与范围

真实板端转储根因已定位（Phase D，见 `PHASE_D_ROOT_CAUSE_AUDIT.md`）：
- **D1**：RX 恢复参考 `payload_gain_training_complex()` 跨架构不确定（首个 int16 差异
  x86=-883 vs aarch64=-2650，delta=1767；前导/尾 ZC 一致，仅 payload-training 分歧）。
- **D2**：板端 BPSK 残差 0.116（corr 0.993，SNR≈18.7 dB）是真实 RF 噪声，非代码缺陷。
- **D3**：「BPSK 过/4ASK 过」是 RF 实现噪声，非调制相关（payload-training 块调制无关）。

Batch 1 交付的离线重放器用**运行时 `std::sqrt/std::lround` 动态生成** payload-training 参考，
与板端 aarch64 权威参考存在 D1 跨架构舍入差异，使重放器在「参考盲区」内无法精确复现板端字段。
Batch 2 修复该盲区（D1 的诊断工具部分）：

- 新增 `--canonical-reference`：改用**编译期内嵌的 aarch64 权威参考**
  `iq_fix10_canonical_frame_data.hpp`（红线头，不改）做恢复参考，**禁止** `std::sqrt/std::lround`
  动态生成 payload-training 参考。
- 默认旧模式（runtime 参考）**字节/行为不变**，只有显式 `--canonical-reference` 才走 canonical。

**不改**：24 类 BF16 模型 JSON/RAW、labels、baseline、0.10 `payload_training_residual` 门限、
sync/CFO/SRO/gain 估计/恢复数学、14 红线头、canonical 3 CI16 组件、PC/板 TCP 状态机、24→23 合并合同。

**禁**：BPSK 特判 / per-class 补偿 / 失败重试绕过；不得声称「提高增益必然带来固定 20 dB SNR 提升」。

---

## 2. 交付物清单（11 文件：5 new + 6 changed）

> 本包是 Batch 1 之后的首个包，故也纳入 Phase D 根因审计档与 Batch 1 审计档的 SHA 回填。

**新增（5）**：
| 文件 | 内容 |
|---|---|
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_PHASE_D_ROOT_CAUSE_AUDIT.md` | Phase D 真实转储根因（D1/D2/D3） |
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_RF_SWEEP_PLAN.md` | 三档 TX 衰减扫描方案（板端执行手册） |
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_CANONICAL_REPLAY_AUDIT.md` | 本文档 |
| `host_tests/test_fix10class24_replay_canonical.cpp` | 8 项必测（§4）的 in-process 覆盖 |
| `scripts/package_fix10class24_bf16_dualsdr2_canonical.py` | Batch 2 打包器 |

**修改（6）**：
| 文件 | 修改 |
|---|---|
| `docs/M29_RML24_FIX10CLASS24_DUALSDR2_PACKAGING_AUDIT.md` | Batch 1 最终 SHA 回填（full `097c6942…`/patch `57350773…`）+ 计数更正 12→13 patch 文件 |
| `host_tools/replay_fix10class24_failed_rx.hpp` | 新增 canonical 段：`verify_canonical_components/file`、`replay_canonical_from_dir`、`compare_canonical_vs_runtime`；新增 include `iq_fix10_canonical_frame_data.hpp` |
| `host_tools/replay_fix10class24_failed_rx.cpp` | 新增 `--canonical-reference/--canonical-file/--canonical-vs-runtime` 分支 |
| `host_tools/replay_fix10class24_failed_rx.sh` | usage 注释（功能不变，`-MM` 依赖闭包使缓存自动失效） |
| `host_tests/build_host_tests.sh` | 增 `test_fix10class24_replay_canonical` 编译行 |
| `host_tests/run_tests.sh` | 增 canonical 测试 + `--self-test` + `--canonical-vs-runtime` 运行行 |

---

## 3. canonical 重放模式（任务 §三 逐条）

1. **参考来源**：编译期内嵌 `iq_fix10_canonical_frame_data.hpp::kCanonicalPayloadTraining`
   （== `contracts/fix10_canonical_frame_v1/payload_training.ci16` 字节一致），或可选
   `--canonical-file FILE` 直接读 `.ci16`（两者 SHA 强制一致）。
2. **启动校验**：`verify_canonical_components()` 校验 `complex_count=1024`、`byte_count=4096`、
   `SHA256=f06e9b3de0f51594d8db0501a03918350072d4bc0e5a56f955053bafa35663ca`（前导/尾同验）。
3. **fail-closed**：缺失/错长/错 SHA 一律抛错退出（`test_asset_rejection` 覆盖 missing/trunc/tamper/good）。
4. **禁动态生成**：canonical 路径不调用 `std::sqrt/std::lround` 生成 payload-training 参考。
5. **真实 BPSK 复现**（对板端转储）：
   `timing_offset=36074`、`payload_training_residual≈0.116199`、`payload_training_corr≈0.993317`、
   `coarse_cfo_hz≈-118.316`（§5 实测）。
6. **浮点比较**：文档化小容差（timing 精确；coarse/fine 2e-2；corr/resid 1e-5）。
7. **默认旧模式兼容**：不加 `--canonical-reference` 时走原 runtime 参考路径，字节/行为不变。

---

## 4. 8 项必测覆盖

| # | 测试 | 覆盖方式 | 结果 |
|---|---|---|---|
| 1 | canonical 组件长度+SHA | `test_length_and_sha()` | PASS |
| 2 | missing/truncated/tampered 拒绝 | `test_asset_rejection()` | PASS |
| 3 | 默认旧模式不变 | 未修改的既有 `test_fix10class24_replay` 仍过 | PASS |
| 4 | canonical 逐字段复现真实 BPSK | `run_real()`（timing/coarse/fine/corr/resid 容差断言 + residual>0.10） | PASS |
| 5 | x86 两跑一致 | `run_real()` 二跑逐字段 `==` | PASS |
| 6 | canonical vs x86 动态参考真不同 + 首差异 | `test_reference_diff()`（`first_pt_diff_index=0 delta=1767`） | PASS |
| 7 | 不改生产 runner/恢复/模型/红线头 | packager 红线字节一致审计 | PASS |
| 8 | host_tests 全套无回归 | `build_host_tests.sh` + `run_tests.sh` | ALL PASSED |

---

## 5. 离线验证结果（实测）

### 5.1 编译
`build_host_tests.sh` 全量编译成功（exit 0），新增
`test_fix10class24_replay_canonical` + `replay_fix10class24_failed_rx` 均通过 `-Werror`。

### 5.2 canonical 逐字段复现（对板端转储 `board_capture/extracted/failed_rx/1500`）

```
test_fix10class24_replay_canonical: pass=27 fail=0
  payload_training FIRST_DIFF int16_index=0 runtime=-883 canonical=-2650 delta=1767
  canonical reproduced: timing=36074 coarse=-118.325155421 fine=-6.265276847
                        corr=0.993316525 residual=0.116198801
```

`.sh` wrapper canonical 模式（内容寻址缓存）：
```
FIX10CLASS24_REPLAY_CANONICAL dump_dir=... timing=36074 coarse_cfo_hz=-118.325155421
  fine_cfo_hz=-6.265276847 sro_ppm=0.000000000 fractional_timing_samples=0.294921875
  payload_training_corr=0.993316525 payload_training_residual=0.116198801
  payload_gain_mag=0.015481068 payload_phase_deg=-3.317406760 crosscheck=PASS
```

与板端字段对照（全部在容差内）：
| 字段 | 板端 | canonical 重放 |
|---|---|---|
| timing_offset | 36074 | 36074（精确） |
| coarse_cfo_hz | -118.316 | -118.325 |
| fine_cfo_hz | -6.27395 | -6.265 |
| payload_training_corr | 0.993317 | 0.9933165 |
| payload_training_residual | 0.116199 | 0.1161988（> 0.10，复现失败非通过） |
| payload_gain_mag | 0.0154811 | 0.0154811 |

**结论：canonical 重放精确复现板端失败转储**（含失败门限 residual>0.10，非「修好」）。

### 5.3 全套回归
`run_tests.sh` → **`ALL HOST TESTS PASSED`**（exit 0），含新增 canonical 测试。

---

## 6. RF 扫描方案（板端执行手册）

见 `docs/M29_RML24_FIX10CLASS24_DUALSDR2_RF_SWEEP_PLAN.md`：TX 衰减 -40/-35/-30 dB 三档，
rx-gain=30 固定，其余参数全程不变；每档 BPSK+4ASK 两样本；记录字段、通过条件、停止升功率条件、
3× 复跑、24 类单样本命令、如实上报规则。**先不扫 RX gain**；-30 dB 仍不稳定则停报。

---

## 7. 红线验证（打包器 fail-closed，全过）

- **14 红线头** 与 Batch 1 基字节一致（`iq_rf_sync_recovery.hpp` / `iq_rf_training_frame.hpp` /
  `iq_digital_loopback.hpp` / `iq_pc_tx_board_rx_transfer_fix10.hpp` / `iq_rf_fix9r_baseline.hpp` /
  `iq_clean_baseline.hpp` / `iq_dual_sdr_coarse_cfo_recovery.hpp` / `iq_pc_tx_board_rx_23class_fix10.hpp` /
  `iq_fix10_canonical_frame.hpp` / `iq_fix10_canonical_frame_data.hpp` / `rml23_merged.hpp` /
  `rml24_raw.hpp` / `rml24_bf16_baseline.hpp` / `iq_clean_iq_24class_bf16_fix10.hpp`）。
- **红线合同**（merged + raw24）字节一致。
- **protected 目录**（model/labels/baseline/clean24_smoke/contracts）字节一致。
- **canonical 3 CI16 + manifest** 字节一致（= aarch64 权威，未动）。
- **依赖闭包**：patch 内每个 C++ 引用的 quoted include 都在树内解析（含新增
  `iq_fix10_canonical_frame_data.hpp`）。
- **complete-delta**：base + patch == full（无删除）。
- **patch-over-base overlay**：patch 平铺覆盖 Batch 1 full == Batch 2 full（字节级）。
- **old-fix10 零残留**：无 external_rf / pluto_external 泄漏。

---

## 8. 打包

- patch：`dist/sdr_rml24_fix10class24_bf16_dualsdr2_canonical_patch.tar.gz`
  （平铺，覆盖 Batch 1 full 即可得 Batch 2 full）。
- full：`dist/sdr_rml24_fix10class24_bf16_dualsdr2_canonical_full.tar.gz`（单顶层目录）。
- 两侧车：`*_SHA256SUMS.txt`（`HASH *relpath` 约定）。
- 确定性：每个 tar **两跑字节一致**；独立解包 + `sha256sum -c` 全过。
- 最终 full/patch tar SHA 记录于交付消息 + 项目 memory（不自引用入包）。

---

## 9. 状态

本轮 Batch 2 离线验证完成：canonical 重放精确复现板端、8 项必测全过、host 全套无回归、
红线零触碰、确定性打包全过。状态推进为
**`M29-RML24-FIX10CLASS24-DUALSDR2-CANONICAL-REPLAY-READY-FOR-BOARD-RF-SWEEP`**。
（前序状态：Batch 1 `RECOVERY-DIAGNOSTIC-READY-FOR-BOARD-CAPTURE` → Phase D
`PHASE-D-ROOT-CAUSE-LOCATED`，见 `PHASE_D_ROOT_CAUSE_AUDIT.md` §5。）

后续（用户执行，API 不碰板）：按 RF 扫描方案跑三档 TX 衰减 → 找到最低通过功率 → 3× 复跑 →
24 类单样本。无板端结果前不写 SMOKE-PASS / RF-PASS / 24CLASS-PASS。
