$ErrorActionPreference = "Stop"

$Version = "v0.8.5"
$Url = "https://github.com/NextronSystems/evtx-baseline/releases/download/$Version/evtx-sigma-checker-win"
$ExpectedSha256 = "813fdd73e93dae4659467fd6942861902165b0f92b52daee51412bedce08be61"

$BinDir = Join-Path $PSScriptRoot "bin"
$OutFile = Join-Path $BinDir "evtx-sigma-checker.exe"

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

Write-Host "Downloading evtx-sigma-checker $Version ..."
Invoke-WebRequest -Uri $Url -OutFile $OutFile

$ActualSha256 = (Get-FileHash -Algorithm SHA256 $OutFile).Hash.ToLowerInvariant()
if ($ActualSha256 -ne $ExpectedSha256) {
    Remove-Item $OutFile -Force -ErrorAction SilentlyContinue
    throw "SHA256 mismatch. Expected $ExpectedSha256 but got $ActualSha256"
}

Write-Host "SHA256 verified: $ActualSha256"
Write-Host "Installed: $OutFile"
