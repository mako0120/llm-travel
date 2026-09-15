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
foreach ($key in 'LLM_TRAVEL_WEBHOOK_SECRET', 'LLM_TRAVEL_WEBHOOK_PORT', 'LLM_TRAVEL_WORKSPACE', 'CODEX_WEBHOOK_AUTORUN', 'LLM_TRAVEL_SMEE_URL') {
    if (-not $settings[$key]) { throw "Missing $key in $ConfigPath" }
}
foreach ($entry in $settings.GetEnumerator()) { Set-Item -Path "env:$($entry.Key)" -Value $entry.Value }
$workspace = $settings['LLM_TRAVEL_WORKSPACE']
$receiver = Start-Process -FilePath python -ArgumentList 'scripts/github_webhook_bridge.py' -WorkingDirectory $workspace -WindowStyle Hidden -PassThru
$relay = Start-Process -FilePath npx.cmd -ArgumentList '--yes smee-client', '--url', $settings['LLM_TRAVEL_SMEE_URL'], '--target', 'http://127.0.0.1:8766/github-webhook' -WorkingDirectory $workspace -WindowStyle Hidden -PassThru
@{ receiver_pid = $receiver.Id; relay_pid = $relay.Id; target = 'http://127.0.0.1:8766/github-webhook' } | ConvertTo-Json -Compress
