# 真实 RF 采集协议（REAL_RF_CAPTURE_PROTOCOL）

> 任务：十二类调制识别模型 V2 鲁棒性改进 · 阶段十六（真实 RF 采集工具）+ 阶段五 D4
> 生成：2026-10-07。API 只生成采集脚本、校验器、manifest 与用户操作命令，**不接触板卡**；采集由用户本人执行（我禁碰板）。

## 0. 采集目标（规格 §五 D4）

用 UI v3 / Gate 10 十二类信号发生器采集真实 RF，最终评价关键。覆盖：

- 同轴 TX→RX；单 Pluto 双天线（未来第二台 SDR 则加独立发射端）
- 多个中心频率；多个 TX 衰减；多个 RX gain；多个距离；多个方向
- 多个采集日期/会话；多个温度/重新上电条件；每类多个随机 seed

## 1. SigMF 格式与必录元数据

数据保存为 `*.sigmf-data` + `*.sigmf-meta`，I/Q 数据与采集元数据不可分离。

必录（规格 §五，冻结）：

- 类别（12 类权威标签 + 索引）
- seed
- 中心频率
- 采样率
- TX 衰减
- RX gain
- rec_scale
- SDR 序列号
- 同轴 / 天线
- 距离
- 时间（UTC ISO8601）
- 位流 SHA
- 软件版本
- 模型 SHA
- 波形参数（signal 契约 §2）
- 标签来源（golden generator / manual）

## 2. 采集脚本安全（规格 §十六）

`scripts/capture_real_rf_12class.sh` 必须：

- 默认 TX 衰减安全（默认最大衰减，最小发射功率）
- 显式 `--confirm-safe-rf-path`（同轴直连必须显式确认，防止大功率损伤）
- 每类多个 seed
- 保存完整元数据
- 异常停止 TX（fail-closed，出错即关发射）
- SHA 冻结（采集后立即计算并写 manifest）
- 支持同轴和天线两种路径
- 不将标签写入 I/Q 内容（标签只在 meta）

## 3. 采集会话切分（防泄漏）

- 每个「采集会话」= 唯一 session id（时间戳 + 设备序列号 + 配置哈希）。
- 同一 session 的所有样本**必须同 split**（`tools/split_by_session.py` 强制执行）。
- 采集参数矩阵（频率×衰减×gain×距离×方向）变化即视为不同 session。

## 4. 校验与 manifest

- `tools/build_sigmf_manifest.py`：扫描目录，解析 meta，生成 manifest（文件列表 + SHA256 + 元数据摘要）。
- `tools/verify_sigmf_dataset.py`：校验 SigMF 完整性（data/meta 配对、SHA 匹配、必录字段齐全、12 类覆盖、每类每 SNR/配置样本数平衡、标签不写进 data）。
- `tools/split_by_session.py`：按 session 元数据分配 split。
- `tools/check_data_leakage.py`：跨 split 泄漏检测（同 session 不得跨 split；黄金输入不得混入训练）。

## 5. 操作流程（用户本人执行）

1. 确认位流 SHA（权威 `_disable_icap.bit`）、软件版本、模型 SHA。
2. 同轴路径：接好衰减（TX 衰减 ≤ 安全阈值，默认最大衰减），`--confirm-safe-rf-path`。
3. 按参数矩阵逐 session 采集，每类多 seed。
4. 采集后 `build_sigmf_manifest.py` → `verify_sigmf_dataset.py` → `split_by_session.py` → `check_data_leakage.py`。
5. `real_rf_development` 供开发，`real_rf_final_holdout` 只在候选冻结后跑一次。

## 6. 状态红线

- 真实 RF 导入前，最高状态 = `NEEDS-REAL-RF-DATA`。
- 导入但未上板，最高 = `READY-FOR-12CLASS-V2-NPU-HARDWARE-TEST`。
- 未经真实 NPU + 真实 RF 验证，绝不写 `REAL_RF_PASS / FINAL_MODEL_PASS / OOD_PASS`。
- 我禁碰板、禁写 Flash；发射类操作由用户本人执行并确认 RF 路径安全。
