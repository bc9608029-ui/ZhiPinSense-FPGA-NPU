#!/usr/bin/env bash
# Build + run the pre-SDR libiio gate in BOTH configurations (39e5b / Task 3).
#
# Usage:   bash build_libiio_gate.sh
# Env:
#   LIBIIO_SYSROOT   path to the extracted libiio sysroot
#                    (default: $HOME/iio_work/sysroot)
#   LIBIIO_OUT       output dir for the built binaries
#                    (default: $HOME/iio_work/build, a native-WSL dir so binaries
#                     stay executable -- NOT the exFAT source tree)
#   CXX              compiler (default: g++)
#
# Config 0 (SDR_ADAPTER_HAVE_LIBIIO=0): mock backend, no libiio, no device.
# Config 1 (SDR_ADAPTER_HAVE_LIBIIO=1): links libiio; with no Pluto it must
#           exit 2 with "device not found" (fast, clean, no mock fallback).

set -u

cd "$(dirname "$0")"
SYSROOT="${LIBIIO_SYSROOT:-$HOME/iio_work/sysroot}"
OUT="${LIBIIO_OUT:-$HOME/iio_work/build}"
CXX="${CXX:-g++}"
STD="-std=gnu++17 -Wall -Wextra -O2"
INC="-I."

LIBIIO_INC="-I$SYSROOT/usr/include"
# -rpath-link lets ld resolve libiio.so's transitive deps (libusb / libserialport /
# libavahi / libxml2) inside the sysroot; -rpath makes the binary self-locating
# at run time (LD_LIBRARY_PATH below is then belt-and-suspenders).
LIBIIO_LIB="-L$SYSROOT/usr/lib/x86_64-linux-gnu -liio \
  -Wl,-rpath-link,$SYSROOT/usr/lib/x86_64-linux-gnu \
  -Wl,-rpath,$SYSROOT/usr/lib/x86_64-linux-gnu"

mkdir -p "$OUT"
LOG="$(dirname "$0")/build_libiio/build_gate.log"
mkdir -p "$(dirname "$LOG")"

rc=0
{
  echo "== [1/4] build config 0 (mock, no libiio) =="
  if $CXX $STD $INC libiio_gate.cpp -o "$OUT/libiio_gate_mock"; then
      echo "    build OK -> $OUT/libiio_gate_mock"
  else
      echo "    BUILD FAILED (config 0)"; rc=1
  fi

  echo "== [2/4] build config 1 (libiio) =="
  if $CXX $STD -DSDR_ADAPTER_HAVE_LIBIIO $INC $LIBIIO_INC \
       libiio_gate.cpp pluto_libiio.cpp $LIBIIO_LIB -o "$OUT/libiio_gate_libiio"; then
      echo "    build+link OK -> $OUT/libiio_gate_libiio"
  else
      echo "    BUILD/LINK FAILED (config 1)"; rc=1
  fi

  echo "== [3/4] run config 0 (mock, offline) =="
  if [ -f "$OUT/libiio_gate_mock" ]; then
      "$OUT/libiio_gate_mock" --frames 4; e=$?
      echo "    exit=$e (expect 0)"
      [ $e -eq 0 ] || rc=1
  fi

  echo "== [4/4] run config 1 (libiio, NO device) =="
  if [ -f "$OUT/libiio_gate_libiio" ]; then
      export LD_LIBRARY_PATH="$SYSROOT/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
      out=$("$OUT/libiio_gate_libiio" --frames 4 2>&1); e=$?
      echo "$out"
      echo "    exit=$e (expect 2 = device not found)"
      if [ $e -eq 2 ] && echo "$out" | grep -q "device not found"; then
          echo "    GATE PASS: fast, clean 'device not found' (no crash/hang/mock fallback)"
      else
          echo "    GATE FAIL"; rc=1
      fi
  fi

  echo "== result: $([ $rc -eq 0 ] && echo PASS || echo FAIL) =="
  exit $rc
} 2>&1 | tee "$LOG"
exit "${PIPESTATUS[0]:-0}"
