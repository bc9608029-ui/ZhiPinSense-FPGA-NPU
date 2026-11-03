$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Source = Join-Path (Split-Path -Parent $Root) 'amr_rescue_gmsk_candidate_20261026'
$Model = Join-Path (Split-Path -Parent $Root) 'fix10class24_full24_accuracy1_work\sdr_rml24_fix10class24_full24_accuracy1\model_rml24_bf16'
$Evidence = Join-Path $Root 'evidence\offline_evidence_audit.json'
$Expected = Join-Path $Source 'validation_seed5100000\expected_private.json'

python (Join-Path $Root 'scripts\make_public_tx_manifest.py') `
    --expected $Expected `
    --out (Join-Path $Root 'pc_runtime\selftest_manifest_240.json')
if ($LASTEXITCODE -ne 0) { throw "public TX manifest generation failed: $LASTEXITCODE" }

python -m unittest discover -s (Join-Path $Root 'host_tests') -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw "host tests failed: $LASTEXITCODE" }

$CppTest = Join-Path $Root 'host_tests\test_rml24_final_ui_parser.cpp'
wsl.exe --cd $Root bash -lc "g++ -std=c++17 -O2 -Wall -Wextra -Werror host_tests/test_rml24_final_ui_parser.cpp -o /tmp/test_rml24_final_ui_parser && /tmp/test_rml24_final_ui_parser"
if ($LASTEXITCODE -ne 0) { throw "RML24 final UI C++ parser test failed: $LASTEXITCODE ($CppTest)" }

wsl.exe --cd $Root bash -lc "bash host_tests/check_stage7_ui_build.sh"
if ($LASTEXITCODE -ne 0) { throw "RML24 final full UI build check failed: $LASTEXITCODE" }

python (Join-Path $Root 'scripts\audit_frozen_evidence.py') `
    --source-root $Source `
    --integration-root $Root `
    --model-dir $Model `
    --out $Evidence
if ($LASTEXITCODE -ne 0) { throw "evidence audit failed: $LASTEXITCODE" }

python (Join-Path $Root 'scripts\export_ui_replay.py') `
    --board-results (Join-Path $Source 'validation_rf_r1\board_results.json') `
    --expected $Expected `
    --out (Join-Path $Root 'evidence\ui_replay_r1.jsonl')
if ($LASTEXITCODE -ne 0) { throw "R1 UI replay export failed: $LASTEXITCODE" }
python (Join-Path $Root 'scripts\export_ui_replay.py') `
    --board-results (Join-Path $Source 'validation_rf_r2\board_results.json') `
    --expected $Expected `
    --out (Join-Path $Root 'evidence\ui_replay_r2.jsonl')
if ($LASTEXITCODE -ne 0) { throw "R2 UI replay export failed: $LASTEXITCODE" }

python (Join-Path $Root 'scripts\summarize_selftest.py') `
    --expected $Expected `
    --board-results (Join-Path $Source 'validation_rf_r1\board_results.json') `
    --board-results (Join-Path $Source 'validation_rf_r2\board_results.json') `
    --out-json (Join-Path $Root 'evidence\selftest_combined.json') `
    --out-tsv (Join-Path $Root 'evidence\selftest_per_class.tsv')
if ($LASTEXITCODE -ne 0) { throw "self-test summary failed: $LASTEXITCODE" }

python (Join-Path $Root 'scripts\package_final_integration.py')
if ($LASTEXITCODE -ne 0) { throw "package build failed: $LASTEXITCODE" }

python (Join-Path $Root 'scripts\package_stage7.py')
if ($LASTEXITCODE -ne 0) { throw "Stage-7 package build failed: $LASTEXITCODE" }

Write-Output 'RML24_FINAL_HOST_CHECKS result=PASS raw_capture_replay=PENDING_CAPTURE_COPY'

