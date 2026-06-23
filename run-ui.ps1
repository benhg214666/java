$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

Set-Location $ProjectRoot

if (-not (Test-Path $BundledPython)) {
    Write-Host "Python was not found on PATH and the bundled Codex Python was not found." -ForegroundColor Red
    Write-Host "Install Python, then run this command before starting the UI:" -ForegroundColor Yellow
    Write-Host '$env:PYTHON_EXE = "C:\Path\To\python.exe"'
    exit 1
}

$env:PYTHON_EXE = $BundledPython

Write-Host "Using Python: $env:PYTHON_EXE" -ForegroundColor Cyan
Write-Host "Compiling Java files..." -ForegroundColor Cyan
javac output_ui\org\slf4j\*.java output_ui\*.java backend\java\*.java input_ui\*.java

Write-Host "Opening task input UI..." -ForegroundColor Cyan
java -cp "input_ui;output_ui;backend\java" TaskView
