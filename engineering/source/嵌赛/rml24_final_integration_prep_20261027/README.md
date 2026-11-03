# RML24 最终集成电脑侧准备包

状态：`PC_PREPARATION_COMPLETE_BOARD_INTEGRATION_PENDING`

本目录把已经完成的定频识别、居中扫频、四页 UI 和 SD 断电自启证据收敛为一个最终集成入口。它不覆盖任何历史工程，也不把候选误写为已经部署。

优先阅读：

1. `HANDOFF_FINAL_INTEGRATION.md`：下一位开发者的唯一交接入口。
2. `BOARD_ACCEPTANCE_CHECKLIST.md`：上板后必须逐项完成的验收门。
3. `FEATURE_SCOPE.md`：还应添加什么，以及明确不再添加什么。
4. `INDEPENDENT_VALIDATION_PLAN.md`：最终独立数据集的冻结规则。
5. `RELEASE_MANIFEST.json`：冻结输入包、SHA256 和成绩口径。

电脑侧自检：

```powershell
python -I .\scripts\verify_final_inputs.py
```

通过只表示电脑侧文件、哈希和结果口径一致，不代表新候选已经冷启动、长稳或最终 RF 验收通过。
