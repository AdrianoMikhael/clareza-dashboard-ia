# Reutiliza SOMENTE o ambiente preparado nesta pasta de trabalho.
# Para outro computador, use compose.yaml conforme o README.
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskWorkspace = Split-Path (Split-Path $taskRoot -Parent) -Parent
$taskRuntime = Join-Path $taskWorkspace 'work/runtime'
$taskPython = Join-Path $taskWorkspace 'work/venv/Scripts/python.exe'
$taskPg = 'C:/Program Files/PostgreSQL/18/bin/postgres.exe'
$taskLlama = Join-Path $taskRuntime 'ollama/lib/ollama/llama-server.exe'

function Test-DemoPort([int] $Port) {
    $taskClient = New-Object System.Net.Sockets.TcpClient
    try { $taskClient.Connect('127.0.0.1', $Port); return $true }
    catch { return $false }
    finally { $taskClient.Dispose() }
}

foreach ($taskFile in @($taskPython, $taskPg, $taskLlama, (Join-Path $taskRuntime 'model-path.txt'))) {
    if (-not (Test-Path -LiteralPath $taskFile)) {
        throw 'O ambiente preparado nao foi encontrado. Use a instalacao com Docker descrita no README.'
    }
}

if (-not (Test-DemoPort 55432)) {
    $taskData = Join-Path $taskRuntime 'pgdata'
    Start-Process -FilePath $taskPg -ArgumentList '-D', ('"' + $taskData + '"'), '-p', '55432', '-h', '127.0.0.1' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRuntime 'pg.stdout.log') -RedirectStandardError (Join-Path $taskRuntime 'pg.stderr.log')
}
if (-not (Test-DemoPort 11435)) {
    $taskModel = (Get-Content -LiteralPath (Join-Path $taskRuntime 'model-path.txt') -Raw).Trim()
    Start-Process -FilePath $taskLlama -ArgumentList '-m', ('"' + $taskModel + '"'), '--host', '127.0.0.1', '--port', '11435', '-c', '8192', '-t', '4', '-ngl', '0', '--jinja' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRuntime 'model.stdout.log') -RedirectStandardError (Join-Path $taskRuntime 'model.stderr.log')
}
for ($taskAttempt = 0; $taskAttempt -lt 30; $taskAttempt++) {
    if ((Test-DemoPort 55432) -and (Test-DemoPort 11435)) { break }
    Start-Sleep -Seconds 1
}
$env:DATABASE_URL = 'postgresql+psycopg://dashboard@127.0.0.1:55432/dashboard'
$env:AI_BACKEND = 'llamacpp'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11435'
$env:OLLAMA_MODEL = 'qwen2.5:1.5b'
if (Test-DemoPort 8501) {
    Write-Host 'Dashboard ja disponivel em http://127.0.0.1:8501'
} else {
    Set-Location -LiteralPath $taskRoot
    & $taskPython run.py
}
