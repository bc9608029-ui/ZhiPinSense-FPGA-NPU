# 限制与证据缺口（诚实标注）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
本文件列出所有「离线无法完成 / 未证实」项，禁止后续把「未证实」当「已证实」。

## 1. 主机无 C/C++ 编译器

- 本主机（Windows 11）**没有任何 C/C++ 编译器**（g++/gcc/clang/cl/aarch64-linux-gnu-g++/c++ 均缺失，已逐一探测）。
- 因此 `read_display_registers_ro.cpp` **未编译**，本阶段**不声称编译成功**。
- 只做了 **Python 静态检查**（括号配平、`O_RDONLY`/`PROT_READ` 存在、无 `PROT_WRITE`、无写 `/dev/mem`），
  见 `host_tests/test_collect_scripts_static.sh`。板端/交叉环境编译是**未来用户步骤**。
- 板端编译器选择逻辑（`select_cxx.sh`）通过 **mock PATH** 验证（`host_tests/test_select_cxx.sh`），
  本主机上未做真实编译。

## 2. 板端实跑均未执行（未来用户步骤）

- `collect_fmql_boot_state_v2.sh`、`collect_sd_boot_partition_ro.sh` 的板端实跑：未执行。
- `read_display_registers_ro` 对 `/dev/mem` 的实跑：未执行。
- aarch64 交叉编译：未执行。
- systemd 安装/enable：未执行（本包不含任何 systemd 安装/自启脚本）。
- 断电重启验证、JTAG 加载验证：未执行。

## 3. 板端事实仍缺（写启动介质前必须补）

1. 板实际启动设备（MIO3~MIO5 真值表为 PDF 图片，本地文本无法读取 → `UNCONFIRMED`）。
2. 板实际 U-Boot `printenv`（bootcmd/loadbit/uenvcmd/分区映射）。
3. 板当前 BOOT.bin 内容 + SHA（含内嵌 FSBL/位流身份）。
4. 板端 secure boot 是否启用（vendor 镜像未加密 ≠ 板端禁用）。
5. 板端 FMSH FPGA Manager 驱动镜像格式（本地无源码 → `FORMAT_NOT_PROVEN`）。
6. QSPI mtd0/mtd1 实际角色（是否承载第二启动路径）。

## 4. 未证实的本地判定

- vendor BOOT.bin 内嵌位流属于 `ai7030_edif_top.bit` 还是 `ai7030_top_disable_icap.bit`：
  打包位序变换致原始载荷未逐字对齐，`UNCONFIRMED`。
- Linux FPGA Manager 镜像格式 / 停启顺序 / 全 PL 重配能力：`FORMAT_NOT_PROVEN` / `NOT_PROVEN`。
- 板端 secure boot 状态：`UNCONFIRMED`。
- 任何 FMSH 只读状态寄存器地址（boot-mode / secure-boot）：本地无权威文档，**不猜测不读取**。

## 5. 不得写的状态

最高只写 `FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
**不写** BOARD_PASS / BOOT_PASS / AUTO_DISPLAY_PASS / PROJECT_COMPLETE / "safe to burn"。
「开机自动显示通过」只能在用户完成备份、实际部署并**至少三次完整断电重启验证**后由用户确认。

## 6. 本包不含任何写/加载/自启脚本

dist 包内**没有** auto-burn、auto-BOOT.bin-replace、auto-systemd-enable 脚本；不含 systemd 单元。
红线静态扫描覆盖全部 `scripts/*`，见 `host_tests/test_no_forbidden_ops.py`。
