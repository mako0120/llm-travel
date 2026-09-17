param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) '.env')
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ConfigPath)) { throw ".env was not found: $ConfigPath" }
$settings = @{}
Get-Content -LiteralPath $ConfigPath | ForEach-Object {
    $key, $value = $_ -split '=', 2
    if ($key -and $value) { $settings[$key] = $value }
}
foreach ($key in 'LLM_TRAVEL_WEBHOOK_SECRET', 'LLM_TRAVEL_WEBHOOK_PORT', 'LLM_TRAVEL_WORKSPACE', 'CODEX_WEBHOOK_AUTORUN', 'LLM_TRAVEL_SMEE_URL', 'LLM_TRAVEL_WEBHOOK_ALLOWED_LOGINS') {
    if (-not $settings[$key]) { throw "Missing $key in $ConfigPath" }
}

function Start-RestrictedProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [hashtable]$ProcessEnvironment
    )
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $FilePath
    $info.Arguments = (($ArgumentList | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' }) -join ' ')
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.EnvironmentVariables.Clear()
    foreach ($key in 'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'SSL_CERT_FILE', 'SSL_CERT_DIR') {
        $value = [Environment]::GetEnvironmentVariable($key, 'Process')
        if ($value) { $info.EnvironmentVariables[$key] = $value }
    }
    foreach ($entry in $ProcessEnvironment.GetEnumerator()) { $info.EnvironmentVariables[$entry.Key] = $entry.Value }
    return [System.Diagnostics.Process]::Start($info)
}

$workspace = $settings['LLM_TRAVEL_WORKSPACE']
$receiverSettings = @{}
foreach ($key in 'LLM_TRAVEL_WEBHOOK_SECRET', 'LLM_TRAVEL_WEBHOOK_PORT', 'LLM_TRAVEL_WORKSPACE', 'CODEX_WEBHOOK_AUTORUN', 'LLM_TRAVEL_WEBHOOK_ALLOWED_LOGINS') { $receiverSettings[$key] = $settings[$key] }
$receiver = Start-RestrictedProcess 'python' @('scripts/github_webhook_bridge.py') $workspace $receiverSettings
$relay = Start-RestrictedProcess 'npx.cmd' @('--yes', 'smee-client', '--url', $settings['LLM_TRAVEL_SMEE_URL'], '--target', 'http://127.0.0.1:8766/github-webhook') $workspace @{}
@{ receiver_pid = $receiver.Id; relay_pid = $relay.Id; target = 'http://127.0.0.1:8766/github-webhook' } | ConvertTo-Json -Compress
