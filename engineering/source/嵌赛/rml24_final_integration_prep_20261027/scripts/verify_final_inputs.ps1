$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $Root 'RELEASE_MANIFEST.json'
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Failures = New-Object System.Collections.Generic.List[string]

foreach ($Artifact in $Manifest.artifacts) {
    if (-not (Test-Path -LiteralPath $Artifact.path -PathType Leaf)) {
        $Failures.Add("MISSING $($Artifact.role): $($Artifact.path)")
        continue
    }
    $Actual = (Get-FileHash -LiteralPath $Artifact.path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Artifact.sha256.ToLowerInvariant()) {
        $Failures.Add("SHA_MISMATCH $($Artifact.role): expected=$($Artifact.sha256) actual=$Actual")
    } else {
        Write-Host "SHA_OK $($Artifact.role) $Actual"
    }
}

$ScanRoot = $Manifest.authoritative_paths.scan_evidence_root
$SummaryPath = Join-Path $ScanRoot 'FINAL_SCAN_AUTOTEST_SUMMARY.json'
if (-not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
    $Failures.Add("MISSING scan summary: $SummaryPath")
} else {
    $Summary = Get-Content -LiteralPath $SummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $ExpectedScan = $Manifest.verified_metrics.centered_scan
    if (($Summary.candidate_scan_correct -ne $ExpectedScan.correct) -or
        ($Summary.candidate_scan_total -ne $ExpectedScan.total)) {
        $Failures.Add('METRIC_MISMATCH centered scan summary')
    } else {
        Write-Host "METRIC_OK centered_scan $($ExpectedScan.correct)/$($ExpectedScan.total)"
    }
}

foreach ($Name in @('fixed_r1_results.json', 'fixed_r2_results.json', 'centered_wide_v2_results.json', 'centered_narrow_v2_results.json')) {
    $Path = Join-Path $ScanRoot $Name
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $Failures.Add("MISSING results: $Path")
        continue
    }
    $Rows = (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json).records
    $Unique = @($Rows.seq | Sort-Object -Unique)
    if (($Rows.Count -ne 240) -or ($Unique.Count -ne 240) -or ($Unique[0] -ne 0) -or ($Unique[-1] -ne 239)) {
        $Failures.Add("DENOMINATOR_INVALID $Name rows=$($Rows.Count) unique=$($Unique.Count)")
    } else {
        Write-Host "DENOMINATOR_OK $Name 240/240 unique seq=0..239"
    }
}

if ($Failures.Count -gt 0) {
    $Failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Host 'FINAL_PC_PREFLIGHT result=PASS board_integration_still_required=1'
