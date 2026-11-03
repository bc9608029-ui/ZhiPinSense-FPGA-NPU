from pathlib import Path
import json,re,hashlib,tarfile,gzip
P=Path(__file__).parent
sha=lambda b:hashlib.sha256(b).hexdigest()
B=P/'baseline_backup'
expected_archives={'runtime_before.tar.gz':'b4fab53e1e036fe8246d5758ee02804b54d57263d81171cce79988a5ce03524b','sd_boot_before.tar.gz':'f4fbd761fe0e3becd6d25a470c060d1d06dfb6a2281fd067e4c494822fced900'}
backup={}
for name,digest in expected_archives.items():
 data=(B/name).read_bytes();assert sha(data)==digest
 assert gzip.decompress(data)[:2]!=b'\x1f\x8b'
 with tarfile.open(B/name) as t:backup[name]={'sha256':digest,'bytes':len(data),'members':len(t.getmembers()),'tar_readable':True,'single_gzip':True}
with tarfile.open(B/'sd_boot_before.tar.gz') as t:
 expected={'./BOOT.bin':'ff350477e624c50d2f8180fb4b9130ec7688fbc7ca553412ed7c3dd2a68b31ef','./Image':'ee88eae627df17fdf615b44cb9fc5a7a7a37d2baaa3f21e90d613f48bedf0929','./uEnv.txt':'b81563447febf35023b7c99a918bd204270518a87ea9cff169a11fbf26d1f4a9','./download.bit':'22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9'}
 for n,s in expected.items():assert sha(t.extractfile(n).read())==s,n
 backup['sd_file_hashes']=expected
with tarfile.open(B/'runtime_before.tar.gz') as t:
 targets={'root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json':'28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42','root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw':'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151','opt/rml24-system/rml24_final/recovery/candidate_two_dc.py':'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a','etc/systemd/system/rml24-ui.service':'6ee4461dfae6f1b513e1ae136dc489982ab95318e6aa3b8213654a17e2b8e00e','etc/systemd/system/rml24-receiver.service':'febdfe0940585b56d6725f04fdcad1a8a71b9fd703a3a4bc5fc6493b34229c7e'}
 for n,s in targets.items():assert sha(t.extractfile(n).read())==s,n
 backup['runtime_identity_hashes']=targets
(B/'BACKUP_VERIFICATION.json').write_text(json.dumps(backup,indent=2),encoding='utf-8')
vec=json.loads((P/'vector_comparison.json').read_text());assert vec['pass'] and vec['mismatches']==0
for f,marker in [('xsim_stats.log','TB_FRAME_STATISTICS PASS'),('xsim_vectors.log','PASS tb_qam_feature_vectors samples=19456'),('xsim_stress.log','FEATURE_STRESS_PASS samples=19456 frames=19'),('xsim_harness.log','OOC_HARNESS_EQUIVALENCE_PASS samples=4')]:assert marker in (P/f).read_text(errors='replace'),f
frozen={}
for n,h in [('qam_feature_pipeline','2c8b8543f1ae8819e745e46002fcd250fdbe5ee52ca501b8453e53c0ddb766a7'),('frame_statistics','97a173e11f53c6d020962fb7ed7ca0e5f69dd963d27e2053a0a7055f3c3a93c3')]:
 assert sha((P/'source/rtl'/(n+'.sv')).read_bytes())==h
 assert sha((P/'procise_rtl'/(n+'.v')).read_bytes())==h
 frozen[n]=h
impl={}
for name,folder in [('frame_statistics','procise_project'),('qam_original_top','procise_qam'),('qam_serial_test_harness','procise_qam_harness')]:
 text=(P/folder/'stdout.log').read_text(errors='replace')
 area=re.search(r'the design has (\d+) instances including (\d+) LUTs (\d+) FFs (\d+) CU (\d+) RAMB',text)
 timings=re.findall(r'^\s*Trr\s+(\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+(-?\d+\.\d+)',text,re.M)
 impl[name]={'flow_complete':'FMQL_OOC_PROJECT_FLOW_PASS' in text,'synthesis_pass':'TEST_STAGE_PASS synth' in text,'area':dict(zip(['instances','luts','ffs','cu','ramb'],map(int,area.groups()))) if area else None,'register_timing':{'period_ns':float(timings[-1][0]),'setup_slack_ns':float(timings[-1][1]),'hold_slack_ns':float(timings[-1][3])} if timings else None,'note':'Includes extra serial input/output registers; not a PS-PL adapter.' if 'harness' in name else ''}
assert impl['frame_statistics']['flow_complete'] and impl['qam_serial_test_harness']['flow_complete']
assert not impl['qam_original_top']['flow_complete']
for name in ['frame_statistics','qam_serial_test_harness']:
 assert impl[name]['register_timing']['setup_slack_ns']>0 and impl[name]['register_timing']['hold_slack_ns']>0
board=(P/'board_final_state.txt').read_text(errors='replace');assert 'BOUNDED_BACKUP_SERVER_CLOSED' in board
summary={'status':'RTL_SIM_AND_FMQL_STANDALONE_IMPLEMENTATION_VERIFIED_PS_PL_AB_PENDING','client_date':'2026-10-27','workdir':str(P),'device':'JFMQL30TAI676H','package':'fcbga676','speed_grade':'-2','procise':'2025.1.1 temp SVN32494','simulation_tool':'XSim2018.3, generic RTL simulation only','vector_comparison':vec,'stress':{'samples':19456,'frames':19,'input_stalls':6389,'output_stalls':6377,'stats_stalls':14,'partial_frame_reset_tested':True,'max_energy':2199023255552,'max_peak_power':2147483648,'dut_modified':False},'implementations':impl,'frozen_rtl_sha256':frozen,'baseline_backup':backup,'board_access_restored':True,'baseline_services_unchanged':True,'temporary_backup_server_closed':True,'new_bitstream_generated_or_loaded':False,'ps_pl_actual_ab_completed':False,'automatic_fallback_board_tested':False,'model_input_sha_ab_tested':False,'new_rf_regression_run':False,'fivepage_native_build_done':False,'new_ui_physical_test_done':False,'long_stability_done':False}
(P/'RESULTS_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(P/'README.md').write_text('本轮交接入口：HANDOFF_FPGA_EXECUTION.md\n\n本包是验证证据及回退备份，不是可直接烧录的整机部署包。没有生成或加载新位流。真实PS→PL同帧A/B、自动回退、五页UI和新RF回归尚未完成。\n\n详见RESULTS_SUMMARY.json、REMAINING_WORK.md和baseline_backup/BACKUP_VERIFICATION.json。原始失败尝试及原因均保留。\n',encoding='utf-8')
text='''# FPGA迁移本轮实测交接（2026-10-27）

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
'''
(P/'HANDOFF_FPGA_EXECUTION.md').write_text(text,encoding='utf-8')
remaining='''# 下一阶段顺序

1. 保留本包备份，确认板端现有模型、two-DC和工作位流SHA一致。
2. 明确恢复float IQ到特征int16旁路的固定转换、量纲与饱和规则；原模型float输入字节保持不变。
3. 基于现有官方BSP/整机工程，接入真实Power/Lag和Energy/Peak侧路，设计可回读的原始整数结果、帧ID/计数/版本/错误状态。不得臆造MMIO基址或把INT8张量当u32/s33结果。
4. 实现真实software/fpga/auto后端和驱动，软件保持默认；明确超时、帧号/长度/CRC/设备错误的回退行为。
5. 新整机工程先综合/P&R/完整STA，保留回退位流；先临时加载，不改开机默认。
6. 冻结19帧真板逐点零差异，再做同一真实恢复IQ的软件/FPGA A/B，验证统计、模型输入SHA和预测全等；做异常回退测试。
7. 定频240与两个扫频频点各240的RF回归；不能拿历史成绩代替新版本。独立验收集不得用于继续调参。
8. 补齐五页UI功能后板端构建和实屏触控；参数只显示已验证量，RMS按Energy派生，未经校准不能写dBm。
9. 满足门禁后才切systemd/启动位流，做新版本重启、冷启动及旧版本恢复。
10. 30–60分钟长稳定性仍暂缓，只有用户重新要求才执行。

主要数值/RTL证据：source/rtl、source/tb、source/vectors、source/tb/results、xsim_*.log、vector_comparison.json。
独立实现证据：procise_project、procise_qam、procise_qam_harness、procise_rtl。
默认禁止覆盖：/opt/rml24-system、现有SD启动文件、冻结BF16和two-DC。
'''
(P/'REMAINING_WORK.md').write_text(remaining,encoding='utf-8')
print(json.dumps({'status':summary['status'],'backups_verified':len(expected_archives),'implementations':impl},ensure_ascii=False))