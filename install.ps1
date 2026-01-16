<#
.SYNOPSIS
    Install Claude Microloop skills for Claude Code

.DESCRIPTION
    Creates symbolic links from .claude/skills/ to the microloop skills,
    so that Claude Code can recognize and use them.

.EXAMPLE
    # After cloning to .claude/microloop/
    powershell -ExecutionPolicy Bypass -File .claude/microloop/install.ps1
#>

$ErrorActionPreference = "Stop"

# Get script directory (should be .claude/microloop/)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$microloopDir = $scriptDir

# Get .claude directory (parent of microloop)
$claudeDir = Split-Path -Parent $microloopDir

# Verify we're in the right place
$expectedPath = Join-Path $claudeDir "microloop"
if ($microloopDir -ne $expectedPath) {
    Write-Host "Warning: Expected to be in .claude/microloop/, but found: $microloopDir" -ForegroundColor Yellow
}

# Create skills directory if it doesn't exist
$skillsDir = Join-Path $claudeDir "skills"
if (!(Test-Path $skillsDir)) {
    New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
    Write-Host "Created: $skillsDir" -ForegroundColor Green
}

# Skills to link
$skills = @("microloop")

foreach ($skill in $skills) {
    $source = Join-Path $microloopDir "skills\$skill"
    $target = Join-Path $skillsDir $skill

    # Check if source exists
    if (!(Test-Path $source)) {
        Write-Host "Error: Source not found: $source" -ForegroundColor Red
        continue
    }

    # Remove existing link/directory if exists
    if (Test-Path $target) {
        $item = Get-Item $target -Force
        if ($item.LinkType -eq "SymbolicLink") {
            Remove-Item $target -Force
            Write-Host "Removed existing link: $target" -ForegroundColor Yellow
        } else {
            Write-Host "Error: $target exists and is not a symbolic link. Please remove it manually." -ForegroundColor Red
            continue
        }
    }

    # Create symbolic link (requires admin on Windows)
    try {
        New-Item -ItemType SymbolicLink -Path $target -Target $source -Force | Out-Null
        Write-Host "Linked: $target -> $source" -ForegroundColor Green
    } catch {
        Write-Host "Error creating symbolic link. Try running as Administrator." -ForegroundColor Red
        Write-Host "Alternative: Copy the skills directory manually:" -ForegroundColor Yellow
        Write-Host "  Copy-Item -Recurse `"$source`" `"$target`"" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Skills are now available in: $skillsDir" -ForegroundColor Cyan
