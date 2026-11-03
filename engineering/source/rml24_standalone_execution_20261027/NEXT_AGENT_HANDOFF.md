# 唯一继续入口：自主接收与五页 UI 测试交接

**2026-10-28 最新用户要求：正式定频240＋扫频240开始前先征求同意；用户随后已明确同意冻结相干平均候选的这两轮RF验证。最新执行目录为 `E:\rml24_repeat_mean_validation_20261028`，授权见APPROVAL.md。用户又要求当前这个240项测试结束后先暂停：完成正在运行的扫频、收齐结果并恢复原服务后，不得再启动修复、部署或其他测试。先读该目录的PAUSE_AFTER_CURRENT_ROUND.md、PROGRESS.json和HANDOFF_RF_VALIDATION.md。不要自动运行旧run_regression.py，不要把历史诊断交接中的“等待批准”当成当前授权状态。**

交接日期：2026-10-28（Asia/Shanghai）。请完整阅读本文件，再按需查阅同目录 `HANDOFF_STANDALONE_TESTS.md` 与 JSON 证据。

## 1. 当前准确状态

`BOARD_FUNCTIONAL_TESTED_PRODUCTION_PROMOTION_PENDING`

本轮定频/扫频独立收发回归已经完成，但**实信号误识别未根治，候选没有正式部署**。
用户明确要求 FPGA 迁移放到后面，长时间稳定性测试也暂不做。不要自行恢复这两项工作。
优先处理真实收发后的分类偏差，以及现有五页 UI 的未完成项。

## 2. 位置与封存包

- 本轮电脑工作目录：`E:\rml24_standalone_execution_20261027`。
- 结果总表：`FINAL_TEST_SUMMARY.json`。
- 详细报告：`HANDOFF_STANDALONE_TESTS.md`。
- 已封存结果/源码包：`E:\rml24_standalone_tests_20261028.zip`。
- ZIP SHA256：`0456856fc3899ec8ee29d96a66aa771ca936642f7c299173dfaa22a25d356cd6`。
- ZIP：2,443,698 bytes，254 个文件，CRC 和包内逐文件 SHA 已验证。

本文件是封存后新增的继续入口，不在上述 ZIP 中；不要为了加入它而悄悄改写封存包或沿用旧 SHA。

## 3. 板子和连接

- 板端：`192.168.126.49`；电脑直连网口：`192.168.126.50`。
- 串口：COM8，115200；用户已登录 root。不要索要或输出密码。
- 电脑 TX Pluto、板端 RX Pluto，同轴 TX→RX；每次重新枚举 USB URI，不硬编码旧 URI。
- 已有串口助手：`E:\scan_exec_20261027\serial.ps1 -Command 'Linux命令' -Seconds 3`。
- 若串口工具占用 COM8，先请用户释放；若出现 `U login:`，请用户自行登录并释放。

## 4. 测试结束时板端状态

**原版已恢复运行**：`rml24-ui`、`rml24-receiver` 当时均 active、enabled。
本轮候选 UI 已停止；测试接收器、纯净输入 NPU 检查均正常退出。
原 `/opt/rml24-system` 和 systemd 启动入口未替换，SD 位流未修改，未加载迁移位流。
所以重启后仍是原版；不能把过去原版冷启动通过，算作本轮五页/脱机候选冷启动通过。
再次操作前重新查询实际状态，不要仅依据本文件认定设备仍在线或进程仍存在。

候选源/板端构建位置：`/root/rml24_standalone_execution_20261027/candidate`。
每轮原始接收 JSONL、NPU 日志在 `/root/rml24_standalone_execution_20261027/<run>/`。
电脑 `board_evidence.json.gz` 是紧凑记录导出，不是完整原始 RF IQ 存档。

## 5. 真实结果与口径

| 测试 | 结果 |
|---|---|
| 定频 2.4 GHz，240 项 | 227/240 = **94.58%**，漏项0 |
| 扫频，TX 2.4036 GHz，240 项 | 232/240 = **96.67%**，漏项0 |
| 纯净输入直接送同一 NPU | **33/33**；其中 AM-DSB-WC 10/10 |
| 软件控制/计分测试 | 10/10 |
| 板端真实控制闭环 | 19/19 |
| 结果审计 | 35/35 |
| 模型/源代码/原入口审计 | 10/10 |
| 五页导航、真实频谱/瀑布/星座 | 用户实屏确认正常 |

这不是任意外部信号无前导盲识别。仍使用固定公共训练帧与冻结模型。
接收器没有 TCP 发射通知、NEXT/READY 握手、类别或逐帧发送通知；仅自主采集、搜索、恢复和推理。
发射时间及真值只在电脑，结束后才用于对齐和计分。

源集合为已有240个波形，24类各10个，SHA全部一致，已与原私有真值逐项核对。
不是新的独立泛化集合。每项取 `[TX开始+1.5s, TX结束-0.3s]` 内第一条捕获；错项和漏项都保留固定分母。
定频每项4秒，扫频每项6秒，均预留40秒初始捕获阶段，间隔0.25秒。保持时间不同，不能据此断言扫频模式本身提升模型精度。
初次有效捕获：定频约0.26秒、正式扫频约9.16秒（从本轮暖机信号开始计算）。时钟初次对齐不确定度约57毫秒。
不能用33/33纯净输入或24项冒烟代替240项真实RF结果，也没有复现历史475/480=98.96%的指标。

## 6. 本轮修改了什么

- 新增自主 `standalone_receiver.py`，不再等待电脑逐帧通知。
- 新增 `standalone_control.py`，提供模式、START/STOP、SET_FIXED_HZ、SET_SCAN_RANGE_HZ、GET_TUNING。
- 调频由接收主线程执行，实际读回后才发已应用确认；失败回退；非法参数不改变已应用值。
- 五页候选已在 aarch64 板端以 `-Werror` 构建；扩展状态解析支持自主接收状态版本。
- 已锁定频点出现一次短暂断流时先重试，连续三次失败才丢锁重扫。

未改冻结模型、two-DC 恢复、公共帧结构、正式样本集合。
公共检测门限0.10、居中后1000Hz校验保持不变。参数：Fs2.56MS/s，BW18MHz，RX手动35dB，TX衰减-40dB。
默认扫2395–2405MHz、步进1MHz；控制允许2300–2500MHz是本轮演示配置，不代表Pluto完整硬件范围。

最初无暖机、一次失败立刻重扫的扫频冒烟 **15/24、漏项9**，已保留失败证据。
增加重试并预留捕获阶段后24项冒烟24/24；条件不同，不能说“模型从15/24提高到24/24”。
完整扫一轮约18秒，首次捕获时间随启动相位变化，尚不能称快速扫频。

## 7. 冻结文件与主要依赖

- 模型板端：`/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16`。
- JSON SHA：`28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42`。
- RAW SHA：`c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151`。
- two-DC SHA：`e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a`。
- receiver_core SHA：`cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a`。
- 本轮自主接收器 SHA：`4448eda5b943ed2f883631f938cd7dfa94bbcc660494ff34d0d9463ffa0ff85e`。
- 全部本轮源冻结值：`RF_SOURCE_FREEZE.json`；板端与原版校验：`BASELINE_AND_SOURCE_AUDIT.json`。
- 科学 Python：`/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3`。
- 旧libiio/公共训练依赖与NPU程序：`/root/amr_rescue_20261025`。
- 模型输入：FP32 planar `[8,2,1024]`，每窗24 logits，8窗平均。

## 8. 未完成项，不能宣称通过

1. 实RF分类偏差未根治：定频13错中8个AM-DSB-WC→AM-DSB-SC；扫频8错中该混淆2个。
2. 屏上定频/扫频频率数字键盘、实际频率与扫描进度显示尚未接入；后端命令通过不等于键盘完成。
3. MEASURE页完整数值接入未完成；预留/“--”不是测量通过。
4. 多信号发现列表、全频段拼接瀑布未实现；当前是当前接收/锁定频点图。
5. 本候选持久自启动、重启和冷启动验收未做。
6. FPGA迁移和长期稳定性按用户要求暂缓。

调查过DC跟踪假设，但源AM-DSB-WC载波主要在±80kHz，不在DC，现有证据不足以确认该根因。
`DC_DIAGNOSTIC_PLAN.md`、shim和diagnostic_tx只是排查准备，**没有部署或执行，没有修改跟踪开关**。
不要把准备好的诊断脚本当成已通过的修复。

## 9. 下一步顺序

1. 先阅读逐项错误、混淆图和纯净NPU对照，保留本轮结果。
2. 针对实收输入偏差做独立、有限的原始IQ/恢复张量诊断；当前记录没有保存每次原始IQ，需要新建诊断轮采集。
3. 不能按真值挑正确帧、按类别设参数或把开发集上的改进当独立验证。任何新候选另建目录、先冻结再测试。
4. 补齐频率输入/进度、数值测量等既定UI缺口，再做相应板端与实屏验证。
5. 回归和功能验收通过后，才考虑替换原自启动，并单独做重启/冷启动；不能先覆盖原版再追认通过。
6. FPGA迁移继续等用户明确安排，不要因为电脑准备包存在就自行加载位流。

## 10. 复测注意与入口

不要盲目重跑 `run_regression.py`：它的固定输出目录已存在，复测必须新建run名，保持旧证据。
不要同时运行原接收器与候选，否则争用Pluto/NPU；UI也不能同时写同一个显示缓冲区。
候选构建：在 `candidate/board_package` 执行 `bash build_ui_live_rml24_final.sh`。
运行命令模板见 `run_regression.py`，模型、legacy、独立UI/控制socket参数均已写全。
`run_standalone.sh` 是有界测试包装，默认60秒；持续运行须显式 `DURATION_SEC=0`，不代表已接入正式启动。
`standalone_delta.tar.gz` 是修复前旧实验；最新差分是 `standalone_delta_final.tar.gz`，完整源码以 `candidate/` 为准。

证据脚本：`collect_evidence.ps1`、`emit_evidence.py`、`score_independent.py`、`audit_results.py`、`audit_baseline.py`。
原版恢复脚本 `restore_baseline.py` 只停止本轮精确UI路径，再启动未修改的原服务；当前已执行成功。
PC上的 `*_tx`、私有真值文件、结果ZIP属于电脑分析资料，不得整包部署给接收器。
