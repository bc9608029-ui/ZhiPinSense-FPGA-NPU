# npu_realtime_v1 — 常驻 Device 连续推理

在已验证的 FPGA→NPU 联合闭环（`fpga_npu_joint_v1`，Tensor 0 mismatch + NPU 12/12）之后，
解决 iCraft 3.39 / ZG330 **同进程连续推理的一帧旧结果**问题，使 Device 只 Open 一次即可
连续推理，消除每帧 ~265 ms 的 `Device::Close/Open` 开销。这是 SDR 接入前的最后一步。

只读审计（根因 + 官方 API 证据）见 `board_package/REPORT.md`。核心结论：

- `Session::forward()` 对 ZG330 是异步的，输出 Tensor 的完成由「软件 `ready_` 缓存 +
  硬件 `check_func_`」编码；
- `Tensor::waitForReady()` 在 `ready_==true` 时短路，且 `check_func_` 轮询的 FPGA 完成
  状态在同一个 Device 内单调不回零，只有 Device 初始化或 `Device::reset` 才重 arm；
- 修复 = 每帧用**文档化官方 API**（`Device::reset(1)`「只复位 FPGA 状态」/
  `Tensor::setReady(false)`）重 arm 完成状态，并用 `--rearm` sweep 在板上定位正确机制。

## 布局

```
npu_realtime_v1/
└── board_package/                 # 自包含、板上可运行
    ├── npu_realtime.cpp           # 连续推理 + re-arm sweep + 交替帧全 logits 验证
    ├── CMakeLists.txt
    ├── build_on_board.sh
    ├── run_rearm_sweep.sh         # 定位正确 re-arm
    ├── run_realtime.sh            # 3 轮 100 帧 + 交替测试的 PASS 判定
    ├── README.md
    ├── REPORT.md                  # 只读审计报告
    ├── sha256_manifest.txt
    ├── model.json / model.raw
    ├── reference_argmax.txt
    └── tensor_19frames_sint8.bin
```

## 状态

- 审计完成，代码与板载包已备好，**尚未上板**。
- 待板卡：`./build_on_board.sh` → `./run_rearm_sweep.sh`（定位 re-arm）→
  `REARM=reset1 ./run_realtime.sh`（3 轮 100 帧 + 交替测试）。
- 若 `reset1`/`reset1_apply` 均不 PASS，则按 `REPORT.md` §D 携带 `RT_*` 输出向 FMSH
  FAE 书面确认 `getOpWait/setOpWait`/私有状态寄存器的精确语义。
