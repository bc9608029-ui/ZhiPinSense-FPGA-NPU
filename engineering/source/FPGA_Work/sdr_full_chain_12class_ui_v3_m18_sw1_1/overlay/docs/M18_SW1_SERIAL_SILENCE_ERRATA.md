# M18-SW1 串口静默（Task B）勘误 与 M18-SW1.1 补丁说明

日期：2026-10-08
状态：M18-SW1.1 = `READY-FOR-M18-SW1.1-TOUCH-LOG-AND-ACCEPTANCE-HARDWARE-TEST`（未实机验证，不写 PASS）

## 1. 勘误：`run_ui_live.sh` 归属

M18-SW1 交付报告把 Task B「串口静默」表述为“`run_ui_live.sh` 实现了 stdin=/dev/null 及
stdout/stderr 日志重定向”。经逐字节核对，**该表述不准确**：

- `scripts/run_ui_live.sh` 与 M18-0 **逐字节一致**（SHA256
  `6a49f3b23d01713c1e810c0fa3f387685b7959e7c529170081aff6bff33b053d`），**不在
  M18-SW1 的 diff 清单内**。M18-SW1 对 M18-0 的实际改动 = **6 改 + 2 新**（另
  `SHA256SUMS.txt` 重生成），即：
  - 改：`board_package/board_ui_live_12class.cpp`、`board_package/touch_mode_control.hpp`、
    `board_package/ui_dirty_state.hpp`、`host_tests/test_touch_mode_control.cpp`、
    `ui_sw/ui_render.cpp`、`ui_sw/ui_render.hpp`
  - 新：`scripts/run_m18_sw1_touch_acceptance.sh`、`scripts/test_m18_sw1_touch_acceptance.sh`
- 重定向 `nohup "$BIN" --sock="$SOCK" "$@" >"$LOG_FILE" 2>&1 </dev/null &` 位于
  `run_ui_live.sh` **第 43 行**，其上方第 39–42 行注释带 **`[M18]`** 标记——即该重定向
  **M18-0 就已存在**，M18-SW1 并未改动它。

## 2. 串口静默实际由哪些 M18-SW1 改动实现

Task B 的**代码实现**集中在 `board_package/board_ui_live_12class.cpp`（在 M18-SW1 diff 内），
配合 M18-0 已有的 `run_ui_live.sh` 重定向：

| 需求 | 实现位置 |
|---|---|
| 启动最多打印一条 `UI_LIVE_READY` | `board_ui_live_12class.cpp:346`（循环前仅一次） |
| `UI_CTL` 仅真实 CONNECTED↔DISCONNECTED 跳变 | `board_ui_live_12class.cpp:625–634` |
| `TOUCH_CONTROL_STATS` 仅计数变化/退出 | `board_ui_live_12class.cpp:773–788` |
| `--verbose` / `--stats-interval` | `board_ui_live_12class.cpp:204–211`（解析）+ `:789–795`（周期） |
| stdin→/dev/null、stdout/stderr→日志 | `scripts/run_ui_live.sh:43`（**M18-0 已有，未改**） |

## 3. 缺口：无「真实后台子进程 fd」验证

M18-SW1 交付时，Task B 的 fd 重定向**没有被真实后台子进程 fd 验证过**——只有 `bash -n`
语法 + g++ 编译 + 逻辑测试。**不存在**「120 秒静默测试」；`process_guard.sh` 里的
`/proc/PID/fd` 读取只用于 Task C 的 socket 归属校验（`socket_served_by`），**不是**串口
（stdin/stdout/stderr）fd 校验。

## 4. M18-SW1.1 补丁内容

- `scripts/run_ui_live.sh`：新增 `UI_RUN_DIR` 环境变量覆盖（默认仍 `/tmp/sdr_ui_live`），
  使启动器可被 hermetic 测试——这是此前无法写真实 fd 测试的根因。**仅 1 行功能改动**
  （`RUN_DIR="${UI_RUN_DIR:-/tmp/sdr_ui_live}"`）。
- `scripts/test_serial_silence.sh`（新增）：真实后台子进程 fd 验证测试——用假
  `board_ui_live_12class`（输出与真实 server 相同），经真实 `run_ui_live.sh` 启动，读
  `/proc/<pid>/fd/{0,1,2}` 断言 stdin→/dev/null、stdout/stderr→日志；并断言启动器终端
  不出现周期行、日志包含全部周期行（含 stderr-only 标记，证明 `2>&1` 生效）。
- `docs/M18_SW1_SERIAL_SILENCE_ERRATA.md`（本文件）。

## 5. 不修改项（红线不变）

模型、RTL/XDC、位流、标签/分类阈值、SDR/NPU 数据链、framebuffer 换帧生产逻辑、
M18-0 A/B/C/D 诊断工具、M14～M18-SW1 历史交付包，均未改动。
