#!/usr/bin/env bash
set -euo pipefail

test -f data/radioml2018/GOLD_XYZ_OSC.0001_1024.hdf5 || {
  echo "Missing data/radioml2018/GOLD_XYZ_OSC.0001_1024.hdf5" >&2
  echo "Link the uploaded official RadioML2018.01A file here; no fallback is allowed." >&2
  exit 2
}
python -u -m scripts.audit_radioml2018 \
  --config configs/ad_amr_v1_1_data_v3_12class.yaml
