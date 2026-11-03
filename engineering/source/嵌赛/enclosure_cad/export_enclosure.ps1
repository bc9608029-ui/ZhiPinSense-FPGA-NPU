# export_enclosure.ps1 -- deterministic STL/PNG export from the .scad master
# (Windows OpenSCAD).  -D string quoting is unreliable through PowerShell/Qt on
# Windows, so each mode is exported from a TEMP COPY with the `part` line
# substituted; the master rough_enclosure_v1.scad is never modified.
#
# Usage:  powershell -NoProfile -File export_enclosure.ps1
#
# Determinism (measured, OpenSCAD 2021.01): the PNG renders are byte-deterministic
# (two runs -> identical SHA-256).  The STL exports are NOT byte-deterministic:
# OpenSCAD/CGAL emits the same mesh (same vertex/facet counts, "Simple: yes",
# identical geometry) but the Nef->Polyhedron tessellation triangle ORDER differs
# run to run, so the STL SHA-256 is a per-run value, not a content fingerprint.
# Record the STL vertex/facet counts + manifoldness as the stable identity instead.

$ErrorActionPreference = 'Stop'

$osc = 'C:\Program Files\OpenSCAD\openscad.com'
if (-not (Test-Path $osc)) { throw "openscad not found: $osc" }

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$master = Join-Path $dir 'rough_enclosure_v1.scad'
$utf8 = [System.Text.UTF8Encoding]::new($false)
$src = [System.IO.File]::ReadAllText($master, $utf8)

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("enclosure_export_" + [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Force $tmp | Out-Null

function Invoke-Part([string]$part, [string]$out, [string[]]$extra) {
    $scad = $src.Replace('part = "assembly";', 'part = "' + $part + '";')
    $tf = Join-Path $tmp ("part_" + $part + ".scad")
    [System.IO.File]::WriteAllText($tf, $scad, $utf8)
    $oa = @('-o', $out) + $extra + @($tf)
    & $osc @oa
    if ($LASTEXITCODE -ne 0) { throw "openscad failed for part=$part exit=$LASTEXITCODE" }
    if (-not (Test-Path $out)) { throw "no output produced: $out" }
}

$renders = Join-Path $dir 'renders'
New-Item -ItemType Directory -Force $renders | Out-Null

# Main STLs (master-derived, part substituted)
Invoke-Part 'base'     (Join-Path $dir 'rough_enclosure_v1_base.stl')     @()
Invoke-Part 'lid'      (Join-Path $dir 'rough_enclosure_v1_lid.stl')      @()
Invoke-Part 'assembly' (Join-Path $dir 'rough_enclosure_v1_assembly.stl') @()

# Main PNG renders
$img = @('--imgsize=1600,1200')
Invoke-Part 'assembly' (Join-Path $renders 'assembly_isometric.png') $img
Invoke-Part 'base'     (Join-Path $renders 'base_isometric.png')     $img
Invoke-Part 'lid'      (Join-Path $renders 'lid_isometric.png')      $img
Invoke-Part 'preview'  (Join-Path $renders 'internal_layout.png')    $img

# Fit-test STLs (standalone sources, exported directly)
foreach ($ft in @('fit_test_lip','fit_test_rj45_wall','fit_test_sma_wall')) {
    $srcf = Join-Path $dir ($ft + '.scad')
    $outf = Join-Path $dir ($ft + '.stl')
    & $osc -o $outf $srcf
    if ($LASTEXITCODE -ne 0) { throw "openscad failed for $ft exit=$LASTEXITCODE" }
}

Remove-Item -Recurse -Force $tmp

Write-Output '=== OpenSCAD version ==='
& $osc --version
Write-Output '=== SHA256 (STL) ==='
Get-ChildItem -Path $dir -Filter '*.stl' | Sort-Object Name | ForEach-Object {
    (Get-FileHash -Algorithm SHA256 $_.FullName).Hash + '  ' + $_.Name
}
Write-Output '=== SHA256 (PNG) ==='
Get-ChildItem -Path $renders -Filter '*.png' | Sort-Object Name | ForEach-Object {
    (Get-FileHash -Algorithm SHA256 $_.FullName).Hash + '  ' + $_.Name
}
Write-Output 'export_enclosure.ps1: done'
