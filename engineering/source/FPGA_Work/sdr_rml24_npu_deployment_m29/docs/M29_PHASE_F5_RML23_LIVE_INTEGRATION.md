# M29 Phase F5 — RML23 实时 NPU 主链集成（勘误）交付报告

> 状态：`M29-RML23-LIVE-CORRECTNESS-FIX-READY-FOR-BOARD-TEST`（最高允许，待用户真实上板；
>       offline conformance gate ≥0.90 仅能由板端 `run_gate9_rml23.sh --phase=offline --count=240` 验证）
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁自动启动 QAT / 不训练专家模型 /
>       不覆盖 M22/M23/M24 / 禁写 FINAL_*/NPU_PASS/RML23_LIVE_HARDWARE_PASS /
>       UI_HARDWARE_PASS/PROJECT_COMPLETE。

本阶段把 F4 的「离线 logits 回放候选包」升级为**真实实时 NPU 主链集成**：以
M22.1 真实板端主程序为基线，接入 expA_bf16_head 24 类底层模型，软件层做 24→23
类 AM-SSB logaddexp 合并，保持 M22 全部功能并实时输出 23 类。

---

## 0. 结论

- 交付目录：`board_rml23_live/`（独立新目录，不覆盖 M22/M23/M24）。
- 最高状态：`M29-RML23-LIVE-CORRECTNESS-FIX-READY-FOR-BOARD-TEST`。
- 离线自洽全绿（详见 §5）；offline conformance gate ≥0.90 **仅能由用户在板端**
  `run_gate9_rml23.sh --phase=offline --count=240` 验证（本轮重建 conformance golden，见 §0.1）。

## 0.1 正确性修复勘误（conformance golden 重建 + 4 项集成遗留）

上一版 `deployment_golden/` 仍是 M22 的 **12 类** golden（不同模型/不同标签合同/不同输入来源），
与 23 类 RML23 输出不可比较，故板端 offline gate 实测 `match_rate=0.000000`。本轮：

- **conformance golden 重建**（`scripts/gen_rml23_golden.py`）：从冻结 expA_bf16_head 重建
  `deployment_golden/`（严格 24 源类 ×10=240 帧；`expected_argmax.tsv` 第 2 列 = merged-23 argmax；
  含 BPSK/QPSK 标签守卫；`coverage_supplemental/` 仅覆盖审计、板端 gate 不读）。golden 是
  **部署一致性参考，非准确率评估**，任何文档不得把 match_rate 称作「模型准确率」。
- **4 项集成遗留**：一键 `start_all_rml23.sh`/`stop_all_rml23.sh`；RML23 socket `_rml23` 后缀对齐；
  1000 ms steady-clock 状态心跳（携带 `version=rml23-chain-v2` + `model_sha`）；state 协议版本
  `rml23-chain-v2`（解析器兼容 `12class-chain-v2`）。
- 1000/10000 帧结果改标 **runtime-stability-only**（非正确性门禁）。

**交付物（详见 `board_rml23_live/dist/RML23_CORRECTNESS_FIX_DELIVERY.txt`）**：

| 工件 | SHA256（前 8） | 字节 | 文件数 |
|---|---|---|---|
| 增量补丁 `sdr_rml23_live_correctness_fix_patch.tar.gz` | `4abe1546…` | 2194457 | 294（38 新 + 256 改） |
| 全量包 `sdr_rml23_live_board_package_correctness_fix.tar.gz` | `81d66586…` | 3604486 | 479 内容 + SHA256SUMS |
| F5 原包 `sdr_rml23_live_board_package.tar.gz`（保留） | `cb3f204e…` | 3343378 | 439 |
| RF 补丁 `sdr_rml23_live_rf_fix_patch.tar.gz`（保留） | `e988707c…` | 55709 | 17 |
| RF 全量 `sdr_rml23_live_board_package_rf_fix.tar.gz`（保留） | `e166bb32…` | 3352723 | 441 |

**Task B（UI 视觉重构）本轮不执行**，作为独立补丁另行交付（本轮 diff/补丁/全量包不含任何
`ui_render`/`ui_layout`/字体/快照/像素改动）。

---

## 1. 十个问题逐条回答

### Q1. 原包为什么不是真实实时主链包？

F4 的 `board_rml23/` 只有 `rml23_merged_main` 一个「读文件」程序：它读取预生成
`logits.f32`，不调用 iCraft NPU runtime、不加载 `model_24class_ZG.json/raw`、不从
Pluto/M22 实时链路取输入、不接 M22 结果协议与真实 UI；所谓 1000 帧测试只是离线
logits 回放（随包仅 1536 帧），无法执行真实 10000 帧。故它不是「M22 功能保留 +
23 类实时识别」的完整板端包。

### Q2. 新包实际加载模型的代码在哪里？

`board_package/npu_classifier24.hpp` 的 `NpuClassifier24` 构造器：

```cpp
network_(icraft::xir::Network::CreateFromJsonFile(model_json))   // 行 57 加载 JSON
network_.lazyLoadParamsFromFile(model_raw);                       // 行 59 加载 RAW 权重
```

JSON/RAW 路径来自 `board_gate9_full_chain_rml23.cpp` 的 `--model-json` /
`--model-raw`（默认 `model_rml23/model_24class_ZG.json` / `.raw`，即冻结 expA
模型，SHA `d43a2284…` / `2425d990…`）。producer `main()` 行 1244 只构造一次
`NpuClassifier24`。

### Q3. NPU Open/Close 分别发生在哪里？

- **Open**：`npu_classifier24.hpp` 行 69 `device_ = icraft::xrt::Device::Open(kNpuDeviceUrl24)`
  （构造器内，进程启动时一次）；行 75-78 `Session::Create<ZG330Backend, HostBackend>` +
  `apply()` 一次。
- **Close**：行 94 `~NpuClassifier24()` 内 `icraft::xrt::Device::Close(device_)`
  （析构，进程退出时一次）。
- 生命周期计数器 `open_count/apply_count/reset_count/discipline_ok` 强制
  Open 一次、apply 一次纪律；`rearm_.begin_frame()` 保证第 2 帧起每帧只做一次
  `Device::reset(1)`，**不逐帧 reopen/deinit/rebuild**。

### Q4. 每帧 24 维输出在哪里传入 merge_predict？

`board_gate9_full_chain_rml23.cpp`：

- offline 阶段：行 337 `raw24 = npu.infer(tensor.data())` → 行 342
  `merged23 = merge_to_23(raw24)`。
- 实时/loopback 阶段：行 656-666 的 `prod.on_frame(...)` lambda 内
  `npu.infer(t, raw24_frame)`（24 维 raw logits）→ `rml23::merge_logits_23(raw24_frame.data(), m23)`
  → `lg.assign(m23, m23 + rml23::kDeployedClassCount)`（23 维）。
- ambient 阶段：行 1054-1067 同结构。

`merge_to_23`（行 98-104）对 24 维宽度与 NaN/Inf fail-closed（`merge_logits_23`
内部拒绝非有限 logits）。`raw_24_logits`/`raw_24_top1` 保留审计，`merged_23_top1`/
`merged_23_label` 对外输出。

### Q5. 是否完整沿用 M22 输入和控制链？

是。producer 复用 M22 的 `producer::ProducerDecision`（`prod.on_frame`）、
`pluto::`/`sdr_adapter`（Pluto/IQ 实时输入）、resampler、`finish_m22_runtime`
（M22_RUNTIME_RESULT 插桩）、`m22::StageId::NpuInfer` 计时、`--perf-file`/
`--summary-interval`；1000/10000 帧脚本复用 `m22_harness.sh` + `process_guard.sh`。
UI server（`board_ui_live_rml23.cpp`）复用 M22 的 AF_UNIX 服务端 + Style A 双缓冲
framebuffer + 触摸/控制 socket。原 bitstream 不变。

### Q6. 哪些 UI 数组由 12 类改为 23 类？

- `ui_sw/ui_render.cpp` 新增 `CLASSES_23`（行 33，23 个标签，第 18 位为合并后
  `AM-SSB`，无虚假 SC/WC），`classes_23()`（行 395）。
- `board_package/ui_state_map.hpp` 新增 `map_to_state_rml23`（行 106-113）：
  `st.classes = &ui::classes_23()`、`st.model_mode = rml23::kModelMode`
  （`RML23-AMSSB-MERGED`）、`st.class_count = 23`、`st.category_page = 0`
  （触发分页类目表，不再固定为 12）。
- `board_ui_live_rml23.cpp` 行 422/458/485 三处 `waiting/still/current.classes =
  &ui::classes_23()`，`class_count = 23`。顶栏/详情页/历史记录数组均随
  `class_count` 与 `classes_23()` 长度渲染，不再硬编码 12。

### Q7. 是否需要新 bitstream？

**否。** 沿用现有 combined bitstream（SHA `22fec95c…`），不启动 Vivado、不改
RTL/XDC。变更全部在软件 + 模型层。

### Q8. 1000/10000 测试是否为真实 NPU 而非文件回放？

是。`test_live_1000_frames.sh` / `test_live_10000_frames.sh` 以 `--phase=digital`
驱动 `board_gate9_full_chain_rml23`，逐帧走 `npu.infer()` 真实 NPU 推理（Digital
loopback 走 Pluto 数字回环），读取 `M22_RUNTIME_RESULT` 输出
`RML23_TEST_LIVE result=PASS|FAIL`。无任何预生成 logits.f32 路径。

### Q9. 如何上传、校验、构建、启动、测试、停止和回滚？

见包内 `README.md` §3，入口脚本（`scripts/`）：

```sh
./scripts/verify_package.sh                 # fail-closed：模型 SHA + 契约 SHA + 清单
LIBIIO_ROOT=... ./scripts/build_on_board.sh # producer + UI server（板端 aarch64）
./scripts/start_live_rml23.sh               # 启动 UI server
./scripts/test_live_1000_frames.sh          # 真实 NPU 1000 帧
./scripts/test_live_10000_frames.sh         # 真实 NPU 10000 帧
./scripts/check_live_result.sh --result-log=...  # 结果协议 + UI 计数器
./scripts/stop_live_rml23.sh                # 停止
./scripts/rollback_to_m22_12class.sh        # 回滚 M22.1 12 类（不碰 Flash/位流）
```

### Q10. 新包完整路径、大小、SHA256 和文件清单是什么？

- 完整路径：`board_rml23_live/dist/sdr_rml23_live_board_package.tar.gz`
- 大小：`3343378` 字节（约 3.2 MiB）
- SHA256：`cb3f204edfa235b66a829fbdfff0af29012095631221674e6bc476ffc78bd62f`
- 内容文件数：`439`（含 `SHA256SUMS.txt`）
- 顶层目录：`board_package/`、`sdr_adapter/`、`ui_sw/`、`scripts/`、`contracts/`、
  `host_tests/`、`host_tools/`、`model_rml23/`、`model_12class/`、`deployment_golden/`、
  `README.md`、`SHA256SUMS.txt`。
- 清单：包内 `SHA256SUMS.txt`（相对路径，不含自身），解包后 `sha256sum -c` 全 OK。
- 架构：纯源码，`file` 扫描 `NO_BINARIES_OK (0 ELF/PE32/Mach-O/x86)`。

---

## 2. 新增/修改文件清单（F5）

**新建（RML23 专用）**：`model_rml23/`（expA 模型 + SHA + 部署契约）、
`contracts/rml23_merged_contract.{py,json}`、`board_package/board_gate9_full_chain_rml23.cpp`、
`board_package/board_ui_live_rml23.cpp`、`board_package/rml23_merged.hpp`、
`board_package/npu_classifier24.hpp`、`board_package/result_frame_rml23_parse.hpp`、
`board_package/build_ui_live_rml23.sh`、`scripts/common_rml23.sh`、
`scripts/build_on_board.sh`、`scripts/run_gate9_rml23.sh`、
`scripts/start_live_rml23.sh`、`scripts/stop_live_rml23.sh`、
`scripts/test_live_1000_frames.sh`、`scripts/test_live_10000_frames.sh`、
`scripts/check_live_result.sh`、`scripts/rollback_to_m22_12class.sh`、
`scripts/verify_package.sh`、`scripts/verify_rml23_contract.py`、
`scripts/package_board_release_rml23.sh`、`README.md`、
`host_tests/test_rml23_merged.cpp`、`host_tests/test_result_frame_rml23.cpp`、
`host_tests/test_ui_rml23.cpp`、`host_tests/test_rml23_build.sh`。

**修改（仅追加，不改 12 类行为）**：`board_package/CMakeLists.txt`
（`BUILD_GATE9_RML23` 选项 + `board_gate9_full_chain_rml23` 目标）、
`board_package/build_npu_on_board.sh`（`--gate9-rml23` 模式）、
`host_tests/run_tests.sh`（追加 3 个 RML23 测试 + `test_rml23_build.sh`）、
`host_tests/syntax_check.sh`（追加 gate9_rml23 语法检查）、
`ui_sw/ui_render.cpp`（`CLASSES_23` + `classes_23()`）、
`ui_sw/ui_render.hpp`（`classes_23()` 声明）、
`board_package/ui_state_map.hpp`（`map_to_state_rml23`）。

**从 M22 复制（冻结 12 类回滚工件，不改）**：`model_12class/`、
`deployment_golden/`。

---

## 3. 协议与状态

- 结果协议版本 `rml23-chain-v2`（新增，旧 12 类解析器不误读）；
  state event 版本同为 `rml23-chain-v2`（RML23 心跳/状态事件携带 `model_sha`；解析器同时接受
  `12class-chain-v2` 以保 12 类兼容）。
- `deployment_mode=AMSSB_MERGED`；UI/serializer `model_mode=RML23-AMSSB-MERGED`；
  `class_count=23`；`expert_enabled=false`、`expert_result=NOT_RUN`。
- 每帧记录 `raw_24_logits`/`raw_24_top1`（审计）+ `merged_23_top1`/`merged_23_label`。
- 23 类标签序 SHA `15072cd2…`；合并契约 SHA `f9f7f381…`；源 24 类序 SHA `3e1382d1…`。

---

## 4. 冻结输入（SHA256）

| 工件 | SHA256 |
|---|---|
| 12 类回滚 raw | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |
| expA JSON | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` |
| expA RAW | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` |
| 23 类标签 | `15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88` |
| bitstream | 沿用 `22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9` |

---

## 5. 离线门禁结果

| 门禁 | 结果 |
|---|---|
| 23 类合并（`test_rml23_merged`） | 172 断言 pass / 0 fail |
| conformance golden 回归（`test_golden_rml23` + `verify_golden_rml23.py`） | 17/0 + 正向 7 + 负向 8 全通过（本轮新增） |
| 结果协议（`test_result_frame_rml23`） | 42 pass / 0 fail |
| UI 23 类边界/字体/裁剪（`test_ui_rml23`） | 27 pass / 0 fail |
| 完整主机套件（release） | ALL HOST TESTS PASSED（33 二进制 + 3 shell 套件） |
| ASan（3 个新测试） | 172/42/27 pass，0 fail |
| UBSan（3 个新测试） | 172/42/27 pass，0 fail |
| 12/24/23 维度误配 fail-closed | `test_rml23_merged` + `merge_to_23` 宽度/NaN 拒绝 |
| 模型 SHA + 标签 SHA 错误拒绝 | `verify_package.sh` + `verify_rml23_contract.py` PASS |
| 模型 Open 一次纪律 | `NpuClassifier24` lifecycle 计数器 + `discipline_ok` 断言 |
| 启停/残留 PID | `rollback_to_m22_12class.sh` + `process_guard.sh`（板端执行） |
| 构建接线（`test_rml23_build.sh`） | 7 pass / 0 fail |
| `bash -n`（全部 .sh） | BASH_N_ALL_OK |
| Python `compileall` + 契约重算 | PASS（label_order_23=`15072cd2…`，merged=`f9f7f381…`） |
| iCraft 语法检查（`syntax_check.sh`） | gate7/gate9/gate10/gate9_rml23 全 OK |
| 解包后 `sha256sum -c` | §1 Q10 自校验 OK |

---

## 6. 状态红线

- 最高状态：`M29-RML23-LIVE-CORRECTNESS-FIX-READY-FOR-BOARD-TEST`。
- 真实上板前**禁止**声明：`RML23_LIVE_HARDWARE_PASS` / `NPU_PASS` /
  `UI_HARDWARE_PASS` / `PROJECT_COMPLETE`。
- 完整 24 类状态保持 **BLOCKED**；原 24 类 PTQ 候选的 24 类判定保持 **REJECTED**。
