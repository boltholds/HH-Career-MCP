[CmdletBinding()]
param(
    [string]$Profile = "hh-career-mcp",
    [string]$TunnelClient = "tunnel-client"
)

$ErrorActionPreference = "Stop"

if (-not $env:CONTROL_PLANE_API_KEY) {
    throw "CONTROL_PLANE_API_KEY is not set in this PowerShell session."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$tunnelCommand = Get-Command $TunnelClient -ErrorAction Stop

Push-Location $repoRoot
try {
    & $tunnelCommand.Source doctor --profile $Profile --explain
    if ($LASTEXITCODE -ne 0) {
        throw "tunnel-client doctor failed with exit code $LASTEXITCODE"
    }

    & $tunnelCommand.Source run --profile $Profile
    if ($LASTEXITCODE -ne 0) {
        throw "tunnel-client run failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
