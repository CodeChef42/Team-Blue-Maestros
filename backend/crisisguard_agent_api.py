#!/usr/bin/env python3
"""
CrisisGuard local agent with HTTP API & WebSocket push.

Features:
- Watches SANDBOX_DIR for file events and monitors processes.
- Detection engine (heuristics + optional ML) computes a confidence score.
- FastAPI server exposes:
    POST /set_rates -> update thresholds at runtime
    GET  /status    -> current confidence & detector breakdown
    WS   /ws        -> real-time push of alerts/status updates
- When action threshold reached, agent:
    - snapshots recent files (encrypted)
    - moves most-recent modified file to quarantine
    - sends desktop notification (plyer)
    - pushes alert via WebSocket to connected clients
"""

import os, time, threading, json, shutil, secrets, math, logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque, defaultdict

import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Crypto
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# FastAPI & WebSockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
import uvicorn
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Desktop notifications
try:
    from plyer import notification as desktop_notification
    PLYER_AVAILABLE = True
except Exception:
    PLYER_AVAILABLE = False

# Optional ML
try:
    from sklearn.ensemble import IsolationForest
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False

# -------------------------
# Basic logging
# -------------------------
LOG_FILE = Path.home() / "crisisguard_agent_api.log"
logging.basicConfig(filename=str(LOG_FILE), level=logging.DEBUG,
                    format="%(asctime)s %(levelname)s %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

# -------------------------
# Config & runtime settings (mutable via API)
# -------------------------
BASE_DIR = Path(__file__).parent.resolve()  # folder where crisisguard_agent_api.py lives
SANDBOX_DIR = BASE_DIR / "demo_sandbox"
BACKUP_DIR = BASE_DIR / "demo_backups"
QUARANTINE_DIR = BASE_DIR / "demo_quarantine"

# default thresholds (tunable)
runtime_config = {
    "FILES_MODIFIED_THRESHOLD": 5,    # lower: trigger after few modified files
    "TIME_WINDOW_SECONDS": 15,        # shorter window = faster reactions
    "BYTES_WRITTEN_THRESHOLD": 10 * 1024,  # only ~10 KB before full score
    "RENAMES_THRESHOLD": 2,           # few renames will trigger rename spike
    "ENTROPY_THRESHOLD": 2.0,         # small random data looks "high entropy"
    "CONFIDENCE_ACTION_THRESHOLD": 0.05,  # trigger even on small confidence
    "CONFIDENCE_WARN_THRESHOLD": 0.02,
}

# detector weights
WEIGHTS = {
    "file_rate": 0.25,
    "bytes_written": 0.20,
    "rename_spike": 0.15,
    "ransom_note": 0.20,
    "entropy": 0.2,
    "proc_behavior": 0.25,
    "ml_score": 0.15
}

PROCESS_WHITELIST = {"explorer.exe", "System", "code", "python", "bash", "powershell", "GoogleDriveSync", "DropBox"}

AESGCM_KEY = AESGCM.generate_key(bit_length=256)

# -------------------------
# Utility functions
# -------------------------
def now_ts():
    return datetime.utcnow().isoformat() + "Z"

def ensure_dirs():
    for d in (SANDBOX_DIR, BACKUP_DIR, QUARANTINE_DIR):
        d.mkdir(parents=True, exist_ok=True)

def entropy(data: bytes):
    if not data:
        return 0.0
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    ent = 0.0
    ln = len(data)
    for v in freq.values():
        p = v / ln
        ent -= p * math.log2(p)
    return ent

def encrypt_and_store(filepath: Path, backup_dir: Path = BACKUP_DIR):
    # ensure backup dir exists and is writable
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.exception("Failed to ensure backup_dir exists")
        raise

    aes = AESGCM(AESGCM_KEY)
    nonce = secrets.token_bytes(12)
    try:
        with filepath.open('rb') as f:
            data = f.read()
    except Exception:
        logging.exception("Failed to read file for backup: %s", filepath)
        raise

    try:
        ct = aes.encrypt(nonce, data, None)
    except Exception:
        logging.exception("Encryption failed for: %s", filepath)
        raise

    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    dest = backup_dir / f"{filepath.name}.{stamp}.enc"
    try:
        with dest.open('wb') as out:
            out.write(nonce + ct)
    except Exception:
        logging.exception("Failed to write encrypted snapshot to %s", dest)
        raise


def move_to_quarantine(path: Path):
    try:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        logging.exception("Failed to ensure quarantine dir exists")
        raise

    dest = QUARANTINE_DIR / f"{path.name}.{int(time.time())}"
    try:
        # Use a safe copy (in case path is on different FS) then unlink
        shutil.copy2(path, dest)
        path.unlink(missing_ok=True)  # python 3.8+: for earlier versions check existence then unlink
        logging.warning("Moved to quarantine: %s", dest)
        return dest
    except Exception:
        logging.exception("Failed to move to quarantine: %s -> %s", path, dest)
        raise

def send_desktop_notification(title: str, message: str):
    if PLYER_AVAILABLE:
        try:
            desktop_notification.notify(title=title, message=message, timeout=6)
        except Exception:
            logging.exception("desktop notify failed")
    else:
        logging.info(f"[NOTIFY] {title} - {message}")

# -------------------------
# Sliding window helper
# -------------------------
class SlidingWindowCounter:
    def __init__(self, window_seconds=30):
        self.window = timedelta(seconds=window_seconds)
        self.events = deque()
    def add(self):
        self.events.append(datetime.utcnow())
        self._prune()
    def _prune(self):
        cutoff = datetime.utcnow() - self.window
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
    def count(self):
        self._prune()
        return len(self.events)

# -------------------------
# State
# -------------------------
file_mod_counter = SlidingWindowCounter(window_seconds=runtime_config["TIME_WINDOW_SECONDS"])
bytes_written_window = deque()  # (timestamp, bytes)
rename_counter = SlidingWindowCounter(window_seconds=runtime_config["TIME_WINDOW_SECONDS"])
recent_modified_files = deque(maxlen=200)
ransom_note_patterns = ("README", "HOW_TO_DECRYPT", "RECOVER", "README_FOR_DECRYPT")
proc_writes = defaultdict(lambda: deque())
ml_model = None

# -------------------------
# Filesystem event handler
# -------------------------
class SandboxHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not SANDBOX_DIR in path.parents and path != SANDBOX_DIR:
            return
        # update sliding window counters using current runtime config
        file_mod_counter.add()
        recent_modified_files.append(path)
        try:
            size = path.stat().st_size
        except Exception:
            size = 0
        bytes_written_window.append((datetime.utcnow(), size))
        # prune bytes window
        cutoff = datetime.utcnow() - timedelta(seconds=runtime_config["TIME_WINDOW_SECONDS"])
        while bytes_written_window and bytes_written_window[0][0] < cutoff:
            bytes_written_window.popleft()
        logging.debug(f"Modified: {path} size={size}")

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not SANDBOX_DIR in path.parents and path != SANDBOX_DIR:
            return
        file_mod_counter.add()
        recent_modified_files.append(path)
        logging.debug(f"Created: {path}")
        name = path.name.upper()
        if any(pat in name for pat in ransom_note_patterns):
            logging.warning(f"Ransom note pattern created: {path}")

    def on_moved(self, event):
        src = Path(event.src_path)
        dst = Path(event.dest_path)
        if not SANDBOX_DIR in dst.parents and dst != SANDBOX_DIR:
            return
        rename_counter.add()
        logging.debug(f"Renamed: {src} -> {dst}")

# -------------------------
# Process monitor thread
# -------------------------
def process_monitor_loop(stop_event):
    while not stop_event.is_set():
        for proc in psutil.process_iter(['pid','name','cpu_percent','io_counters']):
            try:
                name = (proc.info.get('name') or "")
                pid = proc.info.get('pid')
                if name in PROCESS_WHITELIST:
                    continue
                cpu = proc.cpu_percent(interval=0.1)
                io = proc.info.get('io_counters')
                writes = 0
                if io:
                    writes = getattr(io, 'write_bytes', 0)
                proc_writes[pid].append((datetime.utcnow(), writes))
                cutoff = datetime.utcnow() - timedelta(seconds=runtime_config["TIME_WINDOW_SECONDS"])
                while proc_writes[pid] and proc_writes[pid][0][0] < cutoff:
                    proc_writes[pid].popleft()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(0.5)

# -------------------------
# Detector functions (use runtime_config)
# -------------------------
def detect_file_rate_score():
    cnt = file_mod_counter.count()
    thr = runtime_config["FILES_MODIFIED_THRESHOLD"]
    score = min(1.0, cnt / max(1.0, thr))
    return score

def detect_bytes_written_score():
    total = sum(sz for ts, sz in bytes_written_window)
    thr = runtime_config["BYTES_WRITTEN_THRESHOLD"]
    score = min(1.0, total / max(1.0, thr))
    return score

def detect_rename_score():
    cnt = rename_counter.count()
    thr = runtime_config["RENAMES_THRESHOLD"]
    score = min(1.0, cnt / max(1.0, thr))
    return score

def detect_ransom_note_score():
    for p in list(recent_modified_files):
        if not p.exists():
            continue
        name = p.name.upper()
        if any(pat in name for pat in ransom_note_patterns):
            return 1.0
    return 0.0

def detect_entropy_score():
    sampled = list(recent_modified_files)[:5]
    scores = []
    thr = runtime_config["ENTROPY_THRESHOLD"]
    for p in sampled:
        try:
            with p.open('rb') as f:
                chunk = f.read(4096)
            e = entropy(chunk)
            scores.append(min(1.0, e / max(0.001, thr)))
        except Exception:
            continue
    return sum(scores)/len(scores) if scores else 0.0

def detect_proc_behavior_score():
    scores = []
    thr = runtime_config["BYTES_WRITTEN_THRESHOLD"] / 10.0
    for pid, dq in list(proc_writes.items()):
        if not dq:
            continue
        if len(dq) >= 2:
            bytes_written = dq[-1][1] - dq[0][1]
            s = min(1.0, bytes_written / max(1.0, thr))
            if s > 0.1:
                scores.append(s)
    return max(scores) if scores else 0.0

def detect_ml_score():
    # placeholder: 0 if no model
    if not ML_AVAILABLE or ml_model is None:
        return 0.0
    fc = file_mod_counter.count()
    bt = sum(sz for ts, sz in bytes_written_window)
    rc = rename_counter.count()
    proc_max = 0
    for dq in proc_writes.values():
        if len(dq) > 1:
            w = dq[-1][1] - dq[0][1]
            proc_max = max(proc_max, w)
    x = [[fc, bt, rc, proc_max]]
    score_raw = ml_model.decision_function(x)[0]
    sc = 0.0
    if score_raw < 0:
        sc = min(1.0, -score_raw / 10.0)
    return sc

def compute_confidence():
    detectors = {
        "file_rate": detect_file_rate_score(),
        "bytes_written": detect_bytes_written_score(),
        "rename_spike": detect_rename_score(),
        "ransom_note": detect_ransom_note_score(),
        "entropy": detect_entropy_score(),
        "proc_behavior": detect_proc_behavior_score(),
        "ml_score": detect_ml_score()
    }
    weighted = sum(WEIGHTS.get(k,0)*v for k,v in detectors.items())
    weight_sum = sum(WEIGHTS.values()) or 1.0
    confidence = weighted / weight_sum
    return confidence, detectors

# -------------------------
# WebSocket manager
# -------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass
    async def broadcast(self, msg: dict):
        living = []
        for conn in list(self.active_connections):
            try:
                await conn.send_json(msg)
                living.append(conn)
            except Exception:
                try:
                    await conn.close()
                except Exception:
                    pass
        self.active_connections = living

manager = ConnectionManager()

# -------------------------
# Actions on detection
# -------------------------
def snapshot_and_alert(confidence, detectors):
    snap_list = []
    for p in list(recent_modified_files)[:20]:
        try:
            logging.debug("Attempting snapshot for %s", p)
            dest = encrypt_and_store(p)
            snap_list.append(str(dest))
        except Exception:
            logging.exception("backup failed for %s", p)
    alert = {
        "timestamp": now_ts(),
        "confidence": confidence,
        "detectors": detectors,
        "snapshots": snap_list
    }

    # soft quarantine last file
    if recent_modified_files:
        target = recent_modified_files[-1]
        try:
            logging.debug("Attempting quarantine for %s", target)
            move_to_quarantine(target)
        except Exception:
            logging.exception("quarantine failed for %s", target)

    send_desktop_notification("CrisisGuard Alert",
                              f"Possible ransomware detected (confidence {confidence:.2f}).")
    return alert

# -------------------------
# FastAPI app & endpoints
# -------------------------
app = FastAPI()
# allow CORS for browser extension local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/set_rates")
async def set_rates(request: Request):
    """
    Accepts JSON body with any subset of keys in runtime_config.
    Example:
    {
      "FILES_MODIFIED_THRESHOLD": 10,
      "BYTES_WRITTEN_THRESHOLD": 5000000
    }
    """
    payload = await request.json()
    updated = {}
    for k, v in payload.items():
        if k in runtime_config:
            try:
                runtime_config[k] = type(runtime_config[k])(v)
                updated[k] = runtime_config[k]
            except Exception:
                return JSONResponse({"error": f"invalid value for {k}"}, status_code=400)
        else:
            return JSONResponse({"error": f"unknown key {k}"}, status_code=400)
    logging.info(f"Runtime config updated: {updated}")
    # update sliding windows if TIME_WINDOW_SECONDS changed
    if "TIME_WINDOW_SECONDS" in updated:
        # recreate sliding counters with new window length
        global file_mod_counter, rename_counter
        file_mod_counter = SlidingWindowCounter(window_seconds=runtime_config["TIME_WINDOW_SECONDS"])
        rename_counter = SlidingWindowCounter(window_seconds=runtime_config["TIME_WINDOW_SECONDS"])
    return {"status": "ok", "updated": updated}

@app.get("/status")
async def status():
    confidence, detectors = compute_confidence()
    return {"confidence": confidence, "detectors": detectors, "runtime_config": runtime_config}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # keep connection open; client can send pings or commands (not required)
            data = await websocket.receive_text()
            # echo for now
            await websocket.send_text(f"pong: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# -------------------------
# Main agent loop (background)
# -------------------------
def agent_loop(stop_event):
    ensure_dirs()
    observer = Observer()
    handler = SandboxHandler()
    observer.schedule(handler, str(SANDBOX_DIR), recursive=True)
    observer.start()

    pm_thread = threading.Thread(target=process_monitor_loop, args=(stop_event,), daemon=True)
    pm_thread.start()

    try:
        while not stop_event.is_set():
            confidence, detectors = compute_confidence()
            if confidence >= runtime_config["CONFIDENCE_ACTION_THRESHOLD"]:
                logging.error(f"CONFIDENCE {confidence:.2f} >= ACTION threshold")
                alert = snapshot_and_alert(confidence, detectors)
                # broadcast alert to WS clients (sync via event loop)
                import asyncio
                asyncio.run(manager.broadcast({"type":"alert","payload": alert}))
                # clear recent files to reduce repeated triggers
                recent_modified_files.clear()
            elif confidence >= runtime_config["CONFIDENCE_WARN_THRESHOLD"]:
                logging.warning(f"CONFIDENCE {confidence:.2f} >= WARN threshold")
            else:
                logging.info(f"Confidence {confidence:.2f}")
            time.sleep(2)
    finally:
        observer.stop()
        observer.join()

# -------------------------
# Start FastAPI server in thread and agent loop in main thread
# -------------------------
def run_api():
    # run uvicorn programmatically
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    print("Starting CrisisGuard agent + API on http://127.0.0.1:8000")
    stop_event = threading.Event()
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    try:
        agent_loop(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
        print("Shutting down...")
