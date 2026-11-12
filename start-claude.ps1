Set-Location $PSScriptRoot
Remove-Item Env:MINECRAFT_CODEX,Env:MINECRAFT_DEEPSEEK -ErrorAction SilentlyContinue
$env:MINECRAFT_CLAUDE = '1'
node bin/minecraft-agent.js --name Claude --host 127.0.0.1 --model anthropic/claude-haiku-5-5 --thinking high --sandbox none --objective 'Cooperate with ChatGPT, Claude and DeepSeek in Skyblock. Together put 1 diamond in the starter chest at (-2,65,-4). Mine cobblestone from the existing generator, reach the sand island, build a house and reach the Nether along the way.'
