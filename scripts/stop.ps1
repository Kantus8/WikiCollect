$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $projectRoot 'data\server.pid'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Host 'Aucun serveur lancé par ce lanceur.'; exit 0 }
$serverPid = [int](Get-Content -LiteralPath $pidPath)
$processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"
if (-not $processInfo) { Write-Host 'Le serveur est déjà arrêté.'; exit 0 }
$expectedPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if ($processInfo.ExecutablePath -ne $expectedPython -or $processInfo.CommandLine -notlike '*backend.wikidex.api:app*') {
    throw 'Le PID appartient à un autre programme : aucun processus arrêté.'
}
# The Windows venv launcher may have a child Python interpreter.
& taskkill.exe /PID $serverPid /T /F | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Le serveur n'a pas pu être arrêté." }
Write-Host 'Wikidex est arrêté. Votre collection est conservée.'
