# M29 Phase F4 — RML23-AMSSB-MERGED 板端软件接入与候选包

> 状态：`M29-RML23-MERGED-BOARD-PACKAGE-READY-FOR-TEST`（最高允许，待用户真实上板）
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁自动启动 QAT / 不训练专家模型 /
>       不覆盖 M22/M23/M24 / 禁写 FINAL_*/NPU_PASS / 板端包禁含 Windows/x86/WSL 二进制。

---

## 0. 结论

23 类 AM-SSB 合并板端候选包已生成并通过全部离线校验：

- **包路径**：`dist/sdr_rml23_amssb_merged_board_package.tar.gz`
- **大小**：505575 字节（约 494 KiB）
- **SHA256**：`33e051e93e2468c973eefaf1e7da96882f42f11022316ad89b38629b67212be5`
- **板端二进制架构**：包内**不含任何二进制**（源码构建），故无 Windows/x86/WSL 二进制风险。
- **位流**：沿用现有 bitstream（软件 + 模型层变更，不重新生成位流）。

---

## 1. 板端链路

```
NPU 24维输出 (raw logits, 不变)
  → 保存原始24维输出 (供未来 SC/WC 专家)
  → AM-SSB logaddexp 合并: merged[17] = log(exp(logit_SC) + exp(logit_WC))
  → 23类 argmax
  → UI 显示 / 结果协议
```

- NPU 模型仍只加载一次（沿用现有驱动，不逐帧 reopen）。
- 不修改 NPU 输入预处理、不改变原 24 维输出索引、后处理不引入明显帧延迟。
- UI 显示 `model mode = RML23-AMSSB-MERGED`，类别只显示 `AM-SSB`。
- 结果日志记录 `raw_24_top1`、`merged_23_top1`、`deployment_mode`。
- 专家接口预留禁用态：`expert_enabled=false`、`expert_result=NOT_RUN`，无假专家、无规则式 SC/WC 拆分。

---

## 2. 新目录隔离（不覆盖历史）

集成全部落在新目录 `board_rml23/`，与 12 类 / 24 类历史产物、M22/M23/M24 交付物零接触。若现有板端包使用 12 类固定结构，本包为**独立协议版本**（23 类标签表新增，非覆盖 12 类标签表）。

---

## 3. 板端包内容

| 需求 | 交付物 |
|---|---|
| NPU json/raw 候选 | `model/model_24class_ZG.json` / `.raw`（expA_bf16_head） |
| 23 类标签与映射契约 | `contract/rml23_merged_contract.py` / `.json` |
| 板端可执行文件 | `rml23_merged.hpp` + `src/rml23_merged_main.cpp`（源码，`scripts/build_board.sh` 板端构建） |
| 动态库依赖说明 | `README.md`「Board runtime dependencies」 |
| 一键启动脚本 | `scripts/start_rml23.sh` |
| 一键停止脚本 | `scripts/stop_rml23.sh` |
| 模型与 manifest 校验脚本 | `scripts/verify_package.sh` + `scripts/verify_rml23_contract.py` |
| 1000 帧测试脚本 | `scripts/test_1000_frames.sh` |
| 10000 帧稳定性测试脚本 | `scripts/test_10000_frames.sh` |
| UI/结果检查脚本 | `scripts/check_ui_result.sh` |
| SHA256 清单 | `SHA256SUMS.txt`（19 个内容文件，不含自身） |
| 上传/解包/校验/运行说明 | `README.md` |
| 回滚方法 | `scripts/rollback.sh`（恢复 `model.prev/`，不碰 Flash/位流） |

---

## 4. 离线校验结果

| 校验项 | 结果 |
|---|---|
| C++ 主机自测（WSL g++ 15.2.0） | 40/40 断言通过 |
| 跨语言 C++↔Python（1536 帧） | merged top-1 不一致 0 / raw top-1 不一致 0 / 最大 logit 绝对差 9.537e-7 |
| 1000 帧稳定性 | 0 invalid |
| 10000 帧稳定性 | 0 invalid |
| 集成示例 `rml23_merged_main` | frame 3: raw_24_top1=11(128APSK) → merged_23_top1=17(AM-SSB) |
| 包内 `sha256sum -c SHA256SUMS.txt` | 19/19 OK |
| `verify_package.sh`（manifest + 模型 + 契约） | PASS |
| 契约 SHA 重算 | label_order_23=`15072cd2…` / merged_contract=`f9f7f381…` |
| 板端二进制架构扫描 | 无 ELF/PE32/Mach-O/x86-64（0 二进制） |
| `bash -n` 全部脚本 | 8/8 通过 |
| Python `compileall` | 通过 |
| pytest（32 项契约测试） | 32 passed |

---

## 5. 上传 / 校验 / 启动 / 停止 / 回滚（摘要）

```sh
mkdir -p /opt/sdr/rml23 && tar -xzf sdr_rml23_amssb_merged_board_package.tar.gz -C /opt/sdr/rml23
cd /opt/sdr/rml23
./scripts/verify_package.sh                 # fail-closed 校验
./scripts/build_board.sh                    # 板端 aarch64 从源码构建 + 自测
./scripts/test_1000_frames.sh  /data/npu_logits_1000.f32
./scripts/test_10000_frames.sh /data/npu_logits_10000.f32
./scripts/start_rml23.sh /data/npu_logits.f32 N result/rml23_result.jsonl
./scripts/stop_rml23.sh
./scripts/rollback.sh                       # 回滚至上一 model.prev/（不碰 Flash）
```

详细步骤与运行态依赖见包内 `README.md`。
