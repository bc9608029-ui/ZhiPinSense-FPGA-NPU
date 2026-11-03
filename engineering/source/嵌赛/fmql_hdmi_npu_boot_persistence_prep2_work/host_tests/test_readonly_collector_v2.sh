#!/usr/bin/env bash
# test_readonly_collector_v2.sh -- collect_fmql_boot_state_v2.sh 修订项静态断言（剥 # 注释后）。
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V2="$HERE/../scripts/collect_fmql_boot_state_v2.sh"
[ -f "$V2" ] || { echo "FATAL: missing $V2"; exit 1; }
body="$(grep -vE '^[[:space:]]*#' "$V2")"

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

has() { printf '%s\n' "$body" | grep -qE "$1"; }   # 在正文字符串中查找（管道，而非当文件名）

# 修复1：无旧 "0x%s 作用于 $v" 双前缀缺陷；使用 normalize_hex
if has 'printf .*0x%s.*\$v'; then bad "old 0x%s-on-\$v bug present"; else ok "no old 0x%s-on-\$v bug"; fi
if has 'normalize_hex[ (]'; then ok "uses normalize_hex"; else bad "missing normalize_hex"; fi
if has 'normalize_devmem_value\.sh'; then ok "sources normalize_devmem_value.sh"; else bad "does not source normalize helper"; fi
if has 'normalize_hex "\$raw"'; then ok "frame_ctrl read normalizes raw"; else bad "frame_ctrl read does not normalize"; fi

# 修订2：新增采集项
has 'lsblk -f' && ok "has lsblk -f" || bad "missing lsblk -f"
has 'modinfo' && ok "has modinfo" || bad "missing modinfo"
has '/usr/src' && ok "enumerates /usr/src" || bad "missing /usr/src"
has '/lib/modules' && ok "enumerates /lib/modules" || bad "missing /lib/modules"
has '/etc/fw_env\.config' && ok "fw_printenv config guard" || bad "missing fw_printenv config guard"

# 红线
if has 'systemctl[[:space:]]+(enable|start|restart)'; then bad "systemctl enable/start present"; else ok "no systemctl enable/start"; fi
if has '\breboot\b'; then bad "reboot present"; else ok "no reboot"; fi
if has 'pkill|killall'; then bad "pkill/killall present"; else ok "no pkill/killall"; fi

echo
echo "RESULT test_readonly_collector_v2.sh PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
