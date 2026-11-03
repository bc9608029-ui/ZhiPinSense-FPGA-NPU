# RML24 主链修复与整机冻结候选

状态：`PROMOTION_CANDIDATE_OFFLINE_PACKAGE_READY_TARGET_ACCEPTANCE_PENDING`。

## 已有真实 RF 证据

所有结果固定分母 240，缺失、拒绝和错误均计错，没有删除失败项。

| 模式 | 原正式基线 | 当前组合候选 | 漏项 |
|---|---:|---:|---:|
| 定频 | 227/240 | 233/240 | 0 |
| 扫频 | 232/240 | 237/240 | 0 |

候选定频和扫频都优于原正式基线，因此冻结的逐行晋级逻辑给出
`PROMOTION_CANDIDATE`。233/240 低于一次中间定频候选的 235/240，但该中间候选
不是正式基线；不能据此把当前候选写成回退，也不能把不同 RF 轮次的随机波动冒充
算法差异。

## 候选内容

- 公共帧 two-DC 恢复与冻结 NPU 模型不变。
- 8 段重复载荷相干平均用于定频和扫频识别。
- 扫频采用单点增量搜索，在搜索点之间重访最后成功锁定频点，避免阻塞式全扫造成漏项。
- 五页 UI2：识别、参数、瀑布、星座、调谐；定频和扫频参数可通过数字键盘输入。
- 频率单位合同（§3）收口：内部协议/存储/计算一律整数 Hz；界面以 MHz/kHz/MS/s 显示并
  显式标注单位；键盘十进制 MHz 输入精确转整数 Hz（拒子 Hz/非法/越界，禁浮点截断）。
- UI 中不能可靠测得的 SNR、dBFS、符号率不会伪装成有效测量值。

候选文件位于 `candidate/`。它尚未覆盖板端正式服务。

## 冻结身份（SHA256，前 8 位标签）

| 对象 | SHA256（前 8） | 说明 |
|---|---|---|
| 冻结 NPU 模型 JSON | `28272abc…` | `rml24_adamrv11_bf16.json` |
| 冻结 NPU 模型 RAW | `c1781aec…` | `rml24_adamrv11_bf16.raw`（UI 侧 `model_sha`） |
| two-DC 恢复 | `e0aa1202…` | `recovery/candidate_two_dc.py` |
| 冻结接收核 | `cb529824…` | `runtime/receiver_core.py` |
| 独立接收器（覆盖层） | `4d35cf5e…` | `board_runtime/standalone_receiver.py` |

平均策略为 8 段**相同**载荷重复的相干平均（`repeat_mean_candidate.py` 对
`[8,2,1024]` 张量 `mean(axis=0)` 后广播回 8 段），不是被否决的“八段不相关窗口相干
平均”候选；两者不可混用。

## 控制闭环与频率单位（离线核验结论）

- 控制协议端到端：`SET_MODE FIXED|BAND_SCAN` / `SET_FIXED_HZ <hz>` /
  `SET_SCAN_RANGE_HZ <start> <stop> <step>` / `START` / `STOP` / `STATUS` /
  `GET_TUNING`；非法值 fail-closed 返回 `ERR`，不落地状态。
- `AUTO_LOCK` 不是用户模式（fail-closed 拒绝），仅作为扫描内部锁定状态显示。
- 单位换算：内部整数 Hz；命令侧 `isdecimal()` 校验整数 Hz；UI 键盘十进制 MHz（含
  `.` 小数点键）精确转整数 Hz，拒子 Hz（>6 位小数）/非法/越界，禁浮点截断。
- 非法范围：越界频率 `OUT_OF_RANGE`、起止倒置 `INVALID RANGE`、步长非正/过大/超点数
  `INVALID RANGE`；`BUSY`（队列满或模式冲突）与取消/离页丢弃草稿均已覆盖。
- 触摸：VID/PID `1a86:e5e3` 发现，`--touch-swap-xy` / `--touch-invert-x` /
  `--touch-invert-y` 校正；无旋转编码器。
- 参数诚实：未校准值不标 dBm（只标 dB rel / model domain / dB）；未测符号率不伪造；
  `SNR (est)` 与 `dBFS` 不出现。

## 离线复验

```powershell
python scripts/audit_release.py
python candidate/tests/test_scan_lock_policy.py
python candidate/tests/test_standalone_control.py
python candidate/tests/test_ui_measurements.py
python candidate/tests/static_audit.py
```

应看到 release audit 为 `PROMOTION_CANDIDATE`（checks=7 failed=0）、
`static_audit PASS 16/16`，其余测试全部通过。C++ 无 Windows 编译链，板端
`build_ui_live_rml24_final.sh` 是唯一编译门（`cpp_host_compile=NOT_RUN`）。

## 历史 RF 分数 vs 本轮离线测试（分列）

| 项 | 来源 | 状态 |
|---|---|---|
| 定频 233/240、扫频 237/240（漏项 0，固定分母 240） | 历史真实 RF（上一轮已测） | 历史已测，作为晋级门槛 |
| release audit `PROMOTION_CANDIDATE checks=7 failed=0` | 本轮离线 | 已跑 PASS |
| static_audit 16/16、py_compile、scan_lock_policy、standalone_control、ui_measurements | 本轮离线 | 已跑全 PASS |
| C++ 板端编译、实屏、触控、240+240 回归 | 板端 | 未上板 |

离线 PASS 不等于实屏/RF 已过；240 源身份多次复用，不代表未知波形泛化。

## 集成验收准备清单

1. 候选、`install_overlay.sh` 与 7 个冻结基线 SHA 一致：安装器校验 7 个被覆盖文件的
   旧 SHA 后复制 BASE 再叠加，绝不就地改 BASE（本轮已复审，无漂移）。
2. 接收包装器 `receiver_repeat_mean_gapfix1.py` 已改为按自身所在树解析路径
   （`Path(__file__).resolve().parents[1]`），不再硬编码 `/root/...` 板端绝对路径；
   运行时仍校验三个冻结依赖（独立接收器 `4d35cf5e…`、接收核 `cb529824…`、
   two-DC `e0aa1202…`），身份守护不变。
3. UI 可读单位（MHz/kHz/MS/s 显式标注）+ 十进制 MHz 精确转整数 Hz + 无 2500 倍数
   步长前提，均已保留，不重做。
4. 板端一键命令集见 `candidate/docs/BOARDTEST.md`（备份 → 部署校验 7 SHA → C++
   编译 → py_compile 五文件 → 24+24 smoke + 五页触控 + 十进制 MHz 键盘 → 240+240
   固定分母回归 → 回滚）。

## 上板顺序

1. 备份当前正式服务文件、位流身份和 systemd unit；记录 SHA256。
2. 把 `candidate/overlay/` 复制到一个独立测试树，不直接覆盖正式树。
3. 在板端原生重建 UI C++；编译失败立即停止，不修改编译选项掩盖错误。
4. 先跑 24 项 smoke：定频 24、扫频 24、调谐键盘（十进制 MHz，含小数点键，精确转
   整数 Hz）、五页触控、停止/恢复；第五页标签以 MHz 显式标注；用控制 socket
   （`/run/sdr_amr_control_rml24_final.sock`）验证 `SET_MODE AUTO_LOCK` 返回 ERR、
   越界/非法步长返回 ERR。板端 `python3 -m py_compile` 覆盖五个 .py 文件。
5. 再跑 240+240 正式 A/B，固定分母，必须检查漏项、恢复错误和服务退出码。
6. 仅当结果不低于本文件的 233/240 与 237/240，且触控/重启/恢复均通过，才允许
   独立安排部署；否则恢复步骤 1 的备份。

## 诚实边界

- 当前包已有两轮真实 RF 的分模式证据，但 UI2 更新后尚未在目标板 C++ 编译和实屏验收。
- 这 240 个源身份已被多次用于开发和验证，不代表任意未知波形泛化。
- `PROMOTION_CANDIDATE` 是数值和完整性判定，不等于已部署、开机自启通过或整机完成。
