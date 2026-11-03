# 板测手册 — fix1v2-independent-rx-recovery-fix2（A/B/C 三线收口）

状态令牌：`…-HOST-A-LINE-COMPLETE`（纯离线，禁 RF_PASS；**审阅通过前不恢复 READY**）。板端
C++ 未 aarch64 编译（Windows 主机无交叉链），上板前必须在板端原生构建并逐字节核验。

本手册只覆盖 fix2 相对 fix1v2 board impl1 的**增量**。fix1v2 的 G1–G4 板测步骤见
`docs/BOARDTEST.md`（同一树内，本 PATCH 不覆盖它）。

---

## 0. 增量内容

- A 线：`radioml_independent_rx_public_recovery.hpp` 用**联合 (cfo, τ) 2D 网格**替代前导两半
  CFO（修 CFO-τ 耦合），`frac_delay_sinc` 增加 `τ==0 → 恒等` 特例（修干净数字域字节漂移）。
- B 线：`radioml_independent_rx_fft.hpp` FFT 前导定位 + `sdr_adapter/latency_stats.hpp` 资源计量。
- C 线：`host_tests/test_recovery_fix2.cpp`（真实 24 帧 C++==Python 逐字节）、
  `test_sync_bench.cpp` / `test_sync_fft_invariant.cpp`（B 线）、
  `scripts/judge_radioml_independent_rx_board.py`（21→23 列：新增 `fractional_timing` 与
  `cfo_preamble_legacy_hz` 两列）。
- 恢复接口（`recover_and_classify_one` 签名）不变，`gate9_wiring.patch` 无需重打。

---

## 1. Host 侧编译/运行复现（纯离线，WSL/g++ 15.2.0，已验）

已验结果（本 PATCH 交付前）：`test_recovery_fix2` **27/0**（sha 24/24、cfo/τ 网格坐标精确）、
`test_radioml_independent_rx` v1+v2 各 **8/0**（干净数字 fix2==fix1 逐字节）、
`test_sync_fft_invariant` **offset/no_sync 24/24**、`test_sync_bench` **FFT 5.2×**、
Python `radioml_independent_rx_recovery_fix2.py --self-test` **10/10**、
`judge_radioml_independent_rx_board.py --self-test` **13/13**。完整复现命令见
`docs/RECOVERY_FIX2_REPORT.md` §8 与各脚本 docstring。

---

## 2. 板端应用 + 构建（确定性可执行命令）

```bash
# (a) 解包 + 逐文件校验（fix2 树根 = fix1v2 board impl1 树）
tar xzf fix2_recovery_PATCH.tar.gz -C <tree_root>
cd <tree_root>
sha256sum -c SHA256SUMS.txt        # 全部 OK 才继续（任一 FAIL 立即停）

# (b) 构建——只构建 producer 单目标（gate9-rml23；fix2 不改接线，无需重打 gate9_wiring.patch）
cd board_package
LIBIIO_ROOT=/opt/sdr/libiio-0.26 taskset -c 0 ./build_npu_on_board.sh --gate9-rml23
#   期望输出：NPU_BUILD_RESULT gate=9R result=PASS binary=<tree_root>/bin/board_gate9_full_chain_rml23
#   失败则：  NPU_BUILD_RESULT gate=9R result=FAIL （失败前已删旧二进制，绝不留下旧包冒充本轮）
```

- `LIBIIO_ROOT` 首选 `/opt/sdr/libiio-0.26`（持久化安装）；若尚未完成退回
  `/tmp/sdr_pluto_gate1_5/libiio-arm64`。
- `taskset -c 0` 把构建钉到单核（`nproc`→1→`make -j1`），避免多线程 OOM 与 g++15
  `sign-compare` 竞态。
- 若 g++15 在冻结头报 `sign-compare`，仅本测一次性追加 `-DCMAKE_CXX_FLAGS=-Wno-error=sign-compare`
  （不改冻结头/永久 flags）。

---

## 3. 板端验收（核心）

### 3a. 干净数字域 byte-exact（fix2==fix1 回归，主验收）

板端跑**文件源**（复用已冻结 v1/v2 `tx_package`，不重新生成）：

```bash
export OUT_FILE="/tmp/rml24_independent_rx_file_fix2_$(date +%s)"
bash scripts/run_gate9_rml23.sh \
  --phase=radioml-independent-rx-public-protocol-24class-bf16-fix1 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --input-dir=<v1|v2 tx_package> \
  --capture-source=file \
  --rx-gain=35 \
  --out-dir="$OUT_FILE" | tee "$OUT_FILE.run.log"
```

判读器用 `--kind file`。**判读器不支持 `--out-dir` / `--v1` / `--v2`**，必须用下面这组参数：

```bash
python -I scripts/judge_radioml_independent_rx_board.py --kind file \
  --results "$OUT_FILE/board_independent_rx_results.tsv" \
  --summary "$OUT_FILE/board_independent_rx_summary.tsv" \
  --manifest <v1|v2 tx_package>/public_protocol_tx_manifest.tsv \
  --layers-dir <v1|v2 replay_out>/layers \
  --tensor-dir "$OUT_FILE" \
  --digital-baseline <v1|v2 replay_out>/independent_rx_replay.tsv \
  --baseline-identity scripts/digital_baseline_identity.json \
  --out-json board_file_judge.json
```

- 退出码：0 = 分析成功且测量完整有效；1 = 分析失败；2 = 分析成功但测量不完整/无效。
- v1 用 fix1 `replay_out/layers` + `replay_out/independent_rx_replay.tsv` + v1 `tx_package`；
  v2 用 v2 的对应目录（`source_id` 不同 → S 不同 → 不同 recovered SHA）。
- `--baseline-identity` 用同一个 `scripts/digital_baseline_identity.json`（内含 v1/v2 两套
  身份记录，判读器按 manifest 的 `source_id/version` 自动命中）。
- 期望：rc=0、`byte_identical=24/24`、`digital_binding=24/24`、`board_tensor_files=24/24`、
  `prediction n_valid=24 n_agree=24 n_new_flip=0`、`agreement/24=1.0`。此验证证明板端 fix2
  恢复链与 host fix2==fix1 逐字节一致（干净数字域 cfo=0、τ=0、a=1、b=0，
  `frac_delay_sinc(τ=0)=恒等`）。

### 3b. 真实捕获 C++==Python（可选，非必须）

INPUTS 包 `fix2_recovery_INPUTS.tar.gz` 含 `fix2_cpp_ref/`（24 `<sid>.burst.i16` +
`metrics.tsv` + `model_input_sha.tsv`，真实 24 帧 v2 捕获切片）。解包到板端后：

```bash
tar xzf fix2_recovery_INPUTS.tar.gz -C <work_dir>
cd <tree_root>
g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
    -o test_recovery_fix2 host_tests/test_recovery_fix2.cpp
./test_recovery_fix2 --ref-dir <work_dir>/fix2_cpp_ref
```

期望 `pass=27 fail=0`（cfo/τ 网格坐标精确、sha_match=24/24）。此步非必须（主验收为 3a）。

---

## 4. 诚实边界

- 板端 C++ 未 aarch64 编译，本手册 §2(b) 是首次原生编译点；host 侧已用同一 `.hpp` g++ 15.2.0
  编译 + 运行验证（§1）。
- 分离验证段 `training_residual_rel` 仍 **0/24 < 0.100**（0.12–0.16）。这只是「CFO+τ+广线性
  模型在独立验证段未达 0.100」的**负结论**，**不能单独归因于时变/非线性**——需进一步排除估计
  过拟合（拟合目标在估计段）、插值边界效应、验证实现本身的贡献。未排除前，fix2 **不宣称
  RF 恢复完成，也不宣称已定位残余根因**；判读不因 23/24 达标而调门限或剔 sid=18（0.119）。
