# 三线并行公共合同（冻结）

版本：2026-10-29（唯一入口，覆盖旧交接的过期状态）。任务书：
`F:\嵌赛\HANDOFF_PARALLEL_MAINCHAIN_FPGA_MULTISIGNAL_20261029.md`。

## 0. 目录与文件所有权

| 线 | 工作树 | 权限 |
|----|--------|------|
| 主线程 | 本文件 + 集成/验收 | 只读三树，最终打包 |
| A 主链 | `F:\嵌赛\rml24_mainchain_finalize1_20261028` | 拥有（生产入口唯一编辑者） |
| B FPGA | `F:\嵌赛\rml24_fpga_smartscan_prep2_20261028` | 拥有 |
| C 多信号 | `F:\嵌赛\rml24_multisignal_prep1_20261029`（新建） | 拥有；对 A/B 树只读 |

禁止共同编辑生产入口。B 线不得修改 A 线树的任何文件；C 线不得修改 A/B 树。

## 1. 后端枚举（冻结）

`software` | `fpga` | `auto`。`auto` = 先尝试 FPGA，任何故障（协议错误/溢出/超时/版本不符/帧未提交）**切软件 FFT**，不得展示过期 FPGA 结果。此三值字符串为唯一合法后端标识，不得新增或改名。

## 2. 版本（冻结）

FPGA 扫描核版本 `8'h01`（`smart_scan_psd_buffers` 的 `version` 输出）。任何合同/位序/寄存器的破坏性变更必须递增此值，且 `auto` 在版本不符时回退软件。

## 3. 频率单位与坐标（冻结，2026-10-29 修订）

内部存储/协议/计算一律**整数 Hz**，字段名 `*_hz`（`center_hz`/`start_hz`/`stop_hz`/`step_hz`/`bw_hz`/`offset_hz`）。界面可显示 MHz/GHz/MS/s 但必须显式标注单位；十进制输入须精确转换到整数 Hz，拒绝无法表示的子 Hz、非法、越界输入（禁浮点截断）。
采样率冻结 `sample_rate_hz=2560000`；FFT 1024 点 → 单 bin `2500 Hz`（物理事实）。**调谐步长不天然等于 2500 Hz 整数倍**：除非真实接收器/控制器确有对齐前提（须核实并记录原因），否则不设该限制，频谱拼接按实际 Hz 坐标完成。`0.9*fs=2304000` 是扫描跨度/上限，不是 `fs`，不得为凑整数 bin 擅改主链为 2302500。

## 4. 状态/错误（冻结）

FPGA 读回状态字段（已有）：`version[7:0]`、`status_frame_id[31:0]`、`status_protocol_error`、`status_overflow`、`committed_valid`、`committed_bank`。错误分类：协议错误（tlast 异常/输入 starvation/输出失步）、溢出、帧未提交、版本不符、读超时。任一 → `auto` 回退软件。

## 5. 缓存一致性 / 防撕裂（原则冻结，机制 B 线定版）

PS 读前**必须**检查 `committed_valid` 与完整帧世代（`status_frame_id`），读取前后世代变化则重试/拒收；单纯读 `committed_bank` 不能防被下一轮覆盖。B 线在 `smart_scan_psd_buffers` 之上定义明确的占有/释放或世代重查机制，并核实真实 BRAM 读延迟。

## 6. PSPL 寄存器映射（B 线定版，命名约定冻结）

寄存器前缀 `SS_`；地址映射由 B 线输出到 `contract/pspl_register_map.md` 并回填本合同。命名约定：数据/控制/状态三组，宽度与 `smart_scan_top` 端口一致（IQ `{Q,I}` 32-bit、rd_bank+rd_addr、rd_data 64-bit、状态 8+32+1+1+1+1）。

## 7. 多目标身份 / 老化（冻结字段集）

目标记录字段（冻结）：`target_id`（稳定）、`center_hz`、`bw_hz`、`power_valid`、`top3`（3 元组 class+confidence）、`confidence`、`last_seen`、`status`、`backend`。老化：连续 N 个重访周期未再检出即丢弃（N 可配置，默认 3）。列表时间戳 ≠ 同时识别（单 SDR 顺序扫描）。

## 8. 分类/判分口径（冻结）

分类不得读测试真值/发射样本/逐样本补偿。判分按冻结预期 target 集合 + 时间窗：检出率/漏检/虚警/重复目标/首次发现延迟/重访周期/分类正确；**漏项固定计错**；检出与分类分开报告，不得只对收到的目标报准确率。

## 9. 红线（不变，覆盖所有线）

- 不碰板 / 不写 Flash / 禁发射；板端加载、RF、正式切换由用户按明确命令执行。
- 模型 IQ / 冻结 NPU / 软件扫频 / 旧位流不变；`auto` 回退必须。
- OOC 外壳 `production_bitstream=NO`，永远不是位流，不得冒充板测。
- 禁写 `RF_PASS` / `PROJECT_COMPLETE` 直至对应证据齐备。
- 先验收主链版本、FPGA same-IQ 与回退通过，再做主链定频/扫频回归；上述通过后才执行 C 线多目标 RF。
- 工具构建排队：不同时跑多个 Vivado/Procise 重型构建。

## 10. 交付门

1. A/B/C 各自独立测试完成，主线程审查共享字段、依赖闭包、无泄漏。
2. 冻结主链版本并验收；FPGA 完整工程生成候选（`production_bitstream` 仅在完整顶层 P&R 后才为 YES，仍不写 Flash）。
3. FPGA same-IQ 与回退通过 → 主链定频/扫频回归。
4. 通过后才做 C 线多目标 RF；失败按原始采集诊断，不改分母、不择优。
5. 整机断电自启 + 连续运行 + 真实 UI + 外壳装配后复验。
