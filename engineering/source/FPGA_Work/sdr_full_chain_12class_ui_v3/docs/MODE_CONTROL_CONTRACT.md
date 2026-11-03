# 反向控制通道契约（任务 39e5 UI v3 · M6–M10）

> 状态：**生产者集成完成（READY-FOR-GATE10-DISPLAY-AND-CONTROL-INTEGRITY-HARDWARE-TEST 的软件里程碑）**。
> 纯逻辑状态机：`board_package/mode_control.hpp`（iCraft-free，主机可测）。
> 控制通道**所有者 = Gate 9 实时生产者**（`board_package/board_gate9_full_chain_12class.cpp`），
> 不再是 LIVE UI 服务端。
> 控制客户端：`board_package/board_mode_ctl.cpp` + `scripts/mode_ctl.sh`。
> 主机测试 `host_tests/test_mode_control.cpp`（状态机 + 回环 reply）与
> `host_tests/test_producer_12class.cpp`（生产者接线：模式/运行态/停止真的生效）。

## 1. 目的

工作模式（FIXED/AUTO LOCK/BAND SCAN）与运行态（RUNNING/STOPPED）是**系统级控制状态**，
不属于逐帧分类数据，因此单独开一条**反向控制通道**（默认
`/run/sdr_amr_control.sock`）。

**关键权威关系（M6–M10 冻结）**：控制通道由 **Gate 9 生产者**持有与消费——它是唯一
`ModeState` 的所有者。LIVE UI 服务端**只显示**生产者回传的权威 `work_mode`/`run_state`
（随每条 `12class-chain-v2` 结果帧下发），**绝不**自改文字冒充模式生效。这直接解决
原「UI 控制 socket 只改 UI 内部显示态、不触达生产者」的缺陷。

## 2. 状态模型（`mode_ctl::ModeState`）

| 字段 | 类型 | 默认 | 语义 |
|------|------|------|------|
| `mode` | `ModeKind{Fixed,AutoLock,BandScan}` | `Fixed` | 工作模式 |
| `run` | `RunState{Stopped,Running}` | `Running` | 运行态（生产者启动即流式采集，故默认 RUNNING） |

- 显示名（MODE 页）：`FIXED` / `AUTO LOCK` / `BAND SCAN`。
- 线协议 token（SET_MODE）：`FIXED` / `AUTO_LOCK` / `BAND_SCAN`（下划线避免空格歧义）。
- 运行态显示名：`RUNNING` / `STOPPED`。

## 3. 命令协议（每行一条，空白分隔，大小写敏感，fail-closed）

| 命令 | 语法 | 成功回复 | 失败回复 |
|------|------|----------|----------|
| `SET_MODE` | `SET_MODE FIXED\|AUTO_LOCK\|BAND_SCAN` | `OK mode=<token>` | `ERR unknown_mode` / `ERR set_mode_usage` |
| `START` | `START` | `OK running=1` | `ERR start_usage` |
| `STOP` | `STOP` | `OK running=0` | `ERR stop_usage` |
| `STATUS` | `STATUS` | `OK mode=<token> running=0\|1` | `ERR status_usage` |
| 其它 / 空 | — | — | `ERR unknown_command` / `ERR empty_command` |

红线：**任何畸形/未知命令绝不改动状态**（`apply_command` fail-closed），仍回复 `ERR ...`；
绝不 throw。命令与 token **大小写敏感**（`set_mode` / `auto_lock` 拒绝）。

## 4. 生产者接入（`board_gate9_full_chain_12class.cpp`）

- 新增 `--ctl-sock`（默认 `/run/sdr_amr_control.sock`）；数据通道 `--sock` 不变。
- 生产者构造 `producer::Producer12` 后，用 `ui::UnixSocketServer` 绑控制通道；**bind
  失败则 fail-closed 退出**（`control_socket_bind_failed`，不静默丢控制面）。
- 打印 `GATE9_MODE_CTL_READY sock=... mode=... running=... <init_resp>`。
- 采集循环每次迭代 `drain_control(control, prod)`：`control.poll(0)` 非阻塞排空命令 →
  `prod.apply_command(line)`（`SET_MODE` 成功时同步 `WorkModeEngine::set_mode` 并重置
  扫频序列）→ `control.reply(resp)` → `GATE9_MODE_CTL cmd=... -> ...`。控制命令绝不
  阻塞采集循环。
- 每帧决策 `ProducerDecision.work_mode`/`.run_state` 随 `result_frame_v3_line` 下发；
  UI 侧由 `map_to_state` 解析显示。
- `STOP` 使 `running()==false` → 生产者暂停采集（`on_frame` 返回 `run_state=STOPPED`、
  `publish=false`、跳过测量），`START` 恢复。

## 5. 控制客户端（`board_mode_ctl` / `scripts/mode_ctl.sh`）

- 一次性客户端：连接 `--sock`（默认控制 socket，现由 Gate 9 生产者持有）→ 发送一行 →
  读一行回复 → 打印。
- 退出码：`0`=回复以 `OK` 开头，`1`=`ERR` 回复或 send/recv 失败，`2`=连接失败。
- 纯 g++（无 iCraft/libiio），由 `build_ui_live.sh` 与 UI 服务端一同构建安装到 `bin/`。
  `mode_ctl.sh` 直接 `exec` 该客户端。

## 6. UI 呈现（M5 渲染扩展）

- `UiState` 新增 `bool running = true;` 与 `std::string work_mode;`。二者**由
  `map_to_state` 从结果帧写入**（`mode_from_token` 把 wire token 转显示名；空 token
  回退 FIXED；`running = (run_state != "STOPPED")`），不再由 UI 服务端本地 `ModeState`
  写入。
- MODE 页详情卡在 `presence` / `level_mode` 之后显示 `run_state` 行：
  `RUNNING`（success 绿）/ `STOPPED`（warning 橙）。

## 7. 主机测试

- `test_mode_control.cpp`（状态机纯逻辑）：默认态、显示名/token/运行态名、
  `mode_from_token` 有效与无效、`split_ws`、`apply_command` 全命令 + 每类畸形不改态、
  `mode_state_line`、AF_UNIX 回环 reply。
- `test_producer_12class.cpp`（生产者接线）：`SET_MODE`/`START`/`STOP`/`STATUS` 经
  `Producer12::apply_command` 生效；`STOP` 后 `running()==false` 且 `on_frame` 返回
  `run_state=STOPPED`/`publish=false`/跳过测量；`START` 恢复。

## 8. 红线

- 控制通道只改 `work_mode` / `running`（系统控制态）与对应的**生产者**行为
  （FIXED/AUTO LOCK/BAND SCAN 的增益/锁/扫频），**绝不**改类别契约/分类结果/TX 功率/
  RF 安全路径（与触摸导航同一条红线）。
- 未实机验证只标 `READY-FOR-GATE10-DISPLAY-AND-CONTROL-INTEGRITY-HARDWARE-TEST`，不写任何
  *_PASS。
- 我禁碰板/禁写 Flash；上板由用户本人执行。
