接收端人工验收：
1. 部署版本及SHA人工记录；保存屏幕、时钟映射、软件版本，确认FIXED 2400MHz。
2. 真实触控：选择FIXED/BAND_SCAN/CONTINUOUS_SCAN，点击START/STOP，记录触控前后截图、GET_TUNING完整回复与applied值；accepted不得作为已生效证据。
3. 范围2395..2405 step1应11点；2396..2404 step2应5点；2395..2405 step0.5应21点；step1.5补终点应8点。核对端点与顺序。
4. start>=stop、step<=0、step>2.304MHz、超过101点必须拒绝且applied不变。
5. TX矩阵默认离线。使用qt_matrix_runner.py --limit 1做离线冒烟；无limit覆盖24类、两个消息库各首末消息、三个频点及三个增益，共864例。完整消息枚举可按需要扩展。只有显式--transmit才设置真实TX；本任务未执行。
6. -50/-60dB仅弱信号诊断，不能默认保证分类准确率。每例保留源SHA、事件QPC、截图、result独立恢复回读；离线恢复为NOT_APPLICABLE。
7. typed_unix_plan.py仅生成命令，不接触任何socket或板卡。传输协议/响应结构尚无依据，必须使用部署版本已验证的typed Unix客户端人工执行、轮询GET_TUNING并验证applied，不能将命令清单视为自动验收通过。
8. 最终STOP，恢复FIXED2400、2395..2405 step1；读取applied并截图。

已验证：Python3.8实际Qt START/STOP离线1例通过，输出session_1793461558999833100。未进行物理触控、RF、网络、板卡、SD或COM8操作。控制台源码未修改/复制。所有输出在本目录。
