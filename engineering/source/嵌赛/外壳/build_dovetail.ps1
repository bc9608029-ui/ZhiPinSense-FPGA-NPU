$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$run=Join-Path $env:TEMP ('shell_dovetail_'+(Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $run | Out-Null
$original=Get-ChildItem -LiteralPath $root -Filter '*.stl' | Where-Object Length -eq 193684 | Select-Object -First 1
if(!$original){throw 'original STL missing'}
Copy-Item -LiteralPath $original.FullName -Destination (Join-Path $run 'shell_original.stl')
Copy-Item -LiteralPath (Join-Path $root 'dovetail_lid_v1.scad') -Destination $run
$exe='C:\Program Files\OpenSCAD\openscad.com'
foreach($entry in @(@(1,'body_dovetail_v1'),@(2,'lid_dovetail_v1'),@(3,'fit_rail_v1'),@(4,'fit_lid_v1'))){
 $out=Join-Path $run ($entry[1]+'.stl')
 & $exe --export-format binstl -o $out -D ('part_id='+$entry[0]) (Join-Path $run 'dovetail_lid_v1.scad')
 if($LASTEXITCODE -ne 0){throw "export failed: $out"}
 Copy-Item -LiteralPath $out -Destination $root -Force
}
Copy-Item -LiteralPath (Join-Path $run 'shell_original.stl') -Destination $root -Force
Write-Output "DOVETAIL_EXPORT_PASS run=$run"
