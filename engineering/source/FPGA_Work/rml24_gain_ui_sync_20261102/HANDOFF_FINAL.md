# Final deployment handoff / 最终部署交接

状态：SOFTWARE_DEPLOYED_POST_RF_AND_SOFTWARE_RESTART_PASS。

板端当前版本：/opt/rml24-integrated/releases/gain_ui_sync_20261102
原版本保留用于回退：/opt/rml24-integrated/releases/range_20261101
最终源码标识SHA256：d960b668f1298962ec230db661fbcf2f7881206ba49c1ceb4d39dc25518c611b

部署后正式服务验证：定频24/24、巡扫6/6，缺项0；真实巡扫校准已生效。NPU干净退出、软件服务重新启动均通过，接收/NPU/UI均正常。用户实屏确认单份清楚界面和实际RX GAIN，观察值60dB。逐帧UI增益与硬件最终读回一致。FPGA频谱后端保持使用。模型、公共前导、8次载荷重复、2.56MS/s及持久FPGA位流未变；本次软件部署未改SD启动文件或烧写位流。

部署前：校正版巡扫24/24、定频24/24、搜索锁定24/24；最终显示版定频3/3、搜索3/3、巡扫6/6。历史完整定频240/240、搜索238/240及协调调频13/13，仅在实际两阶段源码等价审计证明对应识别路径未变后继承，不是最终源码重新跑过240+240。原巡扫22/24失败保留。来源和SHA见deployment/QUALIFIED_GATES.json、SCOPE_PROOF.json。历史搜索两项误判仍是限制，不宣称全场景100%。

接收增益策略为自动选择后在采集期间冻结，并有ADC余量保护。巡扫模型输入仅对功率0.8..1.25做有限幅度校正，其他能量等级保留；这是一项新内部规则，不是任意外部信号适应保证。全局归一化因纯净240项新增44项错误已否决，未部署。减少重复次数及采样率自适应没有部署。系统仍使用公共前导/公共帧与8次重复，不是任意信号盲识别。

电脑发射入口：E:\FPGA_Work\rml24_range_expansion_20261101\START_TX_CONSOLE.cmd
现已转向新入口：E:\FPGA_Work\rml24_gain_ui_sync_20261102\START_TX_CONSOLE.cmd
原入口备份：deployment/PREVIOUS_TX_LAUNCHER.cmd。更新入口不会自动发射，打开界面也不自动发射。TX核心、worker和帧构建未变，保留旧240个波形及48个新消息波形；新消息仍标注待RF验证。界面区分硬件增益/衰减、dBm和固定数字幅度；RX显示硬件读回，不再写死35dB。

主要证据：deployment/DEPLOYMENT_RESULT.json、PC_DEPLOYMENT_RESULT.json、POST_NUMERICAL_AUDIT.json、post24/SCORE.json、postsweep6/SCORE.json、SCOPE_PROOF.json、QUALIFIED_GATES.json、PHYSICAL_UI_CONFIRMATION.json。回退由software_deploy_gain_ui.py rollback执行并检查硬件干净退出；不可手动清除同一启动周期脏硬件标记。

本版本未做实物断电重开验收，不宣称冷启动或长时间稳定性通过。频率控制仍为驱动扩展70..6000MHz、最多101个扫描点、步进<=2.304MHz；13代表频点不等于全频段所有类别高准确率。本ZIP为执行证据与PC控制台包，板端完整软件已留在当前release及候选目录，Qt依赖复用本机现有deps路径。
