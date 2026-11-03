# AC 实测失败与后续修复交接（2026-10-29）
状态：AC_BUILD_AND_NO_TX_FIXED_PASS_MULTITARGET_RF_FAIL。不是RF_PASS，不得部署或替换自启动。
## 用户目标与范围
先验收AC：依赖、板端构建、UI触控、真实多目标、定频/扫频240回归、回退。保留原FPGA位流和正式版。修复后新240+240开始前须征求用户同意。本轮止于多目标失败，未跑AC正式240+240。
## 唯一输入
E:/嵌赛/HANDOFF_AC_NEXT_TEST_20261029.md；原包E:/嵌赛/rml24_ac_integration_20261029/dist/rml24_ac_integration_candidate.tar.gz，SHA f8e5cbd56995bc886835f7482d1bab4f11170bcfdd974e9ce7d4cc366bc6d5dd。本轮54/54内容SHA通过，原清单CRLF需剥行尾CR再交sha256sum读取。
## 实际目录
电脑E:/rml24_ac_execution_20261029；板/root/rml24_ac_execution_20261029。
板delivery为原归档解包；candidate为复制BASE叠加并修复后的独立候选；launch_scripts为Linux换行兼容启动副本。原delivery/归档/BASE保留不改。
BASE=/root/rml24_standalone_execution_20261027/candidate。
板192.168.126.49，电脑192.168.126.50，COM8/115200。Python=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3。
模型/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16；legacy=/root/amr_rescue_20261025。
## 安装冲突审查与处理
安装器原期望BASE ui_event.py SHA为41c475b040ffa9d69f688cf7e253ddc6746508d20c51e63ff781c273951f9167；实机为be1f0ae7a40d3638d989f543eb581528eeb5d1a7c2e10fc07a52088fd5f76fbb。
已只读回传实机源码board_base_ui_event.py，与E:/rml24_standalone_execution_20261027/candidate/rml24_final/runtime/ui_event.py逐字节同SHA。不是单纯CRLF差异。
AC新ui_event覆盖层增加display_measurements及验证/输出字段。差异见ui_event_diff.txt。
新增install_overlay_compat_verified.sh，仅将已核实旧基线的精确期望改为be1f...，其他6项仍严格核验；原安装器保留。BASE_COMPATIBILITY.json在板端。没有声称找到了41c475原件，也没让任意实测SHA自动通过。
## 严格依赖预检
13冻结Python文件和5BASE依赖均PASS_STRICT；dependency_expect.txt取交接独立期望，不是任意实测抄写：
standalone_control 522aeaaa10d5a7e0472478a088ab04c38855876fcbf4eeb0592800cc52de6799
radio_tuning a6df471b9d69f37334546b436d32eb3aff3f9ea8012027aafd9738c981a323bf
scan_runtime 26d38b8eddbaf299a2e396198e392b3e6e3f618bc97290aeb836f07331ed7a9b
rml24_dualmode_receiver_centered_v2 11061886abbd51d63eb1ac70bd555d06688e0b673759dc46cb475d2161ef2b36
mode_control_server ffd78518c69d6203b137c28111fd2b14b9dbb7d2049b1cf0f4f2ab50bcce23d8
## 本轮修复（原包未改）
1. frequency_control.hpp中if与return同行引发-Werror misleading-indentation：加括号并拆行。
2. 新旧解析器ui::detail::JsonReader重定义：只把target_list_rml24_parse.hpp内部命名空间改为targets_detail。
3. ui_render.cpp未使用draw_kv_row：加C++17 [[maybe_unused]]，不关闭-Werror。
4. Python3.8运行时类型别名list[Any]/tuple[...]报错：multisignal_scan_adapter.py仅PsdDetector/Classifier别名改typing.List/Dict/Tuple，并增加对应import。注解from future不覆盖运行时别名。
5. Linux脚本原包CRLF：创建launch_scripts副本，.sh仅CRLF→LF并chmod，.py保持原字节。原脚本与54文件校验保留。
第4项改变一个冻结源文件，launch_scripts/preflight_deploy.py仅更新对应项为补丁后精确SHA；delivery原预检不改。不得用原包冻结清单宣称补丁树字节未变。补丁前后SHA在板CPP_COMPAT_PATCH.json、CPP_UNUSED_PATCH.json、PY38_TYPE_ALIAS_PATCH.json、LAUNCH_SCRIPT_LINE_ENDINGS.json。
## 已执行结果
- Python编译通过。
- 完整aarch64 UI -O2 -Wall -Wextra -Werror构建通过，build_ui_retry2.log，bin/board_ui_live_rml24_final。
- short_fixed01启动NPU/UI成功，RX因Python3.8别名失败。身份回退停UI/NPU，RX已退出，refused0/failed0；保留失败记录。
- short_fixed02修复后无发射60秒：NPU/UI/RX全部就绪，272条、valid0/rejected272、restore_errors0，rc0；没有有效信号误报。只是无信号短测，不证明RF分类准确率。
- 身份回退日志核实仅停本轮，保留RUN目录，原服务恢复。
- UI扫频ui_scan01有UI_FB_READY，用户确认界面清楚、多目标列表区域存在、五页可切换。AC数字键盘/所有触控尚未全部验收；旧Fix2的确认不算AC本轮通过。
## 真实双频点失败（关键）
TX脚本two_target_tx.py，电脑独立控制唯一TX Pluto；接收端没有类别/时序/频点通知。
原Fs2.56MS/s公共帧各重采样4倍，TX Fs10.24MS/s、LO2401.8MHz，偏移±1.8MHz，两个信号同时位于2400和2403.6MHz。先120秒两路，60秒仅第一路，30秒静默。
源文件03_02.bin SHA1562575bbedd6e815535726f16de6752da0f7441ea609acd3cb2cf6be529c0f8；09_09.bin SHA465def280290eafb0ef659e46b63c11c1c9eba96a66d74487807fe6ba34dd355。
复合波形component峰213.50、乘16前上限2047内，无数字削顶；TX -40dB、BW18MHz。只完成离线源SHA/幅度检查，尚无独立频谱仪验证谱纯度/重采样频谱，所以不能只据此排除发射链影响。
TX最后TX_DONE []，实际发射已结束；计划JSON里rf_started=false是离线生成的遗留字段，不代表未发射，以TX_PHASE与TX_DONE日志为准。
RX实测出现4个候选：约2399.999946、2401.039942、2403.599945、2406.159944MHz（上述数值以Hz日志为准，勿误解单位）；额外候选与真实中心差一个2.56MHz采样率。撤去一路后仍出现约2397.439959、2402.559957MHz等别名候选。
注意：正确单位示例2399999946Hz=2399.999946MHz，2401039942Hz=2401.039942MHz。
用户实屏反馈“目标数或频点异常，或全部missing”。后台targets为空Top3、status missing。整个ui_scan01最终records22、valid0、rejected7、restore_errors0，不能称多目标通过。
UI日志UI_RX type=rml24_targets valid=1，证明事件可解析，不证明目标正确。完整板端RUN保留records.jsonl/ui.log/receiver.log/preflight.log/pids.tsv/run_id/npu.log/rollback.log。
## 已定位的确定代码问题与待验证假设
multisignal_scan_adapter.py：
observe_candidate计算center=LO+CFO，但_observe将_target_lo[target_id]存成发现时lo_hz。
classify_pass/revisit再调到这个原扫描LO，而不是估计中心。冻结恢复器要求正确居中，这是可直接审查的调谐缺陷；尚未修改修复。
sweep只有score门，不做重调谐后的中心验证或恢复确认；相关器CFO存在采样率别名候选，可能造成伪目标，尚未通过独立实验确认每个伪目标唯一根因。
classify_pass遇到_classify_one返回空Top3也调用tracker.classify、记last_classified并出队，可能把恢复失败误当分类完成，需要复核。
step把周期开始now传给长达18–31秒的扫频/分类/重访；last_seen并非实际探测时刻，老化/页面新鲜度需审计。不要未经验证直接说计时问题是唯一根因。
BAND_SCAN记录每周期candidate={}、capture_time在周期结束；现有按逐捕获第一帧计分器可能不能直接复用，须先冻结逐目标逐捕获证据与评分映射，禁止拿周期数作240源计分。
当前候选入口直接infer(frame.tensor)，没有自动使用旧Fix2相干平均包装器；因此旧233/240、237/240不可套用AC。
## 下一位具体顺序
1. 完整阅读本文件及原AC交接，核对当前板端原服务和模型/位流，复制当前候选成新的修复树。
2. 修正中心调谐；补“发现→重调谐→验证公共帧/恢复成功→确认目标”过程与可审计日志，处理失败重试/出队/老化，不能用类别真值过滤。
3. 用构造样本和真实短RF分别覆盖±Fs别名、发现LO偏置、多目标公平重访、撤去一路后老化、选目标清旧数据；先证明两路真实发现与分类，不先跑长回归。
4. 验证独立TX重采样与频谱、单路/双路对照，避免把发射链异常全归因RX。
5. 更新修复候选版本/完整SHA闭包，严格门仍必须检验新冻结身份；原归档与所有失败保留。
6. AC实屏触控完整验收，选中目标的星座/参数必须身份对应，失效清除，不能残留上一目标。
7. 补每次实际接收/推理的时间与目标身份记录，冻结评分合同。再征求用户同意新定频240+扫频240；固定分母、缺失/拒绝/误分类分开。
8. 实测身份回退及原服务恢复。全部通过前不部署、不写SD/Flash、不改自启动，不与FPGA辅助换位流同时做。
## 当前恢复状态
本轮已按完整身份停止ui_scan01：stopped RX/UI，NPU已退出，refused0/failed0；保存multitarget_rollback.log。随后systemctl start原UI/RX并确认均active。TX完成恢复错误[]。没有本轮持续收发，不自动继续正式回归。
## 历史成绩边界
旧Fix2定频233/240、扫频237/240缺0，非AC新成绩；定频原235门槛仍未达。RMS方案开发回放76次退步已否决，不得重新部署。FPGA辅助部分不在本轮，原位流保持。
