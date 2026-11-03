# 三模式与历史记录：本轮测试交接

日期：2026-10-29。唯一入口：本文件 HANDOFF_TEST_RESULTS.md。
当前状态：AUTHORIZED_THREE_MODE_RF_TESTS_COMPLETE_NOT_PROMOTED。

## 1. 结论与边界

用户授权的本轮功能验收、定频240项、搜索锁定240项、连续巡扫24项RF验证已完成。候选未晋级，未覆盖正式程序、未替换自启动、未修改FPGA位流或SD启动文件。原 rml24-ui、rml24-receiver 服务已恢复，最终实查均为 active。

本轮不是FPGA扩展迁移验收；没有新增RTL综合、PS/PL板端bit-exact A/B或新位流验收。没有开展长期稳定性、未见波形泛化或任意无前导信号盲识别验收。

## 2. 正式RF结果

| 运行 | 模式 | 正确/固定分母 | 正确率 | 缺项 | 拒绝 | 类别误判 |
|---|---|---:|---:|---:|---:|---:|
| formal_fixed01 | FIXED | 233/240 | 97.08% | 0 | 0 | 7 |
| formal_lock01 | SEARCH LOCK，协议BAND_SCAN | 235/240 | 97.92% | 0 | 3 | 2 |
| formal_sweep24_02 | SWEEP，协议CONTINUOUS_SCAN | 23/24 | 95.83% | 0 | 1 | 0 |

历史晋级门：定频至少235/240，搜索至少232/240。当前定频233低于235，因此不得自动部署或宣称全面精度回归通过。巡扫24项单列，不能等同240项回归，不能与定频/搜索直接合并计算总准确率。

沿用既有冻结240波形，做新RF采集；不是未见波形泛化。模型、检测门限和帧结构未改。RX不接收PC的发射时序握手或类别真值；PC私有计划/真值只用于事后判分。公共前导及八段重复载荷仍是系统输入合同，不能描述为任意信号盲识别。

## 3. 冻结条件与计分

定频TX 2400 MHz，每项4秒；搜索TX 2403.6 MHz，每项6秒；巡扫TX 2403.6 MHz，每项40秒。共同预热40秒，前后静默8秒，间隔0.25秒。扫频范围2395–2405 MHz、步进1 MHz。

定频/搜索：在发射开始+1.5秒至结束前0.3秒窗口取第一次采集，不允许挑后面正确帧。拒绝和缺项均计错。
巡扫：同一窗口内，取首个发现LO距真实TX中心不超过1.152 MHz的计划驻留机会；按几何覆盖选机会，不按检测成功或预测正确筛选。首次机会失败计错，没有机会计缺项；最终中心误差还须不超过10 kHz。

冻结清单在板端 VALIDATION_FREEZE.json，共174项，清单SHA256：
ea6715f166145e73fd90ba2f49bb7cd73dadf200666a4ddd8be1c9322bab06ef
最后巡扫结束再次核验 VALIDATION_FREEZE_PASS。

## 4. 已完成的功能验收

- aarch64完整UI构建、依赖和模型身份核验通过。
- 五页实屏/触控：CLASSIFY、MEASURE、WATERFALL、CONSTELLATION、SETUP切换正常；真实收发时频谱/瀑布和星座更新，用户确认。
- FIXED、SEARCH LOCK、SWEEP模式切换，STOP/START，以及2401→2400 MHz应用均由用户实屏确认。
- 历史摘要/详情、取消清空/确认清空、自动持久化与损坏文件保留检查通过。当前设计为自动保存，没有SAVE按钮；旧对话里曾误称SAVE，以此为准。
- 独立10条历史夹具：每页5条、NEXT/PREVIOUS、第二页详情返回保持页码和CLOSE由用户确认。夹具不是真实10频点RF采集。
- SWEEP无信号时进度原被NoSignal提前返回遮住；仅调整绘制顺序，用户已确认SCAN x/11出现且循环更新。SEARCH LOCK搜索时也可有进度，锁定后停止完整扫描。
- 搜索失锁再捕获短测：静默阶段无有效结果，恢复发射后约9.99秒得到首个有效结果；这不是全部场景的最大延迟保证。
- 两频点短测覆盖静默→A→B→A+B→A→静默。A约2400 MHz、类别3，B约2403.6 MHz、类别9；有效26次均对应本次两主信号，内部静默阶段有效0，未出现额外有限分类结果。完整巡扫周期实测19.46–32.01秒，中位26.58秒。这是功能短测，不是多目标完整准确率认证。

## 5. 本轮发现和修复的问题

### 显示进度
候选副本 delivery_progressfix1 中仅修UI绘制顺序：先画SCAN进度，再处理NoSignal返回。未修改接收算法或模型。
ui_render.cpp修改后SHA256：895d82efb402319e246ffc903cdae40590e5ccefc919d8864864b9f385a1addd。

### 正常退出被监督程序误判
第一轮 formal_sweep24_01 的24次发射已完成，TX/RX参数恢复无报错，但监督程序在NPU正常EOF退出、RX仍在清理时判为异常。该轮 clean_stop=false，严格判分被阻断；原证据保留，不得追认该轮PASS。

新增独立入口 run_candidate_finalize_v2.py：正常NPU rc=0后，最多等待40秒让RX完成退出；还要求RX正常退出、UI存活、final/restore无错误，并核对NPU帧数=valid×8、apply=1、reset=frames−1、discipline=1。没有放宽分类门限、修改模型或忽略退出错误。
新监督程序SHA256：302b7588634c71c516825195baf963224adb220962b2c3011864c4c9de4ddb91。
先完成20秒无发射短测，再只重跑巡扫24项 formal_sweep24_02；没有重复定频/搜索240项。
最终巡扫：clean_stop=true，finalization_accounting_verified=true，stop_errors=[]，rx_restore=[]；有效捕获72、拒绝捕获406、总记录478，UI发送551/失败0；NPU frames=576 apply=1 reset=575 discipline=1。这里72/406是全部接收记录统计，不是24项正式计分分母。

### 多频点发射工具兼容性
离线科学库缺少np.trapezoid，兼容入口仅别名到np.trapz。四组实际int16发射数组与冻结输入逐点一致。硬件采样率/LO读回存在约1–2 Hz量化差，新兼容入口仅调整读回容差（采样率±2 Hz、LO±5 Hz），不改波形或接收检测条件。不能声称原严格1 Hz读回条件通过。

## 6. 文件位置

电脑完整工作目录：E:\rml24_three_modes_execution_20261029
板端工作目录：/root/rml24_three_modes_execution_20261029
候选源码/构建：板端 delivery_progressfix1/。原 delivery/及candidate.zip保留。
候选输入包SHA256：19724dc5c1360fb4add86825bfc016b362fcbd47bdc68eda3e051d33e97a8173。

主要电脑证据：
- FINAL_RF_AUDIT.json：最终状态与不晋级限制。
- formal_fixed01_score.json、formal_lock01_score.json、formal_sweep24_02_score.json：逐项判分。
- formal_evidence.json.gz：原三轮接收摘要，包含失败巡扫01。
- formal_evidence_v2.json.gz：成功退出的巡扫02接收摘要。
- formal_*_clock.json、formal_*_tx/：时钟偏差、发射私有计划/事件、恢复日志。私有标签仅留PC，不传板端。
- formal_console.log、formal_retry_console.log及各自serial_transcript：完整执行过程。
- FORMAL_PLAN.json、FORMAL_APPROVAL.json、FORMAL_HELPERS_FREEZE.json：原计划、授权、助手冻结。
- SWEEP_RETRY_HELPERS_SHA.json：独立重测助手SHA。
- MULTIFREQ_SWEEP_ANALYSIS.json、SOURCE_RF02_ANALYSIS.json、TX_DEVICE_SAMPLE_COMPARISON.json：多频点证据。
- PAGINATION_ACCEPTED.json、CURRENT_STATUS.json及UI/短测相关脚本：功能验收记录；CURRENT_STATUS可能早于正式测试，最终状态以FINAL_RF_AUDIT为准。
- FORMAL_PROGRESS.json是旧驱动在首次巡扫失败时留下的历史进度，不是当前仍运行；FORMAL_RETRY_PROGRESS.json已显示重测完成。

板端逐帧原记录：formal_fixed01/capture/、formal_lock01/capture/、formal_sweep24_01/capture/、formal_sweep24_02/capture/，以及各运行目录的supervisor.json、rx.log、npu.log、ui日志。板端原始大体积采集不保证包含在本交接ZIP；不要把摘要包当完整原始IQ归档。
板端 SUPERVISOR_FINALIZE_V2.json、PROGRESS_RENDER_FIX.json、VALIDATION_FREEZE.json 为身份和修改证据。
历史文件 formal_history.txt 是本轮候选历史，不替代正式历史。板子时钟日期与电脑不同，不要凭显示日期混淆运行；计分使用每轮clock同步记录。

## 7. 下一位执行顺序与红线

1. 先读本文件和FINAL_RF_AUDIT，校验交接包SHA256及包内SHA256SUMS.json。读板端冻结清单并核验身份；不要直接运行旧的run_formal_validation.py，它会重复全部三轮且使用旧退出检查。
2. 本轮授权测试已经结束，当前无须继续发射。若要新增正式240项回归，按用户既有要求先征求同意；先明确要修的算法和晋级标准。
3. 如诊断剩余错误，优先离线审查逐项判分和接收记录，独立候选开发；保留原证据和全部失败项，不筛掉错误、不修改分母、不按标签挑捕获。
4. 当前不晋级；不得修改正式服务、自启动、位流或SD文件。若用户后续授权部署，需要独立变更/回退方案和部署后验收，不能套用本轮测试结论。
5. FPGA扩展迁移是后续独立任务：应先完成Procise综合与RTL仿真/接口准备，再做同帧软件/FPGA bit-exact A/B和回退验证。当前不能称已完成迁移。
6. 不把本轮UI测试等同新候选部署后冷启动；本轮未新增长期稳定性或冷启动认证。既往正式版冷启动结论也不能自动继承给本候选。
7. 电脑源文件、板端原始证据及冻结外部模型/NPU依赖需要保留；本交接包是结果与执行助手归档，不是可独立安装的完整系统镜像。

建议给下一位的指令：完整阅读本文件，先确认当前正式版本仍运行；本轮测试已结束且候选未晋级。根据用户决定做离线错误诊断或另行准备FPGA扩展，未经授权不重跑正式回归、不覆盖正式版。