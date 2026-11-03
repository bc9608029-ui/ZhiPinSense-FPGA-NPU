cmake_minimum_required(VERSION 3.10)
project(continuous_joint_stress LANGUAGES CXX)

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

# Continuous joint stress: fixed-IQ loop -> PL DDR -> FPGA Mandatory Core ->
# tensor readback -> per-cycle Golden compare -> SAME persistent Device/Session
# -> NPU inference (frames 7..18, Device::reset(1) re-arm) -> repeat.
#
# iq_source.cpp is the SdrIqSource placeholder only (throws on construction);
# FileIqSource (file_iq_source.cpp) is what actually runs today.
add_executable(continuous_joint_stress
    continuous_joint_stress.cpp
    iq_source.cpp
    file_iq_source.cpp)
target_compile_options(continuous_joint_stress PRIVATE -std=gnu++17)
target_link_libraries(continuous_joint_stress PRIVATE Icraft::ZG330Backend Icraft::HostBackend pthread dl)
