# 正式模型训练参考

所选24类检查点为rml24_seed2027_best.pt，第50轮，模型参数280584；与部署导出身份一致。训练主工程由SOURCE_MAP.json查找sdr_amr_rml24_ood_v1_1并按restore_tree.py还原。

rml24_base.yaml是基础配置，不能把基础默认学习率当作所选试验值；本检查点历史起始lr为0.0003，weight decay为0.00001，所选试验与检查点元数据见TRAINING_VERIFIED.json。原始RadioML数据集不包含于本包。

浮点离线RadioML测试与BF16部署/真实RF成绩分列，不能直接互换。检查点只用于复核和离线复现；不要自动执行任何历史烧录、发射或部署脚本。
