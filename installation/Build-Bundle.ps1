[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'Get-Packages.ps1')
$revision = [string](& git -C $root rev-parse --short HEAD)
if ($LASTEXITCODE -ne 0) { throw 'A Git checkout is required to build the bundle.' }
$outputDir = [IO.Path]::GetFullPath((Join-Path $root 'outputs'))
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$staging = Join-Path $outputDir ('bundle-' + [guid]::NewGuid().ToString('N'))
$project = Join-Path $staging 'WorkspaceLSE'
$output = Join-Path $outputDir ("WorkspaceLSE-windows-x64-$($revision.Trim()).zip")
if (Test-Path -LiteralPath $output) { throw "Bundle already exists: $output" }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
try {
    $sourceZip = Join-Path $staging 'source.zip'
    & git -C $root archive --format=zip HEAD --output=$sourceZip
    if ($LASTEXITCODE -ne 0) { throw 'git archive failed.' }
    Expand-Archive -LiteralPath $sourceZip -DestinationPath $project
    Remove-Item -LiteralPath $sourceZip
    $bundlePackages = Join-Path $project 'installation/packages'
    New-Item -ItemType Directory -Path $bundlePackages -Force | Out-Null
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'packages.json') -Raw | ConvertFrom-Json
    foreach ($package in $manifest) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('packages/' + $package.file)) -Destination $bundlePackages
    }
    @("Revision: $($revision.Trim())", 'Windows x64 installer kit; see installation/README.md.') | Set-Content -LiteralPath (Join-Path $project 'BUNDLE.txt') -Encoding UTF8
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($staging,$output,[IO.Compression.CompressionLevel]::Fastest,$false)
    $hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($output))" | Set-Content -LiteralPath "$output.sha256" -Encoding ASCII
    Write-Host "Bundle: $output"
    Write-Host "SHA-256: $hash"
} finally {
    $resolvedStaging = [IO.Path]::GetFullPath($staging)
    if (-not $resolvedStaging.StartsWith($outputDir + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Staging cleanup target is outside the outputs directory.'
    }
    if (Test-Path -LiteralPath $resolvedStaging) { Remove-Item -LiteralPath $resolvedStaging -Recurse -Force }
}
