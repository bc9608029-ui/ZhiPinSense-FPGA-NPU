# sdr_full_chain_12class_combined_v1 — NPU + HDMI 合并位流与十二类实时完整链路（任务 39e5 最终阶段）

> **离线状态：`READY-FOR-COMBINED-BITSTREAM-IMPLEMENTATION`（Phase 0 可行性审计完成）**
> （未经实机验证，**绝不**标 PASS / READY；我禁碰板 / 禁写 Flash，上板由用户本人执行。）

## 本工程做什么

把 ZG330 NPU 与 HDMI 720p 帧缓冲**合并进同一位流**，实现真正的实时全链路：

```
Pluto SDR → RX IQ → NCO/重采样/receiver_scale → 十二类 NPU → ResultFrame v2
         → Unix Socket → HDMI 实体屏幕  ↕  TOUCH 触摸交互（Gate C7）
```

- **必须真实并发**，禁止用 Golden/Mock/离线回放冒充实时。
- 四个保护原工程**绝不修改**：`pl_ddr_mandatory_core_v1`（NPU FPGA）、
  `hdmi_framebuffer_ui_v4_fix`（HDMI FPGA+SW）、`npu_realtime_v1`、`sdr_full_chain_12class_v1` /
  `sdr_full_chain_12class_ui_v1`（十二类软件链）。

## 当前进度（Phase 0 完成 · Phase 1 进行中）

| 阶段 | 状态 |
|---|---|
| Phase 0 可行性审计（§四） | ✅ 完成，见 `docs/COMBINED_FEASIBILITY_AUDIT.md` |
| Phase 1 M1 基线复现 + M2 frame_ctrl 接入 + 1GHz 分析 | 🔄 进行中，见 `docs/PHASE1_M1_M2_PLAN.md` + `docs/TIMING_1GHZ_DECISIVE_ANALYSIS.md` |
| §五-§六 合并实现 + Vivado/FMSH 硬门（M3-M7） | ⏳ 待 M1/M2 回报后 |
| §七 软件集成（含 Gate C7 触摸 evdev） | ⏳ 未开始 |
| §八 主机/仿真测试 | ⏳ 未开始 |
| §九 Gate C1-C7 板测（仅用户上板） | ⏳ 未开始 |
| §十 交付包 | ⏳ 未开始 |

## Phase 0 关键结论（先读）

1. **地址不冲突**：两 `ps_ai.bd` byte-identical（`78f5599b…`），地址图 4 段各 512K 互不重叠；
   NPU `0x40000000` 与 frame_ctrl `0x40080000` 可同一位流共存。**此前 ui_v1 的"地址冲突导致互斥"结论
   基于错误的 1MiB 假设，已被权威 BD 地址图推翻**——真实原因是**原先尚无同时实例化 NPU 和 HDMI 的
   位流**，且**旧位流不具备完整链路能力**（见 `docs/ADDRESS_MAP_AUDIT.md`）。
2. **无缺失资产**：NPU（AI_Mate.edif + Mandatory Core RTL + BD + XDC）与 HDMI（fb_read_720p +
   frame_ctrl + 显示核 + XDC）资产齐全，且各自位流均已上板实证可构建/运行。
3. **唯一硬集成点**：HDMI 引脚（AC17/AA15/Y16/W16）有两个驱动源（NPU 的 SDI/cam 显示 vs
   fb_read_720p），合并需二选一让 fb_read_720p 独占。
4. **DDR 独立**：PS DDR（32-bit，Linux+帧缓冲）与 PL DDR（64-bit MIG，NPU DMA）互不争抢，无带宽阻塞。
5. **PS 已具备 USB0**：Gate C7 触摸（1a86:e5e3）+ Pluto（0456:b673）+ Hub（0424:2514）在合并位流
   PS 配置下**具备同时枚举条件**。`USB0 配置一致` 仅证明逻辑枚举能力，不证明供电/长期稳定性；
   **TOUCH 与 Pluto 具备同时枚举条件，最终稳定性仍待 Gate C7 实测**。

## 状态红线（§十一 + Gate C7）

- 命名序列：`READY-FOR-COMBINED-BITSTREAM-IMPLEMENTATION` →
  `READY-FOR-COMBINED-BITSTREAM-HARDWARE-TEST` → `FULL_CHAIN_HARDWARE_PASS`（C1-C6）→
  `FULL_CHAIN_WITH_TOUCH_HARDWARE_PASS`（C1-C7 全过）。
- 绝不伪造合并位流、绝不 Golden/Mock 冒充实时、绝不降低 0.90 门限、绝不改标签序、
  绝不偏移比较、RF 绝不 Golden、禁碰板、禁写 Flash、绝不动保护原工程。

## 目录

```
sdr_full_chain_12class_combined_v1/
├── docs/                        ← Phase 0 五份审计 + 来源清单（本阶段产出）
├── SOURCE_PROVENANCE_SHA256.txt ← FPGA 来源资产 SHA256 锚定
├── fpga/                        ← 后续 §五-§六 合并 RTL/脚本/位流
├── board_package/ sdr_adapter/ ui_sw/  ← 后续 §七 软件（含触摸 evdev）
├── scripts/ host_tests/         ← 后续 §七-§八
├── model_12class/ deployment_golden/  ← 后续冻结模型 + Golden
└── dist/                        ← 后续交付包
```
