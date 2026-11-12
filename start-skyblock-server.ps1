param([switch]$ResumeReset, [switch]$StartAgents, [string]$PlayerName = 'Krebes')
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:SKYBLOCK_PLAYER = $PlayerName
$controllerArgs = @((Join-Path $PSScriptRoot 'scripts\agent-controller.py'))
if ($StartAgents) { $controllerArgs += '--start-when-ready' }
Start-Process -FilePath 'python' -ArgumentList $controllerArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
if ($ResumeReset) { python scripts/skyblock-supervisor.py --resume-reset }
else { python scripts/skyblock-supervisor.py }
