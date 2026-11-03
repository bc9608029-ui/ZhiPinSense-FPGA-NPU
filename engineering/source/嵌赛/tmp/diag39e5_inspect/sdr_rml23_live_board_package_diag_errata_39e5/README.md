# RML23 实时 NPU 主链集成（M29 Phase F5）

> 状态：`M29-RML23-LIVE-CORRECTNESS-FIX-READY-FOR-BOARD-TEST`（最高允许，待用户真实上板；
>       offline conformance gate ≥0.90 只能由板端 `run_gate9_rml23.sh --phase=offline` 验证）
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁自动启动 QAT / 不训练专家模型 /
>       不覆盖 M22/M23/M24 / 禁写 FINAL_*/NPU_PASS/RML23_LIVE_HARDWARE_PASS/
>       UI_HARDWARE_PASS/PROJECT_COMPLETE。

本目录是基于 M22.1 真实实时框架的 23 类集成版本：接入 `expA_bf16_head` 24 类
底层模型，在软件层做 24→23 类 AM-SSB logaddexp 合并，保持 M22 全部功能并实时
输出 23 类。

---

## 1. 冻结输入（SHA256）

| 工件 | SHA256 |
|---|---|
| 12 类回滚模型 raw | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |
| expA 模型 JSON | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` |
| expA 模型 RAW | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` |
| 23 类标签 | `15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88` |
| bitstream | 沿用现有 `22fec95c…`，不重新生成 |

模型文件在 `model_rml23/`（expA 24 类）与 `model_12class/`（回滚）。

---

## 2. 板端运行时依赖

### 2.1 iCraft 3.39 runtime（producer 必需）

- **头文件**：板上 iCraft 3.39 SDK，`icraft-backends/`、`icraft/xir/`、`icraft/xrt/`
  位于 `/usr/include`（默认）或由 `ICRAFT_CMAKE_DIR` 指定（cmake 配置目录，默认 `/usr/cmake`）。
- **动态库**：`Icraft::ZG330Backend`、`Icraft::HostBackend` 由 cmake `find_package` 解析，
  运行期依赖 ZG330 后端 `.so`（板上 iCraft 环境自带）。
- 来源：诸葛 iCraft 3.39 目标 `@zhuget(330)`（FMQL30TAI + ZG330）。

### 2.2 libiio（producer 必需）

- producer 链接真实 libiio 后端（Pluto SDR RX），需显式 `LIBIIO_ROOT` 前缀：
  `LIBIIO_ROOT/include/iio.h` + `LIBIIO_ROOT/lib/libiio.so`。
- 例：`LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64`。
- UI server 不依赖 libiio / iCraft（纯 g++）。

### 2.3 启动前检查

`require_libiio_runtime` 在 `LIBIIO_ROOT` 已设置时会 fail-closed 校验
`lib/libiio.so` 存在并设置 `LD_LIBRARY_PATH`；缺库则非零退出。

---

## 3. 上传 / 校验 / 构建 / 启动 / 测试 / 停止 / 回滚

```sh
# 0. 解包
mkdir -p /opt/sdr/rml23 && tar -xzf sdr_rml23_live_board_package.tar.gz -C /opt/sdr/rml23
cd /opt/sdr/rml23

# 1. fail-closed 校验（模型 SHA + 23 类契约 SHA + 解包清单）
./scripts/verify_package.sh

# 2. 板端 aarch64 构建（producer + UI server）
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/build_on_board.sh

# 3. 正确性门禁（conformance golden，24×10=240 帧，板端唯一正确性判定）
./scripts/run_gate9_rml23.sh --phase=offline --count=240

# 4. 一键启动实时链（UI server + ambient producer，写 PID）
./scripts/start_all_rml23.sh -- --rx-lo=2400000000 --rx-bw=200000 --rx-gain=10 \
    --nco-offset=10000 --rf-diag --rf-diag-interval=100

# 5. 真实 NPU 1000 帧 / 10000 帧稳定性 soak（runtime-stability-only，非正确性门禁）
./scripts/test_live_1000_frames.sh
./scripts/test_live_10000_frames.sh

# 6. 检查结果协议 / UI 计数器
./scripts/check_live_result.sh --result-log=runs/.../rml23_result.jsonl

# 7. 一键停止
./scripts/stop_all_rml23.sh

# 8. 回滚到 M22.1 12 类链（不写 Flash / 不重烧位流）
./scripts/rollback_to_m22_12class.sh
```

构建成功会打印 `NPU_BUILD_RESULT gate=9R result=PASS` 与
`UI_BUILD_RESULT result=PASS`。offline 门禁打印 `match_rate=... GATE_RESULT=PASS|FAIL`
（conformance golden，**不是**模型准确率）；1000/10000 帧脚本打印
`M22_RUNTIME_RESULT result=PASS ... reopen=0 ...` 与 `RML23_TEST_LIVE result=PASS`
（仅证明主链运行时稳定性，**不**构成正确性结论）。

---

## 4. 结果协议

- 新协议版本 `rml23-chain-v2`（state event 同为 `rml23-chain-v2`，心跳/状态事件携带 `model_sha`），
  旧 12 类解析器不会误读 24/23 维结果。
- 每帧记录：`raw_24_logits`（保留审计）、`raw_24_top1`、`merged_23_top1`、
  `merged_23_label`、`deployment_mode=AMSSB_MERGED`、`model_mode=RML23-AMSSB-MERGED`、
  `class_count=23`、`expert_enabled=false`、`expert_result=NOT_RUN`。
- AM-SSB-SC / AM-SSB-WC 只显示为合并后的 `AM-SSB`（23 类标签第 18 位）。

---

## 5. 与 M22 / 12 类链的关系

- 本目录为**独立新目录**，不覆盖 M22/M23/M24 交付物。
- 12 类链（`model_12class/` + `deployment_golden/`）随包携带，`rollback_to_m22_12class.sh`
  停止 RML23 进程并清理状态后，回到 M22.1 12 类链即可复跑既有回归。
