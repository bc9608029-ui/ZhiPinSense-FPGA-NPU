#!/bin/bash
set -euo pipefail
WORK=/root/rml24_boot_persistence_20261027
CAND=$WORK/candidate_lf
SRC=/root/rml24_stage7_execution_20261027/final_waterfall_fix1
[ ! -e /opt/rml24-system ]
[ ! -e /etc/systemd/system/rml24-ui.service ]
[ ! -e /etc/systemd/system/rml24-receiver.service ]
(cd "$CAND" && sha256sum -c SHA256SUMS.txt)
mkdir "$WORK/system_before"
cp -a /etc/rc.local "$WORK/system_before/rc.local"
systemctl list-unit-files > "$WORK/system_before/unit_files.txt"
cp -a "$SRC" /opt/rml24-system
mkdir /opt/rml24-system/startup
install -m 0755 "$CAND/startup/check-ui.sh" /opt/rml24-system/startup/check-ui.sh
install -m 0755 "$CAND/startup/start-receiver.sh" /opt/rml24-system/startup/start-receiver.sh
install -m 0644 "$CAND/rml24-ui.service" /etc/systemd/system/rml24-ui.service
install -m 0644 "$CAND/rml24-receiver.service" /etc/systemd/system/rml24-receiver.service
systemd-analyze verify /etc/systemd/system/rml24-ui.service /etc/systemd/system/rml24-receiver.service > "$WORK/systemd_verify.log" 2>&1
systemctl daemon-reload
echo RML24_RUNTIME_INSTALL_VERIFIED