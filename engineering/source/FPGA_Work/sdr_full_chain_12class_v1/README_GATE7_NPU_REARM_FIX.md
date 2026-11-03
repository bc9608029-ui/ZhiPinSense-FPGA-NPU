# Gate 7 十二类 NPU 固定一帧延迟修复（补丁）

任务 39e5 第二批（十二类 Gate 6–9）。板端 `--diagnostic` 抓到的决定性证据：
**ZG330 固定一帧陈旧输出**——sample1 重复 sample0 的完整 logits、sample2→pred1、
sample3→pred2、…、sample12→pred11，混淆矩阵整体严格向前错一帧，2880/2880 logits
有限无 NaN/Inf。这不是模型、布局、量化或黄金集问题。

本补丁按 `npu_realtime_v1` 板上已验证的机制修复（12/12、delay shift 0/10）。
状态：**`NEEDS-GATE7-NPU-REARM-FIX`**（未上板复测，**非 PASS**）。

## 1. 根因

iCraft 3.39 的 ZG330 后端 `Session::forward()` 是异步的：`waitForReady()` 轮询的
FPGA 完成状态**按 Device 单调递增**，只在 `Device::Open`（初始化）或
`Device::reset` 时重新武装。旧的 `npu_classifier.hpp` 每帧新建一个 Session 并
`apply()`，但 **Session 重建并不会重新武装 Device 的 FPGA 完成状态**——于是除首帧外
每次 `waitForReady()` 都立即返回「已完成」，读回的是**上一帧**的输出。这就是
Gate 7 `matched=3/240`（低于随机 8.3%）的直接原因。

## 2. 修复内容

### 2.1 `board_package/npu_classifier.hpp`（核心）

与 `npu_realtime_v1/board_package/npu_realtime.cpp` 的 `reset1` 机制逐条对齐：

| 项 | 旧（错误） | 新（修复） |
|---|---|---|
| Device | 打开一次 | 打开一次（不变） |
| Session | **每帧新建 + apply()** | **持久一个，apply() 一次** |
| 首帧 | forward | forward（**不 reset**，硬件刚初始化） |
| 第 2 帧起 | forward（陈旧） | **`Device::reset(1)` 后 forward** |
| reset(1) 后 | — | **绝不再次 `session.apply()`**（iCraft 拒绝已 apply 的 Session 重复 apply） |
| 输入 Tensor | 每帧新建+写 | 每帧新建+写（不变） |
| 输出 | forward→waitForReady→to(host)→read | 不变 |

### 2.2 `board_package/npu_rearm_state.hpp`（新增，iCraft-free 纯逻辑状态机）

把「首帧不 reset / 后续每帧恰好一次 reset(1) / 不重复 apply / reset 失败 fail-closed」
抽成纯逻辑类 `chain::NpuReArmState`，`NpuClassifier12` 在板上咨询它，主机可脱离
iCraft 直接单测。

### 2.3 `board_package/board_gate7_12class_npu.cpp`（Gate 7 新输出 + 新门）

新增输出字段：`npu_reset_count`（240 帧应为 **239**）、`npu_frame_count`、
`npu_apply_count`、`npu_discipline`、`delay_shift_match`、`delay_shift_compared`。

PASS 硬门（在 0.90 门限之上叠加，**不改 0.90**）：
```
pass = (240/240) && match_rate>=0.90 && nan_inf==0
       && npu_discipline==OK && delay_shift_match==0
```
`delay_shift_match`：相邻两帧期望类别不同时，本帧 pred 等于**上一帧**期望类别的次数；
干净运行应为 0，固定一帧延迟时为 ~239/239。

### 2.4 Gate 9 同步修复

Gate 9 复用同一个 `chain::NpuClassifier12`（`npu.infer()`），因此**自动**获得
reset(1) 修复；未做任何「Gate 7 单独结果偏移」。仅更新了 `board_gate9_*.cpp` 第 22
行的过时注释（“每帧新建 session” → “持久 Session + reset(1)”）。

### 2.5 主机纯逻辑单测 `host_tests/test_npu_rearm.cpp`（新增）

- 首帧不 reset；
- 后续每帧恰好一次 reset(1)；
- reset 失败 fail-closed；
- 不重复 apply；
- 240 帧 reset_count==239。
共 **500 项断言**全过。

## 3. 主机验证

```
g++ -std=gnu++17 -fsyntax-only -I board_package -I "<iCraft include>" \
    board_package/board_gate7_12class_npu.cpp   -> EXIT 0
g++ ... board_package/board_gate9_full_chain_12class.cpp -> EXIT 0
host_tests/build_host_tests.sh                  -> OK（含 test_npu_rearm）
host_tests/run_tests.sh                         -> ALL HOST TESTS PASSED
test_npu_rearm                                   -> pass=500 fail=0
```

## 4. 板端重编译与复测（仅用户本人执行）

```bash
cd sdr_full_chain_12class_v1
tar xzf gate7_npu_rearm_fix_patch.tar.gz
sha256sum -c SHA256SUMS.txt          # 必须全 OK

# 重编译（ICRAFT_CMAKE_DIR 换成板端实际路径）
ICRAFT_CMAKE_DIR=/usr/cmake ./board_package/build_npu_on_board.sh --gate7-only
LIBIIO_ROOT=<libiio-arm64> ICRAFT_CMAKE_DIR=/usr/cmake \
    ./board_package/build_npu_on_board.sh --gate9

# Gate 7 复测（先诊断，再正式门限）
./bin/board_gate7_12class_npu --diagnostic --golden=deployment_golden --count=240
./bin/board_gate7_12class_npu --golden=deployment_golden --count=240
#   期望：match_rate>=0.90、240/240、nan_inf=0、
#         npu_reset_count=239、npu_discipline=OK、delay_shift_match=0。

# Gate 9 offline 复测（同一 NpuClassifier12）
./bin/board_gate9_full_chain_12class --phase offline ...
```

## 5. 状态红线

- 板端复测 `match_rate>=0.90` 且 240/240、nan_inf=0、`npu_reset_count=239`、
  `delay_shift_match=0`、退出码真透传之前，状态只写 **`NEEDS-GATE7-NPU-REARM-FIX`**，
  **绝不写 PASS/READY**。
- 不通过移动标签、跳过比较或降低 0.90 门限来掩盖问题。
- 我（助手）不碰板、不写 Flash；重编译与复测由用户本人执行。
