#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_no_forbidden_ops.py -- 静态扫描 scripts/ 全部脚本（含 .cpp），确认不含任何
写启动介质/Flash/FPGA 配置/系统服务的危险操作。

红线：包内绝不允许出现自动烧写、自动替换 BOOT.bin、自动 systemd enable、
      U-Boot saveenv、fpga load、写 /dev/mem|/dev/xdevcfg|块设备、写 FPGA Manager sysfs、
      remount rw、向启动分区 cp 等。本脚本只做静态扫描，不执行任何脚本。
"""
import re
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")

# 需要扫描的脚本文件（相对 scripts/）
FILES = [
    "normalize_devmem_value.sh",
    "select_cxx.sh",
    "collect_fmql_boot_state_v2.sh",
    "collect_sd_boot_partition_ro.sh",
    "read_display_registers_ro.cpp",
]

# 禁止模式：(名称, 正则)。全部大小写不敏感。
FORBIDDEN = [
    ("dd of= 写设备",            r"\bdd\s+[^\n]*\bof\s*="),
    ("flashcp 烧写",             r"\bflashcp\b"),
    ("fw_setenv 写 U-Boot 环境",  r"\bfw_setenv\b"),
    ("saveenv 保存 U-Boot 环境",  r"\bsaveenv\b"),
    ("editenv 编辑 U-Boot 环境",  r"\beditenv\b"),
    ("fpga load 写 FPGA",        r"\bfpga\s+load\b"),
    ("fpgautil 写 FPGA Manager", r"\bfpgautil\b"),
    ("mmc write U-Boot 写",      r"\bmmc\s+write\b"),
    ("fatwrite 写 FAT",          r"\bfatwrite\b"),
    ("sf erase/write/program",   r"\bsf\s+(erase|write|program)\b"),
    ("nand erase/write",         r"\bnand\s+(erase|write)\b"),
    ("mw 内存写 (U-Boot)",        r"\bmw\s+[0-9a-fA-FxX]"),
    ("systemctl enable/start",   r"\bsystemctl\s+(enable|start|restart)\b"),
    ("reboot",                   r"\breboot\b"),
    ("pkill/killall",            r"\bpkill\b|\bkillall\b"),
    ("remount",                  r"\bremount\b"),
    ("mount -o rw",              r"mount\s+-o\s*rw"),
    ("sync 刷写",                 r"\bsync\b"),
    ("open /dev/mem O_WRONLY|O_RDWR", r"open\(\s*\"/dev/mem\"[^)]*O_(WRONLY|RDWR)"),
    ("重定向写 /dev/mem",          r">>?\s*/dev/mem"),
    ("重定向写 /dev/xdevcfg",      r">>?\s*/dev/xdevcfg"),
    ("tee 写 /dev/ 块设备",        r"\btee\s+(?:-a\s+)?/dev/"),
    ("mmap PROT_WRITE",           r"\bmmap\([^)]*PROT_WRITE"),
    ("写 /sys (FPGA Manager 等)",  r">>?\s*/sys/|tee\s+/sys/"),
    ("cp 到块设备",               r"\bcp\s+[^\n]*\s/dev/"),
]

# shell 注释剥离：整行 # 注释（不剥内联 #，避免破坏 ${f#...} / $#）。
def strip_shell(src):
    return "\n".join(
        ln for ln in src.splitlines() if not re.match(r"^\s*#", ln)
    )

# C++ 注释剥离：// 与 /* */
def strip_cpp(src):
    s = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//.*", "", s)

def strip_comments(path, src):
    if path.endswith(".cpp"):
        return strip_cpp(src)
    return strip_shell(src)

def main():
    passed = 0
    failed = 0
    all_clean = True
    for fn in FILES:
        path = os.path.join(SCRIPTS, fn)
        if not os.path.isfile(path):
            print("FAIL: missing file %s" % path)
            failed += 1
            all_clean = False
            continue
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        body = strip_comments(fn, raw)
        for name, pat in FORBIDDEN:
            m = re.search(pat, body, flags=re.I)
            if m:
                print("FAIL: %-28s %s  (match: %r)" % (fn, name, m.group(0)[:60]))
                failed += 1
                all_clean = False
            else:
                passed += 1

    # 正向确认：SD 分区采集脚本必须用只读挂载
    sd = os.path.join(SCRIPTS, "collect_sd_boot_partition_ro.sh")
    if os.path.isfile(sd):
        with open(sd, "r", encoding="utf-8") as f:
            body = strip_shell(f.read())
        if re.search(r"mount\s+-o\s+ro\b", body):
            passed += 1
        else:
            print("FAIL: collect_sd_boot_partition_ro.sh missing 'mount -o ro'")
            failed += 1
            all_clean = False

    print("RESULT test_no_forbidden_ops.py PASS=%d FAIL=%d" % (passed, failed))
    sys.exit(0 if all_clean else 1)

if __name__ == "__main__":
    main()
