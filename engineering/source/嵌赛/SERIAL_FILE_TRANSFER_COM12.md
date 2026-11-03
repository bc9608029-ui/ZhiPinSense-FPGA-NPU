# COM12 串口文件上传

板端文件统一使用 `transfer_file_over_serial.ps1` 上传。该脚本采用已经验证过的串口方式：

1. 发送 Ctrl+C，终止未完成的终端输入；
2. 执行 `stty -echo`，避免 Base64 内容回显；
3. PC 分块发送 Base64，板端以 `base64 -d` 写文件；
4. 发送 Ctrl+D（EOF）结束解码；
5. 板端核对文件字节数和 SHA256；
6. 恢复 `stty echo`。

使用前必须关闭 MobaXterm、串口助手等占用 COM12 的程序，并让板子停在 Linux shell。

```powershell
powershell -ExecutionPolicy Bypass -File "F:\嵌赛\transfer_file_over_serial.ps1" `
  -PortName COM12 `
  -SourceFile "F:\path\package.tar.gz" `
  -RemoteFile "/root/package.tar.gz"
```

115200 波特率上传数 MB 文件通常需要数分钟。等待 `TRANSFER_HASH_PASS`，不要中途按 Ctrl+C。

如串口持续显示 Base64 字母，关闭串口终端后执行：

```powershell
powershell -ExecutionPolicy Bypass -File "F:\嵌赛\interrupt_board_serial.ps1" -PortName COM12 -BaudRate 115200
```

恢复提示符后再检查板端文件；不要在未核对字节数和 SHA256 前直接使用该文件。
