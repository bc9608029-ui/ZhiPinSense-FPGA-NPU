# FPGA迁移本轮实测交接（2026-10-27）

状态：`RTL_SIM_AND_FMQL_STANDALONE_IMPLEMENTATION_VERIFIED_PS_PL_AB_PENDING`。

本轮完成电脑实际RTL仿真、目标FMQL器件的独立综合/实现/内部寄存器时序验证，并保全当前工作系统。**尚未实现并验证真实PS→PL特征适配器，没有新位流下载，没有真实同帧硬件A/B，没有新的识别准确率成绩。**

## 已通过

- 原输入ZIP身份：总交接0429261b02adb92ffbb5150aaabe091ad65aec9bce2dc3f4b0f3fb85d0b77758；FPGA迁移准备包d379a9c11056803ea47fbbc89fde8622d008b42efe4fe4315f5f4af360aa9fb9。
- 软件数值合同5项检查通过；原包11个required_files检查通过，见package_verify.log。
- 冻结19帧、19456样本的实际RTL输出，与参考Power/LagRe/LagIm逐点零差异，帧号和采样序号也全等，见vector_comparison.json与source/tb/results/rtl_features.csv。
- 帧统计基础HDL仿真通过，见xsim_stats.log。
- 联合压力仿真：19456样本/19帧，随机输入空隙、6389次输入背压、6377次特征输出背压、14次统计输出背压；输出在背压期间保持；完整帧计数/Energy/Peak全等；有非零部分帧后复位再跑完整集合。最大Energy=2199023255552（2^41）、Peak=2147483648（2^31）。见xsim_stress.log与source/tb/tb_feature_stress.sv。
- 独立布局测试外壳4例/每例175位完整输出的仿真等价性通过，见xsim_harness.log。

## 真实Procise结果与边界

使用本机D:/FMSH/Procise，Procise2025.1.1 temp SVN32494，器件JFMQL30TAI676H/fcbga676/-2。XSim仅用于通用RTL仿真，未用Vivado资源/时序代替FMQL结果。

| 项目 | 综合 | 布局布线 | 100MHz内部寄存器setup/hold裕量 |
|---|---|---|---|
| frame_statistics原模块 | PASS | PASS | +6.537ns / +0.151ns |
| qam_feature_pipeline原顶层 | PASS | FAIL：258 IO超过250 | 未完成 |
| qam_feature_pipeline＋串行寄存器测试外壳 | PASS | PASS | +5.830ns / +0.108ns |

对应目录：procise_project、procise_qam、procise_qam_harness；保留Tcl、FPE、EDIF、PHY、工具日志和报告。

测试外壳只是为独立实现分析减少顶层封装引脚，原计算模块字节不变。它含额外输入/输出移位寄存器，资源不能当作纯计算模块资源；它不是PS→PL适配器，也不能直接代替整机顶层。没有板卡引脚约束和完整输入/输出延时约束，本轮正裕量只支持当前100MHz内部寄存器路径，不能宣称整机/DDR/CDC/复位时序验收通过。

资源数字见RESULTS_SUMMARY.json中的implementations：工具报告的原模块与外壳分别列出。

## 保留的失败和修复

1. 首次比较直接将包含额外INT8/地址字段的参考CSV与五字段CSV整个字典比较，造成全行不等；修正比较投影后19456样本零差异。旧schema错误记录保留，不是RTL算术失败。
2. 新压力测试台首次触发XSim对混合wire声明的兼容错误；仅修正新增测试台，未改DUT。
3. Procise当前入口不识别.sv，复制成内容完全相同的.v后重试；直接shell展开流程失败，官方create_project/save_project/launch_run流程成功。原失败日志保留。
4. 原QAM顶层独立布局因258/250 IO失败，不是算术资源不足；通过新增独立串行外壳完成寄存器到寄存器实现验证，不修改冻结位宽规避失败。
5. COM8最初报设备错误，用户重插后恢复；用户自行登录并释放串口。未取得或保存密码。
6. 备份网络导出先被自动审批拒绝，后经用户明确授权，只向电脑192.168.126.50提供5个指定文件，导出后临时服务已关闭。

## 备份和当前板状态

板端工作目录：/root/rml24_fpga_execution_20261027。
电脑实际目录：E:/rml24_fpga_execution_20261027。旧交接中的F盘属于此前环境，本轮实际使用E盘；Procise路径是D:/FMSH/Procise。

- baseline_backup/runtime_before.tar.gz：当前/opt/rml24-system、服务和rc.local、两份冻结模型文件、legacy关键代码及npu_stream的文件级备份；SHA b4fab53e1e036fe8246d5758ee02804b54d57263d81171cce79988a5ce03524b。
- baseline_backup/sd_boot_before.tar.gz：SD启动分区只读文件级备份；SHA f4fbd761fe0e3becd6d25a470c060d1d06dfb6a2281fd067e4c494822fced900。
- 两包均在电脑独立读回、检查gzip/tar与关键文件SHA，见baseline_backup/BACKUP_VERIFICATION.json。不是全盘SD镜像，也未备份整个Linux根文件系统。
- 工作download.bit仍为22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9；uEnv为b81563447febf35023b7c99a918bd204270518a87ea9cff169a11fbf26d1f4a9。
- BOOT.bin、Image、two-DC、BF16模型与原服务身份均核对。SD只读挂载已卸载。
- 原rml24-ui.service、rml24-receiver.service仍enabled，结束检查均active。接收器无电脑TX时的原等待/重试行为未改。
- 没有写Flash/SD启动文件、没有下载新bit、没有改生产模型、恢复算法、扫频门限或systemd入口。

## 尚未完成

- integration/目前只有backend_contract.json，并非实际可运行的software/fpga/auto后端与硬件驱动。
- frame_statistics.sv本身不携带帧ID/CRC或帧错误输出；真实适配器还需按合同关联元数据、校验计数并处理超时/错帧。
- 现有接收器的模型张量为float32[8,2,1024]，本次特征合同输入为int16 IQ。旁路量化/缩放/饱和策略与单位须明确冻结；不能悄悄把模型原始输入改成int16，不能按类别定标。
- 旧Mandatory Core整机通路的对外结果包含INT8张量，不能把它当作新合同原始u32/s33逐点回读的完整证据。真实PS→PL回读通路、Energy/Peak寄存器/缓冲接口仍待集成。
- 没有同帧软件/真实FPGA bit-exact、模型输入SHA/预测A/B、实际自动回退或新RF回归。
- 五页UI本轮未板端构建、未显示/触控验收。原五页包的频率命令/数字键盘、多信号列表及宽带拼接瀑布仍待实现，不能只当作几个测试步骤。
- 用户途中表示可以看UI，但本轮未切换五页候选，不能写实屏PASS。以前四页UI通过不等于五页通过。
- 长时间稳定性按用户要求暂不做。新版本重启/冷启动也未做。

## 下一接手入口

先看REMAINING_WORK.md；先补真实适配与数值边界，再做板端A/B，不能跳过门禁直接下载这两个独立模块的设计。当前未生成整机新位流，可随时继续当前原演示系统。之前475/480、464/480和472/480均为历史RF口径，不属于本轮新增成绩。

## 复现提示

- 仿真执行命令保存在xvlog/xelab/xsim各日志中；测试源在source/tb。先运行make_stress_vectors.py生成统计参考，再在source目录编译。xsim.dir仅为可再生模拟器缓存，不纳入交付。
- compare_vectors.py只比较双方都有的5个整数特征字段；别直接比较CSV整行结构。
- Procise用独立新工作目录执行对应run.tcl；不要直接重跑覆盖现有证据。进程环境设置TCL_LIBRARY、ICTIME_HOME、APP_DIR、FMSH_DB到D:/FMSH/Procise相应路径，并将dll、bin加入PATH。
- 板端时钟与电脑日期不一致，保留原始日志时间；本轮归档日期按电脑2026-10-27。
- baseline_backup是恢复资料，整包不作为板端应用部署包。新代码未部署，当前系统无需执行回滚。
