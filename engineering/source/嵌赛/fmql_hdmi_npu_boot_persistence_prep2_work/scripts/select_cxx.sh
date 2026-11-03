#!/usr/bin/env bash
# select_cxx.sh -- 板端 C++ 编译器选择共享助手（PREP1 缺陷修复）。
#
# 选择顺序：1. g++  2. c++  3. aarch64-linux-gnu-g++
# 找到第一个可用的打印其命令名（exit 0）。
# 三者全部缺失则打印 CXX_NOT_FOUND 并 exit 1 —— 绝不假装编译成功、绝不误报完成。
#
# 用法：
#   直接运行：  bash select_cxx.sh              -> stdout 输出 g++/c++/aarch64-linux-gnu-g++，或 CXX_NOT_FOUND
#   被 source： source select_cxx.sh && select_cxx
#
# 说明：本主机（Windows）没有任何 C/C++ 编译器，因此本脚本的选择逻辑通过 mock PATH 验证，
#       见 host_tests/test_select_cxx.sh；板上真实编译是未来用户步骤。

select_cxx() {
    local cand
    for cand in g++ c++ aarch64-linux-gnu-g++; do
        if command -v "$cand" >/dev/null 2>&1; then
            printf '%s' "$cand"
            return 0
        fi
    done
    return 1
}

# 直接运行（非 source）时：打印选择结果。
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    if cxx="$(select_cxx)"; then
        printf '%s\n' "$cxx"
        exit 0
    fi
    printf 'CXX_NOT_FOUND\n'
    exit 1
fi
