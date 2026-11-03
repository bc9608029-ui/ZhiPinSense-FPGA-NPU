# 纯净生成v2：24帧真实双SDR测试结果

日期：2026-10-26（北京时间）。状态：MEASUREMENT_COMPLETE；冻结判定：CONTINUE。

- 正确：23/24（95.83%）。固定分母24；接收失败/缺帧0。
- 数字基线：23/24；与数字基线逐帧一致22/24。
- RF新增错误：source_index=23，GMSK（class22）→256QAM（class16）。
- 数字原有错误：source_index=21，AM-DSB-SC（class20）数字直送预测256QAM（class16）；本轮RF恢复后正确识别为AM-DSB-SC。
- NPU：192次推理，apply=1，reset=191，discipline=1。
- TX和RX参数恢复记录均为空错误列表；测试进程已结束。

## 测试合同与完整性

载荷为物理定义修正后的v2纯净生成IQ，不是RadioML HDF5样本，不是S1/S2数据集IQ。24类各一条1024 complex载荷，统一公开帧16384 complex，每载荷重复8次并融合logits。固定尺度68.46059377833956；没有样本触发峰值缩放。RX只收到序号，不收到类别、源IQ、种子、尺度或理想恢复参数。

交接ZIP SHA256与提供值完全一致。电脑测试前冻结审计PASS；板端五个接收文件测试前后SHA全部与frozen_receiver_sha256.json一致。模型JSON/RAW身份核验通过。没有修改模型、恢复器、门限、帧结构或样本集合；未训练、未重建NPU、未进行FPGA迁移。

本机硬盘实际为E盘，F盘为Pluto盘；仅通过既有命令行参数显式指定E盘资产路径。交接指定的D:/radioconda/python.exe在本机不存在，使用现有D:/Miniconda3/python.exe，冻结审计通过。未改脚本默认值。原始结果通过串口压缩传回并核验原始字节SHA，不需要交换登录密码。

## 文件与原始证据

本目录：board_results.json为板端原始结果，expected_private.json为主机私有真值，clean_v2_score.json为原封不动的冻结判分器输出；serial_result_copy.txt记录传回过程；post_test_board_evidence.txt记录后置指纹与NPU纪律；restore.json为TX恢复记录。

板端完整raw IQ、恢复输入、logits、NPU日志已保存在：
/root/amr_clean_v2_results_20261026_rf_01

本轮原始运行目录：/tmp/amr_rescue_run.4waQI8。结果JSON已复制到主机，SHA256：
BEB62C215B94A3BAE3D5571827E856D51C7B2D3B88BE93C5CC4E5A51BF18073C

## 结论边界

本轮达到既定20–24/24的CONTINUE标准，说明冻结通用恢复器在这24条纯净生成波形上也可工作。仅是一轮、每类一条波形、同轴直连、统一公共前导、8窗口融合的测量，不等价于多种种子/码率/SNR、未知无前导信号或空口泛化准确率95.83%。数字与RF同为23/24，但错误样本不同，不能声称RF完全复现数字基线。
