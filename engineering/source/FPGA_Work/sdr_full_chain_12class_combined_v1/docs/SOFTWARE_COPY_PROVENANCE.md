# 软件拷贝来源清单（combined_v1 §七 M7）

> 生成：2026-10-06。合并工程软件侧（board_package / sdr_adapter / ui_sw / scripts /
> contracts / host_tests / model_12class / deployment_golden）**逐字节**拷贝自
> `sdr_full_chain_12class_ui_v1`（已上板/主机全 PASS 的十二类软件链，不重复开发）。

## 1. 拷贝来源与逐字节校验

| 目录 | 来源 | 文件数 | 逐字节校验 |
|---|---|---|---|
| board_package/ | sdr_full_chain_12class_ui_v1/board_package | 19 | `diff -rq` IDENTICAL |
| sdr_adapter/ | sdr_full_chain_12class_ui_v1/sdr_adapter | 35 | IDENTICAL |
| ui_sw/ | sdr_full_chain_12class_ui_v1/ui_sw | 7 | IDENTICAL |
| scripts/ | sdr_full_chain_12class_ui_v1/scripts | 12→改 1 | 见 §2 |
| contracts/ | sdr_full_chain_12class_ui_v1/contracts | 3 | IDENTICAL |
| host_tests/ | sdr_full_chain_12class_ui_v1/host_tests（排除 bin/ asan/） | 13 | IDENTICAL |
| model_12class/ | sdr_full_chain_12class_ui_v1/model_12class | 258 | IDENTICAL |
| deployment_golden/ | sdr_full_chain_12class_ui_v1/deployment_golden | 244 | IDENTICAL |

> 权威逐文件 SHA256 见来源工程 `sdr_full_chain_12class_ui_v1/PROVENANCE.md`（590 文件，
> 0 不一致）。本工程与之一致（`diff -rq` 全 IDENTICAL），不再重复生成 590 条 SHA。

## 2. 相对 ui_v1 的差异（仅合并工程内的改动）

| 文件 | 动作 | 说明 |
|---|---|---|
| `scripts/run_gate9_ui.sh` | **解锁**（改写） | 删掉旧 `FULL_CHAIN_UI_BLOCKED bitstream_incompatible exit3` 桩；改为组合位流下真实接线：fail-closed 校验 UI socket（HDMI 在位）→ `exec run_gate9.sh --sock=...`（NPU 由 gate9 二进制 `Device::Open` fail-closed）。旧 BLOCKED 结论仅适用于 HDMI-only/NPU-only 位流，已被组合位流取代。 |
| `scripts/package_board_release_combined.sh` | 新增 | smoke_v1 板端软件包打包脚本（适配本工程目录，无 tools/ 无 PROVENANCE.md）。 |
| `docs/BOARD_SMOKE_TEST_COMBINED.md` | 新增 | C1/C2/C3 三条板端烟测命令 + 合并位流身份判定。 |
| `docs/COMBINED_BITSTREAM_DESIGN.md` §5 | 补充 | 身份判定实现要点（HDMI=`/dev/mem` 版本门；NPU=iCraft `Device::Open`，**不可经 `/dev/mem`**）。 |
| `docs/{GATE6_9_BOARD_TEST,BOARD_LIVE_UI_TEST,RECEIVER_SCALE_CALIBRATION}.md` | 拷贝（原样） | 仍有效的逐门板测流程（C1/C2/C3 引用）。 |

> 未拷贝 ui_v1 的 `BITSTREAM_COMPAT_AUDIT.md`：其「NPU 与 HDMI 互斥/BLOCKED」结论已被
> 组合位流推翻，放入本包会误导（本工程自有 `ADDRESS_MAP_AUDIT.md` 已纠正）。
