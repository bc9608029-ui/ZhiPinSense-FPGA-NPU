# 下一步决策（PREP2 收口）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
**最高只写本令牌；不写 BOARD_PASS / BOOT_PASS / AUTO_DISPLAY_PASS / PROJECT_COMPLETE / "safe to burn"。**

## 1. 本阶段做了什么（离线，未碰板）

1. 修复 PREP1 两个采集工具缺陷：
   - devmem 输出归一化（`scripts/normalize_devmem_value.sh`，修复 `0x0x20230218` 双前缀，正负测试覆盖）；
   - 板端编译器选择（`scripts/select_cxx.sh`，`g++` → `c++` → `aarch64-linux-gnu-g++`，全缺 `CXX_NOT_FOUND` 即停，mock PATH 测试覆盖）。
2. 交付 Linux 只读采集工具 v2（`collect_fmql_boot_state_v2.sh`，新增 lsblk/modinfo/驱动源码枚举/fw_printenv 配置守卫）。
3. 交付 SD 启动分区只读审计（`collect_sd_boot_partition_ro.sh`，sysfs+/proc/partitions 双重确认、只 ro 挂载、只读备份、绝不写回）。
4. 交付 COM12 U-Boot 只读手册 + 5 份证据审计文档 + 逐方案阻断矩阵。
5. 离线解出并解析 `.bif`（`.bif` 分区顺序权威确认；vendor 示例 BOOT.bin 结构解析；vendor 组件与示例 BOOT.bin 组件字节一致）。

## 2. 7 个问题 → 采集映射（用户板端执行，全部只读）

| 问题 | 采集动作 |
|---|---|
| 1 板实际从哪启动 | Boot-DIP 照片 / MIO3~MIO5 读数 + U-Boot `printenv` |
| 2 U-Boot 是否自动载位流（哪个分区/文件） | U-Boot `printenv`（bootcmd/loadbit）+ `help fpga` |
| 3 当前 BOOT.bin/uEnv.txt 内容 + SHA | `collect_sd_boot_partition_ro.sh` |
| 4 当前 BOOT.bin 的 FSBL/U-Boot/位流组成 | 板 BOOT.bin 备份后用 `verify_boot_artifacts.py bootbin-info` |
| 5 secure boot 是否启用 | U-Boot `printenv` + dmesg + 板 BOOT.bin 加密字 |
| 6 Linux FPGA Manager 镜像格式 | `collect_fmql_boot_state_v2.sh` 的 modinfo/源码枚举 |
| 7 A/B/C 哪条有足够证据 | 见 `docs/SCHEME_BLOCKER_MATRIX.md`，据采集结果刷新 |

## 3. 采集完成后才允许的下一步

1. 补齐 `docs/BOOT_MODE_EVIDENCE.md`（MIO3~MIO5 真值表 + 板上实际位置）。
2. 判定方案 A/B/C 的阻断项哪些解除（刷新 `SCHEME_BLOCKER_MATRIX.md`）。
3. 若选 A：用户用 Procise「Create Image」按 `.bif` 生成候选 BOOT.bin（用工作位流 `22fec95c…` 替换 vendor 位流）→
   离线 `verify_candidate_image.sh --boot-bin … --bit …` 校验 → 备份 → 授权后写入 → **至少三次完整断电重启验证**。
4. 若选 B：先板端确认 `fpga loadb` 可用 + 分区/路径正确，再决定是否把 `download.bit` 放到正确分区。

## 4. 停止条件

- **在 A/B 板端阻断项补齐前，不写任何启动分区 / Flash / U-Boot env / FPGA 配置。**
- secure boot 未确认前不写自生成 BOOT.bin。
- 完成证据采集后本阶段即停，等用户回传板端采集结果再进入下一阶段（届时状态可升级为 `…-BOARD-EVIDENCE-COMPLETE`）。
