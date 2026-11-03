#!/usr/bin/env bash
# verify_candidate_image.sh -- 离线核验候选启动产物（只读解析，不写板）。
#
# 用法：
#   bash verify_candidate_image.sh --bit <file.bit>                       # 核验 .bit 身份
#   bash verify_candidate_image.sh --download-bit <candidate/download.bit> # 核验方案 B 候选
#   bash verify_candidate_image.sh --boot-bin <BOOT.bin> --bit <file.bit>  # 核验方案 A 候选 BOOT.bin
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="$ROOT_DIR/scripts/verify_boot_artifacts.py"
EXPECT_SHA="22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9"
EXPECT_DESIGN="jpl_ddr_mandatory_core_top_combined"

BIT=""
BOOTBIN=""
MODE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --bit) BIT="$2"; MODE="${MODE:-bit}"; shift 2 ;;
        --download-bit) BIT="$2"; MODE="download"; shift 2 ;;
        --boot-bin) BOOTBIN="$2"; MODE="${MODE:-bootbin}"; shift 2 ;;
        *) echo "unknown arg: $1"; exit 2 ;;
    esac
done

fail() { echo "[verify_candidate] FAIL $*"; exit 1; }

case "$MODE" in
    bit|download)
        [ -n "$BIT" ] || fail "missing --bit/--download-bit"
        [ -f "$BIT" ] || fail "file not found: $BIT"
        SHA="$(sha256sum "$BIT" 2>/dev/null | awk '{print $1}')"
        echo "[verify_candidate] file=$BIT sha256=$SHA"
        python "$PY" bit-info "$BIT" || fail "bit-info parse failed"
        ;;
    bootbin)
        [ -n "$BOOTBIN" ] || fail "missing --boot-bin"
        [ -n "$BIT" ] || fail "missing --bit"
        [ -f "$BOOTBIN" ] || fail "BOOT.bin not found: $BOOTBIN"
        [ -f "$BIT" ] || fail "bit not found: $BIT"
        echo "[verify_candidate] BOOT.bin=$BOOTBIN bit=$BIT"
        python "$PY" bootbin-info "$BOOTBIN" || fail "bootbin-info parse failed"
        python "$PY" bit-in-bootbin "$BOOTBIN" "$BIT" || fail "bitstream not embedded in BOOT.bin"
        ;;
    *)
        fail "no mode selected (use --bit / --download-bit / --boot-bin)"
        ;;
esac

echo "[verify_candidate] OK"
exit 0
