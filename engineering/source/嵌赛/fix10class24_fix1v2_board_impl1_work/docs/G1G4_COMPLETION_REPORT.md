# G1–G4 板端实装收口 + 旧交付包解包核查 — 证据报告

- 任务：fix10class24 独立接收交付（fix1 + v2）的**板端侧收口**，补齐 Task C 发现的四个缺口（G1–G4）+ 旧交付包单层解包核查。
- 红线遵守：冻结模型 / 公共协议 / 独立接收边界不变；**不训练、不操作 SDR、不发射、不重跑 RF**（模拟设备 + 文件源，纯离线）。
- 状态：**证据交付供审查，审阅通过前不恢复 READY**。板端 C++ **未在 aarch64 编译**（Windows 无交叉工具链），上板 `make -j1` 原生构建。

---

## 0. 基线（指定基线 = dc-ab1）

- 基础树 = `fix10class24_original_radioml_dc_ab1_work/board_package/`（3 相位共存：npu + dualsdr + singlesdr，8 文件 delta，叠加在 tx_rms_sweep1 全树之上）。
- 本 PATCH 只**新增** fix1 独立接收相位，不覆盖 dc-ab1/npu-ab/dualsdr-ab/singlesdr-ab/v2 的任何文件（唯一例外：见 §5 无覆盖审计）。

---

## 1. G1 — 7 参 shim（修复 fix1「dispatch 调 shim 但 shim 未定义 → 编译失败」）

- `board_gate9_full_chain_rml23.cpp:3305` 定义 7 参 shim：

  ```cpp
  int run_radioml_independent_rx(chain::NpuClassifier24& npu,
                                 const cat::Contract& /*contract*/,
                                 ui::StdoutSink& out, ui::UnixSocketSink& sock,
                                 m22::StageTiming& timing, int argc, char** argv)
  ```

- 内部委托 `iqindepfix1::run_radioml_independent_rx(npu, timing, argc, argv, on_frame)`；`on_frame` 复用 `emit_frame_rml24`。
- 接线：`:3954` `else if (phase == "radioml-independent-rx-public-protocol-24class-bf16-fix1") rc = run_radioml_independent_rx(...)`；错误文本 `:3888` 含新相位。
- `gate9_phase.hpp:30` 新增 `valid_phase` 分支。

## 2. G2 — `rx_int16` 真实填充（禁 stub）

- `radioml_independent_rx_runner.hpp` 两条捕获源均为**真实填充**：
  - `--capture-source=file`：`read_i16_file` 读 burst `.i16` → `iqrftrain::deinterleave` → 恢复 → 分类（host 可测）。
  - `--capture-source=device`：`board::capture_contiguous` 真实 RX + `--tx-control=tcp://<PC_IP>:39010` PC-TX 控制通道（HELLO/PREPARE/START/CAPTURED/STOPPED）。
- **捕获路径证据（host 链路测试，ELF 编译 + 实跑）**：`host_tests/test_radioml_independent_rx` 对 v1、v2 各跑 24 帧：
  - v1 `pass=8 fail=0`（24/24：recovered model_input_sha256 == Python B 层参考、recovered tensor 字节 == Python B 层 bin、clean-digital gated、classification finite、infer-twice repeatable、mock infer 调 48 次、A 层 SHA != B 层 SHA）。
  - v2 `pass=8 fail=0`（同上，v2 的 uniform S 不同 → 不同 recovered SHA，逐字节核验通过）。
  - 结论：**「实际收到的 IQ → 恢复 → 分类」全链路在 host 上真跑通、与 Python 数字契约逐字节一致**。无 stub。

## 3. G3 — v2 板端接线 + manifest source_id

- `radioml_independent_rx_loader.hpp` fail-closed 接受**两套冻结 source_id/version**：

  | source_id | version | S (uniform) |
  |---|---|---|
  | `fix1-public-protocol-24waveforms` | `v1` | 117.84922023433009 |
  | `fix1v2-waveform-corrected-24waveforms` | `v2` | 71.609111379029812 |

- 一个 manifest = 一次转换运行（禁止 v1/v2 混排）；`source_index == class_index+1` 显式；10 列头逐字节；每 burst 239616 字节 + SHA 逐字节校验，任一不符 throw。
- v2 走**同一相位名**（协议同、仅 S 不同），manifest 的 `(source_id, conversion_version)` 决定 S——无需新增相位。v2 板端 runner 即同一 runner。

## 4. G4 — 公共协议 PC TX 服务（39010 SERVER）

- `host_tools/fix10_tx_protocol.py`（协议/session/frame I/O）+ `host_tools/pc_tx_sdr_fix10_public.py`（engine：真实 libiio 惰性导入 + `--mock` 模拟设备；R7 已从旧名 `pc_tx_sdr_fix10.py` 重命名）。
- 完整控制流 HELLO→HELLO_ACK→PREPARE→PREPARED→START→READY→CAPTURED→STOPPED；provenance 断言 `payload_sha_pre==post==burst_sha==manifest burst_sha256`、`tx_scale==1.0`（burst 已预缩放到 S，PC 不再重缩放）、`tx_running==true`/`tx_restore_ok==true`。
- **模拟设备控制流证据**：`host_tests/test_pc_tx_simulated_device.py`（纯 `python -I`，无 libiio/RF）**`pass=36 fail=0`**（v1+v2 各 11 项 + 14 项 R1 TX-restore 反例：manifest SHA 冻结常量、source_id/version、24 burst 逐字节、24 帧全周期、干净退出、ABORT 后停 TX、wrong manifest_sha256 拒绝、wrong payload_sha_pre 拒绝、restore 写真实 `.value` + 读回、静默非写被捕获、MockTxDevice 真恢复、失败恢复传播 `tx_restore_ok=false`）。

## 5. 独立解包 + 真编译 + 无覆盖审计

- **独立解包核查**：重建 dc-ab1 基线（`git init` + 2 文件）→ `git apply --check` **PASS** → `git apply` **PASS** → 应用后内容（LF 归一）与 fork 树逐字节 **一致**（`applied(LF)==fork(LF): True`，两文件）。
- **能编译的部分已真编译**：`host_tests/bin/test_radioml_independent_rx`（ELF x86-64，WSL g++ 15.2.0）已实跑；测试源码 include 了 runner/loader/public_recovery 三个头（编译即证明这三个头 + G2 链路语法正确）。**可复现命令**（工作树根，无 `-I`、无 libiio）：`g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -o host_tests/bin/test_radioml_independent_rx host_tests/test_radioml_independent_rx.cpp` → `BUILD_RC=0`；用**重建二进制**复跑 v1/v2 各 `pass=8 fail=0`（已复现，命令与运行参数见 `BOARDTEST.md` §1）。`board_gate9_full_chain_rml23.cpp` 的 G1 shim 依赖 libiio/NPU，Windows 无交叉链，**未 aarch64 编译**（诚实标注）。
- **无覆盖冲突审计**：本 PATCH 覆盖的唯一既有交付文件是 fix1 的两个同名文件（`board_package/gate9_wiring.patch` 的补丁体、`board_package/radioml_independent_rx_runner.hpp` 的 stub）——这是 G1/G2 修复的实质（补 shim、把 stub 换真），非冲突。其余全部为新增文件。v2 / dc-ab1 / npu-ab / dualsdr-ab / singlesdr-ab 交付文件一律不碰。

## 6. 旧交付包单层解包核查

- `scripts/audit_old_tarballs.py` 遍历 `F:\嵌赛\**\dist\*.tar.gz`，对每包做 `gzip.decompress` 一次 + `tarfile r:` 成员列取 + `r:gz` 交叉验证。
- 结果：**TOTAL=62，SINGLE_OK=62，DOUBLE_GZIP_BROKEN=0，CORRUPT=0**（清单 `dist/old_tarball_audit.json`，含每包 sha256/bytes/members/cross_check）。
- 结论：当前 `dist/*.tar.gz` 无一损坏。Task C 已修复的 4 个 double-gzip 包已用 `mode="w"` 重打包（fix1 PATCH `dea9e391…`/INPUTS `cef55be5…`，v2 PATCH `83548e0f…`/INPUTS `1743b784…`）；损坏原件保存在 `*/dist_doublegzip_BROKEN/`（历史证据，不重改）。**无需再修任何包，未改算法、未重跑 RF。**

## 7. 诚实缺口

1. 板端 C++ **未 aarch64 编译**（Windows 无交叉工具链）；上板 `cd board_package && LIBIIO_ROOT=/opt/sdr/libiio-0.26 ./build_npu_on_board.sh --gate9-rml23` 原生构建，与 host 数字参考 `recover_model_input` 逐字节核验 1/S 归一化。
2. `--capture-source=device` 分支的 libiio 实采 + PC-TX 真 RF 链路未实测（本任务离线，模拟设备 + 文件源已覆盖控制流与恢复分类，真 RF 待用户上板）。
3. 本任务**不宣称 RF 幅度恢复**；只交付「公共协议下未知载荷/未知类别的独立接收测量 + 可信分层诊断」。

## 8. 部署包

- PATCH 包（单 tar.gz）：`board_package/{gate9_wiring.patch, radioml_independent_rx_{loader,public_recovery,runner}.hpp}`、`host_tools/{fix10_tx_protocol,pc_tx_sdr_fix10_public}.py`、`host_tests/{test_radioml_independent_rx.cpp, test_pc_tx_simulated_device.py}`、`scripts/{audit_old_tarballs.py, judge_radioml_independent_rx_board.py, package_fix1v2_board_impl1.py}`、`dist/old_tarball_audit.json`、`docs/{G1G4_COMPLETION_REPORT.md, BOARDTEST.md}`、`SHA256SUMS.txt`（逐文件 64 位 SHA）。
- 输入数据复用 fix1 INPUTS（`cef55be5…`）+ v2 INPUTS（`1743b784…`），本任务不新增 INPUTS。

## 9. 审查反馈修复记录（R1–R7，本报告第 2 轮）

审阅未通过，7 项阻塞发现（R1–R7）已在 bounded 范围内逐一修复，不训练/不改模型与波形
资产/不新增 RF 矩阵/不自动加 FPGA 或均衡实验。修复清单：

- **R1 TX restore 替换 Python 属性对象**：`pc_tx_sdr_fix10_public.py` 的 `PlutoTxDevice.restore()`
  从 `attrs.__setitem__`（把 `ChannelAttr` 换成 `str`）改为 `_wr`/`_wr_dbg` 写真实 `.value` +
  读回校验（`_rd_ll`/`_rd_d`/`_rd_dbg_ll`）+ 逐项 `except` 传播 false + exception-safe TX stop；
  `MockTxDevice.restore()` 从 no-op `return True` 改为真正恢复保存态。反例测试
  `_run_restore_counterexamples`（注入假 iio：可写 `.value` / 静默非写 sticky / 失败 restore）
  覆盖 (a) 写 `.value` + 保持 `ChannelAttr` + 读回匹配，(b) 静默非写被读回捕获→restore False，
  (c) mock 真恢复，(d) 失败 restore→`tx_restore_ok=false`。**36/0**。
- **R2 捕获间隔不保证整 cyclic 帧**：`estimate_timing_offset` 已对称化（`roll(burst,+100)`→-4、
  `roll(burst,-100)`→-100 的 Python bug 不复现）；capture 侧按 `kDeviceCaptureComplex=2*kTotalBurstComplex`
  抓取保证整帧覆盖。
- **R3 residual 增益依赖**：生产残差改为**增益无关相对保真** `training_residual_rel = sqrt(Σ|e|²/Σ|r|²)`
  （RX 能量作分母；即生产平方 NMSE `normalized_residual = ||y-ax||²/||y||² = 1-|corr|²` 的
  **平方根**——源码实际取了平方根，此前摘要漏写），行内新增 `training_residual_rel` 列；
  增益 1.0→0.1999、0.03→0.0060 的假相关被消除。
- **R4 无 RX 读回/限幅检查/负对照**：runner 新增 RX 写后读回 fail-closed、`clip_ratio`（`kClipRatioLimit=0.001`、
  `kClipRail=32766`）限幅检查、TX 关窗无前导同步负对照；门内只接受有限输入，奇异逆被
  `kInverseDenomMin=1e-6` 拒绝。
- **R5 runner 不落盘原始 RX/真 logits/逐次诊断/infer-twice**：`persist_raw_rx`（`<sid>.raw_rx.i16`）、
  `persist_logits`（`<sid>.logits.tsv`，真 24 维 infer-twice，非合成 one-hot）、逐次捕获诊断；
  results 文件在循环前即开并 flush 表头、逐行 flush；`functional_pass` 现在检查
  `completed == n_sources == 24`（而非只查 error/restore）。
- **R6 BOARDTEST 路径/缩写 SHA/$OUT 未初始化/Windows 续行**：重写 `docs/BOARDTEST.md`——
  构建用 `board_package/build_npu_on_board.sh --gate9-rml23`（非 root `build_on_board.sh`）、
  运行用 `scripts/run_gate9_rml23.sh`、全模型 SHA（json `28272abc…a14a42` / raw `c1781aec…b9151`）、
  `$OUT` 显式 `export`+`mkdir`、PC 端 PowerShell `^` 续行（非 Bash `\`）；host 测试 include
  `../board_package/`（非 `../board_package_base/`）。
- **R7 旧文件名撞名**：`pc_tx_sdr_fix10.py` → `pc_tx_sdr_fix10_public.py`（engine + docstring +
  3 处 run 命令 + `prog` + 错误消息 + 测试 import + 打包 FILES 映射全部同步）。

## 10. 第二轮复查反馈修复记录（Items 1–5，本轮）

第二轮复查「仍暂不通过，但只剩明确的实现和部署问题」（已确认新包 SHA/文件校验通过、PC 模拟
测试 36/36、TX 恢复/扩大捕获区间/正向定时搜索等修复已落实；残差源码实际取平方根，摘要公式
已更正）。剩余五项在 bounded 范围内逐一修复：

- **Item 1 削顶检测错误**：`kClipRail` 从 32766 改为 **2047**（12-bit ADC full-scale=2048，
  与板端 `board_calibrate_rec_scale.cpp` 的 `a>=2047` 口径一致；32766 是 16-bit 假想值，
  对已解码 12-bit 数据永不会触发）。**capture_ok=false、rx_clipped=true 现真正阻止分类**：
  runner 内 `usable = capture_ok && !rx_clipped` 后门拒 `gated = usable && !no_sync && …`、
  `forceable` 同理。削顶检测**限定在 ADC 域**（device / `--rx-i16` 源）：干净数字 burst 的
  前导/尾/训练本设计即满幅（|v| 可到 2048），在 rail 2047 下会误判削顶，故文件源分支
  不应用 clip 检测（host 测试显式传 `rx_clipped=false` 并注释原因）。
- **Item 2 负控制假通过**：负对照 fail-closed——`noise_valid = nc_captured && ncont.ok() &&
  !noise_i16.empty()`，任一不成立即 `negative_control_pass=false`（不再把「捕获失败/空数据」
  当成「无同步、负控制通过」）。
- **Item 3 运行状态不一致**：`functional_pass` 移到 summary **写盘之前**计算（不再写过期值），
  且 `device_ok` 只在 `--capture-source=device` 时要求 `rx_readback_ok && negative_control_pass`
  ——文件模式完成 24 帧后 `completed==24` 即 `functional_pass=true`（不再误返回失败）。
- **Item 4 手册命令仍会出错**：`BOARDTEST.md` 的 PowerShell 续行从 `^` 改为反引号 `` ` ``
  （注明必须是行尾最后一个字符）；§5 删去 `mkdir -p "$OUT"`（runner 对已存在 `--out-dir`
  fail-closed 拒绝，预建目录会致本轮被拒，改为 `tee "$OUT.run.log"` 写在 `$OUT` 之外）；
  运行命令显式加 `--rx-gain=35`（`run_gate9_rml23.sh` 默认注入 10，不显式会继承旧值）；
  构建改为 `LIBIIO_ROOT=/opt/sdr/libiio-0.26 taskset -c 0 ./build_npu_on_board.sh
  --gate9-rml23`（`taskset -c 0` 使 `nproc` 返回 1 → 硬编码 `make -j$(nproc)` 退化为 `-j1`
  单线程，避免多线程 OOM 与 g++15 sign-compare 竞态）。
- **Item 5 板端判读未接通**：新增 `scripts/judge_radioml_independent_rx_board.py`（自包含
  stdlib、无第三方依赖），是**21 列专用**板端判读器（旧 `judge_radioml_board_vs_baseline.py`
  要求 11 列，与本相位 21 列输出不匹配）。`--kind file` 做逐字节独立对照（`--layers-dir` 指向
  数字 B 层参考，每个 `<sid>.recovered.tensor.bin` SHA 必须一致 + 全 gated/finite/repeatable）；
  `--kind device` 只做可观测统计（独立重算 processed/gated/classified/correct/no_sync/
  rx_clipped 并与 summary 逐项比对，SUMMARY_DRIFT 即 fail-closed；不归因 RF）。自测
  `--self-test` **4/4 PASS**（file 逐字节一致 rc=0、单 SHA 漂移 rc≠0、summary 漂移 rc≠0、
  device 模式统计 rc=0）。已加入打包 FILES。

本轮未改模型/波形资产/恢复器/门限，未训练，未重跑 RF，未碰板。

## 11. 第三轮复查反馈修复记录（Item 5 判读器三个缺口，本轮）

第三轮复查：前四项关闭，仅第 5 项判读器未完整落实（新包完整性已核验、判读器自测 4/4 通过），
剩三个明确缺口。本轮**只补判读器、反例测试和对应命令，不改恢复算法/模型/波形**：

- **缺口 1 未读数字基线**：判读器新增 `--digital-baseline <replay_out>/independent_rx_replay.tsv`
  （host 数字重放，19 列，`recovered_pred` 为 host 恢复预测），读入后与 `board_pred` 对照，计算
  **预测一致率**（`n_agree`/`agreement_rate`）、**同错**（`n_same_error`，两者一致且都错到同一类）、
  **新增翻转**（`n_new_flip`，数字基线正确但板端翻转）及反向 `n_board_fix`。`--kind file` 下
  `n_agree != 24`（含新增翻转）判测量无效（rc=2）；`--kind device` 下仅作记录不归因 RF。已用
  真实 fix1/v2 两个 `independent_rx_replay.tsv` 加载核验（各 24 行、表头逐字节匹配）。
- **缺口 2 未核验板端实际张量文件**：新增 `--tensor-dir <OUT>`（板端 `$OUT` 目录，含
  `<sid>.recovered.tensor.bin`），逐文件读实际字节算 SHA 与 TSV 声明的 `model_input_sha256` 比对，
  发现文件缺失/被篡改（`TENSOR_FILE` 测量错误，rc=2），不再只信 TSV 里的 SHA。
- **缺口 3 重复 ID 静默覆盖 + 分析/测量未区分**：
  - `load_manifest`/`load_results`/`load_digital_baseline` 在**加载期**即检测重复 `source_index`
    并抛错（不再被 dict 静默覆盖，原 `validate_identity` 的 `seen` 去重逻辑因 dict 已折叠而失效，
    现已移除）。
  - 明确区分「分析执行成功」（判读器能否读全输入并产生可信判定）与「本轮测量完整有效」
    （`completed==1 && functional_pass==1 && 24 源齐全 && 无摘要漂移/字节不符/张量文件缺失/预测不一致`），
    用**三态退出码**区分：`0`=分析成功且测量完整有效、`1`=分析失败（缺文件/表头错/列数错/重复 ID/
    身份不一致/KIND/source_id/version 不符）、`2`=分析成功但测量不完整或无效。分析失败时
    `measurement_valid` 强制置 false（fail-closed，不担保测量有效）。
  - 反例测试扩到 **8/8**：file 全清 rc=0、单 SHA 漂移 rc=2、summary 漂移 rc=2、device 统计 rc=0、
    重复 ID 抛错、张量文件缺失 rc=2、预测新增翻转 rc=2 且 `n_new_flip=1`、KIND 不符 rc=1。

本轮未改模型/波形资产/恢复器/门限，未训练，未重跑 RF，未碰板。

## 12. 第四轮复查反馈修复记录（S1/S2 判读与身份绑定，本轮）

第四轮复查（`RECHECK_4641E014.md`）：主要修复已落实，包校验通过、判读器自测复现，但还剩
两处判读问题，暂不签整体通过。本轮**只修这两处判读与身份绑定，不再改接收算法/模型/波形，
也不增加 RF 采集**：

### S1 — 一致率分母 + 有效行限定

- **原缺陷**：`compute_prediction` 分母是 `n_comparable=len(现帧)`，缺 1 帧仍显示 100%；
  `board_pred` 未检查 `gated/finite/capture_ok/no_sync/rx_clipped`，非有限/捕获失败行也计入一致。
- **修复**：新增 `_is_valid_classification`（`gated==1 && finite==1 && capture_ok==1 &&
  no_sync==0 && rx_clipped==0 && board_pred>=0`）；主指标
  `agreement_over_expected = 有效一致预测数/24`（分母恒为 24），条件一致率
  `conditional_agreement = 有效一致预测数/有效行数`（另列并带分母 `conditional_denominator`）；
  缺行/门拒/非有限/未捕获/未分类(-1)行**不**计入分子，分别以 `n_missing/n_rejected/n_invalid`
  报告；同错/新增翻转/板端纠正只在有效行上算；独立输出 `correct/24`（`correct_over_expected`）、
  `coverage`（`n_valid/24`）、`gated accuracy`、`end_to_end_accuracy`。
- **反例测试（新增）**：缺 1 行 → `agreement/24 = 23/24` 且 `n_missing=1`（不再 100%）；
  `finite=0 + capture_ok=0` 且保留匹配 `board_pred` 的行 → `agreement/24 = 23/24`、
  `n_rejected=1`、`n_invalid=0`。未改 RF 质量门（0.100）来让这些测试通过。

### S2 — 数字基线身份绑定

- **原缺陷**：`load_digital_baseline` 只核类别/编号，基线无 `source_id/version/模型` 绑定，
  其 `model_input_sha256` 未用于确立参考身份。真实 v1/v2 基线有相同 24 类身份
  （`V1_BASELINE_V2_CLASS_IDENTITY_ACCEPTED=True`），正确 v2 manifest + 误选 v1 基线不被拒。
- **修复**：新增冻结 sidecar `scripts/digital_baseline_identity.json`（随包冻结），映射
  `(source_id, conversion_version)` → 该基线的确切 TX manifest SHA + 数字基线 replay TSV SHA，
  并声明冻结 BF16 模型 json/raw SHA（`28272abc…`/`c1781aec…`）。判读器新增
  `--baseline-identity`（与 `--digital-baseline` 联用），`bind_baseline` 校验：
  - manifest SHA 不符 → `BASELINE_MANIFEST_SHA_MISMATCH`（分析失败 rc=1）；
  - 数字基线 TSV SHA 不符 → `BASELINE_TSV_SHA_MISMATCH`（分析失败 rc=1）；
  - 未命中身份 → `BASELINE_UNBOUND`；sidecar 声明的模型 json/raw SHA 与判读器内置冻结身份不符 →
    `BASELINE_MODEL_IDENTITY_MISMATCH`（防换模型）。
  - 文件模式另把数字基线每源 B 张量 SHA 绑定到 `--layers-dir` 同名 bin
    （`verify_digital_baseline_binding`，`DIGITAL_BASELINE_BINDING` 测量错误 rc=2）；设备模式
    **不**比较 RF C 张量与 B 层字节。
- **真实文件核验**：`bind_baseline` 对 real v1+v1 / v2+v2 均 0 错误；v2 manifest + v1 基线、
  v1 manifest + v2 基线均返回 `BASELINE_TSV_SHA_MISMATCH`。真实 v2 基线的唯一已知错
  source_index=21（AM-DSB-SC，class 20）→ recovered_pred=16（256QAM）；端到端用真实 v2
  manifest/数字基线/layers 复现「正确 v2 组合」：rc=0、`n_agree=24 n_same_error=1 n_new_flip=0`、
  `correct=23`、`byte_identical/digital_binding/board_tensor_files` 均 24/24。

### 反例测试与命令

- 判读器自测扩到 **13/13**（原 8 项 + S1 缺行 23/24、S1 非有限行 23/24、S2 正确 v2 组合接受
  （1 已知错 `n_same_error=1`）、S2 v1 基线 + v2 manifest 拒绝、S2 模型身份不符拒绝）。
- BOARDTEST §6 文件模式命令追加 `--baseline-identity scripts/digital_baseline_identity.json`。

本轮未改接收算法/模型/波形资产/恢复器/门限，未训练，未重跑 RF，未碰板，未 aarch64 编译。
