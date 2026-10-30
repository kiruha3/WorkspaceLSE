[CmdletBinding()]
param([switch]$CheckOnly, [switch]$ToolsOnly)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $root '.runtime'
$packageDir = Join-Path $PSScriptRoot 'packages'
. (Join-Path $PSScriptRoot 'Offline-Assets.ps1')
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    throw 'This kit requires Windows x64.'
}
foreach ($required in @('backend/pyproject.toml','backend/uv.lock','frontend/package-lock.json','infra/local.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $required))) { throw "Missing project file: $required" }
}
if ($CheckOnly) {
    & (Join-Path $PSScriptRoot 'Get-Packages.ps1') -VerifyOnly
    if (-not $ToolsOnly) { Assert-OfflineAssets $root }
    Write-Host 'Check passed. No installers, database commands or dependency changes were run.'
    return
}
if (-not $ToolsOnly -and (Test-Path -LiteralPath (Join-Path $runtime 'postgresql-data/PG_VERSION'))) {
    throw 'This project already has a database. Fresh installation stopped; use the update instructions in docs/RUNNING.md.'
}

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $File $Arguments" }
}
function Refresh-ProcessPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:Path
}
function Install-SystemPackage([string]$File, [string[]]$Arguments) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'A system tool is missing. Reopen PowerShell as Administrator and run the same command.'
    }
    $process = Start-Process -FilePath $File -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -notin @(0,3010)) { throw "Installer failed ($($process.ExitCode)): $File" }
    if ($process.ExitCode -eq 3010) { Write-Warning 'The installer requested a Windows restart.' }
    Refresh-ProcessPath
}

& (Join-Path $PSScriptRoot 'Get-Packages.ps1') -VerifyOnly
if (-not $ToolsOnly) { Assert-OfflineAssets $root }
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$uvDir = Join-Path $runtime 'installation-tools/uv'
Expand-Archive -LiteralPath (Join-Path $packageDir 'uv-x86_64-pc-windows-msvc.zip') -DestinationPath $uvDir -Force
$uv = (Get-ChildItem -LiteralPath $uvDir -Filter uv.exe -Recurse | Select-Object -First 1).FullName
if (-not $uv) { throw 'uv.exe is missing from the extracted archive.' }

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    Install-SystemPackage (Join-Path $packageDir 'Git-2.51.2-64-bit.exe') @('/VERYSILENT','/NORESTART','/SUPPRESSMSGBOXES','/SP-')
}
$node = Get-Command node.exe -ErrorAction SilentlyContinue
$nodeReady = $false
if ($node) { $nodeReady = ([version]((& $node.Source --version).TrimStart('v'))) -ge [version]'22.12.0' }
if (-not $nodeReady) {
    Install-SystemPackage 'msiexec.exe' @('/i',('"' + (Join-Path $packageDir 'node-v22.20.0-x64.msi') + '"'),'/qn','/norestart')
}

$python = ''
try {
    $python = [string](& $uv python find 3.13 --offline --no-python-downloads 2>$null)
    if ($LASTEXITCODE -ne 0) { $python = '' }
} catch { $python = '' }
if (-not $python) {
    $pythonDir = Join-Path $env:ProgramFiles 'Python313'
    Install-SystemPackage (Join-Path $packageDir 'python-3.13.12-amd64.exe') @('/quiet','InstallAllUsers=1','PrependPath=1','Include_test=0',('TargetDir="' + $pythonDir + '"'))
    $python = Join-Path $pythonDir 'python.exe'
}
$python = $python.Trim()
Invoke-Checked $python @('--version')
Invoke-Checked 'node.exe' @('--version')

$pgDir = Join-Path $runtime 'postgresql'
if (-not (Test-Path -LiteralPath (Join-Path $pgDir 'bin/postgres.exe'))) {
    $unpack = Join-Path $runtime 'installation-tools/postgresql'
    New-Item -ItemType Directory -Path $unpack -Force | Out-Null
    New-Item -ItemType Directory -Path $pgDir -Force | Out-Null
    Invoke-Checked 'tar.exe' @('-xf',(Join-Path $packageDir 'embedded-postgres-binaries-windows-amd64-17.11.0.jar'),'-C',$unpack,'postgres-windows-x86_64.txz')
    Invoke-Checked 'tar.exe' @('-xf',(Join-Path $unpack 'postgres-windows-x86_64.txz'),'-C',$pgDir)
}
Invoke-Checked (Join-Path $pgDir 'bin/postgres.exe') @('--version')
if ($ToolsOnly) { Write-Host 'Tools prepared. No project dependencies or database were changed.'; return }

Push-Location $root
try {
    $backendPython = Join-Path $root 'backend/.venv/Scripts/python.exe'
    $offline = Join-Path $PSScriptRoot 'offline'
    Invoke-Checked $uv @('venv','--offline','--no-cache','--python',$python,'--no-python-downloads',(Join-Path $root 'backend/.venv'))
    Invoke-Checked $uv @('pip','sync','--python',$backendPython,'--offline','--no-cache','--no-index','--find-links',(Join-Path $offline 'python/wheels'),'--require-hashes',(Join-Path $offline 'python/requirements.txt'))
    $npmCache = Join-Path $runtime 'npm-cache'
    New-Item -ItemType Directory -Path $npmCache -Force | Out-Null
    Invoke-Checked 'tar.exe' @('-xf',(Join-Path $offline 'npm-cache.tgz'),'-C',$npmCache)
    Invoke-Checked 'npm.cmd' @('--prefix','frontend','ci','--offline','--cache',(Join-Path $runtime 'npm-cache'),'--ignore-scripts','--no-fund','--no-audit','--update-notifier=false')
    Invoke-Checked $backendPython @('infra/local.py','db-start')
    foreach ($command in @('migrate','seed_result_catalogs','seed_issue_catalogs','seed_correspondence_catalogs')) {
        $arguments = @('infra/local.py','backend','manage.py',$command)
        if ($command -eq 'migrate') { $arguments += '--noinput' }
        Invoke-Checked $backendPython $arguments
    }
    Invoke-Checked $backendPython @('infra/local.py','bootstrap','--seed-staff','--with-personnel-role')
    Invoke-Checked $backendPython @('infra/local.py','backend','manage.py','check')
    Invoke-Checked 'npm.cmd' @('--prefix','frontend','run','build')
} finally { Pop-Location }
Write-Host ''
Write-Host 'Installation completed. No demo expertises were created.'
Write-Host 'Initial login: .runtime/local-login.json (local file; do not publish).'
Write-Host 'Start Django and Vite using docs/RUNNING.md, section 4.'
Write-Host 'Then configure roles and import Google Sheets through the web UI.'
