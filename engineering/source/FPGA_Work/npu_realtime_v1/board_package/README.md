# npu_realtime — 常驻 Device 连续推理（消除每帧 ~265 ms 重开开销）

在已验证的联合闭环 `fpga_npu_joint_v1`（FPGA Tensor 0 mismatch + NPU 12/12）之外，
独立解决 iCraft 3.39 / ZG330 **同进程连续推理的一帧旧结果/完成同步**问题，使 Device
只 Open 一次即可连续推理，不再每帧 `Device::Close/Open`。

**只读审计结论**（详见 `REPORT.md`）：`Session::forward()` 对 ZG330 是异步的，输出
Tensor 的完成由「软件 `ready_` 缓存 + 硬件 `check_func_`」编码；`waitForReady()` 在
`ready_==true` 时短路，且 `check_func_` 轮询的 FPGA 层计数/状态在同一个 Device 内
**单调不回零**。只有 Device 初始化或 `Device::reset` 才重 arm。修复 = 每帧用官方 API
重 arm 完成状态。

## 冻结（不修改）

- 6 个 Mandatory Core RTL、Golden、固定 IQ 与 Tensor 布局
- `model.json` / `model.raw` / ONNX / `best.pt`
- 已验证 bitstream、`AI_Mate.edif`、FMSH patch
- 已 PASS 的 `fpga_npu_joint_v1/`（本工程与其无关，不覆盖）

## 内容

| 文件 | 用途 |
|---|---|
| `npu_realtime.cpp` | 常驻 Device 连续推理 + `--rearm` sweep + 交替帧全 logits 验证 |
| `CMakeLists.txt` | 板载构建（`icraft-zg330backend` + `icraft-hostbackend`，gnu++17） |
| `build_on_board.sh` | cmake + make |
| `run_rearm_sweep.sh` | 逐个 re-arm 机制跑 7..18，定位能 PASS 的官方接口 |
| `run_realtime.sh` | 3 轮 100 帧 + 交替测试的 PASS 判定 |
| `REPORT.md` | 只读审计：根因、官方 API 证据、禁止项、待确认语义 |
| `model.json` / `model.raw` | 冻结 iCraft ZG330 编译产物 |
| `reference_argmax.txt` | 冻结参考（`frame_id,argmax_id,class,ood,ground_truth`） |
| `tensor_19frames_sint8.bin` | 冻结 19 帧 5-plane SInt8（97280 B，逐帧反量化喂 NPU） |
| `sha256_manifest.txt` | 上述文件 SHA-256 |

## 执行顺序（在板卡上）

```sh
cd board_package
sha256sum -c sha256_manifest.txt      # 校验冻结输入未被改动

./build_on_board.sh                   # 编译 npu_realtime

# 1) 定位正确的 re-arm 机制（每次只改一个变量）
./run_rearm_sweep.sh
#   期待：reopen 恒 PASS（正确性对照）；reset1 或 reset1_apply 也 PASS。

# 2) 用定位到的机制跑完整 PASS 判定（默认 reset1）
REARM=reset1 ./run_realtime.sh
#   等价于：3 轮 --test sequence --frames 100 + 1 轮 --test alternating。
```

## 参数

```
npu_realtime --model model.json --raw model.raw --tensor tensor_19frames_sint8.bin \
             --reference reference_argmax.txt \
             --rearm {none|setready|reset1|reset1_apply|reopen} \
             --test {sequence|alternating} [--frames N] [--alt-iterations K] [--rounds R]
```

## PASS 判定

`RT_RESULT=PASS` 需要同时满足（`run_realtime.sh` 汇总）：

1. 持久路径 Device 只 Open 一次、Close 一次（`reopen` 对照除外）；
2. 至少 100 连续帧；
3. 每帧 argmax 对 reference 正确，无任何一帧延迟（`delay_shift=0`）；
4. 无丢帧/重复帧/旧结果/顺序错乱；
5. `timeout=0`、`error=0`；
6. 帧 7..18 参考序列重复运行全部匹配；
7. 交替帧（7 vs 10）逐帧比对**完整 logits** 证明输出确实更新；
8. 持久路径每帧 setup 为毫秒级（无 ~265 ms Device 重开）；
9. 3 轮结果稳定（脚本跑 3 轮 100 帧）；
10. 原 `fpga_npu_joint_v1` 联合闭环仍 Tensor 0 mismatch、NPU 12/12（独立工程，不受影响）。

## 禁止（不调用）

私有 FPGA 寄存器（`STATE_CLEAR/STATE/EXHS_VLD/EXHS_ACK/RESET`）、`setOpWait/getOpWait`、
`clearMMUCache`、`icoreCalc`、假延时、丢/移/预热帧。`layerCount()` 仅只读观测。
