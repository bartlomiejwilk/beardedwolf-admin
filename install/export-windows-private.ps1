# BeardedWolf - PRIVATE local backup of existing Windows connection credentials.
# Run only on a computer you administer. This exports actual existing files,
# including saved credentials and keys. It does NOT decrypt DPAPI/WinSCP data.
# Nothing is uploaded, and nothing is written to the Syncthing directory.
# Windows PowerShell 5.1. No extra software, no elevation.
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$base = Join-Path $env:USERPROFILE 'Documents\BeardedWolf-AccessAudit'
$dest = Join-Path $base ('PRIVATE-' + $env:COMPUTERNAME + '-' + $stamp)
New-Item -ItemType Directory -Path $dest -Force | Out-Null

# Restrict access to the exporting Windows account, SYSTEM and Administrators.
# This does not encrypt the files; use a BitLocker volume for transporting them.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
$allow = [Security.AccessControl.AccessControlType]::Allow
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', $allow)))
$sys = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
$adm = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')
foreach ($principal in @($sys, $adm)) {
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($principal, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', $allow)))
}
Set-Acl -LiteralPath $dest -AclObject $acl

$summary = New-Object System.Collections.ArrayList
function Safe-Copy {
    param([string]$Source, [string]$Destination, [string]$Description)
    if (!(Test-Path -LiteralPath $Source)) { return }
    $item = Get-Item -LiteralPath $Source -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        Write-Warning ('Skipped reparse point: ' + $Description)
        return
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
    [void]$summary.Add($Description)
}

$files = Join-Path $dest 'FileZilla'
New-Item -ItemType Directory -Path $files | Out-Null
foreach ($name in @('sitemanager.xml', 'recentservers.xml', 'filezilla.xml')) {
    Safe-Copy (Join-Path $env:APPDATA ('FileZilla\' + $name)) (Join-Path $files $name) ('FileZilla ' + $name)
}

$ssh = Join-Path $env:USERPROFILE '.ssh'
if (Test-Path -LiteralPath $ssh -PathType Container) {
    Safe-Copy $ssh (Join-Path $dest 'Windows-OpenSSH') 'OpenSSH config + local keys'
}

$winscpini = Join-Path $env:APPDATA 'WinSCP.ini'
Safe-Copy $winscpini (Join-Path $dest 'WinSCP.ini') 'WinSCP.ini'
foreach ($pair in @(
    @{ key='HKCU\Software\SimonTatham\PuTTY'; file='PuTTY.reg' },
    @{ key='HKCU\Software\Martin Prikryl\WinSCP 2'; file='WinSCP.reg' }
)) {
    reg.exe query $pair.key *> $null
    if ($LASTEXITCODE -eq 0) {
        & reg.exe export $pair.key (Join-Path $dest $pair.file) /y | Out-Null
        if ($LASTEXITCODE -eq 0) { [void]$summary.Add($pair.file) }
    }
}
@{
    source = $env:COMPUTERNAME
    exported_at = (Get-Date).ToString('o')
    content = @($summary.ToArray())
    notice = 'PRIVATE: may contain passwords and SSH private keys; never upload or sync'
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $dest 'MANIFEST.json')
Write-Output ('PRIVATE backup folder: ' + $dest)
Write-Output ('Sources copied: ' + $summary.Count)
foreach ($x in $summary) { Write-Output ('  ' + $x) }
Write-Warning 'Contains secrets. Keep on this PC or encrypted BitLocker volume. Do NOT upload to chat, GitHub or Syncthing.'
