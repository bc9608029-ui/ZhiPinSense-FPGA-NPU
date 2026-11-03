# rollback_to_frozen.ps1 — restore the FROZEN NPU+HDMI bitstream as the active
# candidate reference.  This script never programs a board, never writes Flash and
# never modifies the frozen source project; it only verifies the frozen bitstream
# is byte-identical to the recorded SHA and restores the "active" pointer used by
# the board-test manifest.  Run after a failed smart-scan candidate A/B if the
# operator needs to return to the frozen baseline.
#
# Red lines honoured here: no board access, no bitstream load, no Flash write.

$ErrorActionPreference = 'Stop'

$frozenBit = 'F:\FPGA_Work\sdr_full_chain_12class_smartscan_candidate_v1\outputs\smoke_v1\bitstream\combined_npu_hdmi_disable_icap.bit'
$frozenSha = '22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9'

if (-not (Test-Path -LiteralPath $frozenBit)) {
    throw "Frozen bitstream missing: $frozenBit"
}

$actual = (Get-FileHash -LiteralPath $frozenBit -Algorithm SHA256).Hash.ToLower()
if ($actual -ne $frozenSha) {
    throw "Frozen bitstream SHA mismatch: expected $frozenSha got $actual — do NOT proceed; frozen baseline may be corrupted."
}

Write-Output "ROLLBACK_FROZEN_SHA_OK $actual"
Write-Output "ROLLBACK_INSTRUCTIONS: the frozen bitstream at"
Write-Output "  $frozenBit"
Write-Output "is byte-identical to the recorded SHA.  To return the board to the frozen"
Write-Output "baseline, program THIS file with the same board tooling used for the original"
Write-Output "delivery.  Do NOT use the smart-scan candidate bitstream."
