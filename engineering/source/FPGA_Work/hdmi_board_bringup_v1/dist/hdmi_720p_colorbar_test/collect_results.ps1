# collect_results.ps1 — 打包上板结果/失败现场信息。
# 运行位置：本交付包目录（hdmi_720p_colorbar_test/）。
# 作用：把构建报告 + 构建日志 + 你的现场描述打成一个带时间戳的结果目录，方便定位。
# 本脚本只读 + 复制，不做任何写入开发板的动作。

$ErrorActionPreference = 'Stop'

$base   = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$out    = Join-Path $base ("results_" + $stamp)

New-Item -ItemType Directory -Force -Path $out | Out-Null

# 1) 复制构建产物（reports/ 与 build.log 若存在）
$reportDir = Join-Path $base 'reports'
if (Test-Path $reportDir) {
    Copy-Item -Path (Join-Path $reportDir '*') -Destination $out -Recurse -Force
    Write-Host "[ok] copied reports/ -> $out"
} else {
    Write-Host "[warn] reports/ not found (build 未完成?)"
}
foreach ($f in @('build.log','build_summary.txt','SHA256SUMS.txt','BOARD_TEST_GUIDE.md','TROUBLESHOOTING.md')) {
    $src = Join-Path $base $f
    if (Test-Path $src) { Copy-Item -Path $src -Destination $out -Force }
}

# 2) 现场描述（交互输入）
Write-Host ""
Write-Host "=== 现场信息 ==="
$screen  = Read-Host "屏幕现象 (空=黑屏/无信号, bar=彩条, flicker=闪烁, noise=花屏, other)"
$led0    = Read-Host "led[0](J1) 状态 (on/off/unknown)"
$led1    = Read-Host "led[1](M6) 状态 (blink/on/off/unknown)"
$verdict = Read-Host "判定 (PASS/FAIL)"
$note    = Read-Host "补充说明 (可空)"

$summary = @"
timestamp = $stamp
screen    = $screen
led0(J1)  = $led0
led1(M6)  = $led1
verdict   = $verdict
note      = $note
"@
Set-Content -Path (Join-Path $out 'field_notes.txt') -Value $summary -Encoding utf8

Write-Host ""
Write-Host "=== 请另外手工补上（脚本无法自动收集）==="
Write-Host "  - Hardware Manager 截图（含器件树与 Program 结果）"
Write-Host "  - 屏幕照片/短视频（含显示器 OSD）"
Write-Host "  - 显示器型号 + 供电方式 + HDMI 线信息"
Write-Host "  把它们一并放进：$out"
Write-Host ""
Write-Host "结果目录：$out"
