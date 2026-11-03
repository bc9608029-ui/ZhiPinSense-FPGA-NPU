# 运行时依赖完整身份（A 线交付级复审，纯离线）

本表追踪部署运行入口 `standalone_receiver.py`（覆盖层，SHA `4d35cf5e…`）的**全部
import 语句** → 实际导入文件路径 → 来源（覆盖层 vs 板端 BASE）→ 完整 SHA256 →
溯源性质（独立来源 vs 循环复制）。生成时间 2026-10-29，只读审计，未改任何冻结文件。

## sys.path 解析规则（standalone_receiver.py 第 15-18 行）

```python
ROOT = Path(__file__).resolve().parents[1]   # <部署树>/rml24_final
sys.path.insert(0, str(ROOT/'runtime'))      # runtime/
sys.path.insert(0, str(ROOT/'recovery'))     # recovery/
sys.path.insert(0, str(Path(__file__).parent))  # board_runtime/
```

所有模块名在 runtime/、recovery/、board_runtime/ 之间无重名，故每个 import 的解析路径唯一。

## 身份表

| # | import（行号） | 解析到的部署路径 | 来源 | 本地可核对 SHA256（独立副本） | 溯源性质 | 板端 BASE 核验状态 |
|---|---|---|---|---|---|---|
| 1 | `import candidate_two_dc`（19） | `rml24_final/recovery/candidate_two_dc.py` | BASE | `e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a` | **独立**（10-27 `integration_assembled_final/recovery/` 实测） | 已冻结：接收包装器运行时校验，不符 fail-closed |
| 2 | `from receiver_core import recover_frame`（20） | `rml24_final/runtime/receiver_core.py` | BASE | `cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a` | **独立**（10-27 assembled runtime 实测） | 已冻结：接收包装器运行时校验，不符 fail-closed |
| 3 | `from radio_tuning import RxLoController`（21） | `rml24_final/runtime/radio_tuning.py` | BASE | `a6df471b9d69f37334546b436d32eb3aff3f9ea8012027aafd9738c981a323bf` | **独立**（10-27 scan + fivepage 两棵独立树 9 副本同值，早于 standalone_execution 轮） | **待板端核验**（本地无 standalone_execution 树） |
| 4 | `from scan_runtime import ScanConfig, detect_public_training`（22） | `rml24_final/runtime/scan_runtime.py` | BASE | `26d38b8eddbaf299a2e396198e392b3e6e3f618bc97290aeb836f07331ed7a9b` | **独立**（10-27 scan 权威树 + C reference 同值） | **待板端核验**（本地无 standalone_execution 树） |
| 5 | `from standalone_control import Controller, ControlServer, RestartAcquisition`（23） | `rml24_final/runtime/standalone_control.py` | BASE | `522aeaaa10d5a7e0472478a088ab04c38855876fcbf4eeb0592800cc52de6799` | **循环复制**（本地 8 副本同值，但 C reference 自述从本 candidate 抄；无任何 10-27 独立产物） | **待板端核验（最弱）**（本地无 standalone_execution 树，唯一独立证据是 fix1 树该文件 mtime=Oct 27 22:29 与 BASE 轮同日，属推断非证明） |
| 6 | `from scan_lock_policy import LockHysteresis`（24） | `rml24_final/runtime/scan_lock_policy.py` | **覆盖层** | `912f2e24a0cb50768eb8bcdcfc552a8a57082900c85ec4c8485ffb264c13f320` | 覆盖层清单 | 已冻结：覆盖层 12 文件 0 失配 |
| 7 | `from rml24_dualmode_receiver_centered_v2 import UiSocketClient, infer, write_json_atomic`（25） | `rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py` | BASE | `11061886abbd51d63eb1ac70bd555d06688e0b673759dc46cb475d2161ef2b36` | **独立**（10-27 fivepage 树，唯一精确同名副本） | **待板端核验**（本地无 standalone_execution 树） |
| 8 | `from ui_event import build_ui_event, build_board_ui_result`（26） | `rml24_final/runtime/ui_event.py` | **覆盖层** | `990d75fe288ecd50a41743d5f6fa451171b435505015278d3a757c961b7ec43d` | 覆盖层清单 | 已冻结：覆盖层 12 文件 0 失配 |

另有两个 legacy-root 依赖（standalone_receiver.py 第 51-53 行经 `--legacy-root` 动态导入）：
`pluto_link_probe`、`pilot_recovery` —— 由 `run_repeat_mean_gapfix1.sh` 第 37-38 行做存在性检查（不存在即 exit 2），内容为上一轮正式 legacy 树，不属本轮候选。

## 关键结论

1. **四个 BASE 来源运行时依赖**（#3 radio_tuning、#4 scan_runtime、#5 standalone_control、
   #7 rml24_dualmode_receiver_centered_v2）均**不在覆盖层**，部署后来自板端 BASE
   `/root/rml24_standalone_execution_20261027/candidate/rml24_final/…`。
2. 这四者**均不在 install_overlay.sh 的 7 个冻结基线 SHA 里，也不在 run 脚本 / 接收包装器的
   运行时校验里**——是现有交付的依赖闭包缺口。
3. 其中 #3/#4/#7 有**独立的 10-27 年代本地副本**可作期望值（非循环）；#5 standalone_control
   的本地副本是**循环复制**（C 从本 candidate 抄），无独立板端年代产物，身份最弱。
4. 板端 BASE 树 `/root/rml24_standalone_execution_20261027` **本地不存在**，故四者板端实际
   内容**均属「待板端核验」**，本地副本不得当可信板端基线、不得自动接受任意 SHA。
5. 预检脚本 `scripts/preflight_deploy.py` 对 #1/#2/#6/#8 做冻结 SHA 硬校验（不符 rc≠0），
   对 #3/#4/#5/#7 只测存在性 + 输出实测 SHA 并标记「待板端核验」；若提供 `--expect` 清单
   则严格比对、不符即停（rc≠0）。

## AC 集成新增：候选多信号入口 `standalone_receiver_multisignal.py`（覆盖层）

该入口是**显式候选模式**，不修改冻结单目标入口 `standalone_receiver.py`（4d35cf5e）。其 import
闭包（第 34-41 行）与单目标入口高度重叠，仅新增第 41 行的 `multisignal_receiver_entry`：

| import（行号） | 解析路径 | 来源 | SHA256（覆盖层/独立副本） | 板端核验状态 |
|---|---|---|---|---|
| `import candidate_two_dc`（34） | `rml24_final/recovery/candidate_two_dc.py` | BASE | `e0aa1202…`（同上表 #1） | 已冻结（运行时校验） |
| `from receiver_core import …`（35） | `rml24_final/runtime/receiver_core.py` | BASE | `cb529824…`（同上表 #2） | 已冻结（运行时校验） |
| `from radio_tuning import RxLoController`（36） | `rml24_final/runtime/radio_tuning.py` | BASE | `a6df471b…`（同上表 #3） | 待板端核验 |
| `from scan_runtime import …`（37） | `rml24_final/runtime/scan_runtime.py` | BASE | `26d38b8e…`（同上表 #4） | 待板端核验 |
| `from standalone_control import …`（38） | `rml24_final/runtime/standalone_control.py` | BASE | `522aeaaa…`（同上表 #5） | 待板端核验（最弱，循环复制） |
| `from rml24_dualmode_receiver_centered_v2 import …`（39） | `rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py` | BASE | `11061886…`（同上表 #7） | 待板端核验 |
| `from ui_event import …`（40） | `rml24_final/runtime/ui_event.py` | 覆盖层 | `990d75fe…`（同上表 #8） | 已冻结（覆盖层） |
| `from multisignal_receiver_entry import …`（41） | `rml24_final/runtime/multisignal_receiver_entry.py` | 覆盖层 | `125590e7…` | 已冻结（覆盖层） |

`multisignal_receiver_entry` 的传递闭包（全为覆盖层、本轮权威 SHA，已冻结）：

| 模块 | 依赖 | SHA256（覆盖层） |
|---|---|---|
| `multisignal_receiver_entry.py` | `multisignal_scan_adapter`（try 优先，fallback `src.scan_adapter` 仅为 C 线兼容，覆盖层部署必走前者） | `125590e7…` |
| `multisignal_scan_adapter.py` | `multisignal_contracts`、`multisignal_tracker` | `95723bae…` |
| `multisignal_tracker.py` | `multisignal_contracts` | `7af0ff26…` |
| `multisignal_contracts.py` | 无内部依赖 | `f23dd340…` |
| `multisignal_psd.py` | `multisignal_contracts` | `4dba4f7e…`（**不在生产闭包**：仅离线测试经 `psd_detect` 注入；生产公共帧为满带宽，相关器单命中，`psd_detect=None`） |

**新增第 9 个 BASE 传递依赖**：`rml24_dualmode_receiver_centered_v2` 内部 `from mode_control_server
import ModeControlServer, ModeState`。该文件此前**未在身份表登记**（单目标入口同样传递依赖它，属上一轮
交付即存在的闭包缺口）。本地独立副本 SHA `ffd78518…`（scan 树 + fivepage 树同值），但同 #3/#4/#7，
板端实际内容**待板端核验**，本地副本不得当可信板端基线。预检脚本将其列入 `UNVERIFIED_DEPS`，
`board_collect_dep_sha.sh` 一并采集其板端实测 SHA。

## AC 集成 C++ UI 文件（覆盖层，编译期非运行时 import 闭包）

预检脚本只校验 Python 运行时闭包；以下 C++ 文件的身份由打包 SHA256SUMS 清单在解包时校验：

| 文件 | 来源 | 本轮 SHA256 |
|---|---|---|
| `board_package/target_list_dispatch.hpp` | 覆盖层（新增） | `d3b7dc70…` |
| `board_package/target_list_rml24_parse.hpp` | 覆盖层（C 线） | `5799f904…` |
| `board_package/target_list_state.hpp` | 覆盖层（C 线） | `38cc7484…` |
| `board_package/board_ui_live_rml24_final.cpp` | 覆盖层（改，7 处） | `1c422cf8…` |
| `ui_sw/ui_render.hpp` | 覆盖层（改） | `b2ece3ca…` |
| `ui_sw/ui_render.cpp` | 覆盖层（改） | `0f6c489c…` |

## 进程身份回退（本轮最终整改新增）

依赖身份（文件 SHA）之外，回退还核对**进程身份**，防止误杀同名正式进程 / 其他 RUN 的候选进程 /
PID 复用后的无关进程。`run_ac_candidate.sh` 起每个子进程后，把它的完整身份写入 `$RUN/pids.tsv`：

| 字段 | 来源 | 含义 |
|---|---|---|
| role | 脚本硬编码 | `npu` / `ui` / `rx`（预期角色） |
| pid | `$!` | 本次启动的进程 PID（>1 正整数） |
| starttime | `/proc/PID/stat` 第 22 字段 | 进程启动 ticks（防 PID 复用） |
| exe | `readlink -f /proc/PID/exe` | 精确可执行文件路径 |
| argv_sha | NUL 分隔 `/proc/PID/cmdline` 的 sha256 | 按真实参数边界比较，非子串 |

`rollback_ac_candidate.sh` 停止前要求**同 boot_id + 同 starttime + 预期角色 + 精确 exe + argv_sha 全匹配**；
任一不符或不可核对（如 `/proc` 读不到、记录为空/UNKNOWN/0）即 `REFUSED` 并返回非零，**绝不退化到
通用程序名（`npu_stream`/`board_ui_live_rml24_final`）**。对 Python RX 不只看解释器 exe（argv 的 sha256
已涵盖脚本路径与本 RUN 参数）。回退顺序固定 RX→UI→NPU（RX 先做有界 TERM 清理，默认不 KILL）。
