# 智能扫频 C 线（多信号）离线准备 — HANDOFF

状态：`OFFLINE_PREP_COMPLETE` + **`INTEGRATION_PATCH_READY`**（2026-10-29）。
纯离线，未发射、未碰板、未烧 Flash、未训练、未改模型、未改 A/B 树就地。
全树 `python -m pytest -q` → **59/59 PASS**（48 离线模块 + 11 真实入口回放）。
（2026-10-29 主线程修订 §3 后已收回「最大 2302500」与「12.5kHz/25dB 冻结承诺」
两处口径，并补 power_valid 数值契约；真实公共帧占用带宽已核验为满带宽 QPSK，
收回 ≤10 kHz 替身假设。）

## 一句话结论

现有扫频器与五页 UI **均不支持多信号**（单信号顺序扫描）；本线在离线层面补齐了
多候选提取、去重、老化、判分、TX 多载波合成与 UI 蓝图，并明确区分「冻结参数」与
「待板测验证的测试目标」。

## 任务逐条结论

1. **现有扫频是否支持多信号**：否。详见 `docs/SCAN_SUPPORT_AUDIT.md`
   （多候选队列/逐频锁定/结果列表/去重/老化全部不存在，有主链只读证据）。
2. **冻结目标记录**：合同 §7 九字段（`target_id, center_hz, bw_hz, power_valid,
   top3, confidence, last_seen, status, backend`）已冻结，见
   `contract/target_record_schema.json`；频谱坐标/调谐时间放独立 `SpectrumFrame`
   日志不污染记录。`power_valid` 已补数值契约（dB 相对中位噪声底，相对尺度，
   不标 dBm）。分类红线（不读真值/发射样本/逐样本补偿）保持不变。
3. **独立测试清单**：`docs/TEST_CHECKLIST.md` + `tests/`（0/1/2/3 目标、范围边缘、
   进出场、不同功率、近邻 12.5 kHz/不可分辨 7.5 kHz、判分口径、UI 模型）。
4. **双 Pluto 数字域多载波**：`src/tx_synth.py` + `src/spectrum_audit.py` +
   `docs/TX_SYNTH_AUDIT.md`（PAPR、12 dB 余量削顶、保护带、IM3、公共前导互扰=
   谱泄漏）。超单 TX 瞬时带宽需额外硬件；快速轮流发射不算同时。
5. **判分口径**：`src/scoring.py` + `docs/SCORING_SPEC.md`（检出/分类分开、
   漏项固定计错、虚警/重复/首次发现延迟/重访周期/分类正确单独报告）。

## 冻结 vs 待板测验证（修订后口径）

**冻结（合同逐字）**：fs=2.56 MHz、FFT=1024、bin=2500 Hz；扫描跨度/上限
2304000（=0.9×fs，主链既有值，非 bin 对齐要求，不设 2500 整数倍限制）；公共帧
协议；目标记录九字段；老化 3 周期；状态/后端枚举。

**待板测验证（离线测试目标，非承诺）**：可分辨频差 12 500 Hz、近邻动态范围
25 dB、检测阈值中位+14 dB、dwell 预算 0.25 s。须结合真实占用带宽、保护带与检测
算法板测验证后才可宣称。

**不承诺**：<12.5 kHz 重叠分离、>25 dB 近邻、超出单 TX/RX 瞬时带宽的同时呈现、
快速轮流冒充同时、列表时间戳=同时识别、单 dwell 内同时多信号（需 FPGA PSD 路径）。
真实公共前导/尾占用带宽**已核验** = 满带宽 QPSK（≈2.56 MHz Nyquist，−20 dB 占用
≈1.00×fs），**不是 ≤10 kHz 窄带**；待板测的只剩真实**载荷**波形占用带宽。

## 多目标真实入口集成（本阶段交付）

- **集成层定位**（`docs/INTEGRATION_LAYER.md`）：多信号接在扫描循环**控制层**
  （`standalone_receiver.py`），检测/恢复/分类/NPU/UI 事件 schema 均不动；逐 dwell
  单检测 → 列表来自跨 LO dwell 顺序扫描。
- **集成补丁**（待主线程合入）：`integration/patch_standalone_receiver.diff` +
  `integration/standalone_receiver.multisignal.py`（完整参考）+ `integration/README.md`。
  四个插入点：import/初始化 tracker、扫描段逐 dwell `tracker.observe`（`best` 仍只选
  本帧主体）、每次全扫 `tracker.end_cycle()` 老化过期清理、BAND_SCAN 每帧发
  `rml24_targets` 目标列表事件（五页 UI 列表页消费；C++ 渲染在 A/B 树板端包，不在本补丁）。
- **真实入口回放**（`tests/test_real_entry_replay.py`，11 项全过）：在真实
  `scan_runtime`/`receiver_core`/`ui_event`/`standalone_control`/`scan_lock_policy` +
  `candidate_two_dc` 上回放 0/1/2/3 目标、进出场+老化清理、范围修改、取消
  （`should_stop` 镜像真实 `stop.is_set()`）、逐目标 UI 事件、恢复入口。
- **占用带宽核验**（`docs/OCCUPIED_BW_VERIFICATION.md` + `scripts/verify_public_bw.py` +
  `results/public_bw_verification.json`）：真实公共前导/尾满带宽 QPSK，收回 ≤10 kHz
  替身；已同步修订 `contract/multisignal_contract.json`、`docs/FROZEN_PARAMS.md`、
  `docs/TX_SYNTH_AUDIT.md`、`rf/RF_COMMANDS_DRAFT.md`。
- **判分脚本**：`scripts/score_multisignal_run.py`（固定分母，检出/分类分开，漏项
  固定计错，fail-closed 退出码）。

## 交付物清单

- 离线代码：`src/`（contracts/psd/tracker/scoring/tx_synth/spectrum_audit/simulate/ui_model/scan_adapter）
- 冻结契约：`contract/multisignal_contract.json`、`contract/target_record_schema.json`
- 集成：`integration/patch_standalone_receiver.diff`、`integration/standalone_receiver.multisignal.py`、
  `integration/README.md`
- 判分脚本：`scripts/score_multisignal_run.py`；占用带宽：`scripts/verify_public_bw.py` +
  `results/public_bw_verification.json`
- 文档：`docs/INTEGRATION_LAYER.md`、`docs/OCCUPIED_BW_VERIFICATION.md`、
  `docs/SCAN_SUPPORT_AUDIT.md`、`docs/FROZEN_PARAMS.md`、`docs/TEST_CHECKLIST.md`、
  `docs/SCORING_SPEC.md`、`docs/TX_SYNTH_AUDIT.md`、`docs/UI_PLAN.md`、本文档
- RF 草稿：`rf/RF_COMMANDS_DRAFT.md`（待 FPGA 验收后执行，含阻塞项）

## 给主线程的提示（修订后）

- 扫描步长上限按主链既有 `0.9*fs = 2304000` 冻结，**不再**提 2302500，也不要求
  步长为 2500 整数倍；频谱拼接按实际整数 Hz 坐标（合同 §3 修订）。本线不改 A/B 树。
- `power_valid` 数值契约已补（来源/单位/有效范围），明确不标 dBm。
- 集成补丁合入前必读 `integration/README.md` 的「诚实边界」：锁定期按目标重访调度
  未写进最小补丁（完整参考 `src/scan_adapter.py`）；`rml24_targets` 是新增事件 schema，
  需板端 C++ 列表页对接；`multisignal_tracker.py` 需与 entry 同级部署。

## RF 阶段阻塞项

FPGA 验收未过 / 主线程未授权板测 / 真实**载荷**占用带宽未回填（真实公共前导/尾
已核验满带宽）/ 重叠与跨带场景无证据。四项全未满足前不发射。
