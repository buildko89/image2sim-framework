# run_build.ps1 - パラメトリック船舶モデル自動生成パイプライン実行ラッパー (UTF-8 BOM)
param(
    [string]$Target = "container_749gt",
    [switch]$SkipBlender
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "run_build.py"

$argsList = @($pythonScript, $Target)
if ($SkipBlender) {
    $argsList += "--skip-blender"
}

Write-Host "[run_build.ps1] Executing: python $argsList" -ForegroundColor Cyan
python $argsList
if ($LASTEXITCODE -ne 0) {
    Write-Error "[run_build.ps1] Build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "[run_build.ps1] Build completed successfully." -ForegroundColor Green