#!/usr/bin/env bash
# build_candidate_image.sh -- 离线生成「候选」启动载荷（方案 B），并打印方案 A 配方。
#
# 本脚本只做离线文件操作，不写板、不烧 Flash、不生成 BOOT.bin（方案 A 需闭源 Procise GUI）。
#
# 方案 B 候选：把验证过的合并位流按字节复制为 download.bit，供 U-Boot `fpga loadb` 使用。
#   - 字节复制，SHA 与源一致 → 完全可复现。
# 方案 A 配方：打印 vendor 教程的 BOOT.bin 生成步骤（见 docs/BOOT_PERSISTENCE_OPTIONS.md），
#   不生成 .bin、不猜测格式。
#
# 用法：
#   bash build_candidate_image.sh            # 用默认源位流生成候选 download.bit + 校验
#   bash build_candidate_image.sh --help     # 打印配方说明
set -u

# 默认源位流（可在命令行覆盖，不依赖 git 工作树绝对路径）
BIT_SRC="${BIT_SRC:-F:/FPGA_Work/sdr_full_chain_12class_combined_v1/outputs/smoke_v1/bitstream/combined_npu_hdmi_disable_icap.bit}"
EXPECT_SHA="22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CAND_DIR="$ROOT_DIR/candidate"

log() { echo "[build_candidate] $*"; }

print_recipe_a() {
    cat <<'EOF'
===== 方案 A 配方（需闭源 Procise GUI，本脚本不生成 .bin）=====
依据：F:\嵌赛\2026嵌赛FPGA开发\30TAI使用教程.pdf §三「生成BOOT.bin」
1. 解压 BOOT_Gen.zip，用文本编辑器打开 BOOT_Gen/7030ai_psin.bif；
   将 bif 内路径替换为解压目录（路径不得含反斜杠，且能找到各文件）。
2. 将 Vivado 生成的位流（后缀 .bit，即 combined_npu_hdmi_disable_icap.bit，
   SHA 22fec95c…）拷贝到解压目录，确保文件名与 bif 中位流文件名一致。
3. 打开 Procise，按 30TAI 教程图 3-2 依次点击，最后「Create Image」。
4. 生成 bin 文件（BOOT.bin）位于解压目录。
5. 离线校验：bash scripts/verify_candidate_image.sh --boot-bin <BOOT.bin> \
     --bit combined_npu_hdmi_disable_icap.bit
6. 部署（用户授权+备份后）：见 docs/BOARDTEST_DEPLOYMENT_DRAFT.md 阶段 2。
红线：本脚本不写板、不烧 Flash、不 program Flash、不改 U-Boot env。
===== 结束 =====
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    print_recipe_a
    exit 0
fi

mkdir -p "$CAND_DIR"

if [ ! -f "$BIT_SRC" ]; then
    log "FAIL source bitstream not found: $BIT_SRC"
    exit 2
fi

SRC_SHA="$(sha256sum "$BIT_SRC" 2>/dev/null | awk '{print $1}')"
if [ -z "$SRC_SHA" ]; then
    log "FAIL cannot sha256sum source"
    exit 2
fi
if [ "$SRC_SHA" != "$EXPECT_SHA" ]; then
    log "FAIL source SHA mismatch: got=$SRC_SHA expected=$EXPECT_SHA"
    exit 1
fi

log "source bit SHA OK: $SRC_SHA"
log "byte-copy to candidate/download.bit"
cp -f "$BIT_SRC" "$CAND_DIR/download.bit"

OUT_SHA="$(sha256sum "$CAND_DIR/download.bit" | awk '{print $1}')"
if [ "$OUT_SHA" != "$EXPECT_SHA" ]; then
    log "FAIL candidate copy SHA mismatch: $OUT_SHA"
    exit 1
fi

# 生成逐文件 SHA256SUMS
( cd "$CAND_DIR" && sha256sum download.bit > SHA256SUMS.txt )

log "OK candidate/download.bit sha256=$OUT_SHA"
log "OK candidate/SHA256SUMS.txt written"
print_recipe_a
exit 0
