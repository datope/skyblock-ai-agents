from pathlib import Path
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parent.parent / "tts" / "voices"
root.mkdir(parents=True, exist_ok=True)
for name in ("denis", "dmitri", "ruslan"):
    for ext in ("", ".json"):
        filename = f"ru_RU-{name}-medium.onnx{ext}"
        target = root / filename
        if target.exists() and target.stat().st_size:
            continue
        url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/{name}/medium/{filename}"
        print(f"Downloading {filename}...", flush=True)
        temp = target.with_suffix(target.suffix + ".part")
        with urlopen(Request(url, headers={"User-Agent": "skyblock-agents/1.0"}), timeout=120) as response, temp.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temp.replace(target)
