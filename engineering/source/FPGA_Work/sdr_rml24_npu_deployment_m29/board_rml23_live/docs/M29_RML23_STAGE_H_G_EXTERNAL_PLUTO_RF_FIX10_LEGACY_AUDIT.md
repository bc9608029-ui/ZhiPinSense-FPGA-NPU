# M29 RML23 Stage H-G / Route G fix10 — Task A 旧草稿审计（FIX10_LEGACY_AUDIT）

状态：**`FIX10_LEGACY_AUDIT=READY`**（审计 + 分类完成；fix10 实现/打包/上板仍 BLOCKED）

本审计按 fix10 任务书 §2 执行：在写任何 fix10 新代码之前，把既有 fix10 草稿逐文件分成 **KEEP / REWRITE / DELETE** 三类，并给出 `duplicate_recovery_cores` 检测值。它只做**审计**，不写实现、不打包、不声明可上板。

**强制启动门（§1，未满足）**：完整 fix10 只能在 `fix9r2b 波形判因完成 → fix9r2 Phase 2 最小修复 → 同机 Pluto R8 两样本通过 → R9 46 样本通过 → ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS` 全部达成后启动。基线必须是**最终通过板测的 Route F 全量包**（记录其文件名/完整 SHA/训练帧版本/frame-layout 版本/恢复核心版本）；**禁止**继续以 fix9r1、fix9r2a 或未过板的 fix9r2b Phase 1 为基线。

---

## 0. FIX10_LEGACY_AUDIT 输出

```
FIX10_LEGACY_AUDIT
kept=2
rewritten=10
deleted=2
duplicate_recovery_cores=1
```

- `duplicate_recovery_cores=1` 是**草稿检测值**：草稿里存在 1 套与公共核心 `iq_rf_sync_recovery.hpp` 并行的第二套同步/CFO/SRO/提取核心（`iq_external_rf_rx.hpp::dsp`）。审计已把它归入 **REWRITE**，KEEP 内 = 0；**重写后必须 = 0**（任务书 §3 的硬目标）。
- 另有 **6 份本应存在但从未创建的 fix10 文件**（见 §4，属「缺失」而非 KEEP/REWRITE/DELETE）。

---

## 1. KEEP（保留，2 文件）

| 文件 | 保留依据（§2 可保留项） |
|---|---|
| `docs/M29_RML23_STAGE_H_G_EXTERNAL_PLUTO_RF_FIX10_TASK_A_AUDIT.md` | **官方资料审计**：libiio URI/USB 枚举、WSL2 USB/IP、iio_context 生命周期、AD936x 族（AD9364 1T1R 命名澄清）、采样率/带宽/12-bit、cyclic TX、双晶振 CFO/SRO 七项，四分类标注 + 官方源引用。**唯一瑕疵**：§0 基线引用 fix9r1（已过时），重启 fix10 时须把基线字段更新为最终 Route F 通过全量包。 |
| `sdr_adapter/pluto_device.hpp`（`FakePlutoDevice` 的 `rf_cfo_hz`/`rf_sro_ppm`，默认 0.0，host-only） | **公共测试扩展**（§3 明确允许）：双独立 Pluto 的 CFO/SRO 注入只在 fake 的 `read_rx` 回声路径生效（"the real board device is unaffected"），默认关闭、向后兼容、与恢复算法无关。 |

---

## 2. REWRITE（重写，10 文件）

| 文件 | 触犯的 §2 重写/删除项 | 重写方向 |
|---|---|---|
| `board_package/iq_external_rf_frame.hpp` | ②独立维护的训练帧（自造 CAZAC-16 前导/头/尾）、③旧 frame layout（自造 `[silence][preamble×2][header][guard][payload][guard][tail][silence]`）、⑧未版本化契约字段（只有 8-bit `kFrameVersion`，无 `training_version`/`sample_id`/`framed_logical_sha256`/`formatted_tx_sha256`） | 复用公共 `iq_rf_frame_layout.hpp` + `iq_rf_training_frame.hpp`；契约字段按 §4 Task C 的 20 字段机器可读 manifest 重做 |
| `board_package/iq_external_rf_rx.hpp` | ①复制/并行同步器（`dsp::` 的 S&C 粗 CFO + 匹配滤波 + 精 CFO + 尾前导 SRO + 提取，与 `iq_rf_sync_recovery.hpp` 并行 = **1 个 duplicate recovery core**）、⑤旧 valid 语义（自造 `RxWindowReport`/verdict，不用公共 typed `rec.valid`）、⑥不一致 residual 指标（`normalized_residual`=尺度无关 `‖e‖/‖x‖`，与公共 RMS 比 residual 口径不同）、⑨依赖第一个 USB 设备（RX `--uri` 可选 → `make_device("")` 后端扫第一台） | 复用公共 `iq_rf_sync_recovery.hpp` + `iq_rf_per_frame_recovery.hpp`；双 SDR 的更大 CFO/SRO 只作为公共算法的**向后兼容扩展/公共配置参数**（§3）；RX `--uri`+`--serial` 显式必填并逐字比对（§5/§7）；继承 fix9r2b 波形诊断（§10） |
| `board_package/pluto_external_tx.hpp` | 仪表语义不符 §6（`expected_dma_sha`/`tx_dma_payload_sha` 被称作「DMA readback」，而 §6 明确「不得称为 DMA readback」，只叫 `submitted_buffer_sha`；无 `requested_bytes`/`pushed_bytes`、无 `EXTERNAL_TX_DEVICE/CONFIG/FRAME/SUBMITTED_BUFFER/PUSH/READY/RESTORE` token、无 `--report-json`） | 保留「控制协议 + 安全序列 + URI/serial 逐字比对」骨架，重写仪表语义（§6） |
| `tools/pluto_external_tx.cpp` | ⑧未版本化 manifest（硬编码 24 列 `route_d2_rf_manifest.tsv` 的列 0/12/20/22，无 frame_version/training_version/sample_id 校验）、CLI 契约不符 §6（缺 `--sample-id`/`--report-json`/`--bandwidth`/`--duration-sec`/`--repeat`，只有 `--payload-dir/--manifest/--index/--count/--pause-ms/--loop`） | 重写 CLI 契约（§6）+ 复用版本化 manifest 契约（§4） |
| `host_tests/test_iq_external_rf_rx_23class.cpp` | 测试的是被重写的重复恢复核心；§12 要求**先失败用例再修复**、覆盖公共核心 | 重写为针对公共核心 + §12 的失败优先用例清单（CFO/SRO 网格 ±60 kHz/±50 ppm、任意循环起点、分数时延、跨 wrap、低 SNR 负对照、token 一致性、波形保存失败 fail-closed、内存/FD 有界） |
| `host_tests/test_pluto_external_tx.cpp` | 测试旧仪表语义（`tx_dma_payload_sha`） | 重写为 §6 新仪表语义（submitted_buffer_sha / requested vs pushed bytes / cyclic 生命周期 / Ctrl+C / short-push / serial 错配） |
| `board_package/gate9_phase.hpp` | 接线指向被重写的 runner（`iq-external-rf-rx-23class`、`iq-external-rf-level-sweep` 两相） | 相位名不变，接线在 runner 重写后重新验证 |
| `board_package/board_gate9_full_chain_rml23.cpp` | `#include "iq_external_rf_rx.hpp"` + 2 条 dispatch 分支指向被重写的实现 | dispatch 接线重做 |
| `host_tests/build_host_tests.sh` | 构建 2 个被重写的测试 | 构建接线重做 |
| `host_tests/run_tests.sh` | 运行 2 个被重写的测试 | 运行接线重做 |

---

## 3. DELETE（删除，2 文件）

| 文件 | 删除理由 |
|---|---|
| `host_tests/bin/test_iq_external_rf_rx_23class` | 编译产物（二进制），非源码；重写后重建 |
| `host_tests/bin/test_pluto_external_tx` | 编译产物（二进制），非源码；重写后重建 |

---

## 4. 缺失（本应存在但从未创建，6 文件）

fix10 草稿是**不完整草稿**（§0「此前 fix10 草稿不是有效交付物」的印证），以下文件在其自身头注释/任务书中被引用，但磁盘上不存在：

- `tools/build_external_pluto_tx.sh`（`pluto_external_tx.cpp` 头注释引用）
- `tools/run_external_pluto_tx.sh`
- `scripts/preflight_external_pluto_tx.sh`
- `scripts/package_external_pluto_rf_fix10.py`
- `docs/M29_RML23_STAGE_H_G_EXTERNAL_PLUTO_RF_FIX10_AUDIT.md`（主审计，现仅存在 Task A 审计）
- `dist/RML23_EXTERNAL_PLUTO_RF_FIX10_DELIVERY.txt`

这些**不属于** KEEP/REWRITE/DELETE；它们须在 fix10 解锁后按任务书新建。

---

## 5. duplicate_recovery_cores 检测

- 公共恢复核心（Route F，唯一权威）：`iq_rf_training_frame.hpp` + `iq_rf_frame_layout.hpp` + `iq_rf_sync_recovery.hpp` + `iq_rf_per_frame_recovery.hpp`。
- 草稿内的第二套核心：`iq_external_rf_rx.hpp::dsp`（`estimate_coarse_cfo`/`matched_filter_peak`/`estimate_fine_cfo_phase`/`estimate_sro_from_tail`/`extract_payload`/`aligned_fidelity`）。
- 检测值 = **1**；审计已将它归入 REWRITE，KEEP 内 = **0**。重写后必须 `recovery_core_count=1`、`training_generator_count=1`、`frame_layout_definition_count=1`（§3）。

---

## 6. 前向设计指针（§3/§4/§5/§7，仅设计，不实现）

- **§3 单一恢复核心**：双 SDR 的更大 CFO(±60 kHz)/SRO(±50 ppm)/任意循环起点/分数时延/频响补偿，只允许通过公共核心的**配置参数 / 向后兼容扩展 / 公共测试扩展**实现；禁止 `external_*_sync.hpp`、`fix10_sync.hpp`、`dual_sdr_recovery.hpp`。
- **§4 版本化 TX/RX 契约**：机器可读 manifest 需含 20 字段（frame_version/training_version/sample_id/source_index/source_class/deployed_class/modulation/sample_rate/center_frequency/frame_period/training_offset/training_length/payload_offset/payload_length/guard_before/guard_after/payload_sha256/training_sha256/framed_logical_sha256/formatted_tx_sha256）；PC TX 与板端 RX 共用同一份；frame_version/training_version/sample_id/payload SHA/sample rate/frame length 任一不一致必须 fail-closed，**不得靠文件排序猜样本身份**。
- **§5/§7 设备身份**：发射路径只实现一条（Windows-native 优先，否则 WSL+usbipd+libiio 0.21–0.26）；`--uri`+`--serial` 运行时强制，读回 serial 不匹配立即退出；板端纯 RX 强制 TX 关闭 + 不建 TX buffer + 数字回环读回 0 + RX 设备身份明确，检测到板端 TX 启用即 `BOARD_TX_UNEXPECTEDLY_ENABLED` 退出。
- **§10/§11/§15**：继承 fix9r2b 波形诊断（5 波形 + `route_g_waveforms.tsv`，离线分析器与 Route F 共用同一套口径）；负对照（TX 关/频错开/错训练版本/错 sample-id·SHA/随机噪声/截断帧）必须 `estimate_valid=0`+`classification=SKIPPED`+`scored=0`；逐文件指标由独立汇总器重算并对总行，不一致即 `INSTRUMENTATION_INCONSISTENT` 且禁打包；诊断模式 regression token 恒 `NOT_EVALUATED`。

## 7. 红线（不变）

禁写 `DUAL_SDR_PASS / EXTERNAL_RF_PASS / RF_PATH_PROVEN / BOARD_TEST_PASS / PROJECT_COMPLETE / FINAL_PASS`。host 完成后最多写 `M29-RML23-EXTERNAL-PLUTO-READY-FOR-BOARD-TEST`。两样本未过不准跑 46，46 未过不准跑 690。RadioML 回放（radioml-replay）与纯净生成（generated-clean）**分账**，不混为一个准确率。

**本次审计未写任何 fix10 实现代码、未打包、未声明可上板。**
