# Task C 回报：fix1+v2 交付核验 + 板测命令 + 冻结判读基线

日期 2026-10-20（纯离线；不碰板 / 不发射 / 不训练）。

结论一句话：**数字/离线侧完整正确（4 包 SHA 匹配、依赖齐全、phase 接线上下文正确、
补丁不互相覆盖、v2 数字基线已冻结）；板端 C++ 侧有 4 处缺口（G1..G4）在补齐前**
**block 板端构建/运行**，须如实上报。

---

## 第 1 点：逐项核验清单（PASS/FAIL + 实际 SHA）

### 1.1 包层面整体 SHA（PASS — 已修复 F0 双 gzip 缺陷后重算）

| 包 | 新 SHA256（修复后） | 字节 |
|---|---|---|
| fix1 PATCH | `dea9e391f09cad39352ee447f4e890e61fadbb772f88d2a95db771609477cef7` | 40953 |
| fix1 INPUTS | `cef55be5a5c773457b73802191616e863b2b1d4d254cb3aeae7f2ccc607c483c` | 226851 |
| v2 PATCH | `83548e0ff7de100161b0ed3c2004b4bab7c2ce40a07917d11a4c1a9079f979c8` | 33856 |
| v2 INPUTS | `1743b784f8d4b2f3663b850b4982175c7c36074ea33d490210c15438a4c1d320` | 227032 |

**F0（已修复）**：原 4 个交付 tar 是 `gzip(gzip(tar))`（打包器用了 `tarfile.open(mode="w:gz")`
后又包一层 gzip），标准 `tar xzf` / Python `tarfile r:gz` 均**无法解包**。已把两个打包器
`mode="w:gz"` → `mode="w"`（内存未压缩 tar + 单层 gzip mtime=0），重新打包。旧包保留在
`dist_doublegzip_BROKEN/`。上面的 4 条 SHA 是**新包**的 SHA（原交付报文里的
`06c3ce49…/898bcaa5…/c0c43565…/c8d533f2…` 是旧双 gzip 包，作废）。新包 4/4 已实测
`gzip.decompress` + `tarfile r:` 解包成功，成员数 fix1 PATCH 17 / fix1 INPUTS 27 /
v2 PATCH 14 / v2 INPUTS 27。

### 1.2 包内 SHA256SUMS 一致性（PASS）

`sha256sum -c` 级别逐文件复算：fix1 INPUTS 24/24、v2 INPUTS 24/24，0 不匹配。

### 1.3 依赖文件齐全（PASS）

- fix1 PATCH 17 文件 = 脚本 9（contract/waveform_correctness/public_protocol_tx/
  independent_rx_replay/judge/package + 4 vendored）+ board 2（runner.hpp + gate9_wiring.patch）
  + contract 3（amplitude_contract.json/.md + waveform_correctness.json）+ host_tests 1 + docs 2。
- v2 PATCH 14 文件 = 脚本 6（waveform_correct_v2/v2_contract/v2_tx/v2_replay/judge/package
  + 4 vendored）+ contract 2（v2_waveform_definitions.md + v2_waveform_correctness.json）
  + host_tests 1 + docs 1。
- 4 个 vendored 冻结文件 fix1↔v2 逐字节相同（见 1.5）。

### 1.4 phase 接线正确性（PATCH 上下文 PASS；shim 缺失 FAIL）

phase 名 `radioml-independent-rx-public-protocol-24class-bf16-fix1`。

`gate9_wiring.patch` 对 dc-ab1 基线树的 4 处插入点上下文**逐行匹配**，可干净应用：
1. `gate9_phase.hpp` `valid_phase`（`radioml-original-singlesdr-ab…` 之后新增）；
2. `board_gate9_full_chain_rml23.cpp` `#include "radioml_independent_rx_runner.hpp"`
   （第 74 行 singlesdr include 之后）；
3. usage 提示串（第 3837 行 singlesdr 之后新增该 phase）；
4. dispatch（第 3901 行 singlesdr dispatch 之后新增
   `rc = run_radioml_independent_rx(npu, contract, out, sock, timing, argc, argv);`）。

**FAIL G1（编译失败）**：第 4 处 dispatch 引用的 7 参 shim
`run_radioml_independent_rx(npu, contract, out, sock, timing, argc, argv)` 在 cpp 中
**未定义**。dc-ab1 cpp 里已有同形状 shim 的是 npu(3203)/dualsdr(3250)/singlesdr(3303) 三个，
唯独缺 independent_rx。patch 注释声称它是「thin board_gate9 shim … passes through to
iqindepfix1::run_radioml_independent_rx(argc, argv, on_frame)」，但该 shim 体不存在 →
`make` 时 undefined reference，**无法构建**。

### 1.5 补丁不互相覆盖（PASS，但 INPUTS 须分目录）

- **PATCH 层面**：fix1-only 13 文件、v2-only 10 文件、共享 4 vendored 逐字节相同。v2 对
  脚本是 ADDITION（新增 v2_* 模块），不覆盖 fix1。共享 4 文件全文 SHA：
  - `radioml_clean_contract.py` `aa5fe816dbfddbd26512ac2240c504eccfe3769293aac2fbf2caf7c172fa76d5`
  - `radioml_dualsdr_common.py` `0839fc407d793787db33371be5614c9d8aa1857b685ef1d711c76e289ab3329c`
  - `radioml_dualsdr_burst.py` `df5ff7008a11df68201f69e53f6bb8e84afb4e574f4af9cceef05c29a39f96e6`
  - `radioml_independent_rx_contract.py` `207552e21f627680b2fe7b0dc7982ea0fbf79804b167f5528d7cd5b09cd94b86`
- **INPUTS 层面**：24 个 burst 文件名相同，但 **0/24 逐字节相同**（v2 是波形 REPLACEMENT，
  fix1 source_id=`fix1-public-protocol-24waveforms`/v1，v2 source_id=
  `fix1v2-waveform-corrected-24waveforms`/v2）。**必须各自解到独立目录**，否则互相覆盖。

### 1.6 包内 SHA256SUMS 与整体 tar SHA 一致（PASS，附 G5 次要说明）

`dist_manifest.json` 内记录的 PATCH/INPUTS 整体 SHA 与实际文件 SHA 4/4 一致（见 1.1）。
INPUTS 两包内 `tx_package/SHA256SUMS.txt` 逐文件 24/24 一致（见 1.2）。

**G5（次要，非阻塞）**：fix1/v2 的 **PATCH 包内无逐文件 SHA256SUMS**（仅 INPUTS 有），
故解包后 `sha256sum -c` 只能对 INPUTS 做，PATCH 文件只能靠解包前整体 tar SHA（Step 2）保护。
（dc-ab1 dualsdr 的 PATCH 曾带独立 `…_PATCH_SHA256SUMS.txt`，本次 fix1/v2 未带。）
整体 tar SHA 已足够保证内容未被篡改，G5 只是少一个解包后逐文件便利校验，不 block。

### 1.7 板端 C++ 完整性（4 缺口，FAIL — block 板端运行）

| 缺口 | 位置 | 现象 | 后果 |
|---|---|---|---|
| **G1** | gate9_wiring.patch dispatch | 7 参 shim 未定义 | 编译失败 |
| **G2** | runner.hpp 第 254 行 | `rx_int16` 声明但永不填充（捕获体注释「照抄 dualsdr」）| 无法真实捕获 RX |
| **G3** | runner.hpp 第 118-122 行 | `load_independent_rx_manifest` fail-closed 只接受 source_id=`fix1-public-protocol-24waveforms` 且 conversion_version=`v1`；v2 无任何 board runner | **拒绝 v2 manifest**，v2 波形无法上板 |
| **G4** | 整个 fix1/v2 交付 | 无 PC TX 服务（39010 SERVER）；只有 build-only 的 `radioml_public_protocol_tx.py`（产 tx_package，不监听 39010 不发 SDR）| PC 侧无法驱动 TX SDR 发公共协议 burst |

G2/G4 补充：runner 头部注释明确要「逐字复用 dualsdr 的负控 + `iqpctbrx` 控制通道 +
`board::capture_contiguous`」，但 fix1 交付里既没有这段捕获实现（stub），也没有
dualSDR 那套 `pc_tx_radioml_dualsdr.py` 的公共协议版 PC TX 服务。dc-ab1 有
`pc_tx_radioml_dualsdr.py`（发 dualsdr payload），无公共协议版。

> 结论：fix1/v2 交付的**数字/离线侧**（波形、合同、SHA、回放、判读）完整；
> **板端侧**是「接线 patch + 恢复核心骨架 + TX 包」，未到可构建/可运行状态。
> 在 G1..G4 补齐前，不能声称 `READY-FOR-BOARD-TEST`。

---

## 第 2 点：板测命令块（COM12；含 BLOCKED 标注）

> 下列命令按既有 dc-ab1 dualsdr 上板流程（`docs/…_DUALSDR_BOARDTEST.md`）编排，可直接
> 粘贴；但 **Step 5 构建 / Step 6 PC-TX / Step 7 运行** 受 G1..G4 影响，**在补齐前会失败
> 或无从执行**，已逐处标注，不混入 `PS>`/示例输出。

### Step 1 — 只读核验基线项目 + 冻结模型（不覆盖）

```bash
PROJ=/root/fix10class24_original_radioml_dc_ab1   # 例；以实际 dc-ab1 部署目录为准
if [ ! -d "$PROJ" ]; then echo "MISSING $PROJ — 候选:"; ls -d /root/fix10class24* 2>/dev/null; fi
cd "$PROJ" || exit 1
echo "== 二进制 =="; ls -l bin/board_gate9_full_chain_rml23 2>/dev/null
echo "== 冻结 24 类 BF16 模型 SHA（须等于冻结值）=="
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.json model_rml24_bf16/rml24_adamrv11_bf16.raw
# 期望: 28272abc…  .json  /  c1781aec…  .raw
```

### Step 2 — COM12 上传 4 个 tar.gz，逐包校验整体 SHA

用既有串口文件传输（ZMODEM `rz`/`sz` 或 base64）把 dist/ 下 4 个 tar 传到 `/root/`，逐个
校验整体 SHA（**任一不符立即停**）：

```bash
cd /root
sha256sum fix1_independent_rx_PATCH.tar.gz
sha256sum fix1_independent_rx_INPUTS.tar.gz
sha256sum v2_waveform_correct_PATCH.tar.gz
sha256sum v2_waveform_correct_INPUTS.tar.gz
# 期望（本报告 1.1 四条 64 hex）:
#   dea9e391…  /  cef55be5…  /  83548e0f…  /  1743b784…
```

### Step 3 — 解包 fix1 PATCH 到项目根 + 应用 phase 接线，校验包内 SHA

```bash
cd "$PROJ" || exit 1
tar -xzf /root/fix1_independent_rx_PATCH.tar.gz
# gate9_wiring.patch 落到 board_package/ 下；板端 git apply（或按 BOARDTEST.md 照抄 4 处）:
cd "$PROJ/board_package"
git apply gate9_wiring.patch 2>/dev/null || echo "git apply 失败 -> 按 BOARDTEST.md 手工照抄 4 处插入"
cd "$PROJ"
# PATCH 包内无逐文件 SHA256SUMS（G5），解包后完整性以 Step2 整体 tar SHA 为准；
# 不执行 sha256sum -c（无 SUMS 文件可 -c）。
```

> 说明：fix1 PATCH 是「扁平相对路径」内容，直接解到项目根（`scripts/`、`board_package/`、
> `contract/`、`host_tests/`、`docs/`）。`gate9_phase.hpp` + `board_gate9_full_chain_rml23.cpp`
> 需按 `gate9_wiring.patch` 升级出第 4 相位（npu/dualsdr/singlesdr/independent-rx）。

### Step 4 — 解包两套 INPUTS（**各自全新目录，勿混**）

```bash
# fix1 输入包（v1 波形，24 burst + 10 列 manifest）:
FIX1_IN=/root/fix1_public_protocol_tx
mkdir -p "$FIX1_IN" && cd "$FIX1_IN"
tar -xzf /root/fix1_independent_rx_INPUTS.tar.gz
sha256sum -c tx_package/SHA256SUMS.txt

# v2 输入包（v2 修正波形，24 burst + 10 列 manifest，source_id 不同）——单独目录:
V2_IN=/root/v2_public_protocol_tx
mkdir -p "$V2_IN" && cd "$V2_IN"
tar -xzf /root/v2_waveform_correct_INPUTS.tar.gz
sha256sum -c tx_package/SHA256SUMS.txt
```

### Step 5 — 单线程构建（⚠ BLOCKED by G1：缺 7 参 shim，先补再建）

```bash
cd "$PROJ/board_package" || exit 1
LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64
ICRAFT_CMAKE_DIR=/usr/cmake
BUILD_DIR=build_gate9_rml23
TARGET=board_gate9_full_chain_rml23

rm -f "$PROJ/bin/$TARGET"
rm -rf "$BUILD_DIR" && mkdir -p "$BUILD_DIR" && cd "$BUILD_DIR"
# 单线程；g++15.2.0 冻结标量 WL 头 iq_rf_loopback_24class_bf16_scalarwl_core.hpp:352
#   sign-compare -Werror 会崩 —— 仅本测一次性 -Wno-error=sign-compare，不改冻结头/永久 flags：
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_GATE9_RML23=ON \
  -DLIBIIO_ROOT="$LIBIIO_ROOT" -DCMAKE_PREFIX_PATH="$ICRAFT_CMAKE_DIR" \
  -DCMAKE_CXX_FLAGS="-Wno-error=sign-compare"
make -j1 "$TARGET"
[ -f "$TARGET" ] && mkdir -p "$PROJ/bin" && cp "$TARGET" "$PROJ/bin/$TARGET" \
  && echo "NPU_BUILD_RESULT gate=9R result=PASS binary=$PROJ/bin/$TARGET"
```

> ⚠ G1：`gate9_wiring.patch` 的 dispatch 引用未定义的
> `run_radioml_independent_rx(npu, contract, out, sock, timing, argc, argv)`，在补上该 7 参
> shim（同 npu/dualsdr/singlesdr 形状，转发到
> `iqindepfix1::run_radioml_independent_rx(argc, argv, on_frame)`）之前，本步必然编译失败。

### Step 6 — PC 侧启动 TX 服务（⚠ BLOCKED by G4：无公共协议 TX 服务）

```bash
# 期望：PC（radioconda）先启动与板端一致的公共协议 TX 服务，监听 0.0.0.0:39010，
#       只传控制消息 + 身份 + SHA，绝不传实时 IQ。
# ⚠ 当前交付无此服务。fix1 只有 build-only 的 radioml_public_protocol_tx.py（产 tx_package），
#   无 serve/launch/39010 监听；需补 pc_tx_radioml_public_protocol.py launch 后才有下面命令：
# D:\radioconda\python.exe -I scripts/pc_tx_radioml_public_protocol.py launch \
#     --tx-payload <FIX1_IN/tx_package> --tx-uri "<PC_TX_URI>"
```

### Step 7 — 板端运行（⚠ BLOCKED by G1/G2/G3）

```bash
cd "$PROJ" || exit 1
# 期望运行命令（显式 24 类 BF16 + --rx-gain=35；公共协议 TX 由 PC 侧循环发）:
./bin/board_gate9_full_chain_rml23 \
  --phase radioml-independent-rx-public-protocol-24class-bf16-fix1 \
  --input-dir "$FIX1_IN/tx_package" \
  --out-dir "/root/fix1_board_out_$(date +%s)" \
  --tx-control "tcp://<PC_IP>:39010" \
  --rx-uri "<板端 RX SDR URI>" \
  --sample-rate 2560000 \
  --rx-gain 35
```

> ⚠ G2：runner 捕获体 stub（`rx_int16` 不填充），无法真实捕获 RX；G3：该 runner 只接受 v1
> manifest（reject v2），且无 v2 board runner；G1：shim 缺失导致根本无法构建出二进制。

### Step 8 — 回传整个 $OUT

回传 `$OUT_DIR`：`board_independent_rx_results.tsv`（11 列）+ 24 个
`<sid>.recovered.tensor.bin`。**门拒（gated=0）/ hard_invalid（finite=0）/ 不可恢复样本
同样落盘、保留分母不剔除**（本报告第 3 点判读脚本已按此口径实现）。

---

## 第 3 点：冻结判读基线 + 判读脚本

### 3.1 冻结基线文件

- 路径：`F:\嵌赛\fix10class24_waveform_correct_v2_work\baseline\v2_digital_baseline_frozen.json`
- **文件 SHA256**：`cd2ed6a830ba27c1cd83eee33960cd515fb89c24393af82ce94c6e312946e343`
- 内容：v2 数字 orig 层 **23/24**，24 行逐样本
  `{source_index, class_index, class_name, seed, burst_sha256, payload_ci16_sha256,
  manifest_model_input_sha256(A层), recovered_model_input_sha256(喂模型张量),
  orig_pred, orig_correct}`，逐样本 SHA 绑定（A 层 + recovered 双 SHA）。
- recovered tensor SHA 核验 24/24 通过（对 layers 目录逐字节重算）。
- 唯一误分类：源 21 `AM-DSB-SC`（class 20）→ orig_pred=16（256QAM）。如实记录为
  「模型与新波形域不匹配」，不掩盖 / 不归因 RF / 不反向改波形。

### 3.2 判读脚本

- 冻结生成器：`F:\嵌赛\fix10class24_waveform_correct_v2_work\scripts\freeze_v2_baseline.py`
  （读 manifest + replay + layers，写冻结 JSON，打印文件 SHA）。
- 板端判读器：`F:\嵌赛\fix10class24_waveform_correct_v2_work\scripts\judge_radioml_board_vs_baseline.py`
  （`--baseline` + `--board` + `--out-json`），板测回传后统计三项：
  - (a) `real_label_accuracy` = board_pred == class_index；
  - (b) `board_vs_baseline_agree` = board_pred == 基线 orig_pred；
  - (c) 分母恒 24：缺失 / 门拒(gated=0) / 非有限(finite=0, board_pred=-1) 全部保留不剔除。
  - 额外：区分「数字与板端同错（board_pred==orig_pred 且都≠真值）」与「板端新增翻转」，
    **不自动归因 RF**。
- 验证：`judge_radioml_board_vs_baseline.py --self-test` **7/7 PASS**；端到端合成板端
  （board_pred 逐样本复现基线）实测 `real_label_accuracy=23/24、agree=24/24、same_wrong=1、
  new_flips=0`。

判读器用法（板测回传后）：

```bash
D:/Anaconda/python.exe -I scripts/judge_radioml_board_vs_baseline.py \
  --baseline baseline/v2_digital_baseline_frozen.json \
  --board <回传的 board_independent_rx_results.tsv> \
  --out-json <fresh judge dir>/board_vs_baseline_verdict.json
```

---

## 附：待办（block 板测的 4 缺口，须另开工作补齐）

1. G1：补 `run_radioml_independent_rx` 7 参 shim（同 npu/dualsdr/singlesdr 形状）。
2. G2：把 runner 捕获体从 stub 补成 dualsdr 同款（负控 + iqpctbrx + capture_contiguous +
   7 分支保真门 + ≤3 重捕 + 末次选择）。
3. G3：放宽/新增 v2 分支（v2 source_id + conversion_version=v2），或明确 v2 仅数字、
   板测只跑 fix1 v1；并决定 v2 是否需独立 board runner。
4. G4：补 PC TX 服务 `pc_tx_radioml_public_protocol.py launch`（39010 SERVER，循环发
   24 公共协议 burst，HELLO 带 source_id + manifest_sha256 fail-closed）。

以上 4 缺口均在另一 fork（blind-clean1 `a00c8648…`，已暂停）工作树范畴内或需新开工作；
本次 Task C 未越界改动该 fork 的判读器 / 共享契约。
