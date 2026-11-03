#!/usr/bin/env bash
set -euo pipefail
BASE=http://192.168.126.10:39020
TMP=$(mktemp -d /root/rml24_test_setup_XXXXXX)
get_file() {
 if command -v curl >/dev/null; then curl -fSs --connect-timeout 5 "$BASE/$1" -o "$TMP/$1";
 else wget -q -T 5 "$BASE/$1" -O "$TMP/$1"; fi
}
get_file board.zip
get_file test.pub
printf '%s  %s\n' 662b57818f22a56d68d2c42eab63707093b60e559e9e3dd6a197275c40eba921 "$TMP/board.zip" | sha256sum -c -
printf '%s  %s\n' 9db7c44e6809b3ff6bc99bc0f502d62bbce1bb2c8a7631ad6769f5773129798e "$TMP/test.pub" | sha256sum -c -
python3 -m zipfile -e "$TMP/board.zip" "$TMP"
ROOT="$TMP/rml24_test_readiness_20261030"
python3 - "$TMP/test.pub" <<'PY'
from pathlib import Path
import os
key=Path(__import__('sys').argv[1]).read_text().strip()
if not key.startswith('ssh-ed25519 ') or not key.endswith('rml24-test-20261030'):raise ValueError('unexpected test key')
directory=Path('/root/.ssh');directory.mkdir(exist_ok=True);directory.chmod(0o700)
file=directory/'authorized_keys';line='restrict '+key
old=file.read_text() if file.exists() else ''
if line not in old.splitlines():
 with file.open('a') as f:f.write(('\n' if old and not old.endswith('\n') else '')+line+'\n')
file.chmod(0o600)
print('TEST_KEY_INSTALLED')
PY
printf '%s\n' "$ROOT" > /root/rml24_parameter_test_root.txt
echo "TEST_ROOT=$ROOT"
stat -c '%a %U %n' /root /root/.ssh /root/.ssh/authorized_keys
/usr/sbin/sshd -T | grep -E '^(permitrootlogin|pubkeyauthentication|authorizedkeysfile) '
echo 'SETUP_COMPLETE_NO_RF_STARTED'
