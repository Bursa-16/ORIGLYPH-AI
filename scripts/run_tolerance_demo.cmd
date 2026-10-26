@echo off
REM Origlyph AI -- Tolerance Workspace Demo (Windows double-click launcher)
REM Delegates all logic to the PowerShell launcher; no duplicated launch code.
powershell.exe -ExecutionPolicy Bypass -File "%~dp0run_tolerance_demo.ps1"
