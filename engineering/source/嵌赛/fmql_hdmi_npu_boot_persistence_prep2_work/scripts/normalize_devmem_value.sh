#!/usr/bin/env bash
# normalize_devmem_value.sh -- devmem/十六进制值归一化共享助手。
#
# 背景（PREP1 缺陷修复）：PREP1 曾对已带 0x 前缀的值再拼 "0x%s"，产出 "0x0x20230218"。
# 本助手先剥离所有前导 0x/0X，再统一补一个 0x 前缀并转小写，杜绝双前缀复发。
#
# 接受输入：20230218、0x20230218、0X20230218、任意大小写、首尾空白（含换行/回车）。
# 归一化输出：小写 0x 前缀形式，例如 0x20230218。
#
# 用法：
#   直接运行：  bash normalize_devmem_value.sh 0x20230218     -> stdout 输出 0x20230218，exit 0
#               bash normalize_devmem_value.sh 0XDEADBEEF     -> stdout 输出 0xdeadbeef，exit 0
#   被 source： source normalize_devmem_value.sh && normalize_hex "DEADBEEF"
#
# 退出码：0 = 归一化成功；1 = 非法输入（空 / 非十六进制 / 含内部空白 / 多 token）；2 = 用法错误。

normalize_hex() {
    local raw="$1"
    # 1) 去掉首尾空白（含 CR/LF）
    raw="$(printf '%s' "$raw" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [ -n "$raw" ] || return 1
    # 2) 拒绝含内部空白的多 token（如 "1234 5678"）
    case "$raw" in
        *[[:space:]]*) return 1 ;;
    esac
    # 3) 循环剥离所有前导 0x/0X（修复 0x0x 双前缀）
    while :; do
        case "$raw" in
            0x*) raw="${raw#0x}" ;;
            0X*) raw="${raw#0X}" ;;
            *) break ;;
        esac
    done
    # 4) 校验为纯十六进制
    case "$raw" in
        ''|*[!0-9a-fA-F]*) return 1 ;;
    esac
    # 5) 转小写 + 补 0x
    printf '0x%s' "$(printf '%s' "$raw" | tr 'A-F' 'a-f')"
    return 0
}

# 直接运行（非 source）时：归一化第一个参数。
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    set -u
    if [ $# -lt 1 ]; then
        printf 'usage: normalize_devmem_value.sh <hex-value>\n' >&2
        exit 2
    fi
    if out="$(normalize_hex "$1")"; then
        printf '%s\n' "$out"
        exit 0
    fi
    printf 'INVALID_HEX_VALUE\n' >&2
    exit 1
fi
