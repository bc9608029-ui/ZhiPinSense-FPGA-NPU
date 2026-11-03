# 十二类 SDR→FPGA/NPU→UI 完整链路 Gate 6–9 交付报告

**项目**：`F:\FPGA_Work\sdr_full_chain_12class_v1`
**任务**：39e5 第二批（Gate 6–9），十二类完整链路离线交付
**状态**：**`READY-FOR-GATE6-9-HARDWARE-TEST`**（未上板，非 PASS）
**日期**：2026-10-06

---

## 1. 交付内容

| 交付物 | 位置 |
|---|---|
| 逐门板端程序 | `board_package/board_gate{6,7,8,9}_*.cpp` + `board_calibrate_rec_scale.cpp` |
| 十二类链核心 | `board_package/chain_common.hpp`（SDR→tensor + ResultFrame） |
| NPU 封装 | `board_package/npu_classifier.hpp`（iCraft-only） |
| 板端构建 | `board_package/build_on_board.sh`、`build_npu_on_board.sh`、`CMakeLists.txt` |
| 模型产物 | `model_12class/model_12class.json/.raw/.sha256` + `MODEL_DEPLOYMENT_CONTRACT.md` |
| 黄金集 | `deployment_golden/`（240 输入 + expected_argmax/logits + manifest） |
| 主机测试 | `host_tests/`（WSL g++ -O2 -Werror，**43/43 通过，零警告**） |
| 运行脚本 | `scripts/run_gate{6,7,8,9}.sh` + `run_calibrate_rec_scale.sh` + `package_board_release.sh` |
| 文档 | `docs/`（本报告 + 板测指南 + 验收 + 定标 + 修正 + 溯源） |
| 清单 | `SOURCE_PROVENANCE_SHA256.txt`（上游冻结）+ `SHA256SUMS.txt`（包自校验） |
| 板端包 | `dist/sdr_full_chain_12class_board_package.tar.gz` |

## 2. 链路与契约

```
Pluto RX(12-bit,FS 2048) → NCO → FIR 抽取(2.56M/3.84M→128k, ×20/×30)
→ receiver_scale(全局固定标量) → fp32 [1,2,1024] → 十二类 NPU(int8 对称 per-channel)
→ logits[1,12] → softmax → ResultFrame(§七) → UI JSONL(§八) → 连续稳定
```

- 类别顺序 FROZEN：`OOK,4ASK,AM-DSB,WBFM,2FSK,GFSK,BPSK,QPSK,8PSK,16QAM,64QAM,OFDM`。
- 模型标签：**`12CLASS_CHAIN_VALIDATION_MODEL`**（通路验证）；OOD = **NO_GO**。
- 模型输入单输入 `[1,2,1024]` fp32，输出 `[1,12]` fp32；128 HardOp@zhuget(330) + 2 host op。

## 3. 主机验证（已做，全部通过）

- `host_tests/build_host_tests.sh` → 编译零警告（-Wall -Wextra -Werror）。
- `host_tests/run_tests.sh` → `test_chain_common`(25/25) + `test_result_frame_v2`(18/18) = **43/43**，
  另加 `test_board_build.sh`（**21/21**）：板端构建依赖修复（无 pkg-config 时 Gate 7 配置路径可用、
  显式 `LIBIIO_ROOT` 时 Gate 6/9 参数正确、`LIBIIO_ROOT` 缺头/库时 fail-closed、路径含空格正确引用、
  `require_libiio_runtime` 运行时检查）+ 板端构建目录隔离修复（`build_gate7/`/`build_gate9/` 互不删除、
  产物自动安装顶层 `bin/`、失败不留旧二进制冒充成功）。合计 **64/64**，零失败零告警。
- 覆盖：契约顺序、张量布局（I 平面/Q 平面、×rec_scale）、receiver_scale 定标、PreprocessChain
  10 kHz 单音过抽取、ResultFrame 填充、UI v2 行 JSON 合法性 / argmax/类自洽 / NaN→null。
- 复用文件一致性：`sdr_adapter/` 与 `board_common.hpp` 除 `result_frame.hpp`、`ui_report.hpp`
  外，均与第一批 `sdr_pluto_board_integration_v1` **逐字节一致**（SHA 核对通过）；
  后两者为 §七/§八 的**纯增量扩展**（`result_frame_v2_line` + 扩展字段，见 §G diff）。

## 4. 未上板（用户本人执行）

- Gate 7/9 依赖 iCraft 运行时（`Device::Open`），仅在 FMQL30TAI 板端可跑；主机未编译该两门
  （iCraft/libiio 不在主机）。
- 板端流程：解包 → `sha256sum -c SHA256SUMS.txt` → 构建 → `bin/` → 严格
  **Gate 6 → 7 → 8 → 9** 逐门（§九定标在 Gate 9 digital/rf 前）。详见 `docs/GATE6_9_BOARD_TEST.md`。

## 5. 措辞红线（严格遵守）

- 未实机验证 → 只标 **`READY-FOR-GATE6-9-HARDWARE-TEST`**，不写 PASS/READY/HARDWARE_PASS。
- 模型不称「最终鲁棒/最终准确率 PASS/OOD PASS」。
- 不碰板、不写 Flash；RF 发射需 `--confirm-safe-rf-path` 且衰减天花板 -40 dB。

## 6. 板端构建依赖修复（2026-10-06）

已确认板端真实环境：**无 pkg-config、无系统 libiio**，libiio 0.26 由用户自行编译在
`/tmp/sdr_pluto_gate1_5/libiio-arm64`（`include/iio.h` + `lib/libiio.so` + `lib/pkgconfig/libiio.pc`）。
据此修复如下，并重新打包：

- `CMakeLists.txt`：删除 `find_package(PkgConfig REQUIRED)` + `pkg_check_modules`；新增
  `option(BUILD_GATE9)`（默认 OFF，Gate 7 单独可配置，不依赖 libiio/pkg-config）；Gate 9 用
  `find_path(iio.h)` / `find_library(iio)` 限定在 `${LIBIIO_ROOT}/{include,lib}`（`NO_DEFAULT_PATH`），
  缺失即 `FATAL_ERROR`；并给 Gate 9 设 `BUILD_RPATH`/`INSTALL_RPATH`。
- `build_on_board.sh`：新增 `LIBIIO_ROOT`（`-I…/include -L…/lib -liio -Wl,-rpath,…/lib`），
  编译前校验 `iio.h`/`libiio.so`，缺失 exit 1；改用 bash 数组以支持含空格路径。
- `build_npu_on_board.sh`：`--gate7-only`（默认，无 libiio）/ `--gate9`（需 `LIBIIO_ROOT`），
  支持 `ICRAFT_CMAKE_DIR`；`--gate9` 缺 `LIBIIO_ROOT` 在调 cmake 前退出。
- 运行时：`scripts/common.sh` 新增 `require_libiio_runtime`，`run_gate6/9` + `run_calibrate_rec_scale`
  调用它，检查 `${LIBIIO_ROOT}/lib/libiio.so` 并设置 `LD_LIBRARY_PATH`，缺失 exit 2，**不回退 Mock**。
- 主机测试：`host_tests/test_board_build.sh`（11 项，见 §3），接入 `run_tests.sh`。
- 权威指南 `docs/GATE6_9_BOARD_TEST.md` 已改为 **不要求安装 pkg-config**，全部用 `LIBIIO_ROOT`。

> 说明：主机无 cmake 二进制，故 CMakeLists 的 configure 无法在主机实际执行，改为静态断言 +
> 逐行审阅 + 用假 cmake 验证 `build_npu_on_board.sh` 的参数传递；`build_on_board.sh` 的 fail-closed
> 与含空格路径均在主机用假 g++ 实测。

## 7. 板端构建目录隔离修复（2026-10-06）

`build_npu_on_board.sh` 原先无论 `--gate7-only` 还是 `--gate9` 都先 `rm -rf build`，第二次构建会删除
第一次的产物。修复如下：

- **目录隔离**：Gate 7 固定 `board_package/build_gate7/`、Gate 9 固定 `board_package/build_gate9/`，
  各自只清理/创建自己的目录，不再共用 `build/`；产物分别为
  `board_package/build_gate7/board_gate7_12class_npu`、`board_package/build_gate9/board_gate9_full_chain_12class`。
- **自动安装**：构建成功后 `mkdir -p <包根>/bin`，把产物复制为顶层
  `bin/board_gate7_12class_npu`、`bin/board_gate9_full_chain_12class`（run 脚本默认在此找）；复制只在
  构建成功且产物存在之后，构建前先删除该 gate 的旧 `bin/` 产物，失败则删除、绝不留旧二进制冒充成功。
- **结果回传**：成功打印 `NPU_BUILD_RESULT gate=7|9 result=PASS binary=<绝对路径>`，失败打印
  `result=FAIL` 并返回非零。
- **依赖修复保留**：Gate 7 无需 libiio/pkg-config、Gate 9 需 `LIBIIO_ROOT`、`ICRAFT_CMAKE_DIR`、
  fail-closed、`BUILD_RPATH`/`INSTALL_RPATH` 全部不变。
- **测试**：`host_tests/test_board_build.sh` 扩展至 21 项（新增目录隔离、顺序构建、失败不删对门、
  失败不冒充、含空格路径等 10 项回归）。
