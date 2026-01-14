param(
    [string]$Title = "ShowForAi",
    [int]$WindowWidth = 1280,
    [int]$WindowHeight = 720,
    [int]$X = 0,
    [int]$Y = 0,
    [int]$ExpectScale = 100,
    [ValidateSet("window", "client")]
    [string]$Mode = "client",
    [switch]$UseClientSize,
    [int]$OverlayMs = 600,
    [switch]$NoOverlay
)

$ErrorActionPreference = "Stop"

# claude-microloop 根目录
$microloopRoot = Split-Path -Parent $PSScriptRoot

# 项目根目录 (claude-microloop 的上两级)
$projectRoot = Split-Path -Parent (Split-Path -Parent $microloopRoot)
Set-Location $projectRoot

$py = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $py)) {
    $py = "python"
}

$driver = Join-Path $microloopRoot "driver\dev_driver.py"
if (!(Test-Path $driver)) {
    throw "dev_driver not found: $driver"
}

$sizeArg = "{0}x{1}" -f $WindowWidth, $WindowHeight
$session = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $microloopRoot ("trace\preflight_" + $session)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$shot = Join-Path $outDir "step-0001.png"

$focusArgs = @($driver, "focus", "--title", $Title, "--x", "$X", "--y", "$Y")
if ($UseClientSize) {
    $focusArgs += @("--client-size", $sizeArg)
} else {
    $focusArgs += @("--window-size", $sizeArg)
}
& $py @focusArgs | Out-Null

Start-Sleep -Milliseconds 150

$inspectArgs = @(
    $driver, "inspect",
    "--title", $Title,
    "--strict",
    "--expect-foreground",
    "--expect-scale", "$ExpectScale"
)
if ($UseClientSize) {
    $inspectArgs += @("--expect-client-size", $sizeArg)
} else {
    $inspectArgs += @("--expect-window-size", $sizeArg)
}
& $py @inspectArgs | Out-Null

Start-Sleep -Milliseconds 150

$observeArgs = @(
    $driver, "observe",
    "--window-title", $Title,
    "--mode", $Mode,
    "--activate",
    "--out", $shot
)
if (-not $NoOverlay) {
    $observeArgs += @("--overlay", "--overlay-ms", "$OverlayMs")
}
& $py @observeArgs | Out-Null

Write-Host ("PREFLIGHT_OK trace=" + $shot)
