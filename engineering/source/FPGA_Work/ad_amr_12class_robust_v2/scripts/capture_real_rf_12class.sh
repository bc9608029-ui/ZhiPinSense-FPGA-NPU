#!/usr/bin/env bash
# capture_real_rf_12class.sh — 12-class real-RF capture driver (SigMF).
#
# 安全/元数据/SHA 编排层。真实 I/Q 收发由板端采集命令完成（用户提供），
# 本脚本不直接操作射频；由用户本人在板端执行（API 不碰板卡）。
#
# 必须显式 --confirm-safe-rf-path 才允许发射；默认 TX 衰减取安全最大值；
# 出错即调用 --tx-stop-cmd 关发射；每类多 seed；保存完整 SigMF 元数据；
# 采集后立即计算 SHA 并冻结；支持同轴与天线。
#
# 用法示例：
#   ./scripts/capture_real_rf_12class.sh \
#     --path-type coax --confirm-safe-rf-path \
#     --sdr-serial PLUTO-0001 --center-freq-hz 915000000 --sample-rate 2560000 \
#     --tx-atten-db 40 --rx-gain-db 30 --rec-scale 21.8556709 \
#     --bitstream-sha 22fec95c... --software-version smoke_v1 --model-sha 2ae95275... \
#     --out-dir /data/rf/coax_915m \
#     --capture-cmd 'board_capture --class {class} --seed {seed} --out {out_data} ...' \
#     --tx-stop-cmd 'board_capture --stop-tx'
set -euo pipefail

# ---- 默认安全参数 ----------------------------------------------------------
LABEL_ORDER=(OOK 4ASK AM-DSB WBFM 2FSK GFSK BPSK QPSK 8PSK 16QAM 64QAM OFDM)
CLASSES=""
NUM_SEEDS=5
SEED_START=0
CENTER_FREQ_HZ=""
SAMPLE_RATE=""
TX_ATTEN_DB=""
DEFAULT_MAX_TX_ATTEN_DB=40
RX_GAIN_DB=""
REC_SCALE=""
SDR_SERIAL=""
PATH_TYPE=""
DISTANCE_M=0.5
DIRECTION="fixed"
BITSTREAM_SHA=""
SOFTWARE_VERSION=""
MODEL_SHA=""
LABEL_SOURCE="golden_generator"
OUT_DIR=""
CAPTURE_CMD=""
TX_STOP_CMD=""
CONFIRM_SAFE_RF=0

usage() {
  echo "usage: $0 --path-type coax|antenna --confirm-safe-rf-path --sdr-serial S --out-dir D --capture-cmd C [--tx-stop-cmd T] ..." >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --classes) CLASSES="$2"; shift 2 ;;
    --num-seeds) NUM_SEEDS="$2"; shift 2 ;;
    --seed-start) SEED_START="$2"; shift 2 ;;
    --center-freq-hz) CENTER_FREQ_HZ="$2"; shift 2 ;;
    --sample-rate) SAMPLE_RATE="$2"; shift 2 ;;
    --tx-atten-db) TX_ATTEN_DB="$2"; shift 2 ;;
    --rx-gain-db) RX_GAIN_DB="$2"; shift 2 ;;
    --rec-scale) REC_SCALE="$2"; shift 2 ;;
    --sdr-serial) SDR_SERIAL="$2"; shift 2 ;;
    --path-type) PATH_TYPE="$2"; shift 2 ;;
    --distance-m) DISTANCE_M="$2"; shift 2 ;;
    --direction) DIRECTION="$2"; shift 2 ;;
    --bitstream-sha) BITSTREAM_SHA="$2"; shift 2 ;;
    --software-version) SOFTWARE_VERSION="$2"; shift 2 ;;
    --model-sha) MODEL_SHA="$2"; shift 2 ;;
    --label-source) LABEL_SOURCE="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --capture-cmd) CAPTURE_CMD="$2"; shift 2 ;;
    --tx-stop-cmd) TX_STOP_CMD="$2"; shift 2 ;;
    --confirm-safe-rf-path) CONFIRM_SAFE_RF=1; shift 1 ;;
    *) echo "unknown arg: $1" >&2; usage ;;
  esac
done

# ---- fail-closed 参数校验 ---------------------------------------------------
[ "$CONFIRM_SAFE_RF" = "1" ] || { echo "FAIL: must pass --confirm-safe-rf-path before any TX" >&2; exit 2; }
[ -n "$PATH_TYPE" ] || { echo "FAIL: --path-type required (coax|antenna)" >&2; exit 2; }
case "$PATH_TYPE" in coax|antenna) ;; *) echo "FAIL: --path-type must be coax or antenna" >&2; exit 2 ;; esac
[ -n "$SDR_SERIAL" ] || { echo "FAIL: --sdr-serial required" >&2; exit 2; }
[ -n "$CENTER_FREQ_HZ" ] || { echo "FAIL: --center-freq-hz required" >&2; exit 2; }
[ -n "$SAMPLE_RATE" ] || { echo "FAIL: --sample-rate required" >&2; exit 2; }
[ -n "$OUT_DIR" ] || { echo "FAIL: --out-dir required" >&2; exit 2; }
[ -n "$CAPTURE_CMD" ] || { echo "FAIL: --capture-cmd required" >&2; exit 2; }

# 默认 TX 衰减安全（最大衰减 = 最小发射功率）。
if [ -z "$TX_ATTEN_DB" ]; then
  TX_ATTEN_DB="$DEFAULT_MAX_TX_ATTEN_DB"
  echo "NOTE: TX attenuation defaulted to safe maximum ${TX_ATTEN_DB} dB"
fi

if [ -z "$CLASSES" ]; then
  CLASSES="$(IFS=,; echo "${LABEL_ORDER[*]}")"
fi

mkdir -p "$OUT_DIR"

# 会话 id = RF 配置轴（不含类别/seed），保证同一配置的全部记录同 split。
SESSION_ID="$(printf '%s|%s|%s|%s|%s|%s|%s|%s' \
  "$SDR_SERIAL" "$PATH_TYPE" "$CENTER_FREQ_HZ" "$SAMPLE_RATE" \
  "$TX_ATTEN_DB" "$RX_GAIN_DB" "$DISTANCE_M" "$DIRECTION" | sha256sum | cut -c1-16)"

# 出错/退出时关发射。
stop_tx() {
  if [ -n "$TX_STOP_CMD" ]; then
    echo "TX STOP: $TX_STOP_CMD"
    eval "$TX_STOP_CMD" >/dev/null 2>&1 || true
  fi
}
trap stop_tx EXIT

RUN_MANIFEST="$OUT_DIR/run_manifest.json"
RUN_SUMS="$OUT_DIR/SHA256SUMS.txt"
: > "$RUN_SUMS"
echo "session_id=$SESSION_ID"

# ---- 逐类 × 多 seed 采集 ----------------------------------------------------
RUN_FILES="["
first_file=1
for CLASS in ${CLASSES//,/ }; do
  IDX=-1
  for i in "${!LABEL_ORDER[@]}"; do
    if [ "${LABEL_ORDER[$i]}" = "$CLASS" ]; then IDX=$i; break; fi
  done
  [ "$IDX" -ge 0 ] || { echo "FAIL: unknown class $CLASS" >&2; exit 2; }

  for ((s=SEED_START; s<SEED_START+NUM_SEEDS; s++)); do
    STEM="${CLASS}_seed${s}"
    OUT_DATA="$OUT_DIR/${STEM}.sigmf-data"
    OUT_META="$OUT_DIR/${STEM}.sigmf-meta"

    # 展开捕获命令占位符并执行；失败即关发射并退出。
    CMD="${CAPTURE_CMD//\{class\}/$CLASS}"
    CMD="${CMD//\{seed\}/$s}"
    CMD="${CMD//\{out_data\}/$OUT_DATA}"
    CMD="${CMD//\{center_freq\}/$CENTER_FREQ_HZ}"
    CMD="${CMD//\{sample_rate\}/$SAMPLE_RATE}"
    CMD="${CMD//\{tx_atten\}/$TX_ATTEN_DB}"
    CMD="${CMD//\{rx_gain\}/$RX_GAIN_DB}"
    echo "CAPTURE: $CMD"
    eval "$CMD" || { echo "FAIL: capture failed for $CLASS seed $s" >&2; exit 1; }
    [ -s "$OUT_DATA" ] || { echo "FAIL: empty capture $OUT_DATA" >&2; exit 1; }

    CAPTURED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # SigMF 元数据（标签只写 meta，绝不写进 I/Q 内容）。
    cat > "$OUT_META" <<EOF
{
  "global": {
    "core:datatype": "cf32_le",
    "core:sample_rate": ${SAMPLE_RATE},
    "core:frequency": ${CENTER_FREQ_HZ},
    "core:author": "${SDR_SERIAL}",
    "core:description": "12-class AMR V2 real-RF capture",
    "amr12:label": "${CLASS}",
    "amr12:label_index": ${IDX},
    "amr12:seed": ${s},
    "amr12:tx_attenuation_db": ${TX_ATTEN_DB},
    "amr12:rx_gain_db": ${RX_GAIN_DB},
    "amr12:rec_scale": ${REC_SCALE},
    "amr12:sdr_serial": "${SDR_SERIAL}",
    "amr12:path_type": "${PATH_TYPE}",
    "amr12:distance_m": ${DISTANCE_M},
    "amr12:direction": "${DIRECTION}",
    "amr12:bitstream_sha": "${BITSTREAM_SHA}",
    "amr12:software_version": "${SOFTWARE_VERSION}",
    "amr12:model_sha": "${MODEL_SHA}",
    "amr12:session_id": "${SESSION_ID}",
    "amr12:label_source": "${LABEL_SOURCE}",
    "amr12:captured_utc": "${CAPTURED_UTC}"
  },
  "captures": [{"core:sample_start": 0}],
  "annotations": [{"core:sample_start": 0, "core:sample_count": 0, "amr12:label": "${CLASS}"}]
}
EOF

    DATA_SHA="$(sha256sum "$OUT_DATA" | cut -d' ' -f1)"
    printf '%s  %s\n' "$DATA_SHA" "${STEM}.sigmf-data" >> "$RUN_SUMS"
    [ "$first_file" = "1" ] && first_file=0 || RUN_FILES="$RUN_FILES,"
    RUN_FILES="$RUN_FILES{\"relpath\":\"${STEM}.sigmf-data\",\"label\":\"${CLASS}\",\"label_index\":${IDX},\"seed\":${s},\"session_id\":\"${SESSION_ID}\",\"data_sha256\":\"${DATA_SHA}\"}"
  done
done
RUN_FILES="$RUN_FILES]"

cat > "$RUN_MANIFEST" <<EOF
{
  "session_id": "${SESSION_ID}",
  "path_type": "${PATH_TYPE}",
  "center_freq_hz": ${CENTER_FREQ_HZ},
  "sample_rate": ${SAMPLE_RATE},
  "tx_attenuation_db": ${TX_ATTEN_DB},
  "rx_gain_db": ${RX_GAIN_DB},
  "sdr_serial": "${SDR_SERIAL}",
  "bitstream_sha": "${BITSTREAM_SHA}",
  "software_version": "${SOFTWARE_VERSION}",
  "model_sha": "${MODEL_SHA}",
  "files": ${RUN_FILES}
}
EOF

echo "DONE: $(wc -l < "$RUN_SUMS") captures in $OUT_DIR (session $SESSION_ID)"
echo "next: python3 tools/build_sigmf_manifest.py --root $OUT_DIR"
