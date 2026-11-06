[CmdletBinding()]
param(
    [string]$Version = '2.1.0',
    [string]$InnoSetupCompiler = '',
    [switch]$SkipInstaller,
    [string]$SignTool = '',
    [string]$CodeSignCertificate = '',
    [string]$CodeSignPassword = '',
    [string]$TimestampServer = 'http://timestamp.digicert.com'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$AppName = 'WhatsAppCapitalize'
$SourceRoot = Join-Path $ProjectRoot 'src'
$WindowsDist = Join-Path $ProjectRoot 'dist\windows'

if (-not $SkipInstaller -and -not $InnoSetupCompiler) {
    $knownCompilers = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    )
    $InnoSetupCompiler = $knownCompilers | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $SkipInstaller -and (-not $InnoSetupCompiler -or -not (Test-Path -LiteralPath $InnoSetupCompiler))) {
    throw 'Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php, then run this script again.'
}

if ($CodeSignCertificate) {
    if (-not $CodeSignPassword) {
        throw 'CodeSignPassword is required when CodeSignCertificate is provided.'
    }
    if (-not (Test-Path -LiteralPath $CodeSignCertificate)) {
        throw "Code-signing certificate was not found: $CodeSignCertificate"
    }
    if (-not $SignTool) {
        $SignTool = (Get-Command signtool.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    }
    if (-not $SignTool -or -not (Test-Path -LiteralPath $SignTool)) {
        throw 'signtool.exe was not found. Install the Windows SDK or pass -SignTool.'
    }
}

function Invoke-CodeSigning([string]$FilePath) {
    if (-not $CodeSignCertificate) {
        return
    }

    & $SignTool sign /fd SHA256 /tr $TimestampServer /td SHA256 /f $CodeSignCertificate /p $CodeSignPassword $FilePath
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed for $FilePath with exit code $LASTEXITCODE."
    }

    & $SignTool verify /pa /v $FilePath
    if ($LASTEXITCODE -ne 0) {
        throw "Signature verification failed for $FilePath with exit code $LASTEXITCODE."
    }
}

Push-Location $ProjectRoot
try {
    python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --paths $SourceRoot `
        --distpath $WindowsDist `
        --workpath (Join-Path $ProjectRoot 'build\windows') `
        --specpath (Join-Path $ProjectRoot 'build\spec') `
        --icon (Join-Path $ProjectRoot 'assets\icon.ico') `
        --hidden-import whatsapp_capitalize.windows_app `
        --name $AppName (Join-Path $SourceRoot 'whatsapp_capitalize\__main__.py')
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
    $portablePath = Join-Path $WindowsDist "$AppName.exe"
    Invoke-CodeSigning $portablePath

    if (-not $SkipInstaller) {
        $installerScript = Join-Path $ProjectRoot 'packaging\windows\WhatsAppCapitalize.iss'
        & $InnoSetupCompiler "/DMyAppVersion=$Version" $installerScript
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup failed with exit code $LASTEXITCODE."
        }
    }
}
finally {
    Pop-Location
}

Write-Host "Portable executable created: $portablePath"
if (-not $SkipInstaller) {
    $installerPath = Join-Path $WindowsDist "WhatsAppCapitalize-Setup-$Version-win64.exe"
    Invoke-CodeSigning $installerPath
    Write-Host "Installer created: $installerPath"
}
