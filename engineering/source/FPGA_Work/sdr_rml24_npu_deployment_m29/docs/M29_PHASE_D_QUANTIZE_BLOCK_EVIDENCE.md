# M29 Phase D — iCraft Quantize 阻塞证据记录（2026-10-10）

状态：`M29-PHASE-D-QUANTIZE-BLOCKED-ROOTCAUSE-ISOLATION`（尚未完成 quantize，未碰板/未写 Flash/未访问 test）

本文件冻结 Phase D（iCraft `quantize`）失败的全量证据，用于隔离"工具/环境问题"与"24 类模型/转换配置问题"。

---

## 1. 现象（唯一失败点）

`icraft quantize` 在 `HostBackendNode::init → safeLoadFile(poly_params.json)` 处抛
`Check failed: (file_stream.is_open()) is false / Open file <path> failed!`，退出码 **1**。

完整栈（来自 stdout）：
```
CalibratePass.cpp:1522/744 CalibrateByForward
  → session.h:86 Session::Create<HostBackend>
  → backend.cpp:143 HostBackendNode::init
  → file.cpp:32 safeLoadFile
  → file.cpp:17 safeLoadFile        ← is_open()==false
```

## 2. 三次运行，三种解析路径，全部失败（退出码均为 1）

| 运行 | 主入口 | 解析到的 poly_params 路径 | 结果 |
|---|---|---|---|
| ① `D:/icraft/bin/icraft.exe quantize` | icraft.exe | `C:\Icraft\CLI\bin\poly_params.json`（软链接） | FAIL |
| ② 同上 + `export PATH="D:/icraft/bin:$PATH"` | icraft.exe | `C:\Icraft\CLI\bin\poly_params.json`（软链接，PATH 前置未改变子工具解析） | FAIL |
| ③ `D:/icraft/bin/icraft-quantize.exe --bits 8 ...`（直接） | icraft-quantize.exe | `D:\icraft\bin\poly_params.json`（**无空格实拷贝**） | FAIL |

**结论：与路径空格/reparse point 无关。** 无空格、无 reparse 的实拷贝 `D:\icraft\bin` 同样失败。

## 3. poly_params.json 七点核查（原安装 + 复制目录，结果一致）

| # | 检查项 | 结果 |
|---|---|---|
| 1 | 文件存在（77533 字节） | PASS |
| 2 | 普通用户可读（`BUILTIN\Users Allow ReadAndExecute`） | PASS |
| 3 | JSON 可解析（Python json.load） | PASS |
| 6 | 原安装与复制目录 SHA256 一致（`B3BC133C…`） | PASS |
| 7 | 无 reparse/readonly/encrypted/compressed/offline/sparse/Zone.Identifier ADS | PASS |

## 4. WinAPI 层打开验证（ProcMon 等价证据，无需内核驱动）

`CreateFileA` / `CreateFileW`（share=READ / READ\|WRITE / NONE）对 `D:\icraft\bin\poly_params.json`
与 `C:\Icraft\CLI v3.39.0\bin\poly_params.json` **全部 SUCCESS**，无 `ACCESS_DENIED` / `FILE_NOT_FOUND` /
`SHARING_VIOLATION`。

**含义：文件在 CreateFile 层可正常打开，失败发生在 icraft 进程内部（libtorch 加载之后）的 `fopen`/`ifstream`。**

## 5. 关键对照：12 类 quantize 曾在本机成功

`F:\FPGA_Work\sdr_full_chain_12class_v1\model_12class\compile\.icraft\logs\model_12class\model_12class_quantize.log`
时间戳 `2026-10-06 08:22→08:26`：
```
08:22:52.907 Measure Begin
08:22:52.907 Before ReLU: 0
08:23:11.197 Batch 0 Begin     (+18s，poly_params 打开成功)
08:26:55.754 Measure End
```
12 类当时用的是**带空格**版本路径 `C:/Icraft/CLI v3.39.0/bin/icraft.exe`，无 PATH 修复，成功。
→ 4 天后（今）同一套工具对 24 类失败，且对无空格实拷贝也失败。

## 6. 当前最强嫌疑（待证）

文件在 CreateFile 层可开、但进程内 `ifstream` 失败 → 嫌疑集中在**进程状态**：
- **FILE* / 文件句柄耗尽（EMFILE, errno 24）**：`torch_cpu_ic.dll`（120MB libtorch）加载期间可能
  打开大量文件，导致后续 `fopen(poly_params.json)` 返回 NULL。
- 12 类 "Before ReLU→Batch 0 Begin" 仅 18s；24 类（junction 路径那次）约 268s 才失败——libtorch
  加载耗时差异显著，需进一步取证。

## 7. 完整 stdout/stderr（原始文件，未截断）

- `work/compile/quantize_stdout.log`（运行① 输出，含软链接路径失败栈）
- `work/compile/quantize_stdout2.log`（运行② 输出）
- `work/compile/quantize_direct.log`（运行③ 输出，含 `D:\icraft\bin\poly_params.json` 失败栈）
- `work/compile/.icraft/logs/model_24class/model_24class_quantize.log`（iCraft 进度日志）

真实退出码：三行 `[fatal] 1`，进程退出码 1。

## 8. 未做 / 阻塞项

- **ProcMon**：已下载 `work/tools/procmon/Procmon64.exe`，但**内核驱动加载需管理员**（本会话
  `IsAdmin=False`），无法抓取 CreateFile 的 Result/Desired Access。已用第 4 节 CreateFileA/W 直测
  作为等价证据（结论：文件可开，失败在进程内）。
- **官方示例模型**：安装目录内**未随包附带 .onnx 示例模型**（`docs/demo/samples` 等均为 HTML 文档，
  无模型文件；`bin/{zhuge,wolong,buyi}` 仅 `adapter.toml`/`optimizer.toml`）。
- **未修改** 24 类网络结构、标签序、预处理、模型参数。
