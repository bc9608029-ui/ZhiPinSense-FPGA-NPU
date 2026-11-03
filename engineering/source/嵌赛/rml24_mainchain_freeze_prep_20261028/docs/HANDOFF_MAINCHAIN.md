# 主链修复电脑侧交接

本包不修改板端正式版本。它把下一次诊断需要的证据、候选冻结和独立验证判据固定下来。

先运行：

```powershell
python scripts/audit_scores.py F:\rml24_standalone_execution_20261027\formal_fixed01_score.json F:\rml24_standalone_execution_20261027\formal_scan01_score.json --out results/current_score_audit.json
```

新诊断轮取得IQ后用 `analyze_iq_triplet.py`；候选形成后用 `freeze_candidate.py`；独立240+240完成后用 `promotion_gate.py`。判定脚本只输出决策，不会更改systemd或覆盖文件。

当前最重要的未知量是WC/SC真实接收偏差。纯净NPU 33/33只排除了该小样本上的模型执行错误，不能替代RF诊断。
