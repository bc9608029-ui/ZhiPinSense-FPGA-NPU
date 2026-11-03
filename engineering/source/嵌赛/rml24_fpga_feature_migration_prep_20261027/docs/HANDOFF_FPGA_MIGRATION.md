# FPGA 特征迁移交接

## 先看结论

这是“可开始 Procise/板端集成”的电脑侧候选，不是已部署版本。最安全的迁移是让 PL 计算 Power/Lag 和帧 Energy/Peak，CPU 只派生 RMS；冻结模型仍吃原始恢复 I/Q，因此不应改变识别精度。

## 复用资产

`rtl/` 中 6 个文件来自既有已验证 Mandatory Core；`evidence/` 是冻结向量。新增 `frame_statistics.sv` 只做旁路统计，不进入模型数据通路。

## 接手顺序

1. 运行 `python scripts/verify_package.py`。
2. 阅读 `contract/feature_migration_contract.md` 与 `docs/BOARDTEST.md`。
3. 在 Procise 建独立工程，先综合两个特征模块并保存报告。
4. 只在逐点零差异和真实 A/B 通过后接正式系统。
5. 最终合入五页 UI：参数页显示 RMS、Peak、Energy、特征后端和延迟。

## 红线

不得修改 two-DC、冻结 BF16、模型输入字节、扫频门限；不得删除软件后端；不得在未验证时覆盖已工作的位流。
