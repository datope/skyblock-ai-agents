"""Show the speaking agent above Krebes' hotbar using vanilla actionbar."""
from pathlib import Path
import json, logging, threading

class GameOverlay:
    def __init__(self, root):
        self.control = Path(root) / 'skyblock-server' / 'console-commands.txt'
        self.condition = threading.Condition()
        self.speaker = None
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True)
    def start(self): self.thread.start()
    def set_speaker(self, name):
        with self.condition:
            self.speaker = name
            self.condition.notify()
    def _send(self, speaker):
        label = '♪  ' + speaker if speaker else ''
        component = {'text':label, 'color':'green'}
        with self.control.open('a',encoding='utf-8') as f:
            f.write('title @a[name=Krebes] actionbar '+json.dumps(component,ensure_ascii=False)+'\n')
    def _run(self):
        last = None
        while True:
            with self.condition:
                current = self.speaker
                if self.closed: break
                if current is None and last is None:
                    self.condition.wait(timeout=5)
                    continue
                try: self._send(current)
                except OSError: logging.exception('Minecraft actionbar update failed')
                last = current
                self.condition.wait(timeout=1.5 if current else 5)
        if last:
            try: self._send(None)
            except OSError: pass
    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify()
        self.thread.join(timeout=3)
