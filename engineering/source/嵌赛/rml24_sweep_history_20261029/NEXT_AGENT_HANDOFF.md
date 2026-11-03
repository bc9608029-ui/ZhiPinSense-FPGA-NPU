# 唯一交接：三模式＋10条历史记录候选（2026-10-29）

状态：OFFLINE_IMPLEMENTED_HOST_VERIFIED_BOARD_PENDING。只做电脑侧；没有上板、发射、加载FPGA、修改正式服务或自启动。不是AC成功版本，不是RF_PASS。

## 交付位置

F:\嵌赛\rml24_sweep_history_20261029

- candidate/：独立原生C++ UI和Python接收源码，基于稳定单目标代码及其gapfix/UI2修订，不采用失败AC调度。
- dist/rml24_three_modes_history_candidate_20261029.zip及.zip.sha256：电脑侧交付包（不含模型、外部npu_stream、x86验证二进制或位流）。
- docs/BOARDTEST.md：从上传、原服务核对到构建、启动、短测、恢复的完整步骤。
- docs/DESIGN_AND_LIMITS.md：模式、历史语义、参数、能力边界和B线任务修订。
- previews/main.png、tuning.png、history.png、detail.png：实际C++渲染器生成的1280×720预览；内容是合成演示，非RF成绩。

## 已实现

1. 定频 FIXED：原稳定处理路径。
2. 搜索锁定 SEARCH LOCK（线协议保留BAND_SCAN）：原扫描选择和失锁迟滞，持续信号锁定期间不继续巡扫。
3. 连续巡扫 SWEEP（CONTINUOUS_SCAN）：顺序检查各点，发现→居中重采→公共参考确认→恢复/推理→继续下一点；无永久锁定；扫描进度和最近识别频率/收到结果时间可见。
4. 第一页HISTORY：最近10条、每页5条、两页。10kHz内同频摘要更新而不逐帧刷屏；固定详情副本显示Top3/频率/时间/模式/次数，不显示历史IQ或套用实时参数。清空确认、正常保存和重新加载、损坏文件保护。打开列表是快照，关闭重开刷新。
5. 保留五页；底部星座页简称IQ PLOT，避免原长标签和相邻导航重叠；三模式按钮、数字输入、历史触摸不与模式按钮串触。

## 实测范围

Python主机17项：巡扫9、实际接收入口注入模拟5、监督器反例3。全部通过；模拟Radio/NPU，不是真RF或真实模型推理。Python3.8语法静态检查通过，未在板端3.8运行。

WSL g++15.2：-std=c++17/-O2/-Wall/-Wextra/-Werror历史与模式单测通过，完整UI程序编译通过；真实绘制器输出像素预览。是x86主机ELF，不是aarch64。

真实C++ UI进程＋本地Unix socket：12条合成结果和新模式状态通过，rejected=0，历史保留10条；没有物理触控/HDMI或SDR。日志TOUCH_CONTROL_RESULT FAIL是此无触摸测试未发送控制命令，不代表物理触控已测失败或通过。

two-DC、receiver_core、repeat_mean_candidate三文件SHA与来源一致；模型不在包内，启动时核验冻结JSON28272abc…/RAWc1781aec…。不宣称准确率改善或保持；历史233/240、237/240不是本候选成绩。

## 下一步

完整读BOARDTEST.md。先核对原正式服务ExecStart、原模型/位流与legacy，上传至全新目录、逐文件SHA、aarch64编译、只读预检。再暂停已记录的原UI/RX，使用 scripts/run_candidate.py 前台监督器运行候选；它不改enable、不动位流。先无发射、单信号和UI短测。

多频点TX任务独立交付：F:\嵌赛\rml24_multifreq_tx_validation_20261029；包SHA36dd6007…。其19/19纯数字通过不等于干净双目标RF通过：已知约−28dBc镜像可能被接收器检出。先验TX单/双路频谱和恢复；10秒相位可能不够完整扫描，需按实际耗时冻结时长。不能把TX杂散一律算RX伪目标。

短测通过再安排各模式回归，不自动跑240＋240，不替换正式自启。出错先保存RUN，监督器先停RX再UI/NPU；stop_errors或恢复不明时不强杀后直接开新轮。恢复原先active的服务，原来inactive的不要擅自启动。

## B FPGA辅助

核心FFT/Hann/PSD/PSPL/双缓冲与软件回退任务保留；验收基线改成本候选验收后的三模式稳定版本，增加LO/帧号/时间戳及换频旧帧排除。没有改B代码或位流，也不承诺B接口只需几行修改。先软件验收再换位流。

## 明确没有做

接收AGC/带宽自适应、1/2/4/8重复次数实验、重训/微调、空口/低SNR/干扰/任意协议支持、FPGA实现及正式部署。当前公共帧和固定配置的受控系统定位可成立，不应写任意复杂环境通用。

## 给下一位的一句话

请完整阅读本文件与docs/BOARDTEST.md，用本包独立候选验证三模式和历史功能，保留原正式版本与位流；先短测、先确认TX源，再做RF回归。电脑能做的自主完成，设备操作按用户安排；不要反复询问yes/no，也不要把主机模拟或历史分数冒充本轮板测。遇具体异常保留证据并定位，不能通过删除漏项、改门限或按类别补偿凑成绩。
