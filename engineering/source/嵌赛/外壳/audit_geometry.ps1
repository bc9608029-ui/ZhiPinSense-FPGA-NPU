$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$run=Join-Path $env:TEMP ('shell_audit_'+(Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $run | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'shell_original.stl'),(Join-Path $root 'dovetail_lid_v1.scad') -Destination $run
$exe='C:\Program Files\OpenSCAD\openscad.com'
$evidence=Join-Path $root 'geometry_audit'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
foreach($check in @(@(5,'assembled_collision'),@(6,'changes_below_188'),@(7,'sampled_slide_collision'))){
 $out=Join-Path $run ($check[1]+'.stl')
 $log=Join-Path $evidence ($check[1]+'.log')
 $err=Join-Path $evidence ($check[1]+'.stderr.log')
 $p=Start-Process -FilePath $exe -ArgumentList @('--export-format','binstl','-o',$out,'-D',('part_id='+$check[0]),(Join-Path $run 'dovetail_lid_v1.scad')) -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
 $empty=(Select-String -LiteralPath $err,$log -SimpleMatch 'Current top level object is empty' -Quiet) -contains $true
 if(Test-Path $out){Copy-Item $out $evidence -Force}
 Write-Output "$($check[1]) rc=$($p.ExitCode) empty=$empty output_exists=$(Test-Path $out)"
}
Write-Output "AUDIT_RUN=$run"
