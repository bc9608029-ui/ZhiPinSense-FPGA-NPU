#!/usr/bin/env bash
# run_all.sh -- PREP2 离线自测聚合运行器。
# 依次运行全部主机测试，汇总 PASS/FAIL，任一失败则整体退出非零。
# 用法：bash host_tests/run_all.sh  （或 cd host_tests && bash run_all.sh）
set -u
export PYTHONIOENCODING=utf-8   # 让 Python 测试输出 UTF-8（重定向到文件/终端时避免 GBK 乱码）
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python}"
if ! command -v "$PY" >/dev/null 2>&1; then
    PY="${PYTHON:-python3}"
fi

TOTAL_PASS=0
TOTAL_FAIL=0
run() {
    local name="$1"; shift
    echo
    echo "================ $name ================"
    local out rc
    out="$("$@" 2>&1)"; rc=$?
    printf '%s\n' "$out"
    local p f
    p="$(printf '%s\n' "$out" | grep -oE 'PASS=[0-9]+' | awk -F= '{s+=$2} END{print s+0}')"
    f="$(printf '%s\n' "$out" | grep -oE 'FAIL=[0-9]+' | awk -F= '{s+=$2} END{print s+0}')"
    TOTAL_PASS=$((TOTAL_PASS + p))
    TOTAL_FAIL=$((TOTAL_FAIL + f))
    if [ $rc -eq 0 ]; then
        echo ">>> $name : OK (pass=$p fail=$f)"
    else
        echo ">>> $name : FAILED (pass=$p fail=$f rc=$rc)"
    fi
}

run "test_normalize_devmem"      bash "$HERE/test_normalize_devmem.sh"
run "test_select_cxx"            bash "$HERE/test_select_cxx.sh"
run "test_collect_scripts_static" bash "$HERE/test_collect_scripts_static.sh"
run "test_readonly_collector_v2" bash "$HERE/test_readonly_collector_v2.sh"
run "test_sd_partition_ro"       bash "$HERE/test_sd_partition_ro.sh"
run "test_no_forbidden_ops"      "$PY" "$HERE/test_no_forbidden_ops.py"
run "test_bootbin_bif_audit"     "$PY" "$HERE/test_bootbin_bif_audit.py"

echo
echo "================ AGGREGATE ================"
echo "RESULT run_all.sh TOTAL_PASS=$TOTAL_PASS TOTAL_FAIL=$TOTAL_FAIL"
[ "$TOTAL_FAIL" -eq 0 ]
