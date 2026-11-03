# 真实 RF 命令草稿（待 FPGA 验收后执行）

**红线状态：本文件是“草稿”，不发射、不碰板。** 这些命令只有在 B 线 FPGA 扫描
验收通过、且主线程授权板测后才执行。执行前用当前板端 CLI 实测口径回填所有
`<占位>`，不得照抄历史包中的旧参数。

依据现有板端 CLI（主链 `standalone_receiver.py`）的参数面起草；多信号扩展点
标注在每条命令的注释里。

## 前提（先满足）

1. FPGA 窗/FFT/模平方/双缓冲 OOC 验收通过（B 线）。
2. 板端 `standalone_receiver`（或合并位流对应版本）已包含多目标 tracker 的
   CPU 侧实现；本线 `src/tracker.py` 是其离线参考。
3. 冻结参数与本线 `src/contracts.py` 一致（fs=2.56 MHz、FFT=1024、bin=2500 Hz、
   扫描跨度/上限 2304000=0.9×fs；步长不设 2500 整数倍限制，按实际整数 Hz 坐标拼接）。

## RX 侧：多信号扫描

```bash
# 扫频（单 SDR 顺序，多目标由 CPU tracker 维护）
./standalone_receiver \
  --legacy-root /opt/sdr/rml24_legacy \
  --npu-socket /run/rml24_npu.sock \
  --out /tmp/rml24_scan_out \
  --initial-mode BAND_SCAN \
  --scan-start-hz <2395000000> \
  --scan-stop-hz <2405000000> \
  --scan-step-hz <1000000> \
  --duration-sec <600> \
  --save-captures
# 期望输出：目标列表（9 字段）追加写 /tmp/rml24_scan_out/targets.jsonl
# 每行一个 TargetRecord；last_seen 为该频点被调谐到的时间
```

```bash
# 停止 / 复位
./rml24_ctl --socket /run/rml24_standalone_control.sock stop
```

## TX 侧：多载波数字域合成（另一 Pluto，一 TX 一 RX）

```bash
# 生成多载波合成波形（本线 src/tx_synth.py 的板端对应物），只生成不发射
python -m rml24_tx_synth \
  --carriers <f1>,<f2>            # 相对 LO 的 offset，单位 Hz，间距>=12500
  --amplitudes <a1>,<a2>          # 可选，默认等功率
  --symbol-rate-hz <8000>         # 公共帧替身符号率（待真实占用带宽回填）
  --out /tmp/rml24_multi_carrier.i16
# 生成后跑频谱审计（src/spectrum_audit.py 板端对应物）确认 guard_ok/PAPR/削顶/IM3

# 上载并发射（仅在 TX 板、且审计通过后）
./rml24_tx_burst --file /tmp/rml24_multi_carrier.i16 --lo-hz <2400000000> --repeat <N>
```

## 顺序（每轮 RF 会话）

1. 先跑 RX 纯噪声 dwell（0 目标）确认虚警 ≈ 0。
2. 上 1 目标 → 2 目标（频率分离 ≥12.5 kHz 且 ≥1 个 scan-step 可分辨）→ 3 目标。
3. 逐轮回填真实：公共帧占用带宽、dwell 实测时长、LO 稳定时间、真实动态范围。
4. 判分：`src/scoring.py` 口径，检出与分类分开，漏项固定计错。

## 阻塞项（未满足前不发射）

- FPGA 验收未过。
- 主线程未授权板测。
- 真实**载荷**波形占用带宽未回填（真实公共前导/尾已核验为满带宽 QPSK，
  见 `docs/OCCUPIED_BW_VERIFICATION.md`；离线 TX 窄带替身不代表真实公共帧）。
- 单 TX 瞬时带宽外的多信号、任意重叠分离：无证据，不承诺，不在此草稿内。
