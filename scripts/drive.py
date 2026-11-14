#!/usr/bin/env python3
"""Parallel, resumable batch OCR over a page range.

Env: same as run_page.py (VLO_PDF, VLO_WORK, VLO_BIN, VLO_LANG, VLO_DPI).
Usage: drive.py [workers] [start] [end]   (1-based inclusive; default 1..VLO_TOTAL)
Skips pages whose raw/page_NNN.json already exists.
"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import run_page

WORK = run_page.WORK
WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
START = int(sys.argv[2]) if len(sys.argv) > 2 else 1
END = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get("VLO_TOTAL", "0")) or START

def done(n):
    return os.path.exists(f"{WORK}/raw/page_{n:03d}.json")

def work(n):
    if done(n):
        return (n, "skip")
    try:
        run_page.process_page(n - 1)
        return (n, "ok")
    except Exception as e:
        return (n, f"ERR {e}")

t0 = time.time()
pages = list(range(START, END + 1))
ok = err = skip = 0
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(work, n): n for n in pages}
    for i, f in enumerate(as_completed(futs)):
        n, st = f.result()
        if st == "ok": ok += 1
        elif st == "skip": skip += 1
        else:
            err += 1
            print(f"PAGE {n}: {st}", flush=True)
        if (i + 1) % 25 == 0:
            print(f"progress {i+1}/{len(pages)} ok={ok} err={err} skip={skip} elapsed={time.time()-t0:.0f}s", flush=True)
print(f"DONE ok={ok} err={err} skip={skip} elapsed={time.time()-t0:.0f}s", flush=True)