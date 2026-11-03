# Linux FPGA Manager 格式审计（PREP2 离线）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
本审计**只读**：只枚举驱动/源码，**绝不试加载文件来验证格式**。结论只阻塞「方案 C（Linux FPGA Manager）」，
不阻塞方案 A（SD BOOT.bin）/ B（U-Boot fpga loadb）。

## 1. 已确认（板端采集，PREP1）

- 驱动名：`FMSH FMQL FPGA Manager`（dmesg：`fpga_manager fpga0: FMSH FMQL FPGA Manager registered`；
  `/sys/class/fpga_manager/fpga0/name=FMSH FMQL FPGA Manager`）。
- 状态：`/sys/class/fpga_manager/fpga0/state=operating`。
- 无 `/dev/xdevcfg` 设备节点；板端无 `fpgautil`。
- `/sys/class/fpga_bridge`、`/sys/class/fpga_region` 存在。

## 2. 未确认（关键缺口 → `FORMAT_NOT_PROVEN`）

- **驱动接受的镜像格式（.bit / .bin / 厂商头镜像）：`FORMAT_NOT_PROVEN`**。
- 本地**没有** FMSH 内核 FPGA Manager 驱动源码（PREP1 `find` 无 `*fpga*manager*` 命中；
  无 `/usr/src` 驱动源码；无 vendor SDK 驱动源码）。
- `modinfo`（内核版本、作者、参数）本地无板端输出（`UNCONFIRMED`，待板端采集）。
- 是否支持全 PL 重配（full reconfig）：`UNCONFIRMED`。
- 加载前是否需要停 NPU/DMA/UI、停的顺序：`NOT_PROVEN`（未确立）。
- 加载后设备重新初始化顺序（NPU/DMA/udmabuf/UI 重绑）：`NOT_PROVEN`。

## 3. 只读采集方式（补证据，不加载）

`scripts/collect_fmql_boot_state_v2.sh` 已含：
- `/sys/class/fpga_manager/*/name|state|firmware|compatible`（只读列出）；
- 驱动模块 `modinfo`（枚举 `/sys/module/*fpga*|*fmql*|*devcfg*`）；
- `/lib/modules/$(uname -r)` 与 `/usr/src` 下 `*fpga*|*fmql*` 源码/模块只读枚举；
- 板端 dmesg 里 FPGA 相关行。

> 若板端 `collect` 后拿到驱动源码路径或 `modinfo` 指明镜像格式，才能把 `FORMAT_NOT_PROVEN` 升级为「已证」。
> 在此之前**不做任何试加载验证**（试加载会改变 PL 配置，属写操作，超出本阶段红线）。

## 4. 结论

- **Linux FPGA Manager 路线 = `FORMAT_NOT_PROVEN`**：驱动镜像格式、停/启顺序、全重配能力均未证实。
- 该缺口**只阻塞方案 C**；方案 A（SD BOOT.bin，FSBL 编程 PL）与方案 B（U-Boot `fpga loadb .bit`，
  vendor 明文流程已证 .bit 可直接载）**不受此缺口阻塞**。
- 主方案若选 A，不得因为「方案 C 未证」而延迟 A 的推进。
