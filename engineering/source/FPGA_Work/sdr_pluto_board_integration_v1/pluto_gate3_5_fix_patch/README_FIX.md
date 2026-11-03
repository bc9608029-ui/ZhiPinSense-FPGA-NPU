# 补丁说明：Gate 3 板端失败修复 + Gate 4/5 完整审计（pluto_gate3_5_fix_patch）

> 状态：**`READY-FOR-PLUTO-SDR-GATE1-5-RETEST`**（离线验证完成，待用户本人上板复测；
> Gate 1–5 板端全 PASS 前不写 PASS）。本补丁**只改软件**（数据格式/数值映射/状态机/
> 单测/文档），**不碰** RTL / bitstream / 模型 / UI / FPGA-NPU。

## 1. 修了什么

上板实测 Gate 1（PASS）、Gate 2（RX-only PASS）后，Gate 3 失败：

```
GATE_RESULT gate=digital_loopback result=FAIL ratio=0.017670 peak=625
short=0 overflow=0 drop=0 disc=0 timeouts=0 (tone_not_detected)
```

**根因（经 libiio 0.26 `channel.c` 源码确认，非猜测）**：AD9364 是 **12-bit 转换器**，
有效位在 16-bit 容器的**高 12 位**（`shift=4`，左对齐）；`iio_channel_convert` 右移 4 位
后符号扩展，**主机 int16 满量程是 ±2048（2¹¹），不是 ±32768**。旧 TX 不走
`iio_channel_convert_inverse`，直接写原始 16-bit 振幅 10000，12-bit DAC 只取高 12 位 →
`10000 >> 4 = 625`。所以 TX 实际发的是 625 而非 10000，回环后单音被噪声淹没，ratio=0.0177
判 `tone_not_detected`。

同时修复了状态恢复的悬垂/顺序风险（旧代码在「删 Device 而 TX 仍引用」的顺序下析构，
use-after-free），并**完整审计了 Gate 4 射频安全、Gate 5 指标维度**，逐项收紧。

详见 `docs/REPORT.md` §9。

## 2. 文件清单（本补丁，完整当前版本，覆盖式安装）

```
sdr_adapter/device_state_guard.hpp       DeviceStateGuard（快照/恢复 RAII，restore 返回 bool）
sdr_adapter/pluto_device.hpp             DataFormatInfo（12-bit/shift/is_fully_defined）+ Fake
sdr_adapter/pluto_device_libiio.cpp      真 libiio：convert/convert_inverse + 数据格式查询
sdr_adapter/pluto_tx.hpp/.cpp            -40 dB 衰减天花板 + 12-bit 振幅（默认 1500）
board_package/board_common.hpp           ÷2048、Goertzel 幅度、restore_report、失败落盘
board_package/board_detect_pluto.cpp     Gate 1：打印 rx/tx_data_format
board_package/board_rx_only.cpp          Gate 2：DeviceStateGuard + 中断检查
board_package/board_digital_loopback.cpp Gate 3：ratio_pos/neg + peak<2048 + 失败落盘
board_package/board_rf_loopback.cpp      Gate 4：-40 dB 天花板 + RX 20 dB
board_package/board_resampler_test.cpp   Gate 5：五维指标分离 + 12-bit 振幅
host_tests/test_pluto_tx.cpp             45 断言（天花板/安全/恢复/12-bit）
host_tests/test_device_state_guard.cpp   状态快照/恢复单测（新增）
host_tests/build_host_tests.sh run_tests.sh run_tests_asan.sh   接线新增单测
contracts/rx_iq_format_contract.md       12-bit ÷2048、I-Q 方向、查询数据格式
contracts/pluto_config_contract.md       状态恢复、-40 dB 天花板、Gate 4 = 20 dB
docs/BOARD_PLUTO_BRINGUP.md              逐门判据更新（peak<2048 等）
docs/REPORT.md                           §9 本轮修复说明
```

## 3. 上板步骤

```bash
cd /path/to/sdr_pluto_board_integration_v1
tar -xzf pluto_gate3_5_fix_patch.tar.gz -C .     # 覆盖到工程树
sha256sum -c SHA256SUMS.txt 2>/dev/null || true   # 可选自校验（本补丁侧车清单）
cd board_package && ./build_on_board.sh g++      # 重新编译（等效 -O2 -Wall -Wextra -Werror）
```

然后**严格按 Gate 1 → 5 顺序复测**（失败即停，见 `docs/BOARD_PLUTO_BRINGUP.md`）：

```bash
scripts/board_detect_pluto.sh          # Gate 1
scripts/board_rx_only.sh --frames 64   # Gate 2
scripts/board_digital_loopback.sh      # Gate 3（本轮修复目标）
scripts/board_rf_loopback.sh --confirm-safe-rf-path   # Gate 4（会发射 RF，先接好衰减/电缆）
scripts/board_resampler_test.sh        # Gate 5
```

## 4. 关键判据变化（本轮）

- Gate 3/4：`peak < 2048`（12-bit 满量程，**不是旧的 32000**）；单音同时打印 `ratio_pos`
  /`ratio_neg`（共轭/I-Q 方向不一致会报告而非掩盖）。
- Gate 4：默认工作衰减 = **-40 dB 天花板**（独立硬限制，绝不高于 -40 dB），先设 -89.75 dB
  安全地板读回确认后再降到工作衰减；RX 手动 20 dB；仍须 `--confirm-safe-rf-path`。
- Gate 5：默认 `--tone-amp 1200 --probe-amp 800`（**12-bit 计数，和 < 2048 防饱和**，不是
  旧的 12000/18000）。
- TX 波形振幅是 12-bit 计数（默认 1500）；**不要用旧 16-bit 10000 的数值判断**。

## 5. 自校验

解包后 `sha256sum -c SHA256SUMS.txt` 全 OK（`pluto_gate3_5_fix_patch.tar.gz` 生成时已做
extract-and-verify 自检）。主机侧 9 套单测 **413/0**、ASan+UBSan 全 PASS、5 个板端门程序
对真 libiio 0.26 编译+链接通过（详见 `docs/REPORT.md` §9）。
