# M27.1 交付报告（Delivery Report）

任务 id="39e5" · M27.1 — FMQL30TAI/ZG330 NPU 多模型能力核验 · **离线交付，未碰板、未出位流、未跑真实探针。**

---

## 1. 状态

```
M27_1-MULTI-MODEL-PROBE-READY
```

本交付把 M27.1 推进到"**探针就绪**"：SDK 审计完成、5 个板端探针源码+构建脚本就绪、一键板测脚本就绪、结果模板就绪、主机单元测试 36/36 通过。**A/B/C/D 结论尚未声明**——只有完成真实板端探针后才能声明（任务 §六）。

## 2. 七项交付物对照（任务 §七）

| # | 交付物 | 位置 | 状态 |
|---|---|---|---|
| 1 | SDK 审计报告 | `docs/M27_1_SDK_MULTI_MODEL_AUDIT.md` | ✅ |
| 2 | 探针源码和构建脚本 | `probes/*.cpp` + `probes/CMakeLists.txt` + `probes/build_on_board.sh` | ✅ |
| 3 | 板端一键测试脚本 | `board_scripts/run_m27_1_board_probes.sh` | ✅ |
| 4 | 结果 JSON 模板 | `results/M27_1_RESULT_TEMPLATE.json` | ✅ |
| 5 | 主机单元测试 | `host_tests/test_m27_1_metrics.cpp` + 4 脚本 | ✅（36/0 三套） |
| 6 | 精确 diff 清单 | `M27_1_DIFF_LIST.txt` | ✅ |
| 7 | 版本化补丁包及 SHA256 | `dist/m27_1_multimodel_probe_patch.tar.gz` + `M27_1_PATCH_SHA256SUMS.txt` | ✅ |

## 3. SDK 审计核心结论（详见审计报告）

- iCraft 3.39 XRT **对象模型允许多实例**：多 `Device::Open`、多 `Network`、多 `Session`、多 `ZG330Backend`（`zg330backend_sid` 实例计数）。
- **官方多网络部署机制存在**：`userReuseSegment`（不同网络只能复用 FTMP 段）+ `userConnectNetwork`（多网络 PL DDR I/O 连接）。
- **无** `Job`/异步提交/并发执行 API；**无**独立 `unload/release`（切换＝`Backend::deinit`+重建）。
- 结论修正：M27 审计的 `MULTI_MODEL_RESIDENCY_UNSUPPORTED` 判过强，更正为 `MULTI_MODEL_RESIDENCY=UNVERIFIED`（容量依赖，待板测）。

## 4. 主机单元测试结果（离线已跑）

| 套件 | 结果 |
|---|---|
| release（`-O2 -Wall -Wextra -Werror`，WSL g++ 15.2.0） | `assertions=36 passed=36 failed=0` |
| ASan（address） | `assertions=36 passed=36 failed=0` |
| UBSan（undefined） | `assertions=36 passed=36 failed=0` |

覆盖：LatencyStats(mean/max/p99/count)、argmax、all_finite、Json 字符串转义、Json 精确输出、`ProbeResult.to_json` 全字段+合法 JSON、`M27_1_RESULT_TEMPLATE.json` 合法 JSON。

## 5. 板端探针（待上板，未跑）

| 探针 | 作用 | 预期尾标 |
|---|---|---|
| `probe_single_model` | 基线（单模型 1000 帧） | PASS/FAIL |
| `probe_two_networks` | A+B 同 Device 驻留 + 交替 forward | PASS/FAIL |
| `probe_sequential_inference` | A→B→A 串行（无逐帧 Open） | PASS/FAIL |
| `probe_concurrent_inference` | SDK 门禁（无异步 API → 预期 SKIP） | SKIP |
| `probe_unload_reload` | 卸载 B 后 A 仍工作 + 重载 B | PASS/FAIL |

模型：A=12 类冻结（raw `2ae95275…`），B=8 类板证模型（raw `c48979b3…`），均为真实编译产物，**非 stub**。

## 6. 安全边界执行情况

✅ 未写 Flash；✅ 未改 RTL/XDC/位流；✅ 未覆盖历史模型（只读引用 A/B，SHA 冻结校验）；✅ 未接 Gate 9/10 生产链（独立进程）；✅ 探针无逐帧串口打印；✅ 探针一次 Open 一次 Close（无 263ms 重开）；✅ 并发探针因 API 不允许而 SKIP；✅ 全程 fail-closed。

## 7. 状态红线

- 已写：`CURRENT_PROJECT_VERIFIED_MODE=SINGLE_MODEL_RESIDENT` + 三个 `UNVERIFIED`。
- 禁止（本阶段不得出现）：`MULTI_MODEL_RESIDENT_SUPPORTED / MULTI_MODEL_CONCURRENT_SUPPORTED / MULTI_MODEL_SWITCH_ONLY / SINGLE_MODEL_ONLY_CONFIRMED`（A/B/C/D 结论）——**均未声明**。
- 最高离线状态：`M27_1-MULTI-MODEL-PROBE-READY`。
