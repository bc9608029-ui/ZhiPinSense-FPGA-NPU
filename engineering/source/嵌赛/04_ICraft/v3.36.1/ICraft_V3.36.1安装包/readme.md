# Icraft自述文件

## 安装与卸载

Icraft目前提供以下九个安装包

### Icraft_Setup_v3.36.1.exe

Icraft安装包Windows10版，直接双击即可安装

安装目录在C:\Icraft，不可修改

安装目录下有卸载程序uninst.exe

#### Icraft_3.36.1_amd64.deb（在amd64上交叉编译arm64需要此安装包）

Icraft安装包Ubuntu20.04-amd64版

安装命令：`sudo dpkg -i Icraft_3.36.1_amd64.deb`

卸载命令：`dpkg -r Icraft`

#### Icraft_3.36.1_arm64.deb

Icraft安装包Ubuntu20.04-aarch64版

安装命令：`sudo dpkg -i Icraft_3.36.1_arm64.deb`

卸载命令：`dpkg -r Icraft`

#### CustomOp_Setup_v3.36.1.exe（自定义算子，可选）

CustomOp安装包Windows10版，，直接双击即可安装

务必先安装Icraft_Setup_v3.36.1.exe再安装本程序

安装目录在C:\Icraft\CustomOp_v3.36.1，不可修改

安装目录下有卸载程序uninst.exe

#### CustomOp_3.36.1_amd64.deb（自定义算子，可选）

CustomOp安装包Ubuntu20.04-amd64版

务必先安装IIcraft_3.36.1_amd64.deb再安装本程序

安装命令：`sudo dpkg -i CustomOp_3.36.1_amd64.deb`

卸载命令：`dpkg -r CustomOp`

#### CustomOp_3.36.1_arm64.deb（自定义算子，可选）

CustomOp安装包Ubuntu20.04-aarch64版

务必先安装IIcraft_3.36.1_arm64.deb再安装本程序

安装命令：`sudo dpkg -i CustomOp_3.36.1_arm64.deb`

卸载命令：`dpkg -r CustomOp`

#### icraft-3.36.1-cp38-none-win_amd64.whl（pythonAPI，可选）

Icraft pythonAPI Windows10版，仅支持python38

务必先安装Icraft_Setup_v3.36.1.exe再安装本程序

安装命令：`pip install icraft-3.36.1-cp38-none-win_amd64.whl`

卸载命令：`pip uninstall icraft`

#### icraft-3.36.1-cp38-none-manylinux2014_x86_64.whl（pythonAPI，可选）

Icraft pythonAPI Ubuntu20.04-amd64版，仅支持python38

务必先安装IIcraft_3.36.1_amd64.deb再安装本程序

安装命令：`pip install icraft-3.36.1-cp38-none-manylinux2014_x86_64.whl`

卸载命令：`pip uninstall icraft`

#### icraft-3.36.1-cp38-none-manylinux2014_aarch64whl（pythonAPI，可选）

Icraft pythonAPI Ubuntu20.04-aarch64版，仅支持python38

务必先安装IIcraft_3.36.1_arm64.deb再安装本程序

安装命令：`pip install icraft-3.36.1-cp38-none-manylinux2014_aarch64.whl`

卸载命令：`pip uninstall icraft`



## 使用方法

在`Windows`下安装完成后，使用命令`icraft docs`即可打开完整文档

## HostFix

v3.36.1 1、hostbackend支持在axi下qwen的前向；2、hostbackend的matmul去掉使用GPU；3、detpostzg修复fp16的下界值；