# 合并位流首次烟测（smoke_v1）板端测试 — C1 / C2 / C3

> 状态：**READY-FOR-FIRST-COMBINED-HARDWARE-SMOKE**
> 未经实机验证绝不写 PASS。**我禁碰板、禁写 Flash；全部板端命令由用户本人执行。**

## 0. 前置：加载合并位流（仅 JTAG 临时加载，绝不写 Flash）

位流：`outputs/smoke_v1/bitstream/combined_npu_hdmi_disable_icap.bit`（5,980,628 B，经 Procise
`-disable_icap` FMSH patch，SHA256 `22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9`）。

```bash
# 仅 JTAG 临时加载（上电即失效），绝不 program Flash / 绝不写 QSPI。
# （由用户使用 FMSH JTAG 工具加载；本仓库不提供任何写 Flash 脚本。）
```

## 1. 合并位流身份判定（最小，软件侧，无新 RTL）

组合位流判定 = 两条件同时满足（各自 fail-closed，已由既有软件实现）：

| 条件 | 判定点 | 由谁实现 |
|---|---|---|
| HDMI 帧缓冲在位 | 读 `0x40080000 + 0x0C == 0x20230218`（frame_ctrl 版本寄存器） | `run_ui_live.sh` → `board_ui_live_12class` 版本门（C2） |
| NPU 在位 | `Device::Open("axi://zg330aiu?npu=0x40000000&dma=0x80000000")` 成功 | `run_gate7.sh` / `run_gate9.sh` 的 iCraft `Device::Open`（C1） |

- NPU-only 位流：C2 失败（无 frame_ctrl 版本寄存器）。
- HDMI-only 位流：C2 通过、C1 失败（`Device::Open` 抛异常 → exit 2）。
- **组合位流：C1 与 C2 均通过。** 因此 C1+C2 本身就是身份判定，无需新增寄存器或二进制。

## 2. 三条板端测试命令（逐条 fail-fast）

### C1 — NPU 自检（证明 NPU 在位 + re-arm 正确）

```bash
./scripts/run_gate7.sh
```

**通过门（8 条件，`GATE_RESULT` 一行为准）**：
`match_rate >= 0.90` 且 `processed == expected == 240` 且 `nan_inf == 0` 且
`npu_reset_count == 239` 且 `npu_frame_count == 240` 且 `npu_apply_count == 1` 且
`npu_discipline == OK` 且 `delay_detected == NO`。

### C2 — HDMI 帧缓冲显示（证明 HDMI 在位 + 版本门通过）

```bash
./scripts/run_ui_live.sh
```

**通过**：输出 `UI_LIVE_READY sock=... pid=...`，且日志出现
`UI_VERSION_CHECK ... ok=YES`（frame_ctrl 版本 `0x20230218`），屏幕显示初始 STALE 帧。
（测试后可 `./scripts/stop_ui_live.sh` 停止。）

### C3 — NPU + HDMI 并发（证明单板单位流下真实时链）

先确保 UI 服务端在跑（C2 已启动），然后：

```bash
./scripts/run_gate9_ui.sh --phase=offline        # 最强：已知输入 → NPU → 屏幕
# 或（Pluto 数字回环，链活性）：  ./scripts/run_gate9_ui.sh --phase=digital --rec-scale=<定标值>
# 或（外部 RF 回环，必须显式确认射频路径 + 衰减）：
#   ./scripts/run_gate9_ui.sh --phase=rf --rec-scale=<定标值> --tx-atten=-40 --confirm-safe-rf-path
```

**通过（offline）**：`GATE_RESULT` 显示 `frames == 240`、`match_rate >= 0.90`、
`sock_errors == 0`；UI 日志末条 `UI_STATS received == valid == 240`、`rejected == 0`、
`rendered >= 1 && rendered <= valid`、`last_frame_id == 最后一帧`；屏幕上实时显示十二类
分类结果（LIVE 徽标，非 MOCK）。

> **RF（Gate 9 --phase=rf）安全红线**：必须由用户本人确认同轴/衰减链路已接好，并显式传
> `--tx-atten=-40 --confirm-safe-rf-path`；软件不得绕过安全门。RF 发射属不可逆对外动作，仅在
> 用户明确确认射频路径后执行。

## 3. 通过后的状态升级（仅用户实测）

- C1+C2 通过 → 合并位流身份确认（NPU+HDMI 同单位流）。
- C1+C2+C3(offline) 通过 → `FULL_CHAIN_HARDWARE_PASS`（C1-C6 中的前几项，按最终任务书 §九）。
- 触摸（Gate C7）与 30 分钟稳定性、十二类 RF 属 **Batch 2**（`smoke_v2` / `release_candidate`
  独立版本目录），不覆盖 `smoke_v1` 的冻结位流与包。
