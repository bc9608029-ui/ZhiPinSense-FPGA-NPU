$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

python -m unittest -v "$PSScriptRoot\test_scan_prep.py"
if ($LASTEXITCODE -ne 0) { throw "Python host tests failed" }

$Drive = $Root.Substring(0, 1).ToLowerInvariant()
$Rest = $Root.Substring(2).Replace('\', '/')
$WslRoot = "/mnt/$Drive$Rest"
wsl bash -lc "set -euo pipefail; cd '$WslRoot'; python3 -m unittest -v host_tests.test_scan_prep.ModeControlTests.test_ui_two_phase_protocol; g++ -std=c++17 -O2 -Wall -Wextra -Werror host_tests/test_touch4.cpp -o /tmp/rml24_test_touch4; /tmp/rml24_test_touch4"
if ($LASTEXITCODE -ne 0) { throw "C++ touch test failed" }

Write-Host 'HOST_TEST_RESULT result=PASS'

