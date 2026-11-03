# fix1 审计笔记（第 1–6 节覆盖 + 诚实缺口）

Token: `M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1`

## 六节覆盖情况

| 节 | 内容 | 交付物 | 状态 |
|---|---|---|---|
| 1 公共协议主验收臂 | 共用同步/训练/帧结构；公共参考估 CFO/定时/增益/IQ；定位 1024 窗口；旧盲采降级 | `radioml_independent_rx_contract.py`（10/10）+ 板端头 | ✅ 离线 |
| 2 幅度合同 | TX 尺度 S / RX 增益 a / 模型归一 1/S 三量分离；删「数字逆变换证明 RF 恢复」 | `contract/*.json/.md` | ✅ 离线 |
| 3 波形正确性 | Hilbert 正交性 / SSB 边带 / WC-SC 载波；发现 F1/F2/F3；历史不变、新增版本 | `radioml_waveform_correctness.py`（7/7）+ json | ✅ 审计 |
| 4 数据对齐与判定器 | 显式分臂源；同源三键；缺失/重复/身份→报错或 INCOMPLETE；label_correct 独立重算 | `judge_radioml_independent_rx.py`（6/6） | ✅ 离线 |
| 5 三层诊断 | 读 C 层实际输入 + 核验 SHA；RMS/DC/corr/residual/预测变化；不自动归因 RF；固定旋转=单数字实验 | replay 三层 + judger | ✅ 离线（C 待板测）|
| 6 交付与验证 | 反例回归 + 保留旧测；依赖 + `make -j1`；诚实 aarch64 标注；重打包 + SHA | `run_regression.py` + `package_fix1.py` + docs | ✅ 离线 |

## 反例回归结果（数字域）

- 公共协议恢复（无固定旋转）：`recovered == orig`，**24/24 无翻转**——修复 blind-clean1
  固定窗口 [512,1536) 旋转导致的 AM-SSB-WC→SC 翻转。
- 固定 512 旋转：**23/24**，唯一翻转 AM-SSB-WC(17)→SC(18)——证明「任意固定旋转只代表
  一个数字实验，不代表真实捕获的未知相位」。

## 波形正确性三处缺陷（只审计，不改历史资产）

- F1 `_hilbert` 返回 `.real`（恒等），非 `.imag`（Hilbert 变换）。
- F2 因 F1，AM-SSB 实为双边带（pos≈neg），非上边带 USB。
- F3 SC 未抑制载波（SSB-SC 载波/边带 +17.92 dB、DSB-SC +25.33 dB），仅调制指数更大。
- 修正须**新增版本**重新生成输入与数字基线，不悄悄替换。

## 诚实缺口

1. **板端 C++ 未 aarch64 编译**（无交叉工具链）；上板前 `make -j1` 原生构建。
2. 板端「counts vs waveform」域以首次构建与 host 数字参考逐字节核验为准。
3. C 层板端模型输入本任务离线不产（无板端通道）；三层诊断的 C 待板测回传。
4. 数字与 RF 同错、无新增翻转时不自动归因 RF；RF 幅度恢复未宣称。
