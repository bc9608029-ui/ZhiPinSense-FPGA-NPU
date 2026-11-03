# CMakeLists.txt — minimal build for the Phase 1A PS smoke test (FMQL30TAI / ZG330).
#
# Mirrors the official fpai_demo_app example CMake (PLin+SingleNet+HDMI) but drops
# every dependency the smoke test doesn't need (OpenCV, ffmpeg, YAML, spdlog,
# onnxruntime, Eigen, ...).  Only the iCraft runtime is required.
#
# Build (ON the board, native aarch64 g++):
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
#   cmake --build build -j
#   ./build/phase1a_fb_test checker
#
# For x86-host cross-compile, add: -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64
#   and set CMAKE_C_COMPILER / CMAKE_CXX_COMPILER to aarch64-linux-gnu-gcc/g++.
# (The official example does this; native on-board build needs none of it.)

cmake_minimum_required(VERSION 3.16)
project(phase1a_fb_test CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# FMQL30TAI == ZG330 NPU platform -> FPAIDevice = icraft::xrt::ZG330Device
add_compile_definitions(USE_ZG330_BACKEND)

# iCraft SDK (installed by Icraft_*.deb: headers in /usr/include, CMake package
# configs in /usr/cmake).  The package config names resolve to the lowercase
# icraft-*-config.cmake files and export targets Icraft::<Backend>.
find_package(icraft-zg330backend REQUIRED)
find_package(Icraft-HostBackend REQUIRED)
find_package(Icraft-BuyiBackend REQUIRED)

add_executable(phase1a_fb_test phase1a_fb_test.cpp)

target_link_libraries(phase1a_fb_test PRIVATE
    Icraft::ZG330Backend
    Icraft::HostBackend
    Icraft::BuyiBackend
    stdc++fs
)
