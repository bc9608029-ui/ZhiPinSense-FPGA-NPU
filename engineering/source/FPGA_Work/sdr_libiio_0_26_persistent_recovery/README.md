# libiio 0.26 板端持久化恢复包（FMQL30TAI）

## 1. 这是什么

板端重启后 `/tmp` 会被清空，之前放在 `/tmp/.../libiio-arm64` 的自编译 libiio 会丢失。
本包在**离线、无 pkg-config、无网络**的条件下，把 libiio 0.26 编译并安装到**持久目录**
`/opt/sdr/libiio-0.26`，重启后仍在。

当前板端检查结论（据实）：

| 检查项 | 状态 |
|---|---|
| `/usr/include/libusb-1.0/libusb.h` | FOUND（libusb 开发头文件已永久安装） |
| `/usr/include/libxml2/libxml/parser.h` | **MISSING**（本包用 `dpkg-deb -x` 离线提取） |
| `/usr/include/unicode/ucnv.h` | **MISSING**（本包提供 ICU 头文件补丁） |

> 根因：libxml2 的 `encoding.h` 在 `LIBXML_ICU_ENABLED` 下 `#include <unicode/ucnv.h>`，
> 而板上 libxml2 是带 ICU 编译的（`xmlversion.h` 定义了 `LIBXML_ICU_ENABLED`），所以
> 编译 libiio（会间接包含 `libxml/parser.h`）时必须有 ICU 的 `unicode/` 头文件。

## 2. 包内容（6 个文件）

| 文件 | 说明 |
|---|---|
| `libiio-0.26.tar.gz` | libiio v0.26 官方源码（`analogdevicesinc/libiio`） |
| `libxml2-dev_2.9.10+dfsg-5ubuntu0.20.04.5_arm64.deb` | libxml2 开发头文件（arm64） |
| `icu_headers.tar.gz` | ICU 66 unicode 头文件（`usr/include/unicode/*.h`，187 个） |
| `install_persistent_libiio.sh` | 板端安装脚本（本节所述全部流程） |
| `SHA256SUMS.txt` | 本包自校验清单（`sha256sum -c`） |
| `README.md` | 本文 |

## 3. 目录约定

| 用途 | 路径 |
|---|---|
| 安装目标（持久） | `/opt/sdr/libiio-0.26` |
| 构建临时目录 | `/opt/sdr/build/libiio-0.26`（源码解包到 `../libiio-0.26-src/`） |
| libxml2 头文件 sysroot | `/opt/sdr/builddeps/libxml2` |
| ICU 头文件 sysroot | `/opt/sdr/builddeps/icu` |

> 以上都在 `/opt/sdr` 下，**绝不写入/覆盖 `/usr`**，**绝不落到 `/tmp`**。

## 4. 板端前置条件（脚本会逐一校验）

- `uname -m` = `aarch64`
- 运行库：`/lib/aarch64-linux-gnu/libxml2.so.2`、`libicuuc.so.66`、`libicui18n.so.66`、
  `libicudata.so.66`、`libusb-1.0.so.0`
- 开发头：`/usr/include/libusb-1.0/libusb.h`
- 工具：`g++`、`cc`、`cmake`、`make`、`dpkg-deb`（已确认存在）

## 5. 板端逐行安装命令

```bash
# 1) 解包
tar xzf sdr_libiio_0_26_persistent_recovery.tar.gz
cd sdr_libiio_0_26_persistent_recovery

# 2) 自校验（必须全 OK，任何 FAILED 都停）
sha256sum -c SHA256SUMS.txt

# 3) 安装（写 /opt/sdr，需要 root；脚本内部会重新解包、编译、安装）
sudo bash install_persistent_libiio.sh
```

成功时最后两行是：

```
LIBIIO_PERSISTENT_INSTALL=PASS
LIBIIO_ROOT=/opt/sdr/libiio-0.26
```

## 6. 安装后验证（可选，逐行）

```bash
ls -l /opt/sdr/libiio-0.26/include/iio.h /opt/sdr/libiio-0.26/lib/libiio.so
readelf -h /opt/sdr/libiio-0.26/lib/libiio.so | grep -i 'Machine'
ldd /opt/sdr/libiio-0.26/lib/libiio.so
```

随后 Gate 6–9 的构建/运行改用持久路径：

```bash
LIBIIO_ROOT=/opt/sdr/libiio-0.26 ./board_package/build_on_board.sh
LIBIIO_ROOT=/opt/sdr/libiio-0.26 ICRAFT_CMAKE_DIR=/usr/cmake ./board_package/build_npu_on_board.sh --gate9
```

## 7. 脚本行为与安全红线

- `set -euo pipefail`，任何一步失败返回非零，**绝不打印假 PASS**。
- 校验 aarch64 → 校验 5 个运行库 → 校验 libusb 头文件 → `dpkg-deb -x` 提取 libxml2 头
  （**不 `dpkg -i`**）→ 解包 ICU 头到独立 sysroot → 解包 libiio 源码 → 显式路径配
  CMake（**不依赖 pkg-config**，禁网络/本地/串口后端、禁 IIOD/Tests/Examples/IPv6）→
  `cmake --build --parallel 2` → `cmake --install` → 校验 `iio.h`+`libiio.so` →
  `readelf`/`file` 确认 AArch64 → `ldd` 确认无 `not found` → 打印 PASS。
- **重复运行安全**：脚本开头会 `rm -rf` 并重建 builddeps/build 目录，可反复重装。
- 不改模型/RTL/位流/UI/Gate 1–9 源码；只读写 `/opt/sdr` 与自身包内文件。

## 8. 状态

本包离线制作、未经板端实机验证，状态为 **`READY-FOR-BOARD-LIBIIO-PERSISTENT-INSTALL-TEST`**，
非 PASS。板端安装命令由用户本人执行。
