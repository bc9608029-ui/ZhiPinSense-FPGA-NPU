#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_bootbin_bif_audit.py -- 离线证据一致性测试（只读，不生成/不部署任何镜像）：
  1) .bif 分区顺序/属性权威解析断言
  2) vendor BOOT.bin 头部（魔数/标识/加密字）+ 内嵌位流同步字/XLNX
  3) BOOT_Gen 组件 SHA == 审计文档冻结值，且与 vendor_lite_boot 同名组件字节一致
  4) 位流「不逐字存在」的诚实判定（设计名被剥离，但同步字存在）
  5) 工作位流 combined_npu_hdmi_disable_icap.bit 冻结 SHA
  6) PREP1 交付包冻结 SHA

路径可用环境变量覆盖（默认指向 PREP2/PREP1 工作目录与 F:/FPGA_Work）。
"""
import os
import sys
import hashlib

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.join(HERE, "..", "..")
BOOT_GEN = os.environ.get(
    "AUDIT_BOOT_GEN",
    r"F:\嵌赛\fmql_hdmi_npu_boot_persistence_prep2_work\_evidence\boot_gen_extract\BOOT_Gen",
)
VENDOR_LITE = os.environ.get(
    "AUDIT_VENDOR_LITE",
    r"F:\嵌赛\fmql_hdmi_npu_boot_persistence_prep1_work\_evidence\vendor_docs\vendor_lite_boot",
)
WORKING_BIT = os.environ.get(
    "AUDIT_WORKING_BIT",
    r"F:\FPGA_Work\sdr_full_chain_12class_combined_v1\outputs\smoke_v1\bitstream\combined_npu_hdmi_disable_icap.bit",
)
PREP1_PKG = os.environ.get(
    "AUDIT_PREP1_PKG",
    r"F:\嵌赛\fmql_hdmi_npu_boot_persistence_prep1_work\dist\fmql_hdmi_npu_boot_persistence_prep1_offline_20261021.tar.gz",
)

BIF_PATH = os.path.join(BOOT_GEN, "7030ai_psin.bif")
BOOTBIN_PATH = os.path.join(VENDOR_LITE, "BOOT.bin")

passed = 0
failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("PASS: %s" % name)
    else:
        failed += 1
        print("FAIL: %s %s" % (name, detail))

# ---- 1) .bif 解析 ----
check("bif 存在", os.path.isfile(BIF_PATH), BIF_PATH)
if os.path.isfile(BIF_PATH):
    bif = open(BIF_PATH, "r", encoding="utf-8", errors="replace").read()
    check("bif arch=fmql", "arch = fmql" in bif)
    check("bif split=false", "split = false" in bif)
    check("bif format=BIN", "format = BIN" in bif)
    # 分区顺序
    idx_fsbl = bif.find("FSBL251210_ddr400_demo.out")
    idx_bit  = bif.find("ai7030_edif_top.bit")
    idx_bl31 = bif.find("bl31.elf")
    idx_ub   = bif.find("u-boot")
    order_ok = -1 < idx_fsbl < idx_bit < idx_bl31 < idx_ub
    check("bif 分区顺序 FSBL<bit<bl31<u-boot", order_ok,
          "idx=%d,%d,%d,%d" % (idx_fsbl, idx_bit, idx_bl31, idx_ub))
    check("bif FSBL=bootloader,ps", "[bootloader, destination_device = ps]" in bif)
    check("bif bit=pl", "[destination_device = pl]" in bif)
    check("bif bl31=apu_0,ps", "[destination_cpu = apu_0, destination_device = ps]" in bif)
    check("bif fsbl_config apu_x32", "[fsbl_config]apu_x32" in bif)

# ---- 2) vendor BOOT.bin 头部 + 内嵌位流 ----
check("vendor BOOT.bin 存在", os.path.isfile(BOOTBIN_PATH), BOOTBIN_PATH)
if os.path.isfile(BOOTBIN_PATH):
    b = open(BOOTBIN_PATH, "rb").read()
    check("BOOT.bin 魔数 0xAA995566@0x20", b[0x20:0x24] == b"\x66\x55\x99\xaa",
          b[0x20:0x24].hex())
    check("BOOT.bin 标识 HSMF@0x24", b[0x24:0x28] == b"HSMF", b[0x24:0x28])
    check("BOOT.bin 加密字=0@0x28", b[0x28:0x2C] == b"\x00\x00\x00\x00", b[0x28:0x2C].hex())
    sync = b"\x66\x55\x99\xaa"
    check("BOOT.bin 含位流同步字 66 55 99 aa", sync in b)
    check("BOOT.bin 同步字@186864", b[186864:186868] == sync, b[186864:186868].hex())
    check("BOOT.bin XLNX@158888", b[158888:158892] == b"XLNX", b[158888:158892])
    check("BOOT.bin 不含明文设计名 ai7030", b"ai7030" not in b)

# ---- 3) BOOT_Gen 组件 SHA 冻结值 + 与 vendor_lite 字节一致 ----
FROZEN = {
    "7030ai_psin.bif": "2ac0ca602d2e1200cd92429880f7942aa52bd97007e678ef039f191393ab2389",
    "FSBL251210_ddr400_demo.out": "5501c470e07537a8fb369ae40641c20c16ab403fad558e65e0a4bbf380f2396f",
    "ai7030_edif_top.bit": "1405d7f1cb992d8f9c78e7b4bbe756faa96eeecb2ff4bdd0d253e92b191e2575",
    "bl31.elf": "fdcf0af48a7f9716f73a477c3cc1b4cd90c914fe0e5ad7acc5ab282660802303",
    "u-boot": "c4570e3e51128211905bdf20c7b7e0ea9cb7ca1492652a070ebdd985bc213e97",
}
VENDOR_CMP = ["FSBL251210_ddr400_demo.out", "bl31.elf", "u-boot"]
for name, want in FROZEN.items():
    p = os.path.join(BOOT_GEN, name)
    if not os.path.isfile(p):
        check("BOOT_Gen %s 存在" % name, False, p)
        continue
    got = sha256_of(p)
    check("BOOT_Gen %s SHA 冻结一致" % name, got == want, got)
    if name in VENDOR_CMP:
        vp = os.path.join(VENDOR_LITE, name)
        if os.path.isfile(vp):
            vs = sha256_of(vp)
            check("vendor_lite %s 字节一致" % name, vs == got, vs)
        else:
            check("vendor_lite %s 存在" % name, False, vp)

# ---- 4) 位流「不逐字存在」诚实判定 ----
def bit_payload(path):
    d = open(path, "rb").read()
    i = d.find(b"\xaa\x99\x55\x66")
    return d[i + 4:] if i >= 0 else b""

if os.path.isfile(BOOTBIN_PATH):
    boot = open(BOOTBIN_PATH, "rb").read()
    cand1 = os.path.join(BOOT_GEN, "ai7030_edif_top.bit")
    cand2 = os.path.join(VENDOR_LITE, "ai7030_top_disable_icap.bit")
    for label, p in (("edif_top", cand1), ("top_disable_icap", cand2)):
        if os.path.isfile(p):
            pl = bit_payload(p)
            check("候选位流 %s 载荷非空" % label, len(pl) > 0)
            # 诚实结论：打包位序变换后，原始载荷不逐字出现在 BOOT.bin（不能因此断言缺失）
            check("位流 %s 载荷不逐字存在于 BOOT.bin（符合预期）" % label, pl not in boot)

# ---- 5) 工作位流冻结 SHA ----
check("工作位流存在", os.path.isfile(WORKING_BIT), WORKING_BIT)
if os.path.isfile(WORKING_BIT):
    ws = sha256_of(WORKING_BIT)
    check("工作位流 SHA=22fec95c…", ws == "22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9", ws)

# ---- 6) PREP1 交付包冻结 SHA ----
check("PREP1 包存在", os.path.isfile(PREP1_PKG), PREP1_PKG)
if os.path.isfile(PREP1_PKG):
    ps = sha256_of(PREP1_PKG)
    check("PREP1 包 SHA=2802dc54…", ps == "2802dc54cb3c3a8fd79b4be6b325cf8743ff7e108312bebcbcbfd8448c221fff", ps)

print("RESULT test_bootbin_bif_audit.py PASS=%d FAIL=%d" % (passed, failed))
sys.exit(0 if failed == 0 else 1)
