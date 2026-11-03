# 回退手册 — hdmi-boot-display-fix1(修正版)

状态令牌：`…-ROLLBACK-READY`。本方案所有持久化改动都有可执行回退步骤,逐字节可还原到全手动状态。

---

## 0. 原始状态(回退目标)

- FPGA 位流: **不持久化**,JTAG 临时加载合并位流 `combined_npu_hdmi_disable_icap.bit`(SHA `22fec95c…`),
  掉电丢失。本方案**从不加载/重配/固化位流**。
- 启动: 无任何自启服务起 UI。
- UI: 手动 `scripts/start_live_rml23.sh`(RML23 链)。
- 冻结模型/识别算法/NPU 配置参数: 本方案从不触碰,无回退需求。

---

## 1. 本方案写入/改动的完整清单

| 文件 | 动作 | 原始状态 | 回退 |
|---|---|---|---|
| `/etc/systemd/system/boot-display-ui.service` | 新增 | 不存在 | `uninstall_boot_display.sh` 删除 |
| `/opt/sdr/bin/board_ui_live_rml23` | 新增(UI 二进制副本) | 不存在(或不影响;源二进制保留在原路径) | `uninstall_boot_display.sh` 删除 |
| systemd enable 状态 | enable `boot-display-ui` | disabled | `uninstall_boot_display.sh` disable |
| `/run/sdr_amr_ui_rml23.sock`、`/run/sdr_amr_control_rml23.sock`、`/tmp/sdr_ui_live_rml23/*` | 运行时残留 | 可能残留 | 脚本已清理(仅死亡进程残留) |

**不写入、不修改**: Flash / QSPI、BOOT.bin、`/boot/`、`/lib/firmware/`、合并位流 `.bit`、冻结模型文件、
识别算法、NPU 配置寄存器、任何历史交付、接收恢复 fix2 工作树。

---

## 2. 执行回退(用户本人)

```bash
# 方式 A: 一键回退(推荐)
sudo bash /opt/sdr/uninstall_boot_display.sh
#   期望: UI_STOPPED pid=<pid> 或 REFUSE_KILL pid=<pid>
#         UNINSTALL_OK service=boot-display-ui removed=1
#         已回到全手动状态: JTAG 加载位流 + 手动 start_live_rml23.sh。

# 方式 B: 手动逐步(等价)
sudo systemctl stop boot-display-ui.service 2>/dev/null || true
sudo systemctl disable boot-display-ui.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/boot-display-ui.service
sudo rm -f /opt/sdr/bin/board_ui_live_rml23
sudo systemctl daemon-reload
# 若 UI 还在跑,按 PID 文件安全停(不 pkill):
#   [ -f /tmp/sdr_ui_live_rml23/ui_live_rml23.pid ] && \
#     sudo kill -TERM "$(cat /tmp/sdr_ui_live_rml23/ui_live_rml23.pid)"
```

---

## 3. 回退核验

```bash
# 1) 服务单元已消失
systemctl list-unit-files | grep -i boot-display-ui || echo "OK: 无 boot-display-ui 单元"
# 2) 文件已删除
ls -l /opt/sdr/bin/board_ui_live_rml23 /etc/systemd/system/boot-display-ui.service 2>/dev/null \
  || echo "OK: 目标文件均已删除"
# 3) UI 未在跑
pgrep -af board_ui_live_rml23 || echo "OK: UI 未运行"
# 4) Flash/BOOT/位流未被动过(本方案从不写,此步仅为冗余核对)
```

---

## 4. 回退后行为

回到原全手动状态: 重启后屏幕仍黑(合并位流掉电丢失),需 JTAG 重载合并位流 + 手动 `start_live_rml23.sh`。
这与「安装前」行为**逐字节一致**——本方案未改变任何持久化硬件状态。
