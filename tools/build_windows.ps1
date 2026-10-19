param(
    [string]$Python,
    [string]$IsccPath,
    [string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$dspProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $Python) { $Python = Join-Path $dspProjectRoot '.venv\Scripts\python.exe' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $dspProjectRoot 'dist' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
if (-not $IsccPath) {
    $dspCompilerOnPath = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    $dspCompilerCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        $dspCompilerOnPath.Source
    )
    $IsccPath = $dspCompilerCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath -PathType Leaf)) { throw 'Install Inno Setup or pass -IsccPath.' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Python environment missing.' }
Push-Location $dspProjectRoot
$dspPreviousPath = $env:PATH
# Do not resolve Qt dependencies from unrelated tools on the host PATH.
# In particular Poppler's icuuc.dll is incompatible with Windows' ICU shim.
$env:PATH = ([IO.Path]::GetDirectoryName($Python)), (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot -join ';'
try {
    $dspReleaseVersion = (& $Python -c 'from dsp408.version import VERSION; print(VERSION)').Trim()
    if ($LASTEXITCODE -ne 0 -or $dspReleaseVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid release version.' }
    & $Python tools\prepare_release_assets.py
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
    & $Python -m PyInstaller --noconfirm --distpath $OutputDirectory --workpath build\windows DSP408_Control.spec
    if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
    $dspAppSource = Join-Path $OutputDirectory 'DSP408FIR Control'
    $dspSetupOutput = Join-Path $OutputDirectory 'installer'
    & $IsccPath "/DAppSource=$dspAppSource" "/DSetupOutput=$dspSetupOutput" packaging\windows\DSP408_Control.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
    $dspSetupFile = Join-Path $dspSetupOutput "DSP408FIR-Control-$dspReleaseVersion-Setup.exe"
    $dspSetupHash = (Get-FileHash -LiteralPath $dspSetupFile -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$dspSetupFile.sha256" -Value "$dspSetupHash  $([IO.Path]::GetFileName($dspSetupFile))" -Encoding ascii
    Write-Host "Installer: $dspSetupFile"
}
finally { $env:PATH = $dspPreviousPath; Pop-Location }
