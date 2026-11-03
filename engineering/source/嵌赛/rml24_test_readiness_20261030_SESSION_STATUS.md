# 2026-10-30 参数实测启动预检

- 用户已授权开始设备测试；当前尚未采集/发射/停止板端服务/加载新位流。
- 192.168.126.49 Ping回复<1ms。外部OpenSSH与独立Python TCP探测均显示22端口拒绝连接；不能据此宣称SSH已登录或板端依赖已确认。
- 本机System32默认libiio缺少iio_create_context_from_uri。找到并只读验证D:/radioconda/Library/bin/libiio.dll（0.26），PC USB枚举为usb:1.7.5。没有创建SDR采集/发射上下文。
- 测试入口增加--libiio-library并保留DLL依赖目录句柄；不修改冻结vendor文件。
- 下一步需要板端串口确认/启动SSH服务，网络恢复后继续板端只读预检。没有密钥认证也尚未解决，不能凭Ping认为自动时钟探针已可运行。
