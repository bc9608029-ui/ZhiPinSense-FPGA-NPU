# M17_HARDWARE_FINDINGS.md — M17 板端实测发现（用户板端日志转录）

> 本文记录 M17（任务 39e5）在实机上观察到的四类缺陷。**§2 全部为「用户板端日志转录」**，
> 非本机离线测得；离线侧只做根因归因与软件修复，最终结论仍以用户本人上板复测为准。
> 红线：未实机验证不写任何 `*_PASS`，我禁碰板 / 禁写 Flash。

## 1. 背景与基线

- 基线 MUST 使用已核验的 M16 全量包
  `dist/sdr_full_chain_12class_ui_v3_board_package_m16.tar.gz`
  SHA256 `47b599dc01e557835853c42265977c54071cb0138482c832cab6c3da0fa44590`。
- 权威合并位流 `combined_npu_hdmi_disable_icap.bit`（SHA `22fec95c…`）、十二类模型
  `model_12class.raw`（SHA `2ae95275…`）均保持不变。
- 12 类冻结顺序：`OOK,4ASK,AM-DSB,WBFM,2FSK,GFSK,BPSK,QPSK,8PSK,16QAM,64QAM,OFDM`。

## 2. 板端实测发现（用户板端日志转录）

### 2.1 Gate 10 默认参数 = settle 缺陷（回归）

- 命令行默认：`--frames=20 --seed=0x39e50001 --settle-frames=2`。
- 结果：**OOK 0/20**，十二类总计 **20/240**，绝大多数被预测为 **AM-DSB**；
  `requested_input_complex=462541`。
- 归因：M15 的「捕获 frames+settle 帧再丢弃前 N 帧」路径在连续逐类自测中破坏了首类
  （尤其 OOK）的相位/幅度连续性，导致首类样本对齐错位 → 全部误判 AM-DSB。

### 2.2 A/B 对照（`--settle-frames=0`）证实 settle 路径是根因

- `--settle-frames=0` 时：**OOK 20/20**，十二类 **236/240**，11 类各 20/20，
  **64QAM 16/20**，`requested_input_complex=421581`。
- 对照说明：去掉「捕获再丢弃」后 11/12 类恢复满分，仅 64QAM 剩 16/20 —— 这与 M15 已记录的
  64QAM int8 量化精度问题一致（见 `docs/64QAM_PRECISION_DIAGNOSIS.md`），**是模型鲁棒性问题，
  不是 settle 缺陷**。

### 2.3 TX/RX 缓冲生命周期计数错误

- 所有类均报告 `tx_buffer_create_count=1, tx_buffer_destroy_count=0`（快照在 PlutoTx
  析构**之前**采集）。
- 归因：生命周期 delta 在 `PlutoTx` RAII 析构器运行前读取，TX 缓冲此时尚未销毁，故
  `tx_destroy_delta` 恒为 0，无法证明「create==destroy 无泄漏」。

### 2.4 HDMI 撕裂 / 启动条纹

- 首次 submit 时屏幕顶部出现一条水平线；置信度数字更新时**反复闪烁**。
- UI 初始化**之前**（位流加载后）先出现条纹。
- 归因：见 `docs/FRAMEBUFFER_VBLANK_AUDIT.md` —— (a) 启动条纹 = `display_en` 复位为 1 且
  `camera_rd_addr` 复位为 `0x7E00000`，软件编程 rd_addr 前 PL 已扫描 DDR 残留；(b) 闪烁 =
  M16 每显示 tick（~33 ms）都重翻转缓冲选择，无 vblank 同步、翻转频率贴近显示帧率。

### 2.5 UI 空闲 CPU ~32%

- UI 在 `received=0/valid=0/rendered=0` 的静止状态仍占用 **~32% CPU**，持续 ~1min55s。
- 归因：静止帧仍每 tick 走完「渲染 → 拷贝 → msync → 翻转」整条路径，纯空转。

## 3. 根因 → 修复映射（本工程 M17 落地）

| 发现 | 根因 | 修复 | 代码/测试 |
|---|---|---|---|
| 2.1/2.2 | M15 settle 捕获-丢弃路径 | Task A：删除该路径，仅 `TIME_ONLY`；非零 `--settle-frames` fail-closed；官方捕获精确 `required_input(frames)` | `board_package/gate10_settle.hpp`、`board_gate10_selftest_12class.cpp`、`host_tests/test_gate10_settle.cpp` |
| 2.3 | delta 在析构前读 | Task B：快照时机移到 PlutoTx 析构 + 类末 `recreate_rx_buffer` 之后（不改 pluto_device），`tx_live=0/rx_live=0` | 同上（`gate10_settle.hpp` + `board_gate10_selftest_12class.cpp` + `test_gate10_settle.cpp`） |
| 2.4 (b) | 每 tick 重翻转 | Task E：`FlipScheduler` 事件驱动翻转 | `board_package/ui_dirty_state.hpp`、`board_ui_live_12class.cpp`、`host_tests/test_ui_scheduler.cpp` |
| 2.4 (a) | 复位地址残留 | Task F：启动先消隐、帧 0 有效且 rd_addr 编程后再解除 | `ui_sw/direct_framebuffer_backend.{hpp,cpp}`、`board_ui_live_12class.cpp`、`host_tests/test_display_integrity.cpp` |
| 2.5 | 静止帧空转 | Task G：同上 `FlipScheduler` + `UI_RUNTIME_STATS` | 同上 |
| 2.2 64QAM 16/20 | int8 量化精度（模型鲁棒性） | **只保留诊断证据，不重训/不调门限/不假修** | `host_tools/compare_64qam_threeway.py`（不变） |
| — | dump 证据不足 | Task C：`--dump-error-class` + 富化 manifest + SHA256SUMS | `board_gate10_selftest_12class.cpp`、`host_tests/test_gate10_settle.cpp` |
| — | 翻转无 vblank 同步 | Task D：只读审计 | `docs/FRAMEBUFFER_VBLANK_AUDIT.md` |

## 4. 状态红线

- 离线最高 **`READY-FOR-M17-GATE10-UI-INTEGRITY-AND-TOUCH-HARDWARE-TEST`**。
- 绝不写 `GATE10_PASS / SCREEN_PASS / TOUCH_MODE_CONTROL_PASS / FULL_CHAIN_HARDWARE_PASS /
  FINAL_MODEL_PASS / PROJECT_COMPLETE`。
- 64QAM 16/20 仅诊断归因，**不重训/不换模型/不调门限/不挑种子**。
- 我禁碰板、禁写 Flash；上板与复测由用户本人执行。
