# 十二类 Gate 6–9 板端测试指南（权威）

任务 39e5 §十四：**Gate 6 → 7 → 8 → 9 逐门推进，失败即停**；任何一门 FAIL，停止后续，
先诊断修复，重跑该门。**离线状态只能标 `READY-FOR-GATE6-9-HARDWARE-TEST`**；只有用户本人
上板逐门 PASS 后才可改为 HARDWARE 侧 PASS。

---

## 0. 前置条件

- FMQL30TAI 板端 Linux（aarch64），权威 HDMI 位流已加载（`_disable_icap.bit`，`df8a0c66…`）。
- 板端已装：iCraft 3.39 运行时 + cmake 配置（`/usr/cmake/icraft-*.cmake`）；`g++` / `cmake`。
  **板端没有 pkg-config，也没有系统 libiio**；libiio 由你自行编译，位于
  `/tmp/sdr_pluto_gate1_5/libiio-arm64`（含 `include/iio.h`、`lib/libiio.so`、
  `lib/pkgconfig/libiio.pc`），构建/运行时通过环境变量 `LIBIIO_ROOT` 传入（见 §2）。
- Pluto（Rev.C + AD9364，fw v0.39）USB 接板端，`iio_info -s` 能枚举到。
- 我（助手）**不碰板、不写 Flash**；以下命令全部由用户本人执行。

## 1. 解包与自校验

```
tar xzf sdr_full_chain_12class_board_package.tar.gz
cd sdr_full_chain_12class_board_package
sha256sum -c SHA256SUMS.txt          # 必须全 OK
```

## 2. 构建

板端 **无 pkg-config、无系统 libiio**；libiio 是你自行编译的，位于
`/tmp/sdr_pluto_gate1_5/libiio-arm64`（`include/iio.h` + `lib/libiio.so` +
`lib/pkgconfig/libiio.pc`）。所有依赖 libiio 的构建/运行都必须显式传 `LIBIIO_ROOT`。

```
# Gate 6 / Gate 8 / 定标器（直接 g++；Gate 8 无 libiio，但同脚本一起构建）
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./board_package/build_on_board.sh

# Gate 7（iCraft，cmake；不依赖 libiio / pkg-config，可单独构建）
ICRAFT_CMAKE_DIR=/usr/cmake ./board_package/build_npu_on_board.sh --gate7-only

# Gate 9（iCraft + libiio；必须传 LIBIIO_ROOT）
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 \
ICRAFT_CMAKE_DIR=/usr/cmake ./board_package/build_npu_on_board.sh --gate9
```

构建脚本 fail-closed：`LIBIIO_ROOT` 下缺 `include/iio.h` 或 `lib/libiio.so` 时**编译前**
报错退出（build_on_board.sh exit 1 / cmake FATAL_ERROR），`--gate9` 缺 `LIBIIO_ROOT` 也会
在调 cmake 前退出。运行侧 `run_gate9.sh` 同样会检查 `${LIBIIO_ROOT}/lib/libiio.so`，
缺失即退出非零，**绝不回退 Mock**。

把产物复制到 `bin/`（run 脚本默认在此找）：

```
mkdir -p bin
cp board_package/bin/board_gate6_sdr_preprocess \
   board_package/bin/board_gate8_ui \
   board_package/bin/board_calibrate_rec_scale bin/
```

> **Gate 7 / Gate 9 已由 `build_npu_on_board.sh` 自动安装到顶层 `bin/`**：
> `bin/board_gate7_12class_npu`、`bin/board_gate9_full_chain_12class`，**无需手动复制**。
> 构建成功打印 `NPU_BUILD_RESULT gate=7|9 result=PASS binary=<绝对路径>`；失败返回非零，
> 且构建前先删除该 gate 的旧 `bin/` 产物、失败后也不留旧二进制冒充成功。Gate 7 用
> `board_package/build_gate7/`、Gate 9 用 `board_package/build_gate9/`，相互隔离，反复构建互不删除。

> `ICRAFT_CMAKE_DIR` 用于定位 iCraft cmake 配置（`-DCMAKE_PREFIX_PATH`）；若未设而
> `find_package(icraft-* REQUIRED)` 找不到，显式 `ICRAFT_CMAKE_DIR=/usr/cmake` 重跑。

## 3. 逐门命令与判据（严格顺序，失败即停）

每门程序打印一行 `GATE_RESULT gate=... result=PASS|FAIL ...`，退出码 0=PASS / 1=FAIL /
2=device-not-found（Gate 6/9）。判据**不得放宽**。

### Gate 6 — SDR 预处理（先环境，后回环）

```
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/run_gate6.sh            # --loopback=0：采环境
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/run_gate6.sh --loopback=1  # 数字回环，验证每帧含 10 kHz 单音
```

**PASS**：`frames=16/16`、`short=0 interrupted=0 overflow=0 drop=0 disc=0`，且
`--loopback=1` 时 `ratio_min > 0.3`。

### Gate 7 — 十二类 NPU 对黄金集

```
./scripts/run_gate7.sh
```

**PASS**：`samples=240/240`，`match_rate >= 0.90`（黄金集自洽 98.3%，int8 量化允许少量
边界翻转）。打印 `per_class=` 每类匹配。

### Gate 8 — 结果→UI JSONL（无 SDR/NPU）

```
./scripts/run_gate8.sh
```

**PASS**：`samples=240/240 valid=240`（每条 JSONL 结构合法、argmax/类自洽、概率和≈1、
class_count=12、version=12class-chain-v1、model_sha 匹配）。

### §九 定标（Gate 9 digital/rf 之前）

```
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/run_calibrate_rec_scale.sh   # 连跑 ≥3 次，rec_scale 稳定（相对变化 <1%）
```

记下 `rec_scale` 值（见 `RECEIVER_SCALE_CALIBRATION.md`）。

### Gate 9 — 全链三阶段

```
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/run_gate9.sh --phase=offline   # 最强：黄金集→NPU→UI
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/run_gate9.sh --phase=digital --rec-scale=<定标值>
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/run_gate9.sh --phase=rf --rec-scale=<定标值> --confirm-safe-rf-path
```

**PASS**：
- `offline`：`samples=240/240`、`match_rate>=0.90`、`valid=240`；
- `digital`/`rf`：`frames=16/16`、`valid=16`、无流异常（`short=0 overflow=0 drop=0 disc=0`）、
  `ratio_min>0.3`（活性，**不判分类正确**），且 `rf` 必须实际给了 `--confirm-safe-rf-path`。

## 4. 失败即停

任何一门 FAIL：**停止后续门**，保存该门日志（含 `GATE_RESULT` 行 + `restore_result=`），
诊断根因后再重跑该门。禁止 Mock 冒充真实、禁止降低阈值。

## 5. 状态措辞（红线）

- 离线交付（未上板）：**`READY-FOR-GATE6-9-HARDWARE-TEST`**，**不写** PASS / READY / HARDWARE_PASS。
- 模型标签只能是 **`12CLASS_CHAIN_VALIDATION_MODEL`**（通路验证模型），**不得**写成
  「最终鲁棒模型 / 最终准确率 PASS / OOD PASS」；OOD 门 = **NO_GO**。
- 上板逐门 PASS 后，由用户本人在 `END_TO_END_ACCEPTANCE.md` 记录结论。
