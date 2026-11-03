# 板卡相关文件逐项清单

扫描根目录：`F:\嵌赛`。优先级定义：P0＝架构/上板前必须；P1＝近期部署必须；P2＝按所选路径阅读；P3＝辅助工具或可替代资料。`必须阅读`表示团队是否应在相应阶段阅读/核验，并不表示当前机器已能完整打开加密归档。

`01_“复旦微”赛题解读` 与 `02_FMQL30TAI-悟净开发板获取途径` 当前为空目录，没有可审计文件。

## 板卡与竞赛资料

| 文件名 | 路径 | 文件类型 | 主要内容 | 涉及硬件 | 对当前项目的作用 | 必须阅读 | 优先级 |
|---|---|---|---|---|---|---|---|
| 悟净开发板硬件使用手册V1.0_嵌赛.pdf | `03_FMQL30TAI-悟净开发板手册\悟净开发板硬件使用手册V1.0_嵌赛.pdf` | PDF，41页 | 板卡配置、FMQL30TAI资源、DDR、时钟、引脚和全部外设 | FMQL30TAI、PS/PL/NPU、DDR、USB、GbE、GT | 本审计的板级主证据 | 是 | P0 |
| 悟净开发板硬件使用手册V1.0_嵌赛.pdf | `悟净开发板硬件使用手册V1.0_嵌赛.pdf` | PDF，41页 | 与上项提取文本一致；二进制大小/SHA不同 | 同上 | 重复备份；不作为第二份独立规格 | 否 | P3 |
| de2aca5a-535d-4288-aecd-aed3d0cf5841.pdf | `de2aca5a-535d-4288-aecd-aed3d0cf5841.pdf` | PDF，8页 | 2026竞赛平台、Lite板删件表、赛事任务/评分 | FMQL30TAI-悟净 Lite、ZG330、PL | 决定实际竞赛板接口边界，纠正完整版手册假设 | 是 | P0 |

## Icraft 3.36.1 与 30TAI 参考实现

| 文件名 | 路径 | 文件类型 | 主要内容 | 涉及硬件 | 对当前项目的作用 | 必须阅读 | 优先级 |
|---|---|---|---|---|---|---|---|
| fpai_demo_package_26040701.md5 | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+pHDMI(外置detpost)参考实现\25122301\runtimeapp\fpai_demo_package_26040701.md5` | 文本校验 | runtime ZIP 的 MD5/大小/时间；实测校验通过 | 30TAI runtime | 保证参考包完整 | 是 | P1 |
| fpai_demo_package_26040701.txt | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+pHDMI(外置detpost)参考实现\25122301\runtimeapp\fpai_demo_package_26040701.txt` | 文本说明 | 版本26040701、ZG、Icraft 3.36.0、AI-Mate 25122301、目录/编译入口 | ZG330/30TAI | 快速判断包用途和版本 | 是 | P1 |
| fpai_demo_package_26040701.zip | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+pHDMI(外置detpost)参考实现\25122301\runtimeapp\fpai_demo_package_26040701.zip` | ZIP，约313 MiB | Pipeline/Actor、BufferManager、XRT/XIR、PLIN+HDMI/AI C++示例 | PLIN、NPU、HDMI、DDR | 可复用 runtime 架构；包内文档对 30TAI HDMI 位流仍写 TODO | 是 | P0 |
| BOOT_25122301_单路PLIN+pHDMI(外置detpost).zip | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+pHDMI(外置detpost)参考实现\25122301\位流\BOOT_25122301_单路PLIN+pHDMI(外置detpost).zip` | ZIP | `BOOT.bin`、u-boot 等启动产物 | PLIN、HDMI、30TAI | 只能作既有视频位流启动参考，不能作为 RF 位流 | 按需 | P2 |
| fpai_demo_package_26040702.md5 | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+VPU编码_MIG_axi接口(外置detpost)参考实现\25122301\runtimeapp\fpai_demo_package_26040702.md5` | 文本校验 | runtime ZIP 的 MD5/大小/时间；实测校验通过 | 30TAI runtime | 保证参考包完整 | 是 | P1 |
| fpai_demo_package_26040702.txt | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+VPU编码_MIG_axi接口(外置detpost)参考实现\25122301\runtimeapp\fpai_demo_package_26040702.txt` | 文本说明 | 版本26040702、ZG、Icraft 3.36.0、AI-Mate 25122301 | ZG330/30TAI | 快速判断包用途；“用途”行误写为 HDMI，需以包内目录为准 | 是 | P1 |
| fpai_demo_package_26040702.zip | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+VPU编码_MIG_axi接口(外置detpost)参考实现\25122301\runtimeapp\fpai_demo_package_26040702.zip` | ZIP，约313 MiB | PLIN+VPU、MIG AXI、ZG330 `.json+.raw`、XRT Session/Tensor/BufferManager | PL、DDR/MIG、NPU、VPU | 当前最接近 PL→DDR→NPU 的软件参考，但仍是视频通路 | 是 | P0 |
| BOOT_25122301_单路PLIN+VPU编码_MIG_axi接口(外置detpost).zip | `04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\单路PLIN+VPU编码_MIG_axi接口(外置detpost)参考实现\25122301\位流\BOOT_25122301_单路PLIN+VPU编码_MIG_axi接口(外置detpost).zip` | ZIP | `BOOT.bin`、u-boot 等启动产物 | PLIN、PL DDR/MIG、VPU | 板到货后验证视频参考路径；不等同 RF DMA 工程 | 按需 | P2 |
| CustomOp_3.36.1_amd64.deb | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\CustomOp_3.36.1_amd64.deb` | Debian包 | amd64 自定义算子环境 | Icraft host | 只有需要自定义算子/旧版复现时使用 | 否 | P2 |
| CustomOp_3.36.1_onchip.deb | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\CustomOp_3.36.1_onchip.deb` | Debian包 | Ubuntu20.04 aarch64 板载自定义算子 | ZG330板载环境 | 旧版板端自定义算子支持 | 按需 | P2 |
| CustomOp_Setup_v3.36.1.exe | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\CustomOp_Setup_v3.36.1.exe` | Windows安装器 | Windows自定义算子工具 | Icraft host | 本模型不用自定义算子时非必需 | 否 | P3 |
| Icraft_3.36.1_amd64.deb | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\Icraft_3.36.1_amd64.deb` | Debian包 | Ubuntu20.04 amd64 交叉编译/转换 | ZG330工具链 | 复现260407参考包匹配环境 | 按需 | P1 |
| Icraft_3.36.1_onchip.deb | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\Icraft_3.36.1_onchip.deb` | Debian包 | Ubuntu20.04 aarch64 板载runtime | ZG330 | 参考工程所需旧版板载runtime | 按需 | P1 |
| Icraft_Setup_v3.36.1.exe | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\Icraft_Setup_v3.36.1.exe` | Windows安装器 | Windows Icraft 3.36.1 | NPU host工具链 | 用于严格复现旧参考包；新项目优先评估3.39 | 按需 | P2 |
| icraft-3.36.1-cp38-none-manylinux2014_aarch64.whl | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\icraft-3.36.1-cp38-none-manylinux2014_aarch64.whl` | Python wheel | Python3.8 aarch64 API | 板载ZG330 | Python板载控制旧版接口 | 按需 | P2 |
| icraft-3.36.1-cp38-none-manylinux2014_x86_64.whl | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\icraft-3.36.1-cp38-none-manylinux2014_x86_64.whl` | Python wheel | Python3.8 x86_64 API | host Icraft | host自动化/转换旧版接口 | 按需 | P2 |
| icraft-3.36.1-cp38-none-win_amd64.whl | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\icraft-3.36.1-cp38-none-win_amd64.whl` | Python wheel | Python3.8 Windows API | host Icraft | Windows自动化旧版接口 | 按需 | P2 |
| IcraftMdz_ThirdParty_v0.2.exe | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\IcraftMdz_ThirdParty_v0.2.exe` | Windows安装器 | ModelZoo第三方依赖 | host环境 | 仅运行相应modelzoo/demo时需要 | 否 | P3 |
| IcraftMdzThirdParty.deb | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\IcraftMdzThirdParty.deb` | Debian包 | ModelZoo第三方依赖 | Linux host/board | 仅运行相应modelzoo/demo时需要 | 否 | P3 |
| readme.md | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\readme.md` | Markdown | 九类安装包、平台、Python3.8限制、安装顺序 | Icraft 3.36.1 | 防止装错架构/版本 | 是 | P1 |
| tags_3.36.1.txt | `04_ICraft\v3.36.1\ICraft_V3.36.1安装包\tags_3.36.1.txt` | 文本 | 所有组件统一 tag v3.36.1 | Icraft组件 | 版本追踪 | 是 | P2 |

## Icraft 3.39.0

| 文件名 | 路径 | 文件类型 | 主要内容 | 涉及硬件 | 对当前项目的作用 | 必须阅读 | 优先级 |
|---|---|---|---|---|---|---|---|
| 30TAI&100TAI.zip | `04_ICraft\v3.39\icraft_v3.39.0\30TAI&100TAI.zip` | ZIP，约966 MiB | amd64/on-chip deb、cp38 wheels、ZG/通用解码库与组件版本 | 30TAI/100TAI、ZG330 | TimePowerPhase 首选正式转换/板载runtime包 | 是 | P0 |
| 30TAI&100TAI_win_python.zip | `04_ICraft\v3.39\icraft_v3.39.0\30TAI&100TAI_win_python.zip` | ZIP | Windows Python3.8 Icraft wheel | host | Windows API自动化 | 按需 | P2 |
| commit_id.ini | `04_ICraft\v3.39\icraft_v3.39.0\commit_id.ini` | INI | ZG330 backend、onnx/pytorch parser、quantizer、XIR/XRT等commit | Icraft 3.39 | 精确环境溯源及确认parser组件 | 是 | P0 |
| CustomOp_Setup_v3.39.0.exe | `04_ICraft\v3.39\icraft_v3.39.0\CustomOp_Setup_v3.39.0.exe` | Windows安装器 | 3.39自定义算子 | host | 当前模型标准算子优先，不必先装 | 否 | P3 |
| Icraft_Setup_v3.39.0.exe | `04_ICraft\v3.39\icraft_v3.39.0\Icraft_Setup_v3.39.0.exe` | Windows安装器，约1.70 GiB | Windows Icraft 3.39 | ZG330 host工具链 | 正式模型编译/量化/仿真候选 | 是 | P0 |
| IcraftMdz_ThirdParty_v0.2.exe | `04_ICraft\v3.39\icraft_v3.39.0\IcraftMdz_ThirdParty_v0.2.exe` | Windows安装器 | ModelZoo第三方依赖 | host | demo辅助 | 否 | P3 |
| IcraftMdzThirdParty.deb | `04_ICraft\v3.39\icraft_v3.39.0\IcraftMdzThirdParty.deb` | Debian包 | ModelZoo第三方依赖 | Linux | demo辅助 | 否 | P3 |
| readme.md | `04_ICraft\v3.39\icraft_v3.39.0\readme.md` | Markdown | 3.39安装矩阵；30/100TAI为Ubuntu20.04/cp38，400TAI为Ubuntu24.04/cp312 | Icraft/各TAI平台 | 决定正确安装包与Python版本 | 是 | P0 |
| tags_3.39.0.txt | `04_ICraft\v3.39\icraft_v3.39.0\tags_3.39.0.txt` | 文本 | 组件tag，XRT/hostbackend/server另有 `v3.39.0-wl` | Icraft组件 | 版本冻结与问题复现 | 是 | P1 |
| 开发教程.txt | `04_ICraft\开发教程.txt` | 文本链接 | 指向外部CSDN教程 | Icraft | 非离线权威资料，不能替代随包文档 | 否 | P3 |

## Procise、板载系统与交叉编译

| 文件名 | 路径 | 文件类型 | 主要内容 | 涉及硬件 | 对当前项目的作用 | 必须阅读 | 优先级 |
|---|---|---|---|---|---|---|---|
| FMSH_Procise_2025.1.1_temp_202603201420_32494.rar | `05_Procise\FMSH_Procise_2025.1.1_temp_202603201420_32494.rar` | 加密RAR，约769 MiB | Procise FPGA开发工具归档；用户已成功解出下项安装程序 | FMQL30TAI PL | 安装介质外层归档 | 按需 | P1 |
| FMSH_Procise_2025.1.1_temp_202603201420_32494.exe | `05_Procise\FMSH_Procise_2025.1.1_temp_202603201420_32494.exe` | 未签名PE32/Inno Setup，约767 MiB | 元数据确认 Fudan Micro Procise 2025.1.1 temp；尚未执行，内部器件库/IP/工程不可见 | FMQL30TAI PL | 后续安装、综合、实现、位流入口；运行前应校验可信哈希 | 是 | P0 |
| 解压密码.txt | `05_Procise\解压密码.txt` | 敏感文本 | Procise归档口令 | 工具安装 | 仅安装时本地使用；报告不记录其内容 | 按需 | P0 |
| icraft_v3_ubuntu20.04_aarch64_sd_image.7z | `06_板载Linux系统镜像\icraft_v3_ubuntu20.04_aarch64_sd_image.7z` | 7z，约3.92 GiB | 内含单个 `.bin` SD镜像 | 30TAI板载系统 | 板到货后基础系统与runtime启动 | 是 | P0 |
| imageUSB.exe | `06_板载Linux系统镜像\imageUSB.exe` | Windows可执行文件 | USB/SD镜像烧写工具 | TF/SD卡 | 烧写系统镜像 | 按需 | P2 |
| imageUSB烧写镜像说明.png | `06_板载Linux系统镜像\imageUSB烧写镜像说明.png` | PNG | imageUSB操作截图/说明 | TF/SD卡 | 防止烧错目标盘 | 是 | P2 |
| 系统登录.txt | `06_板载Linux系统镜像\系统登录.txt` | 敏感文本 | 板载系统登录信息 | Ubuntu系统 | 板到货后登录；报告不记录内容 | 是 | P0 |
| 因占用空间太大，不推荐此方式，请使用docker环境 | `07_交叉编译环境\01_VM虚拟机\因占用空间太大，不推荐此方式，请使用docker环境` | 空标记文件 | 明确不推荐VM，建议Docker | host编译环境 | 选择开发环境 | 是 | P2 |
| docker导入ubuntu20.04环境.PNG | `07_交叉编译环境\02_Docker镜像\docker导入ubuntu20.04环境.PNG` | PNG | Docker镜像导入操作截图 | host | 搭建离线交叉编译环境 | 是 | P1 |
| ubuntu20.04_container.tar | `07_交叉编译环境\02_Docker镜像\ubuntu20.04_container.tar` | Docker归档，约745 MiB | Ubuntu20.04交叉编译环境 | host/30TAI软件 | 编译参考runtime和板端应用的推荐环境 | 是 | P0 |

## 第三方工具、深度学习环境与分类示例

| 文件名 | 路径 | 文件类型 | 主要内容 | 涉及硬件 | 对当前项目的作用 | 必须阅读 | 优先级 |
|---|---|---|---|---|---|---|---|
| CP210x_Windows_Drivers.zip | `08_FMQL30TAI开发教程资料\01_第三方软件工具\01_串口驱动\CP210x_Windows_Drivers.zip` | ZIP | CP210x Windows串口驱动 | PS USB-UART CP2103GM | 串口bring-up与日志 | 是 | P1 |
| MobaXterm_Installer_v25.0.zip | `08_FMQL30TAI开发教程资料\01_第三方软件工具\02_MobaXterm\MobaXterm_Installer_v25.0.zip` | ZIP | SSH/SFTP/串口终端 | PS/Linux | 上传文件、远程调试，可替换 | 否 | P3 |
| Netron Setup 6.4.4.rar | `08_FMQL30TAI开发教程资料\01_第三方软件工具\03_Netron\Netron Setup 6.4.4.rar` | RAR | Netron模型可视化工具 | ONNX模型 | 检查部署图输入输出和算子 | 否 | P3 |
| cmake-3.31.6-linux-aarch64.tar.gz | `08_FMQL30TAI开发教程资料\01_第三方软件工具\04_Cmake\cmake-3.31.6-linux-aarch64.tar.gz` | tar.gz | aarch64 CMake | 400TAI板载环境 | 旁边标注仅400TAI；不要默认用于30TAI | 否 | P3 |
| 仅用于400tai板载系统安装.txt | `08_FMQL30TAI开发教程资料\01_第三方软件工具\04_Cmake\仅用于400tai板载系统安装.txt` | 空标记文件 | 限定上项用途为400TAI | 400TAI | 防止平台误用 | 是 | P2 |
| charset_normalizer-3.1.0-...aarch64.whl | `08_FMQL30TAI开发教程资料\02_深度学习环境搭建\ubuntu20.04-aarch64\charset_normalizer-3.1.0-cp38-cp38-manylinux_2_17_aarch64.manylinux2014_aarch64.whl` | Python wheel | 教程中修复 yolov5_axi.py 环境问题 | aarch64板载Python | 只在对应demo报错时使用 | 否 | P3 |
| torch_v2.0.1_aarch64.zip | `08_FMQL30TAI开发教程资料\02_深度学习环境搭建\ubuntu20.04-aarch64\torch_v2.0.1_aarch64.zip` | ZIP，约402 MiB | Python3.8/PyTorch2.0.1 aarch64离线环境 | 30TAI Linux | 板端Python smoke/对照；正式C++ runtime不一定依赖 | 按需 | P1 |
| torch_v2.0.1.7z | `08_FMQL30TAI开发教程资料\02_深度学习环境搭建\windows\torch_v2.0.1.7z` | 7z，约466 MiB | Windows Python3.8/PyTorch2.0.1环境 | host | 复现Icraft脚本环境 | 按需 | P2 |
| 深度学习环境搭建指导手册.pdf | `08_FMQL30TAI开发教程资料\02_深度学习环境搭建\深度学习环境搭建指导手册.pdf` | PDF，13页 | Windows/Ubuntu20.04-aarch64、Python3.8、Torch2.0.1、Icraft板载安装 | host、30TAI Linux/NPU | 环境搭建和版本约束主文档 | 是 | P0 |
| image_cls_resnet18.zip | `08_FMQL30TAI开发教程资料\03_图像分类部署示例工程\image_cls_resnet18.zip` | ZIP，约338 MiB | 五类花数据、ResNet18 pth/TorchScript/ONNX、推理与ftmp脚本 | Icraft/NPU | 证明ONNX工作流和Icraft校准数据布局；不是完整RF部署例程 | 是 | P1 |

## 完整性与已知文档问题

- 两份硬件手册 PDF 的文本 SHA-256 相同，二进制 SHA-256 分别为 `C50D3C99...CFF93` 与 `6F2D8080...D87A`；视为内容重复、副本编码不同。
- `fpai_demo_package_26040701.zip` 与 `26040702.zip` 的实际 MD5 分别与随附清单完全一致。
- `26040702.txt` 的“用途”行仍写 `PLIN+pHDMI`，但目录、包内 README 和示例均为 PLIN+VPU；这是随附说明不一致。
- `26040701` 的部分包内 README 标题/正文也出现 HDMI/VPU 混写，且 30TAI 对应位流处写 TODO；不能把它当作成熟的 30TAI HDMI 集成证据。
- Procise RAR 已由用户解出单个安装程序。安装程序元数据已审计，但未执行，因此内部器件库、IP catalog、文档和工程模板仍未审计；这还不是“Procise 内容已完整审计”。
- Procise EXE 的 SHA-256 为 `BF04E66431EAA59EAB860BC56D9D97E0993F84011527FEE707F3450A7B8FA8F6`，Windows Authenticode 状态为 `NotSigned`。
- 登录与解压口令文件仅确认存在，没有在报告中复述敏感内容。
