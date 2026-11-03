# 开机显示修复方案 — hdmi-boot-display-fix1(修正版)

状态令牌：`…-READY-FOR-BOARD-COLLECTION`。本版**撤回方案2(软件重配 FPGA)**,方案选择收敛为诚实结论。

---

## 1. 方案重评

| 方案 | 说明 | 结论 |
|---|---|---|
| 方案1 开机自启 UI | 仅起 UI 进程,不重配 PL | **不选为「修复」**: 位流未加载时 UI 版本门失败,屏幕仍黑。仅作为 JTAG 重载后的便利项保留(可选)。 |
| 方案2 开机软件重配 FPGA | 软件把 `.bit` 交给 fpga_manager/fpgautil | **撤回**。无 `.bin`;违背「never re-program by script」不变量;驱动/格式/NPU-DMA停止/顺序均未验证。 |
| 方案3 硬件设计变更(位流固化到 Flash/BOOT.bin) | 唯一真正修复 | **OUT-OF-SCOPE-FORBIDDEN**。红线禁止擅自写 Flash/替换 BOOT.bin;需 Vivado 生成 BOOT.bin + 烧写,超出「API 不碰板」职责;须用户明确批准并另行授权。 |

**结论: 离线侧在红线内无「重启自动显示」修复。** 交付收敛为两项诚实、可回退的辅助能力。

## 2. 交付 A — 修正的只读采集脚本

`scripts/collect_boot_display_state.sh`: 只读收集重启后/JTAG 重载后的位流身份与重配接口,
确认 §ROOT_CAUSE_AUDIT 的机制,**不据此尝试加载**。修正点:
- 移除 `fpgautil -o`(不是通用只读状态查询,`-o` 常见语义是设备树覆盖文件);
- FPGA 状态改用标准只读 sysfs `/sys/class/fpga_manager/*/name|state` + `ls` 枚举 `/dev/xdevcfg`;
- UI 进程/socket/日志改用 RML23 命名(`board_ui_live_rml23`、`/run/sdr_amr_ui_rml23.sock`、`/tmp/sdr_ui_live_rml23/`)。

## 3. 交付 B — UI 自启服务(可选便利,非修复)

`scripts/boot_display.sh` + `boot-display-ui.service` + `install_boot_display.sh` + `uninstall_boot_display.sh`。

- **正确二进制**: `board_ui_live_rml23`(不是 `board_ui_live_12class`),socket `/run/sdr_amr_ui_rml23.sock`
  + `--ctl-sock=/run/sdr_amr_control_rml23.sock`(与 `common_rml23.sh` 一致)。
- **前台托管**(修正 systemd 生命周期): service 用 `Type=simple`,直接 `ExecStart` 二进制,不用
  `Type=oneshot`+`RemainAfterExit=no`+脚本后台 `nohup &`(否则子进程会被 systemd 清理)。
- **正确就绪判据**(修正假报成功): 不只看 `UI_LIVE_READY`(它在帧缓冲初始化**之前**打印)。成功 =
  进程存活 **且** `UI_VERSION_CHECK ... ok=YES` **且** `UI_FB_READY phys=...`(帧缓冲真正建立并解禁)。
  失败 = `UI_LIVE_FAIL error=version_mismatch|framebuffer_init_failed` 或进程退出 → 非零退出,不假报。
- **不重配 FPGA**: 脚本不加载位流;位流是否在位的判定完全交给 UI 二进制自身的版本门(它在写任何寄存器前
  已强制校验 `0x40080000+0x0C==0x20230218`,不符即 `UI_LIVE_FAIL error=version_mismatch` 退出 3)。
- **绝对路径**: install 把用户提供的已构建 `board_ui_live_rml23` 复制到 `/opt/sdr/bin/board_ui_live_rml23`
  并据此写 service,不依赖 git 树路径。
- **明确语义**: 该服务**不修重启黑屏**。重启后位流丢失,服务会版本门失败(fail-closed);它是「JTAG 重载后
  免手动 `start_live_rml23.sh`」的便利,是否 enable 由用户决定。

## 4. 停止条件

- 离线侧到此为止: 修正文档 + 修正脚本 + 主机自检 + 打包 + 回退准备。
- **先只读采集**(交付 A),据此确认机制;安装(交付 B)由用户本人决定并执行,不自动推进。
- 最高状态令牌 `…-READY-FOR-BOARD-COLLECTION`;**不写** BOOT_DISPLAY_PASS / AUTONOMOUS_BOOT_PASS。

## 5. 红线(不变)

不写 Flash/不替换 BOOT.bin/不放宽 /dev/mem 或设备节点权限/不自动 SDR 发射或识别测试/无识别数据显示
等待帧不伪造/不允许多 UI 实例操作帧缓冲/不改冻结模型与 NPU 配置/停 UI 不影响文件系统·模型·测试结果/
不修改接收恢复 fix2 工作树。
