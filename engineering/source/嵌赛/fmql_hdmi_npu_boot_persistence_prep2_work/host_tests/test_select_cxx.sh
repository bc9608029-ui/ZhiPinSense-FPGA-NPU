#!/usr/bin/env bash
# test_select_cxx.sh -- 板端编译器选择逻辑测试（mock PATH 注入假编译器；主机无 C/C++ 编译器）。
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$HERE/../scripts/select_cxx.sh"
[ -f "$HELPER" ] || { echo "FATAL: missing $HELPER"; exit 1; }
BASH_BIN="$(command -v bash)"   # 在覆盖 PATH 之前捕获绝对 bash 路径（覆盖后 'bash' 词无法解析）
. "$HELPER"

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

mkmock() { # $1=dir  $@=names
    local dir="$1"; shift
    mkdir -p "$dir"
    for n in "$@"; do
        printf '#!/usr/bin/env bash\nexit 0\n' > "$dir/$n"
        chmod +x "$dir/$n"
    done
}

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# 1) 三者全有 → g++（顺序优先）
mkmock "$TMP/all" g++ c++ aarch64-linux-gnu-g++
if out="$(PATH="$TMP/all" select_cxx)" && [ "$out" = "g++" ]; then ok "all-present -> g++"; else bad "all-present got '$out'"; fi

# 2) 仅 c++ → c++
mkmock "$TMP/cxx" c++
if out="$(PATH="$TMP/cxx" select_cxx)" && [ "$out" = "c++" ]; then ok "only c++ -> c++"; else bad "only c++ got '$out'"; fi

# 3) 仅 aarch64 → aarch64
mkmock "$TMP/aarch" aarch64-linux-gnu-g++
if out="$(PATH="$TMP/aarch" select_cxx)" && [ "$out" = "aarch64-linux-gnu-g++" ]; then ok "only aarch64 -> aarch64-linux-gnu-g++"; else bad "only aarch64 got '$out'"; fi

# 4) g++ 优先于 c++
mkmock "$TMP/gc" g++ c++
if out="$(PATH="$TMP/gc" select_cxx)" && [ "$out" = "g++" ]; then ok "g++ wins over c++"; else bad "g++/c++ got '$out'"; fi

# 5) 全缺 → 函数返回非零（绝不假装成功）
mkdir -p "$TMP/empty"
if out="$(PATH="$TMP/empty" select_cxx 2>/dev/null)"; then bad "all-missing did not fail (got '$out')"; else ok "all-missing -> fail (no false completion)"; fi

# 6) CLI 全缺 → stdout CXX_NOT_FOUND + exit!=0
if out="$(PATH="$TMP/empty" "$BASH_BIN" "$HELPER" 2>/dev/null)"; then
    bad "CLI all-missing rc=0 out='$out'"
else
    if [ "$out" = "CXX_NOT_FOUND" ]; then ok "CLI all-missing prints CXX_NOT_FOUND (rc!=0)"; else bad "CLI all-missing out='$out'"; fi
fi

# 7) CLI 有 g++ → 打印 g++ (rc=0)
if out="$(PATH="$TMP/all" "$BASH_BIN" "$HELPER" 2>/dev/null)" && [ "$out" = "g++" ]; then ok "CLI with g++ prints g++ (rc=0)"; else bad "CLI with g++ out='$out'"; fi

echo
echo "RESULT test_select_cxx.sh PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
