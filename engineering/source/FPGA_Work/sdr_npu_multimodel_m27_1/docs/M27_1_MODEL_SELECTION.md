# M27.1 模型选择（Model Selection）

任务 id="39e5" · M27.1 · 板端探针用两个**真实编译 NPU 模型**（A/B）。**禁止用 stub 冒充真实 NPU 模型。**

---

## 1. 模型 A — 12 类正式模型（冻结，只读引用，禁止修改）

| 项 | 值 |
|---|---|
| 身份 | 12 类 NPU 分类模型（`12CLASS_CHAIN_VALIDATION_MODEL`） |
| json | `sdr_full_chain_spectrum_monitor_m22_m24/work/pkg/model_12class/model_12class.json` |
| raw | `sdr_full_chain_spectrum_monitor_m22_m24/work/pkg/model_12class/model_12class.raw` |
| json SHA256 | `51364bdf49d280944094f7af89ea4c759b3ae4d0d350be5f8c43e0c5849ab834` |
| raw SHA256 | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |
| 输入契约 | `[1,2,1024]` fp32（plane0=I, plane1=Q，C-order） |
| 输出契约 | `[1,12]` fp32 raw logits |
| 硬算子 | 128 HardOps @zhuget(330)，int8 per-channel 对称量化内部 |

**红线**：模型 A 为**生产冻结模型**，探针只读加载，**不得修改/覆盖/重编译**。探针通过路径参数引用，不复制进包（见 §4）。

## 2. 模型 B — 8 类板证模型（真实编译产物，非 stub）

| 项 | 值 |
|---|---|
| 身份 | 板证 8 类 NPU 模型（`npu_realtime_v1`/`npu_stage_v1` 共用，M20/M21 阶段已真板 PASS） |
| json | `npu_realtime_v1/board_package/model.json` |
| raw | `npu_realtime_v1/board_package/model.raw` |
| json SHA256 | `ad57fc0b4a9ec5ae6e8cd2d2c2c0c91f81ef4e5fc7898447b322dc00c349a2e4` |
| raw SHA256 | `c48979b3ab1bc62fa2efcfb07202ee640513f424244d15d089c89a6d2260b42a` |
| 输入契约 | `[1,2,1024]`（与 A 同源 IQ 布局，探针可复用同一输入张量） |
| 输出契约 | `[1,8]` fp32 raw logits（8 类：argmax_id 0–7） |
| raw 大小 | 2,507,348 字节（vs A 的 2,851,472 字节） |

**为何合法**：
1. B 是**真实 iCraft ZG330 编译产物**（`.json` + `.raw`），非 stub / 非占位。
2. B 已在**同一块板**上真板跑通（`npu_realtime_v1` 冻结输入 `sha256_manifest.txt` 全对上、reference_argmax 12/12）。
3. B 与 A **输入同构**（都是 `[1,2,1024]`），探针可用同一 `tensor_19frames_sint8.bin` 反量化喂两个模型 → 直接测 A→B→A 切换，无需另造输入。
4. B 输出 8 维、A 输出 12 维 → 天然区分两个模型的输出，防混淆。

## 3. 两模型的关键差异（探针判据）

| 判据 | A（12 类） | B（8 类） |
|---|---|---|
| 输出 logits 数 | 12 | 8 |
| raw 体积 | 2,851,472 B | 2,507,348 B |
| weight+instr+ftmp 需求 | 更大 | 更小 |

`probe_two_networks` 同时驻留 A+B 时，若 ZG330 etm 不足，`apply()` 或 `forward()` 应报错/失败 → 据此判定驻留容量边界（fail-closed，不掩盖错误）。

## 4. 探针如何拿到模型文件

- 探针**不复制**模型文件进本包；通过命令行参数 `--model-a-json/--model-a-raw/--model-b-json/--model-b-raw` 指向板卡上的既有路径。
- 一键脚本 `board_scripts/run_m27_1_board_probes.sh` 在运行前先 `sha256sum -c` 校验 A/B 四个文件的冻结 SHA（§1/§2），**任何不匹配立即退出**（fail-closed，保护生产模型不被探针误用）。

## 5. 备选模型 B（若用户指定）

若用户提供另一个**真实编译的小测试模型**（如 iCraft demo 编译产物、或用户自训练的小网络），以 `--model-b-*` 参数覆盖，同样必须通过 `sha256sum` 冻结校验。**禁止**：用一个"假 logits 常量返回"的 stub 冒充模型 B。
