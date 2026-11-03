# M29-RML24-V2-SAME-CAPTURE-ORACLE-ABLATION1 — 终态判决

状态：`…-DECISION-AFFINE_CORRECTION_INSUFFICIENT_MODEL_DOMAIN_SHIFT_UNRESOLVED`（纯离线）

判决 token：`M29-RML24-V2-SAME-CAPTURE-ORACLE-ABLATION1-JUDGE-AFFINE_CORRECTION_INSUFFICIENT_MODEL_DOMAIN_SHIFT_UNRESOLVED`

## 1. 终态

**AFFINE_CORRECTION_INSUFFICIENT_MODEL_DOMAIN_SHIFT_UNRESOLVED**。

当前真实 RF 载荷差异**无法由窗口、单一复尺度、直流和固定广线性仿射修正充分解释**；
存在更复杂或时变的残余失真。但它**是否唯一主因、微调模型是否仍有效，尚未证明**。

## 2. 五个假设逐条

| 假设 | 证据 | 判定 |
|---|---|---|
| H1 载荷窗/定时误差 | O1（只改窗）agree 不变（fix2 2→2、old 1→1） | **不支持** |
| H2 逐样本尺度缺失 | O2（只改尺度）增益 ≤1（fix2 2→2、old 1→2） | **非主要** |
| H3 合法直流不可恢复 | O3（只改直流）fix2 修回 3 帧（2→5），NRMSE 3.61→0.76 | **次要贡献** |
| H4 固定仿射修正不足 | O5 交叉验证仿射上界 fix2=5/24、old=2/24，远低于 23/24 | **支持（主）** |
| H5 模型 RF 域失配 | 数字基线 23/24 仅证数字 v2 域健康，不能排除 RF 残余失真失效 | **未决（不可排除）** |

H4 与 H5 可同时成立：固定仿射修正不足是已证事实，但它不排除「即便失真可修，冻结模型
对真实 RF 域仍失配」。数字基线 23/24 只覆盖数字 v2 域，不覆盖真实 RF 域。

## 3. 撤回（SUPERSEDED）三条先前结论

1. **「1/24 主要是门控产物」→ 撤回**。强制 O0 仅 2/24 一致（非门控），且交叉验证仿射
   上界也仅 5/24：问题在恢复后残余失真，不在门控。
2. **「接收链残差是唯一硬瓶颈」→ 撤回（细化）**。窗/尺度/直流均可由 oracle 修正，但
   修正后仍 5/24；瓶颈细化为「盲恢复无法观测的载荷内非仿射/时变 RF 失真」。
3. **「不是模型域失配」→ 撤回为「未决」**。数字基线 23/24 只证数字域健康，不能排除
   模型对真实 RF 残余失真失效（H5 UNRESOLVED）。

## 4. 保留结论

- `MORE_RF_DATA_REQUIRED`
- `TRAIN_VAL_TEST_SPLIT_IMPOSSIBLE`
- 暂不正式微调。

## 5. 红线确认

不训练、不碰板、不 SDR、不发射、不改生产恢复/门/协议；24 分母不剔；oracle 不进入生产
恢复；不按标签挑选逐帧最优 oracle；C0(18/24) 未并入 v2 统计；O0 生产 e2e 与强制 O0
分列；NMSE/NRMSE 不与生产门直接比较。
