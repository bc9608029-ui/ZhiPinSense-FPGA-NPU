# CMakeLists.txt — multi-target build for the HDMI instrument-UI PS programs
# (FMQL30TAI, 1280x720@60, double-buffered flip path).
#
# v3 scope: the instrument-UI refactor.  phase1b/phase1c are v2-validated assets
# and are intentionally NOT part of v3 (see REPORT.md); they are not built here.
#
# Board programs (native aarch64 g++, libc only):
#   phase2_ui_render        — RF-signal-recognition UI, staging + scalar submit
#   phase3_touch_test       — USB touch detect / calibrate / page switch
#
# Host tests (x86/WSL, no board):
#   test_direct_framebuffer_backend — backend logic + submit()/canary mock test
#   test_ui                          — font/softmax/touch/hit-test/draw determinism
#   render_screenshots               — 7 scenarios + font specimen -> BMP + hash
#
# NO iCraft / NPU / Device::Open dependency: the HDMI-only bitstream has no NPU,
# and the axi:// open path hangs the board's Linux.  The backend talks directly
# to /dev/udmabuf0 and /dev/mem; only libc is required.

cmake_minimum_required(VERSION 3.16)
project(hdmi_framebuffer_ui_v3_sw CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The safe direct framebuffer backend (replaces iCraft Device::Open).
add_library(direct_framebuffer_backend STATIC
    direct_framebuffer_backend.cpp)

# The generic-N-class instrument UI (canvas is header-only).
add_library(ui STATIC
    font.cpp
    ui_renderer.cpp
    model_contract.cpp
    touch.cpp)

add_library(image_writer STATIC
    image_writer.cpp)

# ---- board programs ---------------------------------------------------------
add_executable(phase2_ui_render phase2_ui_render.cpp)
target_link_libraries(phase2_ui_render PRIVATE direct_framebuffer_backend ui)

add_executable(phase3_touch_test phase3_touch_test.cpp)
target_link_libraries(phase3_touch_test PRIVATE direct_framebuffer_backend ui)

# ---- host tests -------------------------------------------------------------
add_executable(test_direct_framebuffer_backend test_direct_framebuffer_backend.cpp)
target_link_libraries(test_direct_framebuffer_backend PRIVATE direct_framebuffer_backend)

add_executable(test_ui test_ui.cpp)
target_link_libraries(test_ui PRIVATE ui)

add_executable(render_screenshots render_screenshots.cpp)
target_link_libraries(render_screenshots PRIVATE ui image_writer)
