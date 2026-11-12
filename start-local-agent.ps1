Set-Location $PSScriptRoot
$env:MINECRAFT_CODEX = '1'
Remove-Item Env:MINECRAFT_DEEPSEEK,Env:MINECRAFT_CLAUDE -ErrorAction SilentlyContinue
node bin/minecraft-agent.js --name ChatGPT --host 127.0.0.1 --model openai/gpt-6-luna --sandbox none --objective 'Cooperate with ChatGPT, Claude and DeepSeek in Skyblock. Together put 1 diamond in the starter chest at (-2,65,-4). Mine cobblestone from the existing generator, reach the sand island, build a house and reach the Nether along the way.'
