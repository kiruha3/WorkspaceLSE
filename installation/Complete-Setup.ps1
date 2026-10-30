[CmdletBinding()]
param([string]$ProjectRoot = '')

$ErrorActionPreference = 'Stop'
if (-not $ProjectRoot) {
    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'infra/local.py')) {
        $ProjectRoot = $PSScriptRoot
    } elseif (Test-Path -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'infra/local.py')) {
        $ProjectRoot = Split-Path $PSScriptRoot -Parent
    } else {
        $ProjectRoot = (Get-Location).Path
    }
}
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$runtime = Join-Path $root '.runtime'
$backendPython = Join-Path $root 'backend/.venv/Scripts/python.exe'
foreach ($required in @('infra/local.py','backend/.venv/Scripts/python.exe',
        '.runtime/postgresql/bin/initdb.exe','frontend/node_modules/.bin/vite.cmd')) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $required))) {
        throw "Missing installed dependency: $required. Run installation/Install.ps1 first."
    }
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm.cmd is missing from PATH. Reopen PowerShell after installing Node.js.' }

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $File $Arguments" }
}

if (-not (Test-Path -LiteralPath (Join-Path $runtime 'postgresql-data/PG_VERSION'))) {
    # PostgreSQL drops administrative group privileges internally. Grant only
    # this user's SID explicit Modify access to the project-local runtime.
    if ((Get-Item -LiteralPath $runtime).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw '.runtime is a link or junction. Choose a regular project-local runtime directory.'
    }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $icacls = Join-Path $env:SystemRoot 'System32/icacls.exe'
    Invoke-Checked $icacls @($runtime,'/grant',("*{0}:(OI)(CI)M" -f $sid),'/T','/C','/Q','/L')
    Write-Host 'Explicit Modify access granted to the current account for .runtime only.'
}

Push-Location $root
try {
    # Real files retain diagnostics and prevent detached PostgreSQL from holding
    # the PowerShell pipe open. Works with old kits without editing their code.
    $startDatabase = @'
import locale, os, runpy, subprocess, sys
m = runpy.run_path('infra/local.py')
def visible_pg(program, *args, check=True):
    executable = m['BIN'] / (program + ('.exe' if os.name == 'nt' else ''))
    log = m['RUNTIME'] / ('postgresql-' + program + '.log')
    with log.open('wb') as stream:
        result = subprocess.run([str(executable), *map(str, args)], check=False,
            stdout=stream, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    data = log.read_bytes()
    try:
        output = data.decode('utf-8')
    except UnicodeDecodeError:
        output = data.decode(locale.getencoding(), errors='replace')
    if output:
        print(output, end='', file=sys.stderr if result.returncode else sys.stdout, flush=True)
    if check and result.returncode:
        raise SystemExit('PostgreSQL ' + program + ' failed. See ' + str(log))
    return result
m['db_start'].__globals__['run_pg'] = visible_pg
m['db_start']()
'@
    Invoke-Checked $backendPython @('-c',$startDatabase)
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
