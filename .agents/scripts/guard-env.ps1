[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$rawInput = [Console]::In.ReadToEnd()

try {
    $payload = $rawInput | ConvertFrom-Json
    $targetFile = ""
    if ($payload.toolCall -and $payload.toolCall.args -and $payload.toolCall.args.TargetFile) {
        $targetFile = $payload.toolCall.args.TargetFile
    }

    if ($targetFile -and ($targetFile -match '(\\|\/)\.env($|\.)' -or $targetFile -like '*.env*')) {
        $response = @{
            decision = "deny"
            reason = "Direct modification of .env is prohibited by eBay Draft Commander rules. Use SettingsManager, the Settings UI, or /api/settings instead."
        }
        $response | ConvertTo-Json -Compress
        exit 0
    }

    if ($targetFile -and ($targetFile -match 'static[\\\/]app[\\\/]')) {
        $response = @{
            decision = "deny"
            reason = "Direct modification of static/app/ is prohibited. It is build output. Modify frontend/src/ and run /build-frontend instead."
        }
        $response | ConvertTo-Json -Compress
        exit 0
    }

    @{ decision = "allow" } | ConvertTo-Json -Compress
} catch {
    @{ decision = "allow" } | ConvertTo-Json -Compress
}
