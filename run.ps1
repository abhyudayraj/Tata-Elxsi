$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        & $pyCommand.Source -3 --version
        if ($LASTEXITCODE -eq 0) { & $pyCommand.Source -3 (Join-Path $PSScriptRoot 'server.py'); exit $LASTEXITCODE }
    }
    Write-Host 'Python 3 was not found. Install Python 3.10+ from python.org and enable Add Python to PATH.' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

& $pythonCommand.Source --version
if ($LASTEXITCODE -ne 0) { throw 'Python could not start.' }
& $pythonCommand.Source -c "import PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Required dependency Pillow is missing. Run: python -m pip install -r requirements.txt' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8765)
    $listener.Start()
    $listener.Stop()
} catch {
    Write-Host 'Port 8765 is already in use. Close the other LabelOps server or set APP_PORT in .env.' -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}

Write-Host 'Starting LabelOps at http://127.0.0.1:8765' -ForegroundColor Cyan
Write-Host 'Keep this window open while you use the app. Press Ctrl+C to stop.'
Start-Process 'http://127.0.0.1:8765'
& $pythonCommand.Source (Join-Path $PSScriptRoot 'server.py')
if ($LASTEXITCODE -ne 0) {
    Write-Host "LabelOps stopped with exit code $LASTEXITCODE" -ForegroundColor Red
    Read-Host 'Press Enter to close'
}
