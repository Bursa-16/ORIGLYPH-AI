# Origlyph AI -- Pre-demo Readiness Check
#
# READ-ONLY health check. Run before every customer demo session.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\check_demo_readiness.ps1
#
# This script DOES NOT modify files, install packages, reset git,
# clean git, switch branches, stash changes, pull, merge, rebase,
# push, or delete files.
#
# Returns:
#   DEMO_READINESS: PASS   -- safe to launch
#   DEMO_READINESS: FAIL   -- resolve listed reasons before launching

$ErrorActionPreference = "SilentlyContinue"

$GOLDEN_COMMIT   = "7fc11129ca63d09d0054ceb8afe241ea894ca93a"
$GOLDEN_VERSION  = "0.4.0a7"
$GOLDEN_BRANCH   = "main"

$repoRoot = Split-Path -Parent $PSScriptRoot
$failures = @()
$warnings = @()

Write-Host ""
Write-Host "=============================================="
Write-Host " Origlyph AI"
Write-Host " Pre-Demo Readiness Check"
Write-Host " Golden baseline: $($GOLDEN_COMMIT.Substring(0,12))"
Write-Host "=============================================="
Write-Host ""

# ── 1. Confirm we are in the correct repository root ──────────────────────────

$markerFile = Join-Path $repoRoot "examples\tolerance_workspace_demo.py"
if (-not (Test-Path $markerFile)) {
    $failures += "REPO_ROOT: expected marker file not found at $markerFile"
}

Set-Location $repoRoot

# ── 2. Branch check ───────────────────────────────────────────────────────────

$branch = & git branch --show-current 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
    $failures += "BRANCH: could not determine current branch (git error or detached HEAD)"
} elseif ($branch.Trim() -ne $GOLDEN_BRANCH) {
    $failures += "BRANCH: expected '$GOLDEN_BRANCH', found '$($branch.Trim())'"
} else {
    Write-Host "  Branch          : $($branch.Trim()) [OK]"
}

# ── 3. HEAD commit check ──────────────────────────────────────────────────────

$head = & git rev-parse HEAD 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($head)) {
    $failures += "HEAD: git rev-parse HEAD failed"
} elseif ($head.Trim() -ne $GOLDEN_COMMIT) {
    $failures += "HEAD: expected $GOLDEN_COMMIT, found $($head.Trim())"
} else {
    Write-Host "  HEAD            : $($head.Trim().Substring(0,12)) [OK]"
}

# ── 4. Fetch remote state (informational; failure is a warning only) ──────────

$fetchOut = & git fetch origin 2>&1
if ($LASTEXITCODE -ne 0) {
    $warnings += "FETCH: could not reach origin (network unavailable) — skipping remote check"
    Write-Host "  Remote fetch    : SKIPPED (no network)"
} else {
    # ── 5. origin/main commit check ───────────────────────────────────────────
    $originMain = & git rev-parse origin/main 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($originMain)) {
        $warnings += "ORIGIN/MAIN: could not resolve origin/main"
    } elseif ($originMain.Trim() -ne $GOLDEN_COMMIT) {
        $failures += "ORIGIN/MAIN: expected $GOLDEN_COMMIT, found $($originMain.Trim())"
    } else {
        Write-Host "  origin/main     : $($originMain.Trim().Substring(0,12)) [OK]"
    }

    # ── 6. ahead / behind check ───────────────────────────────────────────────
    $counts = & git rev-list --left-right --count origin/main...HEAD 2>$null
    if ($counts -match '^\s*(\d+)\s+(\d+)\s*$') {
        $behind = [int]$Matches[1]
        $ahead  = [int]$Matches[2]
        if ($behind -gt 0 -or $ahead -gt 0) {
            $failures += "AHEAD/BEHIND: expected 0/0, found behind=$behind ahead=$ahead"
        } else {
            Write-Host "  Ahead/behind    : 0 / 0 [OK]"
        }
    }
}

# ── 7. Worktree clean check ───────────────────────────────────────────────────

$dirty = & git status --short 2>$null
if ($LASTEXITCODE -ne 0) {
    $failures += "WORKTREE: git status failed"
} elseif (-not [string]::IsNullOrWhiteSpace($dirty)) {
    $failures += "WORKTREE: uncommitted changes present"
} else {
    Write-Host "  Worktree        : clean [OK]"
}

# ── 8. Version check ──────────────────────────────────────────────────────────

$ver = & py -c "import origlyph; print(origlyph.__version__)" 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ver)) {
    $failures += "VERSION: origlyph not importable or version unreadable"
} elseif ($ver.Trim() -ne $GOLDEN_VERSION) {
    $failures += "VERSION: expected $GOLDEN_VERSION, found $($ver.Trim())"
} else {
    Write-Host "  Version         : $($ver.Trim()) [OK]"
}

# ── 9. Required demo files check ─────────────────────────────────────────────

$requiredFiles = @(
    "examples\tolerance_workspace_demo.py",
    "scripts\run_tolerance_demo.ps1",
    "scripts\run_tolerance_demo.cmd",
    "docs\demo\golden_demo_baseline.md",
    "docs\demo\customer_demo_runbook.md",
    "docs\demo\customer_demo_cheat_sheet.md"
)

foreach ($rel in $requiredFiles) {
    $full = Join-Path $repoRoot $rel
    if (-not (Test-Path $full)) {
        $failures += "MISSING_FILE: $rel"
    }
}
if ($failures -notmatch "MISSING_FILE") {
    Write-Host "  Demo files      : all present [OK]"
}

# ── 10. Python launcher check ─────────────────────────────────────────────────

$pyVer = & py --version 2>&1
if ($LASTEXITCODE -ne 0) {
    $failures += "PYTHON: 'py' launcher not found on PATH"
} else {
    Write-Host "  Python          : $pyVer [OK]"
}

# ── 11. Import check ──────────────────────────────────────────────────────────

& py -c "from origlyph.tolerance import launch_tolerance_workspace, ToleranceWorkspaceController" 2>$null
if ($LASTEXITCODE -ne 0) {
    $failures += "IMPORTS: origlyph.tolerance imports failed"
} else {
    Write-Host "  Imports         : OK [OK]"
}

# ── 12. Headless smoke test ───────────────────────────────────────────────────

$entry = Join-Path $repoRoot "examples\tolerance_workspace_demo.py"
& py $entry --headless 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    $failures += "HEADLESS_SMOKE: demo --headless exited with error"
} else {
    Write-Host "  Headless smoke  : PASS [OK]"
}

# ── Summary ───────────────────────────────────────────────────────────────────

Write-Host ""

if ($warnings.Count -gt 0) {
    Write-Host "Warnings:"
    foreach ($w in $warnings) {
        Write-Host "  WARNING: $w" -ForegroundColor Yellow
    }
    Write-Host ""
}

if ($failures.Count -eq 0) {
    Write-Host "DEMO_READINESS: PASS" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Launch with:"
    Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1"
    Write-Host ""
} else {
    Write-Host "DEMO_READINESS: FAIL" -ForegroundColor Red
    Write-Host ""
    Write-Host "Resolve before launching:"
    foreach ($f in $failures) {
        Write-Host "  FAIL: $f" -ForegroundColor Red
    }
    Write-Host ""
    exit 1
}
