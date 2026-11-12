"""Speak new public Minecraft agent chat locally with Piper (Windows)."""
from __future__ import annotations
import argparse, audioop, ctypes, io, logging, msvcrt, os, queue, re, sys, threading, time, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tts' / 'vendor'))
sys.path.insert(0, str(ROOT / 'stt' / 'vendor'))
import sounddevice as sd
from piper import PiperVoice
from overlay import SpeakingOverlay
from game_overlay import GameOverlay

VOICES = {'ChatGPT': 'denis', 'Claude': 'dmitri', 'DeepSeek': 'ruslan'}
CHAT = re.compile(r'^\[\d\d:\d\d:\d\d\] \[.*?/INFO\]: (?:\[Not Secure\] )?<(?P<name>ChatGPT|Claude|DeepSeek)> (?P<text>.+)$')
LOG = ROOT / 'skyblock-server' / 'live-console.log'
MAX_AGE = 60


def parse_chat(line):
    match = CHAT.match(line.strip())
    if not match:
        return None
    text = re.sub(r'\s+', ' ', match.group('text')).strip()
    if not text or text.startswith('/'):
        return None
    return match.group('name'), text[:300]


def parent_alive(pid):
    if not pid:
        return True
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
    if not handle:
        return False
    try:
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        return kernel.WaitForSingleObject(handle, 0) == 0x102
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)


def output_device():
    # Refresh PortAudio so a changed Windows default is picked up for the next line.
    sd._terminate()
    sd._initialize()
    device = sd.default.device[1]
    if device is None or device < 0:
        raise RuntimeError('No default audio output is available.')
    return device


def play_audio(wave_bytes):
    with wave.open(io.BytesIO(wave_bytes), 'rb') as src:
        source_rate = src.getframerate()
        pcm = src.readframes(src.getnframes())
        channels = src.getnchannels()
        width = src.getsampwidth()
    if channels != 1 or width != 2:
        raise ValueError('Unexpected Piper audio format')
    device = output_device()
    info = sd.query_devices(device)
    rate = int(info['default_samplerate'])
    out_channels = min(2, int(info['max_output_channels']))
    if out_channels < 1:
        raise RuntimeError('Default audio device has no output channels.')
    pcm, _ = audioop.ratecv(pcm, 2, 1, source_rate, rate, None)
    if out_channels == 2:
        pcm = audioop.tostereo(pcm, 2, 1, 1)
    with sd.RawOutputStream(device=device, samplerate=rate, channels=out_channels, dtype='int16', blocksize=0, latency='high') as output:
        underflow = output.write(pcm)
        if underflow:
            logging.warning('Audio output reported an underrun (device=%s, rate=%s)', device, rate)


def voice_worker(jobs, overlay, game_overlay):
    cache = {}
    while True:
        item = jobs.get()
        if item is None:
            return
        stamp, name, text = item
        if time.monotonic() - stamp > MAX_AGE:
            logging.info('Skipped stale speech from %s', name)
            continue
        try:
            voice_name = VOICES[name]
            if voice_name not in cache:
                cache[voice_name] = PiperVoice.load(str(ROOT / 'tts' / 'voices' / f'ru_RU-{voice_name}-medium.onnx'))
            audio = io.BytesIO()
            with wave.open(audio, 'wb') as wav:
                cache[voice_name].synthesize_wav(text, wav)
            with wave.open(io.BytesIO(audio.getvalue()), 'rb') as info:
                duration = info.getnframes() / info.getframerate()
            # The microphone ignores speaker output and a short echo tail.
            (ROOT / 'tts' / 'speaking-until.txt').write_text(str(time.time() + duration + 1.0), encoding='ascii')
            try:
                if overlay: overlay.set_speaker(name)
                if game_overlay: game_overlay.set_speaker(name)
                play_audio(audio.getvalue())
            finally:
                if overlay: overlay.set_speaker(None)
                if game_overlay: game_overlay.set_speaker(None)
            logging.info('Spoken: %s (%d characters)', name, len(text))
        except Exception:
            logging.exception('Could not speak message from %s', name)


def follow(parent_pid, jobs):
    # Start at EOF: never replay old chat after restart.
    file = None
    identity = None
    partial = b''
    while parent_alive(parent_pid):
        try:
            st = LOG.stat()
            current = (st.st_dev, st.st_ino)
            if file is None or current != identity:
                if file:
                    file.close()
                file = LOG.open('rb')
                file.seek(0, os.SEEK_END)
                identity, partial = current, b''
            elif st.st_size < file.tell():
                file.seek(0)
                partial = b''
            block = file.read(65536)
            if block:
                lines = (partial + block).split(b'\n')
                partial = lines.pop()
                for line in lines:
                    parsed = parse_chat(line.decode('utf-8', 'replace'))
                    if parsed:
                        try:
                            jobs.put_nowait((time.monotonic(), *parsed))
                        except queue.Full:
                            logging.warning('Speech queue full; skipped %s', parsed[0])
            else:
                time.sleep(.2)
        except (FileNotFoundError, PermissionError, OSError) as exc:
            logging.warning('Waiting for server log: %s', exc)
            if file:
                file.close()
                file = None
            time.sleep(1)
    if file:
        file.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=int, default=0)
    args = parser.parse_args()
    lock = (ROOT / 'tts' / 'speaker.lock').open('a+b')
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return
    logging.basicConfig(filename=ROOT / 'tts' / 'speaker.log', encoding='utf-8', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    jobs = queue.Queue(maxsize=12)
    try:
        overlay = SpeakingOverlay()
        overlay.start()
        logging.info('Overlay ready at http://127.0.0.1:8765/')
    except OSError:
        overlay = None
        logging.exception('Overlay unavailable; speech remains enabled')
    game_overlay = GameOverlay(ROOT)
    game_overlay.start()
    logging.info('Minecraft speaking indicator ready')
    threading.Thread(target=voice_worker, args=(jobs, overlay, game_overlay), daemon=True).start()
    logging.info('Speaker started; voices: %s', VOICES)
    follow(args.parent, jobs)
    game_overlay.close()
    if overlay: overlay.close()
    logging.info('Speaker stopped with server')

if __name__ == '__main__':
    main()
