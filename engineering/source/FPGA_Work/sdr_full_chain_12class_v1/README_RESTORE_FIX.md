# Gate 6–9 状态恢复 + 最终门禁 fail-open 修复（补丁）

任务 39e5 第二批（十二类 Gate 6–9）状态恢复路径修复。状态：**`READY-FOR-GATE6-9-HARDWARE-TEST`**
（未上板，**非 PASS**；本次修复不得把 Gate 6 记录为硬件 PASS）。

## 1. 真实板端日志（触发本修复）

```
pluto: restore: RX gain failed
GATE_RESULT gate=gate6_sdr_preprocess result=PASS ... restore_result=FAIL ...
gate6_ambient_rc=0
```

## 2. 根因

1. **AGC 模式下误写 hardwaregain**：`restore_params()` 先把 `gain_control_mode` 恢复为
   `slow_attack`（AGC），随后又**无条件**写 `hardwaregain`。AD936x 在 AGC 模式（slow_attack /
   fast_attack / hybrid）下**禁止手动写 hardwaregain**，该写入必然失败 → `restore_result=FAIL`。
   且 AGC 模式下读回的 `hardwaregain` 是运行时状态，本就不该作为"可恢复的手动值"写回。

2. **最终门禁 fail-open**：Gate 6 / 定标器 / Gate 9 计算完功能 `pass` 后，没有把
   `restore_result` 纳入最终 PASS 与退出码，导致 `restore_result=FAIL` 仍打印 `result=PASS`
   且退出码 0（fail-open）。

## 3. 修复内容（相对板端工程根目录）

| 文件 | 修复 |
|---|---|
| `sdr_adapter/pluto_device_libiio.cpp` | `restore_params()`：先恢复 `gain_control_mode`；**仅当原模式为 `manual` 才写 hardwaregain**，写后读回验证；AGC 模式只恢复模式、绝不写 gain；模式/增益读回不符也判 FAIL（不伪造 PASS） |
| `sdr_adapter/pluto_device.hpp` | `FakePlutoDevice` 同步 AGC 语义 + 新增 `fail_mode_restore` / `fail_manual_gain_restore` / `gain_write_in_agc_fails` 测试钩子 |
| `board_package/board_common.hpp` | 新增共享 `board::final_gate_pass(功能 pass, restore_ok, detail)`：restore 失败强制最终 FAIL |
| `board_package/board_gate6_sdr_preprocess.cpp` | 最终门禁纳入 `guard->restore_ok()`，restore 失败 → `result=FAIL` + 退出码 1 |
| `board_package/board_calibrate_rec_scale.cpp` | 同上（定标器） |
| `board_package/board_gate9_full_chain_12class.cpp` | 同上（Gate 9 回环阶段） |
| `host_tests/test_restore_semantics.cpp` | **新增**主机单测：AGC 写 gain 失败 / AGC 恢复不写 gain / manual 恢复原增益 / 模式与手动增益恢复失败各判 FAIL / restore 失败传播到 guard / fail-closed 门禁 |
| `host_tests/build_host_tests.sh` | 加入新测试编译 |
| `host_tests/run_tests.sh` | 加入新测试运行 |

## 4. 主机验证（WSL g++ 15.2 -O2 -Wall -Wextra -Werror）

```
test_chain_common        pass=25 fail=0
test_result_frame_v2     pass=18 fail=0
test_restore_semantics   pass=20 fail=0
test_board_build.sh      21 passed, 0 failed
run_tests.sh: ALL HOST TESTS PASSED
```

## 5. 板端覆盖与重编译

```bash
# 1) 在已解包的板端工程根目录覆盖（补丁用相对路径，直接解包覆盖对应文件）
cd sdr_full_chain_12class_v1
tar xzf gate6_9_restore_fix_patch.tar.gz

# 2) 自校验（必须全 OK）
sha256sum -c SHA256SUMS.txt

# 3) 重新编译（LIBIIO_ROOT 换成你板端的实际路径）
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
- **新增行为**：若 `restore_result=FAIL`，最终 `GATE_RESULT` 必须是 `result=FAIL` 且退出码非零，
  detail 末尾带 `(restore_failed)`。**不得再出现 `result=PASS` + `restore_result=FAIL`**。
- AGC 原始模式（slow_attack）的恢复不再报 `RX gain failed`（因为不再写 AGC hardwaregain）。
- RF 发射须 `--confirm-safe-rf-path` + 衰减天花板 -40 dB。

## 7. 状态红线

- 本补丁离线制作、未经板端实机验证，状态 **`READY-FOR-GATE6-9-HARDWARE-TEST`**，**非 PASS**。
- 我（助手）不碰板、不写 Flash；板端覆盖、重编译、复测均由用户本人执行。
