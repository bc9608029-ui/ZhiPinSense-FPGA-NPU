# FPGA整帧预取候选 Fix3 — 2026-10-31

当前状态：ISOLATED_PREFETCH_DIAGNOSTICS_PASS_NOT_RF_ACCEPTANCE。

## 问题和修改
旧候选在本轮复测：首轮8/8；随后预定8轮中，前6轮通过，第7轮第3项plus37数值失败，驱动rc=0。相对L1误差0.6673076907、峰功率误差0.2483086943、峰bin550而非549。首次失败即停，保留原始结果；不能用后续通过抹掉旧失败。
源码存在DDR数据气泡直接进入realtime FFT的路径。独立候选在窗乘后、FFT前加入完整1024点预取，填满才连续输出；帧间反压，保留TLAST长度错误和原FFT错误标志。模型、窗乘数值、公共RF帧、FFT配置均未修改。
这是一项针对输入连续性的修复假设；现有结果支持候选有效，尚无ILA波形证明旧故障的唯一根因，不能声称完全根因闭环。

## 已执行验收
- 输入气泡、输出连续性、反压保持、两帧数据/TLAST、长度错误和复位RTL仿真通过。
- 独立完整综合、布局布线完成；新增缓存映射1块BRAM。资源门确认原FFT、输入/输出FIFO、PSD双缓冲均保留。
- 最终setup WNS=0.030ns、hold WHS=0.029ns，均无失败端点。保留原NPU两条最小周期违规 WPWS=-0.409ns、TPWS=-0.479ns，严格核验对应端点与旧例外一致；不是完整STA全通过，也不是厂商豁免。
- 厂商转换测试位流SHA256：f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c。
- 两次独立临时加载，固定矩阵8×8=64及16×8=128，共192/192通过。并非192个不同向量，而是固定8向量重复24轮。
- auto模式8/8通过，逐项backend_used=fpga；指定不存在的驱动触发software回退，原因driver_launch_failed。
- 候选位流下零输入NPU存活8/8有限输出；这不是分类准确率测试。
- 每次结束临时恢复原位流，下载状态校验通过，原UI/receiver均恢复active。不写Flash、SD、BOOT或自启动。

## 产物与证据
工作目录：E:\FPGA_Work\smartscan_prefetch_fix3_20261031
最终审计：FINAL_DIAGNOSTIC_RECEIPT.json
收回的摘要/日志及原始PSD SHA：board_evidence.json.gz（不等于完整原始PSD归档）
硬件完整结果仍留板端：
/root/rml24_fix3_1793424504 — 64作业
/root/rml24_fix3_1793424787 — 128作业、auto和fallback
/root/rml24_fix3_1793424983 — 候选NPU存活
旧失败：/root/rml24_resume_20261031_1229/repeat_7/2
电脑旧失败摘要：E:\嵌赛\rml24_parameter_execution_20261030\RESUME_20261031_EVIDENCE.log
候选位流：outputs/smartscan_fix3_candidate/smartscan_fix3_vendor_auto_disable_icap.bit
源码：fft_frame_prefetch.sv、fft_vendor_ip_adapter.sv及fpga/独立工程副本。
日志：phase2/、phase3/、generate_bit_fix3.log、resume_implementation_fix3_checkpoint.log。

旧BUILD_STATUS、DEVICE_STATUS、REVISION_CURRENT为阶段记录，可能包含早期失败或npu_liveness_pending字段；最终完成情况以FINAL_DIAGNOSTIC_RECEIPT.json、phase3/CANDIDATE_NPU_RECEIPT.json及实际日志为准。不得直接重跑旧continue_build.py或continue_device.py，避免重复加载/覆盖现有证据。

## 尚未完成
- 已保存真实RX IQ的扩展same-IQ对照；须先冻结取窗位置和量化比例，记录削顶。
- 新候选尚未接管正式扫频后端；隔离计算通过不等于正式RF链路已使用FPGA。
- 新候选未做24/240 RF、正式定频/搜索/巡扫回归、实屏、冷启动或长期稳定性认证。
- 原位流回退后服务恢复已验证，但本轮未另跑原位流下NPU推理存活检查。

后续优先在独立接收候选中明确接入点和后端真值上报，冻结RF真值映射、输入集合、计分规则及晋级门，再按用户授权推进；不得直接运行旧正式回归入口或自动部署。当前正式版本未替换。