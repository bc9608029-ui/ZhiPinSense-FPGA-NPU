#!/usr/bin/env python3
# test_artifact_identity.py -- 位流/启动镜像身份核验自测（纯离线，Windows 主机可跑）。
#
# 覆盖（真实解析，不止 grep）：
#   [A1] verify_boot_artifacts.py 对真实合并位流解析：设计名/part/同步字/SHA 精确断言
#   [A2] 对 vendor BOOT.bin 解析：魔数 0xAA995566 + ident FMSH + 加密字=0
#   [A3] 负例：garbage .bit → 非零退出（fail-closed）
#   [A4] 负例：garbage BOOT.bin → 非零退出
#   [A5] bit-in-bootbin 负例：不匹配位流 → FAIL
#   [A6] 方案 B 候选 download.bit 与源位流字节一致（SHA 相同）
#   [A7] candidate/SHA256SUMS.txt 内容匹配
#
# 运行：python host_tests/test_artifact_identity.py

import hashlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = os.path.join(ROOT, 'scripts', 'verify_boot_artifacts.py')

BIT = os.environ.get(
    'FMQL_BIT',
    r'F:\FPGA_Work\sdr_full_chain_12class_combined_v1\outputs\smoke_v1\bitstream\combined_npu_hdmi_disable_icap.bit')
VENDOR_BOOTBIN = os.path.join(ROOT, '_evidence', 'vendor_docs', 'vendor_lite_boot', 'BOOT.bin')
CAND = os.path.join(ROOT, 'candidate', 'download.bit')
CAND_SUMS = os.path.join(ROOT, 'candidate', 'SHA256SUMS.txt')

EXPECT_SHA = '22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9'
EXPECT_DESIGN = 'jpl_ddr_mandatory_core_top_combined'
EXPECT_PART = '7z030'

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print('PASS:', msg)


def bad(msg):
    global FAIL
    FAIL += 1
    print('FAIL:', msg)


def run(args):
    return subprocess.run([sys.executable, PY] + args, capture_output=True, text=True)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


# A1
if not os.path.exists(BIT):
    print('SKIP A1 (bitstream not present; set FMQL_BIT)')
else:
    r = run(['bit-info', BIT])
    out = r.stdout
    if r.returncode == 0 and 'design_name=%s' % EXPECT_DESIGN in out \
       and 'part=%s' % EXPECT_PART in out and 'sync_word=0xAA995566' in out \
       and 'sha256=%s' % EXPECT_SHA in out:
        ok('A1 bit-info exact identity (design/part/sync/sha)')
    else:
        bad('A1 bit-info identity mismatch rc=%d\n%s' % (r.returncode, out))

# A2
if not os.path.exists(VENDOR_BOOTBIN):
    print('SKIP A2 (vendor BOOT.bin absent)')
else:
    r = run(['bootbin-info', VENDOR_BOOTBIN])
    out = r.stdout
    # ident 字段两种字节序均合法：'FMSH' 或小端字 0x464D5348 的字节串 'HSMF'。
    if r.returncode == 0 and 'magic=665599aa' in out \
       and ('ident=FMSH' in out or 'ident=HSMF' in out) \
       and 'encryption_word=0x00000000' in out and 'encrypted=False' in out \
       and 'BOOTBIN_INFO: OK' in out:
        ok('A2 BOOT.bin header (magic/FMSH-ident/encryption=0)')
    else:
        bad('A2 BOOT.bin header mismatch rc=%d\n%s' % (r.returncode, out))

# A3 garbage .bit
with tempfile.NamedTemporaryFile('wb', delete=False, suffix='.bit') as f:
    f.write(b'\x00' * 64)
    gbit = f.name
r = run(['bit-info', gbit])
if r.returncode != 0:
    ok('A3 garbage .bit fails closed (rc=%d)' % r.returncode)
else:
    bad('A3 garbage .bit did not fail (rc=0)')
os.unlink(gbit)

# A4 garbage BOOT.bin
with tempfile.NamedTemporaryFile('wb', delete=False) as f:
    f.write(b'\x00' * 128)
    gboot = f.name
r = run(['bootbin-info', gboot])
if r.returncode != 0:
    ok('A4 garbage BOOT.bin fails closed (rc=%d)' % r.returncode)
else:
    bad('A4 garbage BOOT.bin did not fail (rc=0)')
os.unlink(gboot)

# A5 bit-in-bootbin negative (vendor BOOT.bin does NOT embed our bitstream)
if os.path.exists(VENDOR_BOOTBIN) and os.path.exists(BIT):
    r = run(['bit-in-bootbin', VENDOR_BOOTBIN, BIT])
    if r.returncode != 0 and 'NOT found' in r.stdout:
        ok('A5 bit-in-bootbin negative: our bitstream not in vendor BOOT.bin')
    else:
        bad('A5 unexpected bit-in-bootbin result rc=%d\n%s' % (r.returncode, r.stdout))

# A6 candidate download.bit == source bit
if os.path.exists(CAND) and os.path.exists(BIT):
    if sha256_file(CAND) == sha256_file(BIT) == EXPECT_SHA:
        ok('A6 candidate download.bit byte-identical (SHA=%s)' % EXPECT_SHA[:16])
    else:
        bad('A6 candidate SHA mismatch: cand=%s src=%s' % (sha256_file(CAND), sha256_file(BIT)))
else:
    print('SKIP A6 (run scripts/build_candidate_image.sh first)')

# A7 SHA256SUMS.txt
if os.path.exists(CAND_SUMS):
    with open(CAND_SUMS) as f:
        line = f.read().strip()
    if line.endswith('download.bit') and EXPECT_SHA in line:
        ok('A7 candidate SHA256SUMS.txt matches')
    else:
        bad('A7 candidate SHA256SUMS.txt mismatch: %r' % line)
else:
    print('SKIP A7 (no candidate SHA256SUMS.txt)')

print()
print('RESULT test_artifact_identity.py PASS=%d FAIL=%d' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
