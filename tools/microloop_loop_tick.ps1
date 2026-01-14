param(
    [string]$StatePath = ".claude\\microloop-loop.local.md"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $StatePath)) {
    Write-Host ("LOOP_STATE_MISSING path=" + $StatePath)
    exit 4
}

$lines = Get-Content -Path $StatePath
$first = [Array]::IndexOf($lines, "---")
if ($first -lt 0) {
    Write-Host "LOOP_STATE_INVALID missing_frontmatter"
    exit 4
}
$second = [Array]::IndexOf($lines, "---", $first + 1)
if ($second -lt 0) {
    Write-Host "LOOP_STATE_INVALID missing_frontmatter_end"
    exit 4
}

$metaLines = $lines[($first + 1)..($second - 1)]
$promptLines = @()
if ($second + 1 -lt $lines.Length) {
    $promptLines = $lines[($second + 1)..($lines.Length - 1)]
}

function Get-MetaValue([string[]]$Lines, [string]$Key) {
    $prefix = ($Key + ":")
    foreach ($line in $Lines) {
        $trim = $line.Trim()
        if ($trim.StartsWith($prefix)) {
            return $trim.Substring($prefix.Length).Trim()
        }
    }
    return $null
}

$active = $true
$activeRaw = Get-MetaValue $metaLines "active"
if ($activeRaw) {
    $active = ($activeRaw.ToLower() -eq "true")
}
if (-not $active) {
    Write-Host ("LOOP_INACTIVE path=" + $StatePath)
    exit 3
}

$iteration = 1
$iterationRaw = Get-MetaValue $metaLines "iteration"
if ($iterationRaw) {
    $iteration = [int]$iterationRaw
}
$maxIterations = 0
$maxRaw = Get-MetaValue $metaLines "max_iterations"
if ($maxRaw) {
    $maxIterations = [int]$maxRaw
}

$iteration++
if ($maxIterations -gt 0 -and $iteration -ge $maxIterations) {
    $active = $false
}

$completionPromise = Get-MetaValue $metaLines "completion_promise"
if (-not $completionPromise) {
    $completionPromise = "null"
}
$startedAt = Get-MetaValue $metaLines "started_at"
if (-not $startedAt) {
    $startedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$outLines = @(
    "---",
    ("active: " + ($active.ToString().ToLower())),
    ("iteration: " + $iteration),
    ("max_iterations: " + $maxIterations),
    ("completion_promise: " + $completionPromise),
    ("started_at: " + $startedAt),
    "---"
)
if ($promptLines.Count -gt 0) {
    $outLines += $promptLines
}

Set-Content -Path $StatePath -Value $outLines -Encoding utf8

if (-not $active) {
    Write-Host ("LOOP_STOP iteration=" + $iteration + " max_iterations=" + $maxIterations + " path=" + $StatePath)
    exit 2
}

Write-Host ("LOOP_TICK iteration=" + $iteration + " path=" + $StatePath)
exit 0
