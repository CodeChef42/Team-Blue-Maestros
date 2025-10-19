#!/usr/bin/env python3
"""
Safe test script to exercise CrisisGuard detectors in demo_sandbox.
- Creates many files quickly (file rate)
- Writes random bytes (bytes_written + entropy)
- Optionally creates a ransom-note-named file to trigger ransom_note detector
- Optionally performs rapid renames to simulate rename spikes

USAGE:
  python test_trigger_agent.py --count 200 --size_kb 10 --ransom --rename --interval 0.02
"""

import argparse
import os
import sys
import time
import random
from pathlib import Path

# ---------- CONFIG ----------
# Relative to this script's directory (should be project root)
DEFAULT_SANDBOX = Path(__file__).parent.resolve() / "demo_sandbox"
# ----------------------------

def safe_resolve_and_check(path: Path) -> Path:
    path = path.resolve()
    base = Path(__file__).parent.resolve()
    try:
        # ensure sandbox is inside project directory
        path.relative_to(base)
    except Exception:
        raise SystemExit(f"Refusing to operate: {path} is not inside project folder {base}")
    return path

def random_bytes(kb: int) -> bytes:
    # generate pseudo-random bytes (high entropy)
    return os.urandom(kb * 1024)

def create_files(sandbox: Path, count: int, size_kb: int, interval: float, start_index=0):
    paths = []
    for i in range(start_index, start_index + count):
        p = sandbox / f"test_file_{i:05d}.bin"
        with p.open("wb") as f:
            f.write(random_bytes(size_kb))
        paths.append(p)
        if interval > 0:
            time.sleep(interval)
    return paths

def modify_files(paths, iterations: int = 1, size_kb: int = 1, interval: float = 0.01):
    for _ in range(iterations):
        for p in paths:
            try:
                with p.open("ab") as f:  # append to increase bytes_written
                    f.write(random_bytes(size_kb))
            except Exception:
                continue
            if interval > 0:
                time.sleep(interval)

def rename_spike(sandbox: Path, base_name: str, spike_count: int, interval: float):
    originals = []
    for i in range(spike_count):
        src = sandbox / f"{base_name}_rename_src_{i:04d}.txt"
        dst = sandbox / f"{base_name}_rename_dst_{i:04d}.txt"
        src.write_text("rename test\n")
        originals.append((src, dst))
        # rename immediately
        src.rename(dst)
        if interval > 0:
            time.sleep(interval)
    return [dst for _, dst in originals]

def create_ransom_note(sandbox: Path):
    # create a file whose name matches ransom note patterns used by the agent
    p = sandbox / "README_FOR_DECRYPT.txt"
    p.write_text("This is a fake ransom note used to test detector. DO NOT DELETE.\n")
    return p

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", default=str(DEFAULT_SANDBOX), help="Path to demo_sandbox")
    ap.add_argument("--count", type=int, default=120, help="Number of files to create")
    ap.add_argument("--size_kb", type=int, default=8, help="Size per file in KB")
    ap.add_argument("--interval", type=float, default=0.02, help="Delay between file operations (sec)")
    ap.add_argument("--append_iter", type=int, default=2, help="How many append rounds to perform")
    ap.add_argument("--append_size_kb", type=int, default=4, help="KB appended each round")
    ap.add_argument("--ransom", action="store_true", help="Create ransom-note-named file")
    ap.add_argument("--rename", action="store_true", help="Perform a rename spike")
    ap.add_argument("--spike_count", type=int, default=30, help="Number of rapid renames if --rename")
    return ap.parse_args()

def main():
    opts = parse_args()
    sandbox = safe_resolve_and_check(Path(opts.sandbox))
    sandbox.mkdir(parents=True, exist_ok=True)
    print(f"[+] Using sandbox: {sandbox}")

    print(f"[+] Creating {opts.count} files of {opts.size_kb} KB each (interval {opts.interval}s)...")
    created = create_files(sandbox, opts.count, opts.size_kb, opts.interval)
    print(f"[+] Created {len(created)} files. Sleeping 0.5s to let agent pick up events...")
    time.sleep(0.5)

    if opts.append_iter > 0:
        print(f"[+] Appending to files {opts.append_iter} times ({opts.append_size_kb} KB each) ...")
        modify_files(created, iterations=opts.append_iter, size_kb=opts.append_size_kb, interval=opts.interval)

    if opts.rename:
        print(f"[+] Performing rename spike of {opts.spike_count} files...")
        rename_spike(sandbox, "spike", opts.spike_count, opts.interval)

    if opts.ransom:
        print(f"[+] Creating ransom-note-style file...")
        rn = create_ransom_note(sandbox)
        print(f"[+] Created ransom note: {rn.name}")

    print("[+] Test finished. Wait a couple seconds and check your agent /status or WS for alerts.")
    print("    Example: curl http://127.0.0.1:8000/status")
    print("    When done, you can remove sandbox files or keep them for more tests.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user.")
        sys.exit(0)
