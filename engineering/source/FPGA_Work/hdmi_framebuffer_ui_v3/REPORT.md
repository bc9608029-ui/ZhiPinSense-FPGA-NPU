# HDMI 仪器化 UI 重构 · 最终报告（v3）

> 生成时间：2026-10-04
> **状态：`READY-FOR-HARDWARE-TEST`（宿主机全部测试已真实执行并通过，未上板）。**
> 本文只陈述**真实执行过的验证**与**仍需上板的检查**，不把任何未实机验证的项目写成 `PASS`/`READY`/"显示成功"。

---

## 1. 一句话结论

将 HDMI 识别 UI 从「写死 10 类、直写设备内存、易触发 SIGBUS」重构为「运行时 8–16 类契约 + 常规内存 staging 缓冲 + 唯一标量提交函数」的仪器化三页 UI。**后端与 UI 全部在宿主机（WSL Ubuntu / g++ 15.2.0）上以 `-Wall -Wextra -O2` 零警告编译，并通过 162+ 条单元测试与 ASan/UBSan**；位流复用已验证的 v2 双缓冲位流，**不改时序**。上板验证由你本人按阶段执行。

---

## 2. SIGBUS 真实根因与证据

### 2.1 根因

上板时对 u-dma-buf 设备映射（`mmap /dev/udmabuf0` 得到的 RGB565 显存）做**整帧 RGB565 拷贝**曾触发 `SIGBUS`（总线错误）。根因是：

- 编译器在 `-O2` 下把 `uint16_t` 拷贝循环**自动向量化**成 **NEON/SIMD 宽访存**（aarch64 上为 `st1`/`st2`/`str q` 一类 64/128 位宽 store）；
- 而 u-dma-buf 的物理连续 DMA 映射**只接受与页面/设备事务宽度匹配的标量访问**，宽 SIMD 事务不被该映射支持 → 触发 `SIGBUS`。

直接向设备映射写普通 `std::vector`/逐像素赋值即可能中招，因为写入路径完全由编译器决定。

### 2.2 证据

1. **机制证据（本报告生成的 objdump）**：`scalar_copy16()` 的 `dst` 声明为 `volatile std::uint16_t*`。C/C++ 抽象机规定每个 `volatile` 存储必须**逐次、按序、以声明宽度（16 位）各发出一次**，编译器**不得**把 volatile 存储合并/加宽。宿主机 `-O2` 反汇编确认其内层循环只发出标量 16 位 store（`mov WORD PTR [rdi-0x2], ax`），无任何 SIMD 宽 store：

   ```
   3e0: 0f b7 06             movzx  eax, WORD PTR [rsi]
   3eb: 66 89 47 fe          mov    WORD PTR [rdi-0x2], ax
   ```

   这一语义是**架构无关**的语言保证，在 aarch64（板端）上同样约束编译器不得用 NEON 宽 store 写 volatile 目标。

2. **架构证据**：v3 采用「staging 缓冲 + 唯一提交点」。UI 只在常规 RAM（`ui::Canvas` 内部 `std::vector<uint16_t>`）里画，**唯一**触碰设备显存的地方是 `dfb::scalar_copy16()`（`direct_framebuffer_backend.cpp` 中的单一 choke point），其余代码再也接触不到 `mmap` 出的设备指针。任何未来的渲染改动都不会重新引入设备内存直写。

3. **加固**：`scalar_copy16()` 额外打 `__attribute__((noinline, optimize("no-tree-vectorize")))`（`#if defined(__GNUC__) && !defined(__clang__)` 保护），作为对 GCC 自动向量器的 belt-and-suspenders 请求；真正的保证来自上面的 `volatile` 指针。

> 板端决定性复核（仍在待办，见 §5）：把 aarch64 的 `phase2_ui_render` 反汇编，确认 `scalar_copy16` 无 NEON `st1/st2/str q`；上板跑满无 SIGBUS、无撕裂。

---

## 3. 如何保证提交不再产生 SIMD 宽写

| 层级 | 措施 | 作用 |
|---|---|---|
| 语言 | `scalar_copy16` 形参 `volatile std::uint16_t* dst` | 编译器**必须**逐元素发标量 16 位 store，禁止加宽/合并 |
| 编译器 | `noinline` + `optimize("no-tree-vectorize")` | 额外关闭 GCC 自动向量器 |
| 架构 | staging 缓冲（常规 RAM）+ 单一 choke point | 除 `scalar_copy16` 外，任何代码不写设备显存 |
| 运行时 | `submit()` 校验指针/帧号，越界拒绝；版本门通过后才写寄存器 | 出错即 FAIL、非零退出，不静默 |

已由宿主机 `-O2` 反汇编**实证**（§2.2 第 1 条）确认标量 store。

---

## 4. Host 真实执行的测试（含真实结果）

以下全部在 **WSL Ubuntu / g++ 15.2.0** 上真实编译并运行，非推测：

| 测试 | 命令 | 真实结果 |
|---|---|---|
| 后端单元测试 | `g++ -std=gnu++17 -Wall -Wextra -O2 test_direct_framebuffer_backend.cpp direct_framebuffer_backend.cpp` → 运行 | **零警告编译；`ALL TESTS PASSED (0 failures)`**，覆盖 parse_u64 / check_framebuffer / check_double_buffer / 版本门 / 读回门 / msync 分类 / submit 金丝雀（canary）+ 帧偏移 + 空指针/越界/未 init 拒绝 |
| UI 单元测试 | `g++ ... test_ui.cpp font.cpp ui_renderer.cpp model_contract.cpp touch.cpp` → 运行 | **零警告编译；`RESULT pass=162 fail=0`**，覆盖字体覆盖/有效性、canvas 裁剪/RGB565、softmax/归一化/argmax/top_k/置信度带、契约校验（7 类拒绝、17 类拒绝、8/16 类接受、glyph 不安全类名拒绝）、NaN/Inf 安全、触摸映射与协议 A/B 解码、tab 命中、三页绘制确定性 |
| ASan + UBSan | 两测试各用 `-fsanitize=address,undefined` 重编重跑 | **零报告**（无内存越界/未定义行为/泄漏） |
| 截图生成 | `render_screenshots screenshots` | 7 场景 + 字体样张 → 1280×720 与 1024×600 BMP + `hashes.txt`，每次重跑哈希一致（确定性渲染） |

完整一键复现：`sw/build_host_tests.sh`（已真实跑通，输出 `ALL HOST TESTS PASSED`）。

> 补充（如实）：`CMakeLists.txt` 的**每个目标**均已用与 cmake 一致的源文件清单**直接 g++ 编译通过**（后端单测、UI 单测、截图、以及板端 `phase2_ui_render`/`phase3_touch_test` 的 x86 编译）。本 WSL 主机未装 cmake（板端有），故未在此跑 `cmake --build`；cmake 路径由板端 `build_on_board.sh` 首次执行时验证。

截图像素哈希（FNV-1a 64-bit，见 `sw/screenshots/hashes.txt`）：

| 场景 | 1280×720 哈希 |
|---|---|
| normal | `91f3990b1c52e69d` |
| low_confidence | `120a4f9c60e370c2` |
| stale | `c65b596ab30532b3` |
| error | `59c25ac119ee39e2` |
| no_signal | `f15216109b61cdff` |
| all_classes | `2741af17538b390d` |
| diagnostics | `454984dd281efb55` |
| font_specimen | `e3815bedf8ee26ed` |

---

## 5. 仍需上板验证的检查（我无法替你做）

以下**一律不能**在宿主机证明，只能由你实机确认，状态保持 `READY-FOR-HARDWARE-TEST`：

1. **无 SIGBUS**：板上跑 `phase2_ui_render` 整帧提交无 `SIGBUS`。
2. **aarch64 无 NEON 宽 store**：板上 `objdump -d phase2_ui_render | grep -A20 scalar_copy16` 确认无 `st1/st2/str q`（宿主机已证 x86 标量，板端为最终确认）。
3. **显示正确**：标题/三页/Top-5/All Classes/Diagnostics 文字清晰、置信度 sum=100%、Top-1 由 argmax 推出且各页一致。
4. **无撕裂**：双缓冲翻页（写 `0x40080050`=后缓冲号）无水平错位/撕裂。
5. **触摸**：`TOUCH_FOUND` + 标定公式 + 至少一次点击走通「点击→坐标→命中区域→翻页」打印 `PHASE3_TOUCH_PASS`；找不到触摸则 `PHASE3_TOUCH_FAIL` 非零退出（不假 PASS）。
6. **寄存器门**：`0x4008000C == 0x20230218` 版本门、`0x40080054 == phys>>3`、`0x40080050` 写读回一致。

上板步骤见 `docs/MASTER_MANUAL.md`（我禁碰板、不写 Flash、只用临时 JTAG `*_disable_icap.bit`）。

---

## 6. 状态声明规则（遵守）

- 实机验证前，所有阶段状态**只写 `READY-FOR-HARDWARE-TEST`**，不写 `PASS`/`READY`/"显示成功"。
- 本文所有「已通过」仅指**宿主机编译/单测/静态检查**，不是上板结论。
- 板测仍用现有 **10 类模型契约**（`model::contract_v1_1()`）；**12 类 DEMO（`contract_target_12()`）只是预留，绝不冒充真实模型输出**。

---

## 7. 类别契约：运行时 8–16 类，不写死 10 类

按你的中途纠正，UI 渲染器**不在 UI 代码里写死类别**：

- `model_contract.hpp` 是类别顺序的**唯一事实源**：`class_names`（`std::vector<std::string>`）、`probabilities`、`class_count` 由运行时契约传入渲染器。
- 渲染器要求 `class_count ∈ [8, 16]`，否则绘制 `INVALID CONTRACT`（`validate_state`）。
- `contract_v1_1()` = 10 类（AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM）——**当前板测用这个**。
- `contract_target_12()` = 12 类（OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK/GMSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM）——**预留，不冒充真实输出**。
- Overview 显示 **Top-5**；All Classes 页按 `class_count` **动态排布**（`%02d` 序号、`>` 标 Top-1、类名、置信度条、百分比）。

---

## 8. phase1b / phase1c 排除说明

- v3 交付范围 = **后端 + UI + Phase2 + Phase3**。
- `phase1b_doublebuf_test.cpp` / `phase1c_dynamic_test.cpp` 是 v2 已上板验证的资产，**不属于 v3 交付物**，故：**保留原文件**、**不参与 v3 构建**（`CMakeLists.txt` 与 `build_on_board.sh` 均已移除），并在 `SHA256SUMS.txt` 中单列「v2 保留未构建」。
- 位流仍复用 v2 双缓冲位流（`_disable_icap.bit`，SHA-256 `686bb1e3…`），时序/TMDS/时钟链/PS7-DDR3 **冻结不动**。

---

## 9. 修改文件清单

### 9.1 新增（v3 核心）

| 文件 | 作用 |
|---|---|
| `sw/direct_framebuffer_backend.hpp/.cpp` | 安全直连后端：sysfs 取 phys/size、版本门、读回门、`submit()` + `scalar_copy16()`（唯一设备写点） |
| `sw/font.hpp/.cpp` | 8×8 位图字体（switch 显式查表，避免 off-by-one），整数缩放 24/32/48/64 |
| `sw/model_contract.hpp/.cpp` | 类别契约唯一事实源；`contract_v1_1()`(10) / `contract_target_12()`(12 预留)；8–16 校验 |
| `sw/canvas.hpp` | 常规 RAM 绘制画布（`std::vector<uint16_t>`），fill_rect/text/glyph/裁剪 |
| `sw/ui_renderer.hpp/.cpp` | 通用 N 类三页渲染器（Overview/All Classes/Diagnostics）+ softmax/argmax/top_k/置信度带 + tab 命中 |
| `sw/touch.hpp/.cpp` | 触摸解码：协议 A/B、EVIOCGABS 范围标定、全幅线性映射 |
| `sw/image_writer.hpp/.cpp` | BMP 写出、最近邻降采样、FNV-1a 像素哈希 |
| `sw/phase2_ui_render.cpp` | Phase2：契约取类 → staging 渲染 → `submit()` → 翻页（`0x40080050`） |
| `sw/phase3_touch_test.cpp` | Phase3：枚举触摸设备、标定、点击命中翻页、USB 断线重连 |
| `sw/test_direct_framebuffer_backend.cpp` | 后端单元测试（含 submit 金丝雀 + 越界/空指针/未 init 拒绝） |
| `sw/test_ui.cpp` | UI 单元测试（162 断言） |
| `sw/render_screenshots.cpp` | 7 场景 + 字体样张截图生成 |
| `sw/build_host_tests.sh` | 宿主机一键：编译零警告 + 单测 + ASan/UBSan + 截图 |
| `sw/build_on_board.sh` | 板端构建/运行（cmake/g++/run，仅 phase2|phase3） |
| `sw/transfer_over_serial.ps1` | 串口传输（paste 默认 / `-Send` 直驱 COM 口） |
| `sw/collect_logs.sh` | 板端证据收集（phase2|phase3） |

### 9.2 重写（v3 替换 v2 同名）

`sw/CMakeLists.txt`、`sw/build_on_board.sh`、`sw/phase2_ui_render.cpp`、`sw/phase3_touch_test.cpp`、`sw/collect_logs.sh`。

### 9.3 保留（v2 资产，v3 不构建）

`sw/phase1b_doublebuf_test.cpp`、`sw/phase1c_dynamic_test.cpp`、`fpga/bitstream/*.bit`、`fpga/program_phase1b_jtag.tcl`。

### 9.4 文档

`docs/MASTER_MANUAL.md`、`docs/PHASE2_BRINGUP.md`、`docs/PHASE3_BRINGUP.md`（已更新为 v3 三页/N 类契约）；`docs/BUILD_RESULTS.md`（v2 位流构建结果，v3 复用）；`docs/CDC_WAIVERS.md`、`docs/HDMI_WORK_REPORT.md`、`docs/PHASE1B_BRINGUP.md`、`docs/PHASE1C_BRINGUP.md`（v2 参考保留）。

---

## 10. 交付物完整性校验

- `SHA256SUMS.txt` 覆盖全部 v3 源码/脚本/位流，已用 `sha256sum -c` 自检 **ALL OK**。
- 截图哈希见 §4 与 `sw/screenshots/hashes.txt`。
- 位流 SHA-256 与 v2 记录一致（`fdc93f10…` / `686bb1e3…`）。

---

## 11. 下一步（等你操作，我不碰板）

1. 加载临时 JTAG 位流（`fpga/program_phase1b_jtag.tcl`，`_disable_icap.bit`，永不写 Flash）。
2. 用 `transfer_over_serial.ps1` 把 `sw/` 传上板（或 scp）。
3. `./build_on_board.sh` 构建；`./build_on_board.sh run phase2 -1 20 -1` 看三页/Top-5/All Classes；`run phase3 30` 测触摸。
4. `./collect_logs.sh phase2|phase3` 收集证据。
5. 全部满足 §5 判据后，才由**你**把状态改为 `PASS`。
