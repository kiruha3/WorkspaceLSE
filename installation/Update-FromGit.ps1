[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$aisRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$aisPython = Join-Path $aisRoot 'backend\.venv\Scripts\python.exe'
$aisData = Join-Path $aisRoot '.runtime\postgresql-data'
$aisConnection = Join-Path $aisRoot '.runtime\postgresql-connection.json'
$aisDumpTool = Join-Path $aisRoot '.runtime\postgresql\bin\pg_dump.exe'
foreach ($aisRequired in @($aisPython, $aisConnection, $aisDumpTool, (Join-Path $aisData 'PG_VERSION'), (Join-Path $aisRoot 'frontend\package-lock.json'))) {
    if (-not (Test-Path -LiteralPath $aisRequired -PathType Leaf)) {
        throw "Not an installed WorkspaceLSE project: missing $aisRequired. No changes made."
    }
}
$aisGit = (Get-Command git.exe -ErrorAction Stop).Source
$aisNpm = (Get-Command npm.cmd -ErrorAction Stop).Source
$aisUv = Join-Path $aisRoot '.runtime\installation-tools\uv\uv.exe'
if (-not (Test-Path -LiteralPath $aisUv)) { $aisUv = (Get-Command uv.exe -ErrorAction Stop).Source }
$aisRepository = 'https://github.com/kiruha3/WorkspaceLSE.git'
$aisNewGit = -not (Test-Path -LiteralPath (Join-Path $aisRoot '.git'))
$aisNeedsBaseline = $aisNewGit
$aisRevision = $null
if (-not $aisNewGit) {
    $aisTop = & $aisGit -C $aisRoot rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($aisTop.Trim()) -ne [IO.Path]::GetFullPath($aisRoot)) {
        throw 'The project must be the root of its own Git checkout.'
    }
    $aisRemote = & $aisGit -C $aisRoot remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $aisRemote.Trim().TrimEnd('/') -notin @($aisRepository, 'https://github.com/kiruha3/WorkspaceLSE', 'git@github.com:kiruha3/WorkspaceLSE.git')) {
        throw 'Unexpected Git origin; inspect it before updating.'
    }
    $aisBranch = & $aisGit -C $aisRoot branch --show-current
    if ($LASTEXITCODE -ne 0 -or $aisBranch.Trim() -ne 'master') { throw 'Switch to the existing master checkout before using this updater.' }
    & $aisGit -C $aisRoot rev-parse --verify --quiet HEAD | Out-Null
    $aisNeedsBaseline = $LASTEXITCODE -ne 0
    foreach ($aisOperation in @('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')) {
        $aisOperationPath = & $aisGit -C $aisRoot rev-parse --git-path $aisOperation
        if ($LASTEXITCODE -ne 0) { throw 'Cannot check the Git operation state.' }
        if (-not [IO.Path]::IsPathRooted($aisOperationPath)) { $aisOperationPath = Join-Path $aisRoot $aisOperationPath }
        if (Test-Path -LiteralPath $aisOperationPath) { throw 'Finish the existing Git operation before updating.' }
    }
}
if ($aisNeedsBaseline) {
    $aisBundle = Join-Path $aisRoot 'BUNDLE.txt'
    if (-not (Test-Path -LiteralPath $aisBundle)) { throw 'BUNDLE.txt is missing; cannot safely determine the original ZIP version.' }
    $aisMatch = [regex]::Match([IO.File]::ReadAllText($aisBundle), '(?m)^Revision: ([0-9a-f]{7,40})\s*$')
    if (-not $aisMatch.Success) { throw 'Cannot determine the original ZIP revision from BUNDLE.txt.' }
    $aisRevision = $aisMatch.Groups[1].Value
}
if ($CheckOnly) {
    Write-Host "Installed project verified. Git setup required: $aisNewGit. No changes made."
    return
}
if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    $aisListeners = @(Get-NetTCPConnection -State Listen -LocalPort 8000,5173 -ErrorAction SilentlyContinue)
    if ($aisListeners.Count) { throw 'Stop Django and Vite with Ctrl+C in their windows before updating (ports 8000/5173 are listening).' }
}
function Invoke-AisChecked {
    param([string]$File, [string[]]$Arguments, [string]$Step)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE). Stop here; do not restart installation or restore old source automatically." }
}
Push-Location -LiteralPath $aisRoot
try {
    if ($aisNewGit) {
        Invoke-AisChecked -File $aisGit -Arguments @('init','--initial-branch=master') -Step 'Git initialization'
        Invoke-AisChecked -File $aisGit -Arguments @('remote','add','origin',$aisRepository) -Step 'Git origin setup'
    }
    Invoke-AisChecked -File $aisGit -Arguments @('fetch','origin') -Step 'Git fetch'
    if ($aisNeedsBaseline) {
        Invoke-AisChecked -File $aisGit -Arguments @('cat-file','-e',"${aisRevision}^{commit}") -Step 'Original bundle revision check'
        # Mixed reset establishes the ZIP baseline without replacing any working files.
        Invoke-AisChecked -File $aisGit -Arguments @('reset','--mixed',$aisRevision) -Step 'ZIP baseline setup'
    }
    # Only tracked source changes are stashed. Untracked files and ignored data stay in place.
    Invoke-AisChecked -File $aisGit -Arguments @('-c','user.name=WorkspaceLSE local snapshot','-c','user.email=local-snapshot@localhost','stash','push','-m','Before AIS Git update') -Step 'Local source snapshot'
    Invoke-AisChecked -File $aisGit -Arguments @('pull','--ff-only','origin','master') -Step 'Source update'
    Invoke-AisChecked -File $aisPython -Arguments @('infra/local.py','db-start') -Step 'Database start'
    $aisBackupDir = Join-Path $aisRoot 'backups'
    New-Item -ItemType Directory -Path $aisBackupDir -Force | Out-Null
    $aisBackup = Join-Path $aisBackupDir ('before-git-update-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8) + '.dump')
    $aisConfig = Get-Content -LiteralPath $aisConnection -Raw | ConvertFrom-Json
    $aisPreviousPassword = [Environment]::GetEnvironmentVariable('PGPASSWORD', 'Process')
    try {
        $env:PGPASSWORD = $aisConfig.password
        Invoke-AisChecked -File $aisDumpTool -Arguments @('--host',[string]$aisConfig.host,'--port',[string]$aisConfig.port,'--username',[string]$aisConfig.user,'--dbname',[string]$aisConfig.dbname,'--format=custom','--file',$aisBackup) -Step 'Database backup'
    } finally {
        if ($null -eq $aisPreviousPassword) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
        else { $env:PGPASSWORD = $aisPreviousPassword }
    }
    Write-Host "Database backup: $aisBackup"
    Invoke-AisChecked -File $aisUv -Arguments @('sync','--directory','backend','--python','3.13','--locked','--no-python-downloads') -Step 'Python dependency update'
    Invoke-AisChecked -File $aisNpm -Arguments @('--prefix','frontend','ci') -Step 'Frontend dependency update'
    Invoke-AisChecked -File $aisPython -Arguments @('infra/local.py','backend','manage.py','migrate','--noinput') -Step 'Database migration'
    Invoke-AisChecked -File $aisPython -Arguments @('infra/local.py','backend','manage.py','check') -Step 'Django check'
    Invoke-AisChecked -File $aisNpm -Arguments @('--prefix','frontend','run','build') -Step 'Frontend build'
    Write-Host 'Update completed. Start Django and Vite as described in docs/RUNNING.md section 4.'
    Write-Host 'Local source snapshots: git stash list. Do not apply old patches automatically.'
} finally { Pop-Location }
