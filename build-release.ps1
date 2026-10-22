[CmdletBinding()]
param(
    [string]$Version = '1.0.0',
    [string]$InnoSetupCompiler = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$AppName = 'WhatsAppCapitalize'

if (-not $InnoSetupCompiler) {
    $knownCompilers = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    )
    $InnoSetupCompiler = $knownCompilers | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $InnoSetupCompiler -or -not (Test-Path -LiteralPath $InnoSetupCompiler)) {
    throw 'Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php, then run this script again.'
}

Push-Location $ProjectRoot
try {
    python -m PyInstaller --noconfirm --clean --onefile --windowed --icon icon.ico --name $AppName wa_capitalize.py

    $installerScript = Join-Path $ProjectRoot 'installer\WhatsAppCapitalize.iss'
    & $InnoSetupCompiler "/DMyAppVersion=$Version" $installerScript
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$installerPath = Join-Path $ProjectRoot "installer\output\WhatsAppCapitalize-Setup-$Version-win64.exe"
Write-Host "Installer created: $installerPath"
