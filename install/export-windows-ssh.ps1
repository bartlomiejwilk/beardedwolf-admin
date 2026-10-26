# BeardedWolf: local SSH inventory for Windows PowerShell 5.1.
# Does not read passwords, private keys, tokens or connect to servers.
$ErrorActionPreference = "Stop"
$inputFile = Join-Path $env:USERPROFILE ".ssh\config"
$outputFolder = Join-Path $env:USERPROFILE "Documents\BeardedWolf-AccessAudit"
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null
$records = @()
$current = $null
if (Test-Path -LiteralPath $inputFile) {
    foreach ($line in [IO.File]::ReadAllLines($inputFile)) {
        if ($line -match "^\s*Host\s+([a-zA-Z][a-zA-Z0-9_-]{0,31})\s*$") {
            if ($null -ne $current -and $current.host) { $records += $current }
            $current = [ordered]@{ alias=$Matches[1]; host=""; user=""; port=22; protocol="ssh"; source="windows-openssh" }
        } elseif ($null -ne $current -and $line -match "^\s*HostName\s+(\S+)") {
            $current.host = $Matches[1]
        } elseif ($null -ne $current -and $line -match "^\s*User\s+(\S+)") {
            $current.user = $Matches[1]
        } elseif ($null -ne $current -and $line -match "^\s*Port\s+(\d+)") {
            $current.port = [int]$Matches[1]
        }
    }
    if ($null -ne $current -and $current.host) { $records += $current }
}
$outputFile = Join-Path $outputFolder ("ssh-" + $env:COMPUTERNAME + ".json")
if (Test-Path -LiteralPath $outputFile) { throw "Plik juz istnieje. Zrob kopie lub wybierz inna nazwe: $outputFile" }
@{ schema=1; device=$env:COMPUTERNAME; profiles=@($records) } |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outputFile -Encoding UTF8
Write-Output "Zapisano metadane SSH: $outputFile"
Write-Output ("Liczba profili: " + $records.Count)
Write-Output "Bez hasel, kluczy prywatnych i tokenow. Plik nie jest automatycznie wysylany."
