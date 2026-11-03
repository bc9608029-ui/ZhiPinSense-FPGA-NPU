# Gate 6–9 连续采集 + CLI 双形态解析修复（补丁）

任务 39e5 第二批（十二类 Gate 6–9）两处软件 bug 修复，合并为**一个补丁**
`gate6_9_contiguous_cli_fix_patch.tar.gz`。状态：**`READY-FOR-GATE6-9-HARDWARE-TEST`**
（未上板，**非 PASS**）。

## 1. 触发本修复的板端现象

Gate 6 数字回环板测：`frame01 ratio=0.999989`，随后骤降到 `0.122329`–`0.50`。
信号幅度稳定、频率正确（10 kHz）、RMS 恒定 → **不是 Pluto 硬件故障**，也**不得**
下调 `ratio_min=0.3` 阈值。

## 2. 根因

### 2.1 多次 refill 相位不连续（连续采集根因）

`board_gate6_sdr_preprocess.cpp` 原先以 `chunk=8192` 循环调用 `collect_raw` 拼接，
跨越约 42 次 `iio_buffer_refill`。不同 refill 之间**不能假设相位连续**——相邻 refill
起点相位可跳变（数字回环尤甚），拼接后的流在块边界出现相位台阶，NCO/FIR 后续每帧
单音 Goertzel 检测失效。Gate 9 digital/rf 与定标器同源。

### 2.2 CLI 系统性错误

`board_common.hpp::get_opt` 原先只认 `--key=value`，但 `run_gate6/7/8/9` 与文档都写
`--key value`（空格形式）→ 空格形式被静默忽略，用户参数根本没生效。

## 3. 修复内容（相对板端工程根目录）

| 文件 | 修复 |
|---|---|
| `board_package/board_common.hpp` | `get_opt` 同时支持 `--key=value` 与 `--key value`，**后出现者胜**；缺失/空/非法整数/浮点**失败即停**（`opt_u64`/`opt_d` 抛异常）；新增 `struct Continuity {requested, capacity, refill_delta, single_refill}` 与共享 `capture_contiguous()`（单次大 refill 连续性规则） |
| `board_package/chain_common.hpp` | `PreprocessChain::required_input(frames)`：按 FIR 暂态 + 每帧 1024 输出 + up/down 反推所需输入复数样本数 |
| `board_package/board_gate6_sdr_preprocess.cpp` | 一次算 `requested`，`capture_contiguous` 单次 refill 采全量，整块喂入链一次后抽完整 tensor；PASS 增加 `refill_count delta==1`、`rx_buffer_capacity>=requested`、`single_refill=1`、全帧完整、`ratio_min>0.3`、无 short/timeout/overflow/drop/disc、`restore_result=PASS`；新增输出 `requested_input_complex=/rx_buffer_capacity=/rx_refill_count_delta=/single_refill=`；不跳过失败帧、不取首帧、不下调 ratio 阈值 |
| `board_package/board_gate9_full_chain_12class.cpp` | digital/rf 回环阶段同样单次大 refill（同连续性规则）；**offline 阶段不动** |
| `board_package/board_calibrate_rec_scale.cpp` | 100000 点请求改 `capture_contiguous`，输出 capacity/refill_delta/single_refill，拒绝多 refill RMS |
| `board_package/board_gate7_12class_npu.cpp` / `board_gate8_ui.cpp` | `opt_u64`/`opt_d` 改为 `board::` 命名空间限定（随 CLI 重构） |
| `sdr_adapter/pluto_device.hpp` | `FakePlutoDevice::read_rx` 增加 `rx_timed_out` / `rx_max_capacity` 测试钩子（模拟超时/缓冲上限，主机测试用） |
| `scripts/run_gate6.sh` `run_gate7.sh` `run_gate8.sh` `run_gate9.sh` `run_calibrate_rec_scale.sh` | 全部 `--key value` → `--key=value` |
| `docs/GATE6_9_BOARD_TEST.md` `docs/RECEIVER_SCALE_CALIBRATION.md` | 命令统一为 `--key=value` 形式 |
| `host_tests/test_contiguous_cli.cpp` | **新增**：CLI 双形态/覆盖/fail-closed、Continuity、`capture_contiguous`（ok/缓冲不足/short/timeout）、`required_input==339661`、单 refill 纯 10 kHz 16 帧全 ratio>0.3、多块相位跳变拼接复现低 ratio 且**不得 PASS** |
| `host_tests/test_cli_harness.cpp` + `test_cli_override.sh` | **新增**：端到端证明用户 post 参数覆盖脚本默认、非法值非零退出 |
| `host_tests/build_host_tests.sh` `run_tests.sh` | 加入新测试编译/运行 |

**红线（本次未改，禁止改动）**：`ratio_min=0.3` 阈值、模型/黄金集/类顺序、DSP 滤波
系数与模型输入契约、RTL/位流/UI、Gate 1–5 工程。

## 4. 主机验证（WSL g++ 15.2 -O2 -Wall -Wextra -Werror）

```
test_chain_common        pass=25 fail=0
test_result_frame_v2     pass=18 fail=0
test_restore_semantics   pass=20 fail=0
test_contiguous_cli      pass=61 fail=0
test_board_build.sh      21 passed, 0 failed
test_cli_override.sh     PASSED
run_tests.sh: ALL HOST TESTS PASSED
```

## 5. 板端覆盖与重编译

```bash
# 1) 在已解包的板端工程根目录覆盖（补丁相对路径，直接解包覆盖）
cd sdr_full_chain_12class_v1
tar xzf gate6_9_contiguous_cli_fix_patch.tar.gz

# 2) 自校验（必须全 OK）
sha256sum -c SHA256SUMS.txt

# 3) 重新编译（LIBIIO_ROOT / ICRAFT_CMAKE_DIR 换成你板端的实际路径）
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./board_package/build_on_board.sh
ICRAFT_CMAKE_DIR=/usr/cmake ./board_package/build_npu_on_board.sh --gate7-only
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ICRAFT_CMAKE_DIR=/usr/cmake \
    ./board_package/build_npu_on_board.sh --gate9

# 4) 复制 Gate 6/8/定标产物到 bin/（Gate 7/9 构建已自动装到顶层 bin/）
mkdir -p bin
cp board_package/bin/board_gate6_sdr_preprocess \
   board_package/bin/board_gate8_ui \
   board_package/bin/board_calibrate_rec_scale bin/
```

## 6. 复测要点（判据不变，见 docs/GATE6_9_BOARD_TEST.md）

- 逐门 Gate 6 → 7 → 8 → 9，失败即停；§九定标在 Gate 9 digital/rf 之前。
- **新增 Gate 6/9 digital/rf 判据**：`single_refill=1`、`rx_refill_count_delta=1`、
  `rx_buffer_capacity >= requested_input_complex`，全帧完整，`ratio_min>0.3`，
  `restore_result=PASS`。**任何一项不满足都必须 `result=FAIL` 且退出码非零**。
- `restore_result=FAIL` 仍强制最终 FAIL（延续 restore fix 行为，不回归）。
- RF 发射须 `--confirm-safe-rf-path` + 衰减天花板 -40 dB。

## 7. 状态红线

- 本补丁离线制作、未经板端实机验证，状态 **`READY-FOR-GATE6-9-HARDWARE-TEST`**，**非 PASS**。
- 我（助手）不碰板、不写 Flash；板端覆盖、重编译、复测均由用户本人执行。
