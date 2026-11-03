# M29 RML23 Stage H-E / Route E — fix1 打包勘误审计

状态: M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST
      （fix1 只修复打包源选择/基线覆盖缺陷，不改变 Route E 最高允许状态；本轮未碰板、
       未训练、未写任何 *_PASS / PROJECT_COMPLETE / FINAL_*；未把
       DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / RF_LEAKAGE_NOT_PROVEN 改 PROVEN）

本文档记录首次 Route E 合并全量包 `2d8b8bab…` 的板端编译失败根因、修复与防复发机制。
旧错误包 `2d8b8babd8a351264a92184c7b388e23936c1a9dfc494c55e509423ab1920c00` 原样保留、不覆盖。

--------------------------------------------------------------------------------
 1. 板端硬证据（编译失败点）
--------------------------------------------------------------------------------
`board_gate9_full_chain_rml23.cpp` 的下列行引用了 `syniq_run::RawRxOutput` 的三个字段：

  board_gate9_full_chain_rml23.cpp:2442  const std::uint64_t pushed_complex = outp.pushed_complex;
  board_gate9_full_chain_rml23.cpp:2451  f.write(..., outp.iq.data(), ...)
  board_gate9_full_chain_rml23.cpp:2476  const std::int16_t v = outp.iq[k];
  board_gate9_full_chain_rml23.cpp:2509  ... << outp.quant_scale << '\t'

而首次合并全量包内的 `board_package/synthetic_iq_runner.hpp` 只含 route-D 基线版
`RawRxOutput { tensors; quant; }`，缺少 `iq / pushed_complex / quant_scale`，故板端
编译失败（`outp` 无这些成员）。

--------------------------------------------------------------------------------
 2. 根因
--------------------------------------------------------------------------------
`scripts/package_iq_digital_loopback.py` 的 `ROUTE_E_FILES` 清单漏列了
`board_package/synthetic_iq_runner.hpp`。该文件在 Route C 持久化（Stage H-E 前置增量）
中已在工作树被修改（新增 `iq / pushed_complex / quant_scale` 三个字段），但打包器只
枚举了「被感知到的改动文件」，未把「被 .cpp 引用的、也改了字段的头文件」纳入清单。

合并全量包的构造是 `copytree(route_d 基线) + 覆盖 ROUTE_E_FILES`。因此漏列的
`synthetic_iq_runner.hpp` 未被覆盖，仍停留在 route-D 基线旧版 —— 而
`board_gate9_full_chain_rml23.cpp`（已在清单内）引用新字段，两者错配。

对照：独立补丁包只含 ROUTE_E_FILES 自身，不含合成器头，故 patch 内无此问题；
缺陷只在「route_d 基线 + Route E」的合并全量包里暴露。

--------------------------------------------------------------------------------
 3. 修复（非手工替换 tar，改打包器）
--------------------------------------------------------------------------------
1. `ROUTE_E_FILES` 显式加入 `board_package/synthetic_iq_runner.hpp`（MODIFIED），
   合并全量包据此用工作树全量内容覆盖基线旧版。
2. 新增 `host_tests/test_route_e_raw_rx_output_fields.cpp`，在编译期直接访问
   `RawRxOutput::iq / ::pushed_complex / ::quant_scale`：今后若再漏包/回退该头，
   此测试将编译失败（正是本次缺陷的失效模式），把「漏包」从运行时错误提前到编译期。
3. 新增 `audit_dependency_closure()`：打包前对 ROUTE_E_FILES 中所有 C/C++ 文件做
   传递闭包 `#include "…"` 扫描，凡解析出的头与 route-D 基线逐字节不同、或基线中
   不存在，却不在 ROUTE_E_FILES 里，立即 fail-closed 终止打包并列出遗漏文件。
   这使「被引用的头在工作树改了却未入清单」这类缺陷无法再静默复发。

--------------------------------------------------------------------------------
 4. 防复发自检（打包器内建，packager 运行即执行）
--------------------------------------------------------------------------------
打包器在生成任何 tar 之前先跑 `audit_dependency_closure`；通过后打印
`dependency-closure audit: OK`。失败则打印遗漏清单并以非零退出码终止，不产出
任何（可能再次缺文件的）包。

--------------------------------------------------------------------------------
 5. 逐字节一致性与离线验证（见交付说明 fix1）
--------------------------------------------------------------------------------
工作树与解包产物对以下 Route E 文件逐字节一致（实测见交付说明）：
  board_package/synthetic_iq_runner.hpp
  board_package/board_gate9_full_chain_rml23.cpp
  board_package/iq_digital_loopback.hpp
  board_package/iq_digital_loopback_runner.hpp

离线验证（本轮执行，未碰板）：
  1. 新合并全量包独立解包 sha256sum -c 全 OK；
  2. host 全套件（含新增 test_route_e_raw_rx_output_fields）ALL PASSED；
  3. syntax_check.sh 用包内 board_package 对 board_gate9_full_chain_rml23.cpp 做
     `-fsyntax-only`（iCraft 3.39 头），与包内 synthetic_iq_runner.hpp 一起编译通过。

  模型 / 标签 / golden / 预处理契约 / RTL / XDC / 位流 / Flash 均未修改。

--------------------------------------------------------------------------------
 6. 红线保持
--------------------------------------------------------------------------------
- 最高状态仍为 M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST，不写 BOARD_TEST_PASS。
- 三判决分离、arbitrary_modulated_iq_fidelity=BOARD_REQUIRED、RF_LEAKAGE_NOT_PROVEN 不变。
- 旧错误包 `2d8b8bab…` 与全部历史包（cb3f204e…/e988707c…/e166bb32…/1158dbfd…/
  6c3258a7…/5a4c4d3a…/29946764… 等）一律保留、不覆盖。
