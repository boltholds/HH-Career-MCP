[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TunnelId,

    [string]$Profile = "hh-career-mcp",
    [string]$TunnelClient = "tunnel-client",
    [string]$PythonExecutable = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $PythonExecutable) {
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExecutable = $venvPython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction Stop
        $PythonExecutable = $pythonCommand.Source
    }
}

$tunnelCommand = Get-Command $TunnelClient -ErrorAction Stop
$pythonPath = (Resolve-Path $PythonExecutable).Path.Replace("\", "/")
$mcpCommand = '"{0}" -m hh_career_mcp.server' -f $pythonPath

$argsList = @("init")
if ($Force) {
    $argsList += "--force"
}
$argsList += @(
    "--profile", $Profile,
    "--tunnel-id", $TunnelId,
    "--mcp-command", $mcpCommand,
    "--open-web-ui"
)

Push-Location $repoRoot
try {
    & $tunnelCommand.Source @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "tunnel-client init failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Host "Tunnel profile '$Profile' is ready."
Write-Host "Run scripts\run-tunnel.ps1 after setting CONTROL_PLANE_API_KEY."
