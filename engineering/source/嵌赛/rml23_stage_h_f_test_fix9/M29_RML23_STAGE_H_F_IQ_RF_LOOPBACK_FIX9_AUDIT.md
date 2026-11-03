# M29 RML23 Stage H-F / Route F — IQ RF 回环 fix9 审计

**状态**：`M29-RML23-IQ-RF-LOOPBACK-READY-FOR-BOARD-TEST`（未取得板端证据前不变；不写任何
`RF_PASS` / `RF_PATH_PROVEN` / `RF_PATH_PRESERVES` / `NPU_PASS` / `PROJECT_COMPLETE` /
`FINAL_*` / `BOARD_TEST_PASS` / `ROUTE_F_23CLASS_ACCURACY_MEASURED`；host 测试永不升级
板端 RF 状态；`ROUTE_F_23CLASS_ACCURACY_MEASURED` 仅由板端合法测试建立）。
**基线**：`sdr_rml23_live_board_package_iq_rf_loopback_fix8.tar.gz` `2577b1c9…`（555 文件）。
**本轮工件**：独立补丁 `sdr_rml23_live_iq_rf_loopback_fix9_patch.tar.gz` + 合并全量
`sdr_rml23_live_board_package_iq_rf_loopback_fix9.tar.gz`（fix8 全量 + fix9）。精确路径/字节/
文件数/manifest 行数/64-hex SHA 见 `dist/RML23_IQ_RF_LOOPBACK_FIX9_DELIVERY.txt`。

---

## §1 背景与判责边界

fix8 已把 Route F 物理 RF 自回环 + Route D2 非训练 4ASK 消融 + 安全工作点扫描 + D-vs-D2 A/B
六门禁推到 READY-FOR-BOARD-TEST。fix9 是 Route F 的**核心版**：D2 物理 RF 闭环 + 23 类准确率
测量。目标是**最小但可信的闭环**：RadioML 原始 IQ → 非训练 Route D2 重构 → 可发射 ci16 →
Pluto TX → 50Ω 同轴 → Pluto RX → D2 RX 恢复 → 原始 24 类模型折叠到 23 部署类分类 → 23 类
准确率 + 混淆矩阵。输出是**测量**，不是 PASS/FAIL 门禁。

| 子任务 | 内容 | 判责边界 |
|---|---|---|
| **A** | `analyze_route_d2_4ask.py` manifest 解析 fail-closed 修复 | 头行检测不假设表头；任何违例 raise，不静默丢行（dropped==0 诚实上报） |
| **B** | `build_route_d2_rf_artifacts.py` D2 RF 工件构建器 | 全局 K 仅在校准子集选（K=2048 优先，削顶重选）；校准/保留分离 |
| **C** | `load_d2_sidecar` radioml-d2-2p56m 装载器 | SHA/尺寸/采样率/类一致/不安全路径全部 fail-closed |
| **D** | `--rf-tx-target-rms=N` 缩放 | 预测削顶即拒绝（tx_clip_post），fail-closed 不静默饱和 |
| **E** | D2 RX 恢复（`apply_d2_restore_to_stream` + `select_classification_window`） | 仅 build 时常量驱动恢复；DC 最后加回（未随 RF 增益旋转） |
| **F** | `--phase=iq-rf-loopback-23class` runner | 强制 direct-cable / tx-atten≤-40；RF_PRESERVES_IQ 不过即排除不评分 |
| **G/H** | 23 类准确率 + 混淆矩阵 | 仅保留 23×23 矩阵 + 23 计数器；RF 保真不过即 `_INVALID_DUE_TO_RF_FIDELITY` |
| **I/J** | D0 小规模对照（文档化）+ 内存有界（peak RSS 回读） | 不新增全 23 类 D0 双跑 |

---

## §2 九个子任务：要求 → 实现

### Task A — manifest 解析 fail-closed（analyze_route_d2_4ask.py）

**要求**：fix8 解析器无条件丢弃首行作"表头"，无表头 manifest 会静默丢失第一条数据行。修复为
按首字段检测表头（首字段为字面 `"index"` 才是表头，否则是整数数据行），永不丢数据行；逐行
fail-closed 校验 index/source_index 唯一性、class_name↔class_index 一致（INDEX_TO_CLASS）、
（给 bin_dir 时）`.bin` 存在/精确 8192 字节/SHA256；任何违例 raise ValueError，绝不静默丢行。

**实现**：`scripts/analyze_route_d2_4ask.py:720` `parse_manifest` 重写（头行检测 `lines[0].split("\t")[0]
== "index"`）；`:778` `_validate_bin_files` 精确 8192 字节 + SHA 校验；self-test 从 fix8 的 10/10
扩到 **15/15**。

### Task B — D2 RF 工件构建器（build_route_d2_rf_artifacts.py，NEW）

**要求**：每样本写 `quantized_d2_2p56m[_cal]_%06d.ci16`（交错 int16 LE，AC-ONLY，全局 K int16
RMS counts）+ `recovered_tensor_d2[_cal]_%06d.f32`（[2,1024] fp32 = 8192 字节）+ 24 列
`route_d2_rf_manifest.tsv`；全局 K 仅由校准子集（无标签、永不看保留）选，K=2048 优先、削顶则
选最大 clip-free 较小 K；校准/保留以 `split_role` 分离，板端有真正独立的 RF 增益校准子集、只评
保留。`--calib-count 8 --holdout-count 30`（正式 690 保留），`--smoke`（46 保留）。

**实现**：`scripts/build_route_d2_rf_artifacts.py:113` `select_global_k`（校准子集、K 候选、无标签）；
`:130` `build_one`（削顶 fail-closed：`clip_count==0`）；`:152` `main` 写 ci16/f32/manifest + 摘要；
`:290` `self_test` **6/6**。

### Task C — D2 sidecar 装载器（iq_digital_loopback.hpp）

**要求**：`input-kind=radioml-d2-2p56m` 新 Loader C，读 `route_d2_rf_manifest.tsv`（24 列），每文件
携带 build 时 D2 常量（original_dc_i/q、rec_scale）+ split_role；SHA/尺寸/采样率/类一致/不安全路径
fail-closed，与 Route D 装载器一致。

**实现**：`board_package/iq_digital_loopback.hpp:420` `load_d2_sidecar`（24 列解析、deployed23 映射校验、
split_role 白名单、采样率 == kFrozenFsIn、不安全路径拒绝、64-hex SHA 校验）；`:548`
`load_frozen_iq` 分发增加 `radioml-d2-2p56m` 分支；`FrozenIq` 增 `d2_rec_scale` /
`recovered_tensor_file` / `recovered_tensor_sha256`。

### Task D — `--rf-tx-target-rms=N` 缩放（iq_rf_loopback_transfer.hpp）

**要求**：`transfer_one_file_rf` 尾部增 `target_rms`；测原生 TX RMS/peak、预测缩放后 peak，仅在预测
peak 不削顶时缩放；`tx_clip_post==true` 表缩放被拒（fail-closed，不静默饱和）、`tx_scale` 保持 1.0。
默认 0.0 = no-op。

**实现**：`board_package/iq_rf_loopback_transfer.hpp:106-115` `RfTransferResult` 增 `tx_target_rms` /
`tx_native_rms` / `tx_scale` / `tx_peak_pre` / `tx_peak_post` / `tx_clip_post`；`:125` 签名增
`double target_rms = 0.0`；`:166-180` 预测缩放 + 拒绝削顶（`tx_clip_post`）。

### Task E — D2 RX 恢复（iq_digital_loopback.hpp）

**要求**：RX 流 decimate（iq/2048 → 单位 RMS AC）→ 撤销**一个**全局 RF 增益（非逐文件拟合）→
`apply_d2_restore_to_stream`（× rec_scale = ac_rms·2048/K，最后加回 build 时 DC，因 DC 在 TX 前
已移除、未随 RF 增益旋转）→ `select_classification_window` 选唯一对齐 [2,1024] 窗口（有界延迟对齐 +
尺度不变 LS 复增益，1/16 计数域尺度永不误判为波形分歧）。

**实现**：`board_package/iq_digital_loopback.hpp:916` `select_classification_window`（全帧相关峰值定位 +
LS 复增益 + 尺度无关 NMSE）；`:995` `apply_d2_restore_to_stream`（纯逻辑，逐帧 `*rec_scale + dc_i/q`）。

### Task F — 23 类 runner（iq_rf_loopback_23class.hpp，NEW）

**要求**：`--phase=iq-rf-loopback-23class`；强制 `--input-kind=radioml-d2-2p56m` /
`--rf-path=direct-cable` / `--tx-atten ≤ -40`；两遍：校准子集（仅全局 RF 增益）→ 保留子集（恢复 +
分类，每文件一窗）。每个评分样本必须先过 `RF_PRESERVES_IQ`（corr≥0.9 ∧ SNR≥6 dB ∧
normalized_residual≤0.05 ∧ 无 TX/RX 削顶）；被排除样本计 `rf_excluded`、绝不评分。

**实现**：`board_package/iq_rf_loopback_23class.hpp:187` `run_iq_rf_loopback_23class`；`:208`
`--rf-tx-target-rms`（默认 2048.0）；`:234` input-kind 校验；`:347` `process_file` lambda
（TX/RX 格式、target_rms 缩放、RF 保真 gate）；`:670` D2 恢复 + 分类（`merge23` → `argmax_of`）；
`:783` 更新 23×23 矩阵 + 计数器；`:824` 准确率 token + 四输出文件。

### Task G/H — 准确率 + 混淆矩阵（内存有界）

**要求**：仅保留固定 23×23 混淆矩阵 + 23 每类计数器（无逐文件结果）；四输出：
`route_f_fix9_summary.json`（token `ROUTE_F_23CLASS_ACCURACY_MEASURED` 或
`ROUTE_F_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY`）、`route_f_fix9_confusion_23.csv`
（行=真、列=预测、部署标签头）、`route_f_fix9_per_class.json`（23 对象）、逐样本明细 TSV。
24→23 映射用 `kSourceToDeployed` + `merge_logits_23`（AM-SSB-SC 经 logaddexp 并入 AM-SSB-WC）。

**实现**：`board_package/iq_rf_loopback_23class.hpp:97` `Rf23RunReport`（23×23 + 23 计数器，无逐文件
结果）；`:72` `merge23` / `:81` `argmax_of`；`:824-903` 准确率 token + CSV/JSON 输出。

### Task I/J — D0 小规模对照（文档化）+ 内存有界

**要求**：Task I 仅文档化一个小规模 D0 对照（不新增全 23 类 D0 双跑）；Task J 内存有界（首/末 RSS
回读，仅保留峰值）。**实现**：`iq_rf_loopback_23class.hpp:821` `rep.peak_res`（first/last RSS 取大）。

---

## §3 文件差异（相对 fix8 `2577b1c9…` 基线）

**7 改**：
| 文件 | 变更 |
|---|---|
| `board_package/iq_digital_loopback.hpp` | `load_d2_sidecar`（Loader C）+ `apply_d2_restore_to_stream` + `select_classification_window` + 分发 |
| `board_package/iq_rf_loopback_transfer.hpp` | `RfTransferResult` + `transfer_one_file_rf` target_rms 缩放 + `tx_clip_post` fail-closed |
| `board_package/board_gate9_full_chain_rml23.cpp` | `run_iq_rf_loopback_23class` 包装 + 分发 |
| `board_package/gate9_phase.hpp` | 新增 `iq-rf-loopback-23class` phase |
| `scripts/analyze_route_d2_4ask.py` | `parse_manifest` fail-closed 头行检测 + 逐行校验（15/15 self-test） |
| `host_tests/build_host_tests.sh` | 构建 `test_iq_rf_loopback_23class` |
| `host_tests/run_tests.sh` | 运行 `test_iq_rf_loopback_23class` |

**5 新**：
| 文件 | 内容 |
|---|---|
| `board_package/iq_rf_loopback_23class.hpp` | D2 RF 闭环 + 23 类准确率 runner（内存有界报告） |
| `host_tests/test_iq_rf_loopback_23class.cpp` | 17 测试（D2 sidecar + restore + target-rms + merge + 端到端） |
| `scripts/build_route_d2_rf_artifacts.py` | D2 RF 工件构建器（ci16 + f32 + 24 列 manifest，6/6 self-test） |
| `scripts/package_iq_rf_loopback_fix9.py` | 打包器（dependency closure fail-closed） |
| `docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9_AUDIT.md` | 本审计 |

**红线合规**：不重训/不微调；不修改模型权重；不修改标签映射；不修改正式生产预处理；不增加 4ASK
标签覆盖规则；不使用真实标签选择 K 或 RF 参数（全局 K 仅校准子集、无标签）；不使用 NPU 输出反向
调参；不改 RTL/XDC/位流/Flash；tx_atten 不高于 -40 dB；仅 50Ω 同轴直连、无天线、无放大器；任一
TX/RX 削顶立即拒绝该样本；RF 保真不通过不报告有效准确率；host 测试不得升级板端 RF 状态；不覆盖
fix8 及更早历史工件；API 未连接/未操作板卡。

---

## §4 核心代码位置

- D2 sidecar 装载器：`iq_digital_loopback.hpp:420-500, 548`
- D2 恢复 + 窗口选择：`iq_digital_loopback.hpp:916-990, 995-1010`
- target_rms 缩放：`iq_rf_loopback_transfer.hpp:106-115, 125, 166-180`
- 23 类 runner：`iq_rf_loopback_23class.hpp:72, 81, 97, 187, 208, 234, 347, 670, 783, 824-903`
- phase 分发：`gate9_phase.hpp:20`；`board_gate9_full_chain_rml23.cpp`（`run_iq_rf_loopback_23class` + main 分发）
- manifest 解析：`scripts/analyze_route_d2_4ask.py:720-796`
- D2 工件构建：`scripts/build_route_d2_rf_artifacts.py:113, 130, 152, 290`
- host 测试：`host_tests/test_iq_rf_loopback_23class.cpp`（17 测试，93 断言）

---

## §5 离线验证（本轮，不碰板）

1. `host_tests/build_host_tests.sh` 全绿（含新增 `test_iq_rf_loopback_23class` 链接
   `../sdr_adapter/pluto_tx.cpp`）；
2. `host_tests/run_tests.sh` → **`ALL HOST TESTS PASSED`**；
3. fix9 host 测试 `test_iq_rf_loopback_23class` 17/0（93 断言全过，含 D2 恢复端到端 corr>0.9999）；
4. `host_tests/syntax_check.sh` → `gate9_rml23: syntax OK`（含 23class 包装与分发）；
5. `scripts/analyze_route_d2_4ask.py --self-test` **15/15**（Windows `python -I`，numpy 2.1.3）；
6. `scripts/build_route_d2_rf_artifacts.py --self-test` **6/6**；
7. 打包器 `audit_dependency_closure` OK（所有改动头已列入 `ROUTE_F_FIX9_FILES`）；两份 tarball 确定性
   重打包一致；独立解包 `sha256sum -c` 全 OK。

---

## §6 官方文档引用（Task 11）

- **libiio 官方文档**：`iio_channel_convert()`（硬件格式→主机格式采样转换）——
  <https://analogdevicesinc.github.io/libiio/>，API 参考
  <https://analogdevicesinc.github.io/libiio/main/api/c/debug/>。
- **AD9361/AD9363/AD9364 Linux IIO 收发器驱动**（本板 AD9364 走此驱动）——
  <https://wiki.analog.com/resources/tools-software/linux-drivers/iio-transceiver/ad9361>
  （镜像 <https://developer.analog.com/docs/linux/latest/drivers/iio-transceiver/ad9361.html>）。
- **AD9364 数据手册 / 参考手册**（UG-673 数据手册 + UG-672 寄存器映射）——
  <https://www.analog.com/en/products/ad9364.html>。
- **ADALM-PLUTO**（Rev.C 板载 AD9364，1T1R）—— <https://wiki.analog.com/university/tools/pluto>。

---

## §7 板端复测（用户执行；本审计不写死 ip、不强制）

```
第一步（构建 D2 RF 工件，产出校准/保留 ci16 + f32 + 24 列 manifest）：
python3 -I scripts/build_route_d2_rf_artifacts.py --bin-dir DIR --manifest DIR/manifest_a.tsv \
  --out-dir /root/rml23_route_d2_rf_fix9 --calib-count 8 --holdout-count 30
python3 -I scripts/analyze_route_d2_4ask.py --bin-dir DIR --manifest DIR/manifest_a.tsv \
  --json /root/rml23_route_d2_fix9.json

第二步（D2 物理 RF 闭环 + 23 类准确率，50Ω 同轴直连，无天线无放大器）：
./scripts/run_gate9_rml23.sh --phase=iq-rf-loopback-23class --center=2400000000 --rx-gain=10 \
  --tx-atten=-40 --rf-path=direct-cable --input-kind=radioml-d2-2p56m \
  --frozen-dir=/root/rml23_route_d2_rf_fix9 --rf-tx-target-rms=2048 \
  --out-dir=/root/rml23_route_f_fix9_out > /root/rml23_route_f_fix9_23class.log 2>&1
  预期观测：IQ_RF_LOOPBACK_23CLASS BOARD_REQUIRED；每文件 RF_PRESERVES_IQ / rf_excluded；
  summary.json token 仅当 RF 保真全部通过才为 ROUTE_F_23CLASS_ACCURACY_MEASURED，否则
  ROUTE_F_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY；confusion_23.csv 23×23；per_class.json 23 对象。
```

---

## §8 交付

2 工件（独立补丁 + 合并全量），SHA256SUMS manifest + 独立解包 `sha256sum -c` 校验，精确
路径/字节/文件数/manifest 行数/64-hex SHA 见 `dist/RML23_IQ_RF_LOOPBACK_FIX9_DELIVERY.txt`。
历史包（fix8 `2577b1c9…` 及更早全部）原样保留。
