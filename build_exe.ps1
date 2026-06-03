$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Local .venv was not found. Run: python -m venv .venv"
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "MoyaMultistudia" `
    main.py

$Version = (& $Python -c "from stopmotion import __version__; print(__version__)").Trim()
$ReleaseDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force $ReleaseDir | Out-Null

$ZipPath = Join-Path $ReleaseDir "MoyaMultistudia-v$Version-win64.zip"
for ($Attempt = 1; $Attempt -le 5; $Attempt++) {
    try {
        Compress-Archive -Path (Join-Path $Root "dist\MoyaMultistudia\*") -DestinationPath $ZipPath -Force
        break
    }
    catch {
        if ($Attempt -eq 5) {
            throw
        }
        Start-Sleep -Seconds 2
    }
}

Write-Host "Done: $ZipPath"
