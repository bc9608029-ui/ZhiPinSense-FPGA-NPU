# sdr_full_chain_12class_ui_v1 — 十二类 Gate 7 门禁收尾 + Gate 9 实体屏幕实时链路集成（任务 39e5）

> **离线状态：`READY-FOR-12CLASS-LIVE-UI-HARDWARE-TEST`**
> （未经实机验证，**绝不**标 PASS / READY；我禁碰板 / 禁写 Flash，上板由用户本人执行。）

## 本工程做什么

在既有的十二类 SDR → NPU → UI 全链路（`sdr_full_chain_12class_v1`）基础上，补两件事：

1. **任务 A — Gate 7 延迟门禁修复**：板测 `delay_shift_match=10/236=0.04237` 只是相邻帧的
   偶然类别碰撞，不是固定一帧延迟，却会被旧门禁误报。新增 `delay_gate.hpp`（纯逻辑）把
   “强固定一帧延迟特征”（`delay_shift_rate>=0.90 且 > aligned_match_rate`）做成 8 条件
   `gate7_pass` 之一，并补 `infer_us` mean/p99/max 时延统计。
2. **任务 B — Gate 9 → Socket → 实体屏幕**：新增 `board_ui_live_12class` 服务端
   （AF_UNIX SOCK_STREAM），逐行严格解析 `result_frame_v2` JSON、映射到 Style A UI、
   经 DirectFramebufferBackend 双缓冲渲染到 HDMI 屏幕。

**绝不修改**三个原工程：`sdr_full_chain_12class_v1`、`hdmi_framebuffer_ui_v5_visual`、
`npu_realtime_v1`；每个拷贝文件的 SHA256 见 `PROVENANCE.md`（590 文件，0 不一致）。

## 关键结论（先读）

- **Gate 8 → Socket → 屏幕回放 兼容，可上板演示**（Golden logits → JSONL，不需要 NPU）。
- **Gate 9 → Socket → 屏幕（真 NPU 实时）BLOCKED**：NPU 与 HDMI 是**互斥的独立位流**
  （HDMI-only 位流无 NPU，且 `frame_ctrl@0x40080000` 落在 `npu=0x40000000` 窗口内），
  目前**没有已验证的 NPU+HDMI 合并位流**。`run_gate9_ui.sh` 会 fail-closed 输出
  `FULL_CHAIN_UI_BLOCKED bitstream_incompatible` 并返回非零，绝不假装 LIVE。
  详见 `docs/BITSTREAM_COMPAT_AUDIT.md`。

## 目录结构

```
sdr_full_chain_12class_ui_v1/
├── sdr_adapter/            ← 拷贝自 sdr_full_chain_12class_v1（原样）
├── board_package/          ← 拷贝 + 新增（delay_gate.hpp / result_frame_v2_parse.hpp /
│                              unix_socket_server.hpp / ui_state_map.hpp /
│                              board_ui_live_12class.cpp / build_ui_live.sh）
├── ui_sw/                  ← 拷贝自 hdmi_framebuffer_ui_v5_visual/sw（UiState 加 model 字段）
├── scripts/                ← 拷贝 + 新增（run_ui_live / stop_ui_live /
│                              run_gate8_ui_socket_test / run_gate9_ui）
├── host_tests/             ← 拷贝 + 新增（test_delay_gate / test_result_frame_parse /
│                              test_ui_live）
├── model_12class/          ← 拷贝（12CLASS_CHAIN_VALIDATION_MODEL，OOD=NO_GO）
├── deployment_golden/      ← 拷贝（240 输入 + expected sidecars）
├── docs/                   ← 拷贝 + 新增（BOARD_LIVE_UI_TEST / BITSTREAM_COMPAT_AUDIT）
├── PROVENANCE.md           ← 来源文件 SHA256 清单
└── SHA256SUMS.txt          ← 交付包自校验清单
```

## 三项强制修正（已实现并测试）

1. **UI 不要求 rendered==received**：NPU ~1.14ms/帧 > 30/60Hz 屏幕，服务端每个显示 tick
   先排空 socket、只渲染**最新**合法帧。契约：`received==valid(+rejected)`、`rejected==0`、
   `rendered>0 && rendered<=valid`、`coalesced==valid-rendered`、`last_frame_id==最后发送帧`；
   绝不逐帧阻塞 Gate 9。见 `scripts/run_gate8_ui_socket_test.sh` 的断言。
2. **run_gate9_ui.sh fail-closed**：无已验证 NPU+HDMI 合并位流标识符即
   `FULL_CHAIN_UI_BLOCKED bitstream_incompatible` 非零退出；演示只能标 `OFFLINE_REPLAY`。
3. **UI 启动核对 HDMI framebuffer 版本寄存器**：读 `0x40080000+0x0C` 必须等于冻结
   `0x20230218` 才碰 framebuffer，否则立即退出（`UI_VERSION_CHECK`）。

## 主机验证（已全 PASS）

- 8 个 C++ 测试 + 2 个 shell 测试：`host_tests/run_tests.sh` 全 PASS
  （含新增 `test_delay_gate 27/0`、`test_result_frame_parse 69/0`、`test_ui_live 96/0`）。
- ASan/UBSan 对 3 个新测试零失败。
- `bash -n` 全脚本零报错。
- `board_ui_live_12class` 主机全编译+链接通过（`build_ui_live.sh` → `UI_BUILD_RESULT result=PASS`，
  iCraft-free / libiio-free）。
- `board_gate7_12class_npu.cpp` 为 iCraft-only，**仅板上编译**（主机无 iCraft SDK）。

## 板端测试

见 `docs/BOARD_LIVE_UI_TEST.md`（逐门 fail-fast）。权威上板位流仍是 v4_fix
`hdmi_framebuffer_720p_top_disable_icap.bit`（SHA `df8a0c66…`），JTAG 只烧该位流，禁写 Flash。
