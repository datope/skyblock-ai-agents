Set-Location $PSScriptRoot
if (-not $env:DEEPSEEK_API_KEY -and -not (Test-Path '.env')) { throw 'Set DEEPSEEK_API_KEY in the environment or the local .env file.' }
Remove-Item Env:MINECRAFT_CODEX,Env:MINECRAFT_CLAUDE -ErrorAction SilentlyContinue
$env:MINECRAFT_DEEPSEEK = '1'
node bin/minecraft-agent.js --name DeepSeek --host 127.0.0.1 --model deepseek/deepseek-flash --sandbox none --objective 'Cooperate with ChatGPT, Claude and DeepSeek in Skyblock. Together put 1 diamond in the starter chest at (-2,65,-4). Mine cobblestone from the existing generator, reach the sand island, build a house and reach the Nether along the way.'
