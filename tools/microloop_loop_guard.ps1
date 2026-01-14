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

if ($promptLines.Count -eq 0) {
    Write-Host ("LOOP_PROMPT_EMPTY path=" + $StatePath)
    exit 5
}

$promptText = [string]::Join("`n", $promptLines)
Write-Output $promptText
exit 0
