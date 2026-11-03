cmake_minimum_required(VERSION 3.16)
project(hdmi_ui_v1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# Qt 5.15 (Anaconda or the board's Qt).  The UI has no GPU on the FMQL30TAI,
# so run the board binary with a software-rendered platform:
#   ./hdmi_ui_v1 -platform linuxfb
#   QT_QUICK_BACKEND=software ./hdmi_ui_v1 -platform eglfs
find_package(Qt5 5.15 COMPONENTS Core Gui Qml Quick QuickControls2 REQUIRED)

add_executable(hdmi_ui_v1
    app/main.cpp
    app/frame_bridge.cpp
    app/frame_bridge.hpp
    app/source_controller.cpp
    app/source_controller.hpp
    src/json_result_frame.cpp
    src/json_result_frame.hpp
    src/jsonlines_data_source.cpp
    src/jsonlines_data_source.hpp
    src/mock_data_source.cpp
    src/mock_data_source.hpp
    resources.qrc
)
target_include_directories(hdmi_ui_v1 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(hdmi_ui_v1 PRIVATE
    Qt5::Core
    Qt5::Gui
    Qt5::Qml
    Qt5::Quick
    Qt5::QuickControls2
)

# Qt-free contract + integrity test: builds with only a C++17 toolchain (no Qt),
# so the frozen contract can be verified on the host before any Qt build.
enable_testing()
add_executable(test_contract tests/test_contract.cpp)
target_include_directories(test_contract PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_test(NAME contract COMMAND test_contract)
