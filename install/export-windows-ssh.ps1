# BeardedWolf Admin - local inventory of connection ENDPOINTS only.
# Windows PowerShell 5.1+; no admin rights, no network calls.
# Never exports passwords, private keys, credential blobs or tokens.
$ErrorActionPreference = 'Stop'
$folder = Join-Path $env:USERPROFILE 'Documents\BeardedWolf-AccessAudit'
New-Item -Path $folder -ItemType Directory -Force | Out-Null
$records = New-Object System.Collections.ArrayList
$counts = @{}

function Add-Endpoint {
    param([string]$Source, [string]$Alias, [string]$HostName,
          [string]$Login, [object]$PortNumber, [string]$Protocol)
    if ([string]::IsNullOrWhiteSpace($HostName)) { return }
    $parsed = 0
    if (-not [int]::TryParse([string]$PortNumber, [ref]$parsed) -or
        $parsed -lt 1 -or $parsed -gt 65535) { $parsed = 0 }
    $record = [ordered]@{
        source = $Source
        alias = $Alias
        host = $HostName.Trim()
        user = $Login
        port = $(if ($parsed -eq 0) { $null } else { $parsed })
        protocol = $Protocol
    }
    [void]$records.Add($record)
    if (-not $counts.ContainsKey($Source)) { $counts[$Source] = 0 }
    $counts[$Source]++
}

# OpenSSH: explicit Host entries; fallback to alias when HostName is absent.
$config = Join-Path $env:USERPROFILE '.ssh\config'
if (Test-Path -LiteralPath $config -PathType Leaf) {
    $current = $null
    function Finish-Host {
        if ($null -eq $current) { return }
        $destination = $current.host
        if (!$destination) { $destination = $current.alias }
        Add-Endpoint 'windows-openssh' $current.alias $destination $current.user $current.port 'ssh'
    }
    foreach ($line in [IO.File]::ReadAllLines($config)) {
        $clean = ($line -replace '\s+#.*$', '').Trim()
        if ($clean -match '^Host\s+(.+)$') {
            Finish-Host
            $alias = $Matches[1].Trim()
            $current = $null
            if ($alias -match '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$' -and
                $alias -notmatch '[*?]') {
                $current = @{ alias=$alias; host=''; user=''; port=22 }
            }
        } elseif ($clean -match '^Match\s+') {
            Finish-Host
            $current = $null
        } elseif ($null -ne $current -and $clean -match '^HostName\s+(\S+)') {
            $current.host = $Matches[1]
        } elseif ($null -ne $current -and $clean -match '^User\s+(\S+)') {
            $current.user = $Matches[1]
        } elseif ($null -ne $current -and $clean -match '^Port\s+(\d+)') {
            $current.port = [int]$Matches[1]
        }
    }
    Finish-Host
}

# PuTTY and WinSCP: allowlisted endpoint properties only.
$sources = @(
    @{ name='putty'; key='Software\SimonTatham\PuTTY\Sessions' },
    @{ name='winscp'; key='Software\Martin Prikryl\WinSCP 2\Sessions' }
)
foreach ($source in $sources) {
    $root = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($source.key)
    if ($null -eq $root) { continue }
    try {
        foreach ($sessionName in $root.GetSubKeyNames()) {
            $session = $root.OpenSubKey($sessionName)
            if ($null -eq $session) { continue }
            try {
                $protocol = if ($source.name -eq 'putty') {
                    [string]$session.GetValue('Protocol', 'ssh')
                } else {
                    'winscp-type-' + [string]$session.GetValue('FSProtocol', 'unknown')
                }
                Add-Endpoint $source.name ([uri]::UnescapeDataString($sessionName)) ([string]$session.GetValue('HostName', '')) ([string]$session.GetValue('UserName', '')) $session.GetValue('PortNumber', 22) $protocol
            } finally { $session.Close() }
        }
    } finally { $root.Close() }
}

# FileZilla: parse site manager and recent servers, select allowlisted fields only.
# Do not export original XML because it may contain password fields.
foreach ($name in @('sitemanager.xml', 'recentservers.xml')) {
    $path = Join-Path $env:APPDATA ('FileZilla\' + $name)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    if ((Get-Item -LiteralPath $path).Length -gt 5242880) {
        Write-Warning ('Pominięto duży plik FileZilla: ' + $name)
        continue
    }
    $settings = New-Object System.Xml.XmlReaderSettings
    $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $reader = $null
    try {
        $reader = [System.Xml.XmlReader]::Create($path, $settings)
        $xml = New-Object System.Xml.XmlDocument
        $xml.XmlResolver = $null
        $xml.Load($reader)
        foreach ($node in $xml.SelectNodes('//Server')) {
            $hostNode = $node.SelectSingleNode('Host')
            if ($null -eq $hostNode) { continue }
            $hostName = [string]$hostNode.InnerText
            $userNode = $node.SelectSingleNode('User')
            $portNode = $node.SelectSingleNode('Port')
            $protocolNode = $node.SelectSingleNode('Protocol')
            $nameNode = $node.SelectSingleNode('Name')
            $rawType = if ($protocolNode) { [string]$protocolNode.InnerText } else { '' }
            $type = switch ($rawType) {
                '1' { 'sftp' }
                '3' { 'ftps' }
                '4' { 'ftps' }
                '0' { 'ftp-security-unverified' }
                default { 'filezilla-type-' + $rawType }
            }
            $label = if ($nameNode) { [string]$nameNode.InnerText } else { $hostName }
            $login = if ($userNode) { [string]$userNode.InnerText } else { '' }
            $port = if ($portNode) { [string]$portNode.InnerText } else {
                if ($rawType -eq '1') { 22 } else { 21 }
            }
            Add-Endpoint ('filezilla-' + $name) $label $hostName $login $port $type
        }
    } catch {
        Write-Warning ('Nie udało się odczytać metadanych z ' + $name)
    } finally {
        if ($null -ne $reader) { $reader.Dispose() }
    }
}

# A fresh timestamped output preserves prior audits.
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outFile = Join-Path $folder ('connections-' + $env:COMPUTERNAME + '-' + $stamp + '.json')
@{
    schema = 1
    device = $env:COMPUTERNAME
    exported_at = (Get-Date).ToString('o')
    profiles = @($records.ToArray())
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Output ('Zapisano: ' + $outFile)
Write-Output ('Liczba wpisów: ' + $records.Count)
foreach ($item in ($counts.Keys | Sort-Object)) {
    Write-Output ('  ' + $item + ': ' + $counts[$item])
}
Write-Output 'Bez haseł, kluczy prywatnych i tokenów. Nie wykonywano połączeń.'
