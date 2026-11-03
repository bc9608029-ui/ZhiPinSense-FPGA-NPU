# 智频感知：安全关机UI候选交接

状态：OFFLINE_VERIFIED_BOARD_BUILD_AND_POWEROFF_PENDING。原板端部署未改；本包不是已部署结果。

## 修改范围
基线是用户只读导出并核验的 /opt/rml24-integrated/releases/gain_ui_sync_20261102，共224个文件。仅改3个原UI源码：board_ui_live_rml24_final.cpp、ui_render.hpp、ui_render.cpp；新增shutdown_ui.hpp与shutdown_action.hpp。识别、恢复、三模式、历史、参数控制、模型、FPGA、原服务及监督器源码均保持SHA不变。
第五页右下角SHUT DOWN，保留全部原字段，右侧3行文字上移给按钮留空间。二次确认CANCEL / SHUT DOWN；拖出、无效释放、断触、重复点击均有保护。对话框独占触摸，避免落入原模式/键盘/导航。确认前不产生系统关机进程。
当前UI服务原本就是root，采用固定/bin/systemctl --no-block poweroff，不经过shell、不接受任意命令、不增加常驻服务。子进程关闭继承的非标准文件描述符；UI异步等待结果，不阻塞渲染循环。复用现有systemd服务SIGTERM正常退出流程，不修改原退出顺序或NPU/SDR处理。

## 已完成的电脑侧验证
- 完整Linux主机UI以gnu++17、-Wall -Wextra -Werror编译通过；不是aarch64板端构建。
- 触摸状态机16项检查；动作6项检查，另强制旧内核close_range不可用路径重复6项；仅执行/bin/true、/bin/false、短sleep等替身，真实poweroff未执行。
- 部署脚本7项反例/保护测试通过：基线不符拒绝、原树不改、失败构建不晋级、已有输出保留、服务未停/硬件guard留存拒绝。
- 固定测试输入下，第1–4页与原版逐像素一致；第5页仅右侧状态区改变，其他像素一致。这是固定画面的离线证明，不等于所有运行态已实测。
- 原始数据与结论在OFFLINE_VERIFICATION.json、offline_checks.log、deployment_tests.log和previews/。PNG是软件渲染预览，不冒充实屏照片。

## 板端步骤（用户串口执行，先不真实关机）
先停止PC发射并确认恢复正常。上传安全关机UI候选.tar.gz至/root/shutdown_ui_candidate.tar.gz，随后：

```bash
WORK="$(mktemp -d /root/rml24_shutdown_prep_XXXXXX)"
tar -xzf /root/shutdown_ui_candidate.tar.gz -C "$WORK"
cd "$WORK/rml24_shutdown_ui_candidate_20261102"
sha256sum -c SHA256SUMS.txt
python3 stage_on_board.py --check-only
python3 stage_on_board.py
```

必须看到基线224文件检查通过、STAGED_BUILD_PASS_NOT_ACTIVATED。构建日志在新候选目录shutdown_ui_build.log；失败不改原current或原二进制。新目录默认/opt/rml24-integrated/releases/shutdown_ui_20261102，存在即拒绝，不自动覆盖。

然后测试UI确认框（此阶段真正关机被替换为/bin/true）：

```bash
python3 -c 'from activate_on_board import stop_clean; stop_clean()'
RUN="$(mktemp -d /root/shutdown_ui_dry_XXXXXX)"
printf '%s\n' "$RUN" > /root/shutdown_ui_dry_run_path.txt
set -o pipefail
/opt/rml24-integrated/releases/shutdown_ui_20261102/candidate/bin/board_ui_live_rml24_final \
  --sock="$RUN/ui.sock" \
  --ctl-sock="$RUN/control.sock" \
  --history-file="$RUN/history.txt" \
  --shutdown-dry-run \
  2>&1 | tee "$RUN/ui.log"
```

在屏幕检查：第1–4页、第五页布局；点击SHUT DOWN→CANCEL不退出；再次点击并确认应显示TEST MODE - NO POWER OFF，按BACK后原页面可继续用。此时没有RX/NPU生产者，状态显示等待/控制未连接是预期，不用启动额外识别链。按Ctrl+C正常退出；ui.log必须含UI_FB_READY、UI_VERSION_CHECK ok=YES、UI_SHUTDOWN_RESULT result=DRY_RUN、UI_LIVE_STOP。
若stop_clean报guard保留或服务未退出，立即停下，不能手动删guard或强杀；按原工程恢复/重启流程处理。

## 验证后启用（会重启接收服务，结束当次运行会话）
仍在包目录，用刚保存的日志：

```bash
RUN="$(cat /root/shutdown_ui_dry_run_path.txt)"
python3 activate_on_board.py --dry-run-log "$RUN/ui.log"
systemctl status rml24-integrated.service --no-pager -l
journalctl -b -u rml24-integrated.service -n 50 --no-pager
```

这一步严格检查新UI身份及干运行日志，再停止旧服务、确认无残留硬件guard，原子切换current并启动原服务。没有改service文件、模型、位流、接收/监督器。激活输出只代表启动请求，必须继续确认UI/NPU/RX就绪。历史沿用原/var/lib路径，不从测试历史覆盖原历史。UI-only更新继承原识别证据，不是新RF测试。
回退命令（同包目录）：

```bash
python3 activate_on_board.py --rollback
```

原gain_ui_sync_20261102目录保持不动。服务无法正常停止或guard留存时回退拒绝强行重启；不能清marker绕过。

## 真正关机验收（最后才做）
1. 正常启动后做原三模式/频率输入/历史/图页短检；PC发射软件先停止并确认恢复。
2. 不登录SSH/串口也可直接从屏幕点击SHUT DOWN并确认；设备应执行Linux关机。
3. 首次验收保留串口，只观察kernel最终halt/power-down提示，核实正常退出与保存。屏幕可能保留末帧，不能仅凭静态画面判断已关机；不能预先承诺固定几秒就可安全断电。
4. 确认系统关机完成后切总电，再开机确认原自启、UI/NPU/RX与历史正常。保留日志后才记录真实关机/再开机PASS。
按钮只关闭接收板Linux，不控制独立电脑TX，也不会代替总电源开关。操作成功表示系统接受关机请求，不能把QUEUED当作已经物理断电。失败/超时只显示NOT CONFIRMED，不谎报成功，不强杀/自动重试。

## 当前缺项
aarch64编译、实屏触摸、最终原功能短检、真实关机与再开机尚未执行。未写RF_PASS/BOOT_PASS或“已部署”。先读本说明，不要直接覆盖正式目录。
