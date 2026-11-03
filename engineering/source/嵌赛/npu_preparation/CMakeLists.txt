cmake_minimum_required(VERSION 3.10)
project(v2_npu_only_smoke LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# The on-chip 3.39 package installs this config under /usr/cmake and imports
# Icraft::ZG330Backend.  It transitively imports Icraft::XRT and Icraft::XIR.
find_package(icraft-zg330backend REQUIRED)

add_executable(v2_npu_only_smoke npu_only_smoke.cpp)
target_link_libraries(v2_npu_only_smoke PRIVATE Icraft::ZG330Backend pthread dl)
