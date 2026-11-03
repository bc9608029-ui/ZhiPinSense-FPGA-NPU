# 板端测试流程（任务 39e5 §十，逐门 fail-fast）

> 本工程最高离线状态只写 **READY-FOR-12CLASS-LIVE-UI-HARDWARE-TEST**。
> 我（离线侧）**禁碰板 / 禁写 Flash**；以下所有上板命令由用户本人执行。
> 权威上板位流仍为 v4_fix 的 `_disable_icap.bit`（SHA `df8a0c66…`），
> JTAG 只烧该位流，**绝不写 Flash**。

## 0. 前提

- 板上已烧 v4_fix HDMI-only 位流（`hdmi_framebuffer_720p_top_disable_icap.bit`）。
- 已解包板端包 `sdr_full_chain_12class_ui_v1_board_package.tar.gz`，`sha256sum -c SHA256SUMS.txt` 全 OK。
- 以 root 运行（UI 服务端需 `/dev/mem` + `/dev/udmabuf0`）。

## 1. 构建

```sh
# UI 服务端（无 iCraft、无 libiio，纯 g++）
./board_package/build_ui_live.sh g++        # 期望 UI_BUILD_RESULT result=PASS
# 头文件/纯 libiio 门（Gate 6 / Gate 8 / 定标）
./board_package/build_on_board.sh g++       # Gate 6 + Gate 8 + calibrate
# NPU 门（Gate 7 / Gate 9，需 iCraft SDK；Gate 9 另需 LIBIIO_ROOT）
./board_package/build_npu_on_board.sh --gate7-only
LIBIIO_ROOT=/opt/sdr/libiio-0.26 ./board_package/build_npu_on_board.sh --gate9
```

任何一步非零退出即停（fail-fast），不要带旧二进制上板。

## 2. 起 UI 服务端

```sh
./scripts/run_ui_live.sh
# 期望输出： UI_LIVE_READY sock=/run/sdr_amr_ui.sock pid=<pid> log=/tmp/sdr_ui_live/ui_live.log
```

- 必须看到 `UI_LIVE_READY` 且 `[ -S /run/sdr_amr_ui.sock ]` 成立。
- 服务端日志必须先出现 **`UI_VERSION_CHECK version=0x20230218 OK`**（读
  `0x40080000+0x0C` 等于冻结版本）才会碰 framebuffer；不匹配则打印
  `UI_VERSION_CHECK FAIL` 并立即退出（exit 3），**绝不写帧缓冲寄存器**。
- 首屏应显示 STALE 等待帧（无数据、徽标 STALE）。

## 3. Gate 8 → Socket → 屏幕回放（OFFLINE_REPLAY，不需要 NPU）

```sh
./scripts/run_gate8_ui_socket_test.sh
# 期望： GATE8_UI_SOCKET_TEST result=PASS
#        received=240 valid=240 rejected=0 rendered>=1 rendered<=240
#        coalesced=valid-rendered last_frame_id=240
```

§四 修正 1 的收口断言：`received==valid==N`、`rejected==0`、`rendered>0 && rendered<=valid`、
`coalesced==valid-rendered`、`last_frame_id==最后发送帧`。屏幕应在 30Hz 上限逐 tick 显示**最新**合法帧
（不逐帧阻塞）。这一步在 HDMI-only 位流下即可完成，**证明 socket→屏幕链路可用**。

## 4. Gate 7 普通 240 条最终门禁（NPU 位流）

切回 NPU 位流后：

```sh
./scripts/run_gate7.sh
# 期望 8 条件 gate7_pass：
#   processed==240 && match_rate>=0.90 && nan_inf==0
#   && npu_reset_count==239 && npu_frame_count==240
#   && npu_apply_count==1 && npu_discipline==OK
#   && delay_detected==NO
# detail 新增： aligned_match_rate= / delay_shift_rate= / delay_detected=YES|NO
#              infer_us_mean= / infer_us_p99= / infer_us_max=
```

延迟门禁**冻结判定**：`delay_shift_rate = compared>0 ? match/compared : 0`；
`delay_detected = compared>0 && rate>=0.90 && rate>aligned_match_rate`。实测
`delay_shift_match=10/236` 属偶然碰撞 → `delay_detected=NO`，不再误报。

## 5. Gate 9 → 屏幕（**BLOCKED**，真 NPU 实时链）

```sh
./scripts/run_gate9_ui.sh <offline|digital|rf>
# 期望： FULL_CHAIN_UI_BLOCKED bitstream_incompatible  （exit 3，fail-closed）
```

Gate 9 需 NPU 位流、UI 服务端需 HDMI 位流，二者互斥、无合并位流（见
`docs/BITSTREAM_COMPAT_AUDIT.md`）。**绝不假装 LIVE**。离线演示请用步骤 3 的
`run_gate8_ui_socket_test.sh`（已标 `OFFLINE_REPLAY`），或“NPU 位流下
`run_gate9.sh --phase=offline --sock=` 记录 JSONL → 切 HDMI 位流 → 回放”，但必须标
`OFFLINE_REPLAY`，不得称 LIVE。

## 6. Gate 9 各相位（NPU 位流下单独跑，不连屏幕）

```sh
./scripts/run_gate9.sh --phase=offline                        # golden -> NPU -> UI
./scripts/run_gate9.sh --phase=digital --rec-scale=<定标值>    # 数字回环
# RF 相位必须先定标 + 显式确认射频路径：
./scripts/run_gate9.sh --phase=rf --rec-scale=<定标值> --confirm-safe-rf-path
```

digital/rf 依赖 `LIBIIO_ROOT`（fail-closed）、不允许 Mock 回退；rf 必须显式
`--confirm-safe-rf-path`（TX 已接 ≤-40 dB 衰减）。

## 7. receiver_scale 定标（§九，Gate 9 RF 前）

```sh
./scripts/run_calibrate_rec_scale.sh
```

## 8. 查收口

- 各门退出码（0/1/2）；Gate 9 发送端 `sock_errors`；UI 服务端日志末条 `UI_STATS`
  `received/valid/rejected/rendered/coalesced/last_frame_id`；断线后服务端应持续渲染
  STALE 并等待重连（不崩溃、不保留假 LIVE）。
- 收尾：`./scripts/stop_ui_live.sh` → `UI_LIVE_STOPPED pid=<pid>`（仅 `kill -TERM`，不 pkill）。

## 9. 收工

```sh
sync && poweroff
```

## 判定红线

- 仅步骤 3 可在 HDMI-only 位流完成并标 **PASS**；步骤 4 需 NPU 位流单独 PASS。
- 步骤 5/6/8 的“Gate 9→屏幕真 NPU 实时链”在合并位流存在前标 **BLOCKED**。
- 模型标签只写 `12CLASS_CHAIN_VALIDATION_MODEL`，OOD=NO_GO；绝不写 SCREEN_PASS /
  FULL_CHAIN_HARDWARE_PASS / FINAL_MODEL_PASS / OOD_PASS。
