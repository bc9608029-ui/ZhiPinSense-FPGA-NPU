# M29 RML24 fix10class24-scalarwl-4way 审计 — OQPSK 单SDR 四路诊断

状态：**`M29-RML24-FIX10CLASS24-SCALARWL-4WAY-READY-FOR-BOARD-TEST`**
（最高允许状态；**禁写 RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_* / RUNTIME-INTEGRATED**）

本任务是**测量**，不是回归 PASS，也不是「板端准确率」。板端只产出**同一次真实单 SDR 捕获**的
两条模型输入 + 当前 BF16 模型的两组 24 维 logits + manifest；旧混合精度模型的两组 logits 在
Windows 离线（`icraft-run --backends Host`）从**同样的两份输入**产出。四路结果拼成 2×2
（scalar/wide-linear × BF16/mixed）argmax/一致性表，供**之后**决定最终修改——**本任务不做
任何修改**：不改 0.100 门限、不改生产行为、不重训。

---

## 1. 为什么做

Phase A（full24-accuracy1）已否定 0.100 门放宽的前提：双 SDR 链路上门旁路也只 18/24，错在
确定性同族升阶，来自板端 NPU。rxrecovery1 之后仍有一个未回答的问题：**同一次恢复，scalar
（`wide_linear=false`）与 wide-linear（`wide_linear=true`）两条模型输入，在当前 BF16 模型与
旧混合精度模型下分别给出什么 logits？** 这四路 logits 决定「wide-linear 补偿是否值得进入
生产模型输入」「BF16 vs 混合精度是否有输入路径耦合」——但**本任务只测量，不决定**。

只测 **OQPSK `source_index=11500`**（full24 里最难的类之一），一次真实单 SDR 捕获，最小诊断。

## 2. 复用点（全部探明并落实）

- **恢复核心（唯一权威，逐字节复用）**：`iqdual23fix10::recover_payload_with_coarse_cfo(rx,
  rec_cfg, payload_tx_scale)`，与双 SDR runner 调用**完全相同**。内部 coarse-CFO 预旋转 → 分数
  定时（Lanczos sinc）→ 三趟 `iqrfrec::estimate` → `iqrfrec::apply`。`rec_cfg` 逐字段一致：
  `min_corr=0.9` / `max_residual=0.100`（不变） / `max_cfo_hz=fine_cfo_range_hz()` /
  `max_sro_ppm=30.0` / `search_limit=0` / `payload_tx_target_rms=target_rms`。
- **有界重捕获 + 最终捕获选择**：逐字复现双 SDR runner；`retry = !stop && verdict=="RF_DISTORTS_IQ"
  && should_retry_payload_training_capture(...)`（≤3）；最终捕获 = 末次 attempt 的 `ccr`。
- **fidelity gate（用户三处逐字修正之一，精确 7 分支顺序）**：负控制 fail/clip →
  `RF_NEGATIVE_CONTROL_FAIL` → 负控制 unstable → `RF_NEGATIVE_CONTROL_UNSTABLE` → TX 期望裁剪 →
  `RF_TX_CLIPPED` → RX 裁剪 → `RF_RX_CLIPPED` → `!ccr.rec.valid`→`failure_rf_verdict(failure)` →
  `!cfo_in_range`→`RF_CFO_OUT_OF_RANGE` → 否则 `RF_PRESERVES_IQ`；`gate_ok=(verdict=="RF_PRESERVES_IQ")`。
- **退出清理（用户三处逐字修正之二，所有退出路径）**：`tx.stop()` → 确认 `tx_running()==false` →
  `DeviceStateGuard::restore()` → 记录 restore 结果（normal/early-return/异常/用户停）；runner 末尾
  显式同一次 `guard->restore()` 产出 `tx_restore_ok`，报告 `restore_report`。
- **单 SDR 物理传输（复用 singlesdr-ab1，不重写）**：`iqrfloop_run_24bf16::
  transfer_one_attempt_rf_24class_bf16_fix10(...)`（`board_package/iq_rf_loopback_transfer_24class_bf16_fix10.hpp`）
  负责单次本地 TX canonical burst + RX 捕获；`cfg.rx_gain_db=35` 显式覆盖 `prepare()` 默认 10 dB。
- **负控制（逐字复现双 SDR runner 内联辅助）**：`iqdiagswl::run_rx_negative_control` —— TX-off →
  确认停止 → ≥3 discard refill → ≥3 噪声窗 → 稳定比 ≤3；每样本一次，位于重捕获循环之外。
- **canonical TX burst**：`fix10canonical::buildTxBurstFromFrozen(...)` 产出与 PC-TX 字节一致的
  burst；`expected.tx_scale` 传进 `recover_payload_with_coarse_cfo` 的 `payload_tx_scale`。
- **模型输入构建（逐字节复用生产 classify 路径）**：`iqdiagswl::build_model_input` = payload →
  int16 → `PreprocessChain` → D2 restore → `select_classification_window` → `[2,1024]` fp32 tensor。

## 3. 四路诊断设计（2×2）

板端 runner（`iq_rf_loopback_24class_bf16_scalarwl_diag.hpp`）从**同一次恢复**产出两条输入：

| 输入 | 定义 |
|---|---|
| scalar | `iqrfrec::apply(aligned, rec{wide_linear=false})` |
| wide-linear | `iqrfrec::apply(aligned, rec{wide_linear=true})`；若 `estimate()` 未启用 WL，则 `recompute_wide_linear_coeffs` 逐字节复现 estimate() step 6.6 重算 (a,b) |

`aligned` 由 `reconstruct_aligned(rx, ccr)` 逐字节复现恢复核心的 LOCAL `aligned`（coarse de-rotate +
`apply_fractional_advance`），host 测试已证明「重新 apply 的 scalar payload == 生产 `ccr.payload`
（字节一致）」。两个 payload 之一必须与生产 `ccr.payload` 字节一致（scalar iff WL 禁用，WL iff
WL 启用），否则 runner fail-closed——这是 `aligned` 未偏离的强自检。

板端对两条输入各跑一次 BF16 推理 → `logits_scalar_bf16.bin` / `logits_wl_bf16.bin`（各 24×f32）。
Windows 离线对**同样的两份输入**（`model_input_scalar_f32le.bin` / `model_input_wl_f32le.bin`）
跑旧混合精度模型（`model_rml23/model_24class_ZG`，24 类源标签序，INT8 body + BF16 head）→
`logits_scalar_mixed.bin` / `logits_wl_mixed.bin`。四路拼成 2×2 argmax/一致性表 + `four_way_report.json`。

四路脚本（`scripts/four_way_oqpsk_scalar_wl.py`）只产出事实，**不做修改决定**：
- `--phase mixed-precision`：混合精度模型 SHA fail-closed + 导出输入 SHA 与 board manifest 逐字节
  对账 fail-closed + `icraft-run --backends Host` 各 ≥2 前向（repeat byte-identical 校验）。
- `--phase four-way`：BF16 pair（manifest 数组 + `.bin` 交叉对账 fail-closed）vs mixed pair →
  2×2 表 + 一致性布尔（scalar_bf16_mixed / wl_bf16_mixed / bf16_scalar_wl / mixed_scalar_wl /
  all_four）+ `four_way_report.json`。

## 4. 红线（逐字节不变）

- **17 个红线头**逐字节等于部署基线（rxrecovery1 FULL + singlesdr-ab1 PATCH）：恢复核心
  `iq_rf_sync_recovery.hpp` + `iq_dual_sdr_coarse_cfo_recovery.hpp`、双 SDR runner
  `iq_pc_tx_board_rx_24class_bf16_fix10.hpp`、canonical 帧 3 组件、transfer 状态机、raw24/baseline
  合同头、**singlesdr-ab1 传输头 `iq_rf_loopback_transfer_24class_bf16_fix10.hpp` + runner
  `iq_rf_loopback_24class_bf16_fix10.hpp`**（本任务逐字节复用，不改）。
- BF16 模型 json `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` /
  raw `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` / checkpoint `96cd25f8…`。
- 旧混合精度模型 json `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` /
  raw `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba`（四路脚本 SHA fail-closed）。
- 24 类标签序、`kPayloadTrainingResidualMax=0.100`、TX 安全上限 `--tx-atten<=-40`、canonical 3 CI16、
  clean24_smoke 24 文件 + manifest、baseline、rml23_merged/rml24_raw 合同。
- 旧 phase（尤其 `iq-rf-loopback-23class-fix9r`、`iq-pc-tx-board-rx-24class-bf16-fix10`、
  `iq-rf-loopback-24class-bf16-fix10`）行为不变。

## 5. 改动集（相对部署基线 = rxrecovery1 FULL `6fd93f78…` + singlesdr-ab1 PATCH `82e1aa8d…`，纯增量，无删除）

新增 9：
- `board_package/iq_rf_loopback_24class_bf16_scalarwl_core.hpp`（iCraft-free / libiio-free / NPU-free
  核心：reconstruct_aligned / recompute_wide_linear_coeffs / build_model_input / 负控制）
- `board_package/iq_rf_loopback_24class_bf16_scalarwl_diag.hpp`（板端专用 runner，唯一差异=板端
  BF16 推理；含精确 7 分支 fidelity gate + RAII 退出清理 + manifest）
- `host_tests/test_iq_rf_loopback_24class_bf16_scalarwl_diag.cpp`
- `host_tests/test_four_way_oqpsk_scalar_wl.py`
- `scripts/four_way_oqpsk_scalar_wl.py`（Windows 四路：mixed-precision Host 推理 + 2×2 一致性）
- `scripts/run_fix10class24_singlesdr_scalarwl.sh`（板端运行脚本）
- `scripts/package_fix10class24_bf16_scalarwl_4way.py`（本打包器）
- `docs/M29_RML24_FIX10CLASS24_SCALARWL_4WAY_AUDIT.md`（本文件）
- `docs/M29_RML24_FIX10CLASS24_SCALARWL_4WAY_BOARDTEST_NOTE.md`

修改 4（纯增量接线）：
- `board_package/gate9_phase.hpp`（`valid_phase()` 加 1 分支）
- `board_package/board_gate9_full_chain_rml23.cpp`（`#include` + 新 wrapper + error 文本 + dispatch）
- `host_tests/build_host_tests.sh`（注册新测编译）
- `host_tests/run_tests.sh`（注册新测运行）

## 6. host 测试结果（离线，不碰板）

- `bash host_tests/build_host_tests.sh` → **BUILD_RC=0**（含新 `test_iq_rf_loopback_24class_bf16_scalarwl_diag`）
- `bash host_tests/run_tests.sh` → **RUN_RC=0 / ALL HOST TESTS PASSED**（全套回归 + 新测，旧 phase 不破）
- 新 C++ 测 `test_iq_rf_loopback_24class_bf16_scalarwl_diag`：**0 fail**（phase 解析 7 +
  `reconstruct_aligned` 字节一致 + `recompute_wide_linear_coeffs` == estimate() 记录 (a,b) +
  过读 fail-closed + 0.100 门红线）
- 新 Python 测 `test_four_way_oqpsk_scalar_wl.py`：**12/12**（身份 2 + 四路数学 5 + 板脚本拓扑 4 + 接线 1）
- 四路脚本自测 `--self-test`：**36 checks / 0 fail**（标签序/模型 SHA/四路 5 场景/输入对账/
  f32le 读取 fail-closed）
- 红线 diff（打包器 fail-closed 审计）：源文件层面**恰好** 4 修改 + 9 新增；17 红线头 / 模型 /
  标签 / contract / canonical / 0.100 门 / singlesdr-ab1 传输+runner 逐字节未变。

## 7. 板测手册

**前提**：板端已部署 rxrecovery1 FULL（`6fd93f78…`）+ singlesdr-ab1 PATCH（`82e1aa8d…`）；
解压本 PATCH 覆盖即可（flat 路径）。构建 + 运行前确认 `LIBIIO_ROOT=/opt/sdr/libiio-0.26`。

**板端命令（由用户串口执行，我不碰板/不操作 SDR）**：

```bash
bash scripts/run_fix10class24_singlesdr_scalarwl.sh --rx-uri=usb:1.3.5 \
    --source-index=11500 --out-dir=/root/scalarwl_out
```

产出（`--out-dir`）：`model_input_scalar_f32le.bin` / `model_input_wl_f32le.bin` /
`logits_scalar_bf16.bin` / `logits_wl_bf16.bin` / `scalarwl_diag_manifest.json` / `run.log`。

**Windows 离线四路（icraft-run.exe，旧混合精度模型）**：

```bash
python scripts/four_way_oqpsk_scalar_wl.py --phase mixed-precision \
    --out-dir '<OUT_DIR>' --icraft-run /path/to/icraft-run.exe --model-dir model_rml23
python scripts/four_way_oqpsk_scalar_wl.py --phase four-way --out-dir '<OUT_DIR>'
```

产出 `logits_scalar_mixed.bin` / `logits_wl_mixed.bin` / `mixed_precision_manifest.json` /
`four_way_report.json`。判读：`four_way_report.json` 的 `cells`（四路 argmax/label/label_correct/
baseline_agreement）+ `agreement`（五项一致性布尔）。**脚本不输出任何 PASS/决定**；最终修改由
四路结果之后再定。

## 8. 停止条件

PATCH 包生成校验通过 + host 测试通过 + 板端构建/运行命令就绪 + 不碰板不操作 SDR +
等用户串口执行 → 暂停汇报。**不写任何 PASS 类结论；板端 BF16 对不可冒充 host 混合精度、反之亦然。**
