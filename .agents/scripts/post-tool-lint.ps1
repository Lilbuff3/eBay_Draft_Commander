[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$rawInput = [Console]::In.ReadToEnd()

try {
    $payload = $rawInput | ConvertFrom-Json
    $targetFile = ""
    if ($payload.toolCall -and $payload.toolCall.args -and $payload.toolCall.args.TargetFile) {
        $targetFile = $payload.toolCall.args.TargetFile
    }

    if ($targetFile -and ($targetFile -match 'frontend[\\\/]src[\\\/].*\.(ts|tsx|js|jsx)$')) {
        $repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
        Push-Location "$repoRoot\frontend"
        try {
            npx eslint --fix $targetFile 2>$null
        } finally {
            Pop-Location
        }
    }
} catch {
    # Non-fatal
}

Write-Output "{}"
