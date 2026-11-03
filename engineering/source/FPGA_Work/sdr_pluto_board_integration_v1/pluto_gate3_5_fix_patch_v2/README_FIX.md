# Gate 3/4/5 修复补丁 v2：逐帧判定 + 单次连续 refill

## 一句话结论

Gate 3 板端报 `FINAL result=FAIL` 是**假 FAIL**：程序把 128 个独立的 1024 点 RX 缓冲块
拼接后跑**一条全长 Goertzel**，块间起始相位不连续 → 全长相干累加相消（`ratio=0.030`），
但离线逐帧分析 `ratio≈0.99998`、`ratio_pass_count=128`、`freq_mean=9998.83Hz`。**信号链路
正常，判定方法错。** 本补丁把判定改为**逐 1024 点帧独立计算**，并让 Gate 5 改为**单次连续
refill**，不降低 `ratio>0.3` 门限。

## 记录（事实，非结论）

- `GATE3_SIGNAL_PATH_CONFIRMED`：数字回环 / I/Q 格式 / TX / RX / 频率**全部正常**。
- `GATE3_AUTOMATED_VERDICT_FALSE_FAIL`：自动判定为假 FAIL（全长拼接相消）。
- **`GATE3=PASS` 暂不标**：仅在逐帧判定补丁上板返回退出码 0 后才标。

## 改动清单（本补丁文件）

| 文件 | 改动 |
|------|------|
| `sdr_adapter/frame_analysis.hpp`（新） | 纯逐帧分析 + 块连续性检测（板端/主机共用） |
| `sdr_adapter/pluto_device.hpp` | `Device` 接口新增 `rx_buffer_capacity()/rx_refill_count()`；`FakePlutoDevice` 实现 |
| `sdr_adapter/pluto_device_libiio.cpp` | `ensure_rx_buffer(capacity)` 按需建/重建，记录 capacity/refill_count |
| `board_package/board_common.hpp` | `run_loopback` 改逐帧判定；新增 `collect_raw_contiguous`；`freq_err_max_hz` |
| `board_package/board_digital_loopback.cpp` | `--freq-err`（默认 300 Hz） |
| `board_package/board_rf_loopback.cpp` | `--freq-err`（默认 300 Hz），复用逐帧判定 |
| `board_package/board_resampler_test.cpp` | `--samples` 默认 4096→1024；单次连续 refill + 证据打印 |
| `host_tests/test_frame_analysis.cpp`（新） | 7 用例 30 断言（随机相位/连续/缺帧/错频/低比值/短 refill/满 refill） |
| `host_tests/build_host_tests.sh` `run_tests.sh` `run_tests_asan.sh` | 接入 `test_frame_analysis` |
| `contracts/pluto_config_contract.md` | §8 新增 RX 缓冲容量 + 逐帧判定契约 |
| `docs/BOARD_PLUTO_BRINGUP.md` | Gate 3/4 逐帧判定、Gate 5 单次 refill + `--samples 1024` |
| `docs/REPORT.md` | §10 记录本修复 + 复测命令 |

## 判据要点（不放松）

- 每帧 PASS = `ratio>0.3`（max(pos,neg)）**且** 频点距 ±10 kHz ≤ `freq_err_max`（默认 **300 Hz**）。
- `global_ratio`（全长 Goertzel）**仅诊断，不参与 PASS**。
- Gate 5：`single_refill=1` 且 `rx_buffer_capacity>=n_in`（`rx_refill_count` 增量 ==1）；短 refill /
  超时 / overflow / drop / discontinuity **fail-closed**。

## 上板步骤

```bash
cd /path/to/sdr_pluto_board_integration_v1
tar -xzf pluto_gate3_5_fix_patch_v2.tar.gz -C .        # 解包覆盖
sha256sum -c SHA256SUMS.txt                            # 自校验全 OK
cd board_package && ./build_on_board.sh g++            # -O2 -Werror 重编译

# 严格按序复测
cd ..
scripts/board_detect_pluto.sh                          # Gate 1
scripts/board_rx_only.sh --frames 64 --out rx_only_raw.bin   # Gate 2
scripts/board_digital_loopback.sh --frames 128         # Gate 3（逐帧判定）
scripts/board_rf_loopback.sh --confirm-safe-rf-path --frames 128   # Gate 4
scripts/board_resampler_test.sh --samples 1024         # Gate 5（单次连续 refill）
```

## 归属

只改软件（逐帧分析/缓冲容量/单测/文档），**不碰** RTL / bitstream / 模型 / UI / FPGA-NPU，
**不写 Flash**；板端程序由用户本人上板运行。
