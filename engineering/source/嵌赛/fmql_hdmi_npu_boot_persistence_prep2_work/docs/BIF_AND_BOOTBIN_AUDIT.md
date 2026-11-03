# .bif 与现有 BOOT.bin 审计（PREP2 离线）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
本审计全部**离线只读**：只解压/解析本地文件，不写板、不生成 BOOT.bin、不部署。

## 1. BOOT_Gen.rar 定位与解压方式

- 位置：`F:\嵌赛\2026嵌赛FPGA开发\BOOT_Gen.rar`
- 原始文件 SHA256：`daf51c9cad9dd7da8e466b0aa759e344c91de15ce5df260e673d8e9f8c825911`（3,894,795 字节）。
- 解压方式：**Windows 系统自带 bsdtar 3.8.9（libarchive）**（`C:\Windows\System32\tar.exe`），
  属于系统解包器，**未下载任何第三方随机工具**。解压到 PREP2 工作目录
  `_evidence/boot_gen_extract/`（独立目录，与脚本目录分离）。
- 解压时 bsdtar 打印 `Can't restore time: Invalid argument`（仅时间戳无法恢复，文件内容完整），
  不影响内容；所有成员均成功解出。

## 2. 归档成员与 SHA（解压后逐文件）

| 成员 | 大小 | SHA256 |
|---|---|---|
| `BOOT_Gen/7030ai_psin.bif` | 449 B | `2ac0ca602d2e1200cd92429880f7942aa52bd97007e678ef039f191393ab2389` |
| `BOOT_Gen/FSBL251210_ddr400_demo.out` | 1,385,156 B | `5501c470e07537a8fb369ae40641c20c16ab403fad558e65e0a4bbf380f2396f` |
| `BOOT_Gen/ai7030_edif_top.bit` | 5,980,020 B | `1405d7f1cb992d8f9c78e7b4bbe756faa96eeecb2ff4bdd0d253e92b191e2575` |
| `BOOT_Gen/bl31.elf` | 610,824 B | `fdcf0af48a7f9716f73a477c3cc1b4cd90c914fe0e5ad7acc5ab282660802303` |
| `BOOT_Gen/u-boot` | 6,579,840 B | `c4570e3e51128211905bdf20c7b7e0ea9cb7ca1492652a070ebdd985bc213e97` |

## 3. .bif 内容与分区顺序/属性（权威解析）

`7030ai_psin.bif` 全文（已解压可读）：

```
//arch = fmql; split = false; format = BIN
the_ROM_image:
{
	[bootloader, destination_device = ps]C:/Users/admin/Downloads/BOOT_Gen/FSBL251210_ddr400_demo.out
	[destination_device = pl]C:/Users/admin/Downloads/BOOT_Gen/ai7030_edif_top.bit
	[destination_cpu = apu_0, destination_device = ps]C:/Users/admin/Downloads/BOOT_Gen/bl31.elf
	[destination_cpu = apu_0, destination_device = ps]C:/Users/admin/Downloads/BOOT_Gen/u-boot
	[fsbl_config]apu_x32
}
```

**分区顺序/属性（BOOT.bin 内嵌顺序）：**

| 序 | 组件 | 属性 |
|---|---|---|
| 1 | FSBL251210_ddr400_demo.out | `[bootloader, destination_device=ps]` |
| 2 | ai7030_edif_top.bit | `[destination_device=pl]`（PL 位流，由 FSBL 编程） |
| 3 | bl31.elf | `[destination_cpu=apu_0, destination_device=ps]` |
| 4 | u-boot | `[destination_cpu=apu_0, destination_device=ps]` |
| 5 | (fsbl_config) | `apu_x32` |

镜像头：`arch = fmql; split = false; format = BIN`。
> 注意：`.bif` 里的路径是 vendor 生成时的绝对路径 `C:/Users/admin/Downloads/BOOT_Gen/...`，
> 用户按 `30TAI使用教程.pdf §3.1` 修改为本地解压目录后即可用 Procise「Create Image」生成 BOOT.bin。

## 4. vendor 示例 BOOT.bin 与 .bif 组件的对应关系

- 归档里的 `FSBL251210_ddr400_demo.out`、`bl31.elf`、`u-boot` 与 PREP1 已解包 vendor Lite 包
  `_evidence/vendor_docs/vendor_lite_boot/` 中同名文件 **字节一致**（SHA 相同）→ vendor 示例 BOOT.bin
  确实由这套组件打包。
- vendor 示例 BOOT.bin（`vendor_lite_boot/BOOT.bin`，SHA `ff350477e624c50d2f8180fb4b9130ec7688fbc7ca553412ed7c3dd2a68b31ef`，
  7,023,552 B）内部结构（本审计解析）：
  - 魔数 `0xAA995566`（文件字节 `66 55 99 aa`）@ `0x20`；标识 `HSMF`（小端 `FMSH`）@ `0x24`；
  - 加密字 @ `0x28` = `0x00000000`（未加密）；
  - 内嵌位流同步字 `66 55 99 aa` @ 偏移 186864；`XLNX` 位流标记 @ 158888；
  - `bl31` 标记 @ ~6,205,352；`u-boot` 标记 @ ~6,817,794；
  - FSBL ELF 内嵌源路径串 `C:\Users\liulei\Documents\ProciseWorks\demo_30tai\SDK\design_1_platform\FSBL\FM_QL_bsp\...`
    → **vendor 示例 FSBL 来自 vendor 的 `demo_30tai` 设计**。

## 5. 「位流是否内嵌」的诚实判定（不因逐字串缺失而误判缺失）

- vendor BOOT.bin 中**不含**明文 `ai7030`（设计名字符串）——因为打包时 `.bit` 的头部（设计名/part/日期）
  被剥离，只保留原始位流数据（'e' 载荷）。
- 但 vendor BOOT.bin **确实内嵌了 PL 位流**：存在位流同步字 `66 55 99 aa` @ 186864 + `XLNX` 标记 @ 158888。
- 两个候选 `.bit` 的原始 'e' 载荷（从同步字 `aa 99 55 66` 起）**均不逐字出现在** vendor BOOT.bin 中
  （打包/位序变换所致，符合预期）。
- **结论**：vendor BOOT.bin 内嵌了位流；不能因为「完整 `.bit` 字节串不逐字存在」就断言位流缺失。
  同理，未来对板备份 BOOT.bin 的判定必须用「同步字 + XLNX + 分区表」而非「设计名逐字搜索」。

## 6. 两个 vendor `.bit` 的命名/设计名对照（重要）

| 文件 | 设计名（.bit 头部） | SHA |
|---|---|---|
| `BOOT_Gen/ai7030_edif_top.bit` | `ai7030_top;UserID=53210711;Version=2018.3` | `1405d7f1…` |
| `vendor_lite_boot/ai7030_top_disable_icap.bit` | `ai7030_edif_top;UserID=53180205;Version=2018.3;…` | `6818b7f8…` |

> vendor 打包时文件名与设计名出现「互换」：`ai7030_edif_top.bit` 的设计名是 `ai7030_top`，
> `ai7030_top_disable_icap.bit` 的设计名是 `ai7030_edif_top`。两者是**不同 UserID 的不同变体**
> （`_disable_icap` 为调试用，见 `复微JFMQL30TAI器件VIVADO开发流程_V1.1` 「下载调试时请选择后缀为
> `_disable_icap.bit` 的位流」）。**未来方案 A 打 BOOT.bin 时，必须用我们的工作位流
> `combined_npu_hdmi_disable_icap.bit`（SHA `22fec95c…`）替换 .bif 中的 vendor 位流，而不是沿用 vendor 位流。**

## 7. 与「板当前 BOOT.bin」的比对（待板端采集）

- 板当前 BOOT.bin 的内容/SHA **尚未采集**（`UNCONFIRMED`）。拿到后（见 `collect_sd_boot_partition_ro.sh`）：
  1. 比对板 BOOT.bin 与 vendor 示例 BOOT.bin 是否字节一致（一致则板用 vendor 原镜像）；
  2. 用 `scripts/verify_boot_artifacts.py bootbin-info` 解析板 BOOT.bin 的魔数/标识/加密字/分区标记；
  3. 检查板 BOOT.bin 内嵌 FSBL 的源路径串，判断板 FSBL 是否也是 vendor `demo_30tai` 版（还是板方定制版）。

## 8. 局限

- 本审计**未生成**任何 BOOT.bin（Procise 闭源 GUI 未运行；`.bif` 仅解析，未用 Procise 打包）。
- vendor BOOT.bin 内嵌位流的「逐字节原始载荷」因打包位序变换未逐字对齐，故**未判定**其属于
  `ai7030_edif_top.bit` 还是 `ai7030_top_disable_icap.bit`（标注 `UNCONFIRMED`）。
- 板当前 BOOT.bin、板实际 FSBL 身份：`UNCONFIRMED`（待板端采集）。
