# M16 触摸模式控制契约（第三页实体触摸）

任务 39e5 UI v3 M16：终端用户直接在**第三页（MODE）实体触摸屏**上控制
`FIXED / AUTO_LOCK / BAND_SCAN / START / STOP`，无需终端。`mode_ctl.sh` 仅保留为
调试接口（`board_mode_ctl`），**不作为**本任务的验收证据。

## 1. 架构硬约束（冻结）

```
触摸按钮 --tap--> board_ui_live_12class --line--> /run/sdr_amr_control.sock
                                                       |
                                           Gate 9 唯一生产者（控制线程 ACCEPTED，
                                           生产者安全点 APPLIED）
                                                       |
                          回传 ACCEPTED / APPLIED / STATUS --> UI 更新实际状态
```

1. **UI 禁止**直接调用 libiio / 切 LO / 改增益 / 控制 Pluto / 操作 NPU。
2. **Gate 9 生产者是唯一硬件控制者**；UI 只是控制 socket 的纯客户端。
3. 复用 M15 的 command_id / 命令队列 / STATUS / apply 超时（`control_channel.hpp`）。
4. 点击只产生请求；**仅当对应 APPLIED 到达才高亮实际模式**。
5. REJECTED / TIMEOUT **保留原实际模式**。

## 2. 第三页布局与几何（单源 `ui::mode_ui`，`ui_sw/ui_render.hpp`）

- 模式按钮行：`FIXED / AUTO LOCK / BAND SCAN`，y ∈ [90,190]，各宽 390、间距 15，x0=25。
- 运行按钮行：`START`(x 25..625) / `STOP`(x 655..1255)，y ∈ [200,270]，各宽 600、间距 30。
- 详情卡：y ∈ [280,548]，六行——current mode / requested mode / run state /
  control connection / last command / command status。
- 按钮区**在底部导航带（y≥630）之上**，两点击区不重叠；几何由
  `ui::mode_ui::button_rect()` 同时供渲染器与触摸命中测试使用。

状态语义：高亮 = applied；PENDING / APPLIED / REJECTED / TIMEOUT /
CONTROL DISCONNECTED / STOPPED / RUNNING。

## 3. 控制协议（复用 M15，不新增命令）

| 方向 | 行 |
|---|---|
| UI → 生产者 | `SET_MODE FIXED\|AUTO_LOCK\|BAND_SCAN`、`START`、`STOP`、`STATUS` |
| 生产者 → UI | `OK accepted command_id=N <raw>` |
| 生产者 → UI | `OK applied command_id=N <raw>` |
| 生产者 → UI | `OK requested_mode=.. applied_mode=.. requested_running=.. applied_running=.. last_command_id=.. last_applied_command_id=.. control_queue_depth=.. mode=.. running=..` |
| 生产者 → UI | `ERR queue_full` / `ERR empty_command` / … |

- ACCEPTED ≤ 500 ms（控制线程），APPLIED ≤ 2 s（生产者安全点，`kApplyTimeoutMs=2000`）。
- 数据平面 `{"type":"state","command_id":N,...}` 事件与 result frame（`work_mode`/
  `run_state`）同为 applied 证据；state 事件按 command_id 解析，frame 仅推进 applied
  不解析 pending（frame 无 command_id）。

## 4. 状态机不变式（`board_package/touch_mode_control.hpp`）

- `requested_*`：仅由触摸推进；`applied_*`：仅由生产者证据推进。
- 两个独立 pending 槽：`mode_cmd_`（SET_MODE）与 `run_cmd_`（START/STOP），因此
  **STOP 高优先级，不被模式请求永久阻塞**；模式 + 运行可并发在途。
- 旧 command_id 应答忽略；重复提交（同槽已 pending）计 `duplicate_commands` 且不发命令；
  幂等（目标 == applied）不发命令。
- REJECTED / TIMEOUT 保留 applied；STOP 冻结上一次分类并显示 STOPPED，START 显示 RUNNING；
  常规 STOP ≠ STALE（STALE 仅在连接异常时出现）。
- 断开时丢弃在途命令（不臆造 REJECT/TIMEOUT），重连后发 STATUS，生产者 applied 为唯一权威。

## 5. 触摸规则

- 同按钮内按下+释放 = 一次点击；长按 = 一条命令（释放时发出）；拖出按钮 = 取消。
- 复用交换/翻转/去抖；每次有效点击一个 command_id；命令在途时禁止重复提交
  （STOP 例外，独立槽）；独立 `control_taps` 计数器。

## 6. CLI（`board_ui_live_12class` 新增）

| 选项 | 默认 |
|---|---|
| `--ctl-sock` | `/run/sdr_amr_control.sock` |
| `--control-timeout-ms` | `2000` |
| `--control-reconnect-ms` | `1000` |

UI 可在 Gate 9 之前启动；socket 缺失时按钮禁用；≤1 s 自动重连；重连后发 STATUS；
半行/粘行/多行应答正确拼接；绝不在渲染/触摸循环中阻塞；退出只关闭客户端 fd，
**绝不 unlink 生产者的 socket**。

## 7. 主机测试（`host_tests/test_touch_mode_control.cpp`）

13 覆盖点：按下/释放=一tap、拖出取消、长按=一条命令、去抖、五按钮映射、
模式幂等、模式 pending 时重复=duplicate、STOP 高优先级（两槽并发）、STOP 期间选新模式、
ACCEPTED 记 id 不 applied、APPLIED 按 id 应用、旧 id 忽略、REJECTED/TIMEOUT 保留 applied、
state 事件 by-id/by-target 解析、command_id=0 事件不解析、frame 仅推进 applied、
STATUS 解析、断开清 pending、以及经真实控制线程 + `ctl::ControlClient` 的全链路回环。

## 8. 板端验收（`scripts/run_m17_touch_acceptance.sh` 编排 + `scripts/test_touch_mode_control.sh` 统计）

**正确启动顺序**（M17.1 勘误：`--phase=offline` 一次性回放后即退出、**不是**长运行生产者）：

1. 先启动 UI：`./scripts/run_ui_live.sh`（等待 UI socket `UI_LIVE_READY`）。
2. 再启动**长运行 digital 生产者**：`./scripts/run_gate9_ui.sh --phase=digital
   --rec-scale=<校准值> --frames=<大值>`（digital = 链活性连续生产者、绝不分类；
   rec_scale 必须先 `run_calibrate_rec_scale.sh` 得到，或显式 `--rec-scale`，**不静默 1.0**）。
3. 等待生产者控制 socket `/run/sdr_amr_control.sock` 就绪。
4. 跑 `./scripts/test_touch_mode_control.sh`。

一键编排（推荐）：`./scripts/run_m17_touch_acceptance.sh`
（自动完成 1→4，含 rec_scale fail-closed + UI-first + 控制 socket 等待，输出
`M17_TOUCH_ACCEPTANCE result=PASS|FAIL`）。

`test_touch_mode_control.sh` **只做 prep/supervision/logging**（tail UI 日志 + 抓最终结果），
**不使用 mode_ctl.sh 替代手工触摸**。人类按
FIXED→AUTO LOCK→BAND SCAN→FIXED→STOP→START 触摸，最终统计：

```
TOUCH_CONTROL_RESULT result=PASS commands_sent= commands_applied= commands_rejected=0 commands_timeout=0 duplicate_commands=0
```

### 8.1 M17.2 编排脚本加固（版本化补丁，不改 C++/模型/RTL/位流）

`scripts/process_guard.sh`（纯 /proc + coreutils，无 `lsof`/`fuser`/`pgrep` 依赖）提供
`pid_alive / pid_exe / pid_matches_bin / find_pids_named / socket_served / socket_inode /
socket_served_by / stop_pid / log_offset_of / tail_since / run_id_new`。据此对
`run_m17_touch_acceptance.sh` + `test_touch_mode_control.sh` 叠加十项硬化：

1. 默认 producer frames = **有限值 2000000**（原 1e9），可 `--producer-frames=` 覆盖。
2. 每次验收**先停止并确认无旧 UI/Gate9 进程**（`stop_stale_services` +
   `confirm_services_stopped`），再由本包启动全新 UI。
3. **校验 PID + 可执行文件路径 + socket 归属**：`pid_matches_bin`（`/proc/$pid/exe` 精确比对）+
   `socket_served_by`（socket inode ↔ `/proc/$pid/fd`）。
4. **唯一 run_id + 日志偏移门控**：只接受本轮 `LOG_OFFSET` 之后追加的 `TOUCH_CONTROL_RESULT`
   （旧日志结果绝不假 PASS）。
5. **自定义 control socket 双端传递**：`--ctl-sock` 同时给 UI 与生产者。
6. **control socket 缺失立即 fail-closed**：`socket_served` 要求节点被活进程服务（陈旧节点 =
   不服务 = 直接 `TOUCH_CONTROL_PREP_FAIL`）。
7. **严格拒绝多行 rec_scale**：`rec_scale.txt` 恰好一行 `rec_scale=<value>`。
8. **EXIT/INT/TERM 只终止本轮 PID**：`_cleanup` 只 `stop_pid` 本轮 UI/PRODUCER PID；INT/TERM 重抛
   130/143。

`test_touch_mode_control.sh` 新增 `--ui-log / --control-sock / --timeout / --log-offset /
--run-id`；`await_result()` 只从 `tail_since "$UI_LOG" "$LOG_OFFSET"` 抓结果。主机侧
`scripts/test_m17_touch_acceptance.sh`（65 断言）覆盖旧日志假 PASS / 旧 socket / 孤儿清理 /
自定义 socket 四场景。

### 8.2 M17.3 最小脚本补丁（版本化，只改脚本/测试/文档，不改 C++/模型/RTL/位流）

`process_guard.sh` 新增 `stop_pid_if_matches <pid> <bin>`（kill 前先确认 PID 仍存活且可执行
文件精确等于 `<bin>`，已退出/被复用一律不信号）。据此四项修正：

1. **LOG_OFFSET 后移**：`LOG_OFFSET` 移到新 UI 启动、socket 归属（`verify_ui`）及 PID 验证
   全部成功**之后**采集——`run_ui_live.sh` 启动时**截断** UI 日志，启动前采集的偏移会越过新
   日志 EOF，`tail_since` 返回空、本轮结果被静默漏读。
2. **默认 producer frames = 50000**（原 M17.2 2000000），仍可 `--producer-frames=` 覆盖。
3. **cleanup 重验 PID 身份**：`_cleanup` 用 `stop_pid_if_matches "$PRODUCER_PID" "$PROD_BIN"` /
   `stop_pid_if_matches "$UI_PID" "$UI_BIN"`，kill 前重新验证 PID 仍对应本轮可执行文件。
4. **UI PID 文件 fail-closed**：PID 文件缺失 / 为空 / 非纯数字 / 身份不符（`verify_ui` 失败）
   一律 `M17_TOUCH_ACCEPTANCE_PREP_FAIL` 退出，绝不静默跳过验证。

主机侧 `scripts/test_m17_touch_acceptance.sh` 新增 §15–§18（LOG_OFFSET 顺序 / PID 文件
fail-closed / 旧日志大于新日志回归 / `stop_pid_if_matches` 功能），共 **78 断言**。

## 9. 状态红线

离线最高状态：`READY-FOR-M17.3-TOUCH-ACCEPTANCE`。
未经板端实体触摸实测，**绝不写** `TOUCH_MODE_CONTROL_HARDWARE_PASS` / `FINAL_HARDWARE_PASS` /
`PROJECT_COMPLETE`。
