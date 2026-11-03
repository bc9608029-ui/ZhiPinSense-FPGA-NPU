# CMake build for the twelve-class NPU gates (Gate 7 / Gate 9), on the FMQL30TAI
# board against the iCraft 3.39 SDK.
#
#   Gate 7  board_gate7_12class_npu        NPU only (iCraft backends, no libiio)
#   Gate 9  board_gate9_full_chain_12class NPU + libiio (full SDR->NPU->UI chain)
#
# Gate 7 is configured by default and does NOT require libiio or pkg-config (the
# board image has neither).  Gate 9 additionally links libiio and is configured
# only when -DBUILD_GATE9=ON, which in turn requires -DLIBIIO_ROOT=/path/to/libiio
# (e.g. /tmp/sdr_pluto_gate1_5/libiio-arm64).  See build_npu_on_board.sh, which
# passes these flags.
#
# The on-chip iCraft 3.39 package installs icraft-zg330backend*.cmake and
# icraft-hostbackend*.cmake under /usr/cmake, importing Icraft::ZG330Backend /
# Icraft::HostBackend.  HostBackend is required because the compiled model's
# Input/Output ops are @hostt while its 128 compute HardOps are @zhuget(330).
cmake_minimum_required(VERSION 3.10)
project(sdr_full_chain_12class_npu LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# GNU dialect is required by the board toolchain (build with -std=gnu++17).
set(CMAKE_CXX_EXTENSIONS ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Gate 9 is opt-in: it needs libiio, which the board image does not ship and must
# be located via -DLIBIIO_ROOT.  Gate 7 configures without either libiio or
# pkg-config.
option(BUILD_GATE9 "Build Gate 9 (full chain); requires -DLIBIIO_ROOT" OFF)
option(BUILD_GATE10 "Build Gate 10 (12-class RF self-test); requires -DLIBIIO_ROOT" OFF)

find_package(icraft-zg330backend REQUIRED)
find_package(icraft-hostbackend REQUIRED)

# ---- Gate 7: NPU partition alone (no libiio, no SDR sources) ------------------
add_executable(board_gate7_12class_npu board_gate7_12class_npu.cpp)
target_compile_options(board_gate7_12class_npu PRIVATE -std=gnu++17)
target_include_directories(board_gate7_12class_npu PRIVATE
    ../sdr_adapter ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(board_gate7_12class_npu PRIVATE
    Icraft::ZG330Backend Icraft::HostBackend pthread dl)

# ---- Gate 9: full chain (NPU + libiio SDR adapter) ----------------------------
if(BUILD_GATE9)
    if(NOT LIBIIO_ROOT)
        message(FATAL_ERROR
            "BUILD_GATE9=ON requires -DLIBIIO_ROOT=/path/to/libiio "
            "(e.g. /tmp/sdr_pluto_gate1_5/libiio-arm64)")
    endif()

    # Explicit-prefix lookup only: the board has no system libiio and no
    # pkg-config, so search exactly ${LIBIIO_ROOT}/{include,lib} and fail closed
    # (FATAL_ERROR) if either the header or the library is missing.
    find_path(LIBIIO_INCLUDE_DIR iio.h
        HINTS "${LIBIIO_ROOT}/include" NO_DEFAULT_PATH)
    find_library(LIBIIO_LIBRARY NAMES iio
        HINTS "${LIBIIO_ROOT}/lib" NO_DEFAULT_PATH)

    if(NOT LIBIIO_INCLUDE_DIR)
        message(FATAL_ERROR
            "libiio header not found: expected ${LIBIIO_ROOT}/include/iio.h "
            "(LIBIIO_ROOT=${LIBIIO_ROOT})")
    endif()
    if(NOT LIBIIO_LIBRARY)
        message(FATAL_ERROR
            "libiio library not found: expected ${LIBIIO_ROOT}/lib/libiio.so "
            "(LIBIIO_ROOT=${LIBIIO_ROOT})")
    endif()
    message(STATUS "libiio: include=${LIBIIO_INCLUDE_DIR} lib=${LIBIIO_LIBRARY}")

    set(SDR_ADAPTER_SRC
        ../sdr_adapter/pluto_device_libiio.cpp
        ../sdr_adapter/pluto_tx.cpp
        ../sdr_adapter/sample_rate_negotiate.cpp
        ../sdr_adapter/resampler.cpp)

    add_executable(board_gate9_full_chain_12class
        board_gate9_full_chain_12class.cpp ${SDR_ADAPTER_SRC})
    target_compile_options(board_gate9_full_chain_12class PRIVATE -std=gnu++17)
    target_compile_definitions(board_gate9_full_chain_12class PRIVATE SDR_ADAPTER_HAVE_LIBIIO)
    target_include_directories(board_gate9_full_chain_12class PRIVATE
        ../sdr_adapter ${CMAKE_CURRENT_SOURCE_DIR} ${LIBIIO_INCLUDE_DIR})
    target_link_libraries(board_gate9_full_chain_12class PRIVATE
        Icraft::ZG330Backend Icraft::HostBackend ${LIBIIO_LIBRARY} pthread dl)
    # Bake the libiio search path into the binary so it runs without
    # LD_LIBRARY_PATH (run_gate9.sh also sets LD_LIBRARY_PATH as a second layer).
    set_target_properties(board_gate9_full_chain_12class PROPERTIES
        BUILD_RPATH "${LIBIIO_ROOT}/lib"
        INSTALL_RPATH "${LIBIIO_ROOT}/lib")
endif()

# ---- Gate 10: twelve-class RF self-test (NPU + libiio + waveform generator) --
if(BUILD_GATE10)
    if(NOT LIBIIO_ROOT)
        message(FATAL_ERROR
            "BUILD_GATE10=ON requires -DLIBIIO_ROOT=/path/to/libiio "
            "(e.g. /tmp/sdr_pluto_gate1_5/libiio-arm64)")
    endif()

    find_path(LIBIIO_INCLUDE_DIR iio.h
        HINTS "${LIBIIO_ROOT}/include" NO_DEFAULT_PATH)
    find_library(LIBIIO_LIBRARY NAMES iio
        HINTS "${LIBIIO_ROOT}/lib" NO_DEFAULT_PATH)

    if(NOT LIBIIO_INCLUDE_DIR)
        message(FATAL_ERROR
            "libiio header not found: expected ${LIBIIO_ROOT}/include/iio.h "
            "(LIBIIO_ROOT=${LIBIIO_ROOT})")
    endif()
    if(NOT LIBIIO_LIBRARY)
        message(FATAL_ERROR
            "libiio library not found: expected ${LIBIIO_ROOT}/lib/libiio.so "
            "(LIBIIO_ROOT=${LIBIIO_ROOT})")
    endif()
    message(STATUS "libiio: include=${LIBIIO_INCLUDE_DIR} lib=${LIBIIO_LIBRARY}")

    set(SDR_ADAPTER_SRC
        ../sdr_adapter/pluto_device_libiio.cpp
        ../sdr_adapter/pluto_tx.cpp
        ../sdr_adapter/sample_rate_negotiate.cpp
        ../sdr_adapter/resampler.cpp)

    add_executable(board_gate10_selftest_12class
        board_gate10_selftest_12class.cpp ${SDR_ADAPTER_SRC})
    target_compile_options(board_gate10_selftest_12class PRIVATE -std=gnu++17)
    target_compile_definitions(board_gate10_selftest_12class PRIVATE SDR_ADAPTER_HAVE_LIBIIO)
    target_include_directories(board_gate10_selftest_12class PRIVATE
        ../sdr_adapter ${CMAKE_CURRENT_SOURCE_DIR} ${LIBIIO_INCLUDE_DIR})
    target_link_libraries(board_gate10_selftest_12class PRIVATE
        Icraft::ZG330Backend Icraft::HostBackend ${LIBIIO_LIBRARY} pthread dl)
    set_target_properties(board_gate10_selftest_12class PROPERTIES
        BUILD_RPATH "${LIBIIO_ROOT}/lib"
        INSTALL_RPATH "${LIBIIO_ROOT}/lib")
endif()
