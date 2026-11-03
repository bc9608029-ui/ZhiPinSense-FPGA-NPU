# 板测手册 — fix1v2 board impl1（G1–G4 收口，独立接收主验收臂）

状态令牌：`…-READY-FOR-BOARD-TEST`（纯离线；禁 RF_PASS）。**板端 C++ 未 aarch64 编译**
（Windows 主机无交叉链），上板前必须在板端原生构建并逐字节核验恢复域。

## 0. 诚实缺口（先读，与验收无关的已知限制）

1. **板端 C++ 未编译**：`board_package/radioml_independent_rx_runner.hpp` + `gate9_wiring.patch`
   是「写定未 aarch64 编译」的接线与恢复核心；host 侧用 g++ 15.2.0 编译 + 运行验证过同一
   `.hpp`（见 §1），但板端原生编译是本手册第 2 步才发生。
2. **归一化 1/S 逐字节核验**：板端恢复载荷的 counts-vs-waveform 域以「板端首次 `--capture-source=file`
   构建」与 host 数字参考（§1 的 8/8×2）逐字节比对为准；host 参考已确立正确 1/S。
3. **设备臂独立板端判读脚本已接通**（Item-5 修复）：新增 `scripts/judge_radioml_independent_rx_board.py`
   （自包含 stdlib，21 列板端判读器）。设备捕获（真实 RF）的 recovered tensor 不要求与数字
   基线逐字节相同（RF 噪声/CFO/时偏带来残差>0），其判读 = 摘要标志 + `board_pred vs class_index`
   + `training_residual_rel` vs 0.100 门（§6 给出具体命令）。文件源用 `--kind file` 做逐字节
   比对，设备源用 `--kind device` 只做可观测统计（不做 RF 归因）。

## 1. Host 侧编译/运行复现（纯离线，WSL/g++ 15.2.0，已验 8/8×2）

`host_tests/test_radioml_independent_rx.cpp`（含在 PATCH 包内）在
`fix10class24_fix1v2_board_impl1_work/` 根目录编译运行；可复现命令（无 `-I`、无 libiio）：

```bash
# 编译（runner 头 quote-include 相对解析到 board_package/ + ../sdr_adapter/）
g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
    -o host_tests/bin/test_radioml_independent_rx \
    host_tests/test_radioml_independent_rx.cpp        # BUILD_RC=0

# 运行（v1 + v2 各一遍，期望各 pass=8 fail=0）
host_tests/bin/test_radioml_independent_rx \
  --tx-dir ../fix10class24_independent_rx_delivery_fix1_work/tx_package \
  --reference-tsv ../fix10class24_independent_rx_delivery_fix1_work/replay_out/independent_rx_replay.tsv \
  --reference-layers ../fix10class24_independent_rx_delivery_fix1_work/replay_out/layers \
  --out-dir host_tests/bin/out_v1_rebuild
# v2：三段 --tx-dir/--reference-tsv/--reference-layers 换成
#     ../fix10class24_waveform_correct_v2_work/...  （source_id 不同 → S 不同 → 不同 recovered SHA）
```

证明点：G2 链路「实际 RX IQ 真捕获 → 恢复 → 分类」在 host 侧全链跑通，recovered
`model_input_sha256` 与 Python B 层参考 24/24 逐字节一致 + recovered tensor 字节 ==
Python B 层 bin + clean-digital gated + classification finite + infer-twice 24/24 +
A 层 manifest SHA != B 层 recovered SHA（恢复为真实计算，非拷贝）。R1 的 TX-restore
反例在 `host_tests/test_pc_tx_simulated_device.py`（36/0，注入假 iio 设备，见 §4）。

## 2. 板端接线 + 构建（板端原生，单目标）

基础树 = `fix10class24_original_radioml_dc_ab1_work/board_package/`（3 相位共存：npu +
dualsdr + singlesdr）。在板端树根执行：

```bash
# (a) 解包 + 逐文件校验（SHA256SUMS.txt 在 PATCH 包内）
tar xzf fix1v2_board_impl1_PATCH.tar.gz -C <tree_root>
cd <tree_root>
sha256sum -c SHA256SUMS.txt        # 全部 OK 才继续（任一 FAIL 立即停）

# (b) 接线（gate9_wiring.patch，5 个 hunk；或手工照抄）
git apply board_package/gate9_wiring.patch

# (c) 构建——只构建 producer 单目标（非 root build_on_board.sh，那会连 UI server 一起建）
cd board_package
# 单线程构建：build_npu_on_board.sh 内部硬编码 make -j"$(nproc)"。taskset -c 0 把进程
# 钉到单核 -> nproc 返回 1 -> make -j1（避免多线程 OOM 与 g++15 sign-compare 竞态）。
LIBIIO_ROOT=/opt/sdr/libiio-0.26 taskset -c 0 ./build_npu_on_board.sh --gate9-rml23
#   期望输出：  NPU_BUILD_RESULT gate=9R result=PASS binary=<tree_root>/bin/board_gate9_full_chain_rml23
#   失败则：    NPU_BUILD_RESULT gate=9R result=FAIL  （失败前已删除旧二进制，绝不留下旧包冒充本轮）
```

- `LIBIIO_ROOT`：板端持久化 libiio 0.26 装在 `/opt/sdr/libiio-0.26`（首选）。
  若该持久化安装尚未完成，退回旧临时安装 `LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64`。
- 二进制安装路径 = `<tree_root>/bin/board_gate9_full_chain_rml23`（`build_npu_on_board.sh`
  自动 cp 到 `PKG_ROOT/bin`；`run_gate9_rml23.sh` 从 `bin/` 加载）。
- 若 g++15 在标量 WL 冻结头报 `sign-compare` 错误，仅本测一次性追加
  `-DCMAKE_CXX_FLAGS=-Wno-error=sign-compare`（不改冻结头/永久 flags）。

## 3. 冻结模型身份（全 SHA，非缩写）

板端运行只用 BF16 `json` + `raw`（NPU 推理），`ckpt` 是 host 训练产物、不上板：

```text
model_rml24_bf16/rml24_adamrv11_bf16.json  = 28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42
model_rml24_bf16/rml24_adamrv11_bf16.raw   = c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151
```

只读核验（板端）：

```bash
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.json
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.raw
# 逐字节比对上面两行全 SHA；任一不符即停，不上板
```

## 4. PC TX 服务（PC 端；真 RF 需 radioconda pylibiio 0.26）

先跑 mock（无 RF 纯控制流回环）打通握手，再上真。命令在 PowerShell 里用反引号 `` ` `` 续行
（**不是** `^`，也不是 Bash 的 `\`）；反引号必须是行尾**最后一个字符**，其后不能有空格：

```powershell
# 真设备（PC 控 TX，板端控 RX，仅 TCP 39010 传控制+SHA，不传 IQ）
D:\radioconda\python.exe -I host_tools\pc_tx_sdr_fix10_public.py --listen 0.0.0.0:39010 `
    --tx-uri "<PC_TX_URI>" --frozen-dir "<public_protocol_tx_package>" `
    --rf-path direct-cable --tx-atten -40

# 模拟设备（无 RF，先跑通再上真）
D:\Anaconda\python.exe -I host_tools\pc_tx_sdr_fix10_public.py --mock `
    --frozen-dir "<public_protocol_tx_package>" --listen 127.0.0.1:39010
```

- 文件名是 `pc_tx_sdr_fix10_public.py`（R7 已重命名，不再是旧的 `pc_tx_sdr_fix10.py`）。
- `--tx-atten -40` 是 -40 dB 安全上限，服务拒绝任何更高值（fail-closed）。
- `--frozen-dir` 指向 `tx_package/`（含 `public_protocol_tx_manifest.tsv` + 24 个
  `<sid>.burst.i16` + `SHA256SUMS.txt`）。
- R1 证据：`host_tests/test_pc_tx_simulated_device.py`（36/0）证明 `restore()` 写真实
  `.value` + 读回校验 + 假 iio 注入的静默非写被捕获 + `tx_restore_ok=false` 传播。

## 5. 板端运行（`$OUT` 只 export 值，**不要 mkdir**）

```bash
# 板端：只 export $OUT 变量（tee 日志写到 $OUT 之外）。**不要 mkdir**——runner 对已存在的
# --out-dir 是 fail-closed 拒绝（它自己会创建该目录），预建目录会导致本轮被拒（Item-4 修复）。
export OUT="/tmp/rml24_independent_rx_$(date +%s)"

# (A) 设备捕获（真实 RX + PC-TX 控制通道 HELLO/PREPARE/START/CAPTURED/STOPPED）
bash scripts/run_gate9_rml23.sh \
  --phase=radioml-independent-rx-public-protocol-24class-bf16-fix1 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --input-dir=<public_protocol_tx_package> \
  --capture-source=device \
  --rx-uri=<board_rx_uri> \
  --tx-control=tcp://<PC_IP>:39010 \
  --rx-gain=35 \
  --out-dir="$OUT" | tee "$OUT.run.log"

# (B) 文件源（host 已验 8/8×2 的同链路，板端复现用；无设备）
export OUT_FILE="/tmp/rml24_independent_rx_file_$(date +%s)"
bash scripts/run_gate9_rml23.sh \
  --phase=radioml-independent-rx-public-protocol-24class-bf16-fix1 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --input-dir=<public_protocol_tx_package> \
  --capture-source=file \
  --rx-gain=35 \
  --out-dir="$OUT_FILE" | tee "$OUT_FILE.run.log"
```

- `--model-json/--model-raw/--model-sha` 三者**必须显式覆盖**：`run_gate9_rml23.sh` 的
  `common_rml23.sh` 默认是 23 类 `model_rml23/model_24class_ZG.*`，本相位要 24 类 BF16
  （后出现参数获胜，`"$@"` 在默认值之后）。
- `--rx-gain=35` 必须**显式**传：`run_gate9_rml23.sh` 默认注入 `--rx-gain=10`，若不在
  `"$@"` 里显式给 35，runner 会继承旧脚本的 10（Item-4 修复）。
- v1 与 v2 是两套 manifest（`source_id`/`conversion_version` 不同 → S 不同），分两次跑、
  分开 `$OUT`。
- 板端**不强制分类**：门拒帧 `board_pred=-1`，只做测量（`ROUTE_F_RADIOML_INDEPENDENT_RX_PUBLIC_PROTOCOL_*`
  token），不判 PASS。

## 6. 结果回传 + 判读

`$OUT` 产物：`board_independent_rx_results.tsv`（21 列，含 `board_pred`/`training_residual_rel`/
`gated`/`finite`/`repeatable`/`capture_ok`/`no_sync`/`rx_clipped`/`raw_rx_sha256`/`logits_sha256`/
`model_input_sha256`）、`board_independent_rx_summary.tsv`（运行级 `completed`/`n_processed`/
`n_gated`/`n_classified`/`n_correct`/`tx_restore_ok`/`rx_readback_ok`/`negative_control_pass`/
`functional_pass`）、24 个 `<sid>.recovered.tensor.bin`、`<sid>.logits.tsv`（真实 24 维 logits，
infer-twice）、`<sid>.raw_rx.i16`（R5 原始捕获）、`run.log`。

```bash
# 回传（板端 -> host）
tar czf "$OUT.tgz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
# scp 或串口传回 $OUT.tgz

# --- host 判读 ---
# (1) 数字基线（离线，主机预跑，fix1 与 v2 各自）：
python -I fix10class24_independent_rx_delivery_fix1_work/scripts/judge_radioml_independent_rx.py \
  --kind digital \
  --manifest <v1 tx_package>/public_protocol_tx_manifest.tsv \
  --result <v1 replay_out>/independent_rx_replay.tsv \
  --layers-dir <v1 replay_out>/layers --out-json v1_digital.json
python -I fix10class24_waveform_correct_v2_work/scripts/judge_radioml_v2.py \
  --manifest <v2 tx_package>/public_protocol_tx_manifest.tsv \
  --result <v2 replay_out>/independent_rx_replay.tsv \
  --layers-dir <v2 replay_out>/layers --out-json v2_digital.json

# (2) 文件源板端结果（--capture-source=file）：21 列专用判读器。判读器做四重核验：
#     (a) recovered tensor 与数字 B 层逐字节相同（--layers-dir 参考 bin 的 SHA ==
#         results.tsv 的 model_input_sha256 列第 21 列）；
#     (b) 板端**实际**张量文件核验（--tensor-dir 指向 $OUT，逐文件读 <sid>.recovered.tensor.bin
#         算 SHA 与 TSV 声明比对，发现缺失/篡改）；
#     (c) 预测对照（--digital-baseline 指向 host 数字重放 independent_rx_replay.tsv，
#         比较 board_pred vs recovered_pred，计算预测一致率/同错/新增翻转）；
#     (d) 数字基线身份绑定（--baseline-identity 指向冻结 sidecar，把数字基线绑定到
#         source_id/version/manifest SHA/模型身份，防 v1/v2 基线混用）。
#     一致率主指标 = 有效一致预测数/24（缺行/门拒/非有限/未捕获/未分类不计入分子）；
#     条件一致率 = 有效一致预测数/有效行数（另列）。
python -I scripts/judge_radioml_independent_rx_board.py --kind file \
  --results "$OUT_FILE/board_independent_rx_results.tsv" \
  --summary "$OUT_FILE/board_independent_rx_summary.tsv" \
  --manifest <v1|v2 tx_package>/public_protocol_tx_manifest.tsv \
  --layers-dir <v1|v2 replay_out>/layers \
  --tensor-dir "$OUT_FILE" \
  --digital-baseline <v1|v2 replay_out>/independent_rx_replay.tsv \
  --baseline-identity scripts/digital_baseline_identity.json \
  --out-json board_file_judge.json
# 退出码：0 = 分析成功且测量完整有效；1 = 分析失败（缺文件/表头错/重复 ID/身份不一致/基线
#         身份不符）；2 = 分析成功但测量不完整或无效（缺源/摘要漂移/字节不符/张量文件缺失或
#         篡改/预测不一致/completed!=1 或 functional_pass!=1）。期望 file 模式 rc=0、
#         byte_identical=24/24、board_tensor_files=24/24、digital_binding=24/24、
#         prediction n_valid=24 n_agree=24 n_new_flip=0、agreement/24=1.0。
# v1 用 fix1 replay_out/layers + fix1 replay_out/independent_rx_replay.tsv + fix1 tx_package；
# v2 用 v2 的对应目录（S 不同 → 不同 SHA）。--baseline-identity 用同一个 sidecar（内含
# v1/v2 两套身份记录，判读器按 manifest 的 source_id/version 自动命中）。

# (3) 设备源板端结果（--capture-source=device）：只做可观测统计 + 门/标签，不要求与数字逐字节相同。
#     仍核验板端实际张量文件（--tensor-dir）；--digital-baseline 可选，提供时计算预测一致率/同错/
#     新增翻转（仅记录，不做 RF 归因）；提供 --digital-baseline 时必须同时给
#     --baseline-identity（绑定 v1/v2 基线身份，防混用），但设备模式**不**比较 RF C 张量与 B 层字节。
python -I scripts/judge_radioml_independent_rx_board.py --kind device \
  --results "$OUT/board_independent_rx_results.tsv" \
  --summary "$OUT/board_independent_rx_summary.tsv" \
  --manifest <tx_package>/public_protocol_tx_manifest.tsv \
  --tensor-dir "$OUT" \
  --out-json board_device_judge.json
#   判读器独立重算 processed/gated/classified/correct/no_sync/rx_clipped 并与 summary 逐项
#   比对（SUMMARY_DRIFT 即 fail-closed）；设备模式**不做 RF 归因**。判据：completed=true、
#   n_processed==24、tx_restore_ok=true、rx_readback_ok=true、negative_control_pass=true
#   （TX 关窗无前导同步）；n_gated/n_classified 与 board_pred==class_index 的 n_correct
#   如实记录；training_residual_rel <= 0.100 过门。rc=0 表示分析成功且测量完整有效；
#   rc=2 表示测量不完整/无效（如 completed/functional_pass!=1 或张量文件缺失）。
```

设备臂不做「RF 归因」：数字与 RF 同错、无新增翻转时，不自动归因 RF（归因须板端训练块
残差单独证据）。

## 关键约束（同 fix1/v2，红线）

- 24 类 BF16 + `--rx-gain=35`（勿用 23 类默认 `--rx-gain=10`）。
- 0.100 门 + ≤3 次重捕 + 末次选择不变；`hard_invalid`（residual_rel>0.30）绝不旁路。
- 不训练、不改模型/波形资产、不发射（TX 只做 `--tx-atten -40` 上限内的直连电缆回环）、
  不重跑 RF；最高状态止于 `…-READY-FOR-BOARD-TEST`，不写 RF_PASS / PROJECT_COMPLETE。
