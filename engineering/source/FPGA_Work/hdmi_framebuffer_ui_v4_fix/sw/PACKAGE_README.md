# hdmi_39e5_sw — 软件修复版传输包（任务 39e5）

本包只含 **PS 软件**，修复 Phase2/Phase3 Release(-O2) 的 **SIGBUS(rc=135)**。
**不包含** RTL/XDC/位流（位流未变，仍用 `hdmi_framebuffer_720p_top_disable_icap.bit`，
SHA 见仓库根 `SHA256SUMS.txt` 与 `docs/BOARD_TEST_39E5.md`）。

## 变更要点

- **根因**：GCC -O2 自动向量化把"非 volatile `uint16_t*` 直写 u-dma-buf mmap"变成
  NEON/SIMD 宽存储，被映射拒绝 → SIGBUS。
- **修复**：普通内存 staging 缓冲（画图向量化无害）+ 唯一设备写路径
  `DirectFramebufferBackend::submit_frame(frame_index, staging_data, pixel_count)`：
  校验 → `volatile uint16_t*` 逐元素标量写 → `flush()`(msync + sync 节点，确认成功)
  → 最后切换显示缓冲寄存器。应用层拿不到非 volatile mmap 指针。
- 强制标量三保险：`noinline` + `optimize("no-tree-vectorize","no-tree-slp-vectorize")` + `volatile`。
- 覆盖 Phase1B/1C/2/3，全部走同一 submit 路径。
- 字号可读性：去掉 scale=1；类名/状态栏/百分比 ≥ scale=2，标题 scale=3，边框 2px，
  经 1024×600 降采样后仍清晰。

## 证据

- `objdump_evidence/submit_frame_aarch64_disasm.txt`：提交循环只有 `ldrh` + `strh`
  （16-bit 标量），**无 st1/st2/st3/st4/str q/str d**。
- `objdump_evidence/submit_frame_aarch64_full.txt`：同一 .o 的完整反汇编（审计用）。
- 主机单测 `test_direct_framebuffer_backend` 全 PASS（含越界/帧大小/frame_index/金丝雀），
  ASan/UBSan 全 PASS。

## 板上用法（root，权威 -O2 构建）

```bash
sha256sum -c SHA256SUMS.txt                 # 先校验
./build_on_board.sh g++                     # g++ -std=gnu++17 -O2 -Wall -Wextra（权威 -O2）
./build_on_board.sh run phase1b 0 60        # 动态双缓冲
./build_on_board.sh run phase2 0 20         # 静态 UI
./build_on_board.sh run phase2 -1 20        # 动态 UI
./build_on_board.sh run phase3 30           # 触摸
```

复测判据与逐条命令见 `docs/BOARD_TEST_39E5.md` §5A（仓库内）。

## 状态

**READY-FOR-HARDWARE-RETEST** —— 待 -O2 上板复测：Phase2/3 无 SIGBUS + 显示/触摸正常后，
由测试者标记 `HARDWARE_PASS`。
