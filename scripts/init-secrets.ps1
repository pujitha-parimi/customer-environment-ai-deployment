# Creates .\secrets\*.txt for file-based Docker secrets (Windows PowerShell 5.1+ / PowerShell 7).
# Gemini key: hidden prompt. Tokens/passwords: cryptographically random. Existing files are not overwritten
# unless -RotateTokens / -ReplaceGeminiKey is passed.
param([switch]$RotateTokens, [switch]$ReplaceGeminiKey)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
New-Item -ItemType Directory -Force -Path secrets | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding $false   # no BOM, no trailing newline

function New-RandomToken {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    ([Convert]::ToBase64String($bytes)).TrimEnd('=').Replace('+','-').Replace('/','_')
}
function Put($name, $value) { [System.IO.File]::WriteAllText((Join-Path (Get-Location) "secrets\$name"), $value, $utf8) }
function Empty-Or-Missing($name) { $p = "secrets\$name"; -not (Test-Path $p) -or (Get-Item $p).Length -eq 0 }

if ((Empty-Or-Missing 'gemini_api_key.txt') -or $ReplaceGeminiKey) {
    $secure = Read-Host 'Paste Gemini API key (input hidden)' -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if ([string]::IsNullOrWhiteSpace($plain)) { throw 'Empty key - aborting.' }
    Put 'gemini_api_key.txt' ($plain -replace '\s','')
    Remove-Variable plain
}
foreach ($f in 'customer_api_tokens','metrics_token','grafana_admin_password') {
    if ((Empty-Or-Missing "$f.txt") -or ($RotateTokens -and $f -ne 'grafana_admin_password')) {
        Put "$f.txt" (New-RandomToken); Write-Host "generated secrets\$f.txt"
    }
}
Write-Host 'Done. Customer API token is in secrets\customer_api_tokens.txt (share securely with the client).'
