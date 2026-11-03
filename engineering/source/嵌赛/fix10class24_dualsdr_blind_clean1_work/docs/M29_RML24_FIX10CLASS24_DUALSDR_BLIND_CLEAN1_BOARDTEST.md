# fix10class24-dualsdr-blind-clean1 — 双 SDR 盲测（无样本先验）纯净调制分类（就绪待上板）

## 状态

**`M29-RML24-FIX10CLASS24-DUALSDR-BLIND-CLEAN1-READY-FOR-BOARD-TEST`**

- 本环境**无板端访问通道**（无 SSH/串口/MCP 板端工具），故**尚未执行任何板端 RF 收发/推理**。
- 已完成：盲测 TX 载荷生成（frozen 常量）、PC TX 服务、板端盲测 runner（新 phase + header + gate9 接线）、
  主机三层对照数字回放 + 判定器（含结论分流）、编排脚本、打包器、离线只读核验。
- **不得报告「已测过」**。板端数字回放/真 RF 测量行留空，等真实输出回填。

## 任务问题（盲测：接收端无样本先验）

PC 用**纯调制器**生成 24 类 RadioML2018.01A 纯净 IQ（无训练帧、无前导、无尾、无 canonical burst），
经 PC SDR 发射 → 50Ω 同轴 → 板 SDR 接收，接收端**只用接收 IQ + 冻结 BF16 模型 + 冻结恢复尺度 + 冻结窗口规则**
给出 raw24 分类。接收端**永远不知道**发射样本、其 DC/尺度、正确窗口、或标签。

这是**测量**（`ROUTE_F_RADIOML_BLIND_CLEAN1_*`），不是新模型优化：不训练、不改模型、不改预处理/恢复器/门限。

### 三层对照（协调员要求 1：同一批样本 + 同一冻结模型）

| 层 | 输入 | 回答 |
|---|---|---|
| **A 原始** | `generate_class(name, seed)` → 冻结 BF16 | 参考基线（离线） |
| **B 数字精确** | A 的 CI16 量化 → `z=int16/2048*rx_scale` 重建 → 同模型 | 量化/重建损失（无 RF） |
| **B′ 数字旋转窗** | B 经冻结盲窗口 `[512,1536)` 截取 → 同模型 | 固定盲窗口的确定性代价（无 RF） |
| **C SDR 接收恢复** | 板 SDR 真实接收 → 同冻结重建+窗口 → 同模型 | 完整 RF 链路后的准确率变化 |

原始参考 IQ（层 A）**仅供离线分析**，禁止进入接收推理路径（盲测红线）。

### 逐层统计（协调员要求 2）

每样本、每层记录：准确率、预测翻转、输入 RMS / DC(实/虚)、
对齐后相关性 `corr=|a^H b|/(||a||·||b||)` + 归一化残差 `resid=||b−a||/||a||`。

### 全量留存（协调员要求 3）

板端逐样本落盘：`<source_index>.raw.i16`（全 2048 复数捕获）、`<source_index>.tensor.bin`（最终 [2,1024] f32 模型输入）、
`<source_index>.diag.json`、`board_logits.tsv`（24 logits + pass1/pass2 预测）、`board_results.tsv`（22 列）、`board_summary.json`。
数字回放落盘 `layers/<sid>.{orig,exact,rotated}.tensor.bin` + `layers/<sid>.logits.tsv`。
**失败样本不从分母删除**（门拒/hard_invalid 同样落盘且计分母）。

### 结论分流（协调员要求 4，不写死唯一归因）

判定器 `route_conclusion()` 输出：问题最先出现在 **预处理（A→B）/ RF 恢复链（B→C）/ 恢复后模型鲁棒性（C 内）**，
按证据排序，证据不足标 **待确认**；显式 `no_single_attribution_guaranteed: true`。

### 本轮不自动扩展（协调员要求 5）

多抽头均衡、避零频传输、RF 微调**只作为有证据后的候选**，另做 A/B，本轮不一次全加。
判定器显式记录 `candidates_not_applied_this_round`。

## RX 信息边界（盲测红线）

**可用**：接收 IQ、冻结 BF16 模型（json `28272abc…`/raw `c1781aec…`/ckpt `96cd25f8`）、
公共 RX 配置（LO/采样率/BW/增益，全样本固定）、冻结恢复尺度 `rx_scale`、冻结窗口规则、匿名 `run_id`。

**禁止**：发射样本/参考 IQ、DC/AC-RMS/TX 尺度/任何 sidecar、类别/基线预测/`source_index→class` 映射、
冻结规则之外的正确起点/窗口、TX 波形模板。`run_id` 匿名，不编码类别，不进 DSP 路径。

## 冻结常量（权威：contract/blind_rx_sampling_contract.json）

| 常量 | 值 |
|---|---|
| `tx_scale` S | `117.84922023433009`（=1600/max_peak，全类单一尺度） |
| `rx_scale` | `17.37813789457223`（=2048/S） |
| `adc_full_scale` | `2048.0` |
| `max_peak` | `13.576670230134553`（AM-SSB-WC, seed `3000017`） |
| `max_lround_ci16_abs` | `1599`（<2048 无 clip；连续峰值 1600，lround 实/虚分开舍入） |
| `seed_base` / `shuffle_seed` | `3000000` / `20261020` |
| 窗口 | flush 4096 ×2 → capture 2048 复数连续 → window `[512,1536)` =1024 复数 |
| 采样/LO/BW/增益/衰减 | 2.56 Msps / 2.4 GHz / 18 MHz / RX 35 dB / TX −40 dB |
| measurements | 25（1 负控 + 24 波形） |

CI16 量化 = `lround(x·S)`，**half-away-from-zero（非 numpy.rint）**，逐字节红线。
重建 `z[k]=int16[k]/2048*rx_scale`。

## 协议（PC TX = 服务端 :39010，板 RX = 客户端）

```
board→PC: HELLO → HELLO_ACK → [TRANSMIT(source_index) → TX_READY → flush+capture+window+infer×2 → CAPTURED → CAPTURED_ACK]×25 → STOP → STOP_ACK
```

`source_index` 是板端唯一知道的关联键：0=负控/TX-off，1..24=波形序号（类永不跨控制通道）。

## 离线只读核验（主机侧）

- `host_tests/test_radioml_blind_clean.py` **14/14 PASS**（frozen 常量自洽、lround 半远离零、逐字节重建、source_index 双射、量化解）。
- `scripts/radioml_blind_clean_contract.py --self-test`（TX 载荷生成自检）。
- `scripts/digital_replay_radioml_blind_clean.py --self-test`（三层数字回放，需 `D:\icraft\bin\icraft-run.exe`）。
- `scripts/judge_radioml_blind_clean.py --self-test`（判定器自测：无失败阶段 + 无扩展候选）。
- **板端 C++ 编译**：`g++15.2.0` 在冻结标量 WL 头 `iq_rf_loopback_24class_bf16_scalarwl_core.hpp:352` sign-compare `-Werror` 崩溃
  （非本任务改动）→ 本测一次性 `-Wno-error=sign-compare`；`make -j1` 单线程。**本环境不 aarch64 编译**——板端构建由用户执行，未声称两端核验。

## 板端执行（用户串口执行；本环境无法连接板端）

前置：**PC SDR TX 与板 SDR RX 用 50Ω 同轴直连**；板端 **RX-only**（永不打开 TX 设备、无本地 TX、loopback=0）。

### Step 1 — 应用 PATCH + 布放 INPUTS（tx 载荷包）

PATCH 增量覆盖 npu-ab1 基线树（gate9_phase/board_gate9 的 diff 基 = dc-ab1）；INPUTS 包解压出 24 个 `.i16` + `blind_tx_manifest.tsv`。

### Step 2 — PC 启动盲测 TX 服务

```bash
D:\radioconda\python.exe -I host_tools/pc_tx_blind_clean.py \
    --listen 0.0.0.0:39010 --tx-uri "<PC_TX_URI>" --tx-dir "<blind tx package dir>"
```

### Step 3 — 板端跑盲测（RX-only，显式 24 类 BF16 + --rx-gain=35）

```bash
bash scripts/run_radioml_blind_clean.sh \
    --tx-control=tcp://<PC_IP>:39010 \
    --rx-uri="<board RX SDR URI>" \
    --out-dir=/root/rml24_blind_clean_$(date +%s)
```

### Step 4 — 主机离线判定（数字回放 + 三层对照 + 结论分流）

```bash
python -I scripts/digital_replay_radioml_blind_clean.py --tx-dir <tx-dir> --out-dir <fresh>
python -I scripts/judge_radioml_blind_clean.py \
    --tx-dir <tx-dir> --board-results <OUT_DIR/board_results.tsv> \
    --digital <digital_replay.tsv> --out-dir <fresh judge dir>
```

## 六项统计（判定器输出）

1. 24 样本完成度（全在场无缺失）
2. 端到端正确 / 24（**失败保留分母**）
3. 准确率 + 覆盖（过门/门拒分列）
4. 每类预测混淆异常
5. 数字 vs 真实 RF（B→C 翻转）
6. 负控结果（source_index 0 = TX off）

## 交付物

| 类别 | 文件 |
|---|---|
| 板端 | `board_package/iq_blind_rx_24class_bf16_fix10.hpp`（新）、`gate9_phase.hpp`（+1 phase）、`board_gate9_full_chain_rml23.cpp`（include+wrapper+error-text+dispatch） |
| 契约 | `contract/blind_rx_sampling_contract.{json,md}` |
| TX | `scripts/radioml_blind_clean_contract.py` + `scripts/radioml_clean_contract.py`（clean2a vendored verbatim） |
| PC | `host_tools/pc_tx_blind_clean.py` |
| 离线 | `scripts/digital_replay_radioml_blind_clean.py`、`scripts/judge_radioml_blind_clean.py` |
| 编排/打包 | `scripts/run_radioml_blind_clean.sh`、`scripts/package_radioml_blind_clean1.py` |
| 测试/文档 | `host_tests/test_radioml_blind_clean.py`、`docs/M29_RML24_FIX10CLASS24_DUALSDR_BLIND_CLEAN1_BOARDTEST.md` |

## 红线（逐字节不变）

冻结模型 json/raw/ckpt、24 类标签序、clean2a 生成器（`radioml_clean_contract.py` SHA `aa5fe816…`）、
0.100 门/恢复/预处理**全部不碰**（本测不使用恢复链，但也不改动）；TX ≤ −40 dB 安全上限；板端无 TX。
