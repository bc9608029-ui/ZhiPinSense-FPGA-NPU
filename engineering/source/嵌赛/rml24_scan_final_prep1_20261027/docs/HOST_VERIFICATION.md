# 主机验证记录

## 结果

- Windows Python：15 个测试定义，14 PASS，1 个 AF_UNIX 测试因 Windows 不提供 `AF_UNIX` 自动跳过。
- WSL Linux：被跳过的 AF_UNIX 两阶段控制协议单独执行 PASS。
- C++：`test_touch4.cpp` 使用 `-std=c++17 -O2 -Wall -Wextra -Werror` 编译并 PASS。
- 完整 UI：在 Stage 7 base + final overlay + 本轮三个 UI 增量组成的干净树中，用原 `build_ui_live_rml24_final.sh` 编译 PASS。
- 固定 TX：默认中心频率下 `build_frame()` 与 Stage 7 原程序输出逐字节相同。
- 历史真实 RF 回放：504/504 公共帧被前端接受，504/504 经粗 CFO 后仍可由冻结 two-DC 恢复；公共分数 min=0.115594、median=0.873988。

## 重要限制

504 份捕获来自已有 Stage 7 定频会话，并用于选择 0.10 公共分数阈值，所以它们是开发回放，不是独立扫频验证。真正的扫频验收必须改变 TX 中心频率，并加入 TX-off 无信号负对照。

## 复跑

```powershell
python -m unittest -v host_tests/test_scan_prep.py
```

Linux/WSL：

```bash
python3 -m unittest -v host_tests.test_scan_prep.ModeControlTests.test_ui_two_phase_protocol
g++ -std=c++17 -O2 -Wall -Wextra -Werror host_tests/test_touch4.cpp -o /tmp/rml24_test_touch4
/tmp/rml24_test_touch4
```

真实采集回放：

```powershell
python -I scripts/replay_scan_frontend.py `
  --captures <EXTRACTED_STAGE7_CAPTURES> `
  --candidate <STAGE7>/recovery/candidate_two_dc.py `
  --out results/realrf_scan_frontend_replay.json `
  --threshold 0.10
```

