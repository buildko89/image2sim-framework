# run_build.ps1 - NC machine model build wrapper (scripts/nc_machine/run_build.py)
param(
    [string]$Target = "all",
    [switch]$SkipBlender,
    [switch]$RequireBlender
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "run_build.py"

$argsList = @($pythonScript, $Target)
if ($SkipBlender) { $argsList += "--skip-blender" }
if ($RequireBlender) { $argsList += "--require-blender" }

Write-Host "[run_build.ps1] Executing: python $argsList" -ForegroundColor Cyan
python $argsList
if ($LASTEXITCODE -ne 0) {
    Write-Error "[run_build.ps1] Build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "[run_build.ps1] Build completed successfully." -ForegroundColor Green
