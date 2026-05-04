param(
    [string]$Config = "config/accounts.yaml",
    [string]$Html = "report.html",
    [switch]$Json,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

py -V *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python är inte installerat. Kör setup.bat först."
    exit 1
}

$cmd = @("-m", "library_tracker.cli", "--config", $Config)
if ($Html) {
    $cmd += @("--html", $Html)
}
if ($Json) {
    $cmd += "--json"
}
if ($Verbose) {
    $cmd += "--verbose"
}

Write-Host "Running library tracker..."
py @cmd

if ($Html -and (Test-Path $Html)) {
    Write-Host "Opening HTML report: $Html"
    Start-Process $Html
}
