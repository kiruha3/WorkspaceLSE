$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'Offline-Assets.ps1')
$runtime = [IO.Path]::GetFullPath((Join-Path $root '.runtime'))
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$fixture = Join-Path $runtime ('offline-validation-' + [guid]::NewGuid().ToString('N'))
function Expect-Failure([string]$Expected) {
    $message = ''
    try { Assert-OfflineAssets $fixture } catch { $message = $_.Exception.Message }
    if ($message -notlike "*$Expected*") { throw "Expected '$Expected', received '$message'" }
}
try {
    foreach ($directory in @('backend','frontend','installation/offline/python/wheels','installation/offline/npm-cache/_cacache')) {
        New-Item -ItemType Directory -Path (Join-Path $fixture $directory) -Force | Out-Null
    }
    [IO.File]::WriteAllText((Join-Path $fixture 'backend/uv.lock'),"version = 1`n")
    [IO.File]::WriteAllText((Join-Path $fixture 'frontend/package-lock.json'),"{}`n")
    Expect-Failure 'Offline dependencies are missing'
    $offline = Join-Path $fixture 'installation/offline'
    $paths = @('python/requirements.txt','python/wheels/example-1.0-py3-none-any.whl','npm-cache/_cacache/example')
    foreach ($relative in $paths) { [IO.File]::WriteAllText((Join-Path $offline $relative),'fixture') }
    $files = @($paths | ForEach-Object { @{path=$_;sha256=(Get-FileHash -LiteralPath (Join-Path $offline $_) -Algorithm SHA256).Hash} })
    $locks = @{}
    foreach ($relative in @('backend/uv.lock','frontend/package-lock.json')) { $locks[$relative] = Get-LockDigest (Join-Path $fixture $relative) }
    @{format=1;target='windows-x64-cp313';locks=$locks;files=$files} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $offline 'manifest.json') -Encoding UTF8
    Assert-OfflineAssets $fixture
    [IO.File]::WriteAllText((Join-Path $fixture 'backend/uv.lock'),"version = 1`r`n")
    Assert-OfflineAssets $fixture
    [IO.File]::WriteAllText((Join-Path $fixture 'backend/uv.lock'),"version = 2`n")
    Expect-Failure 'dependencies are stale'
    [IO.File]::WriteAllText((Join-Path $fixture 'backend/uv.lock'),"version = 1`n")
    $wheel = Join-Path $offline $paths[1]
    Remove-Item -LiteralPath $wheel
    Expect-Failure 'Missing offline asset'
    [IO.File]::WriteAllText($wheel,'changed')
    Expect-Failure 'SHA-256 mismatch'
    Write-Host '6 offline asset checks passed: missing manifest, valid kit, CRLF, stale lock, missing file, corrupt file.'
} finally {
    $absolute = [IO.Path]::GetFullPath($fixture)
    if (-not $absolute.StartsWith($runtime + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid test cleanup path.' }
    if (Test-Path -LiteralPath $absolute) { Remove-Item -LiteralPath $absolute -Recurse -Force }
}
