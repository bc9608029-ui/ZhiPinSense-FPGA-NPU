# 根因审查 — hdmi-boot-display-fix1(修正版)

状态令牌：`…-ROOT-CAUSE-CORRECTED`。本版**撤回**上一版「三层无持久化→重启必黑」的过强结论与「方案2软件重配」，
按审阅意见与源码事实重新归因。

---

## 1. 现象

- 重启后屏幕不亮。
- 经 JTAG 重新加载 NPU＋HDMI 合并位流后恢复。

---

## 2. 直接原因(已证实,不是「未自启 UI」)

**合并位流 `combined_npu_hdmi_disable_icap.bit` 仅 JTAG 临时加载、上电即失效。** 重启后 PL 内无该位流,
HDMI 帧缓冲/720p 输出路径整体不存在,故屏幕黑。

证据链:

1. 设计上明确「绝不写 Flash」、位流仅 JTAG 临时加载(上电即失效):
   - `docs/BOARD_LIVE_UI_TEST.md:6`「JTAG 只烧该位流,**绝不写 Flash**」。
   - `docs/BOARD_SMOKE_TEST_COMBINED.md`「仅 JTAG 临时加载(上电即失效),绝不 program Flash / 绝不写 QSPI」。
   - `docs/BOARD_TOUCH_TEST.md`「仅 JTAG 临时加载,**绝不写 Flash**」。
2. 板端脚本不变量: `board_package`/`common_rml23.sh`「Authoritative combined bitstream(frozen;
   used only as provenance)。**Never re-programmed by any script。**」
3. 用户实测(本次): **手动启动 UI 仍然黑屏**。若「开机未自启 UI」是直接原因,手动起 UI 应当恢复;实际仍黑,
   证明原因在 PL 位流,不在 UI 进程。

## 3. 对上一版结论的撤回与更正

| 上一版说法 | 更正 |
|---|---|
| 「三层无持久化(C1位流/C2无重配/C3无自启UI)→重启必黑」 | 撤回。C3(无自启 UI)**不是**本次现象的直接原因;C1(位流未持久化)是直接原因。 |
| 「方案2: 开机软件重配 FPGA」 | 撤回,见 §4。 |

## 4. 软件重配方案为何撤回

上一版 `boot_display.sh` 设想「探测到 fpga_manager/fpgautil/xdevcfg 接口即把 `.bit` 交给软件加载」。撤回理由:

1. **无原始 `.bin` 位流。** 仓库只有 `.bit`(JTAG 格式,`outputs/smoke_v1/bitstream/combined_npu_hdmi_disable_icap.bit`,
   5,980,628 B,SHA `22fec95c…`)。Xilinx `fpga_manager` firmware 接口期望 raw `.bin`;`fpgautil -b` 对 `.bit`
   的兼容性在本板未核实。
2. **违背既有不变量。** `common_rml23.sh` 明确「never re-programmed by any script」。
3. **驱动/格式兼容、NPU/DMA 停止、服务顺序均未验证。** 软件重配要求停 NPU/DMA、正确的服务顺序,
   这些在本板均无依据。
4. **真正的修复是固化位流到启动介质(Flash/QSPI/BOOT.bin),被红线明确禁止**,且需 Vivado 生成
   BOOT.bin + 烧写流程,超出我「API 不碰板」职责,属硬件设计变更(原「方案3」)。

## 5. 结论

- **离线侧无法在红线内交付「重启自动显示」的修复。** 唯一真正修复 = 位流持久化(写 Flash/BOOT.bin),红线禁止,
  须用户另行明确授权。
- 离线侧能诚实交付的只有:
  - (A) **修正后的只读采集脚本**,用于板端确认上述机制 + 枚举实际存在的重配接口/启动位流(备将来授权后使用);
  - (B) **可选的 UI 自启服务**(正确二进制 `board_ui_live_rml23`、正确就绪判据、前台托管),仅省去 JTAG 重载后
    手动 `start_live_rml23.sh` 一步,**不修重启黑屏**,且位流未加载时 fail-closed(版本门失败即退出)。

## 6. 待板端事实(只读采集脚本收集)

1. 重启后 `devmem 0x4008000c` 是否 `0x20230218`(合并位流在位的身份),以及 JTAG 重载前后的差异。
2. 默认启动位流(QSPI/`/boot/`)实际内容与 dmesg 里开机实际加载了什么 → 佐证「位流未持久化」。
3. 实际存在哪些 FPGA 重配接口(`/sys/class/fpga_manager/*`、`/dev/xdevcfg`、`fpgautil`)及其只读状态 ——
   **仅枚举,不据此尝试加载**。
