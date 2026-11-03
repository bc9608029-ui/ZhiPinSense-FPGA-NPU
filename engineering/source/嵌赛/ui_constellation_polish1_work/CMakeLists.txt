# CMakeLists.txt — M29 RML24 offline IQ constellation viewer.
#
# Two independent targets:
#   * iqframe_core + test_iqframe — pure C++17, NO Qt required (builds and runs
#     anywhere with a C++17 compiler; this is the primary validated target).
#   * constellation_viewer — Qt 5 Quick GUI (built only when Qt5 is found).
#
# On this delivery machine no Qt-capable C++ toolchain is installed (no MSVC /
# MinGW / clang on Windows), so the GUI target is expected to be SKIPPED there
# and the Qt-free unit tests are the honest primary result. See README.md.
cmake_minimum_required(VERSION 3.16)
project(constellation_ui_prototype LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# ---------------------------------------------------------------------------
# Qt-free core (data model, loader, decimation, auto-scale, SHA-256)
# ---------------------------------------------------------------------------
add_library(iqframe_core STATIC
    src/IqFrameLoader.cpp
)
target_include_directories(iqframe_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

# ---------------------------------------------------------------------------
# Unit tests (14 required + extras) — no Qt, run with ctest or directly.
# test_iqframe takes the fixtures directory as its only argument.
# ---------------------------------------------------------------------------
enable_testing()
add_executable(test_iqframe tests/test_iqframe.cpp)
target_link_libraries(test_iqframe PRIVATE iqframe_core)
add_test(NAME iqframe_unit COMMAND test_iqframe ${CMAKE_CURRENT_SOURCE_DIR}/fixtures)

# ---------------------------------------------------------------------------
# GUI (Qt 5 Quick + QML + the C++ scene-graph scatter item)
# ---------------------------------------------------------------------------
find_package(Qt5 QUIET COMPONENTS Quick QuickControls2 Qml)
if(Qt5_FOUND)
    add_executable(constellation_viewer
        src/main.cpp
        src/ConstellationItem.cpp
        qml.qrc
    )
    target_link_libraries(constellation_viewer PRIVATE
        iqframe_core
        Qt5::Quick
        Qt5::QuickControls2
        Qt5::Qml
    )
else()
    message(STATUS "Qt5 not found: GUI target 'constellation_viewer' skipped "
                   "(unit tests still build).")
endif()
