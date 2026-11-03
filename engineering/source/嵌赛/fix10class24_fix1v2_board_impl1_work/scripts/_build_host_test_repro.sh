#!/bin/bash
# 可复现 host 编译命令（fix1v2 board impl1 G2 链路测试）
# 在 WSL (Ubuntu, g++ 15.2.0) 下运行：bash scripts/_build_host_test_repro.sh
set -e
cd "$(dirname "$0")/.."    # -> work tree root
g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
    -o host_tests/bin/test_radioml_independent_rx \
    host_tests/test_radioml_independent_rx.cpp
echo "BUILD_RC=$?  ->  host_tests/bin/test_radioml_independent_rx"
