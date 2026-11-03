# fix1 公共协议 + 幅度合同（第 1/2 节）

Token: `M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1-CONTRACT`

## 第 1 节 恢复公共协议（主验收臂）

所有 24 类共用**同一套**同步/训练/固定帧结构，接收端只用**公共参考**估计
CFO/定时/增益/IQ 补偿并定位 1024 点载荷窗口。旧「无帧盲采 + 固定窗口」降级为独立
反例实验。

公共协议 burst（复用 dualsdr 冻结 `build_burst`，权威 C++ `iq_rf_training_frame.hpp`）：

| 段 | 复样本 | 内容 |
|---|---|---|
| preamble | 1024 | ZC root=1 |
| settling-zero | 1024 | 0 |
| payload-training | 1024 | 16QAM 已知符号，幅度 2896.309（增益/IQ 参考）|
| payload | 53760 | `cyclic_tile(waveform)` 统一 S 量化 |
| guard-zero | 2048 | 0 |
| tail | 1024 | ZC root=3 |
| **总计** | **59904 复 = 119808 int16** | |

接收端（`estimate_public_reference` + `recover_model_input`）：
1. 前导互相关定位 timing offset；
2. 前导两半互相关相位差估 coarse CFO（无歧义 ±2500 Hz）；
3. 去 CFO 相位斜坡；
4. 载荷训练块广线性 LS 拟合 `r ≈ a·x + b·conj(x)`（增益 + IQ 不平衡）；
5. 载荷窗口广线性逆 `x = (conj(a)·r − b·conj(r))/(|a|²−|b|²)`，取 `[:1024]`。

**禁止**读取原始 IQ / 原始 DC / 逐样本尺度 / 标签 / 参考窗口（离线对齐除外）。

## 第 2 节 幅度合同（三量分离）

| 量 | 值 | 含义 |
|---|---|---|
| tx_digital_scale `S` | **117.84922023433009** | = 1600/max_peak，统一类别无关；`ci16 = lround(wf·S)` |
| rx_gain_estimate `a` | 广线性系数 | 训练块已知幅度估计（数字域 a≈1；RF 域 a≈G）|
| model_input_norm `1/S` | **0.008485418893834097** | 统一反缩放；`model_input = wl_inv(payload,a,b)[:1024] · (1/S)` |

`max_peak = 13.576670230134553`（AM-SSB-WC seed 3000017）。数字基线与 RF 输入使用
**同一**公共类别无关规则（统一 S / 1/S，不再是 dualsdr 的 per-class
`tx_scale=2048/native_rms`）。

**已删除**论证：「数字量化逆变换证明 RF 幅度已恢复」。诚实边界：
- 数字域 a≈1、b≈0 只证明「TX → 模型归一化链路自洽」，**不**证明 RF 模拟增益 G 已恢复；
- RF 路径 G 是否由公共参考估计 a≈G 成立，须板端训练块残差单独核验；
- 固定 512 旋转 = 单个数字实验（反例），不代表真实捕获的未知相位。

## 同源绑定（第 4 节，在此固化）

`source_id = fix1-public-protocol-24waveforms`，`conversion_version = v1`，三键绑定 =
`source_id + conversion_version + model_input_sha256`。`source_index` 显式 ==
`class_index + 1`（不 shuffle，不冒充原始 480 帧配对）。
