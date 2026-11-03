# 任务6：JTAG 与真板测试流程（准备稿，**不实际下载**）

> 状态：流程已备好；出 bit 前**冻结**。唯一 P0（1 GHz BUFG Min-Period，待 FMSH 确认）解除后才执行第 1 步。

## 阶段 A —— 出位流（当前冻结，勿执行）

1. FMSH FAE 确认 1 GHz 违例处理方案后，重跑完整实现并确认稳定收敛
   （WNS≥0、TNS=0、WHS≥0、THS=0、Routing Error=0、DRC 0 Error）。
2. `write_bitstream`（走官方 `process_control` hook，自动打 USERID 0x00000529 与 REQP-44/46 豁免）。
3. 生成 `pl_ddr_mandatory_core_top_disable_icap.bit`（经官方 `procise_run_disable_icap.tcl`）。

## 阶段 B —— JTAG 枚举与编程（参照已跑通的 ps_pl_ctrl_smoke_v2）

板级 JTAG 链：`arm_dap_0` + `xc7z030_1`（FPGA，JTAG device index = 1）。

```tcl
# 枚举（enumerate_pl_jtag_v2.tcl 逻辑）
open_hw
connect_hw_server
open_hw_target
set_property PARAM.FREQUENCY 1000000 [current_hw_target]
# 期望：HW_CHAIN_DEVICE=xc7z030_1 PART=xc7z030，PROGRAMMABLE_FPGA_COUNT=1
```

```tcl
# 编程（program_*_disable_icap.tcl 逻辑）
program_hw_devices [get_hw_devices xc7z030_1]
# PROGRAM_FILE = fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_disable_icap.bit
# 完成标志：End of startup status: HIGH；PROGRAMMING_COMMAND_COMPLETE
```

> 注意：xc7z030 无 PROGRAMMED 属性，尾随 `[PROGRAMMED] property` 报错可忽略（前次已如此，属非致命）。

## 阶段 C —— 板载 Linux 冒烟（编译见 03_build_linux_smoke.sh）

```bash
# 1) 数据预处理（Windows 侧或板侧）
python 05_tensor_golden_compare.py data/iq_input.hex iq_input.bin

# 2) 板侧编译
./03_build_linux_smoke.sh

# 3) 运行（device-url 与寄存器基址按官方 adder_demo / ps_pl_ctrl_smoke）
./pl_ddr_mandatory_core_smoke \
    "axi://zg330aiu?npu=0x40000000&dma=0x80000000" \
    0x400C0000 \
    iq_input.bin \
    tensor_output.bin
# 期望输出：PL_DDR_MANDATORY_CORE_LINUX_PASS chunk=0x... tensor=0x...
```

判定点（smoke 内已实现）：
- VERSION 读回 == 0x20260929；
- 轮询 STATUS：10 s 内 DONE，且无 ERROR；
- `iq_accepted == 19×1024` 且 `tensor_accepted == 19×1024`；
- 回读 tensor 97280 B 写 tensor_output.bin。

## 阶段 D —— Golden 比对

```bash
python 05_tensor_golden_compare.py tensor_output.bin data/expected_tensor_plddr.hex
# 期望：总字节=97280 mismatch=0，GOLDEN_MATCH
```

任一字节失配会定位到 `(frame, plane, sample)` 并打印前 20 处。

## 阶段 E —— 安全与回退

- 全程只经 `disable_icap` 位流（禁 ICAP 防篡改）；不启用任何 debug core。
- 失败回退：重烧官方预编译 `ai7030_top_disable_icap.bit` 可恢复官方基线。
- 本流程**当前不执行下载**，仅作为 P0 解除后的行动预案。
