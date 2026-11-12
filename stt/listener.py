"""Local microphone transcription for Krebes in the Minecraft chat."""
from __future__ import annotations
import argparse, audioop, ctypes, json, logging, msvcrt, os, queue, re, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'stt' / 'vendor'))
import sounddevice as sd
import numpy as np
import torch
import whisper

LOG = ROOT / 'skyblock-server' / 'live-console.log'
CONTROL = ROOT / 'skyblock-server' / 'console-commands.txt'
MUTE = ROOT / 'stt' / 'muted.flag'
SPEAKING = ROOT / 'tts' / 'speaking-until.txt'
MODEL = 'small'
PLAYER = os.environ.get('SKYBLOCK_PLAYER', 'Krebes')
PAUSE_SECONDS = 1.2
RATE = 16000
JOINED = re.compile(r'\]: ' + re.escape(PLAYER) + r' joined the game\s*$')
LEFT = re.compile(r'\]: ' + re.escape(PLAYER) + r' left the game\s*$')
TOGGLE = re.compile(r'<' + re.escape(PLAYER) + r'>\s+!voice\s+(on|off)\s*$', re.I)


def parent_alive(pid):
    if not pid: return True
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    handle=kernel.OpenProcess(0x100000,False,pid)
    if not handle: return False
    try:
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        return kernel.WaitForSingleObject(handle,0)==0x102
    finally:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        kernel.CloseHandle(handle)


def speaker_active():
    try: return time.time() < float(SPEAKING.read_text(encoding='ascii'))
    except (OSError,ValueError): return False


def clean_text(text):
    text=re.sub(r'\s+', ' ', str(text)).strip()
    if not text or text.startswith('/') or len(text) < 2: return ''
    return text[:200]


def send_text(text):
    text=clean_text(text)
    if not text: return False
    msg={'text':f'<{PLAYER}> (голос) '+text,'color':'white'}
    with CONTROL.open('a',encoding='utf-8') as f:
        f.write('tellraw @a '+json.dumps(msg,ensure_ascii=False)+'\n')
    logging.info('Voice message delivered to server queue (%d characters)',len(text))
    return True


def watch_presence(state, parent):
    file=None; identity=None; partial=b''
    while parent_alive(parent):
        try:
            stat=LOG.stat(); current=(stat.st_dev,stat.st_ino)
            if file is None or current != identity:
                if file: file.close()
                file=LOG.open('rb'); file.seek(max(0,stat.st_size-262144)); data=file.read()
                online=False
                for line in data.decode('utf-8','replace').splitlines():
                    if JOINED.search(line): online=True
                    elif LEFT.search(line): online=False
                state['online']=online; identity=current; partial=b''
            elif stat.st_size < file.tell():
                file.seek(0); state['online']=False; partial=b''
            data=file.read(65536)
            if data:
                lines=(partial+data).split(b'\n'); partial=lines.pop()
                for raw in lines:
                    line=raw.decode('utf-8','replace')
                    if JOINED.search(line): state['online']=True
                    elif LEFT.search(line): state['online']=False
                    else:
                        toggle=TOGGLE.search(line)
                        if toggle:
                            enabled=toggle.group(1).lower()=='on'
                            if enabled: MUTE.unlink(missing_ok=True)
                            else: MUTE.write_text('muted',encoding='ascii')
                            message={'text':'Микрофон включён' if enabled else 'Микрофон выключен','color':'yellow'}
                            with CONTROL.open('a',encoding='utf-8') as f:
                                f.write('tellraw @a[name=Krebes] '+json.dumps(message,ensure_ascii=False)+'\n')
                            logging.info('Microphone %s by player', 'on' if enabled else 'off')
            else: time.sleep(.3)
        except OSError:
            state['online']=False
            if file: file.close(); file=None
            time.sleep(1)
    if file: file.close()
    state['online']=False


def input_device():
    # Refresh between microphone sessions to follow the Windows default device.
    sd._terminate()
    sd._initialize()
    device = sd.default.device[0]
    if device is None or device < 0:
        raise RuntimeError('No default microphone is available.')
    return device


def transcribe_worker(model, device, jobs, state, parent):
    while parent_alive(parent):
        try: audio, generation = jobs.get(timeout=.5)
        except queue.Empty: continue
        try:
            if generation != state['generation'] or not state['online'] or MUTE.exists(): continue
            started=time.monotonic()
            samples=np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            result=model.transcribe(samples, language='ru', fp16=(device == 'cuda'),
                                    condition_on_previous_text=False, temperature=0,
                                    no_speech_threshold=0.6)
            text=result.get('text', '').strip()
            logging.info('Whisper processed %.1f seconds in %.1f seconds', len(samples)/RATE, time.monotonic()-started)
            if text and generation == state['generation'] and state['online'] and not MUTE.exists(): send_text(text)
        except Exception:
            logging.exception('Whisper transcription failed')
        finally: jobs.task_done()


def run_microphone(state, parent):
    device='cuda' if torch.cuda.is_available() else 'cpu'
    model=None
    chunks=queue.Queue(maxsize=30)
    jobs=queue.Queue(maxsize=8)
    def callback(indata, frames, timing, status):
        try: chunks.put_nowait(bytes(indata))
        except queue.Full: logging.warning('Microphone audio queue full; audio dropped')
    while parent_alive(parent):
        if not state['online'] or MUTE.exists():
            time.sleep(.3); continue
        try:
            if model is None:
                model=whisper.load_model(str(MODEL), device=device)
                logging.info('Loaded local Whisper small on %s', device)
                threading.Thread(target=transcribe_worker,args=(model,device,jobs,state,parent),daemon=True).start()
            if not state['online'] or MUTE.exists(): continue
            while not chunks.empty(): chunks.get_nowait()
            microphone = input_device()
            mic_rate = int(sd.query_devices(microphone)['default_samplerate'])
            with sd.RawInputStream(samplerate=mic_rate,blocksize=max(1, mic_rate // 10),device=microphone,dtype='int16',channels=1,callback=callback):
                logging.info('Microphone active while Krebes is online')
                buffered=[]; preroll=[]; last_voice=0; speech_frames=0; resample_state=None
                while state['online'] and not MUTE.exists() and parent_alive(parent):
                    try: data=chunks.get(timeout=.4)
                    except queue.Empty: continue
                    if speaker_active():
                        buffered=[]; preroll=[]; last_voice=0; speech_frames=0; resample_state=None
                        continue
                    data, resample_state=audioop.ratecv(data,2,1,mic_rate,RATE,resample_state)
                    voiced=audioop.rms(data,2)>300
                    now=time.monotonic()
                    if not buffered:
                        preroll=(preroll+[data])[-3:]
                        if voiced:
                            buffered=preroll; preroll=[]; last_voice=now; speech_frames=1
                    else:
                        buffered.append(data)
                        if voiced: last_voice=now; speech_frames+=1
                        if now-last_voice >= PAUSE_SECONDS or len(buffered) >= 200:
                            if speech_frames >= 3:
                                try: jobs.put_nowait((b''.join(buffered),state['generation']))
                                except queue.Full: logging.warning('Whisper queue full; phrase dropped')
                            buffered=[]; preroll=[]; last_voice=0; speech_frames=0
            state['generation']+=1
            logging.info('Microphone inactive')
        except Exception:
            state['generation']+=1
            logging.exception('Microphone failed; retrying in 5 seconds')
            time.sleep(5)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--parent',type=int,default=0); args=parser.parse_args()
    lock=(ROOT/'stt'/'listener.lock').open('a+b')
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError: return
    logging.basicConfig(filename=ROOT/'stt'/'listener.log',encoding='utf-8',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    state={'online':False, 'generation':0}
    threading.Thread(target=watch_presence,args=(state,args.parent),daemon=True).start()
    run_microphone(state,args.parent)
    logging.info('Listener stopped with server')

if __name__=='__main__': main()
