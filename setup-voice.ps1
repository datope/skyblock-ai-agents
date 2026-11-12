param([switch]$Microphone)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3.12 -m venv .venv-voice
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }
$python = Join-Path $PSScriptRoot '.venv-voice\Scripts\python.exe'
& $python -m pip install 'piper-tts==1.8.0' sounddevice
if ($LASTEXITCODE -ne 0) { throw 'Could not install voice dependencies.' }
& $python scripts/download-voices.py
if ($LASTEXITCODE -ne 0) { throw 'Could not download voice models.' }
if ($Microphone) {
    & $python -m pip install openai-whisper
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Whisper.' }
}
Write-Host 'Voice setup finished.'
