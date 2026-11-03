# 统一交接：主链 + FPGA 辅助智能扫频 + 多信号扫频（三线并行收口）

日期：2026-10-29。唯一入口，覆盖并取代 `HANDOFF_PARALLEL_MAINCHAIN_FPGA_MULTISIGNAL_20261029.md`
与 `NEXT_API_THREE_LINES_20261029.md` 的推进状态。电脑侧离线集成/验证已收口；**板端步骤全部待用户 COM12 执行**。

## 0. 一句话状态

三线离线全部收口且与修订后公共合同一致：主链候选离线 PROMOTION_CANDIDATE、FPGA 生产 OOC + 真实核功能验证双 PASS、多信号离线模块就绪。RF/位流/实屏触控均未跑，待板端。

## 1. 主线程合入记录

- 公共合同 `F:\嵌赛\SHARED_CONTRACT_PARALLEL_20261029.md`（冻结）：后端枚举 `software/fpga/auto`、内部整数 Hz、目标记录九字段、判分口径、红线、交付门。§3 已按新任务书修订：界面可显 MHz/GHz/MS/s 并标单位、十进制输入精确转整数 Hz、**步长不天然 2500 整数倍**、`2304000=0.9*fs` 是跨度上限非 fs。
- 证据复审：三线均未写 `RF_PASS`/`PROJECT_COMPLETE`；均未跨树修改（C 明确只读 A/B）；板端/RF/位流均如实标「待执行」；无重复打包冒充实现。

## 2. 三线结果

### A 主链（树 `F:\嵌赛\rml24_mainchain_finalize1_20261028`）
- 终态 `PROMOTION_CANDIDATE_OFFLINE_PACKAGE_READY_TARGET_ACCEPTANCE_PENDING`。
- 真实 RF 固定分母：定频候选 **233/240**、扫频 **237/240**、漏项 0（原基线 227/232）。
- 五页 UI（Top3/MEASURE/瀑布/星座/TUNING）+ 控制闭环离线全 PASS；`audit_release checks=7 failed=0`、`static_audit 16/16`。
- 修订：调谐对齐前提调查=**无**（LO 任意整数 Hz + 粗 CFO，从不 bin 对齐）；2500 倍数限制已删；UI 恢复 MHz/GHz 可读 + 十进制精确转整数 Hz。
- 冻结身份：NPU JSON `28272abc…`、RAW `c1781aec…`、two-DC `e0aa1202…`、接收核 `cb529824…`、覆盖层独立接收器 `4d35cf5e…`。平均策略=8 段相同载荷重复相干平均（非被否决的八段不相关窗口平均）。
- 板端：`candidate/docs/BOARDTEST.md` A–E 六步（备份→install_overlay 校验 7 冻结 SHA→板端 C++ 编译→py_compile→24+24 smoke+触控+十进制 MHz 键盘→240+240 固定分母回归）。

### B FPGA（树 `F:\嵌赛\rml24_fpga_smartscan_prep2_20261028`）
- 生产 OOC PASS（Hann framer+XFFT9.1+u54+fftshift 双缓冲，100MHz setup +0.154/hold +0.101ns）。
- **真实厂商核功能验证 PASS**：`SMARTSCAN_REAL_FFT_SIM result=PASS tones=2`（`TB_SMART_SCAN_REAL_FFT PASS tones=2 cases=12 faults=3`）。forward 修复定稿（`cfg_tdata[0]=FWD_INV=1`）；+37bin→fftshift 549、−37→475 精确命中、**不镜像**（镜像即逆变换）。
- 故障定义：tlast 异常 / 输入饥饿（`event_data_in_channel_halt`，非「输出太慢」）/ 输出失步，锁存 `data_halt`→`status_overflow`。
- NumPy 对照 `CHECK_REAL_FFT_NUMPY result=PASS cases=9`（峰值相对容差 0.05；定点蝶形截断致非逐位一致，属预期）。行为净表 SHA `d899bd48…`（真 XFFT 9.1 行为模型，非空壳/EDIF/自写 DFT）。
- 证据：`evidence/real_fft_review_fix/`（10×psd_<case>.hex + xvlog/xelab/xsim 日志 + SHA256SUMS + frozen_inputs.sha256）。
- 剩余（本轮未做）：PS→PL AXI 数据通路、双缓冲回读（PS 读前查 frame_id/protocol_error/overflow/bank ownership）、`software/fpga/auto` 三后端 + auto 回退、候选位流、板端 same-IQ A/B + 1000 帧 + 24+24 smoke + 240+240 RF。

### C 多信号（树 `F:\嵌赛\rml24_multisignal_prep1_20261029`）
- 终态 `OFFLINE_PREP_COMPLETE`，`pytest` 48 passed，两份契约 JSON 解析通过。
- 如实结论：现有正式扫频器/UI **不支持多信号**（单 SDR 顺序扫描、只留最强一个命中、无去重/老化）。
- 离线补齐：`src/`（psd 多候选 / tracker 去重老化 target_id 不复用 / scoring 检出分类分开漏项固定计错 / tx_synth 多载波 / spectrum_audit / simulate / ui_model）+ 测试清单 + 判分口径 + UI 蓝图 + RF 命令草稿。
- 参数口径：12.5kHz/25dB/14dB 门=**待板测验证测试目标**（非冻结承诺）；`power_valid`=数值契约（峰值 prominence−自适应中位噪声底，dB 相对中位噪声底，范围 [14,80]，NaN=未测，不标 dBm）；`max_step_hz=2304000`。
- 剩余：真实入口集成 + 多信号 RF（排在 FPGA 辅助链验收之后）。

## 3. 板端执行顺序（用户 COM12，分阶段）

1. **主链 A 验收**：`install_overlay.sh --base <旧树> --out <新测试树>`（校验 7 冻结 SHA）→ 板端 C++ 编译 → 24+24 smoke + 五页触控 + 调谐键盘 → 240+240 固定分母回归（≥233/240 与 237/240 才允许独立部署，否则回滚）。
2. **FPGA B 候选**：完整顶层（含 NPU/HDMI）synth/P&R/STA/DRC → 独立候选位流 + 回退清单 → 板端 same-IQ A/B + 1000 帧 + 故障回退 + 24+24 + 240+240 RF。
3. **多信号 C RF**：仅在 FPGA 辅助链验收通过后执行；先回填真实公共帧占用带宽，再 RF。
4. **整机复验**：断电自启 + 连续运行 + 真实 UI + 外壳装配。

## 4. 红线（不变）

不碰板/不写 Flash/禁发射（板端由用户执行）；模型 IQ / 冻结 NPU / 软件扫频 / 旧位流不变；`auto` 回退必须；OOC 外壳 `production_bitstream=NO`；禁写 `RF_PASS`/`PROJECT_COMPLETE` 直至证据齐备；失败保留分母、不择优；重型 Vivado/Procise 构建排队。

## 5. 待板测 / 阻塞汇总

- A：板端 C++ 编译 + 实屏触控 + 240+240 RF 未做。
- B：PS/PL 接口 + 候选位流 + same-IQ/回退/RF 未做。
- C：真实入口集成 + 多信号 RF 未做（阻塞在 B 验收）。
