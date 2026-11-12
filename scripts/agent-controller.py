from pathlib import Path
import json, msvcrt, os, re, subprocess, sys, time
ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / 'skyblock-server'
LOG = SERVER / 'live-console.log'
CONTROL = SERVER / 'console-commands.txt'
OUT = ROOT / 'agent-logs'
OBJ = 'Cooperate with ChatGPT, Claude and DeepSeek in Skyblock. Together put 1 diamond in the starter chest at (-2,65,-4). Mine cobblestone from the existing generator, reach the sand island, build a house and reach the Nether along the way.'
SPECS = {'ChatGPT': ('MINECRAFT_CODEX','openai/gpt-6-luna'), 'Claude': ('MINECRAFT_CLAUDE','anthropic/claude-haiku-5-5'), 'DeepSeek': ('MINECRAFT_DEEPSEEK','deepseek/deepseek-flash')}
PLAYER = os.environ.get('SKYBLOCK_PLAYER', 'Krebes')
workers = {}

def announce(msg):
    with CONTROL.open('a', encoding='utf-8') as f:
        f.write('tellraw @a ' + json.dumps({'text':msg,'color':'aqua'}, ensure_ascii=False) + '\n')

def start():
    names=[]
    for name,(flag,model) in SPECS.items():
        if name in workers and workers[name].poll() is None: continue
        env=os.environ.copy()
        for key in ('MINECRAFT_CODEX','MINECRAFT_CLAUDE','MINECRAFT_DEEPSEEK'): env.pop(key,None)
        env[flag]='1'
        thinking = ['--thinking', 'high'] if name == 'Claude' else []
        with (OUT / (name+'.log')).open('ab', buffering=0) as log:
            workers[name]=subprocess.Popen(['node','bin/minecraft-agent.js','--name',name,'--host','127.0.0.1','--model',model,*thinking,'--sandbox','none','--objective',OBJ],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        names.append(name)
    announce('Запускаю агентов: '+', '.join(names) if names else 'Агенты уже запущены.')

def remove():
    for name,p in list(workers.items()):
        if p.poll() is None:
            subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    announce('Агенты отключены.')

def main():
    OUT.mkdir(exist_ok=True)
    lock=(ROOT/'scripts'/'agent-controller.lock').open('a+b')
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError: return
    offset=LOG.stat().st_size if LOG.exists() else 0
    pending=b''
    if '--start' in sys.argv: start()
    start_when_ready = '--start-when-ready' in sys.argv
    while True:
        try:
            if LOG.exists():
                if LOG.stat().st_size < offset: offset=0; pending=b''
                with LOG.open('rb') as f: f.seek(offset); data=f.read(); offset=f.tell()
                lines=(pending+data).split(b'\n'); pending=lines.pop()
                for raw in lines:
                    line=raw.decode('utf-8','replace').strip()
                    if start_when_ready and re.search(r'\bDone \(.*\)!', line):
                        start(); start_when_ready = False
                    m=re.search(re.escape(PLAYER) + r' issued server command: /agents (start|remove|stop)\s*$',line,re.I)
                    if m: (start if m.group(1).lower()=='start' else remove)()
            time.sleep(.3)
        except Exception as e:
            with (OUT/'controller-errors.log').open('a',encoding='utf-8') as f: f.write(repr(e)+'\n')
            time.sleep(1)
if __name__ == '__main__': main()
