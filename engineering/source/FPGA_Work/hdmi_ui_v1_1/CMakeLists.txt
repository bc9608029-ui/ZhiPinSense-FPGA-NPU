cmake_minimum_required(VERSION 3.16)
project(hdmi_ui_v1_1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# Qt 5.15 (Anaconda or the board's Qt).  The UI has no GPU on the FMQL30TAI,
# so run the board binary with a software-rendered platform:
#   ./hdmi_ui_v1_1 -platform linuxfb
#   QT_QUICK_BACKEND=software ./hdmi_ui_v1_1 -platform eglfs
find_package(Qt5 5.15 COMPONENTS Core Gui Qml Quick QuickControls2 Network REQUIRED)

add_executable(hdmi_ui_v1_1
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
    src/unix_socket_data_source.cpp
    src/unix_socket_data_source.hpp
    src/line_buffer.hpp
    resources.qrc
)
target_include_directories(hdmi_ui_v1_1 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(hdmi_ui_v1_1 PRIVATE
    Qt5::Core
    Qt5::Gui
    Qt5::Qml
    Qt5::Quick
    Qt5::QuickControls2
    Qt5::Network
)

enable_testing()

# ---- Qt-free contract + integrity tests: build with only a C++17 toolchain
# (no Qt), so the frozen contract, sequence monitor, staleness window, mock, and
# socket line-framing are verified on the host before any Qt build. ----
add_executable(test_contract tests/test_contract.cpp)
target_include_directories(test_contract PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_test(NAME contract COMMAND test_contract)

add_executable(test_sequence_monitor tests/test_sequence_monitor.cpp)
target_include_directories(test_sequence_monitor PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_test(NAME sequence_monitor COMMAND test_sequence_monitor)

add_executable(test_stale tests/test_stale.cpp)
target_include_directories(test_stale PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_test(NAME stale COMMAND test_stale)

add_executable(test_line_buffer tests/test_line_buffer.cpp)
target_include_directories(test_line_buffer PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_test(NAME line_buffer COMMAND test_line_buffer)

# The mock is Qt-free (its wall-clock timestamp is the only non-deterministic
# field); it compiles and runs without Qt.
add_executable(test_mock
    tests/test_mock.cpp
    src/mock_data_source.cpp
    src/mock_data_source.hpp
)
target_include_directories(test_mock PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_test(NAME mock COMMAND test_mock)

# ---- Qt-dependent test (JSON parsing needs QJsonDocument / Qt5::Core). ----
add_executable(test_json_result_frame
    tests/test_json_result_frame.cpp
    src/json_result_frame.cpp
    src/json_result_frame.hpp
)
target_include_directories(test_json_result_frame PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(test_json_result_frame PRIVATE Qt5::Core)
add_test(NAME json_result_frame COMMAND test_json_result_frame)
