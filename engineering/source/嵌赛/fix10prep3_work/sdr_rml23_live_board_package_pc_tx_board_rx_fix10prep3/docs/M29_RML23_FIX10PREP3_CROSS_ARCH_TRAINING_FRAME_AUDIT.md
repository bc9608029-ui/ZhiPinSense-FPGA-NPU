# M29 RML23 — fix10prep3 跨架构确定性训练帧修复 审计（Batch 1）

> 状态：**`M29-RML23-FIX10PREP3-CANONICAL-FRAME-READY-FOR-BOARD-TEST`**（最高允许，canonical 离线交付态）
> 本任务是**离线交付**；ARM 探针与最终板测由用户执行，作者不碰板。
> 禁止写：`SMOKE-PASS / RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE /
> FINAL_*`。

---

## 1. 为什么做

真实双 SDR 链路被**训练帧跨架构字节不一致**堵住：PC/WSL x86 的 full burst SHA
`9d8420cd…`，板端 ARM 期望 `2e965828…`；三个共享头文件 SHA 一致、`payload_sha_post`
一致，只有 full 训练帧 burst 不同。根因：`iq_rf_training_frame.hpp` 用
`std::sin/std::cos/std::lround` 生成 Zadoff-Chu 前导/尾 + payload 训练块，x86/ARM
对这些浮点运算的舍入不同，「同一源码跨架构字节一致」不成立。

修复思路：把**前导 / payload 训练块 / 尾**三个非零训练组件从**当前 ARM 板端输出**
（权威）冻结成平台无关的小端 CI16 资产，PC 与板端都从冻结资产组装 burst。Batch 1
只**定位差异**，不冻结；没有 ARM 分段证据前，不用 x86 结果冒充权威训练帧。

---

## 2. 四个状态台阶（最高允许）

1. `M29-RML23-FIX10PREP3-X86-PROBE-COMPLETE-ARM-PENDING` — **本批交付态**（仅 x86
   分段结果，尚不知哪个分段与 ARM 不同）。
2. `M29-RML23-FIX10PREP3-CROSS-ARCH-DIFF-LOCATED` — 收到 ARM 分段、逐段比较后。
3. `M29-RML23-FIX10PREP3-CANONICAL-FRAME-READY-FOR-BOARD-TEST` — canonical 离线验证后。
4. `...-SMOKE-PASS` — 仅用户真实板测通过。

---

## 3. 基线

- 权威基线 = fix10prep2 正式 full 包（SHA `7d8c8f2f…`，635 文件），解压到本工作树
  `F:\嵌赛\fix10prep3_work\sdr_rml23_live_board_package_pc_tx_board_rx_fix10prep3\`。
- 冻结 D2 资产（`--frozen-dir`，两处字节一致）：`F:\嵌赛\fix10prep2_runtime\
  rml23_route_d2_rf_fix9_smoke23_1773377959\`，含 `route_d2_rf_manifest.tsv`
  （SHA `b7d3f666…`）+ 230 `.ci16` + 230 `.f32`。
- 四个红线头字节不变（§6 校验）：`iq_rf_training_frame.hpp` `d702cb58…`、
  `iq_digital_loopback.hpp` `b4f2a96c…`、`iq_pc_tx_board_rx_transfer_fix10.hpp`
  `f1454bd2…`、`iq_rf_sync_recovery.hpp`。

---

## 4. Batch 1 产物

### 4.1 x86 分段探针（§5.1，完成）

**新增** `host_tools/frame_component_digest.cpp`（iCraft/libiio 全免）+ 包装
`host_tools/frame_component_digest.sh`（WSL g++，内容寻址缓存）。接口：
`--frozen-dir --source-index --target-rms --out-dir --source-root`。读 manifest →
调 `iqpctbrx::build_tx_burst_from_frozen`（复用，不重写帧数学）→ 切 7 段写 CI16 +
SHA，另写 `frame_components.json`（含 7 段 SHA + `payload_sha_pre/post` + `tx_scale`
+ `full_burst_sha` + 三共享头 SHA + `endianness=little` + `sizeof_int16_t=2` 断言）。

**两样本各两跑，`target_rms=2048`，两跑 7 段 + JSON 全部 SHA 一致（确定性）**：

| 样本 | source_index | file | payload_sha_pre | payload_sha_post | tx_scale | full_burst_sha |
|---|---|---|---|---|---|---|
| BPSK | 405512 | `quantized_d2_2p56m_000006.ci16` | `b0c4ff066ee0…` | `efbfad0a4d21…` | 2.2915091544498973 | `9d8420cdebde…` |
| 4ASK | 192513 | `quantized_d2_2p56m_000002.ci16` | `abfe3f0e45b8…` | `67d2cb6680c7…` | 2.2918134810704101 | `527f00e8b3f3…` |

**BPSK full_burst_sha `9d8420cd…` 与任务书 §1 的 x86 SHA 精确一致**，证明探针复现了
现有 PC TX burst 生成。

**6 个组成区段（前导/零/payload 训练/缩放 payload/零/尾）SHA（跨样本一致）**：

| 区段 | SHA256 |
|---|---|
| preamble | `d4b4bb3af9ad…` |
| settling_zero | `ad7facb2586f…` |
| payload_training | `da3fadf4dc2b…` |
| guard_zero | `9f1dcbc35c35…` |
| tail | `ccddabe154b6…` |
| （scaled_payload = payload_sha_post，随样本） | — |

产物落 `results/x86_frame_components/<source_index>/run{1,2}/*.ci16` +
`results/x86_frame_components.json`。

### 4.2 ARM 探针源码 + 用户板端命令（§5.2，API 只出包，不碰板）

同一份 `host_tools/frame_component_digest.cpp` 即 ARM 探针源码（零改动，跨架构同一份）。
用户把 `host_tools/frame_component_digest.cpp` 拷到板端 fix10prep2 树根的
`host_tools/`（三个共享头与 fix10prep2 字节一致），执行：

```bash
cd <fix10prep2树根>
g++ -std=gnu++17 -O2 -Wall -Wextra -Werror \
  -I board_package -I sdr_adapter -I ui_sw \
  host_tools/frame_component_digest.cpp -o /root/frame_component_digest

mkdir -p /root/fix10_frame_probe_arm/405512 /root/fix10_frame_probe_arm/192513
/root/frame_component_digest --frozen-dir <D2_DIR> --source-index 405512 \
  --target-rms 2048 --out-dir /root/fix10_frame_probe_arm/405512 \
  --source-root <fix10prep2树根>
/root/frame_component_digest --frozen-dir <D2_DIR> --source-index 192513 \
  --target-rms 2048 --out-dir /root/fix10_frame_probe_arm/192513 \
  --source-root <fix10prep2树根>
```

`<D2_DIR>` = 已部署的冻结 D2 资产目录（含 `route_d2_rf_manifest.tsv` + 230 `.ci16`）。

**请用户返回**：每样本 **7 个 `.ci16`**（`preamble/settling_zero/payload_training/
scaled_payload/guard_zero/tail/full_burst`）+ `frame_components.json`（含 7 段 SHA +
`payload_sha_pre/post` + `tx_scale` + `full_burst_sha` + 三共享头 SHA +
`endianness=little` + `sizeof_int16_t=2`）。

### 4.3 PC 三个热修（§4，完成）

| 项 | 文件 | 内容 |
|---|---|---|
| §4.1 | `host_tools/fix10_iio_attr.py`（新）+ `pc_tx_sdr_fix10.py` | IIO 数值属性解析抽成纯模块（裸值/dB/Hz/空白/科学计数/畸形），`_rd_attr_ll/_rd_attr_d/_rd_dbg_ll/_tx_atten_readback` 全走它；解析错误在 thin alias 层转 `TxEngineError` |
| §4.2 | `host_tools/fix10_burst_cache.py`（新）+ `pc_tx_sdr_fix10.py` | `burst_cache_key` + `BurstCache` + `require_cached_burst`（纯函数，无 subprocess/iio）；`TxEngine.prepare_from_cache`（重验身份 + 只读缓存，绝不 WSL/g++）、`TxEngine.prewarm`、`--prewarm-source-index`（可重复）、main 先 prewarm 后 listen（`PREWARM …`→`listening …`）；`on_prepare` 只走 `prepare_from_cache` |
| §4.3 | `build_burst_cli.sh` | `TOOL_SHA` = 依赖闭包 + `FLAGS` + 编译器身份（`FLAGS` 作文本经 stdin 哈希）；二进制 `build_burst_cli.$TOOL_SHA` |

### 4.4 测试

- 新增 `host_tests/test_pc_tx_iio_attr_parse.py`（15 用例）、
  `host_tests/test_pc_tx_burst_cache.py`（10 用例），WSL `python3` 纯 stdlib；均 PASS。
- `run_tests.sh` 加两条 `python3 ./test_pc_tx_*.py || rc=1`。
- Windows radioconda `--self-test`：**27/27 PASS**，含新增 §4.1（Hz/dB/畸形/别名转
  TxEngineError）与 §4.2（prepare_from_cache 命中/未命中 fail-closed/身份失配/
  **零 subprocess 调用**）。
- 全量 host 回归（`build_host_tests.sh` + `run_tests.sh`）：**ALL HOST TESTS PASSED（exit 0）**，
  fix10 关键：`test_pc_tx_protocol_fix10` 49/0、`test_pc_tx_board_rx_fix10` 74/0、
  `test_pc_tx_provenance_fix10` 25/0、`test_iq_dual_sdr_fix10` 36/0、
  `test_iq_dual_sdr_23class_fix10` 29/0、`test_clean_iq_23class_fix10` 26/0；
  新增 Python `test_pc_tx_iio_attr_parse` 15/0 + `test_pc_tx_burst_cache` 10/0；
  `test_board_build.sh` 24/0、`test_rml23_build.sh` 7/0。fix10prep2 既有测试无回归。

### 4.5 板测前缓存键 hotfix1

首次真实联调发现：两个样本均已成功 `PREWARM`，但第一个 `PREPARE` 仍返回
`BURST_CACHE_MISS source_index=405512`。根因是 `BurstBuilder.build()` 中复用了变量名
`key`：语义缓存键随后被 SHA 字段校验循环覆盖，最终结果被写到字符串
`"burst_sha"` 键下。

修复仅涉及 `host_tools/pc_tx_sdr_fix10.py`：缓存元组改名为 `cache_key`，SHA
循环变量改名为 `sha_field`，并用 `self.cache.put(cache_key, result)` 入库。新增真实
builder 存储键自测后 Windows radioconda `--self-test` 为 **27/27 PASS**；使用正式
D2 资产执行 `prewarm -> prepare_from_cache` 生命周期验证，BPSK（405512）与 4ASK
（192513）均命中，canonical burst SHA 分别为
`2e965828737350ba5ece97fa3896cfe62f5d7b806532bafa237bc0a25339342e` 与
`7e8126fb37c300e05ed1c22e11c162cbfd919c9ab16e6030644fb48c41195754`。

该 hotfix 不改板端二进制、canonical 合同、模型或红线头；状态仍为
`M29-RML23-FIX10PREP3-CANONICAL-FRAME-READY-FOR-BOARD-TEST`，等待用户重跑烟测。

---

## 5. 红线（逐条不破，本批已守）

- 不改 `iq_rf_training_frame.hpp` / `iq_rf_sync_recovery.hpp` /
  `iq_digital_loopback.hpp` / `iq_pc_tx_board_rx_transfer_fix10.hpp`。
- 不 Python 复刻帧数学（探针复用 C++ `build_tx_burst_from_frozen`）。
- PREPARE 窗口内不启动 WSL/g++（§4.2 `prepare_from_cache` 只读缓存，零 subprocess 已证）。
- 不放松 2 秒超时。
- 没有 ARM 分段证据，不冻结 canonical、不用 x86 冒充权威训练帧。

---

## 6. 下一步（PAUSE）

**停下等用户返回 ARM 组件文件**（§15 硬停）。收到后：①逐段比较 x86 vs ARM 定位第一处
差异（component/int16_index/x86_value/arm_value/delta），写 `CROSS-ARCH-DIFF-LOCATED`；
②无论 x86 是否一致，一律以 ARM 输出冻结 canonical（ARM=权威）；③再进入 Batch 2
（冻结 canonical、接线 PC+board、完整离线测试、打包停在 READY-FOR-BOARD-TEST）。

---

## 7. 打包（§12/§13）+ 状态

**canonical 训练帧已冻结**：三个非零训练组件以 ARM（aarch64）板端权威输出冻结为
平台无关小端 CI16 资产，落在 `contracts/fix10_canonical_frame_v1/`（`manifest.tsv`
3 行契约 + `preamble.ci16` / `payload_training.ci16` / `tail.ci16` + `SHA256SUMS.txt`）。
canonical 组件 SHA（`fix10_canonical_frame_v1` 契约）：前导 `d4b4bb3af9ad…`、payload
训练块 `f06e9b3de0f5…`、尾 `ccddabe154b6…`。PC TX 与板端 RX 都从编译期内嵌资产组装
full burst（新增 `board_package/iq_fix10_canonical_frame.hpp` 接口 +
`iq_fix10_canonical_frame_data.hpp` 字节数组，由
`scripts/generate_fix10_canonical_frame_header.py` 从冻结资产确定性生成），跨架构字节一致。

**打包变更集 = fix10prep2 的完整增量**：**20 NEW + 10 MODIFIED**（patch 内容文件 30 个）。
这包括双 SDR 专用分数时序 wrapper、对应 C++ 回归测试，以及独立热修审计文档；
红线恢复核心与全部原门限仍保持不变。
新增含两个 canonical 板端头、`contracts/fix10_canonical_frame_v1/` 5 文件、本审计档、
`frame_component_digest.{cpp,sh}` 探针、§4 三个 PC 热修模块（`fix10_iio_attr.py` /
`fix10_burst_cache.py`）+ 其测试、canonical 帧测试 + fixtures、canonical 头生成器与
本 packager；修改为 8 个 PC 热修/测试接线文件（`iq_pc_tx_board_rx_23class_fix10.hpp` /
`pc_tx_sdr_fix10.py` / `fix10_tx_protocol.py` / `build_burst_cli.{cpp,sh}` / 测试脚本）。
顶层 `SHA256SUMS.txt` 由 packager 重新生成，**不进 patch**（它列出全树；patch 自带
`FIX10PREP3_PATCH_SHA256SUMS.txt`）。

**六道 fail-closed 审计全部 OK**（任一 FAILED 即退出、不产包）：

1. **红线头审计** — 6 个恢复/帧数学/传输/provenance 状态机/同步契约头
   （`iq_rf_sync_recovery.hpp` / `iq_rf_training_frame.hpp` / `iq_digital_loopback.hpp`
   / `iq_pc_tx_board_rx_transfer_fix10.hpp` / `iq_rf_fix9r_baseline.hpp` /
   `iq_clean_baseline.hpp`）与 fix10prep2 逐字节一致 → 恢复核心/同步数学/CFO/SRO/削顶
   阈值零改动。
2. **受保护目录审计** — `model_rml23/ model_12class/ contracts/ deployment_golden/`
   （模型/权重/标签/预处理/24→23 映射/门禁）与 fix10prep2 逐字节一致 → 无任何模型域
   改动。
3. **依赖闭包审计** — 每个新增 C++ 文件的每个引号 include 都在树内解析 → 无悬空引用。
4. **complete-delta 审计** — 全树每个文件要么与 fix10prep2 逐字节一致、要么在 patch 内
   → patch + fix10prep2 基线精确重现全树（无「改了但没进 patch」的漏网文件）。
5. **old-fix10 零残留** — 无 `external_rf` / `pluto_external` 残留 → 旧 fix10 核心未泄漏。
6. **patch 自包含审计** — patch 单独覆盖到 fix10prep2 基线上即可解析全部 patch C++ 文件
   的 include → patch 独立可消费，不依赖全量包。

**dist/ 工件**（独立解包 + `sha256sum -c` 自检全 PASS）：

- `sdr_rml23_fix10prep3_canonical_frame_patch.tar.gz`（30 内容文件）+ 侧车
  `FIX10PREP3_PATCH_SHA256SUMS.txt`。
- `sdr_rml23_fix10prep3_canonical_frame_boardtest_full.tar.gz`（655 内容文件）+ 侧车
  `sdr_rml23_fix10prep3_canonical_frame_boardtest_full.SHA256SUMS.txt`。
- self-check：patch 30/30 PASS、full 655/655 PASS。

**两跑确定性**：packager 全确定性（tar uid/gid=0、mtime=0、条目排序；gzip level 9、
mtime=0）。本段定稿后连续两次运行、中间零改动，patch/full tarball 两次 SHA 一致
（确定性成立）。tarball 的 gzip SHA256 不入本档（本档在包内，记录即自引用），两跑
一致性与具体 SHA 见交付报告。

**状态推进**：x86 探针（§4.1）→ ARM 分段返回并定位差异（§2 第 2 阶，历史）→ ARM
权威输出冻结 canonical（本 §7）→ 本档状态推进为
`M29-RML23-FIX10PREP3-CANONICAL-FRAME-READY-FOR-BOARD-TEST`（最高允许，canonical 离线
交付态）。下一步仅剩用户真实板测（§2 第 4 阶，作者不碰板）。
