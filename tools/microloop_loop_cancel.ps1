param(
    [string]$StatePath = ".codex\\microloop-loop.local.md"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $StatePath)) {
    Write-Host ("LOOP_NOT_FOUND path=" + $StatePath)
    exit 3
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

$iteration = 0
$iterationRaw = Get-MetaValue $metaLines "iteration"
if ($iterationRaw) {
    $iteration = [int]$iterationRaw
}

Remove-Item -Force $StatePath
Write-Host ("LOOP_CANCELLED iteration=" + $iteration + " path=" + $StatePath)
exit 0
