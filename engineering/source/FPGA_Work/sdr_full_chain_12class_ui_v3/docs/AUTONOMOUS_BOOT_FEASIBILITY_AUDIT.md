# 自主启动可行性审计（任务 39e5 UI v3 · M12）

> 状态：**审计完成（只读，不落地任何新脚本/init 单元/Flash 操作）**。
> 日期：2026-10-07。最高结论：**`AUTONOMOUS_BOOT_FEASIBILITY_AUDITED`**（审计，非就绪）。
> 依据：`docs/BOARD_SMOKE_TEST_COMBINED.md`（合并位流烟测 C1/C2/C3）、
> `docs/BOARD_LIVE_UI_TEST.md`、`scripts/run_ui_live.sh`、`scripts/run_gate7.sh`、
> `scripts/run_gate9.sh`、`scripts/common.sh`、`PROVENANCE.md`。

## 1. 目的

评估 FMQL30TAI 板上电后能否**无人干预**自动完成"加载合并位流 → 起 UI 服务端 → 跑十二类
真实链"的可行性，并精确列出缺口。本轮**只审计**，不改 RTL/位流/Flash，也不新增 init 脚本。

## 2. 当前上电/运行流程（实测现状，全部手动）

| 步骤 | 命令/动作 | 由谁执行 | 现状 |
|------|-----------|---------|------|
| 0. 加载位流 | JTAG 临时加载 `combined_npu_hdmi_disable_icap.bit`（SHA `22fec95c…`） | 用户（FMSH JTAG 工具） | **上电即失效**，绝不写 Flash |
| 1. 解包/构建 | `build_ui_live.sh` + `build_npu_on_board.sh --gate7-only/--gate9` | 用户（root） | 手动，逐门 fail-fast |
| 2. 起 UI | `./scripts/run_ui_live.sh` → `UI_LIVE_READY` | 用户（root） | 已含轮询就绪 + fail-closed |
| 3. NPU 自检 | `./scripts/run_gate7.sh`（8 条件） | 用户 | fail-closed |
| 4. 全链 | `./scripts/run_gate9_ui.sh --phase=offline/digital/rf` | 用户 | fail-closed + 射频安全门 |
| 5. 收工 | `./scripts/stop_ui_live.sh` + `sync && poweroff` | 用户 | 手动 |

**结论**：当前是**纯手动流程**，无任何 systemd/init/rc.local/@reboot 单元，无持久位流。

## 3. 自主启动的前提条件（拆解）

| # | 前提 | 现状 | 缺口 |
|---|------|------|------|
| A | **位流持久化**（上电自加载） | 仅 JTAG 临时加载，上电即失效 | **硬阻塞**：需 program QSPI/Flash 或外部主机每轮 JTAG 重载。写 Flash 被明令禁止，且需用户硬件决策 |
| B | 板端 Linux 有 init 机制（systemd/SysV/rc.local） | 未配置 | 需一个启动单元（systemd unit 或 `/etc/rc.local` 追加） |
| C | 一个**启动器**脚本（编排步骤 2→3→4，fail-closed） | 无（`run_ui_live.sh` 只起 UI） | 需新增编排脚本 |
| D | root 权限（UI 需 `/dev/mem`+`/dev/udmabuf0`） | 手动以 root 跑 | init 单元需 `User=root` 或等价 |
| E | 二进制 + 模型 + golden 已就位 | 手动构建/解包 | 需预先构建并固化到持久分区 |
| F | 身份判定（合并位流在位） | C1+C2 已实现（`Device::Open` + 版本门） | **无缺口**（复用） |

## 4. 现有可复用组件（无需新代码的部分）

- **位流身份判定**：C1（`Device::Open("axi://zg330aiu?…")` 成功）+ C2（`0x40080000+0x0C==0x20230218`）
  已由既有二进制 fail-closed 实现，可直接作为启动器前置检查。
- **UI 就绪轮询**：`run_ui_live.sh` 已轮询 `[ -S sock ]` + 日志 `UI_LIVE_READY`，100×0.2s 超时
  fail-closed；PID/sock/log 落 `/tmp/sdr_ui_live/`，`stop_ui_live.sh` 仅 `kill -TERM`。
- **门禁 fail-closed**：Gate 7（8 条件）、Gate 9（离线/数字/RF + `--confirm-safe-rf-path` 安全门）、
  `require_bin`/`require_libiio_runtime` 均非零退出即停。
- **模型/契约只读**：`common.sh` 从冻结 sidecar 读模型路径与 SHA，不写。

## 5. 可行性判定

- **软件侧（前提 B/C/D/E/F）**：**可行**。现有 fail-closed 脚本已覆盖 90%；仅缺一个编排启动器 +
  一个 init 单元（约几十行），且不碰 RTL/位流/模型。
- **位流侧（前提 A）**：**本轮不可行（被禁 + 需用户决策）**。合并位流持久化需写 QSPI/Flash；
  我禁写 Flash，且这是硬件事项，只能由用户决定是否/如何持久化，或保留外部主机每轮 JTAG 重载。
- **总体**：**`AUTONOMOUS_BOOT_FEASIBILITY_AUDITED`** —— 软件启动链可行且已基本具备，但"真正
  无人值守上电自启"被位流持久化（写 Flash）卡住，本轮仅审计、不落地。

## 6. 建议的启动器设计（文档化，本轮不落地为脚本）

```
autonomous_boot.sh（将来、由用户/后续里程碑决定是否落地）：
  1. require_bin board_ui_live_12class / board_gate7_12class_npu / board_gate9_full_chain_12class
  2. 启动器前置身份判定：
     - C1: Device::Open 成功（run_gate7.sh 或专用最小探针）
     - C2: 0x40080000+0x0C == 0x20230218（run_ui_live.sh 版本门）
     - 任一失败 → 打印 AUTONOMOUS_BOOT_FAIL bitstream_not_ready 退出（fail-closed）
  3. ./scripts/run_ui_live.sh（轮询 UI_LIVE_READY，失败退出）
  4. ./scripts/run_gate7.sh（NPU 自检 8 条件，失败退出）
  5. ./scripts/run_gate9_ui.sh --phase=offline（最强已知输入回放，失败退出）
  6. 全程日志落 /var/log/sdr_autonomous_boot.log；init 单元：
     [Unit] Requires=... After=...; [Service] ExecStart=/opt/sdr/bin/autonomous_boot.sh
     User=root; Restart=on-failure; [Install] WantedBy=multi-user.target
```

- 上述仅为**设计**：不新增脚本、不新增 systemd 单元、不写 Flash（本轮红线）。

## 7. 红线

- 本轮 M12 **只审计**，最高标 `AUTONOMOUS_BOOT_FEASIBILITY_AUDITED`；不写 `AUTONOMOUS_BOOT_READY`
  或任何 *_PASS。
- 位流持久化（写 Flash）**被禁止**，且属硬件事项需用户决策，不在本审计落地范围。
- 我禁碰板/禁写 Flash；上板由用户本人执行。
