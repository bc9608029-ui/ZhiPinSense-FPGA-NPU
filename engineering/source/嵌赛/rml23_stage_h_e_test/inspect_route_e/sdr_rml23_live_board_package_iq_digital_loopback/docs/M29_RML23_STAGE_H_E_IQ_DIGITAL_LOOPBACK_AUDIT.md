================================================================================
 M29 RML23 Stage H-E — 同设备调制IQ数字回环测试准备 — 硬件能力审计（先审计，暂不编码）
================================================================================
状态: 审计结论（未编码，未碰板，未训练）
基线: sdr_rml23_live_board_package_synthetic_iq_route_d.tar.gz
      sha256 5a4c4d3ab7d892cfab3b2237cc714daee4bc896246fc3b46bd91ff90acedd688
      （Stage G A/B/C/D 全保持，本审计只读，不改任何 .cpp/.hpp/.sh/.py）

--------------------------------------------------------------------------------
 0. 结论摘要（先给结论）
--------------------------------------------------------------------------------
 [V-1] DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN
       任意 TX DMA 调制 IQ 经 digital loopback（mode=1）在 2.56 MSPS 下忠实回环，
       当前【未板证】。现有 digital 相位只 TX 过 10 kHz CW 单音，从未 TX 过任意调制
       IQ，更未验证 2.56 MSPS 下 loopback 是否保真/无损/无 I-Q 换位/无增益相位失配。
       「loopback=1 在 DAC 前/ADC 后」是驱动+数据手册语义，非板端实测结论。
       → Route E 必须作为【测量仪表】设计：板端首跑【观测并报告】回环是否保真，绝
         不得预设保真；判决只能由板上实测给出（见 §4）。

 [V-2] RF_LEAKAGE_NOT_PROVEN
       现有代码对「外部 TX 口静默」的唯一证据 = loopback=1 + TX 衰减 -89.75 dB，
       且【无 ENSM 控制、无 TX 射频链路关断、无静默回读证据】。衰减到 -89.75 dBc
       ≠ 证明静默，也不等于 TX RF 输出被禁用。DeviceParams 只保存/恢复 10 个属性，
       【不含 ENSM】。→ Route E 板端必须打印 RF_LEAKAGE_NOT_PROVEN（除非后续新增
       显式 TX 静默 + 回读，且该静默仍只能由板测证明）。不得把物理 RF 泄漏/RF 回环
       伪装成数字回环。

 [V-3] generated-2p56m 输入源缺口
       Route C（generated 2.56 MSPS）的 int16 IQ 只在内存中生成（synthetic_iq_runner
       .hpp:271 的 `iq` 向量），push_int16 后即丢弃，【从不落盘】。RawRxOutput 只回传
       tensors(fp32)+quant，不保留 int16。→ 当前【不存在】可复用的 frozen
       generated-2p56m 工件。Route E 的 --input-kind=generated-2p56m 需先做一处
       【微小的、非语义的 Route C 持久化补充】（把已算出的 `iq` 字节原样 save_raw_iq，
       不改 tensors/量化/推理），否则该输入源应判定为 BLOCKED（见 §5）。

 [V-4] radioml-reconstructed-2p56m 输入源可复用
       Route D 已持久化 `quantized_raw_rx_%06d.ci16`（全 16-bit 交错 int16、I 前 Q 后、
       小端、2.56 MSPS）+ roundtrip_manifest.tsv(13 列) + radioml_original_*.f32 参考，
       Route E 可直接复用这些【实际字节】（见 §5）。

 [V-5] 单进程所有权、RAII、TX/RX buffer 同上下文均已就绪；唯一 RAII 缺口=ENSM。

--------------------------------------------------------------------------------
 1. 11 项审计表
--------------------------------------------------------------------------------
 # | 审计项                       | 结论（证据文件:行）
 --+------------------------------+--------------------------------------------------
 1 | 当前 --phase=digital 调用链  | run_loopback_phase（board_gate9_full_chain_rml23
   |                              | .cpp:427-907）。loopback=(phase=="rf")?0:1；
   |                              | make_device → DeviceStateGuard → negotiate_sample_
   |                              | rate(128000) → set_rx_gain_mode("manual")+set_rx_
   |                              | gain+set_loopback → Producer12 → 控制 socket/线程 →
   |                              | PlutoTx{waveform=make_periodic_tone(tone_hz,fs,8),
   |                              | tx_atten=--tx-atten(默认 -89.75)} → prepare →
   |                              | start_cyclic。循环 capture_contiguous → push_int16 →
   |                              | pull_tensor → npu.infer(24) → merge23 → producer。
   |                              | PASS = frames_ok && tone_ok(ratio_min>0.3) && rf_ok
   |                              | && presence_ok && valid==total。
 2 | 10kHz tone：DDS or TX DMA   | 【host 生成 + TX DMA】，非内部 DDS。make_cw_tone/
   |                              | make_periodic_tone 在主机算 cos/sin，载入 TX DMA
   |                              | cyclic buffer（pluto_tx.cpp/pluto_tx.hpp）。AD9364
   |                              | 虽有内部 DDS（流名 cf-ad9361-dds-core-lpc 即 DDS
   |                              | core），但本代码【未】写 DDS 寄存器，全走 TX DMA。
 3 | loopback 属性位置/取值/回读 | ad9361-phy 的【debug】属性：wr_dbg_ll →
   |                              | iio_device_debug_attr_write_longlong(phy_,
   |                              | "loopback", mode)（pluto_device_libiio.cpp）。
   |                              | 取值 0=off(外RF)/1=digital/2=internal-RF。
   |                              | 回读=read_longlong；恢复=DeviceStateGuard.restore_
   |                              | params（save 的 10 属性含 loopback，best-effort）。
 4 | loopback 在 DAC/ADC 前后    | mode1=数字基带回环（DAC 前/ADC 后）；mode2=内部 RF
   |                              | 回环（DAC 后/ADC 前）。此为 AD9361/9364 标准语义 +
   |                              | iio_attr_routing.hpp 契约声明（"不对外发射"），
   |                              | 【非板端实测】。板测需回读确认 mode 落点。
 5 | 任意 TX DMA IQ 能否过 loopback | tx_start_cyclic 接受【任意】交错 int16（只校验
   |                              | step==4 字节 + convert_inverse）。故任意 IQ【能载入】
   |                              | TX DMA；但 2.56 MSPS 下经 digital loopback 是否
   |                              | 保真/无损/序对/增益相位一致【未板证】。
   |                              | → DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN。
 6 | TX/RX 通道名/IQ排列/位宽/缩放 | TX=cf-ad9361-dds-core-lpc volt0=I volt1=Q；
   |                              | RX=cf-ad9361-lpc volt0=I volt1=Q。12-bit 转换器，
   |                              | 主机域 16-bit（iio_channel_convert(_inverse) 做
   |                              | 12↔16，shift=4）。满幅 ±2048=2^11（kDacFullScale）。
   |                              | Route D 量化用全 16-bit（±32767/32768），进链再
   |                              | ÷2048（PreprocessChain.push_int16）。
 7 | TX/RX buffer 同进程          | LibiioDevice 在同一 iio context 持有 txbuf_ 与
   |                              | rxbuf_（pluto_device_libiio.cpp）；digital 相位已
   |                              | 单进程同时 TX cyclic + RX read 验证。同进程成立。
 8 | loopback 时外部 TX 口 RF 泄漏 | 仅 loopback=1 + TX 衰减 -89.75 dB；【无 ENSM、无
   |                              | TX 射频关断、无静默证据】。→ RF_LEAKAGE_NOT_PROVEN。
 9 | 关闭/衰减外部 TX + 回读证据 | TX 衰减=TX 控制通道 hardwaregain（负 dB，floor
   |                              | -89.75/ceiling -40），set_tx_atten→wr_d；PlutoTx.
   |                              | prepare() require_exact_d 写后回读（衰减/LO/BW/RX
   |                              | gain）。故「衰减已写且已回读」有证据；但「静默」无
   |                              | 证据（见 #8）。RF(loopback=0) 需 --confirm-safe-rf-path。
 10| RAII/cleanup 恢复            | DeviceStateGuard 保存/恢复 10 属性（rx_lo/tx_lo/
   |                              | rx_sr/tx_sr/rx_bw/tx_bw/rx_gain_mode/rx_gain/
   |                              | tx_atten/loopback），【不含 ENSM】（缺口）。PlutoTx
   |                              | RAII destroy TX buffer + stop；SIGINT/SIGTERM 设
   |                              | sig_atomic_t 标志，循环 break 后走 catch/cleanup 的
   |                              | guard->restore()。硬 SIGKILL 无法恢复（不可解）。
   |                              | → Route E 需补 ENSM 保存/恢复（若引入 TX 静默）。
 11| Route E 复用哪些 Stage G 实际IQ | 见 §5：radioml-reconstructed-2p56m 复用 Route D
   |                              | 的 quantized_raw_rx_*.ci16 + roundtrip_manifest.tsv
   |                              | + radioml_original_*.f32；generated-2p56m【无持久化
   |                              | 工件】，需先补 Route C 持久化或 BLOCKED。

--------------------------------------------------------------------------------
 2. 现有 --phase=digital 调用链（展开）
--------------------------------------------------------------------------------
 入口: ./run_gate9_rml23.sh --phase=digital [--tx-atten ..] [--tone-hz ..]
   main() (board_gate9_full_chain_rml23.cpp:2437) → 非 offline/ambient/live-rx/
   synthetic-iq 的 phase 全走 run_loopback_phase（:2474）。

 run_loopback_phase 顺序（:427-907）:
   1. loopback = (phase=="rf") ? 0 : 1       // digital→1，rf→0(需 confirm-safe-rf-path)
   2. make_device() → pluto::Device（单 IIO context，含 TX+RX）
   3. DeviceStateGuard guard(dev)             // 构造时 save_params()（10 属性，无 ENSM）
   4. negotiate_sample_rate(dev, default_rate_candidates(), 128000)
      // 首选 2.56 MHz(÷20)，回退 3.84 MHz(÷30)；write-readback 精确 + 整数比校验
   5. set_rx_gain_mode("manual") + set_rx_gain(gain_db)
   6. set_loopback(loopback)                  // debug attr，wr_dbg_ll
   7. Producer12 + 控制 socket + 线程
   8. PlutoTx: txc.waveform = board::make_periodic_tone(tone_hz, neg.actual_hz, 8)
              txc.tx_atten_db = opt --tx-atten 默认 pluto::kSafeTxAttenDb(-89.75)
              txc.loopback = loopback
   9. txc.prepare()  // 固定序: tx_stop→safe atten→RX manual→align LO→set_loopback
                     //           →ramp atten≤-40；loopback==0 且无 confirm 则 throw；
                     //           tx_atten_db > kSafeTxCeilingDb(-40) 则 throw
  10. txc.start_cyclic()                     // 载入 tone 到 TX DMA cyclic
  11. 循环: capture_contiguous → chain.push_int16 → pull_tensor → npu.infer(24)
           → merge23 → producer.on_frame → result（heartbeat + result frame）
  12. PASS = frames_ok && tone_ok(ratio_min>0.3) && rf_ok && presence_ok && valid==total
  13. catch/cleanup: guard->restore() + restore_report

 关键事实:
  * 该相位 TX 的【只有 10 kHz CW 单音】，从未 TX 过调制 IQ。
  * 采样率协商可落在 3.84 MHz（回退），但 Route E 复用 2.56 MSPS 工件必须强制落
    2.56 MHz 并 fail-closed（3.84 MHz 与 2.56 MSPS 工件速率不匹配）。

--------------------------------------------------------------------------------
 3. RF 泄漏控制证据（+ RF_LEAKAGE_NOT_PROVEN 判定）
--------------------------------------------------------------------------------
 现有（有证据的）:
   [E1] TX 衰减写入 + 回读: TX 控制通道 hardwaregain（负 dB），set_tx_atten→wr_d；
        PlutoTx.prepare() 对衰减/LO/BW/RX gain require_exact_d 写后回读。
        floor -89.75 dB / ceiling -40 dB（pluto_tx.hpp kSafeTxAttenDb/kSafeTxCeilingDb）。
   [E2] 数字回环选通: set_loopback(1) debug attr 写入 + 回读（restore 亦回写）。
   [E3] 外 RF 路径(loopback=0) 无 --confirm-safe-rf-path 即 throw（防误开外发）。

 缺失（无证据，故 RF_LEAKAGE_NOT_PROVEN）:
   [G1] 无 ENSM 控制: DeviceParams/Device 接口【没有任何 ENSM/state 读写】
        （pluto_device.hpp），save_params 也只 10 属性不含 ENSM。
   [G2] 无 TX 射频链路关断/standby/TX-DFE 静默: 仅靠 -89.75 dB 衰减，未关 TX 链。
   [G3] 无「静默」回读证据: 衰减写回 ≠ 静默证明；无任何 TX 输出功率/泄漏测量。

 判定: loopback=1 + TX -89.75 dB 是【降低泄漏】的手段，但【不是静默证明】。
   Route E 板端必须打印 RF_LEAKAGE_NOT_PROVEN（除非后续新增显式 TX 静默 + 回读，
   且静默本身仍只能由板测证明）。不得把物理 RF 泄漏/RF 回环伪装成数字回环。

--------------------------------------------------------------------------------
 4. 数字回环能力判定（DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN）
--------------------------------------------------------------------------------
 已证实的（可复用为 Route E 的前置）:
   [P1] 任意交错 int16 可载入 TX DMA（tx_start_cyclic 只校验 step==4）。
   [P2] 单进程同 context 同时持有 TX/RX buffer（TX cyclic + RX read 已跑通）。
   [P3] loopback debug attr 的写/回读/恢复链路正确（iio_attr_routing 契约 + 单测）。
   [P4] 采样率 2.56 MHz（÷20 到 128 kHz）协商可精确落点并回读。

 未证实的（Route E 板上首跑必须【观测】，不得预设）:
   [U1] 2.56 MSPS 下任意调制 IQ 经 digital loopback 是否【保真】（NMSE/EVM/CFO/
        增益相位/I-Q 序/DC/PAPR 是否通过）。
   [U2] 是否存在丢样/重复样/wrap/不连续（短帧、溢出、refill 不连续）。
   [U3] TX 与 RX 采样时钟/相位是否锁定一致（数字回环虽同芯片，但 TX/RX 路径
        是否引入 CFO/相位漂移仍待测）。
   [U4] 「loopback=1 在 DAC 前/ADC 后」的驱动语义是否与板上实际路径一致。

 判决契约（Route E 只允许 7 种判决，见 Route E 需求）:
   DIGITAL_LOOPBACK_PRESERVES_IQ / DIGITAL_LOOPBACK_DISTORTS_IQ /
   DIGITAL_LOOPBACK_PREPROCESS_DIVERGENCE / MODEL_INPUT_SENSITIVITY /
   SYNC_OR_WRAP_INCONCLUSIVE / DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN /
   INSUFFICIENT_EVIDENCE。
   其中 PRESERVES/DISTORTS 只能由【板端实测】给出，本审计阶段只能落
   DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN。

--------------------------------------------------------------------------------
 5. Route E 复用 Stage G 字节的方案
--------------------------------------------------------------------------------
 5.1 radioml-reconstructed-2p56m（可复用，Route D 已持久化）
   复用文件（Route D run_route_d_roundtrip 产出，:2033-2124）:
     quantized_raw_rx_%06d.ci16   ← 复用为 Route E 的 TX 注入字节
         全 16-bit 交错 int16、I 前 Q 后、小端、2.56 MSPS、Route D 显式统一幅度映射
         (signal RMS=16 counts) + quantize_int16_signal_rms 全 16-bit 量化。
     radioml_original_%06d.f32    ← [2,1024] fp32 参考（Stage G ref tensor）
     interpolated_2p56m_%06d.f32  ← 量化前 2.56 MSPS fp32 参考（诊断对齐用）
     roundtrip_manifest.tsv       ← 13 列 keying: index/source_index/hdf5_label/
         snr_db/class_index/class_name/6 文件名/original_sha256
   fail-closed 需补充字段（Route D manifest 未记录，Route E 用【自己的 sidecar】
   manifest，绝不改 Route D 冻结 manifest）:
     dtype=interleaved int16(int16le)、IQ order=I,Q、sample_rate=2560000、
     sample_count、expected_class(=class_index 0..23)、source_index、quant scale
     (signal_rms→16 counts 映射)、seed(=0x39e5)。
   Route E 读入时对每个 .ci16 做 SHA-256 fail-closed + size + sample_rate 断言。

 5.2 generated-2p56m（缺口，需先补 Route C 持久化或 BLOCKED）
   现状: Route C generate_raw_rx_tensors（synthetic_iq_runner.hpp:252-292）在
   内存中 quantize_int16 得到 `iq`（:271），push_int16 后丢弃；RawRxOutput 只回传
   tensors+quant（:243-246），【不保留、不落盘 int16】。
   结论: 当前无 frozen generated-2p56m 工件。因「禁止重新生成理论相同波形」，
   Route E 不得自行重算。
   两条出路（编码阶段二选一，需用户批准其一）:
     (a) 补 Route C 持久化: 在 run_synthetic_iq_phase route==C 分支，把已算出的
         `iq`（每调制连续波形）原样 board::save_raw_iq 写入 --raw-iq-out-dir（默认
         关闭），并写一个小 manifest（mod/seed/sps/rms_counts/sample_count/SHA）。
         纯新增落盘，不改 tensors/量化/推理/判决 → 不构成"重新生成"，是持久化
         "已实际存在的字节"。
     (b) Route E 的 --input-kind=generated-2p56m 暂判 BLOCKED，等 (a) 落盘后再开。
   Route E 编码采用 (a) 为推荐（符合"复用 Stage G 实际字节"且零语义改动）。

 5.3 速率约束（两个输入源共用）
   Route E 必须强制协商 RX 与 TX 采样率均=2560000 且 write-readback 精确一致
   （fail-closed 拒绝 3.84 MHz 回退），否则 2.56 MSPS 工件与链速率不匹配。

--------------------------------------------------------------------------------
 6. 预期修改文件清单（Route E 编码阶段，待本审计批准后执行）
--------------------------------------------------------------------------------
 新增:
   board_package/iq_digital_loopback.hpp         回环注入/对齐/度量/判决纯逻辑
   board_package/iq_digital_loopback_runner.hpp  单进程编排（IIO→TX/RX→preprocess→NPU）
   host_tests/test_iq_digital_loopback.cpp       12 项自动化测试（parse/fail-closed/
                                                  确定/sync/wrap/DSP/RAII/单进程/NPU/
                                                  契约/no-regression/offline 240）
   scripts/analyze_iq_digital_loopback.py        host 逐帧结果分析 + 判决模板
   scripts/package_iq_digital_loopback.py        Route E 打包器（patch+merged）
   docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_VERDICT_TEMPLATE.md  判决报告模板
   （若采用 5.2(a)）scripts/ 或 Route C 分支的 --raw-iq-out-dir 持久化 + 小 manifest
 修改（均为 .cpp/.hpp/.sh/.py/.md，无模型/位流/RTL/Flash）:
   board_package/board_gate9_full_chain_rml23.cpp  main() 加 --phase=iq-digital-loopback
                                                  dispatch + run_iq_digital_loopback
   board_package/gate9_phase.hpp                  valid_phase 增 iq-digital-loopback
   scripts/run_gate9_rml23.sh                     头注释 + 用法（+若 5.2(a) 的持久化开关）
   host_tests/build_host_tests.sh / run_tests.sh  增 Route E 目标与运行入口
   docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_AUDIT.md（本文件）→ 审计通过后转
                                                  §8 编码记录/判决记录
 不改动: digital/rf/ambient/live-rx/synthetic-iq 现有语义；Stage G A/B/C/D 全保持；
         不覆盖任何历史包；模型 json d43a2284…/raw 2425d990…/位流 22fec95c…/
         HDF5 e3dd0bef…/标签 3e1382d1… 冻结不变。

--------------------------------------------------------------------------------
 7. 红线与最高状态
--------------------------------------------------------------------------------
 禁碰板、禁训练；禁写 RML23_LIVE_HARDWARE_PASS / NPU_PASS / UI_HARDWARE_PASS /
 UI_VISUAL_PASS / RF_PASS / HARDWARE_PASS / PROJECT_COMPLETE / FINAL_*。
 不得把物理 RF 泄漏/RF 回环伪装成数字回环；不得重新生成"理论相同"波形。
 最高状态: M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST。
 不得写 Route E 分类通过 / RF 安全已证明 / 项目完成。
 板端首跑必须先观测并报告回环保真与 RF 泄漏，判决只能由板上实测给出。
================================================================================

--------------------------------------------------------------------------------
 8. 编码记录（审计通过后，§6 文件清单的落地）
--------------------------------------------------------------------------------
 已按 §6 落地 Route E 编码，全部为 .cpp/.hpp/.sh/.py/.md，无模型/位流/RTL/Flash：

 新增:
   board_package/iq_digital_loopback.hpp         回环加载/对齐/度量/判决纯逻辑
   board_package/iq_digital_loopback_runner.hpp  单进程编排（IIO→TX/RX→preprocess→NPU）
   host_tests/test_iq_digital_loopback.cpp       12 项自动化测试（见 §8 测试）
   scripts/analyze_iq_digital_loopback.py        host 逐帧结果分析 + 三判决分离
   scripts/package_iq_digital_loopback.py        Route E 打包器（patch+merged）
   docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_VERDICT_TEMPLATE.md  判决报告模板
 修改:
   board_package/board_gate9_full_chain_rml23.cpp  Route C --raw-iq-out-dir 持久化
                                                   （3-way SHA + 24 列 manifest +
                                                   tensor/logits SHA 身份 + frozen
                                                   参考计数）+ --phase=iq-digital-
                                                   loopback dispatch + 薄包装
   board_package/gate9_phase.hpp                  valid_phase 增 iq-digital-loopback
   scripts/run_gate9_rml23.sh                     头注释 + 用法（C 持久化开关 + E）
   host_tests/build_host_tests.sh / run_tests.sh  增 Route E 目标与运行入口
   docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_AUDIT.md（本文件）→ 本节

 硬要求逐条落点：
   1  C 持久化保存 push_int16 的同一块后量化字节（outp.iq[0..pushed_complex*2)，
      I0,Q0,I1,Q1 交错 int16 LE），save 前内存 SHA / 落盘文件 SHA / 重读 SHA 三者一致
      （board_gate9_full_chain_rml23.cpp Route C 分支）。
   2  持久化默认关闭（--raw-iq-out-dir 空 = 完全旁路），不影响 Route C 历史输出。
   3  manifest 记录 dtype=ci16le / layout=interleaved_iq / sr_req+sr_act / complex /
      byte / seed / source / mod / symrate / beta / span / sps / norm / rms /
      quant_scale / clip / clip_ratio / sha / tensor_sha / logits_sha /
      frozen_frames / frozen_deployed_correct（24 列，带 # 头行）。
   4  Route E 只读 frozen 文件与 Route D 已有 i16；缺失报 STAGE_G_FROZEN_IQ_REQUIRED
      （iq_digital_loopback.hpp::verify_frozen_file / load_ci16）。
   5  旧 Route D 包与 1158dbfd…/6c3258a7…/5a4c4d3a… 不覆盖；C 持久化作为前置增量记入
      新 patch（package_iq_digital_loopback.py，基线=synthetic_iq_route_d 5a4c4d3a…）。
   6  DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN 保持前置状态，host 测试后不改成 PROVEN。
   7  RF_LEAKAGE_NOT_PROVEN 保持；TX 最大衰减写入+回读；不接天线/同轴；日志持续标记；
      ENSM 不在 Device 接口（无读写），记录 ensm=not_managed_by_this_code（未修改）。
   8  采样率判定 abs(actual-2560000)<=5 Hz（2559999 可接受；3840000 fail-closed）；
      PreprocessChain 仍用冻结 nominal 2560000；不据分类动态改采样率。
   9  Route E 分别跑 generated-2p56m 与 radioml-reconstructed-2p56m，不混合汇总。
   10 报告写 arbitrary_modulated_iq_fidelity=BOARD_REQUIRED（不写整能力不存在）。
   11 基础设施/保真/分类三判决分离；分类错误不判基础设施 FAIL，反之亦然。

 主机自洽测试（host，未碰板）：
   host_tests/test_iq_digital_loopback.cpp 通过（见 bin 运行），覆盖：纯循环延迟 /
   +90° 旋转 / 有界延迟搜索恢复精确（delay/gain/phase/NMSE/corr/CFO）、五路保真
   判决、四路分类判决、装载器 fail-closed（缺 manifest / 未知 input-kind / 不安全
   文件名 / 错误 dtype / 3840000 采样率 / SHA/尺寸失配）、generated/radioml sidecar
   端到端往返。analyze_iq_digital_loopback.py 用合成日志自测通过（三判决分离输出）。

 板端（待用户上板，本阶段不执行）：
   ./run_gate9_rml23.sh --phase=iq-digital-loopback --input-kind=generated-2p56m \
       --frozen-dir DIR
   ./run_gate9_rml23.sh --phase=iq-digital-loopback \
       --input-kind=radioml-reconstructed-2p56m --frozen-dir DIR
   判决填写 docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_VERDICT_TEMPLATE.md。
================================================================================
