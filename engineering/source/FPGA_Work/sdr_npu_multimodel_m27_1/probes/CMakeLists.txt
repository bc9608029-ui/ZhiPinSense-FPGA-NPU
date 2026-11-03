cmake_minimum_required(VERSION 3.10)
project(m27_1_probes LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# GNU dialect is required by the board toolchain: build with -std=gnu++17.
set(CMAKE_CXX_EXTENSIONS ON)

# On-chip iCraft 3.39 installs these configs under /usr/cmake and imports
# Icraft::ZG330Backend / Icraft::HostBackend (transitively Icraft::XRT/XIR).
find_package(icraft-zg330backend REQUIRED)
find_package(icraft-hostbackend REQUIRED)

foreach(probe
    probe_single_model
    probe_two_networks
    probe_sequential_inference
    probe_concurrent_inference
    probe_unload_reload)
  add_executable(${probe} ${probe}.cpp)
  target_compile_options(${probe} PRIVATE -std=gnu++17)
  target_link_libraries(${probe} PRIVATE Icraft::ZG330Backend Icraft::HostBackend pthread dl)
endforeach()
