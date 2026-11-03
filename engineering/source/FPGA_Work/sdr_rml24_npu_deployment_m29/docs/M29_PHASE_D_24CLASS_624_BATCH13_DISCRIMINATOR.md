# M29 Phase D — 24类 624 校准 batch=13 拆批判别测试（2026-10-10）

状态：`M29-PHASE-D-QUANTIZE-BLOCKED-ROOTCAUSE-ISOLATION`（判定 **C**：252 成功、624 拆批仍失败 → 触发点是 624 校准集自身（计数/加载边界），非批量组织；未碰板/未写 Flash/未访问 test）

按用户批准：保持 624 样本不变、模型/ONNX/量化参数不变、唯一语义变更 `[quantize] batch: 1→13`、全新输出目录、只跑一次。

---

## 1. 运行前基线（SHA，证明未改模型/未改校准）

| 项 | SHA256 |
|---|---|
| 624 校准 .bin 合并（forward_list 顺序，去 CRLF） | `d86a11449a08769b008474c9b93816a6699560b2d7b088acb6b6e98bda8d988d` |
| forward_list.txt | `cb38169cebc73fd93066c2ff417273958ad42cf24890a9df291b0ad8700dea1b` |
| 输入 model_24class_optimized.json / .raw | `8e3d06ba…` / `7cb9c32f…`（未动） |
| ONNX rml24_24class_opset17.onnx | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51`（未动） |

## 2. 运行结果

| 项 | 值 |
|---|---|
| 真实退出码 | **1（失败）** |
| 耗时 / 峰值内存 | 429 s / 1620197376 B ≈ **1.51 GB**（未 OOM，主机 31.66 GB） |
| config 读取 | `Calibration Set Size: 624` `Batch Number: 13` `Batch Size: 48` ✅（batch=13 生效） |
| Before ReLU | ✅ 19:44:01.071 |
| **Batch 0 Begin** | ❌ **未出现** |
| 失败 | `Check failed: (file_stream.is_open()) is false / Open file C:\Icraft\CLI\bin\poly_params.json failed!`（与 batch=1 完全相同） |

## 3. 三份日志对照（唯一变量 = 校准集规模）

| 运行 | Set Size | Batch | Batch Size | Before ReLU | Batch 0 Begin | Measure End |
|---|---|---|---|---|---|---|
| 12类 252 | 252 | 1 | 252 | ✅ | ✅ | ✅ |
| 24类 252 | 252 | 1 | 252 | ✅ | ✅ | ✅ |
| **24类 624** | **624** | 13 | 48 | ✅ | ❌ | ❌ |

`batch=13` 被正确读入但**无济于事** → `batch` 只拆分"前向计算"，**不拆分 Batch 0 Begin 之前的校准加载/初始化阶段**。该阶段在 624 时触发失败。

## 4. 判定 = C（252 成功、624 拆批仍失败）

按用户判定规则 C：24类 252 成功、但 624 拆成小批次（13×48）仍失败 → 不是批量组织问题，是 624 校准集自身。已按要求检查：

| 检查项 | 结果 |
|---|---|
| 特定校准样本 | 624 个 .bin 全存在、全 8192 B、无坏文件 |
| 数据内容 / 非有限值 | **NaN=0、Inf=0**（624 全量扫描） |
| 异常幅度 | 624 峰值 abs 21.7，**低于** 252 的 41.4（幅度非异常） |
| 加载器边界 | forward_list 624 行 CRLF、ASCII、格式与 252 一致；poly_params.json 存在可读（77533 B） |

数据本身干净，**触发点是"624 这个规模"本身**，不是某个坏样本。

## 5. 根因表述（遵守规则 #7，EMFILE 未确认）

**资源/进程态假设**：24 类量化的校准加载/初始化阶段（`Before ReLU` 之后、`Batch 0 Begin` 之前）会一次性打开并持有全部 N 个校准 .bin 文件的流；N=624 时逼近/超过进程 stdio 流上限（MSVC CRT 默认 `_IOB_ENTRIES`/`FOPEN_MAX`=512），使随后 `HostBackendNode::init` 打开 `poly_params.json` 时 `fopen` 返回 NULL。`batch` 只作用于初始化**之后**的前向，故拆批无效。

佐证：624 失败窗口 ~170s（batch=1）/ 429s 总长（batch=13，含轮询），是 24类 252（45s）的 ~4–9 倍，与该阶段多读 372 个文件一致；峰值内存仅 1.51GB 排除 OOM。**无 errno/ProcMon 证据，EMFILE 未确认，仅为假设。**

## 6. 下一步（待用户批准，本轮已按规则 #8 停止，未自动重试 batch=26）

- **方案 A（推荐，确证根因）**：管理员权限 ProcMon，抓 624 运行在 `poly_params.json` 上 CreateFile 的 Result/errno，确认是否 EMFILE/句柄耗尽。
- **方案 B（诊断，需批准+多次运行）**：阈值二分——用 624 的**前 N** 个样本（如 400/500/512）跑，定位临界点是否 ~512（佐证句柄假设）。仅诊断，不作为最终校准。
- **方案 C（若确认为句柄上限）**：探查可绕开"一次性打开 624 流"的官方/工具侧手段；否则需与 iCraft 官方确认 stdio 上限或更高 `_setmaxstdio` 版本。

## 7. 红线保持

624 未作最终结论（量化产物未生成）；252 产物仅诊断；未改模型/标签/预处理/量化参数；未用 test 校准；未碰板/未写 Flash；未写任何 FINAL_*/NPU_PASS/24CLASS_PASS/PROJECT_COMPLETE；本轮仅 1 次 batch=13 判别运行，无连续重复。
