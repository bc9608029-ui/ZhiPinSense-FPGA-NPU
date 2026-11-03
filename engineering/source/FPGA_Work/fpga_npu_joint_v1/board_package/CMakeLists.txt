cmake_minimum_required(VERSION 3.10)
project(fpga_npu_joint_smoke LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# GNU dialect is required by the board toolchain: build with -std=gnu++17.
set(CMAKE_CXX_EXTENSIONS ON)

# The on-chip iCraft 3.39 package installs these configs under /usr/cmake and
# imports Icraft::ZG330Backend / Icraft::HostBackend (transitively Icraft::XRT
# and Icraft::XIR).  HostBackend is needed because the compiled model's
# Input/Output ops are @hostt while its 85 compute HardOps are @zhuget(330).
find_package(icraft-zg330backend REQUIRED)
find_package(icraft-hostbackend REQUIRED)

# FPGA -> NPU joint correctness closed-loop: Phase A (PL DDR + Mandatory Core
# data path) + Phase B (per-frame NPU inference, exp4 Device reopen lifecycle).
add_executable(fpga_npu_joint_smoke fpga_npu_joint_smoke.cpp)
target_compile_options(fpga_npu_joint_smoke PRIVATE -std=gnu++17)
target_link_libraries(fpga_npu_joint_smoke PRIVATE Icraft::ZG330Backend Icraft::HostBackend pthread dl)
