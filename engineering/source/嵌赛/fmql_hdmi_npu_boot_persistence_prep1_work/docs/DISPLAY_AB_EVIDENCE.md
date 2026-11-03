# 严格显示 A/B 诊断（阶段 B）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。
本任务只交付**只读 MMIO 采集工具 + 用户手动执行手册**；板端采集是未来用户步骤，本任务未执行。

## 1. 目标

区分「磁盘上的启动文件 / 开机实际加载 / 当前已加载 FPGA 运行态」；用 A/B 对照回答：重启黑屏时与 JTAG 重载亮屏时，可见寄存器是否一致。

- **A 侧（黑屏）**：重启 → 同一 UI 二进制同一参数启动 → 记录黑屏 → 采集寄存器 → 停止 UI。
- **B 侧（亮屏）**：JTAG 加载工作位流 → 同一 UI/参数启动 → 记录亮屏 → 再采集寄存器。

## 2. 工具：`scripts/read_display_registers_ro.cpp`

不依赖系统中不存在的 `devmem` 命令。约束：

- `open("/dev/mem", O_RDONLY|O_SYNC)`，仅读已知寄存器；
- `mmap(PROT_READ, MAP_SHARED)`，**禁止任何写权限**（不映射 `PROT_WRITE`）；
- 读取失败 fail-closed：单寄存器失败即整体退出非零，并打印 `READ_FAIL`；
- 输出：寄存器地址、值、采集时间（`clock_gettime(CLOCK_REALTIME)` 单调打印）。

编译（板端，未来用户步骤）：`aarch64-linux-gnu-g++ -O2 -o read_display_registers_ro read_display_registers_ro.cpp`。
运行：`./read_display_registers_ro`（只读 `/dev/mem`，需 root）。

## 3. 采集寄存器清单（与 UI 源码一致）

| 寄存器 | 地址 | 语义 | 来源 |
|---|---|---|---|
| frame_ctrl VERSION | `0x40080000 + 0x0C` | 合并位流身份 `0x20230218` | UI log `UI_VERSION_CHECK base=0x40080000 version=0x20230218`；`ADDRESS_MAP_AUDIT.md` |
| frame_ctrl 帧基址/控制 | `0x40080000 + 0x50`, `+0x54` | framebuffer 物理基址 | `ADDRESS_MAP_AUDIT.md`（frame_ctrl 用 `0x0C/0x50/0x54`） |
| pl_ddr core VERSION | `0x400C0000 + 0x00` | NPU 数据路径版本 `0x20260929` | `board_package/pl_ddr_register_map.hpp` |
| pl_ddr core STATUS | `0x400C0000 + 0x08` | 忙/完成/错误位 | 同上 |
| udmabuf phys/size | sysfs `/sys/class/u-dma-buf/udmabuf0/phys_addr`,`size` | 帧缓冲物理地址/容量 | 板端采集 |

注意：HDMI/VTC enable、分辨率/同步参数、MMCM/PLL lock、HDMI reset/disable、DMA/读帧状态的**具体 MMIO 偏移**在本地可读源码里未逐一定位（`hdmi_framebuffer_720p_top.sv` / `frame_ctrl` 的寄存器定义未随附到本工作树），因此工具只读「已确认的寄存器」+「已知 sysfs」，**不猜测未知偏移**。

## 4. 与 UI 日志的对照（就绪判据，不是 UI_LIVE_READY）

`_evidence/board_capture/board_ui_after_jtag.log` 的标记顺序：

```
UI_LIVE_READY sock=/run/sdr_amr_ui_rml23.sock          ← socket bind 后、帧缓冲 init 前
UI_FB_INIT sock=...
[DFB] udmabuf phys=0x30100000 size=134217728 ...
[DFB] frame_ctrl version = 0x20230218 (expect 0x20230218)
UI_VERSION_CHECK base=0x40080000 version=0x20230218 expected=0x20230218 ok=YES
UI_FB_READY phys=0x30100000 frames=2 frame_bytes=1843200 refresh_hz=30
```

**就绪判据 = 进程存活 + `UI_VERSION_CHECK ... ok=YES` + `UI_FB_READY phys=...`**；单独 `UI_LIVE_READY` 不算成功。失败：`UI_LIVE_FAIL error=version_mismatch|framebuffer_init_failed` 非零退出。

## 5. 判定规则

- 若 A/B 两侧寄存器一致但物理输出不同 → 必须写：
  「可能是未暴露的 PLL、复位、PHY、I2C HDMI 芯片或 JTAG 重配置副作用；不能仅凭已有寄存器唯一定位」。
- 若 A 侧 `frame_ctrl VERSION != 0x20230218`（或读失败）而 B 侧 `==0x20230218` → 佐证「位流仅 JTAG 临时加载、上电失效」。
- 任何读取失败 fail-closed，不把失败当「0 值」继续。

## 6. 手动执行步骤（用户未来执行）

见 `docs/BOARDTEST_READONLY.md`（只读采集全流程）与 `scripts/collect_fmql_boot_state.sh`（宽口径只读采集，包含本 A/B 对比所需的启动文件/加载记录枚举）。

## 7. 已知限制

- `read_display_registers_ro.cpp` 无法在 Windows 主机对 `/dev/mem` 实跑；本任务只做了 g++ 语法编译检查（host），板端运行是未来用户步骤。
- 未暴露寄存器的 PLL/reset/PHY/I2C HDMI 芯片状态无法用本工具定位（诚实标注，见 §5 第一句）。
