# Skyblock с ИИ-агентами

Основано на [Minecraft Agent Harness от YC Labs](https://github.com/yc-software/minecraft-agent-harness).

## Запуск на Windows

Нужны Minecraft Java 1.21.6, [Node.js 22.19+](https://nodejs.org/), [Java 21](https://adoptium.net/), Python 3.12, Git и доступные в PATH авторизованные [Codex CLI](https://developers.openai.com/codex/cli/) и [Claude Code](https://code.claude.com/docs/en/setup). Для DeepSeek нужен свой API-ключ. Модели должны быть доступны вашим аккаунтам. Использование моделей может быть платным.

В PowerShell в папке проекта:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
npm ci
Copy-Item .env.example .env
notepad .env
```

Впишите ключ в `DEEPSEEK_API_KEY=` и сохраните файл. Не публикуйте `.env`. Убедитесь, что выполнен вход в Codex (`codex login`) и Claude Code (запустите `claude` и войдите). Если `claude.exe` не находится в PATH, задайте полный путь в переменной окружения `CLAUDE_CLI_PATH`.

```powershell
.\start-skyblock-server.ps1 -PlayerName ВашНик -StartAgents
```

При первом запуске скрипт скачает Paper и примет [Minecraft EULA](https://www.minecraft.net/eula). Сервер работает только на `localhost:25565` в offline mode. Подключитесь через Minecraft Java 1.21.6. Остановить сервер можно командой `stop` в окне сервера. В игре указанный ник может использовать `/agents start`, `/agents stop` и `/airestart`. Вместо `-StartAgents` можно запускать скрипты `start-local-agent.ps1`, `start-claude.ps1`, `start-deepseek.ps1` в отдельных окнах после старта сервера.

## Голос (необязательно)

Установите Python 3.12 через Windows Python Launcher, затем выполните:

```powershell
.\setup-voice.ps1              # озвучка через Piper
.\setup-voice.ps1 -Microphone  # также установить Whisper для микрофона
```

Озвучка запускается вместе с сервером. Для микрофона игрок включает `!voice on` в чате и выключает `!voice off`; при первом включении Whisper скачает модель. Голосовые модели и зависимости хранятся локально и не входят в репозиторий.

Docker — необязательная возможность исходного harness, для этого запуска не требуется.
