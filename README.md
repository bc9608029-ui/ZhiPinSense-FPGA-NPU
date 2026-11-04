# 智频感知——智能无线电系统

基于 FPGA、NPU 与 CPU 协同的真实 SDR 调制识别系统。本仓库保存已经核验的工程源码归档，包含正式板端快照、PC 发射控制、模型训练参考，以及有明确状态说明的历史候选。

## 工程入口

- `engineering/FINAL_BOARD_SNAPSHOT_20261102/`：正式板端 release 源码快照。
- `engineering/MULTIFREQUENCY_TX_CANDIDATE_20261102/`：PC 单信号及 2–4 频点发射控制工程；测试状态以目录说明与提交报告为准。
- `engineering/TRAINING_REFERENCE/`：模型训练、网络与所选检查点参考。
- `engineering/LATEST_PC_LAUNCHER_20261102/`：适配移动硬盘盘符的启动器补充。
- `engineering/ADDITIONAL_CANDIDATES_20261103/`：未晋级候选，与正式部署版本区分。
- `engineering/source/`：按 SHA 去重保存的工程历史；原路径与存放位置见 `engineering/SOURCE_MAP.json`。
- `llm_usage.md`：AI 辅助使用范围和人工核验责任。

## 使用说明

先阅读 `engineering/README_提交入口_20261103.md` 与 `engineering/README_源码说明.md`。历史目录不是全部可以直接运行的正式版本。需要恢复原目录结构时，使用 `engineering/restore_tree.py --out <新的目录>`；输出目录须不存在。该操作可能生成较多重复文件。

源码文件身份保留于 `engineering/SHA256SUMS.txt`。本仓库不是操作系统镜像；商业工具、SDK、驱动、原始 RadioML 数据集及采集大文件不随仓库提供。部分 FPGA 工程含供应商依赖及生成网表，使用和传播须遵守原权利人的许可；本仓库没有授予第三方代码额外许可，也未默认采用任何开源许可证。

## 系统范围

支持定频、自动锁定、连续巡扫，以及分类、参数、瀑布图、IQ 散点和历史记录界面。已验证结果应结合各批次的信号格式、频率、增益和版本条件理解，不将演示视频中的置信度当作整体测试准确率。

此仓库当前用于私有保存与比赛工程交付。公开前须再次检查供应商材料、个人信息及传播权限。


## 评审代码导航

先读 [工程阅读入口](engineering/00_评审请先阅读.md) 和 [模块与关键入口](engineering/CODE_GUIDE/MODULE_ENTRY_POINTS.md)。逐文件查询见 [CSV索引](engineering/CODE_GUIDE/FILE_INDEX.csv)，下载后还可打开 `engineering/CODE_GUIDE/FILE_BROWSER.html` 离线搜索。

最终运行链请读 [最终代码位置](engineering/CODE_GUIDE/FINAL_CODE_LOCATIONS.md)。AI使用详细说明见根目录 [llm_usage.md](llm_usage.md)。
