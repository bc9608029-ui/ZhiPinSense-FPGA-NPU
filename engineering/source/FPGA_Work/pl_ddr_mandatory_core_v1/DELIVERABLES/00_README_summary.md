# 交付总览（2026-09-30）

阶段：PL DDR + NPU 集成（pl_ddr_mandatory_core_v1）。约束：不生成/不下载 bit、不 waive、不降频、不改 AI_Mate.edif、不改 6 个冻结 Mandatory Core RTL/Golden/固定向量。

## 交付文件（本目录 DELIVERABLES/）

| 文件 | 对应任务 |
|---|---|
| `01_report_inventory.md` | ① 保存 routed DCP + STA/CDC/DRC/PW/route/util 报告 |
| `02_DRC_154_warnings_classification.md` | ② 154 条 DRC Warning 分类 |
| `03_build_linux_smoke.sh` | ③ Linux smoke 编译（iCraft 3.39 + gnu++17） |
| `04_memchunk_verify.md` | ④ MemChunk/64B/77824B/97280B 核对 |
| `05_tensor_golden_compare.py` | ⑤ Tensor 转换 + Golden 比较脚本（已实测可跑） |
| `06_jtag_board_test_flow.md` | ⑥ JTAG + 真板测试流程（不实际下载） |
| `07_1GHz_clock_disable_investigation.md` | ⑦ 1 GHz 时钟能否关闭（结论：不能） |

另保留：`F:\FPGA_Work\pl_ddr_mandatory_core_v1\FMSH_FAE_1GHz_BUFG_MinPeriod_询问.md`（发 FAE 用）。

## 各任务结论

1. **报告**：routed DCP 已保存（55.5 MB）；WNS +0.030 / WHS +0.029 / TNS=THS=0 / Routing Error=0 / DRC 0 Error；pulse-width 报告定位唯一 P0。
2. **DRC 154 条**：官方 vendor IP **90**（NPU 78 + MIG 2 + PS shell 1 + video 9）、用户 frozen_core **62**、meta **2**；**本阶段新增逻辑 0 条**。全为 Warning/Advisory。
3. **Linux 编译**：源码 `pl_ddr_mandatory_core_smoke.cpp` + `pl_ddr_register_map.hpp` 与 iCraft 3.39 头文件/API（`session.h`/`zg330_device.h`/`device.h` 的 `defaultMemRegion/malloc`）逐项对齐；编译在**板载 aarch64** 执行（Windows 无 g++/aarch64 工具链，属预期）。`03_build_linux_smoke.sh` 给出精确 `g++ -std=gnu++17` 命令与库链（ZG330Backend→XRT→XIR→utils + HostBackend）。
4. **MemChunk/对齐/尺寸**：动态地址（XRT malloc）、64B 三层双重校验（malloc 参数 + 软件断言 + 硬件 `[5:0]==0`）、77824 B IQ（19×1024×4，{Q,I} 16-bit）、97280 B Tensor（19×5×1024）全部一致。
5. **Tensor/Golden 脚本**：`05_tensor_golden_compare.py` 已实测：iq 转换 19456 word/77824 B ✅、golden 解析 97280 B（79978 非零）✅；比对时逐字节定位 `(frame,plane,sample)`。
6. **JTAG/测试流程**：枚举（arm_dap_0 + xc7z030_1）→ program `*_disable_icap.bit` → 板载 smoke（`axi://zg330aiu?npu=0x40000000&dma=0x80000000` + 0x400C0000）→ golden 比对，全链路预案就绪，未下载。
7. **1 GHz 关闭**：**不能**。PLL PWRDWN 硬接 GND、动态重配接 const0、reset 与 NPU 全局 `sys_rst` 共用（复位即全 NPU 停摆并影响 User_Ddr_*）。故该违例只能等 FMSH 方案。

## 剩余唯一阻塞项（P0）

> **`clk_out1_AI_CORE_CLK_ST_1`（官方 NPU 标称 1 GHz）的 BUFG Min-Period 违例（Required 1.409 ns / Actual 1.000 ns / Slack −0.409 ns）。** 官方未随包提供 timing summary/显式 waiver，可读 vendor hook 无豁免；该时钟在本次集成中仅驱动 1 个 lock 寄存器、无实际 NPU 负载，但属官方固有时钟结构，约束级/配置级均无法消除。需 **FMSH FAE 书面确认**（官方 timing summary / 内部 waiver / 推荐频率）后，再按官方方案处理并重新完整实现、出 bit。

在此之前：不 waive、不降频、不改 EDIF、不改冻结 RTL/Golden、不生成/下载 bitstream。
