param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host "Installation de l'environnement Python..."
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 ou plus récent est requis.' }
    & $pythonPath -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installation Python interrompue.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    Write-Host "Compilation de l'interface..."
    & npm.cmd ci --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw "Node.js 22.12+ est requis pour installer l'interface." }
    & npm.cmd run build --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'La compilation a échoué.' }
}
$address = 'http://localhost:8000'
$healthAddress = 'http://127.0.0.1:8000/api/health'
$health = $null
try { $health = Invoke-RestMethod -Uri $healthAddress -TimeoutSec 2 } catch { }
if ($health -and $health.schema_version -and $health.rarity_pools) {
    if (-not $NoBrowser) { Start-Process $address }
    Write-Host "Wikidex est déjà disponible : $address"
    exit 0
}
$arguments = @('-m', 'uvicorn', 'backend.wikidex.api:app', '--host', '127.0.0.1', '--port', '8000')
if (Test-Path -LiteralPath (Join-Path $projectRoot '.env')) { $arguments += @('--env-file', '.env') }
$server = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot 'data\server.log') -RedirectStandardError (Join-Path $projectRoot 'data\server-error.log')
Set-Content -LiteralPath (Join-Path $projectRoot 'data\server.pid') -Value $server.Id
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    if ($server.HasExited) { throw 'Le serveur ne démarre pas. Consultez data\server-error.log.' }
    try {
        $health = Invoke-RestMethod -Uri $healthAddress -TimeoutSec 2
        if ($health.schema_version -and $health.rarity_pools) {
            if (-not $NoBrowser) { Start-Process $address }
            Write-Host "Wikidex est prêt : $address"
            exit 0
        }
    } catch { }
    Start-Sleep -Milliseconds 250
}
throw 'Le serveur met trop de temps à répondre. Consultez data\server-error.log.'
