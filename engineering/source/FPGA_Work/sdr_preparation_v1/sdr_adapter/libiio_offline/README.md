# libiio 离线安装包与 AArch64 部署方案（Task 39e5b / Task 3 构建门）

本目录是 SDR（ADALM-Pluto）到货前的 **libiio 构建门**离线资产，与
`sdr_adapter/pluto_libiio.cpp`、`libiio_gate.cpp`、`build_libiio_gate.sh` 配套。
**不含任何"真实采集 PASS"的声明**——到货前只验证「编译 + 链接 + 无设备时快速、
明确地返回 device not found」。

## 1. 已验证的构建门结论（主机，2026-10-04）

| 项 | 值 |
|----|----|
| 编译器 | g++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0（`-std=gnu++17 -Wall -Wextra -O2`）|
| libiio 版本 | **0.26**（Debian 包 `0.26-2build2`，Ubuntu 25.04 "resolute" universe）|
| libiio.so.0.26 依赖（DT_NEEDED）| libusb-1.0.so.0、libserialport.so.0、libavahi-client.so.3、libavahi-common.so.3、libxml2.so.16、libc.so.6 |
| 配置 0（`SDR_ADAPTER_HAVE_LIBIIO=0`）| mock 后端，离线读 4 帧，exit 0 |
| 配置 1（`SDR_ADAPTER_HAVE_LIBIIO=1`）| 链接 libiio；无 Pluto → `device not found (no ADALM-Pluto on USB)`，exit 2，**约 4 ms**；不崩溃 / 不卡死 / 不回退 MOCK |

复现（在 WSL 内，无需 root）：

```sh
cd sdr_adapter/libiio_offline
bash install_offline.sh ~/iio_work/sysroot     # 把 debs 解包成 sysroot
cd .. && bash build_libiio_gate.sh             # 分别实编译 0/1 两种配置并运行
```

## 2. 离线资产清单

| 文件 | 说明 |
|------|------|
| `debs/*.deb`（6 个）| **amd64 主机验证用**的 libiio 0.26 及其运行时依赖包，可无 root 解包编译 |
| `libiio-0.26.tar.gz` | libiio v0.26 官方源码（`analogdevicesinc/libiio`），**可移植到 AArch64** 交叉编译 |
| `install_offline.sh` | 主机侧把 debs 解包成 sysroot 的辅助脚本 |
| `sha256_manifest.txt` | 本目录 7 个资产的 SHA-256（`sha256sum -c` 校验）|

> 注意：`debs/` 是 **amd64** 包，只用于主机侧编译/链接/运行验证；**不能直接装到
> aarch64 板卡**。板卡侧用 §3 的方案。

## 3. AArch64 部署方案（板卡 FMQL30TAI，Zynq-7030，aarch64 Linux）

板卡 OS 的发行版/包管理器**尚未确认**，故给出三种方案；**上板前先确认**板卡 OS
（Debian/Ubuntu 系 + dpkg？还是 Yocto/PetaLinux/自研 BSP？）。

### 方案 A — 离线 .deb（仅当板卡 OS 是 Debian/Ubuntu 系且有 dpkg）

从 `http://ports.ubuntu.com/ubuntu-ports/` 下载与板卡发行版匹配的 **arm64** 包：

```
libiio-dev libiio0 libusb-1.0-0 libserialport0 libavahi-client3 libavahi-common3 libxml2-16
```

U 盘上板后 `dpkg -i *.deb`。依赖 `glibc` 版本须与板卡一致；否则退回方案 B/C。

### 方案 B — 源码交叉编译（通用，推荐）

用 aarch64 交叉工具链（`aarch64-linux-gnu-gcc/g++`）编译 `libiio-0.26.tar.gz`：

```sh
mkdir build-arm && cd build-arm
cmake ../libiio-0.26 \
  -DCMAKE_TOOLCHAIN_FILE=<你的 aarch64.cmake> \
  -DCMAKE_INSTALL_PREFIX=$PWD/install \
  -DBUILD_SHARED_LIBS=ON \
  -DWITH_TESTS=OFF -DWITH_EXAMPLES=OFF -DWITH_IIOD=OFF \
  -DENABLE_IPV6=OFF
make -j && make install
```

产出的 `install/lib/libiio.so*` + 头文件随 `pluto_libiio.cpp` 一起交叉编译上板。

### 方案 C — 静态链接最小化（只留 USB 后端，推荐上板用）

Pluto 走 **USB**，无需网络/XML/串口后端。libiio 0.26 的 **libxml2 / avahi 依赖来自
网络后端**（`WITH_NETWORK_BACKEND`，内部含 DNS-SD/avahi 与 XML 解析），
**libserialport 来自串口后端**（`WITH_SERIAL_BACKEND`，默认 OFF）。禁用网络/本地/
串口后端后，libiio 只剩 **libusb-1.0**（+ libc）依赖，静态链接体积最小：

```sh
mkdir build-arm && cd build-arm
cmake ../libiio-0.26 \
  -DCMAKE_TOOLCHAIN_FILE=<你的 aarch64.cmake> \
  -DCMAKE_INSTALL_PREFIX=$PWD/install \
  -DBUILD_SHARED_LIBS=OFF \
  -DWITH_USB_BACKEND=ON \
  -DWITH_NETWORK_BACKEND=OFF \
  -DWITH_LOCAL_BACKEND=OFF \
  -DWITH_SERIAL_BACKEND=OFF \
  -DWITH_IIOD=OFF \
  -DWITH_TESTS=OFF -DWITH_EXAMPLES=OFF \
  -DENABLE_IPV6=OFF
make -j && make install
```

得到 `install/lib/libiio.a`（+ 静态 libusb），静态链接出**自包含**的板卡可执行：

```sh
aarch64-linux-gnu-g++ -std=gnu++17 -O2 -DSDR_ADAPTER_HAVE_LIBIIO \
  -I<libiio install>/include -I<libusb include> \
  pluto_libiio.cpp libiio_gate.cpp \
  <libiio install>/lib/libiio.a -lusb-1.0 -static -o gate_board
```

产物无 `.so` 运行时依赖，直接拷上板运行。**这就是"离线安装包/静态链接方案"的落点。**

## 4. 边界（禁止）

- **不声称真实采集 PASS**：`pluto_libiio.cpp` 的 `read()`（AD9361 RX 缓冲）按 ADI
  `ad9361-iiostream` 规范写法，但**未经板卡实机验证**，属「待 Pluto 到货后非盲复测」；
- 设备参数（中心频率/采样率/RF 带宽/增益等）与 `receiver_scale` 标定仍是**到货后
  非盲重放确定**，本层不臆造；
- 本目录 amd64 debs 不用于板卡；板卡一律走 §3 的 aarch64 方案。
