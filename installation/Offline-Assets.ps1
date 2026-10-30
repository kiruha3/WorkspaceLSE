function Get-LockDigest([string]$Path) {
    $text = [IO.File]::ReadAllText($Path).Replace("`r`n","`n")
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Assert-OfflineAssets([string]$Root) {
    $offline = [IO.Path]::GetFullPath((Join-Path $Root 'installation/offline'))
    $manifestPath = Join-Path $offline 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw 'Offline dependencies are missing. Use the complete offline ZIP or run installation/Prepare-Offline.ps1 on a connected build machine.'
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.format -ne 2 -or $manifest.target -ne 'windows-x64-cp313' -or -not $manifest.files) {
        throw 'Unsupported or empty offline dependency manifest.'
    }
    foreach ($relative in @('backend/uv.lock','frontend/package-lock.json')) {
        $property = $manifest.locks.PSObject.Properties[$relative]
        if (-not $property -or (Get-LockDigest (Join-Path $Root $relative)) -ne $property.Value) {
            throw "Offline dependencies are stale: $relative changed. Prepare the offline kit again."
        }
    }
    $paths = @()
    foreach ($file in $manifest.files) {
        $path = [IO.Path]::GetFullPath((Join-Path $offline $file.path))
        if (-not $path.StartsWith($offline + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
            throw "Invalid offline asset path: $($file.path)"
        }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing offline asset: $($file.path)" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.sha256) {
            throw "Offline asset SHA-256 mismatch: $($file.path)"
        }
        $paths += $file.path
    }
    if ('python/requirements.txt' -notin $paths -or -not ($paths -like 'python/wheels/*.whl') -or 'npm-cache.tgz' -notin $paths) {
        throw 'The offline kit is incomplete: Python wheels or npm content cache is missing.'
    }
    Write-Host "Verified offline dependencies: $($manifest.files.Count) files."
}
