# 本地完整源码归档

本包收录2026年11月2日盘点得到的F盘项目本地源码、工程配置、脚本、测试及开发说明，包含历史候选和被否决方案。它不是全部历史数据集或商业工具安装包，另包含正式板端release导出快照，但不等于完整设备系统镜像。

## 首先阅读

- 最终部署证据：source/FPGA_Work/rml24_gain_ui_sync_20261102/HANDOFF_FINAL.md（若此文件被去重，可由SOURCE_MAP.json检索原路径）。
- 接收恢复：amr_rescue_gmsk_candidate_20261026/candidate_two_dc.py。
- FPGA：smartscan_prefetch_fix3_20261031/fpga 与其Tcl/RTL/XDC；商业IP的使用遵循原厂授权。
- PC控制台：rml24_gain_ui_sync_20261102/pc_console。
- 模型训练：以TRAINING_REFERENCE和sdr_amr_rml24_ood_v1_1相关源码为准，部署对应sdr_rml24_npu_deployment_m29；model_ad_amr_v1保留为历史原始实现。早期8类/23类属于历史版本，不能当作最终24类入口。

## 无损去重

相同SHA文件只保存一份，SOURCE_MAP.json记录每个原始相对路径、存放位置、长度和提交SHA及原始SHA。历史脚本中的本机访问令牌替换为REDACTED_LOCAL_ACCESS_TOKEN_SET_AT_RUNTIME，其他源码保持字节不变；access_token_redacted字段明确标识修改。需要恢复所有原目录时：

    python restore_tree.py --out F:/新的源码还原目录

输出必须是不存在的新目录。原工程保留开发时的绝对路径，换电脑后须按依赖说明配置，不可直接重跑可能连接硬件或烧录的旧脚本。

## 完整性边界

本包已补入从正式板端只读导出并逐文件核验的FINAL_BOARD_SNAPSHOT_20261102/release，共224个非缓存文件。该目录是正式版本依据；本地历史树不能覆盖它。外部两个NPU可执行文件和模型JSON/RAW的板端身份另有串口校验记录；此包仍不是完整操作系统、SDK与启动介质镜像。

排除私钥/凭据、原始IQ/数据集大文件、商业工具安装包、SDK环境、编译缓存、重复二进制和路由检查点。冻结模型raw单独保留；训练数据、商业IP生成与工具链须按原工程依赖取得。没有改动正式代码、模型、位流或服务。

独立RAR测试、解包SHA和文件数由外部CODE_PACKAGE_VERIFICATION.json记录。历史材料中的E盘路径按当前F盘布局定位；未静默改写原源码。
