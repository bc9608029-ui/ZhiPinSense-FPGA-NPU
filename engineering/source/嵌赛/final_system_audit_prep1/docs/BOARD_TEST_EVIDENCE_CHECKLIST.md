# 板测 / 实物验证证据清单

> 用途：对照最终报告 Q3（哪些仍需板测）、Q6（还缺哪些数字/日志/SHA）。每项标证据级别 E1/E1-R/E2/E3/E4（定义见 README §3）。

## A. 已有离线证据（E2，非板测，但支撑结论）

| # | 项 | 证据 | 级别 |
|---|---|---|---|
| A1 | fix10prep3 canonical 包 host 回归 | `f10p3_regression.log` FULL_REGRESSION_EXIT=0，test_fix10_canonical_frame 44/0 | E2 |
| A2 | fix10clean2a 纯净IQ兼容性 | raw24 0.99325 / deployed23 0.99450，host 29 passed | E2 |
| A3 | fix10class24 24类离线资产 | 24/24 全一致 + D2 恢复 corr≥0.999652，离线 16 passed | E2 |
| A4 | fix10clean2b 离线自检 | full `b6e1df3b…` host 全套 + 2 新测试 37/0+18/0 | E2 |
| A5 | fix9 Route F core host 测试 | test_iq_rf_loopback_23class 17/0(93 断言) + 全套件 ALL PASSED | E2 |
| A6 | fix9r2g1 baseline 合同 E2E | test_iq_rf_loopback_fix9r2g1_baseline_e2e 9/9 | E2 |
| A7 | 24→23 合并正确性 | clean2a deployed23 0.99450 + class24 raw24/deployed23 24/24 | E2 |

## B. 真实板测已做但未过 / 未归档

| # | 项 | 结果 | 证据归档 | 级别 |
|---|---|---|---|---|
| B1 | fix10prep3 真实板测（BPSK+4ASK） | training_corr=0.720230 < 0.9 → classification=SKIPPED；payload_training_corr=0.989795（训练块正常）；PC TX-off 空闲超时 + 第二样本未完成 | 板端执行，原始日志未归档到 PC 树，仅任务书记载 | E1-R |

## C. 真实板测待做（用户执行，API 禁碰板）

| # | 项 | 通过判据 | 解锁 |
|---|---|---|---|
| C1 | fix9 Route F 四步复测（23类） | summary.json token=ROUTE_F_23CLASS_ACCURACY_MEASURED（RF 保真全过） | 23 类准确率 + 混淆矩阵 |
| C2 | R8 两样本（fix9r2g1） | BPSK+4ASK，先跑 6 列生成器，--rf-tx-target-rms=2048 | 开放 46 样本 |
| C3 | R9 46 样本 | 回归通过 | ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS |
| C4 | fix10prep3 重跑（修复后） | training_corr≥0.9 + classification 正常 | 解锁 clean2b / 24 类上板 |
| C5 | fix10clean2b Step 6 | scored=2 / prediction_agreement=2/2 / 负对照 PASS / CFO finite·in-range | 写 SMOKE-PASS |
| C6 | AM-SSB WC/SC Phase C/D | 真实板测判别 | WC/SC 归因定案 |
| C7 | UI 真实显示器 | 构建运行+交互+截图 | DESKTOP-GUI-VERIFIED |

## D. 缺的数字 / 日志 / 截图 / SHA（Q6 答案）

1. **fix10prep3 板测原始日志**（training_corr/classification 的板端原始输出，非任务书转述）。
2. **23 类准确率 + 混淆矩阵**（route_f_fix9_summary.json / confusion_23.csv，全树未见）。
3. **UI 真实显示器截图**（offscreen 烟测 ≠ 真实渲染验收）。
4. **包 tarball 完整 SHA 缺口**（自引用不硬编码，树内无逐字 64hex）：fix9r2g1（f2dcc910…/f1c20720…）、fix10prep（508c6bf55c…/57315e2ed6…）、fix10prep2（7d8c8f2f…/999a83ea…）、fix10clean2a（4dc20e82…/c8af2936…）—— 完整值见各自交付消息/打包脚本运行时输出。
5. **12 类/8 类模型完整 SHA**（仅前缀 2ae95275…/c48979b3…，需从原训练包补录）。
6. **fix9r2g1 独立 DELIVERY.txt**（树内缺失，tarball SHA 无记录文件）。
