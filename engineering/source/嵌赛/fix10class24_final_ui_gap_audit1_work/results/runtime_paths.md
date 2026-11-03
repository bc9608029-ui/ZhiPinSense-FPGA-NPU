# 运行链（前向：捕获 → 预处理 → 分类 → 结果帧 → UI）

审查口径：只登记当前代码里"已接运行链"的路径；对未接线的模块单列"存在但未接"。

## 1. 主入口与 phase 分派

- 主入口 `board_package/board_gate9_full_chain_rml23.cpp`（基线树 B = `fix10class24_tx_rms_sweep1_work\sdr_rml24_fix10class24_tx_rms_sweep1`）。
- 默认 `--phase offline`；默认 `--model-json model_rml23/model_24class_ZG.json` / `--model-raw model_rml23/model_24class_ZG.raw`（**expA 23 类合并模型，非冻结 BF16**）。
- 默认契约 `chain::contract_23()`（23 类）。
- phase 合法性由 `gate9_phase.hpp::valid_phase()` 定义（22 个 phase），24 类 BF16 相关 phase 存在但非默认：
  `iq-clean-iq-24class-bf16-fix10`、`iq-pc-tx-board-rx-24class-bf16-fix10`、
  `iq-rf-loopback-24class-bf16-fix10`、`iq-rf-loopback-24class-bf16-scalarwl`。

## 2. 一键启动链（现状：23 类 expA）

- `scripts/start_all_rml23.sh`：先起 UI server（`board_ui_live_rml23`），后起 producer（默认 `--phase ambient`）。
- `scripts/common_rml23.sh`：`MODEL_JSON/MODEL_RAW` 指向 `model_rml23/model_24class_ZG.*`（expA）。
- 结果版本：producer 输出 `rml23-chain-v2`（`fill_result_rml23` + `merge_logits_23` 24→23 logaddexp 合并）。

## 3. LIVE 分类链（`--phase live-rx`，presence 门控）

- `run_live_rx_phase` 使用 `NpuClassifier24` + `rml23::merge_logits_23`（24→23）。
- `live_rx_gating.hpp::classify_now(s)` 仅当 `SignalPresent` 才分类。
- 结果经 `unix_socket_sink.hpp`（非阻塞，满则丢弃）发送到 UI socket
  `/run/sdr_amr_ui_rml23.sock`；分类/捕获不因 UI 变慢而阻塞。

## 4. 结果帧 → UI 渲染

- UI server `board_ui_live_rml23.cpp`：硬编码 `classes_23()`、`model_mode=rml23::kModelMode`、`class_count=23`。
- 解析 `parse_result_frame_rml23`：**拒绝一切非 `rml23-chain-v2` 帧**（`result_frame_rml23_parse.hpp`）。
- 状态映射 `ui_state_map.hpp::map_to_state_rml23`。
- 渲染 `ui_sw/ui_render.cpp`：存在 `CLASSES_23` 与 `CLASSES_24` 两套标签表（24 标签序与冻结事实一致），但 UI server 无切换到 24 类的代码路径，`CLASSES_24` 当前未被使用。

## 5. 冻结 BF16 24 类路径（存在但仅板测 phase，不进 UI）

- 模型 `model_rml24_bf16/`（json `28272abc…`、raw `c1781aec…`，与冻结事实一致；
  `compiler_metadata.json` = RAW24_UNMERGED / class_count 24 / output [1,24]）。
- `rml24_raw.hpp::raw24_predict`：24 类未合并，AM-SSB WC=17/SC=18 独立。
- 板测 phase `iq_rf_loopback_24class_bf16_fix10.hpp`：`raw24_predict` + `fill_result_rml24`，
  结果版本 `rml24-chain-v1`（`chain_common.hpp::kRml24ResultVersion`），source=`iq_rf_loopback_24class_bf16_fix10`。
- 该 phase 写 TSV 测量文件，**不接入 UI server**（UI 无法解析 rml24-chain-v1）。

## 6. UI 状态与徽章（现状基线 = tx_rms_sweep1）

- 状态徽章：LIVE / NO SIGNAL / STALE / ERROR / MOCK / STOPPED / WAITING / ACQUIRING / SIGNAL_PRESENT。
- 已知缺陷在基线：
  - `map_to_state` 无条件写 `top1/conf/dist` → NO_SIGNAL 时残留旧分类（B2）。
  - `signal_presence.hpp` SIGNAL_LOST/INVALID 无时限恢复（B1，旧版 44ac2e49）。
  - 修复存在于 nosignal 树（signal_presence 2ec93753、ui_state_map 1ab851e0），未并入基线。

## 7. 存在但未接运行链的模块

- 瀑布图：waterfall 树 `ui_sw/waterfall_history.hpp`（64KiB 环，10Hz 上限，无二次 FFT），
  状态 READY-FOR-INTEGRATION；基线无 waterfall 文件。
- 实时频谱曲线：基线只有 PARAMETERS SPECTRUM 标量卡片（`ui_render.cpp` 667-728）。
- 星座点云：constellation 树仅 FileIqFrameSource（`IqFrame.hpp` 116-118）。
- BAND_SCAN LO 扫描：`band_scan.hpp` sequencer/accumulator 纯逻辑未 compose。
- passive_scan（并行任务）：`passive_scan.hpp` prepare-only，未接入 board_gate9/CMake。

## 8. 帧率/吞吐约束

- UI socket 非阻塞，队列有界（CommandQueue/AckQueue 各 32；瀑布环 64KiB）。
- UI server 为独立进程，渲染不阻塞捕获/分类。
