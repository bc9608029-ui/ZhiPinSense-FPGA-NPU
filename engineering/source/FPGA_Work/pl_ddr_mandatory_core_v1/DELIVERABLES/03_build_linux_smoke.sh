#!/usr/bin/env bash
# 板载 Linux（aarch64 Ubuntu 20.04）上编译 pl_ddr_mandatory_core_smoke
# 工具链：板载 g++（-std=gnu++17），iCraft 3.39 SDK（icraft-xrt 头文件 + aarch64 库）
#
# 前置条件：
#   1. iCraft 3.39 已随系统镜像安装到板载 /usr：
#       头文件  /usr/include/icraft-xrt/core/session.h
#               /usr/include/icraft-xrt/dev/zg330_device.h
#       库      /usr/lib/aarch64-linux-gnu/libicraft_{xrt,zg330backend,hostbackend,xir,utils}.so
#   2. 本脚本、pl_ddr_mandatory_core_smoke.cpp、pl_ddr_register_map.hpp 已拷贝到同一目录。
set -euo pipefail

SRC="${1:-pl_ddr_mandatory_core_smoke.cpp}"
REG="${2:-pl_ddr_register_map.hpp}"
OUT="${3:-pl_ddr_mandatory_core_smoke}"

# iCraft 3.39 头文件根目录（板载默认 /usr/include）
ICRAFT_INC="${ICRAFT_INC:-/usr/include/icraft-xrt}"
# aarch64 库目录（板载默认）
ICRAFT_LIB="${ICRAFT_LIB:-/usr/lib/aarch64-linux-gnu}"

g++ -std=gnu++17 -O2 -Wall \
    -I"${ICRAFT_INC}" \
    "${SRC}" \
    -L"${ICRAFT_LIB}" \
    -licraft_zg330backend \
    -licraft_hostbackend \
    -licraft_xrt \
    -licraft_xir \
    -licraft_utils \
    -lpthread -ldl -lrt \
    -o "${OUT}"

echo "OK -> ${OUT}"

# 运行（示例）：
#   ./pl_ddr_mandatory_core_smoke \
#       "axi://zg330aiu?npu=0x40000000&dma=0x80000000" \
#       0x400C0000 \
#       iq_input.bin \
#       tensor_output.bin
#
# 链接库解析依据（iCraft 3.39 cmake targets，实测）：
#   ZG330Backend -> XRT -> XIR（-> utils）；另按官方 CMakeLists 补 HostBackend。
# 命名空间/API 与源码一致（session.h: Device::Open；zg330_device.h: ZG330Device；
#   device.h: defaultMemRegion()/defaultRegRegion()/malloc(bytes,auto_free,alignment)）。
