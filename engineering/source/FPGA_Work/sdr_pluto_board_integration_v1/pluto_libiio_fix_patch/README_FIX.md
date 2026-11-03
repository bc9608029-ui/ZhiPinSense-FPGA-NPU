# Pluto libiio 属性路由修复补丁（Gate 1 修复）

> 本补丁修复板端 Gate 1 实测失败的根因：`GATE_RESULT gate=detect_pluto result=FAIL
> readback_error=pluto: read sampling_frequency failed`。
> **状态：`READY-FOR-PLUTO-SDR-GATE1-5-TEST`（未上板，不写 PASS）。**

## 根因（一句话）

旧 `pluto_device_libiio.cpp` 用 `iio_device_attr_read_longlong(phy_, "sampling_frequency", …)`
读采样率，并把 `rf_bandwidth`/`gain_control_mode`/`hardwaregain` 写到 `cf-ad9361-lpc`
**流通道**、把 `loopback` 当普通设备属性。正确映射是：

- `sampling_frequency` / `rf_bandwidth` / `gain_control_mode` / `hardwaregain`
  是 `ad9361-phy` **控制通道**的 **channel 属性**（RX=`voltage0 output=false`，
  TX=`voltage0 output=true`）；**绝不**用 `iio_device_attr_*`，**绝不**写到流通道。
- `loopback` 是 `ad9361-phy` 的 **debug 属性**（`iio_device_debug_attr_*`）。
- 流设备 `cf-ad9361-lpc` / `cf-ad9361-dds-core-lpc` **只做 DMA**，无控制属性。

属性路由已冻结为可测逻辑 `sdr_adapter/iio_attr_routing.hpp`，并被主机单测锁定。

## 本补丁包含的文件

| 文件 | 改动 |
|------|------|
| `sdr_adapter/iio_attr_routing.hpp` | **新增**：冻结的属性→(target, api) 路由表 |
| `sdr_adapter/pluto_device_libiio.cpp` | **重写**：控制通道/流通道/debug 属性正确路由、RX 缓冲惰性创建、`read_rx` 超时 fail-closed、RX/TX 采样率分开读写、`verify_routing()` |
| `sdr_adapter/pluto_device.hpp` | `DeviceParams` 拆分 `rx/tx_sample_rate_hz`；新增 `get_rx/tx_sample_rate()`；`FakePlutoDevice` 同步 |
| `sdr_adapter/pluto_libiio.cpp` | 同一 bug 修复（RX-only 后端）：`phy_rx_ch_` 发现 + 属性改走 channel 属性 + `try_attr` 打印 errno+字符串 |
| `board_package/board_detect_pluto.cpp` | Gate 1 分开打印 `rx_sample_rate=` `tx_sample_rate=` `rx_lo=` `tx_lo=` `format=` |
| `host_tests/test_attr_routing.cpp` | **新增**：路由表单测（10 路由 + 反向用例，断言无 `kDevice` 路由） |
| `host_tests/build_host_tests.sh` / `run_tests.sh` | 加入 `test_attr_routing` |
| `host_tests/run_tests_asan.sh` | **新增**：ASan+UBSan 全量回归 |
| `host_tests/link_libiio_host_check.sh` | **新增**：主机 x86_64 对真实 libiio 0.26 的编译+链接门 |
| `contracts/pluto_config_contract.md` | §1–3 更正属性映射（控制通道/流通道/debug 属性/RX-TX 分开） |
| `docs/BOARD_PLUTO_BRINGUP.md` | Gate 1 判据改为 `rx/tx_sample_rate` + `rx/tx_lo` 分开 |

## 主机侧已验证（离线，未上板）

- `host_tests/run_tests.sh`：8 套件 **384 断言全 PASS**，`-Wall -Wextra -Werror` 零警告
  （test_all 212 / test_nco 9 / **test_attr_routing 35** / test_receiver_scale 25 /
   test_rx_format 17 / test_resampler 30 / test_sample_rate_negotiate 20 / test_pluto_tx 36）。
- `host_tests/run_tests_asan.sh`：ASan+UBSan 全 PASS，零泄漏/零 UB。
- 两个 libiio 后端（`pluto_device_libiio.cpp` + `pluto_libiio.cpp`）对 **libiio 0.26**
  头文件 `-Wall -Wextra -Werror` 编译通过；5 个板端程序对真实 libiio **链接**通过。
- 既有 `build_libiio_gate.sh` 仍 PASS（mock + 无设备 `device not found` 快速失败）。

## 上板复测步骤（由用户本人执行）

```bash
# 1. 解包本补丁（板端，覆盖同名文件）
tar -xzf pluto_libiio_fix_patch.tar.gz -C /path/to/sdr_pluto_board_integration_v1
sha256sum -c SHA256SUMS.txt        # 解包后自校验，应全部 OK

# 2. 重新编译板端 5 个 Gate 程序（权威 -O2 构建）
cd /path/to/sdr_pluto_board_integration_v1/board_package
./build_on_board.sh g++

# 3. 重跑 Gate 1（枚举 + 身份读回）
cd /path/to/sdr_pluto_board_integration_v1
scripts/board_detect_pluto.sh

# 4. 逐门继续 Gate 2–5（失败即停，勿跳门）
```

Gate 1 判据（PASS）：退出码 0；`GATE_RESULT gate=detect_pluto result=PASS`；
detail 含 `rx_sample_rate=… tx_sample_rate=… rx_lo=… tx_lo=… format=…` 全部读回成功。

## 边界与归属

- 本补丁**只改软件**（属性路由/单测/文档）；**不碰** RTL / bitstream / 模型 / UI。
- 所有板端程序仍由**用户本人**上板运行（本工程作者不碰板、不写 Flash）。
- 未上板前状态只标 `READY-FOR-PLUTO-SDR-GATE1-5-TEST`，**不写 PASS**。
