# 板测手册 — hdmi-boot-display-fix1(修正版)

状态令牌：`…-READY-FOR-BOARD-COLLECTION`。**先只读采集,再决定是否安装**;我禁碰板,以下命令由用户本人
串口/ssh 执行。

> 重要前提: 本交付**不修重启黑屏**。根因是合并位流仅 JTAG 临时加载、上电即失效。本手册验证的是
> (1) 只读采集脚本如实反映该机制,(2) UI 自启服务在「位流已在位」时正确前台托管、正确就绪判据、
> fail-closed。真正修复(位流固化 Flash)红线禁止,不在此交付。

---

## 步骤 0 — 只读采集(必做,先于一切安装)

```bash
bash scripts/collect_boot_display_state.sh > /tmp/boot_display_state.txt 2>&1
cat /tmp/boot_display_state.txt
```

**从采集结果确认三件事**:

1. **[C] frame_ctrl 版本**: `devmem 0x4008000c` 在 JTAG 重载前为 `READ_FAIL`/非 `0x20230218`,
   重载后为 `0x20230218` → 佐证「位流仅 JTAG 临时加载、上电即失效」。
2. **[A]/[B] 默认启动位流**: QSPI/`/boot/` 实际存在什么 `BOOT.bin`/`*.bit`,dmesg 开机实际加载了什么。
3. **[C] FPGA 重配接口(仅枚举,不据此加载)**: `/sys/class/fpga_manager/*/name|state`、`/dev/xdevcfg`
   是否存在 —— 仅为将来授权后的硬件变更留档,本交付不加载位流。

---

## 步骤 1 — 手动前台测试 UI 脚本(不 enable,先验证单次)

**前置: 合并位流已由 JTAG 加载在位**(否则 UI 版本门必失败,这是预期,见步骤 4 反例)。

```bash
sudo bash scripts/boot_display.sh --ui-bin=/abs/path/board_ui_live_rml23
# 前台阻塞运行,stdout 依次出现(人就绪判据):
#   UI_LIVE_READY sock=/run/sdr_amr_ui_rml23.sock
#   UI_FB_INIT sock=...
#   UI_VERSION_CHECK base=0x40080000 version=0x20230218 expected=0x20230218 ok=YES
#   UI_FB_READY phys=0x... frames=2 frame_bytes=... refresh_hz=...
```

判据(三条同时满足才算 UI 真正上屏,不是只看 UI_LIVE_READY):
1. 进程存活;
2. `UI_VERSION_CHECK ... ok=YES`;
3. `UI_FB_READY phys=...`(帧缓冲真正建立并解禁)。

屏幕由黑 → 亮(等待帧)。Ctrl-C 停止。再跑一次 `boot_display.sh` → 打印 `UI_ALREADY_RUNNING`(幂等,不起第二实例)。

---

## 步骤 2 — 安装并 enable(用户明确批准后)

```bash
sudo bash scripts/install_boot_display.sh --ui-bin=/abs/path/board_ui_live_rml23
#   期望: OK ui_binary_installed /opt/sdr/bin/board_ui_live_rml23
#          INSTALL_OK service=boot-display-ui enabled=1 start=0
#   (默认不 --start;下次开机生效,不擅自立即启动)
```

---

## 步骤 3 — 重启验证(预期: 服务 fail-closed,证明「不修重启黑屏」)

```bash
sudo reboot
# 重启后(等 ~60s),再登录:
systemctl status boot-display-ui.service --no-pager
#   预期: failed (exit 3 / version_mismatch) —— 因位流已丢失,版本门失败。这是诚实信号,不是缺陷。
```

**反向判据(必须成立才证明结论正确)**:
1. 重启后服务进入 failed(而非假报 running/ready);
2. `journalctl -u boot-display-ui` 有 `UI_LIVE_FAIL error=version_mismatch`(或 framebuffer_init_failed);
3. 屏幕仍黑(未 JTAG 重载)。

---

## 步骤 4 — JTAG 重载后服务恢复(证明「便利项」可用)

```bash
# 用户本人 JTAG 重载合并位流后:
sudo systemctl restart boot-display-ui.service
systemctl status boot-display-ui.service --no-pager          # 期望: active (running)
journalctl -u boot-display-ui -n 5                           # 期望: UI_VERSION_CHECK ... ok=YES + UI_FB_READY phys=...
```

---

## 步骤 5 — 回退(若不需要该服务)

```bash
sudo bash scripts/uninstall_boot_display.sh
# 见 docs/ROLLBACK.md §2–§3 逐条核验
```

---

## 判定红线

- 最高离线状态只写 `…-READY-FOR-BOARD-COLLECTION`;**不写** BOOT_DISPLAY_PASS / AUTONOMOUS_BOOT_PASS。
- 本服务**不修重启黑屏**、不加载位流、不写 Flash;任何人不得据此宣称「重启自动显示已修复」。
- 不自动启动 SDR 发射或识别测试;无识别数据显示等待帧,不伪造类别/置信度。
- 显示失败不假报成功;不允许多个 UI 实例操作帧缓冲;不通过全局放宽 /dev/mem、设备节点权限。
- 停止 UI 不影响文件系统、模型、已保存测试结果;不修改接收恢复 fix2 工作树。
