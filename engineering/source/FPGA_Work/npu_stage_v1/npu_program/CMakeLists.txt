cmake_minimum_required(VERSION 3.10)
project(npu_only_smoke LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# GNU dialect is required by the board toolchain: build with -std=gnu++17.
set(CMAKE_CXX_EXTENSIONS ON)

# The on-chip iCraft 3.39 package installs these configs under /usr/cmake and
# imports Icraft::ZG330Backend / Icraft::HostBackend, transitively Icraft::XRT
# and Icraft::XIR.  HostBackend is needed because the compiled model's
# Input/Output ops are @hostt while its 85 compute HardOps are @zhuget(330).
find_package(icraft-zg330backend REQUIRED)
find_package(icraft-hostbackend REQUIRED)

add_executable(npu_only_smoke npu_only_smoke.cpp)
target_compile_options(npu_only_smoke PRIVATE -std=gnu++17)
target_link_libraries(npu_only_smoke PRIVATE Icraft::ZG330Backend Icraft::HostBackend pthread dl)

# Diagnostic harness: localizes the same-process one-frame delay by varying one
# variable per experiment (see npu_diag.cpp header). Not part of the real-time
# path; it only runs the compiled model and prints argmax/timing.
add_executable(npu_diag npu_diag.cpp)
target_compile_options(npu_diag PRIVATE -std=gnu++17)
target_link_libraries(npu_diag PRIVATE Icraft::ZG330Backend Icraft::HostBackend pthread dl)
