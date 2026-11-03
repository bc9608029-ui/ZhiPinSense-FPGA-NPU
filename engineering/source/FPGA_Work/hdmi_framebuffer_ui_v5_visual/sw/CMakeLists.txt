# CMakeLists.txt — multi-target build for the v5_visual HDMI display PS tests
# (FMQL30TAI, 1280x720@60, double-buffered flip path).
#
# Targets:
#   phase1b_doublebuf_test  — double-buffer tear-free dynamic test (Phase 1B)
#   phase1c_dynamic_test    — rotating patterns + >=10 min stability (Phase 1C)
#   phase2_ui_render        — Style A recognition UI render (anti-aliased atlas) (Phase 2)
#   phase3_touch_test       — USB touch detect / calibrate / page switch (Phase 3)
#   test_direct_framebuffer_backend — host-only mock test of the safe backend
#
# Phase 2/3 now link the device-independent Style A UI render layer (ui_render),
# which pulls in the pre-rasterized DejaVu glyph atlas (font_atlas_data.cpp) and the
# RGB565 integer alpha-blend text renderer (font_atlas.cpp).  The backend (submit_frame)
# is unchanged from v4_fix.
#
# NO iCraft / NPU / Device::Open dependency: the HDMI-only bitstream has no NPU,
# and the axi:// open path hangs the board's Linux.  The backend talks directly
# to /dev/udmabuf0 and /dev/mem; only libc is required.
#
# Build (ON the board, native aarch64 g++):
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
#   cmake --build build -j
#   ./build/phase2_ui_render
#
# Host mock test (x86 Linux or WSL — no board needed):
#   cmake -S . -B build_host -DCMAKE_BUILD_TYPE=Release
#   cmake --build build_host --target test_direct_framebuffer_backend -j
#   ./build_host/test_direct_framebuffer_backend
#
# Host screenshot renderer (x86/WSL; device-independent, no /dev/mem):
#   g++ -O2 -std=gnu++17 host_screenshot.cpp font_atlas.cpp font_atlas_data.cpp ui_render.cpp -o host_screenshot
#   ./host_screenshot
#
# For x86-host cross-compile of the phase programs, add:
#   -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64
#   and set CMAKE_C_COMPILER / CMAKE_CXX_COMPILER to aarch64-linux-gnu-gcc/g++.

cmake_minimum_required(VERSION 3.16)
project(hdmi_framebuffer_ui_v5_visual_sw CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The safe direct framebuffer backend (replaces iCraft Device::Open).
add_library(direct_framebuffer_backend STATIC
    direct_framebuffer_backend.cpp)

# Style A UI render layer (device-independent; RGB565 atlas + blend + pages).
add_library(ui_render STATIC
    font_atlas.cpp
    font_atlas_data.cpp
    ui_render.cpp)

add_executable(phase1b_doublebuf_test phase1b_doublebuf_test.cpp)
target_link_libraries(phase1b_doublebuf_test PRIVATE direct_framebuffer_backend)

add_executable(phase1c_dynamic_test phase1c_dynamic_test.cpp)
target_link_libraries(phase1c_dynamic_test PRIVATE direct_framebuffer_backend)

add_executable(phase2_ui_render phase2_ui_render.cpp)
target_link_libraries(phase2_ui_render PRIVATE direct_framebuffer_backend ui_render)

add_executable(phase3_touch_test phase3_touch_test.cpp)
target_link_libraries(phase3_touch_test PRIVATE direct_framebuffer_backend ui_render)

# Host mock test (x86/WSL): exercises the backend logic without any hardware.
add_executable(test_direct_framebuffer_backend test_direct_framebuffer_backend.cpp)
target_link_libraries(test_direct_framebuffer_backend PRIVATE direct_framebuffer_backend)

# Host render test (x86/WSL): 8/10/12/16 boundary, text/icon non-overlap,
# error-page nav existence, mock-not-live.  Device-independent, no hardware.
add_executable(test_ui_render test_ui_render.cpp)
target_link_libraries(test_ui_render PRIVATE ui_render)
