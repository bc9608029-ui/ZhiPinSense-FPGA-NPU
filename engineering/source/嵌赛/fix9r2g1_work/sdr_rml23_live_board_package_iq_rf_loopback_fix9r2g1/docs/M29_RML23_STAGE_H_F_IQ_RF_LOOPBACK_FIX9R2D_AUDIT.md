# M29 RML23 Stage H/F — IQ RF Loopback fix9r2d 诊断捕获增强（审计）

- 状态：**`M29-RML23-IQ-RF-LOOPBACK-FIX9R2D-READY-FOR-BOARD-TEST`**
- 交付性质：**诊断捕获增强**（observability completion）。**绝不改 RF 恢复数学**、不改 `iq_rf_sync_recovery.hpp`、不做 Phase 2、不跑 46 样本。
- 基线：fix9r2b 全量 `sdr_rml23_live_board_package_iq_rf_loopback_fix9r2b.tar.gz`，SHA `27ceb83322ae385bc74a0625b2088cc3cac769fb0f27172655798b1130755b42`（587 内容文件）。
- 上级判定：fix9r2c Phase 1 分析器已修复 3 个复数学 bug，真实波形等价门 PASS，但 `FIX9R2C_ROOT_CAUSE cause=NOT_IDENTIFIED result=NOT_PROVEN`。fix9r2d 是**唯一被批准**的后续动作：落盘 raw RX 切片 + 捕获元数据 + 逐切片 provenance，让离线分析器能把残余判为六种之一。

---

## 1. 为什么是 fix9r2d（继承自 fix9r2c 的 NOT_PROVEN）

fix9r2b 板测（R8 2 样本，BPSK/4ASK 各 1）落盘 5 个波形，但只有 `expected_training` / `aligned_rx_training`（raw 前导）/ `training_error` / `expected_payload` / `provisional_recovered_payload`（**已标量恢复域**）。**没有 raw aligned RX payload**，也**没有逐帧/逐周期原始切片**。fix9r2c 分析器修正复数学后复现了板端数值（BPSK corr 0.972983 err 3.4e-8 / res 0.237287 err 1.4e-6；4ASK corr 0.976160 err 5.0e-7 / res 0.222356 err 5.1e-7），但 M0–M4 候选模型**无一能把验证段 residual 降到 0.5×scalar 以下且双 blocked 方向 + 跨捕获一致改善**，判因只能 `NOT_IDENTIFIED`。

残余的候选解释是**复合失真**（~7.5–8.5 dB 滚降 + 逐 bin 相位噪声 + ~0.05 采样时延，非平稳），而现有 5 波形不足以区分「STABLE_LTI_CHANNEL / CYCLIC_BOUNDARY_TRANSIENT / CAPTURE_INDEX_MISMATCH / CYCLE_TO_CYCLE_NONSTATIONARY / TRAINING_PAYLOAD_GAIN_MISMATCH / NOT_IDENTIFIED」。fix9r2d 因此补充捕获：**原始 RX 切片**（raw 域的 payload / full_frame / cycle_0 / cycle_1）+ 捕获元数据 + provenance，让离线分析器在**下一次 R8 板测**之后能定量命名残余。本轮**不重新判因、不改恢复算法**。

---

## 2. 变更集（相对 fix9r2b 全量基线，共 11 文件 = 7 NEW + 4 MODIFIED）

### 2.1 fix9r2c Phase 1（**必须完整携带**，禁止 fix9r2d 包带回旧复数学 bug）

| 类型 | 文件 | 说明 |
| --- | --- | --- |
| MODIFIED | `scripts/analyze_fix9r2b_residuals.py` | 3 复数学 bug 修复（A1 标量共轭方向 / A2 定向 ComplexWarning 升级 / A3 双频带分带防跨 DC 伪影） |
| NEW | `scripts/test_fix9r2c_analyzer_regression.py` | 16/16 分析器回归 |
| NEW | `docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R2C_OBSERVABILITY_AUDIT.md` | 回放可行性 (a)/(b) 审计 |

### 2.2 fix9r2d 诊断捕获（本轮）

| 类型 | 文件 | 说明 |
| --- | --- | --- |
| NEW | `board_package/iq_rf_fix9r2d_diagnostic.hpp` | 8 切片 provenance 捕获 + 捕获元数据（`namespace iqrffix9r2d`） |
| NEW | `host_tests/test_iq_rf_fix9r2d.cpp` | 74 断言 host 测试 |
| NEW | `scripts/analyze_fix9r2d_capture.py` | 六判责离线分析器（含板端接受 fail-closed 门） |
| NEW | `scripts/package_iq_rf_loopback_fix9r2d.py` | 本打包器 |
| NEW | `docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R2D_AUDIT.md` | 本文档 |
| MODIFIED | `board_package/iq_rf_loopback_23class_fix9r.hpp` | 8 波形捕获块 + 捕获 manifest（新增 `complete` 列） |
| MODIFIED | `host_tests/build_host_tests.sh` | 构建 fix9r2d 测试；剥离 fix10 编辑 |
| MODIFIED | `host_tests/run_tests.sh` | 运行 fix9r2d 测试；剥离 fix10 编辑 |

### 2.3 不改变（红线，§6）

- `board_package/iq_rf_sync_recovery.hpp`（恢复核、帧布局、同步搜索、SRO/CFO/标量估计）**零改动**。
- 模型/权重/标签/24→23 映射；NPU 二进制；RadioML 数据；预处理合同；RTL/XDC/位流/Flash；TX 安全上限（`kSafeTxCeilingDb=-40.0`/`kSafeTxAttenDb=-89.75`）；现有 corr/residual/clip 门限。
- fix10 双 SDR 代码（on-disk 文件**绝不触碰**，仅打包时从两个共享接线脚本剥离 fix10 编辑）。
- `analyze_fix9r2d_capture.py` 的诊断算法**不再修改**（本轮只补接受门）。

---

## 3. 六判责 token（离线分析器输出域，`--out` JSON）

`STABLE_LTI_CHANNEL` / `CYCLIC_BOUNDARY_TRANSIENT` / `CAPTURE_INDEX_MISMATCH` / `CYCLE_TO_CYCLE_NONSTATIONARY` / `TRAINING_PAYLOAD_GAIN_MISMATCH` / `NOT_IDENTIFIED`。

任一板端接受前置条件不满足时，分析器 **fail-closed**：输出 `FIX9R2D_ACCEPTANCE result=REJECTED`，**不给任何六类 token**，退出码 2。

---

## 4. 8 波形种类（每 R8 文件落盘，2 样本 × 8 = 16 行 waveform manifest）

`expected_training` / `raw_aligned_rx_training` / `raw_aligned_rx_payload` / `raw_aligned_rx_full_frame` / `raw_cycle_0_full_frame` / `raw_cycle_1_full_frame` / `expected_payload` / `provisional_recovered_payload`。

provenance 证明：`save_slice_with_provenance` 独立重算内存 f32 SHA，`equality = (file_sha == mem_sha) ? 1 : 0`；越界切片返回空且 `equality=0`。捕获元数据含 `capture_sha256 / frame_index0 / frame_index1 / rms / dc / peak / clip_count / cfo_est / sro_est / gain_mag / gain_phase_deg / training_corr / training_residual / complete`。

---

## 5. 板端接受前置条件（delivery 写入，用户 39e5 批准的第 5 条）

板测落盘后，`analyze_fix9r2d_capture.py` 在判因**之前**强制校验，任一不满足即 fail-closed：

1. waveform manifest 数据行 == **16**（2 样本 × 8 波形）；
2. capture manifest 数据行 == **2**；
3. 所有 `provenance equality == 1`；
4. 两个样本 `capture_complete == 1`；
5. `raw_cycle_0_full_frame` / `raw_cycle_1_full_frame` / `raw_aligned_rx_full_frame` / `raw_aligned_rx_payload` 均非空且长度正确（无越界）。

---

## 6. 离线校验（打包前已跑，全部通过）

| 检查 | 结果 |
| --- | --- |
| fix9r2d host 测试 | **74/0**（`test_iq_rf_fix9r2d`，74 断言） |
| fix9r2c 分析器回归 | **16/16**（`test_fix9r2c_analyzer_regression.py`） |
| fix9r2b 分析器 self-test | **8/8** |
| fix9r2d 分析器 self-test | **7 判责用例 + acceptance-gate 6/6 = PASS** |
| fix9 及之前相关回归 | fix9 93/0 · fix9r 71/0 · fix9r2 66/0 · fix9r2a 38/0 · fix9r2b 47/0 |
| syntax / build（gate7/gate9/gate10/gate9_rml23） | 4/4 OK |
| dependency-closure（打包器 fail-closed） | PASS（所有变更头文件被 `ROUTE_F_FIX9R2D_FILES` 覆盖） |
| content-consistency（full == 基线 除 MODIFIED+NEW） | PASS |
| fix10 零残留 | PASS（`build/run_tests.sh` 剥离为 fix9r2d-only，无 `iq_external_rf_rx`/`pluto_external_tx`） |

> 说明：`iq_rf_loopback_23class_fix9r.hpp` 仅被 `board_gate9_full_chain_rml23.cpp` include（经 syntax 校验），无独立 host 测试直接驱动；其新增 `complete` 列与 8 波形捕获块经 syntax/build 校验通过。

---

## 7. 板端命令（用户执行，我禁碰板）

```bash
LIBIIO_ROOT=/opt/sdr/libiio-0.26 \
LD_LIBRARY_PATH=/opt/sdr/libiio-0.26/lib:/home/fmsh/ModelZoo/Deps/so \
./scripts/run_gate9_rml23.sh \
  --phase=iq-rf-loopback-23class-fix9r \
  --input-kind=radioml-d2-2p56m \
  --frozen-dir=<实际 frozen 目录> \
  --baseline=route_f_fix9r_exact_baseline.tsv \
  --diagnostic-classes=BPSK,4ASK \
  --diagnostic-per-class=1 \
  --center=2400000000 \
  --rx-gain=30 \
  --tx-atten=-40 \
  --rf-path=direct-cable \
  --rf-tx-target-rms=2048
```

`--rf-tx-target-rms=2048` **显式给出，不依赖默认值**（39e5 第 2 条）。落盘目录为 `<frozen-dir>/…` 下的 `route_f_fix9r2d_waveforms.tsv`（16 数据行）与 `route_f_fix9r2d_capture.tsv`（2 数据行）。

## 8. 离线判因命令（板测后）

```bash
python3 -I scripts/analyze_fix9r2d_capture.py \
  --wave-manifest route_f_fix9r2d_waveforms.tsv \
  --capture-manifest route_f_fix9r2d_capture.tsv \
  --out route_f_fix9r2d_verdict.json
```

（39e5 第 3 条：`python3 -I`、普通 basename manifest、`--out` JSON。接受门通过才输出六类 token 之一；否则 `FIX9R2D_ACCEPTANCE result=REJECTED` + 退出码 2。）

---

## 9. 门禁 / 红线 / 禁止 token

- 最高状态 `M29-RML23-IQ-RF-LOOPBACK-FIX9R2D-READY-FOR-BOARD-TEST`；**禁止** `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS / RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE / FINAL_PASS`。
- **不批准**：碰板；修改 `iq_rf_sync_recovery.hpp`；Phase 2 补偿；46 样本。
- fix10 / R9 46 / 690 / clean-23 仍 **BLOCKED**，等待 `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`。

## 10. 工件（打包器产出，未覆盖任何历史包；最终 SHA/字节见交付清单 §1）

| 工件 | 路径 | 内容 |
| --- | --- | --- |
| 独立补丁 | `dist/sdr_rml23_live_iq_rf_loopback_fix9r2d_patch.tar.gz` | 11 文件（7 NEW + 4 MODIFIED） |
| 合并全量 | `dist/sdr_rml23_live_board_package_iq_rf_loopback_fix9r2d.tar.gz` | 594 文件（583 fix9r2b 一致 + 4 改 + 7 新） |
| 补丁 manifest | `dist/IQ_RF_LOOPBACK_FIX9R2D_PATCH_SHA256SUMS.txt` | 11 行 |
| 全量 manifest | `dist/sdr_rml23_live_board_package_iq_rf_loopback_fix9r2d.SHA256SUMS.txt` | 594 行 |

fix9r2b 基线包 `sdr_rml23_live_board_package_iq_rf_loopback_fix9r2b.tar.gz`（SHA `27ceb833…`）与 fix9r2a/fix9r2 及更早历史包**均未覆盖**。fix10 零残留：全量包遍历 `iq_external_rf_rx`/`pluto_external_tx`/相关测试名 = NONE。最终两包 SHA、字节数、manifest SHA 以 `dist/RML23_IQ_RF_LOOPBACK_FIX9R2D_DELIVERY.txt` §1 为准。
