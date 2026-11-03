# M29 Phase D — 12类环境对照实验结论（2026-10-10）

状态：`M29-PHASE-D-QUANTIZE-BLOCKED-ROOTCAUSE-ISOLATION`（判定 **B**：环境健康，24类自身问题；未碰板/未写 Flash/未访问 test）

本文件按用户指令（暂停24类、用当前完全一致环境重跑历史成功12类、只跑一次）记录对照实验与判定。

---

## 1. 12类对照实验（本次，全新输出目录，不覆盖历史）

**运行前**：无残留 icraft 进程；默认 PATH 含 `/c/Icraft/CLI/bin`（软链接）；主入口 `C:/Icraft/CLI v3.39.0/bin/icraft.exe`（Aug 21, 303616 B）存在；历史输入 `model_12class_optimized.json`(100202 B)/`.raw`(1111396 B) Oct 6 08:22 完好。

**主命令（与历史成功 run_compile.sh 完全一致，无 PATH 修改、无 export、无 junction/拷贝）**：
```
cd <全新输出目录 _tmp_12class_quantize_retest_20261010>
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" quantize compile_config.toml
```
配置：复用历史 `compile_config.toml`，仅把输出目录（jsonraw/logs）重定向到全新目录；输入 `optimized.json/raw` 与校准 `forward_dir/forward_list` 保持指向原始只读。历史产物时间戳仍 Oct 6，未覆盖。

**运行结果**：
| 项 | 值 |
|---|---|
| 真实退出码 | **0** |
| 耗时 | **285 s** |
| 峰值内存（PeakWorkingSet64） | **1853804544 B ≈ 1.73 GB** |
| Before ReLU | **出现**（18:25:47.285） |
| Batch 0 Begin | **出现**（18:26:06.997，+19 s，与历史 +18 s 吻合） |
| Batch 0 End | 18:29:51.521（252 样本前向 3m45s） |
| Measure End | **出现**（18:30:17.332） |
| poly_params 打开失败 | **0 次（未复现）** |
| 量化产物 | `model_12class_quantized.json` 398648 B / `.raw` 282916 B（与历史字节一致） |

## 2. 判定 = **B**（12类成功、24类失败 → 环境健康）

12类在**当前环境**完整跑通量化（Before ReLU → Batch 0 Begin → Measure End，exit 0），`poly_params.json` 打开失败**未复现**。故 iCraft 安装/环境/资源定位**无回归**，24类不因环境背锅。

## 3. 12 vs 24 全维度对比

| 维度 | 12类（成功） | 24类（失败） | 结论 |
|---|---|---|---|
| 主命令 | `C:/Icraft/CLI v3.39.0/bin/icraft.exe quantize` | 原装同命令首跑失败；后改 D:\icraft 拷贝 3 次仍失败 | 命令等价，非主因 |
| 子工具解析 | PATH 软链接 `C:\Icraft\CLI\bin\icraft-quantize.exe` | 同软链接 / D:\icraft 直接 | 等价 |
| poly_params 路径 | `C:\Icraft\CLI\bin\poly_params.json`（成功打开） | 同路径失败 + `D:\icraft\bin\poly_params.json` 失败 | 同文件不同结果→进程态差异 |
| 工作目录 | `model_12class/compile/` | `work/compile/` | 同树结构 |
| ONNX | [1,2,1024]→12 | [1,2,1024]→24 | 输出维不同 |
| 量化参数 | int8/kld/channel/no_transinput/no_imagemake | **完全一致** | 非主因 |
| optimized 模型 | json 100202 / raw 1111396 | json 100202 / raw 1117588 | 大小近同 |
| **校准集规模** | **252 样本，单批 252** | **624 样本，单批 624** | **唯一实质差异** |
| .bin 格式 | 8192 B，iq_N.bin | 8192 B，iq_N.bin（624 个全存在） | 格式一致 |
| Before ReLU → Batch0 | 19 s | 卡在 Before ReLU 后 ~170 s 失败（无 Batch 0 Begin） | 24类慢 9× 且失败 |

## 4. 失败点定位

24类日志停在 `Before ReLU: 0`（18:01:02）之后，**无 Batch 0 Begin**。失败栈 `CalibrateByForward → Session::Create<HostBackend> → HostBackendNode::init → safeLoadFile(poly_params.json)`。即失败发生在 **HostBackend（libtorch CPU 校准前向引擎）初始化阶段**，是校准前向的验证专用路径，NPU adapt/generate 用的是另一后端。

## 5. 已排除项

- 空格路径（12类带空格版本路径成功；D:\icraft 无空格拷贝仍失败）
- reparse point（junction/symlink/实拷贝全测过）
- 文件可读性（CreateFileA/W 全 SUCCESS；SHA 一致；valid JSON；无 ADS）
- 32位地址空间 OOM（icraft 全 64-bit）
- 物理内存不足（主机 31.66 GB；12类峰值仅 1.73 GB）
- 量化参数差异（逐参数 diff 完全一致）
- forward_list 损坏（624 行全非空、全对应存在、格式同 12类）

## 6. 最强根因假设

**24类校准单批 624 样本导致 HostBackend 初始化资源耗尽（FILE* / 句柄 EMFILE）**，使后续 `fopen(poly_params.json)` 返回 NULL。佐证：24类在 `Before ReLU`→失败窗口 ~170 s，是 12类（19 s）的 **9 倍**，说明 24类在该窗口做了远超 12类的初始化工作（624 vs 252 样本）；fopen 对一个存在/可读/绝对路径/64位进程返回 NULL，最典型是 EMFILE（CRT 默认 512 fd）。

## 7. 建议的判别性下一步（待用户批准，本轮未执行）

**方案1（推荐）**：仅把 24类校准集从 624 降到 252 样本（与 12类对齐，**不动模型/标签/预处理**，仍从 train split 取），重跑一次 quantize。若 poly_params 通过 → 证实"校准批量 624 资源耗尽"，再据此把 24类校准拆成多批或降采样后完成 quantize→adapt→generate。若仍失败 → 触发点是 24 维模型本身，需另查模型侧。

**方案2**：管理员权限跑 ProcMon，抓 24类失败瞬间对 `poly_params.json` 的 CreateFile Result/Desired Access，确认 EMFILE（errno 24）还是其它。

**方案3**：官方安装程序重装到 `C:\icraft39`（用户消息1 #8）——**已无必要**：12类已证明带空格原装路径可正常打开 poly_params，重装不解决 24类自身问题。

## 8. 红线保持

未修改 24类/12类网络结构、标签序、预处理；未重训练；未用 test 数据校准；未用最终测试指标选量化参数；未碰板/未写 Flash；未写任何 FINAL_*/NPU_PASS/24CLASS_PASS/PROJECT_COMPLETE。本轮只做了 1 次 12类对照 + 只读对比，无连续重复运行。
