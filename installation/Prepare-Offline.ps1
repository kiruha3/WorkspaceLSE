[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'Offline-Assets.ps1')

function Invoke-Preparation([string]$File,[string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Preparation failed ($LASTEXITCODE): $File $Arguments" }
}
function Remove-PreparationDirectory([string]$Path,[string]$Parent) {
    $absolute = [IO.Path]::GetFullPath($Path)
    $base = [IO.Path]::GetFullPath($Parent).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not $absolute.StartsWith($base + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Preparation cleanup target is outside its expected parent.'
    }
    if (Test-Path -LiteralPath $absolute) {
        if ((Get-Item -LiteralPath $absolute).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing to replace a linked generated directory.' }
        Remove-Item -LiteralPath $absolute -Recurse -Force
    }
}

& (Join-Path $PSScriptRoot 'Get-Packages.ps1')
$uvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
if (-not $uvCommand) { throw 'Install uv on the connected build machine before preparing dependencies.' }
$uv = $uvCommand.Source
Invoke-Preparation 'node.exe' @('-e',"if(process.platform!=='win32'||process.arch!=='x64')process.exit(1)")
$runtime = Join-Path $root '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$stage = Join-Path $runtime ('offline-preparation-' + [guid]::NewGuid().ToString('N'))
$assets = Join-Path $stage 'offline'
$wheelhouse = Join-Path $assets 'python/wheels'
$requirements = Join-Path $assets 'python/requirements.txt'
$locks = [ordered]@{}
foreach ($relative in @('backend/uv.lock','frontend/package-lock.json')) { $locks[$relative] = Get-LockDigest (Join-Path $root $relative) }
New-Item -ItemType Directory -Path $wheelhouse -Force | Out-Null
try {
    Invoke-Preparation $uv @('export','--directory',(Join-Path $root 'backend'),'--locked','--all-groups','--no-emit-project','--no-header','--format','requirements.txt','--output-file',$requirements)
    $builder = Join-Path $stage 'wheel-builder'
    Invoke-Preparation $uv @('venv','--python','3.13','--no-python-downloads','--seed',$builder)
    Invoke-Preparation (Join-Path $builder 'Scripts/python.exe') @('-m','pip','download','--only-binary=:all:','--require-hashes','--dest',$wheelhouse,'-r',$requirements,'--disable-pip-version-check')

    $frontend = Join-Path $stage 'frontend'
    New-Item -ItemType Directory -Path $frontend -Force | Out-Null
    foreach ($name in @('package.json','package-lock.json')) { Copy-Item -LiteralPath (Join-Path $root ('frontend/' + $name)) -Destination $frontend }
    $npmCache = Join-Path $assets 'npm-cache'
    Invoke-Preparation 'npm.cmd' @('--prefix',$frontend,'ci','--cache',$npmCache,'--ignore-scripts','--no-fund','--no-audit')
    $npmArchive = Join-Path $assets 'npm-cache.tgz'
    Invoke-Preparation (Join-Path $builder 'Scripts/python.exe') @((Join-Path $PSScriptRoot 'archive_tools.py'),'pack-cache',$npmCache,$npmArchive)
    foreach ($relative in $locks.Keys) {
        if ((Get-LockDigest (Join-Path $root $relative)) -ne $locks[$relative]) { throw "Lock file changed during preparation: $relative" }
    }

    # Only wheels, requirements and npm content-addressed data enter the distribution.
    $files = @()
    $selected = @((Get-Item -LiteralPath $requirements)) + @(Get-ChildItem -LiteralPath $wheelhouse -File) + @((Get-Item -LiteralPath $npmArchive))
    foreach ($file in ($selected | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($assets.Length + 1).Replace('\','/')
        $files += [ordered]@{path=$relative;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant();size=$file.Length}
    }
    $manifest = [ordered]@{format=2;target='windows-x64-cp313';locks=$locks;files=$files}
    $destination = Join-Path $PSScriptRoot 'offline'
    Remove-PreparationDirectory $destination $PSScriptRoot
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    foreach ($file in $files) {
        $target = Join-Path $destination $file.path
        New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $assets $file.path) -Destination $target
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $destination 'manifest.json') -Encoding UTF8
    Assert-OfflineAssets $root
    Write-Host 'Offline dependencies prepared. Commit the source, then run installation/Build-Bundle.ps1.'
} finally { Remove-PreparationDirectory $stage $runtime }
