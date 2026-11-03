# 并行线 B — 板端采集手册（BOARD_CAPTURE_RUNBOOK）

任务：`M29-RML24-REALRF-FINETUNE-PILOT1` / 线 B `pilot1_capture_chain`

**执行人 = 用户（串口 COM12）**。我（离线侧）不碰板、不发射、不操作 SDR。本手册给
出 4 个会话（S1/S2/S3/S4，各 240 帧）的完整采集流程；Ethernet 只传整轮控制 + 样本身份
+ SHA，不传逐样本恢复真值、不传实时 IQ。

> 拓扑：Windows PC 拥有 **TX SDR**（`host_tools/pc_tx_radioml_dualsdr.py` 服务，SERVER）；
> 板端拥有 **RX SDR**（`scripts/run_pilot1_capture.sh`，CLIENT）。两端经 TCP 控制通道
> (`--tx-control`) 走严格 HELLO→PREPARE→PREPARED→START→READY→CAPTURED→STOPPED 状态机。

## 0. 采集矩阵

| 会话 | 角色 | 帧数 | 每类 |
|---|---|---|---|
| S1 | train | 240 | 10 |
| S2 | train | 240 | 10 |
| S3 | validation | 240 | 10 |
| S4 | sealed_test（模型/超参确定前不接触） | 240 | 10 |

RF 配置（冻结 C4）：center 2.4 GHz / sample-rate 2.56 Msps / rx-bw 18 MHz / tx-bw
18 MHz / rx-gain 35 dB / tx-atten -40 dB / TX 数字缩放=固定公开常数 S（`TX_DIGITAL_SCALE`，
target-rms 0，非逐样本幅度）/ 直连 cable（`--rf-path=direct-cable`）。

## 1. 部署包与离线资产（我已产出，用户只需校验）

单一部署包（`dist/` 内的 tar.gz + SHA256SUMS）含两部分，部署到**两个位置**：

```
# (A) 板端树（串口 COM12 上板；C++ 采集 runner + 脚本 + 二进制）
board_package/pilot1_capture_runner.hpp     # 板端 RX 采集 runner（save-before-gate）
board_package/pilot1_capture_schema.hpp     # 32 字段 schema
board_package/pilot1_tx_manifest.hpp        # 3 列 TX 公共 manifest 加载器（fail-closed；无真值）
board_package/board_gate9_full_chain_rml23.cpp  # phase 接线（iq-pc-tx-board-rx-24class-finetune-pilot1）
board_package/gate9_phase.hpp               # 合法 phase 增加 pilot1 phase
scripts/run_pilot1_capture.sh               # 板端 RX 采集 wrapper（本手册 2.2 使用）
host_tests/test_pilot1_capture.cpp          # host 侧 loader/schema 回归（34/0）
host_tests/pilot1_capture_runner_syntax.cpp # full-runner -fsyntax-only（评审 39e5 Blocker 1）

# (B) PC 侧（Windows radioconda；TX 服务 + 3 列身份 / 5 列 payload manifest 加载器）
host_tools/pc_tx_radioml_dualsdr.py         # PC TX 服务（SERVER）
host_tools/pilot1_tx_manifest.py            # 纯 stdlib 3 列身份 + 5 列 payload 加载器

# (C) 数据（同一份 tx_payload 复制到 PC 与板端两处）
line_b/tx_payload/S1/{tx_manifest.tsv, tx_payload_manifest.tsv, SHA256SUMS.txt, 240×<source_id>.i16}
line_b/tx_payload/S2/…  S3/…  S4/…         # 每会话 240 个 CI16 payload
line_a/inputs/S{sn}/{source_id}.bin         # 960 源 IQ（数字基线用，非 TX）
line_a/results/source_manifest_960.tsv      # 主机真值 9 列（**仅主机侧**，绝不下发板端）
contract/shared_contract.py                 # 32 字段 + 冻结身份 + 红线（只读）
```

TX payload 由 `export_finetune_tx_payload.py` 生成（类无关、确定性、clip=0）。
`source_id` 格式 = `s{sn}_c{ci:02d}_i{inst:02d}`（如 `s1_c00_i00`），10 字符。

## 2. 每会话采集流程（S1 为例，S2/S3/S4 同）

> **PC 侧先起 TX 服务**（服务启动时自动把本会话 240 个 dataset_index 全部 prewarm 进
> 缓存，listen 后 PREPARE 只读缓存、绝不调 WSL/g++）；**板端后起 RX**。

### 2.1 PC 侧（TX server，radioconda，PC 上连接 TX SDR）
```sh
D:\radioconda\python.exe -I host_tools\pc_tx_radioml_dualsdr.py ^
    --listen 0.0.0.0:39010 ^
    --tx-uri "<PC_TX_URI>" ^
    --tx-payload-dir line_b\tx_payload\S1 ^
    --input-kind radioml-finetune-pilot1 ^
    --center 2400000000 --sample-rate 2560000 --tx-bw 18000000 --tx-atten -40 ^
    --rf-path direct-cable --rf-tx-target-rms 0

`radioml-finetune-pilot1` 的 `target-rms 0` 表示 payload 已按公开固定幅度 S 量化，禁止临时改成
2048 绕过错误；PC HELLO 解析器必须来自 SHA
`d9fe89704032a004de71bddc7733f7e86080f147182ddb71112aa204810e3e66` 对应的新 PATCH。
```
- `--tx-payload-dir` 指向含 `tx_manifest.tsv` + `tx_payload_manifest.tsv` + 240 个 `.i16`
  的目录（会话 S1..S4 各一次）。
- 服务把 `tx_manifest.tsv`（3 列）的 SHA-256 作为控制通道身份；与板端不一致即 fail-closed 拒绝。
- 服务**不在 START 之前发射**；只有板端 PREPARE→START 授权后才 cyclic 发射，CAPTURED/断开即停。

### 2.2 板端侧（RX producer，串口 COM12）
```sh
# 1. 只读校验模型 SHA（fail-closed；期望值逐字一致）
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.json \
          model_rml24_bf16/rml24_adamrv11_bf16.raw
# 期望 json 28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42
# 期望 raw  c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151

# 2. 构建（评审 39e5 Blocker 1 收口项——在部署树根目录跑，确认 ok_pred 顺序修正 + 全链
#    在 aarch64 下链接通过。脚本在 scripts/ 下，需 LIBIIO_ROOT + ICRAFT_CMAKE_DIR 环境）
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 \
ICRAFT_CMAKE_DIR=/usr/cmake \
taskset -c 0 bash scripts/build_on_board.sh
# 构建成功必须看到以下两行（缺一/出现 result=FAIL 即不得进入采集）：
#   NPU_BUILD_RESULT gate=9R result=PASS
#   RML23_BUILD_RESULT result=PASS

# 3. 跑采集（save-before-gate：每个 source_id 无条件先落 raw_rx + 32 字段行）
bash scripts/run_pilot1_capture.sh \
    --tx-manifest=/root/pilot1/tx_payload/S1/tx_manifest.tsv \
    --out-dir="$OUT" \
    --tx-control=tcp://<PC_IP>:39010 \
    --rx-uri="ip:192.168.2.1" \
    --rf-path=direct-cable \
    | tee run_S1.log
```
- **构建门禁**：仅当看到 `NPU_BUILD_RESULT gate=9R result=PASS` 与
  `RML23_BUILD_RESULT result=PASS` 两行后，才允许进入四会话采集；任一 `result=FAIL`
  或两行缺失即停止，回传构建日志。
- `--rf-path=direct-cable` **必填**（50-ohm SMA 直连，无天线、无放大器）；否则板端 fail-closed 拒绝。
- `--tx-manifest` 指向会话目录的 `tx_manifest.tsv`（**3 列**：session_id/source_id/
  tx_payload_sha256，无类别真值、无逐样本幅度；`.i16` 已按固定公开幅度 S 量化，由 PC 端
  读，板端不读 `.i16`）。
- 板端只开 RX SDR，无任何 TX API。

### 2.3 产出（回传 $OUT）
```
$OUT/capture_results_S1.tsv              # 32 字段逐样本行（门拒/失败也写行，不剔分母）
$OUT/capture_summary_S1.json             # 采集口径汇总（rows/capture_ok/…/functional_pass）
$OUT/<source_id>.raw_rx.i16              # 门控前 raw RX（240，直接落 $OUT 下，非子目录）
$OUT/<source_id>.model_input.bin         # [2,1024] f32 张量（仅 rec.valid，240 或更少）
$OUT/<source_id>.logits.bin              # 24 logits（仅 rec.valid）
$OUT/run_S1.log
```
> 注意：`raw_rx` / `model_input` / `logits` 均直接写在 `$OUT` 下（`<source_id>.xxx`），
> **不是** `$OUT/S1/` 子目录。

## 3. 关键纪律

1. **S4 密封**：采集 S4 前不得依据 S1/S2/S3 结果修改任何恢复参数、门限、模型、超参；
   S4 采完解封一次用于最终判级，之前不接触。
2. **不剔分母**：缺帧、门拒、无同步、削顶、hard-invalid 一律在 32 字段里记行，不删除。
3. **门拒仍保存**：门拒样本仍落 `model_input.bin`/`logits.bin`/预测，标 `gate_pass=0` +
   `failure_token`；不得伪装生产结果。
4. **接收端不读真值**：RX 热路径不消费 class_index/label/dataset_index/split/source_iq_sha256；
   这些列板端置空，采集后由主机真值清单 `line_a/results/source_manifest_960.tsv` 离线按
   source_id 回填（`gt_join.py` fail-closed 断言板端未带回真值）。
5. **有界重捕获 ≤3**：失败帧至多重捕 3 次，末次结果为准。

## 4. 回传后（离线判读，非本手册范围）

用户把 `$OUT` 回传后：`line_c/judge_realrf_pilot.py --capture-tsv <32字段TSV>
--baseline-tsv line_c/results/digital_baseline_960.tsv` 出六选一判级（见 METRIC_CONTRACT）。

## 5. 停止条件

采集链离线资产全部就绪 + 24 帧端到端模拟通过即 `READY_FOR_BOARD_CAPTURE`；不写
RF_PASS / PROJECT_COMPLETE / FINETUNE_SUCCESS。板端采集由用户执行，我不自动连接板子。
