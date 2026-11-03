import json, os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(base, 'results')
os.makedirs(R, exist_ok=True)

boot_chain = {
  "schema": "fmql30tai_boot_chain_inventory_v1",
  "status": "OFFLINE_EVIDENCE_ONLY",
  "generated": "2026-10-21",
  "board_identity": {
    "soc": "FMSH FMQL30TAI / JFMQL30TAI676H",
    "board_variant": "Lite (single QSPI, no eMMC; matches single n25q256a in capture)",
    "kernel": "Linux 5.4.52 aarch64 (U.FMSH, #3 SMP Fri Mar 13 13:44:29 CST 2026)",
    "evidence": "board_capture/boot_display_state_before_jtag.txt [uname]"
  },
  "boot_chain": [
    {"stage": "BootROM", "evidence": "vendor Lite HW manual 4.2 (MIO2 cascade/independent; MIO3~MIO5 select JTAG/QSPI/SD; MIO6 PLL bypass)", "confidence": "CONFIRMED_BY_VENDOR_DOC"},
    {"stage": "FSBL", "evidence": "vendor LITE zip FSBL251210_ddr400_demo.out (SHA 5501c470...)", "confidence": "CONFIRMED_BY_VENDOR_ARTIFACT"},
    {"stage": "BL31", "evidence": "vendor LITE zip bl31.elf (SHA fdcf0af4...)", "confidence": "CONFIRMED_BY_VENDOR_ARTIFACT"},
    {"stage": "U-Boot", "evidence": "vendor LITE zip u-boot (SHA c4570e3e...) + uEnv.txt", "confidence": "CONFIRMED_BY_VENDOR_ARTIFACT"},
    {"stage": "PL programming", "evidence": "30TAI tutorial 3 ('replace BOOT.bin... reboot... bitstream takes effect' => FSBL programs PL from BOOT.bin); vendor LITE uEnv.txt loadbit='fpga loadb 0 0x10000000 $filesize' (U-Boot loads download.bit)", "confidence": "CONFIRMED_BY_VENDOR_DOC"},
    {"stage": "Linux kernel", "evidence": "vendor LITE zip Image (SHA 1e40bfe9...) + uEnv.txt uenvcmd booti", "confidence": "CONFIRMED_BY_VENDOR_ARTIFACT"},
    {"stage": "rootfs", "evidence": "board_capture /proc/cmdline root=/dev/mmcblk0p2; mount /dev/mmcblk0p2 on / ext4", "confidence": "CONFIRMED_BY_BOARD_CAPTURE"}
  ],
  "storage_devices": [
    {"device": "QSPI n25q256a (32MiB) at cadence-qspi e0000000.spi",
     "mtd": [
        {"name": "bootloader", "size": "0x00400000 (4MiB)", "role": "UNCONFIRMED (possibly legacy/secondary boot image; uEnv norboot=0xE2100000 references NOR vxWorks path)"},
        {"name": "kernel", "size": "0x01000000 (16MiB)", "role": "UNCONFIRMED"},
        {"name": "rootfs", "size": "0", "role": "empty"}
     ],
     "evidence": "board_capture /proc/mtd + dmesg 'cadence-qspi e0000000.spi: n25q256a (32768 Kbytes)'"},
    {"device": "mmcblk0 (~62.5GB, SD)",
     "partitions": [
        {"name": "mmcblk0p1", "size": "1048576 KB (~1GiB)", "fs": "FAT (vendor fatload mmc 0:1)", "role": "boot partition: BOOT.bin + Image + dtb"},
        {"name": "mmcblk0p2", "size": "27343750 KB (~26GiB)", "fs": "ext4", "role": "rootfs (mounted on /)"}
     ],
     "evidence": "board_capture /proc/partitions + mount + 30TAI tutorial 3.3 + vendor uEnv.txt"}
  ],
  "fpga_load_interfaces": {
    "u_boot_fpga_loadb": {"accepts": ".bit (Vivado/Procise .bit format, sync word 0xAA995566)", "evidence": "vendor LITE uEnv.txt loadbit='... fatload mmc 0:2 ... download.bit && fpga loadb 0 0x10000000 $filesize'", "confidence": "CONFIRMED_BY_VENDOR_DOC"},
    "fsbl_from_boot_bin": {"accepts": "bitstream embedded in BOOT.bin (Procise Create Image from .bif)", "evidence": "30TAI tutorial 3 + BOOT.bin header magic 0xAA995566 'FMSH' (parsed this task)", "confidence": "CONFIRMED_BY_VENDOR_DOC"},
    "linux_fpga_manager": {"driver": "FMSH FMQL FPGA Manager (registered, state=operating)", "accepts_format": "UNCONFIRMED (no driver source found locally; no /dev/xdevcfg; fpgautil absent on board)", "evidence": "board_capture dmesg + /sys/class/fpga_manager/*"}
  },
  "bitstream_format": {
    "file": "combined_npu_hdmi_disable_icap.bit",
    "format": "Vivado/Procise .bit with 0xAA995566 sync word (file bytes aa 99 55 66 at offset 216)",
    "design_name": "jpl_ddr_mandatory_core_top_combined;UserID=0000",
    "part_string": "7z030",
    "bin_conversion_needed": "NO for U-Boot fpga loadb (consumes .bit directly, vendor-proven); .bin conversion is vendor-tool specific (no local evidence)",
    "evidence": "parsed .bit header this task (offline)"
  },
  "secure_boot": {"vendor_boot_bin_encryption_word": "0x00000000 (not encrypted)", "actual_board_setting": "UNCONFIRMED (not captured)", "evidence": "BOOT.bin header @0x28 parsed this task"},
  "recovery_paths": [
    "JTAG PL reload (current board-proven path)",
    "SD FAT BOOT.bin restore from backup (vendor tutorial 3.3)",
    "SD vs QSPI boot-device selection via MIO3~MIO5 jumpers (vendor manual 4.2)",
    "serial U-Boot console console=ttyPS0,115200n8"
  ],
  "stop_condition_notes": [
    "FMQL official loading format: FOUND (vendor .bif -> Procise Create Image -> BOOT.bin; U-Boot fpga loadb consumes .bit)",
    ".bit conversion: NOT NEEDED for U-Boot path; BOOT.bin generation requires closed Procise GUI + .bif (documented, NOT offline-generated)",
    "secure boot/signature on actual board: NOT CAPTURED (vendor BOOT.bin unencrypted)"
  ]
}

bit_id = {
  "schema": "bitstream_identity_v1",
  "status": "OFFLINE_IDENTITY_VERIFIED_PARTIAL",
  "primary_bitstream": {
    "path": "F:/FPGA_Work/sdr_full_chain_12class_combined_v1/outputs/smoke_v1/bitstream/combined_npu_hdmi_disable_icap.bit",
    "sha256": "22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9",
    "size_bytes": 5980628,
    "design_name": "jpl_ddr_mandatory_core_top_combined;UserID=0000",
    "part_string": "7z030",
    "sync_word": "0xAA995566 (file bytes aa 99 55 66 at offset 216)",
    "disable_icap_variant": True
  },
  "sibling_bitstreams": [
    {"file": "combined_npu_hdmi_raw.bit", "sha256": "bc58f4f1204784fc74ea47eff1e5080f79479d3707369cc1bd7d85888dcfdcbb", "size": 5980044, "note": "raw (ICAP enabled) variant"},
    {"file": "combined_npu_hdmi_raw_pre_fix.bit", "sha256": "d62c3d4e3f33a1073ade293496e2063b5f6993a76f2d98c727e8ca727a3003c0", "size": 5980044, "note": "raw pre-fix variant"}
  ],
  "address_map_from_combined_project": {
    "source": "sdr_full_chain_12class_combined_v1/docs/ADDRESS_MAP_AUDIT.md + board_package/pl_ddr_register_map.hpp",
    "npu_control": "0x40000000 (512K) iCraft npu=",
    "npu_dma": "0x80000000 (512K) iCraft dma=",
    "hdmi_frame_ctrl": "0x40080000 (512K) version @+0x0C=0x20230218, framebuffer @+0x50/+0x54",
    "user_gp1_reserved": "0x80080000 (512K)",
    "pl_ddr_mandatory_core": "0x400C0000 (VERSION @+0x00=0x20260929)",
    "udmabuf_framebuffer": "0x30100000 (128 MiB)"
  },
  "compatibility_with_24class_chain": {
    "verdict": "CONSISTENT_AT_CONTRACT_LEVEL",
    "evidence": [
      "24-class rml24 package (fix10class24_dualsdr2_work) pl_ddr_register_map.hpp is identical contract: VERSION_VALUE=0x20260929, User_Reg base 0x400C0000",
      "rml24 common_rml23.sh pins BITSTREAM_SHA=22fec95c... ('Same bitstream as the 12-class chain')",
      "board capture runtime: frame_ctrl 0x40080000+0x0C==0x20230218 and udmabuf0 phys 0x30100000 match UI (UI_VERSION_CHECK ok=YES, UI_FB_READY phys=0x30100000)"
    ],
    "cannot_verify": "bit-level internal NPU netlist / DMA microarchitecture inside the .bit (would require re-running Vivado/Procise synthesis+implementation from RTL and byte-comparing, or the design DCP). RTL provenance anchored in SOURCE_PROVENANCE_SHA256.txt (pl_ddr_mandatory_core_v1 + hdmi_framebuffer_ui_v4_fix, ps_ai.bd byte-identical 78f5599b...)."
  },
  "old_12_or_23_class_mapping_present": "NOT_PRESENT_AT_THIS_LEVEL: '12class' in project dir name is a naming artifact; the bitstream is the shared NPU+HDMI combined design used by both 12-class and 24-class chains (README + common_rml23.sh). No old 23-class mapping artifact found in any local source."
}

cand = {
  "schema": "candidate_image_manifest_v1",
  "status": "OFFLINE_CANDIDATE_INPUTS_ONLY",
  "generated": "2026-10-21",
  "recommended_solution": "A (BOOT.bin 固化) 为目标; 离线仅交付方案B候选载荷(.bit 即 download.bit) + 方案A输入物与配方",
  "candidate_b_download_bit": {
    "description": "方案B候选: 合并位流按字节复制为 download.bit, 供 U-Boot fpga loadb 使用 (需板端确认 uEnv 实际路径)",
    "generation": "byte copy of combined_npu_hdmi_disable_icap.bit",
    "reproducible": True,
    "source_sha256": "22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9",
    "source_size": 5980628
  },
  "candidate_a_boot_bin": {
    "description": "方案A候选 BOOT.bin: Procise Create Image (闭源GUI) + .bif + FSBL + bl31 + u-boot + .bit",
    "offline_generatable": False,
    "blocker": "Procise 为闭源 GUI; .bif 位于 BOOT_Gen.rar (本地无 7z/unrar 无法解压); 板实际 FSBL 未采集",
    "delivered": "input artifacts + documented procedure (docs/BOOT_PERSISTENCE_OPTIONS.md, scripts/build_candidate_image.sh 仅只读校验+配方输出, 不生成 .bin)"
  },
  "vendor_reference_artifacts": {
    "dir": "_evidence/vendor_docs/vendor_lite_boot/",
    "BOOT_bin_sha256": "ff350477e624c50d2f8180fb4b9130ec7688fbc7ca553412ed7c3dd2a68b31ef",
    "standalone_BOOT_bin_sha256": "c87b7959cd9980520324b2c17688d9b7c1e85358bfcef085b1b00bd5a4d2f121",
    "ai7030_top_disable_icap_bit_sha256": "6818b7f8dea8e0f9dbda1b0d11127255ee1ba8876326bc7708a633641784f72e",
    "fsbl_sha256": "5501c470e07537a8fb369ae40641c20c16ab403fad558e65e0a4bbf380f2396f",
    "bl31_sha256": "fdcf0af48a7f9716f73a477c3cc1b4cd90c914fe0e5ad7acc5ab282660802303",
    "u_boot_sha256": "c4570e3e51128211905bdf20c7b7e0ea9cb7ca1492652a070ebdd985bc213e97",
    "image_sha256": "1e40bfe97ae8eb638c15078eda28c57b4f6474872ce2753cf09be7d9238bfbed",
    "dtb_sha256": "4e690cf065424e28ad7e39e0dc87a72f4c593f5bd4d99c11f7c4e892feee3038",
    "uEnv_txt_sha256": "a13c985eb5031d75ec7069333897cae38944ba5fbadd509828b63e6a48408560"
  }
}

def w(name, obj):
    with open(os.path.join(R, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

w('boot_chain_inventory.json', boot_chain)
w('bitstream_identity.json', bit_id)
w('candidate_image_manifest.json', cand)

tsv = "\t".join(["方案", "子项", "风险等级", "依据/证据", "缓解/回退", "可离线完成度"]) + "\n"
rows = [
 ["A 固化 BOOT.bin", "生成 BOOT.bin (Procise Create Image + .bif + FSBL + bl31 + u-boot + .bit)", "HIGH", "30TAI教程 3: .bif->Procise Create Image->BOOT.bin; 闭源GUI + .bif(BOOT_Gen.rar 本地无法解压)", "用户运行 Procise 逐步记录选项; 离线仅提供输入物+配方", "不可离线生成(仅文档+输入物)"],
 ["A 固化 BOOT.bin", "写入 SD FAT 分区 mmcblk0p1", "HIGH", "30TAI教程 3.3 '替换FAT分区BOOT.bin...重启后位流生效'; 红线禁止我写", "先备份原 BOOT.bin + 分区表 + SHA; 双份备份校验", "不可(红线)"],
 ["A 固化 BOOT.bin", "FSBL 与板实际 FSBL 是否一致", "HIGH", "板端当前 BOOT.bin 未采集; vendor FSBL 未必是板实际版本", "板端只读采集当前 BOOT.bin SHA 后比对", "需板端采集"],
 ["A 固化 BOOT.bin", "断电/写入失败恢复", "HIGH", "SD 写入中断可能损坏 BOOT.bin", "保留原 BOOT.bin 备份 + JTAG 恢复 + QSPI/SD 双路径", "文档化恢复步骤"],
 ["B U-Boot fpga loadb download.bit", "依赖板实际 U-Boot 环境含 loadbit/fpga loadb", "MEDIUM", "vendor LITE uEnv.txt 有 loadbit; 板实际 uEnv 未采集(仅 bootargs 字节一致)", "板端只读 printenv 确认", "需板端采集"],
 ["B U-Boot fpga loadb download.bit", "分区布局不一致 (vendor mmc 0:2 fatload vs 板 mmcblk0p2 ext4 rootfs)", "MEDIUM", "vendor uEnv fatload mmc 0:2 与板 root=/dev/mmcblk0p2 ext4 冲突", "以板实际 uEnv 为准; 放 download.bit 到实际指定分区", "需板端采集"],
 ["B U-Boot fpga loadb download.bit", ".bit 可直接加载性", "LOW", "vendor 流程即 fpga loadb 消费 .bit; 无需 .bin 转换", "无需转换", "已确认(离线)"],
 ["B U-Boot fpga loadb download.bit", "NPU/DMA 是否需重新绑定", "LOW", "PL 在内核启动前由 U-Boot 编程, 内核随后全新枚举 NPU/DMA/udmabuf", "启动后核验 0x4008000C/0x400C0000 版本", "已确认(离线)"],
 ["C 保留 JTAG", "仅开发/赛前低风险备用", "LOW", "当前板端已验证 JTAG 重载后 HDMI/UI/触摸正常", "不冒充自动启动", "已确认(离线)"],
 ["Linux FPGA Manager 加载", "FMSH 驱动接受的镜像格式", "HIGH", "驱动源码本地未找到; 无 /dev/xdevcfg; fpgautil 不存在", "不推荐该路径直至取得驱动源码", "不可(缺证据)"],
 ["secure boot/签名", "板端是否启用", "MEDIUM", "vendor BOOT.bin 加密字=0(未加密); 板实际设置未采集", "板端只读采集确认", "需板端采集"],
 ["secure boot/签名", "写入加密/签名 BOOT.bin 会拒绝", "HIGH", "若板启用 secure boot, 自签 BOOT.bin 可能不被 BootROM 接受", "先确认未启用; 否则禁止写入", "需板端采集"],
]
with open(os.path.join(R, 'solution_risk_matrix.tsv'), 'w', encoding='utf-8', newline='') as f:
    f.write(tsv)
    for r in rows:
        f.write("\t".join(r) + "\n")

print("wrote 4 results files:")
for fn in sorted(os.listdir(R)):
    print("  ", fn, os.path.getsize(os.path.join(R, fn)), "bytes")
