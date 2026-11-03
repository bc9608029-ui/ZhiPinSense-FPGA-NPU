# AC 下一轮板测交接（2026-10-29）

## 1. 当前结论

AC 电脑侧部署准备已完成，状态为 OFFLINE_DEPLOYMENT_FLOW_VERIFIED_BOARD_ACCEPTANCE_PENDING。尚未完成板端编译、实屏触控、多目标 RF 和定频/扫频回归。未替换正式版本或自启动，不能写 RF_PASS。

下一位先做 AC，保留现有 FPGA 位流；B 线 FPGA 辅助另行验收，不与 AC 同时换位流。

## 2. 唯一有效交付

- 工作树：F:\嵌赛\rml24_ac_integration_20261029
- 归档：dist/rml24_ac_integration_candidate.tar.gz
- SHA256：f8e5cbd56995bc886835f7482d1bab4f11170bcfdd974e9ce7d4cc366bc6d5dd
- 54 个内容文件，包内 SHA256SUMS_AC.txt；包外 dist/RECEIPT_AC.txt 是归档回执。
- 旧 128b0768…、52d00f7b… 包作废。
- 详细交接：工作树/HANDOFF_AC_INTEGRATION.md
- 板测步骤：工作树/docs/BOARDTEST_AC.md
- 依赖期望：工作树/docs/DEPENDENCY_IDENTITY.md

## 3. 本次实际复核

2026-10-29 独立解包：54/54 SHA 正确；两入口身份正确；5 个多信号模块 import 正常；单目标/多目标依赖闭包分别 9/12 模块，无未解析项。合并树预检及严格模式正常、缺期望、错误 SHA、冻结文件漂移、缺文件等反例通过，verify_ac_package.py 最终 rc=0。

复核目录：F:\嵌赛\ac_review_verify_20261029_2。

交付记录已有 Python 64 测试、C++ 84 checks、部署模拟 55/55；本次未重新运行上述全套，不把文档记录冒充本次执行。

四项部署整改已落实：强制严格预检；完整进程身份回退；取消自动删除；本轮独立 RUN socket。进程身份包括 boot_id/starttime/exe/argv SHA，回退先 RX 后 UI/NPU，日志保留。

## 4. AC 实际改动与限制

新增多目标列表、去重/老化、公平重访和周期扫描、目标事件 UI 分发；集成原有测量、日志、保存采集及五页控制。不是新增准确率修复算法，不代表 FPGA 辅助已完成。

历史单目标候选定频 233/240、扫频 237/240、漏项 0；这是旧测试结果，不是当前 AC 新成绩。调度发生变化，必须回归。扫频为轮流接收，不保证任意弱信号、重叠信号全部检出。

注意历史文档矛盾：曾被否决的相干平均候选也是八段相同重复载荷，并非不相关窗口。勿继续沿用“被否决的是不相关窗口”的解释。其原验证为定频 235/240、扫频 230/240、缺失 4，DO_NOT_PROMOTE；后续组合候选另有改善证据。

## 5. 执行顺序（先核对实机路径）

1. Windows 校验上述归档 SHA，上传板端 /root/ac_candidate.tar.gz；上传不代表安装。
2. 板端解压到全新交付目录，例如 /root/rml24_ac_delivery_20261029；执行包内 sha256sum -c SHA256SUMS_AC.txt。归档不包含其自身 dist/归档文件，勿照旧手册在解压目录查不存在的 dist 包。
3. 只读核对正式服务、原位流、BASE、模型、legacy 根路径和 SDR URI。文档中的 /root 路径是历史路径，存在且身份匹配后才使用。记录原服务状态及恢复命令；正式服务和候选不能争用同一个 SDR/显示设备。
4. 用 install_overlay.sh 将 BASE 复制叠加到全新 TEST，不修改 BASE。保存 TEST 路径。
5. 采集 5 个 BASE 依赖 SHA，与 DEPENDENCY_IDENTITY.md 独立对照。不得直接把任意实测值抄成期望然后声称验证通过；不符就查明来源。严格预检 PASS_STRICT 后继续。
6. 按 BOARDTEST_AC.md B 节完成 aarch64 UI 构建和 Python 编译；保留完整日志。
7. 按文档做原单目标路径与候选定频短测，检查实屏、触控、参数输入和清除旧数据。
8. 候选扫频短测：扫描范围、列表、选择目标、重访、老化、星座/参数身份对应；至少有真实多个频点的证据，单信号测试不能证明多目标能力。
9. 用冻结 TX/真值/计分器做定频 240 + 扫频 240 回归，固定分母，缺失/拒绝/误分类分别报告；不把八窗口计成八样本，不靠改门限过关。
10. 回退实测并确认原 UI/接收服务恢复。候选停止脚本只停止本轮，不等于自动恢复被暂停的正式服务。

长时间回归需按冻结发射计划设足接收 duration；手册 60 秒只是短测示例，不能直接当完整 240 样本回归时长。

## 6. 开始前可复制的安全上传/解包

Windows PowerShell（已联网时）：

```powershell
$AcPackage = 'F:\嵌赛\rml24_ac_integration_20261029\dist\rml24_ac_integration_candidate.tar.gz'
Get-FileHash -Algorithm SHA256 -LiteralPath $AcPackage
scp $AcPackage root@192.168.126.49:/root/ac_candidate.tar.gz
```

板端 Bash：

```bash
sha256sum /root/ac_candidate.tar.gz
DELIVERY=$(mktemp -d /root/rml24_ac_delivery_20261029_XXXXXXXX)
tar -xzf /root/ac_candidate.tar.gz -C "$DELIVERY"
cd "$DELIVERY"
sha256sum -c SHA256SUMS_AC.txt
printf '%s\n' "$DELIVERY" > /root/rml24_ac_delivery_root.txt
```

后续严格按包内 BOARDTEST_AC.md，经核对路径后执行。测试前不要更改 FPGA 位流或开机默认。

## 7. 必须交回

归档 SHA、54 文件校验、5 BASE SHA 与严格预检、编译日志、原服务状态/恢复记录、UI 实屏触控证据、多目标事件和逐目标结果、两组 240 固定分母结果及缺失清单、候选运行日志与回退结果。

## 8. 发给下一位的指令

请先完整阅读 F:\嵌赛\HANDOFF_AC_NEXT_TEST_20261029.md，再阅读有效交付包中的 HANDOFF_AC_INTEGRATION.md 和 docs/BOARDTEST_AC.md。先核对实机路径与原正式服务，按 AC 单独验收，保留原位流和回退路径，不替换自启动。电脑能完成的工作自主推进，不重复询问 yes/no；设备接线与板端步骤按用户操作条件开展。未通过实机验收不得宣称 AC 整体完成，也不得沿用历史 RF 分数作为当前成绩。
