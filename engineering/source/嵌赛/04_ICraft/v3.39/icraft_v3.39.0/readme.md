# Icraft自述文件

## 安装与卸载

Icraft目前提供以下安装包

### Icraft_Setup_v3.39.0.exe

Icraft安装包Windows10版，直接双击即可安装

安装目录在C:\Icraft，不可修改

安装目录下有卸载程序uninst.exe

#### 30TAI&100TAI/Icraft_3.39.0_amd64.deb（在amd64上交叉编译arm64需要此安装包）

Icraft安装包Ubuntu20.04-amd64版

安装命令：`sudo dpkg -i Icraft_3.39.0_amd64.deb`

卸载命令：`dpkg -r Icraft`

#### 30TAI&100TAI/Icraft_3.39.0_onchip.deb

Icraft安装包Ubuntu20.04-aarch64版

安装命令：`sudo dpkg -i Icraft_3.39.0_onchip.deb`

卸载命令：`dpkg -r Icraft`

#### 400TAI/Icraft_3.39.0_onchip.deb

Icraft安装包Ubuntu24.04-aarch64版

安装命令：`sudo dpkg -i Icraft_3.39.0_onchip.deb`

卸载命令：`dpkg -r Icraft`

#### CustomOp_Setup_v3.39.0.exe（自定义算子，可选）

CustomOp安装包Windows10版，，直接双击即可安装

务必先安装Icraft_Setup_v3.39.0.exe再安装本程序

安装目录在C:\Icraft\CustomOp_v3.39.0，不可修改

安装目录下有卸载程序uninst.exe

#### 30TAI&100TAI/CustomOp_3.39.0_amd64.deb（自定义算子，可选）

CustomOp安装包Ubuntu20.04-amd64版

务必先安装Icraft_3.39.0_amd64.deb再安装本程序

安装命令：`sudo dpkg -i CustomOp_3.39.0_amd64.deb`

卸载命令：`dpkg -r CustomOp`

#### 30TAI&100TAI/CustomOp_3.39.0_onchip.deb（自定义算子，可选）

CustomOp安装包Ubuntu20.04-aarch64版

务必先安装Icraft_3.39.0_onchip.deb再安装本程序

安装命令：`sudo dpkg -i CustomOp_3.39.0_onchip.deb`

卸载命令：`dpkg -r CustomOp`

#### 30TAI&100TAI_win_python/icraft-3.39.0-cp38-none-win_amd64.whl（pythonAPI，可选）

Icraft pythonAPI Windows10版，仅支持python38

务必先安装Icraft_Setup_v3.39.0.exe再安装本程序

安装命令：`pip install icraft-3.39.0-cp38-none-win_amd64.whl`

卸载命令：`pip uninstall icraft`

#### 400TAI_win_python/icraft-3.39.0-cp38-none-win_amd64.whl（pythonAPI，可选）

Icraft pythonAPI Windows10版，仅支持python38

务必先安装Icraft_Setup_v3.39.0.exe再安装本程序

安装命令：`pip install icraft-3.39.0-cp38-none-win_amd64.whl`

卸载命令：`pip uninstall icraft`

#### 30TAI&100TAI/icraft-3.39.0-cp38-none-manylinux2014_x86_64.whl（pythonAPI，可选）

Icraft pythonAPI Ubuntu20.04-amd64版，仅支持python38

务必先安装Icraft_3.39.0_amd64.deb再安装本程序

安装命令：`pip install icraft-3.39.0-cp38-none-manylinux2014_x86_64.whl`

卸载命令：`pip uninstall icraft`

#### 30TAI&100TAI/icraft-3.39.0-cp38-none-manylinux2014_aarch64whl（pythonAPI，可选）

Icraft pythonAPI Ubuntu20.04-aarch64版，仅支持python38

务必先安装Icraft_3.39.0_arm64.deb再安装本程序

安装命令：`pip install icraft-3.39.0-cp38-none-manylinux2014_aarch64.whl`

卸载命令：`pip uninstall icraft`

#### 400TAI/icraft-3.39.0-cp312-none-manylinux2014_aarch64whl（pythonAPI，可选）

Icraft pythonAPI Ubuntu24.04-aarch64版，仅支持python312

务必先安装Icraft_3.39.0_arm64.deb再安装本程序

安装命令：`pip install icraft-3.39.0-cp312-none-manylinux2014_aarch64.whl`

卸载命令：`pip uninstall icraft`



## 使用方法

在`Windows`下安装完成后，使用命令`icraft docs`即可打开完整文档
