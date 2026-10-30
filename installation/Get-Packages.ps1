[CmdletBinding()]
param([switch]$VerifyOnly)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$packageDir = Join-Path $PSScriptRoot 'packages'
$packages = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'packages.json') -Raw | ConvertFrom-Json
if (-not $VerifyOnly) { New-Item -ItemType Directory -Path $packageDir -Force | Out-Null }

foreach ($package in $packages) {
    $target = Join-Path $packageDir $package.file
    if (-not (Test-Path -LiteralPath $target)) {
        if ($VerifyOnly) { throw "Missing package: $target. Run installation/Get-Packages.ps1 first." }
        Write-Host "Downloading $($package.id) $($package.version)..."
        $partial = "$target.download"
        Invoke-WebRequest -UseBasicParsing -Uri $package.url -OutFile $partial
        if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $package.sha256) {
            Remove-Item -LiteralPath $partial
            throw "SHA-256 mismatch for $($package.file)."
        }
        Move-Item -LiteralPath $partial -Destination $target
    }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $package.sha256) {
        throw "SHA-256 mismatch for cached package $target. Replace that file before continuing."
    }
    Write-Host "Verified: $($package.file)"
}
