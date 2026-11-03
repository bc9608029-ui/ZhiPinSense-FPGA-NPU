# 增广消融（AUGMENTATION_ABLATION）

> 任务：十二类调制识别模型 V2 鲁棒性改进 · 阶段八（增强策略）
> 生成：2026-10-07。所有增强必须做消融，不能一次全部堆入；不得使用会改变真实标签的增强。

## 0. 原则（规格 §八，冻结）

- **逐项消融**，默认不启用任何新增强（V1 既有信道域随机化作为 baseline 保持）。
- 每个候选增强独立开关，单变量对照，评估 delta。
- **不得改变真实标签**：旋转/翻转/共轭等在 AM（AM-DSB）、FSK（2FSK/GFSK）、非对称调制（OOK/4ASK）上必须逐类验证是否改变类别语义。
- 消融在 `synthetic_frozen_test`（D2）与既有 OOD 域上评估，不碰 test/final holdout。

## 1. V1 baseline（对照基，冻结）

V1 训练用 `ChannelPipeline` 域随机化（见 `SYNTHETIC_GENERATOR_CONTRACT.md` §3）：
AWGN(1.0)/Rayleigh(0.10)/Rician(0.10)/multipath(0.12)/CFO(0.55)/phase_offset(0.65)/phase_noise(0.10)/SFO(0.08)/IQ 不平衡(0.12)/DC(0.08)/幅度缩放(0.5)/削顶(0.06)；窄带/突发干扰关闭。

**消融度量口径**：每个候选 vs baseline，报告 `Δ mean_full_macro_f1`、`Δ mean_rated_0_20`、`Δ focus_ood macro_f1_drop`（cfo_strong/multipath/multi_impairment 三个 V1 失败域）+ 训练是否稳定（NaN/收敛）。

## 2. 分组候选（规格 §八）

### A 组：几何与时序
| 候选 | 是否改标签风险 | 说明 |
|------|----------------|------|
| 随机相位旋转 | 低（类不变） | 全类对称 |
| 随机时间平移 | 低 | 记录起点平移 |
| I/Q 交换 | ⚠️ 中 | 等价共轭镜像；须验证不影响 AM/FSK |
| 合法共轭 | ⚠️ 中 | 复数共轭；FSK 相位方向敏感，逐类验证 |
| 幅度缩放 | 低 | V1 已有 amplitude_scaling(0.5)，作为扩展 |
| 时钟偏差/SRO | 低 | V1 已有 SFO(0.08)，扩展 ppm 范围 |

### B 组：信道
| 候选 | 说明 |
|------|------|
| AWGN | V1 已有 |
| Rayleigh | V1 已有 |
| Rician | V1 已有 |
| 多径 | V1 已有（taps 2–4, delay≤10）；扩展更大时延扩展 |
| 随机延迟 | 扩展延迟分布 |
| 频率选择性衰落 | 扩展：更深的频率选择凹口 |

### C 组：硬件
| 候选 | 说明 |
|------|------|
| CFO | V1 已有（±1200Hz）；扩展更强 CFO（对齐 cfo_strong 失败域） |
| IQ gain/phase imbalance | V1 已有（±1dB/±5°）；扩展 |
| DC offset | V1 已有 |
| 非线性压缩 | 新增（PA 非线性） |
| 量化 | 新增（ADC bit 截断） |
| 削顶 | V1 已有 |
| 模拟滤波差异 | 新增（前端滤波器滚降/带内纹波差异） |

### D 组：干扰
| 候选 | 说明 |
|------|------|
| 邻道信号 | 相邻载波的调制干扰（区别于 V1 单音窄带） |
| 窄带干扰 | V1 有实现但关闭（narrowband_interference false） |
| 脉冲噪声 | 突发脉冲（V1 burst_interference 关闭） |
| 部分带内干扰 | 频域部分带内噪声 |

## 3. 消融执行规范

1. 每个候选一个开关，独立开启，其余同 baseline。
2. 训练预算：pilot seed 2026、较短 epoch（如 30），快速淘汰明显失败项。
3. 淘汰标准（pilot）：训练 NaN/不收敛、`Δ mean_full_macro_f1 < -0.02`、`focus_ood drop 增加 > 0.01`（参照 data-v3 pilot gate 的 `max_focus_ood_drop_increase=0.01`）。
4. 通过项进入 Phase A 组合消融（数据混合比例/增强组合/SNR curriculum/类别采样/训练长度/优化器 lr）。
5. 最终结果写入 `docs/PILOT_RESULTS.md` / `docs/FORMAL_RESULTS.md`，记录每项 delta 与置信区间。

## 4. 状态红线

- 消融是训练阶段工作；离线阶段只产出本消融方案与开关框架。
- 不得根据最终测试结果反复修改门限；不得用 test 选择 epoch。
- 我禁碰板、禁写 Flash。
