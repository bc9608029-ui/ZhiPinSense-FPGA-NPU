#!/usr/bin/env bash
# test_normalize_devmem.sh -- devmem 归一化正/负测试（真实调用 normalize_hex + CLI）。
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$HERE/../scripts/normalize_devmem_value.sh"
[ -f "$HELPER" ] || { echo "FATAL: missing $HELPER"; exit 1; }
. "$HELPER"

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

chk() { # $1=desc $2=input $3=expected
    local desc="$1" input="$2" exp="$3"
    if out="$(normalize_hex "$input")" && [ "$out" = "$exp" ]; then
        ok "$desc -> $out"
    else
        bad "$desc: got '${out:-<none>}' want '$exp'"
    fi
}
chkneg() { # $1=desc $2=input
    if normalize_hex "$2" >/dev/null 2>&1; then
        bad "$1: expected reject but got '$(normalize_hex "$2" 2>/dev/null)'"
    else
        ok "$1 (rejected)"
    fi
}

# 正例
chk "plain hex"            "20230218"        "0x20230218"
chk "0x prefix"            "0x20230218"      "0x20230218"
chk "0X prefix"            "0X20230218"      "0x20230218"
chk "upper no prefix"      "DEADBEEF"        "0xdeadbeef"
chk "upper 0x prefix"      "0xDEADBEEF"      "0xdeadbeef"
chk "leading whitespace"   "  0x20230218"    "0x20230218"
chk "trailing whitespace"  "0x20230218  "    "0x20230218"
chk "trailing newline"     "$(printf '0x20230218\n')" "0x20230218"
chk "mixed case"           "0xa1B2C3"        "0xa1b2c3"
# PREP1 缺陷回归：双 0x 前缀必须归一为一个
chk "double 0x regression" "0x0x20230218"    "0x20230218"
chk "double 0X regression" "0X0Xdeadbeef"    "0xdeadbeef"

# 负例（必须拒绝）
chkneg "empty"         ""
chkneg "only 0x"       "0x"
chkneg "non-hex xyz"   "xyz"
chkneg "space inside"  "1234 5678"
chkneg "0xGG"          "0xGG"
chkneg "negative"      "-1"
chkneg "decimal dot"   "1.5"
chkneg "trailing junk" "0x12g"

# CLI 直接运行（正）
cli_out="$(bash "$HELPER" "0XDEADBEEF" 2>/dev/null)"; cli_rc=$?
if [ $cli_rc -eq 0 ] && [ "$cli_out" = "0xdeadbeef" ]; then ok "CLI 0XDEADBEEF -> 0xdeadbeef (rc=0)"; else bad "CLI rc=$cli_rc out='$cli_out'"; fi
# CLI 直接运行（负）
bash "$HELPER" "nothex" >/dev/null 2>&1
if [ $? -ne 0 ]; then ok "CLI invalid input exits non-zero"; else bad "CLI invalid input did not fail"; fi
# CLI 用法（无参数）
bash "$HELPER" >/dev/null 2>&1
if [ $? -eq 2 ]; then ok "CLI no-arg exits 2 (usage)"; else bad "CLI no-arg did not exit 2"; fi

echo
echo "RESULT test_normalize_devmem.sh PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
