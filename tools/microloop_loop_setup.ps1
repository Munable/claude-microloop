param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string[]]$Prompt,
    [int]$MaxIterations = 0,
    [string]$CompletionPromise = "",
    [string]$StatePath = ".codex\\microloop-loop.local.md"
)

$ErrorActionPreference = "Stop"

$promptText = ($Prompt -join " ").Trim()
if (-not $promptText) {
    throw "No prompt provided."
}

if ($MaxIterations -lt 0) {
    throw "MaxIterations must be >= 0."
}

$completionYaml = "null"
if ($CompletionPromise) {
    $escaped = $CompletionPromise -replace '"', '\"'
    $completionYaml = '"' + $escaped + '"'
}

$stateDir = Split-Path -Parent $StatePath
if ($stateDir) {
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
}

$startedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$content = @(
    "---",
    "active: true",
    "iteration: 1",
    ("max_iterations: " + $MaxIterations),
    ("completion_promise: " + $completionYaml),
    ("started_at: """ + $startedAt + """"),
    "---",
    "",
    $promptText
)

Set-Content -Path $StatePath -Value $content -Encoding utf8

Write-Host "MICROLOOP_LOOP_STARTED"
Write-Host ("state=" + $StatePath)
Write-Host "iteration=1"
if ($MaxIterations -gt 0) {
    Write-Host ("max_iterations=" + $MaxIterations)
} else {
    Write-Host "max_iterations=0 (unlimited)"
}
if ($CompletionPromise) {
    Write-Host ("completion_promise=" + $CompletionPromise)
    Write-Host ("complete_by_output=<promise>" + $CompletionPromise + "</promise>")
    Write-Host "CRITICAL: Only output the promise when it is completely and unequivocally true."
    Write-Host "CRITICAL: Do not output a false promise to exit the loop."
} else {
    Write-Host "completion_promise=none (runs forever)"
}

Write-Host "This loop reuses the SAME prompt until completion or max_iterations."
Write-Host ""
Write-Output $promptText
