# 十二类 SDR→NPU→UI 全链路端到端验收标准

本文定义「十二类完整链路（Gate 6–9）」在实机上达到什么才算通过，以及**绝对不许**跨越的措辞
/语义红线。

---

## 1. 链路定义

```
Pluto RX (12-bit, FS 2048)
  → NCO 下变频(可选) → polyphase FIR 抽取(2.56M/3.84M → 128 kHz)
  → receiver_scale(全局固定标量) → fp32 [1,2,1024]
  → 十二类 NPU (int8 对称 per-channel, 128 HardOp@zhuget(330))
  → logits [1,12] → softmax → ResultFrame(§七)
  → UI JSONL(§八, stdout + 可选 UnixSocket) → 连续稳定运行
```

类别顺序（FROZEN）：`OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`。

## 2. 验收门（全部满足）

| 门 | 判据 |
|---|---|
| Gate 6 | 16 帧合法张量，无流异常；数字回环单音通过 |
| Gate 7 | 黄金集 240 条 match_rate ≥ 0.90 |
| Gate 8 | 240 条 UI JSONL 全合法 |
| §九 | rec_scale 稳定（相对变化 <1%） |
| Gate 9 offline | 黄金集→NPU→UI，match_rate ≥ 0.90，全合法 |
| Gate 9 digital | 16 帧活性全过（单音在、无流异常、argmax 在 [0,12)） |
| Gate 9 rf | 同 digital，且显式 `--confirm-safe-rf-path` |
| 稳定性 | 连续运行 N 帧无 SIGBUS / 崩溃 / 流断裂（参照用户实机记录） |

## 3. 语义红线（不可违反）

1. **模型标签 = `12CLASS_CHAIN_VALIDATION_MODEL`**（通路验证模型）。
   禁止写成「最终鲁棒模型」「最终准确率 PASS」「OOD PASS」。
2. **OOD 门 = NO_GO**：源工程 `acceptance.json` OOD gate 未过，本模型**不**声称具备
   分布外鲁棒性；它只验证「SDR→FPGA/NPU→UI」链路通路。
3. **Mock 不得冒充真实**：任何结果只要 `mock=true`，`quality=0`，不算真实推理；Gate 判据
   里无 Mock 回退路径。
4. **阈值不得放宽**：match_rate 0.90、单音 ratio 0.3、频偏 300 Hz 等阈值是冻结值。
5. **未实机验证 = 只能 READY-FOR-...-TEST**：本工程所有交付离线状态只标
   `READY-FOR-GATE6-9-HARDWARE-TEST`，绝不写 HARDWARE_PASS；HARDWARE 侧 PASS 只能由用户
   本人上板逐门验证后签署。
6. **不碰板 / 不写 Flash**：板端运行、JTAG、写 Flash 全部由用户本人执行；本工程不含任何
   写 Flash 或 JTAG 指令。

## 4. 判定记录（用户上板后填写）

| 门 | 结果(PASS/FAIL) | 关键数值 | 日期 |
|---|---|---|---|
| Gate 6 环境 | | frames= short= overflow= | |
| Gate 6 回环 | | ratio_min= | |
| Gate 7 | | match_rate= | |
| Gate 8 | | valid= | |
| §九 定标 | | rec_scale= | |
| Gate 9 offline | | match_rate= | |
| Gate 9 digital | | frames= ratio_min= | |
| Gate 9 rf | | frames= ratio_min= | |

全部 PASS 且稳定性达标后，链路状态方可记为「十二类全链路 HARDWARE 通路验证 PASS（通路，非
最终鲁棒/OOD）」，并注明模型标签与 OOD=NO_GO。
