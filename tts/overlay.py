"""Transparent OBS browser overlay, updated only while a voice is playing."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, threading

HTML = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden;font-family:Segoe UI,Arial,sans-serif}
#badge{position:absolute;left:14px;top:14px;display:flex;align-items:center;gap:13px;padding:11px 19px 11px 11px;border:1px solid rgba(255,255,255,.16);border-radius:18px;background:rgba(18,23,29,.91);box-shadow:0 8px 26px rgba(0,0,0,.25);color:white;opacity:0;transform:translateY(8px);transition:opacity .18s,transform .18s}
#badge.on{opacity:1;transform:translateY(0)}.icon{width:43px;height:43px;display:grid;place-items:center;border-radius:13px;background:#8ee09b;color:#13251b;flex:none}svg{width:24px;height:24px}.name{font-weight:700;font-size:22px;letter-spacing:.01em;white-space:nowrap}.sub{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#b7c5bc;margin-bottom:3px}
</style></head><body><div id="badge"><div class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15 9a4 4 0 0 1 0 6M18 6a8 8 0 0 1 0 12"/></svg></div><div><div class="sub">Говорит</div><div id="name" class="name"></div></div></div>
<script>const badge=document.getElementById('badge'),nameEl=document.getElementById('name');async function poll(){try{const r=await fetch('/state',{cache:'no-store'});const s=await r.json();nameEl.textContent=s.speaker||'';badge.classList.toggle('on',!!s.speaker)}catch(e){badge.classList.remove('on')}}poll();setInterval(poll,200);</script></body></html>'''

class SpeakingOverlay:
    def __init__(self, host='127.0.0.1', port=8765):
        self.speaker = None
        self.lock = threading.Lock()
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/state':
                    with owner.lock: data = json.dumps({'speaker':owner.speaker}, ensure_ascii=False).encode('utf-8')
                    content_type = 'application/json; charset=utf-8'
                elif self.path in ('/', '/index.html'):
                    data = HTML.encode('utf-8'); content_type = 'text/html; charset=utf-8'
                else:
                    self.send_error(404); return
                self.send_response(200); self.send_header('Content-Type',content_type); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            def log_message(self, fmt, *args): pass
        self.server = ThreadingHTTPServer((host,port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
    def start(self): self.thread.start()
    def set_speaker(self, name):
        with self.lock: self.speaker = name
    def close(self): self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
