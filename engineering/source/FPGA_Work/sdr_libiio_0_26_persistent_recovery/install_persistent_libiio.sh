#!/usr/bin/env bash
#
# install_persistent_libiio.sh — FMQL30TAI 板端持久化 libiio 0.26 恢复安装
#
# 作用：把包内的 libiio 0.26 源码、libxml2-dev 头文件、ICU unicode 头文件，
#       在板端离线编译并安装到持久目录 /opt/sdr/libiio-0.26。
#
# 边界（严格遵守）：
#   - 不联网、不依赖 pkg-config；
#   - libxml2/ICU 头文件只解包到 /opt/sdr/builddeps/，绝不写入/覆盖 /usr；
#   - 不 dpkg -i，仅用 dpkg-deb -x 提取头文件；
#   - 安装结果只落 /opt/sdr，绝不落 /tmp；
#   - 不改模型/RTL/位流/UI/Gate 1–9 源码；
#   - 任何失败返回非零，绝不打印假 PASS。
#
# 用法（板端，需可写 /opt 的权限）：
#   sudo bash install_persistent_libiio.sh
#
# 成功输出（最后两行）：
#   LIBIIO_PERSISTENT_INSTALL=PASS
#   LIBIIO_ROOT=/opt/sdr/libiio-0.26

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INSTALL_PREFIX="/opt/sdr/libiio-0.26"
BUILD_ROOT="/opt/sdr/build"
BUILD_DIR="$BUILD_ROOT/libiio-0.26"
SRC_UNPACK="$BUILD_ROOT/libiio-0.26-src"
SRC_DIR="$SRC_UNPACK/libiio-0.26"
DEPS_ROOT="/opt/sdr/builddeps"
LIBXML2_SYSROOT="$DEPS_ROOT/libxml2"
ICU_SYSROOT="$DEPS_ROOT/icu"

log()  { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# ---- [1] 平台校验：必须 aarch64 ----
log "== [1] 平台校验 =="
[ "$(uname -m)" = "aarch64" ] || fail "expected aarch64, got $(uname -m)"
log "  OK   arch=$(uname -m)"

# ---- [2] 运行库校验 ----
log "== [2] 运行库校验 =="
for lib in \
    /lib/aarch64-linux-gnu/libxml2.so.2 \
    /lib/aarch64-linux-gnu/libicuuc.so.66 \
    /lib/aarch64-linux-gnu/libicui18n.so.66 \
    /lib/aarch64-linux-gnu/libicudata.so.66 \
    /lib/aarch64-linux-gnu/libusb-1.0.so.0 ; do
    if [ -e "$lib" ]; then
        log "  OK   $lib"
    else
        fail "missing runtime library: $lib"
    fi
done

# ---- [3] libusb 开发头文件校验 + 定位链接库 ----
log "== [3] libusb 开发头文件校验 =="
[ -f /usr/include/libusb-1.0/libusb.h ] || fail "missing /usr/include/libusb-1.0/libusb.h"
log "  OK   /usr/include/libusb-1.0/libusb.h"

LIBUSB_LIB=""
for c in /usr/lib/aarch64-linux-gnu/libusb-1.0.so /usr/lib/aarch64-linux-gnu/libusb-1.0.so.0; do
    if [ -e "$c" ]; then LIBUSB_LIB="$c"; break; fi
done
[ -n "$LIBUSB_LIB" ] || fail "libusb-1.0 link library not found"
log "  OK   LIBUSB_LIB=$LIBUSB_LIB"

# ---- [4] 提取 libxml2-dev（dpkg-deb -x，不 dpkg -i）----
log "== [4] 提取 libxml2-dev 头文件 =="
LIBXML2_DEB=""
for f in "$HERE"/libxml2-dev_*_arm64.deb; do
    if [ -f "$f" ]; then LIBXML2_DEB="$f"; break; fi
done
[ -n "$LIBXML2_DEB" ] || fail "libxml2-dev arm64 .deb not found in package"
log "  deb=$LIBXML2_DEB"

rm -rf "$LIBXML2_SYSROOT"
mkdir -p "$LIBXML2_SYSROOT"
dpkg-deb -x "$LIBXML2_DEB" "$LIBXML2_SYSROOT"

LIBXML2_INC="$LIBXML2_SYSROOT/usr/include/libxml2"
[ -f "$LIBXML2_INC/libxml/parser.h" ] || fail "libxml2 header extraction failed (no libxml/parser.h)"
log "  OK   $LIBXML2_INC/libxml/parser.h"

# ---- [5] 解包 ICU 头文件到独立 sysroot（不覆盖 /usr）----
log "== [5] 解包 ICU unicode 头文件 =="
[ -f "$HERE/icu_headers.tar.gz" ] || fail "icu_headers.tar.gz not found in package"
rm -rf "$ICU_SYSROOT"
mkdir -p "$ICU_SYSROOT"
tar xzf "$HERE/icu_headers.tar.gz" -C "$ICU_SYSROOT"
[ -f "$ICU_SYSROOT/usr/include/unicode/ucnv.h" ] || fail "ICU header unpack failed (no unicode/ucnv.h)"
log "  OK   $ICU_SYSROOT/usr/include/unicode/ucnv.h"

# ---- [6] 解包 libiio 0.26 源码 ----
log "== [6] 解包 libiio 0.26 源码 =="
[ -f "$HERE/libiio-0.26.tar.gz" ] || fail "libiio-0.26.tar.gz not found in package"
rm -rf "$SRC_UNPACK"
mkdir -p "$SRC_UNPACK"
tar xzf "$HERE/libiio-0.26.tar.gz" -C "$SRC_UNPACK"
[ -f "$SRC_DIR/CMakeLists.txt" ] || fail "libiio source unpack failed (no CMakeLists.txt)"
log "  OK   $SRC_DIR"

# ---- [7] 显式路径配置 CMake（不依赖 pkg-config）----
log "== [7] 配置 CMake =="
export CPATH="$ICU_SYSROOT/usr/include${CPATH:+:$CPATH}"
export C_INCLUDE_PATH="$ICU_SYSROOT/usr/include${C_INCLUDE_PATH:+:$C_INCLUDE_PATH}"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

cmake -S "$SRC_DIR" -B "$BUILD_DIR" \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DBUILD_SHARED_LIBS=ON \
    -DWITH_USB_BACKEND=ON \
    -DWITH_NETWORK_BACKEND=OFF \
    -DWITH_LOCAL_BACKEND=OFF \
    -DWITH_SERIAL_BACKEND=OFF \
    -DWITH_IIOD=OFF \
    -DWITH_TESTS=OFF \
    -DWITH_EXAMPLES=OFF \
    -DENABLE_IPV6=OFF \
    "-DLIBUSB_INCLUDE_DIR=/usr/include/libusb-1.0" \
    "-DLIBUSB_LIBRARIES=$LIBUSB_LIB" \
    "-DLIBXML2_INCLUDE_DIR=$LIBXML2_INC" \
    "-DLIBXML2_LIBRARY=/lib/aarch64-linux-gnu/libxml2.so.2"

# ---- [8] 构建 ----
log "== [8] 构建 =="
cmake --build "$BUILD_DIR" --parallel 2

# ---- [9] 安装 ----
log "== [9] 安装 =="
cmake --install "$BUILD_DIR"

# ---- [10] 产物校验 ----
log "== [10] 产物校验 =="
[ -f "$INSTALL_PREFIX/include/iio.h" ] || fail "missing $INSTALL_PREFIX/include/iio.h"
[ -f "$INSTALL_PREFIX/lib/libiio.so" ] || fail "missing $INSTALL_PREFIX/lib/libiio.so"
log "  OK   $INSTALL_PREFIX/include/iio.h"
log "  OK   $INSTALL_PREFIX/lib/libiio.so"

# ---- [11] 确认 AArch64 ----
log "== [11] 架构确认 =="
ARCH_OK=0
if command -v readelf >/dev/null 2>&1; then
    if readelf -h "$INSTALL_PREFIX/lib/libiio.so" 2>/dev/null | grep -q "AArch64"; then
        ARCH_OK=1
    fi
elif command -v file >/dev/null 2>&1; then
    if file "$INSTALL_PREFIX/lib/libiio.so" 2>/dev/null | grep -qiE "aarch64"; then
        ARCH_OK=1
    fi
fi
[ "$ARCH_OK" -eq 1 ] || fail "cannot confirm libiio.so is aarch64"
log "  OK   libiio.so is AArch64"

# ---- [12] ldd 无 not found ----
log "== [12] 运行时依赖检查 (ldd) =="
LDD_OUT="$(ldd "$INSTALL_PREFIX/lib/libiio.so" 2>&1 || true)"
if printf '%s\n' "$LDD_OUT" | grep -q "not found"; then
    printf '%s\n' "$LDD_OUT" >&2
    fail "ldd reports not-found dependency"
fi
log "  OK   no 'not found' in ldd"
printf '%s\n' "$LDD_OUT"

# ---- [13] 结果（仅当以上全部通过才会走到这里）----
log ""
log "LIBIIO_PERSISTENT_INSTALL=PASS"
log "LIBIIO_ROOT=$INSTALL_PREFIX"
exit 0
