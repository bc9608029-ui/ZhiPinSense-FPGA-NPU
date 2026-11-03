# M17_BOARD_ACCEPTANCE.md — M17 板端验收（Gate 10 采样回归 + 生命周期 + HDMI 撕裂 + UI 空闲）

> 权威板端验收程序。逐门（Gate 10 → 生命周期 → 显示 → 空闲 → 触摸）给出**可核对的硬门禁**。
> 只测软件侧修复（位流仍为冻结 `combined_npu_hdmi_disable_icap.bit`，SHA `22fec95c…`）。
> 红线：未经用户本人实机复测**绝不**写任何 `*_PASS`；我禁碰板 / 禁写 Flash。
>
> **M17.1 勘误（本版）**：① 启动条纹 F1 拆分为 **F1a / F1b**——M17 软件只能保证
> UI 接管 frame_ctrl 之后（F1b），不能保证位流加载→UI 启动前（F1a，只记录，标
> `NEEDS-RTL-BLANK-ON-RESET`），不再宣称「彻底修复上电初始条纹」；② 触摸验收生产者
> 命令与启动顺序修正为 **UI 先起 → 长运行 digital 生产者 → 控制 socket → 触摸验收**，
> `--phase=offline` 一次性回放后即退出、**不是**长运行生产者，统一走
> `scripts/run_m17_touch_acceptance.sh`。

## 0. 前置与基线

1. 基线 = 已核验 M16 全量包（SHA `47b599dc…`）叠加本 M17 补丁（`dist/gate10_ui_integrity_m17_patch.tar.gz`），
   或直接使用 M17 全量包（`dist/sdr_full_chain_12class_ui_v3_board_package_m17.tar.gz`）。
2. 板端以 **`./build_on_board.sh g++` / `./build_npu_on_board.sh --gate10`** 权威 `-O2` 重编译
   （Gate 10 用 `build_npu_on_board.sh --gate10`，UI 用 `build_ui_live.sh`）。
3. 位流不变、模型 `model_12class.raw`（SHA `2ae95275…`）不变。

## 1. Gate 10（Task A 采样回归 + Task B 生命周期 + Task C dump 富化）

### A1 — settle 路径 fail-closed（必测，负例）

```bash
./board_gate10_selftest_12class --settle-frames=2 --class=0   # 期望 exit 1
```
- 期望：`error=settle_frames_deprecated_nonzero(2): ...`（非零 `--settle-frames` 被拒绝，绝不静默降级）。

### A2 — 默认运行 = TIME_ONLY 单次捕获（必测，正例）

```bash
./scripts/run_gate10.sh    # 默认 --settle-frames=0 --settle-wait-ms=100 --frames=20
```
- 期望每一类 `SELFTEST_CLASS_BEGIN/END` 都报：
  `settle_policy=TIME_ONLY`、`settle_frames_requested=0`、`settle_capture_samples=0`、
  `settle_refill_count=0`、`official_single_refill=1`。
- 期望 `official_requested_input_complex ≈ 421581`（= A/B 对照值；**不是**旧 settle 版 462541）。

### A3 — 逐类结果（必测）

| 项 | 期望 | 说明 |
|---|---|---|
| OOK | **20/20** | settle 修复的直接证据（旧默认 0/20） |
| 除 64QAM 外 10 类 | 各 **20/20** | 11 类满分恢复 |
| 64QAM | **16/20**（诊断） | 已知 int8 量化精度问题，**不重训/不调门限/不假修**，交棒 `ad_amr_12class_robust_v2` |
| 总计 | **236/240** | = A/B 对照值 |

> 说明：Gate 10 整体 exit 会因 64QAM 16/20=0.80 < 0.90 报 **FAIL**——这是**预期且正确**的；
> Task A 的验收依据是「OOK 与其余 10 类恢复 20/20、总 236/240 复现 A/B 对照」，而非整体 PASS。
> 不得为凑 PASS 降低 `--min-match-rate` 或更换种子。

### B1 — 生命周期平衡（必测）

每个 `SELFTEST_CLASS_END` 必须报：
```
tx_buffer_create_count=1 tx_buffer_destroy_count=1 tx_buffer_live_delta=0 rx_buffer_live_delta=0
```
- 期望每类 `tx_buffer_live_delta=0` 且 `rx_buffer_live_delta=0`（快照在 PlutoTx 析构 + 类末
  `recreate_rx_buffer` **之后**采集）。

### C1 — dump 富化 + 目标类过滤（可选，诊断）

```bash
./board_gate10_selftest_12class --dump-error-samples=20 --dump-dir=/tmp/m17_dump \
    --dump-error-class=7 --class=7
cd /tmp/m17_dump && sha256sum -c SHA256SUMS    # 期望全部 OK
```
- 期望：`manifest.tsv` 含 `class_frame_index / global_frame_index / tx_waveform_crc32 /
  official_rx_crc32 / model_tensor_crc32 / confidence / model_sha / bitstream_sha` 列，
  且只含 class=7 的行；`SHA256SUMS` 覆盖 `manifest.tsv` + 每个 `error_*.bin`，`sha256sum -c` 全 OK。

## 2. HDMI 显示（Task E 撕裂/闪烁 + Task F 启动条纹）

### F1 — 启动条纹（M17.1 拆分为 F1a / F1b，澄清验收范围）

M17 软件只能保证 **UI 进程接管 frame_ctrl 控制权之后**（消隐 → 清空 → render →
submit_frame(0) → 编程 rd_addr → 解除消隐）这一段；**无法**保证「位流加载完成 → Linux 启动 →
UI 程序尚未运行」这段屏幕是黑的——那取决于 RTL 的 `display_en` 复位值。

#### F1a — 位流加载完成 → UI 启动前（只记录，**不判 PASS/FAIL**）

- 范围：位流加载完成 → Linux 启动 → UI 程序尚未运行。
- 期望：**只记录**现象（是否出现上电初始条纹），**不作为本验收的通过/失败项**。
- 结论标注：`NEEDS-RTL-BLANK-ON-RESET`（未来 RTL 任务，见 `docs/FRAMEBUFFER_VBLANK_AUDIT.md`
  §7；方向 = `display_en` 复位为 0 + 软件在有效帧缓冲初始化后再解除 + 新位流 + Vivado 复验）。
- **M17 软件不宣称「彻底修复上电初始条纹」。**

#### F1b — UI 接管 frame_ctrl 之后（必测，M17 软件保证范围）

- 范围：`./scripts/run_ui_live.sh` 启动、UI 进程拿到 frame_ctrl 控制权之后。
- 期望：**消隐 → 清空两帧 → render → submit_frame(0) → 编程 rd_addr → 解除消隐**，
  首帧 submit 时屏幕顶部**不再出现水平线**。
- 顺序证据：日志先 `[DFB]` 消隐/清空 → `submit_frame(0)` → 编程 rd_addr → 解除消隐
  （退出码路径 `return 4/5/6/7/8` 不触发）。

### E1 — 置信度更新无反复闪烁（必测）

- 期望：稳定信号下（同一分类持续输出）置信度数字更新**不反复闪烁**；只有内容真实变化
  （新分类/状态/控制/触摸/翻页）才刷新一次。
- 证据：`UI_RUNTIME_STATS submits` 在静止期不再随 tick 增长。

## 3. UI 空闲 CPU（Task G）

### G1 — 静止低占用（必测）

- 前置：UI 服务启动但**无生产者**（`received=0/valid=0/rendered=0`）。
- 期望：UI 进程空闲 CPU **显著低于 ~32%**（用户实测 `top`/`ps`，量级应接近 ~0–2%）。
- 证据：`UI_STATS received=0 valid=0 rejected=0 rendered=0 coalesced=0` 且
  `UI_RUNTIME_STATS submits=1 skips=<增长>`（只有起始 1 帧提交，其余全部 skip）。

## 4. 触摸模式控制（Task H — M16 回归保全）

### H1 — 长运行生产者 + M16 触摸验收不回归（必测）

**正确启动顺序**（M17.1 勘误：`--phase=offline` 一次性回放 golden 后即退出、**不是**长运行
生产者；触摸验收必须用**长运行 digital 生产者**）：

1. 先启动 UI：`./scripts/run_ui_live.sh`，并等待 UI socket `UI_LIVE_READY`。
2. 再启动**长运行 digital 生产者**（连续 loop，非一次性，先校准 rec_scale）：
   `./scripts/run_gate9_ui.sh --phase=digital --rec-scale=<校准值> --frames=<大值>`
   （digital 相位是「链活性」连续生产者、绝不分类；必须先 `run_calibrate_rec_scale.sh`
   得到 `rec_scale.txt`，或显式 `--rec-scale`，**不静默用 1.0**）。
3. 等待生产者控制 socket `/run/sdr_amr_control.sock` 就绪。
4. 跑 M16 触摸验收：`./scripts/test_touch_mode_control.sh`。
- 一键编排（推荐）：`./scripts/run_m17_touch_acceptance.sh`
  （自动完成上述 1→4，含 rec_scale fail-closed + UI-first + 控制 socket 等待，
   输出 `M17_TOUCH_ACCEPTANCE result=PASS|FAIL`）。
- 期望：第三页实体触摸 FIXED / AUTO LOCK / BAND SCAN / START / STOP 全部正常，
  `M17_TOUCH_ACCEPTANCE result=PASS`（`commands_sent>0 && applied==sent && rejected==0 &&
  timeout==0 && duplicate==0`）。
- 说明：M17 的 UI 改动（事件驱动翻转 + 启动消隐）**不得破坏** M16 触摸模式控制
  （`touch_mode_control.hpp` / `control_client.hpp` / `touch_evdev.hpp` /
  `touch_geometry.hpp` 与 M16 字节一致，未改动）。

## 5. 验收结论怎么写

- 全部通过 → 只标 **`READY-FOR-M17.1-CORRECTED-HARDWARE-ACCEPTANCE` 已复测通过**，
  下一步才能由用户决定是否升 `*_PASS`（本工程离线侧**绝不**自行写 PASS）。
- 任一硬门禁未达 → 标 `NEEDS-...` 并回传日志（尤其 A3 逐类结果、B1 生命周期行、
  `UI_RUNTIME_STATS`、`DISPLAY_DIAGNOSTIC` 寄存器 dump）。
- 64QAM 16/20 不作为本门禁的失败项；但若 OOK 仍 < 20/20 或总 < 236/240，则 Task A 未通过。
- **F1a 不判 PASS/FAIL**：位流加载→UI 启动前若仍见上电初始条纹，只记录并标
  `NEEDS-RTL-BLANK-ON-RESET`（未来 RTL 任务），**不构成** M17 软件侧验收失败；
  F1b（UI 接管后首帧无水平线）才是本验收的硬门禁。
