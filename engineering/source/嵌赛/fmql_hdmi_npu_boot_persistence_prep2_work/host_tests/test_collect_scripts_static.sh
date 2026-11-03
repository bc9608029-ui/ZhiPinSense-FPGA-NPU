#!/usr/bin/env bash
# test_collect_scripts_static.sh -- 脚本语法检查 + read_display_registers_ro.cpp 只读安全静态断言（Python）。
# 本主机无 C/C++ 编译器：cpp 仅做静态检查（括号配平 + O_RDONLY/PROT_READ + 无 PROT_WRITE + 无写 /dev/mem），
# 不声称编译成功。
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
S="$ROOT/scripts"

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

echo "=== bash -n 语法检查 ==="
for f in normalize_devmem_value.sh select_cxx.sh collect_fmql_boot_state_v2.sh collect_sd_boot_partition_ro.sh; do
    if bash -n "$S/$f" 2>/tmp/bashn_err; then ok "syntax $f"; else bad "syntax $f: $(cat /tmp/bashn_err)"; fi
done

echo "=== read_display_registers_ro.cpp 只读安全静态断言（Python，静默执行，只回传计数）==="
PY="${PYTHON:-/d/Anaconda/python}"
cpp_out="$("$PY" -I - "$S/read_display_registers_ro.cpp" <<'PY'
import re, sys
cpp = open(sys.argv[1], encoding='utf-8').read()
nocomment = re.sub(r'/\*.*?\*/', '', cpp, flags=re.S)
nocomment = re.sub(r'//.*', '', nocomment)
p = f = 0
def check(name, cond):
    global p, f
    if cond: p += 1
    else: f += 1
    print(('PASS: ' if cond else 'FAIL: ') + name)
check('O_RDONLY present', 'O_RDONLY' in nocomment)
check('PROT_READ present', 'PROT_READ' in nocomment)
check('no PROT_WRITE', 'PROT_WRITE' not in nocomment)
check('no O_WRONLY open /dev/mem', not re.search(r'open\("/dev/mem"[^)]*O_WRONLY', nocomment))
check('no O_RDWR open /dev/mem', not re.search(r'open\("/dev/mem"[^)]*O_RDWR', nocomment))
for a, b in (('(', ')'), ('[', ']'), ('{', '}')):
    check('brace %s%s balanced' % (a, b), nocomment.count(a) == nocomment.count(b))
check('mmap present', 'mmap(' in nocomment)
check('munmap present', 'munmap(' in nocomment)
print('CPP_TOTAL pass=%d fail=%d' % (p, f))
sys.exit(1 if f else 0)
PY
)"
cpp_rc=$?
echo "$cpp_out"
cpp_pass="$(printf '%s\n' "$cpp_out" | sed -n 's/.*CPP_TOTAL pass=\([0-9]*\).*/\1/p')"
cpp_fail="$(printf '%s\n' "$cpp_out" | sed -n 's/.*fail=\([0-9]*\).*/\1/p')"
PASS=$((PASS + ${cpp_pass:-0}))
FAIL=$((FAIL + ${cpp_fail:-0}))
if [ $cpp_rc -eq 0 ]; then ok "cpp static checks overall"; else bad "cpp static checks overall"; fi

echo
echo "RESULT test_collect_scripts_static.sh PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
