# Run once in an elevated PowerShell if Windows blocks inbound web connections.
# Opens only the requested web port; Django and PostgreSQL remain loopback-only.
$aisPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $aisPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open PowerShell as Administrator and run this script again.'
}
$aisNodePath = (Get-Command node.exe -ErrorAction Stop).Source
$aisRuleName = 'AIS-LSE-Web-5173'
if (-not (Get-NetFirewallRule -Name $aisRuleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $aisRuleName -DisplayName 'AIS LSE web TCP 5173' `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 `
        -Program $aisNodePath -Profile Any | Out-Null
}
Get-NetFirewallRule -Name $aisRuleName | Select-Object Name, Enabled, Action
