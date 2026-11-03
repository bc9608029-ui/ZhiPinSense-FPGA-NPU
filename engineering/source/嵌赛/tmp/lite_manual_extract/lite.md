悟净开发板 Lite（轻量版）硬件使用手册

深圳市创芯瑞天科技有限公司

（V1.0 · Lite 轻量版）

# 目录

[1 开发板简介 4](#_Toc218710395)

[2 开发板硬件配置 5](#_Toc218710396)

[3 开发板实物图示 6](#_Toc218710397)

[4 开发板功能描述 7](#_Toc218710398)

[4.1 JFMQL30TAI676H芯片概述 7](#_Toc218710399)

[4.2 配置加载模式 10](#_Toc218710400)

[4.3 PS DDR3 13](#_Toc218710401)

[4.4 PL DDR3 14](#_Toc218710402)

[4.5 时钟管理 15](#_Toc218710403)

[4.6 QSPI Flash 17](#_Toc218710404)

[4.7 JTAG接口 18](#_Toc218710405)

[4.8 以太网接口 19](#_Toc218710406)

[4.9 SD卡 22](#_Toc218710407)

[4.10 串口 25](#_Toc218710409)

[4.11 LED 27](#_Toc218710410)

[4.12 按键 28](#_Toc218710411)

[4.13 USB接口 31](#_Toc218710414)

[4.14 SFP接口 35](#_Toc218710417)

[4.15 PCIE接口 37](#_Toc218710418)

[4.16 HDMI输出接口 39](#_Toc218710419)

[4.17 SDI接口 40](#_Toc218710420)

[4.18 HEADER 14X2接口 41](#_Toc218710421)

[4.19 MIPI接口 42](#_Toc218710423)

[4.20 XADC 43](#_Toc218710424)

[4.21 电源管理 45](#_Toc218710421)

[5 开发板原理图 42](#_Toc218710422)

**用户须知—使用必看**

开发板使用人员：

您好！感谢使用复旦微悟净 PSOC
Lite开发板，为避免在开发过程中遇到问题，请您在使用前阅读以下几点内容：

1.  复旦微悟净Lite开发板使用手册所有的参数说明来自于开发板原理图，如有疑问请查看原理图或者联系我司销售、技术支持。

2.  复旦微悟净Lite开发板使用的是适配器AC\~220V转DC-12V供电，使用过程中，防止触电。

3.  请不要对复旦微悟净Lite开发板上的元器件进行改动或者焊接，如有必要，请联系我司技术支持。

4.  未联系我司技术支持，对开发板进行改动，造成开发板损坏或者功能异常，须使用者自行承担，我司将不予赔付。

> 深圳市创芯瑞天科技有限公司

1.  <span id="_Toc218710395" class="anchor"></span>开发板简介

悟净Lite（轻量版）开发板是基于复旦微电子PSOC系列高端芯片JFMQL30TAI676H开发的平台产品。

主要特色：

1.  国产化器件比例90%以上

> 开发板上的主要芯片，其中包括电源模块、PSOC芯片、DDR、Flash和外围接口芯片等，全部采购于国内芯片厂商。可以为客户的方案设计和项目开发提供了参考。

2）板卡设计紧凑

整板尺寸：202 (mm) x 150 (mm)

3）板上资源丰富

主芯片：JFMQL30TAI676H

PS DDR：1GB DDR3 PL DDR：2GB DDR3

高性能接口：

-   USB Uart

    -   USB2.0

    -   千兆以太网

    -   SFP

    -   HDMI

    -   PCIe x1

    -   SD Card

    -   SDI

4）Demo丰富：

为用户提供FPGA开发、ARM裸跑开发、Linux开发、HLS开发、Vxworks开发等一系列教程，帮助客户加速产品设计开发。

2.  <span id="_Toc218710396" class="anchor"></span>开发板硬件配置

> 悟净开发板Lite（轻量版）的主要配置列表如下

<table>
<thead>
<tr class="header">
<th>名称</th>
<th>具体参数</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td>PSOC</td>
<td>JFMQL30TAI676H<br />
4核CPU<br />
Programmable-Logic</td>
</tr>
<tr class="even">
<td>PS侧 DDR3</td>
<td>1GB DDR3</td>
</tr>
<tr class="odd">
<td>PL侧 DDR3</td>
<td>2GB DDR3</td>
</tr>
<tr class="even">
<td>FLASH</td>
<td>一片 256Mb QSPI FLASH(QSPI0)</td>
</tr>
<tr class="odd">
<td>时钟管理</td>
<td>PS侧50MHz、PL侧200MHz</td>
</tr>
<tr class="even">
<td>以太网</td>
<td>1路10/100/1000Mbps 以太网（PS端）</td>
</tr>
<tr class="odd">
<td>USB2.0</td>
<td>4路USB2.0</td>
</tr>
<tr class="even">
<td>USB UART</td>
<td>1路USB UART</td>
</tr>
<tr class="odd">
<td>PCIe</td>
<td>1路PCIe x1</td>
</tr>
<tr class="even">
<td>SFP</td>
<td>1路SFP光纤通信（SFP0可用）</td>
</tr>
<tr class="odd">
<td>SDI</td>
<td>2路SDI输入</td>
</tr>
<tr class="even">
<td>HDMI</td>
<td>一路HDMI输出</td>
</tr>
<tr class="odd">
<td>TF-CARD</td>
<td>32GB TF-CARD</td>
</tr>
<tr class="even">
<td>XADC</td>
<td>5路XADC接口</td>
</tr>
<tr class="odd">
<td>LED</td>
<td>1路PS MIO LED、4路 PL LED</td>
</tr>
<tr class="even">
<td>KEY</td>
<td>1路PS MIO KEY、2路 PL KEY</td>
</tr>
<tr class="odd">
<td>HEADER</td>
<td>PL端16路通过GPIO接口</td>
</tr>
<tr class="even">
<td>JTAG</td>
<td>1路PS_JTAG、1路PL_JTAG</td>
</tr>
</tbody>
</table>

> <span id="_Toc218710397" class="anchor"></span>

3.  开发板实物图示

悟净Lite开发板采用了单板设计模式，整板元器件密度高，外设种类多，应用功能丰富，客户可以根据项目需求，在开发板上验证所需功能，缩短开发周期，提升产品性能。

开发板实物图示如图3-1所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image1.png" style="width:5.76806in;height:3.42377in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\RWTemp\2026-09\6422ca9bc4639cf9536389d4821520d4.png" />

4.  <span id="_Toc218710398" class="anchor"></span>开发板功能描述

<!-- -->

1.  <span id="_Toc218710399"
    class="anchor"></span>JFMQL30TAI676H芯片概述

PSOC 悟净Lite开发板搭载了一颗复旦微的PSOC片上可编程系列芯片
JFMQL30TAI676H

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image2.png" style="width:5.76806in;height:5.2875in" />

> 图4-1

JFMQL30TAI676H集成了四核ARM
Cortex-A53的处理器和片上可编程逻辑资源，对标Xilinx的XC7Z030FFG676-2I芯片，同时具备了硬件编程和软件编程的功能，PS和PL资源列表如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image3.png" style="width:5.76806in;height:5.5125in" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image4.png" style="width:5.76806in;height:1.67222in" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image5.png" style="width:5.76806in;height:0.49653in" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image6.png" style="width:5.76806in;height:0.96458in" />

产品的封装信息和IO信息如下表所示

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image7.png" style="width:5.76806in;height:1.89722in" />

2.  <span id="_Toc218710400" class="anchor"></span>配置加载模式

PSOC 悟净Lite开发板上支持多种加载启动设备，其中包括JTAG启动加载、QSPI
Flash加载加载和SD卡加载，加载方式的选择通过跳线帽来选，如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image8.png" style="width:5.76806in;height:4.34722in" />

MIO2的上下拉配置决定了JFMQL30TAI676H开发模式是级联模式还是独立模式；MIO3\~MIO5的组合配置决定了JFMQL30TAI676H的启动加载模式；MIO6的上下拉配置决定了PLL是否Bypass；MIO7/MIO8的上下拉配置决定了Bank500和Bank501的电压配置；

具体的模式配置和选型如下表所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image9.png" style="width:5.76806in;height:2.89792in" />

PCB和实物的跳线帽配置选择如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image10.png" style="width:5.76806in;height:1.57778in" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image11.png" style="width:5.76806in;height:3.17986in" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image12.png" style="width:5.41667in;height:3.7in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\12efc5b0-9915-4710-99d9-27e5ec155637.png" />

3.  <span id="_Toc218710401" class="anchor"></span>PS DDR3

PSOC 悟净Lite开发板PS侧内存接口搭载了复旦微（Fudan
Micro）的DDR3内存颗粒，单片DDR颗粒大小是4Gb，数据接口是16bit，开发板采用了Fly-By的拓扑结构，部署了共1GB空间大小的PS内存空间，内存颗粒主频高达1600MHz，数据带宽可达1600MHz\*32bit，DDR3接口原理图如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image14.png" style="width:5.76806in;height:2.96181in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\09baa3ba-5b2c-4216-a824-ca5f9a11639c.png" />

4.  <span id="_Toc218710402" class="anchor"></span>PL DDR3

PSOC 悟净Lite开发板PL侧内存接口搭载了复旦微（Fudan
Micro）的DDR3内存颗粒，单片DDR颗粒大小是4Gb，数据接口是16bit，开发板采用了Fly-By的拓扑结构，部署了共2GB空间大小的PL内存空间，内存颗粒主频高达1600MHz，数据带宽可达1600MHz\*64bit，DDR3接口原理图如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image16.png" style="width:5.76806in;height:3.26667in" />

5.  <span id="_Toc218710403" class="anchor"></span>时钟管理

PSOC
悟净Lite开发板搭载了不同频率的时钟源，包括PS主时钟、固定频率50MHz的晶振、固定频率100MHz的晶振、DDR的外部200MHz时钟等。注意PS的时钟需要50M时钟，不能使用33.333M的时钟。

时钟原理图如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image17.png" style="width:5.42366in;height:1.7402in" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image18.png" style="width:5.382in;height:3.68628in" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image19.png" style="width:5.76806in;height:2.08403in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\RWTemp\2026-09\ae58672dad99c8d99d7288cb6a866194.png" />

6.  <span id="_Toc218710404" class="anchor"></span>QSPI Flash

PSOC 悟净Lite开发板PS侧搭载了复旦微（Fudan Micro）的QSPI
Flash，型号为EFM25QL256-E16。可用来存储Boot加载的代码镜像和用户数据。

EFM25QL256-E16主要技术参数：

1.  容量256Mbit

2.  x1/x2/x4支持

3.  工作电压3V\~3.6V

4.  温度范围：-55℃\~ 125℃

QSPI原理图如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image20.png" style="width:5.76806in;height:1.95485in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\973766e9-3c83-4709-b9d9-5816ff6f1a72.png" />

7.  <span id="_Toc218710405" class="anchor"></span>JTAG接口

悟净Lite开发板的 JTAG 接口用于下载 FPGA 程序或者固化程序到
FLASH。为了方便用户调试， 开发板上共留有 2 个 JTAG 接口，其中 PS 端的
EMIO\_JTAG 接口是一个 20pin 的插座 U18， PL 端 JTAG 接口也是一个 20pin
的插座
U19。采用相同的接口，方便使用J-Link或者I-Jet进行级联模式下的调试。在独立模式下，开发板都配备了一个转接板。PS
端 JTAG 接口的原理图如图所示， PL 端 JTAG 接口的原理图如图所示。

EMIO引出的PJTAG接口连接如下表所示：

| 信号名称    | JFMQL30TAI676H引脚名   | JFMQL30TAI676H引脚号 |
|-------------|------------------------|----------------------|
| Z7\_PS\_TDO | IO\_L15P\_T2\_DQS\_12  | AD16                 |
| Z7\_PS\_TCK | IO\_L14P\_T2\_SRCC\_12 | AB15                 |
| Z7\_PS\_TMS | IO\_L14N\_T2\_SRCC\_12 | AB14                 |
| Z7\_PS\_TDI | IO\_L15N\_T2\_DQS\_12  | AD15                 |

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image21.png" style="width:4.78922in;height:2.04865in" />

8.  <span id="_Toc218710406" class="anchor"></span>以太网接口

开发板采用裕太微的YT8521以太网PHY芯片，实现10/100/1000Mpbs自适应以太网接口，连接至JFMQL30TAI676H的PS端

PS 端以太网PHY芯片与JFMQL30TAI676H的连接关系如下表所示:

| 信号名称      | JFMQL30TAI676H引脚名 | JFMQL30TAI676H引脚号 | 备注             |
|---------------|----------------------|----------------------|------------------|
| PHY\_TX\_CLK  | PS\_MIO16\_501       | G21                  | RGMII 发送时钟   |
| PHY\_TX\_CTRL | PS\_MIO21\_501       | F22                  | 发送使能信号     |
| PHY\_TXD0     | PS\_MIO17\_501       | G17                  | 发送数据 bit0    |
| PHY\_TXD1     | PS\_MIO18\_501       | G20                  | 发送数据 bit1    |
| PHY\_TXD2     | PS\_MIO19\_501       | G19                  | 发送数据 bit2    |
| PHY\_TXD3     | PS\_MIO20\_501       | H19                  | 发送数据 bit3    |
| PHY\_RX\_CLK  | PS\_MIO22\_501       | G22                  | RGMII 接收时钟   |
| PHY\_RX\_CTRL | PS\_MIO27\_501       | F18                  | 接收数据有效信号 |
| PHY\_RXD0     | PS\_MIO23\_501       | F20                  | 接收数据 bit0    |
| PHY\_RXD1     | PS\_MIO24\_501       | J19                  | 接收数据 bit1    |
| PHY\_RXD2     | PS\_MIO25\_501       | F19                  | 接收数据 bit2    |
| PHY\_RXD3     | PS\_MIO26\_501       | H17                  | 接收数据 bit3    |
| PHY\_MDC      | PS\_MIO52\_501       | A20                  | MDIO 管理时钟    |
| PHY\_MDIO     | PS\_MIO53\_501       | A19                  | MDIO 管理数据    |
| PHY\_RESET    | IO\_0\_ 12           | W14                  | PS PHY复位信号   |

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image22.png" style="width:5.76806in;height:2.35903in" />

9.  <span id="_Toc218710407" class="anchor"></span>SD卡

悟净Lite开发板包含了一个Micro型的SD卡接口，以提供用户访问SD卡存储器，用于存储PSOC芯片的BOOT程序，Linux操作系统内核,
文件系统以及其它的用户数据文件。SDIO信号与PSOC的PS的BANK501的IO信号相连，因为该BANK的VCCIO设置为1.8V，但SD卡的数据电平为3.3V,
我们这里通过TXS02612电平转换器来连接。特别注意CD信号的电平也为3.3V，如果跟PSOC的CD信号相连时，也需要经过电平转换。

| 信号名称 | JFMQL30TAI676H引脚名 | JFMQL30TAI676H引脚号 | 备注         |
|----------|----------------------|----------------------|--------------|
| SD\_CLK  | PS\_MIO40            | C22                  | SD时钟信号   |
| SD\_CMD  | PS\_MIO41            | C19                  | SD命令信号   |
| SD\_D0   | PS\_MIO42            | F17                  | SD数据Data0  |
| SD\_D1   | PS\_MIO43            | D18                  | SD数据Data1  |
| SD\_D2   | PS\_MIO44            | E18                  | SD数据Data2  |
| SD\_D3   | PS\_MIO45            | C18                  | SD数据Data3  |
| SD\_CD   | PS\_MIO46            | E17                  | SD卡插入信号 |

SD卡的原理图如下：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image23.png" style="width:5.76806in;height:3.95417in" />

10. <span id="_Toc218710409" class="anchor"></span>串口

> 悟净Lite开发板上配备了一个 Uart 转 USB
> 接口，连接PSOC的PS端。PS端的转换芯片采用Silicon Labs CP2103GM 的
> USB-UAR 芯片, USB 接口采用 MINI USB 接口，可以用一根 USB线将它连接到上
> PC 的 USB 口进行串口数据通信 。

PS端的引脚连接关系如下：

| 信号名称          | JFMQL30TAI676H引脚名 | JFMQL30TAI676H引脚号 | 备注         |
|-------------------|----------------------|----------------------|--------------|
| USB\_UART\_PS\_RX | PS\_MIO50\_501       | B22                  | UART数据输入 |
| USB\_UART\_PS\_TX | PS\_MIO51\_500       | B20                  | UART数据输出 |

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image24.png" style="width:5.75972in;height:2.36806in" />

11. <span id="_Toc218710410" class="anchor"></span>LED

> 悟净Lite开发板上有 5 个 LED， 1 路 PS 端 LED，4路 PL 端 LED。

| 信号名称 | JFMQL30TAI676H引脚号 |
|----------|----------------------|
| PS\_MIO7 | E23                  |
| PL\_LED1 | J1                   |
| PL\_LED2 | M6                   |
| PL\_LED3 | H7                   |
| PL\_LED4 | J8                   |

> <img src="F:\嵌赛\tmp\lite_manual_extract\media\image25.png" style="width:5.76806in;height:2.75486in" />
>
> <img src="F:\嵌赛\tmp\lite_manual_extract\media\image26.png" style="width:5.76806in;height:2.44167in" />

12. <span id="_Toc218710411" class="anchor"></span>按键

> 在功能底板上有 4 个按键， 1路复位按键， 1路 MIO 按键， 2路 PL 按键。

| 信号名称 | JFMQL30TAI676H引脚名   | JFMQL30TAI676H引脚号 |
|----------|------------------------|----------------------|
| PS\_KEY  | PS\_MIO47\_501         | B19                  |
| PL\_KEY1 | IO\_L11P\_T1\_SRCC\_34 | F8                   |
| PL\_KEY2 | IO\_L11N\_T1\_SRCC\_34 | E7                   |

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image27.png" style="width:5.76806in;height:2.14444in" />

> <img src="F:\嵌赛\tmp\lite_manual_extract\media\image28.png" style="width:5.76806in;height:3.93958in" />

13. <span id="_Toc218710414" class="anchor"></span>USB接口

悟净Lite开发板上有4个USB2.0
HOST接口，USB2.0收发器采用的是一个1.8V的，高速的支持ULPI标准接口的USB3320C-EZK芯片，再通过一个USB
HUB芯片USB2514扩展出4路USB
HOST接口。PSOC的USB总线接口和USB3320C-EZK收发器相连接，实现高速的USB2.0Host模式的数据通信。USB3320C的USB的数据和控制信号连接到PSOC芯片PS端的BANK501的IO口上，
USB接口差分信号(DP/DM)连接到USB2514芯片扩展出4个USB接口。2个24MHz的晶振为分别为USB3320C和USB2514芯片提供时钟。4
个 USB 接口为扁型 USB 接口(USB Type A)， 方便用户同时连接不同的 USB
Slave 外设(比如 USB 鼠标和 USB 键盘），每个 USB 接口提供了+5V 的电源。

USB2.0引脚分配：

| 信号名称    | JFMQL100TAI引脚名 | 备注             |
|-------------|-------------------|------------------|
| OTG\_DATA4  | PS\_MIO28\_501    | USB 数据 Bit4    |
| OTG\_DIR    | PS\_MIO29\_501    | USB 数据方向信号 |
| OTG\_STP    | PS\_MIO30\_501    | USB 停止信号     |
| OTG\_NXT    | PS\_MIO31\_501    | USB 下一数据信号 |
| OTG\_DATA0  | PS\_MIO32\_501    | USB 数据 Bit0    |
| OTG\_DATA1  | PS\_MIO33\_501    | USB 数据 Bit1    |
| OTG\_DATA2  | PS\_MIO34\_501    | USB 数据 Bit2    |
| OTG\_DATA3  | PS\_MIO35\_501    | USB 数据 Bit3    |
| OTG\_CLK    | PS\_MIO36\_501    | USB 时钟信号     |
| OTG\_DATA5  | PS\_MIO37\_501    | USB 数据 Bit5    |
| OTG\_DATA6  | PS\_MIO38\_501    | USB 数据 Bit6    |
| OTG\_DATA7  | PS\_MIO39\_501    | USB 数据 Bit7    |
| OTG\_RESETN | PS\_MIO8\_500     | USB 复位信号     |

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image29.png" style="width:5.76806in;height:2.73472in" />

14. <span id="_Toc218710417" class="anchor"></span>SFP接口

Demo
板提供SFP光接口，用户可插入SFP光模块实现光纤通信。SFP光模块接口的原理图如下图所示。SFP模块默认配置为全速率（Full
BW）模式。

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image30.png" style="width:5.76806in;height:1.86842in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\96b5e822-2b3f-4c98-b682-3fb49c39065e.png" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image31.png" style="width:5.76806in;height:1.263in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\73ad146e-e142-4447-941d-603a9c514588.png" />

15. <span id="_Toc218710418" class="anchor"></span>PCIE接口

PSOC 悟净Lite开发板集成了高速PCIE x1接口，接口形式采用金手指。

电路原理图如下图所示。

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image31.png" style="width:5.76806in;height:1.2625in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\73ad146e-e142-4447-941d-603a9c514588.png" />

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image32.png" style="width:5.76806in;height:1.69722in" />

16. <span id="_Toc218710419" class="anchor"></span>HDMI输出接口

HDMI 输出采用了IO模HDMI信号，输出可以达到720P@60HZ
高清传输。实测1080P@60HZ的信号输出，有的显示器会存在闪屏的情况。因为在运行1080P@60HZ的时候，HR的bank的时钟运行在748.5M的TMDS速率，超出了手册HR的bank的IO的最高710M的速率要求。

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image33.png" style="width:5.76806in;height:3.16736in" />

17. <span id="_Toc218710420" class="anchor"></span>SDI接口

悟净Lite开发板支持两路SDI输入接口。

LMH0344自适应电缆均衡器设计用于均衡通过电缆（或具有类似色散损耗特性的任何介质）传输的3-Gbps、HD-SD的SDI数据。均衡器工作在从125
Mbps到2.97 Gbps的宽数据速率范围内，支持ST424、ST292、ST344和ST259。

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image34.png" style="width:5.76806in;height:4.74374in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\4fba54c7-1c38-464a-b9a4-f0d60c11bf4a.png" />

18. HEADER 14X2接口

PSOC
悟净Lite开发板集成了可测试接口，接口形式采用2.54MM的插针接口。其中包含了4根3.3V的GPIO接口，12根1.8V的GPIO接口，用户可以根据自己的需求进行测试。

电路原理图如下图所示。

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image35.png" style="width:5.76806in;height:3.49722in" />

19. <span id="_Toc218710423" class="anchor"></span>MIPI接口

悟净Lite开发板提供了一个MIPI
CSI摄像头接口J16（SFW15R-1STE1LF），包含2路数据LANE和1路时钟LANE，连接到JFMQL30TAI676H的PL端BANK12（IO电平1.8V）。接口同时引出CAM\_GPIO、CAM\_SCL（I2C时钟）、CAM\_SDA（I2C数据）控制信号，其中CAM\_SCL/CAM\_SDA上拉至3.3V。电路为LP（Low
Power）模式和HS（High
Speed）模式分别预留了100Ω和150Ω匹配电阻网络，用户可根据摄像头模组的工作模式选择焊接。

MIPI接口引脚与JFMQL30TAI676H的连接关系如下表所示：

| 信号名称       | JFMQL30TAI676H引脚名   | JFMQL30TAI676H引脚号 | 备注        |
|----------------|------------------------|----------------------|-------------|
| MIPI\_LANE0\_P | IO\_L1P\_T0\_12        | Y12                  | 数据Lane0正 |
| MIPI\_LANE0\_N | IO\_L1N\_T0\_12        | Y11                  | 数据Lane0负 |
| MIPI\_LANE1\_P | IO\_L2P\_T0\_12        | Y10                  | 数据Lane1正 |
| MIPI\_LANE1\_N | IO\_L2N\_T0\_12        | AA10                 | 数据Lane1负 |
| MIPI\_CLK\_P   | IO\_L12P\_T1\_MRCC\_12 | AC13                 | 时钟正      |
| MIPI\_CLK\_N   | IO\_L12N\_T1\_MRCC\_12 | AD13                 | 时钟负      |
| CAM\_GPIO      | IO\_L17N\_T2\_12       | AE15                 | CAM GPIO    |
| CAM\_SCL       | IO\_L18P\_T2\_12       | AE17                 | I2C时钟     |
| CAM\_SDA       | IO\_L18N\_T2\_12       | AF17                 | I2C数据     |
| CAM\_CLK       | IO\_L19P\_T3\_12       | Y17                  | CAM CLK     |

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image36.png" style="width:3.33333in;height:3.53in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\3d70711d-ad33-4e9d-8208-45a207722b49.png" />

MIPI接口原理图如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image37.png" style="width:5.76806in;height:9.21754in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\9d692d82-fc8c-4174-9672-4b5828f92877.png" />

20. <span id="_Toc218710424" class="anchor"></span>XADC

JFMQL30TAI676H片内集成了一路12bit、1MSPS的XADC模数转换器。悟净Lite开发板共引出了5路XADC接口：1路专用模拟输入VP/VN（接口J24），2路外部辅助模拟输入VAUX0/VAUX1（接口J25/J23），以及2路片内电源监测通道VAUX8/VAUX9。模拟输入要求AVpp
&lt;
1Vpp，外部输入信号经100Ω电阻与1nF电容组成的RC网络滤波后接入；VAUX8通道将VCC1V5分压至0.75V、VAUX9通道将VCC1V8分压至0.9V后送入XADC，实现片内电源监测。

XADC接口说明如下表所示：

| 信号名称                    | 接口/来源  | 备注                              |
|-----------------------------|------------|-----------------------------------|
| XADC\_VP / XADC\_VN         | J24        | 专用模拟输入正/负，AVpp &lt; 1Vpp |
| XADC\_VAUX0P / XADC\_VAUX0N | J25        | 辅助模拟输入通道0                 |
| XADC\_VAUX8P / XADC\_VAUX8N | J23        | 辅助模拟输入通道1                 |
| XADC\_VAUX1P / XADC\_VAUX1N | VCC1V5分压 | 片内1.5V电源监测，缩放至0.75V     |
| XADC\_VAUX9P / XADC\_VAUX9N | VCC1V8分压 | 片内1.8V电源监测，缩放至0.9V      |

XADC接口原理图如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image38.png" style="width:5.76806in;height:2.21925in" alt="H:\wechat-files\xwechat_files\feihu1421_aa14\temp\InputTemp\8a02ff7d-6dd2-4a68-a83d-a083eff448f9.png" />

21. <span id="_Toc218710421" class="anchor"></span>电源管理

悟净Lite开发板采用适配器AC\~220V转DC-12V供电。12V输入经DC电源座J37、拨码开关SW8、防反接保护二极管D25后，进入电子保险丝TPS259824（U26）进行过流和欠压保护：欠压阈值设置为9.6V（VINuvlo=1.2\*(R1+R2)/R2），电流阈值限制为6A（Rilim=1460/(Ilim-0.11)），保护电路同时输出电源良好信号PG。保护后的VCC12V0再经多路DC-DC转换为板内各电源轨，整体电源架构如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image39.png" style="width:5.76806in;height:3.99637in" />

各路电源的分配如下表所示：

| 电源芯片    | 输出电压/电流    | 供电对象                                 |
|-------------|------------------|------------------------------------------|
| RSH084630A  | 1.0V / 18A ×2    | VCCINT、VCCBRAM、VCCPINT                 |
| RSHF84644A  | 5.0V / 4A        | DEVICE（USB等外设）                      |
| RSHF84644A  | 1.5V / 4A        | PS\_VCC1V5、PS DDR                       |
| RSHF84644A  | 1.5V / 8A        | PL\_VCC1V5、PL DDR                       |
| RSHF84644A  | 1.0V / 4A        | MGTAVCC                                  |
| RSHF84644A  | 1.2V / 4A        | MGTAVTT                                  |
| RSHF84644A  | 1.8V / 4A        | VCCAUX、VCCO、VCCPAUX、VCCPLL、MGTVCCAUX |
| RSHF84644A  | 3.3V / 4A        | VCCO、DEVICE                             |
| MP1476      | 2.0V / 4A        | VCCAUX\_IO                               |
| TPS51200 ×2 | 0.75V VREF / VTT | PS、PL DDR端接电源                       |

开发板采用分级使能的上电时序：EN1（VCC12V→VCCINT/VCCBRAM/VCCPINT）→
EN2（→VCC1V8/VCC2V0）→ EN3（→VCC3V3/VCC1V5/MGTAVCC）→
EN4（MGTAVCC→MGTAVTT），保证FPGA内核电源先于IO电源上电。12V输入保护电路原理图如下图所示：

<img src="F:\嵌赛\tmp\lite_manual_extract\media\image40.png" style="width:5.76806in;height:2.55697in" />

5.  <span id="_Toc218710422" class="anchor"></span>开发板原理图

> 参考 JFMQL30TAI\_V02\_原理图.pdf 文档
