"""Supervise Skyblock and start a fresh world on Krebes' /airestart."""
from pathlib import Path
import datetime
import hashlib
import json
import ctypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / 'skyblock-server'
RESET = ROOT / 'skyblock-reset'
PAUSE = RESET / 'restarting'
ACTIVE = RESET / 'active'
COMMAND = re.compile(re.escape(os.environ.get('SKYBLOCK_PLAYER', 'Krebes')) + r' issued server command: /airestart\s*$', re.I)
READY = 'Skyblock: one team, one diamond.'
LIVE_LOG = SERVER / 'live-console.log'
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def backup_and_reset(root=ROOT):
    """Move only the three world directories and this project's agent state."""
    server = root / 'skyblock-server'
    backup_root = root / 'skyblock-reset' / 'backups'
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir()
    for source in (server / 'world', server / 'world_nether', server / 'world_the_end', root / '.agent-state'):
        if source.is_symlink():
            raise RuntimeError(f'Refusing to move symlink: {source}')
        if source.exists():
            destination = backup / ('agent-state' if source.name == '.agent-state' else source.name)
            shutil.move(str(source), str(destination))
    return backup


WORLD_NAMES = ('world', 'world_nether', 'world_the_end')
BASELINE_NAME = 'baseline'


def snapshot_manifest(directory):
    """Hash all snapshot files; session locks are never part of a snapshot."""
    result = {}
    for file in sorted(directory.rglob('*')):
        if file.is_symlink():
            raise RuntimeError(f'Symlink in snapshot: {file}')
        if file.is_file() and file.name not in ('session.lock', 'snapshot-manifest.json'):
            h = hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(chunk)
            result[file.relative_to(directory).as_posix()] = h.hexdigest()
    return result


def save_baseline(root=ROOT):
    """Save a complete, verified baseline only while the server is stopped."""
    reset = root / 'skyblock-reset'
    server = root / 'skyblock-server'
    baseline = reset / BASELINE_NAME
    staging = reset / 'baseline-staging'
    if baseline.exists() or staging.exists():
        raise RuntimeError('A baseline or incomplete staging directory already exists; preserve it before replacing.')
    for name in WORLD_NAMES:
        folder = server / name
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError(f'Missing or unsafe world directory: {folder}')
    source_manifest = {}
    for name in WORLD_NAMES:
        for rel, digest in snapshot_manifest(server / name).items():
            source_manifest[f'{name}/{rel}'] = digest
    staging.mkdir(parents=True)
    for name in WORLD_NAMES:
        shutil.copytree(server / name, staging / name, ignore=shutil.ignore_patterns('session.lock'), symlinks=True)
    manifest = snapshot_manifest(staging)
    if manifest != source_manifest:
        raise RuntimeError('Copied baseline differs from the saved world; staging retained.')
    if not manifest or 'world/level.dat' not in manifest:
        raise RuntimeError('Incomplete baseline: world/level.dat is missing.')
    (staging / 'snapshot-manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
    if snapshot_manifest(staging) != manifest:
        raise RuntimeError('Baseline verification failed; staging retained.')
    staging.rename(baseline)
    return baseline


def verify_baseline(root=ROOT):
    baseline = root / 'skyblock-reset' / BASELINE_NAME
    if not baseline.exists():
        return False
    if baseline.is_symlink():
        raise RuntimeError('Refusing symlink baseline.')
    manifest = json.loads((baseline / 'snapshot-manifest.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or 'world/level.dat' not in manifest or snapshot_manifest(baseline) != manifest:
        raise RuntimeError('Baseline is incomplete or corrupt; current world was not replaced.')
    if any(not (baseline / name).is_dir() or (baseline / name).is_symlink() for name in WORLD_NAMES):
        raise RuntimeError('Baseline dimensions are missing or unsafe.')
    return True


def restore_baseline(root=ROOT):
    if not verify_baseline(root):
        return False
    baseline, server = root / 'skyblock-reset' / BASELINE_NAME, root / 'skyblock-server'
    if any((server / name).exists() for name in WORLD_NAMES):
        raise RuntimeError('Refusing to overwrite an existing world during baseline restore.')
    for name in WORLD_NAMES:
        shutil.copytree(baseline / name, server / name)
    expected = json.loads((baseline / 'snapshot-manifest.json').read_text(encoding='utf-8'))
    actual = {}
    for name in WORLD_NAMES:
        for rel, digest in snapshot_manifest(server / name).items():
            actual[f'{name}/{rel}'] = digest
    if actual != expected:
        raise RuntimeError('Restored world failed verification; reset remains paused.')
    return True


def process_alive(pid):
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        return ctypes.get_last_error() != 87  # Invalid PID is gone; other errors fail safe.
    try:
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        return kernel.WaitForSingleObject(handle, 0) != 0
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)


def live_markers():
    live = []
    for marker in ACTIVE.glob('*.pid') if ACTIVE.exists() else []:
        try:
            pid = int(marker.read_text(encoding='ascii').strip())
            if pid <= 0 or not re.fullmatch(r'(ChatGPT|Claude|DeepSeek)-' + str(pid) + r'\.pid', marker.name):
                raise ValueError('Invalid marker')
            if process_alive(pid):
                live.append(marker)
            else:
                marker.unlink(missing_ok=True)
        except (OSError, ValueError):
            live.append(marker)  # Do not reset if a marker cannot be safely verified.
    return live


def wait_for_agents(timeout=30):
    # Supervisors register before starting workers and check the pause a second time.
    deadline = time.monotonic() + timeout
    empty_since = None
    while time.monotonic() < deadline:
        markers = live_markers()
        if markers:
            empty_since = None
        elif empty_since is None:
            empty_since = time.monotonic()
        elif time.monotonic() - empty_since >= 2:
            return
        time.sleep(.2)
    raise RuntimeError('Agents did not stop; world and memory were not reset. Check skyblock-reset/active.')


def run():
    RESET.mkdir(exist_ok=True)
    SERVER.mkdir(exist_ok=True)
    resume = '--resume-reset' in sys.argv
    if PAUSE.exists() and not resume:
        raise RuntimeError('An unfinished reset exists. Inspect skyblock-reset/restarting and backups before restarting.')
    if resume and (not PAUSE.exists() or any((SERVER / name).exists() for name in ('world', 'world_nether', 'world_the_end'))):
        raise RuntimeError('Resume requires a paused reset and all old worlds safely moved to backup.')
    resetting = resume
    restored_baseline = False
    # Tie the voice helpers to the supervisor, not the launcher shell: the
    # server can outlive that shell and /airestart replaces only its child.
    no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    voice_python = ROOT / '.venv-voice' / 'Scripts' / 'python.exe'
    if not voice_python.exists():
        print('Voice helpers are not installed. Run setup-voice.ps1 to enable them.', flush=True)
    for python, script in ((voice_python, ROOT / 'tts' / 'speaker.py'),
                           (voice_python, ROOT / 'stt' / 'listener.py')):
        if Path(python).exists() and script.exists():
            subprocess.Popen([str(python), str(script), '--parent', str(os.getpid())], cwd=ROOT,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=no_window)
    current_child = [None]
    def forward_input():
        for line in sys.stdin:
            child = current_child[0]
            try:
                if child and child.poll() is None:
                    child.stdin.write(line)
                    child.stdin.flush()
            except (OSError, ValueError):
                pass
    threading.Thread(target=forward_input, daemon=True).start()
    while True:
        (ROOT / 'stt' / 'muted.flag').write_text('muted', encoding='ascii')
        child = subprocess.Popen(['node', 'scripts/dev-server.js', '--world', 'void', '--dir', 'skyblock-server'], cwd=ROOT,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding='utf-8', errors='replace', bufsize=1)
        current_child[0] = child
        requested = False
        for line in child.stdout:
            print(line, end='', flush=True)
            clean = ANSI.sub('', line).rstrip()
            # Mirror Paper's console stream as normal log records. Readers tail this
            # separate file and never hold Paper's rotating latest.log open.
            match = re.search(r'\[(\d\d:\d\d:\d\d) (INFO|WARN|ERROR)\]: (.*)', clean)
            if match:
                stamp, level, message = match.groups()
                with LIVE_LOG.open('a', encoding='utf-8') as live:
                    live.write(f'[{stamp}] [Server thread/{level}]: {message}\n')
            if resetting and ((restored_baseline and re.search(r'Done \(.*\)!', clean)) or (not restored_baseline and READY in clean)):
                PAUSE.unlink()
                resetting = False
                print('Skyblock reset complete; agent supervisors may reconnect.', flush=True)
            if COMMAND.search(clean) and not resetting and not requested:
                requested = True
                PAUSE.write_text('Reset in progress. Do not start agents manually.\n', encoding='utf-8')
                child.stdin.write('tellraw @a {"text":"Сбрасываем остров и память агентов. Сервер перезапустится.","color":"gold"}\nstop\n')
                child.stdin.flush()
        code = child.wait()
        if not requested:
            if resetting:
                raise RuntimeError('Server stopped before the new island was ready; reset remains paused.')
            return code
        if code != 0:
            raise RuntimeError(f'Server stopped with exit code {code}; no reset performed.')
        wait_for_agents()
        has_baseline = verify_baseline()
        backup = backup_and_reset()
        restored_baseline = restore_baseline() if has_baseline else False
        print(f'Previous world and agent state saved at {backup}', flush=True)
        if restored_baseline: print('Restored the saved starting world.', flush=True)
        resetting = True


if __name__ == '__main__':
    try:
        sys.exit(run())
    except Exception as exc:
        print(f'SKYBLOCK SUPERVISOR ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
