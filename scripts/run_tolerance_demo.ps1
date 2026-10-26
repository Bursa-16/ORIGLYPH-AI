# Origlyph AI -- Tolerance Workspace Demo Launcher
#
# Launches the interactive customer demo for the tolerance workspace.
# Run from repository root or directly:
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
#
# Requires Python 3.10+ with origlyph installed in development mode:
#
#   py -m pip install -e ".[dev]"

$ErrorActionPreference = "Stop"

# Resolve repository root robustly from this script's location
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "=============================================="
Write-Host " Origlyph AI"
Write-Host " Tolerance Engineering Demo"
Write-Host " Version 0.4.0-alpha.7"
Write-Host "=============================================="
Write-Host ""

# Verify demo entry point exists
$entry = Join-Path $repoRoot "examples\tolerance_workspace_demo.py"
if (-not (Test-Path $entry)) {
    Write-Host "ERROR: Demo entry point not found." -ForegroundColor Red
    Write-Host "  Expected: $entry"
    Write-Host "  Verify you are on branch main at commit 014aec86."
    exit 1
}

# Verify Python launcher is available
try {
    $pyVer = & py --version 2>&1
} catch {
    Write-Host "ERROR: Python launcher 'py' not found on PATH." -ForegroundColor Red
    Write-Host "  Install Python 3.10+ from python.org and ensure 'py' is available."
    exit 1
}
Write-Host "Python : $pyVer"

# Verify origlyph package is importable
$check = & py -c "import origlyph; print(origlyph.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: origlyph package not importable." -ForegroundColor Red
    Write-Host "  Run from the repository root:"
    Write-Host "    py -m pip install -e `".[dev]`""
    exit 1
}
Write-Host "Package: origlyph $check"
Write-Host ""
Write-Host "Launching customer demo..."
Write-Host "(Close the demo window to return to this terminal.)"
Write-Host ""

Set-Location $repoRoot
& py (Join-Path $repoRoot "examples\tolerance_workspace_demo.py")

Write-Host ""
Write-Host "Demo closed."
