# B线收敛审查与独立修复（2026-10-30）

原工程未修改，当前整机布线未被停止，未启动第二份整机实现。修复候选位于本目录，不是已通过的整机位流。

## 实际读取的证据

F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/build/m4c_resume_route_smartscan.log：GI2结束elapsed=05:11:39，WNS=-0.812、TNS=-19.985；GI3起始overlaps=760。Route35-447明确报告拥塞。重叠回升不是报错，但不能保证最终收敛。

早期WHS=-0.647、THS=-4767.777；THS是累计负裕量，不是单条路径延迟。DDR IOB_X1Y124到MMCM_X0Y0存在CLOCK_DEDICATED_ROUTE=FALSE/PLCK-23，尚未判定是否原基线就有及其最终影响，不通过新增false_path掩盖。

## 修复1：PSD存储读口

原smart_scan_psd_buffers.sv为两个1024×64数组，组合assign直接索引读出，和注释声称BRAM存在结构矛盾。单维数组本身不保证块RAM推断；同步读口才符合Xilinx块RAM模板。综合日志显示整个工程存在大量RAM32M/RAM64M，但尚不能把全工程这些资源全部归因这个模块，亦未证明它是拥塞唯一根因。

候选smart_scan_psd_buffers.sv：添加ram_style=block，并在clk上升沿寄存两库输出与bank选择，读延迟1周期。不复位数据RAM、不改变1024深度/u54数据/寄存器地址/银行协议。

XSim2018.3实际验证PASS：两银行2048项数据及提交状态正确，读延迟1周期。现有smart_scan_pspl_engine的RD_IDLE发地址、RD_WAIT等待、RD_CAPTURE取数可容纳此延迟，但完整PSPL与数据通路仍需回归，不把局部仿真算整机通过。

本次两版本受限环境OOC综合出现TclStackFree崩溃，日志保留；资源对比结果以最终compare_synth*.log及original/fixed_utilization.rpt为准。没有资源报告就不得声称“已减少多少LUT或已确认BRAM推断”。另一次排除权限影响的小模块运行不等于重新跑整机。

重要：换RTL后必须重新综合/布局/布线，不能拿旧placed检查点继续跑却声称含此修复。旧placed仍代表原网表。可先做独立OOC确认BRAM与资源变化，再决定整机重跑；不能保证新一轮多久收敛。

## 修复2：报告与晋级脚本

原m4c先write_bitstream再出报告；另外get_timing_paths未指定足够路径就累加TNS/THS，不能代表正式汇总。timing查询异常被catch后仍可能继续copy和IMPL_OK。

独立m4c_reports_first_candidate.tcl：route完成先保存routed DCP，查询缺失立即失败，正式TNS/THS取report_timing_summary；生成route_status、check_timing及原报告。故意停在报告审阅门、exit2，不生成/复制位流，也不写IMPL_OK。须独立检查所有报告后再设置明确bitgen步骤，不能把exit2视为布线自然失败。

该Tcl只做静态修改，尚未在整机执行。路径仍指原候选的报告位置，接手者需先改为本轮独立输出，再用于下一次构建；不得在正在执行的脚本上替换。

## 下一步

1. 先确认小模块对比综合结果：原RAM映射、同步修复后RAMB数量和LUT变化，保存报告；如仍工具崩溃，先解决工具运行，不能报PASS。
2. 原整机运行保留为诊断证据，由现有B线负责人统一管理，不再启动重复整机作业。
3. 在独立工程应用已验证读口修复，更新文件SHA，跑现有缓冲/PSPL回归，再决定重新实现。
4. 审查DDR时钟放宽的基线来源、CDC/未约束路径和最终关键路径。无路径证据不改全局clock_groups/false_path，不盲改FFT。
5. 布通+时序+DRC+约束覆盖通过后才生成候选，之后再做Procise处理与板端same-IQ/回退。位流生成不等于RF或系统通过。

所有新文件、仿真、临时目录均在F盘本工作目录；未安装依赖、未下载模型、未操作板子或正式位流。

## 最终小模块对比：已实测完成

在独立F:/FPGA_Work/codex_bram_review_20261030纯英文目录中，Vivado2018.3综合对比成功；原版RAMB=0、总LUT=3061（Logic565/LUTRAM2496）/FF34。修正版RAMB单元=4；具体LUT/FF见fixed_utilization.rpt。两份报告及compare.log已复制到本交接目录。中文工作目录下的TclStackFree失败记录保留，不再把它判定为RTL失败或单纯权限问题。

结论：异步读口导致本模块使用分布式存储的问题已确认，同步读修复已验证BRAM推断和2048项功能；这是可实施的改进，不保证整机拥塞唯一根因或时序必过。尚未合入原正在布线工程，未重新整机综合/实现。

修正版实际资源：总LUT66（Logic66、LUTRAM0）、FF35、RAMB36=2、RAMB18=2；比原模块少2995个LUT。仅代表该模块OOC综合，不是整机资源/布线成绩。
