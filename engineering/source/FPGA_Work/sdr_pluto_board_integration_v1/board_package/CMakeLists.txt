# CMake build for the Gate 1-5 board programs (secondary to build_on_board.sh,
# which is the authoritative board build).  Requires libiio via pkg-config.
cmake_minimum_required(VERSION 3.10)
project(sdr_pluto_board_integration CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()
add_compile_options(-Wall -Wextra -Werror)

find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBIIO REQUIRED libiio)

add_library(sdr_adapter_common STATIC
    ../sdr_adapter/pluto_device_libiio.cpp
    ../sdr_adapter/pluto_tx.cpp
    ../sdr_adapter/sample_rate_negotiate.cpp
    ../sdr_adapter/resampler.cpp)
target_include_directories(sdr_adapter_common PUBLIC
    ../sdr_adapter ${LIBIIO_INCLUDE_DIRS})
target_compile_definitions(sdr_adapter_common PUBLIC SDR_ADAPTER_HAVE_LIBIIO)
target_link_libraries(sdr_adapter_common PUBLIC ${LIBIIO_LIBRARIES})

foreach(prog board_detect_pluto board_rx_only board_digital_loopback
             board_rf_loopback board_resampler_test)
    add_executable(${prog} ${prog}.cpp)
    target_link_libraries(${prog} sdr_adapter_common)
endforeach()
