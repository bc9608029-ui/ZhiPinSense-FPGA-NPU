cmake_minimum_required(VERSION 3.10)
project(npu_realtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# GNU dialect is required by the board toolchain: build with -std=gnu++17.
set(CMAKE_CXX_EXTENSIONS ON)

# The on-chip iCraft 3.39 package installs these configs under /usr/cmake and
# imports Icraft::ZG330Backend / Icraft::HostBackend (transitively Icraft::XRT,
# Icraft::XIR).  HostBackend is required because the compiled model's
# Input/Output ops are @hostt while its 85 compute HardOps are @zhuget(330).
find_package(icraft-zg330backend REQUIRED)
find_package(icraft-hostbackend REQUIRED)

add_executable(npu_realtime npu_realtime.cpp)
target_compile_options(npu_realtime PRIVATE -std=gnu++17)
target_link_libraries(npu_realtime PRIVATE Icraft::ZG330Backend Icraft::HostBackend pthread dl)
