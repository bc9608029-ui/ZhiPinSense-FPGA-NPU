> 本文件记录原单频界面。多频点候选的当前说明以软件根目录 HANDOFF_MULTIFREQUENCY_UI.md 为准；下方“多信号按钮禁用”属于旧版本状态。

# 发射界面交接

状态：OFFLINE_UI_AND_WORKER_VERIFIED_HARDWARE_ACCEPTANCE_PENDING。

入口app.py；说明README.md；本机启动命令：

```powershell
& 'D:\Anaconda\python.exe' 'F:\嵌赛\rml24_tx_console_20261029\app.py'
```

UI由PyQt5 Widgets实现，桌面1280×850，中文键鼠，支持高DPI和滚动布局；无需联网或浏览器。默认离线，真实TX需要用户显式勾选和开始。

## 本轮通过

- unittest 13/13：24类既有样本SHA与帧构造、频率精确转换、非法输入、模拟Radio发送/回读失败/停止/恢复异常。
- GUI_SMOKE：实际Qt→QProcess→离线工作进程→日志事件→停止请求→结束结果链通过。未加载Radio驱动或访问SDR。
- Windows原生截图preview_windows.png已人工查看，修正高DPI重叠；截图非RF演示。
- 复制既有冻结公共帧生成器、参考和Radio实现，vendor_identity.json绑定；assets内24类各一个既有IQ样本，逐字节校验。
- 子进程管道加UTF-8；JSONL文件作为可靠事件源，管道/文件按time_ns去重，部分尾行等待下次读取。

## 功能范围

选择24类中的一类重复、24类轮播、频率、硬件增益、保持时间、会话时限；单设备URI/只读USB扫描；实际载荷数字PSD预览；运行日志、停止、关闭窗口等待清理。没有给RX连接或传递开始/类别/尺度。

多信号同时TX入口暂禁用；未经RF验收不启用。新选择界面不提供“正式准确率判分”，演示采集不能直接替代冻结RF矩阵。

## 下一步硬件验收（用户执行）

1. 在离线状态打开UI，校验预览并开始/停止；检查assets可独立读取。
2. USB扫描或填准确TX URI；运行解释器默认radioconda，需libiio.dll/numpy/scipy。
3. 同轴链路就绪后默认2.4GHz/2.56MS/s/18MHz/-40dB，短会话发一个已知类，接收端独立运行。
4. 验证停止按钮、会话时限、关窗口清理、错误显示；核验实际属性恢复。
5. 通过后再做24类轮播；6s保持+0.25s间隔完整一轮约150s，默认60s不足一轮。

## 边界

Radio.close是原实现，返回恢复写入错误，不是恢复后独立读回；关闭/停止不可当作硬实时急停。驱动阻塞可能延迟清理。进程被强杀、USB拔除等异常导致状态无法确认时，UI不得标恢复成功。

本轮未操作SDR、未发射、未训练、未改A/B/C或主链。GUI测试使用真实进程和离线数据；模拟Radio测试的real=true只为覆盖分支，不是硬件发射证据。
