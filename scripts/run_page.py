#!/usr/bin/env python3
"""Hybrid Vision OCR for ONE page of a vertical-typeset CJK PDF.

Pipeline:
  1. RecognizeDocumentsRequest (doc_ocr_bin) -> column boxes + structure (reliable detection)
  2. legacy accurate API (ocr_bin) on full-page variants (as-is / square-padded / 150dpi)
     -> high-quality text matched to columns by x position
  3. per-column adaptive deskew (batch_ocr_bin) for columns still missing
  4. strip-context recovery, then new-API text as fallback
Columns ordered right-to-left; paragraph starts flagged by top-y indent.

Env:
  VLO_PDF   absolute path to the source PDF (required)
  VLO_WORK  working dir holding pages/ raw/ crops/ (default: cwd)
  VLO_BIN   dir with ocr_bin/doc_ocr_bin/batch_ocr_bin (default: $VLO_WORK/bin)
  VLO_LANG  recognition language (default: zh-Hant)
  VLO_DPI   render dpi (default: 200)
Usage: run_page.py <pdf-page-number-1based>
"""
import json, os, re, subprocess, sys
from PIL import Image
import pymupdf

WORK = os.environ.get("VLO_WORK") or os.getcwd()
PDF = os.environ.get("VLO_PDF")
BIN = os.environ.get("VLO_BIN") or os.path.join(WORK, "bin")
LANG = os.environ.get("VLO_LANG", "zh-Hant")
DPI = int(os.environ.get("VLO_DPI", "200"))
KANA = re.compile(r'[぀-ヿ]')
CJK = re.compile(r'[一-鿿]')
HEADERS = {'張序', '自序', '導言', '目錄', '插圖目錄', '地圖目錄'}
HEADER_RE = re.compile(r'^我.{0,2}軍$')
NUMV_RE = re.compile(r'^[一二三四五六七八九十百〇0-9iIlOo·]+$')

def score(t):
    if not t or KANA.search(t):
        return -1
    return len(CJK.findall(t))

def run(cmd, inp=None):
    return subprocess.run(cmd, input=inp, capture_output=True, text=True, cwd=WORK)

def ocr_image(path):
    r = run([f"{BIN}/ocr_bin", path, LANG])
    return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]

def process_page(i):
    if not PDF:
        raise SystemExit("VLO_PDF not set")
    os.makedirs(f"{WORK}/pages", exist_ok=True)
    os.makedirs(f"{WORK}/raw", exist_ok=True)
    n = i + 1; tag = f"{n:03d}"
    img = f"{WORK}/pages/p{tag}_{DPI}.png"
    if not os.path.exists(img):
        d = pymupdf.open(PDF); d[i].get_pixmap(dpi=DPI).save(img); d.close()
    r = run([f"{BIN}/doc_ocr_bin", img, LANG])
    obs = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    body, margin, hnum = [], [], []
    for o in obs:
        t = re.sub(r'\s', '', o['text'])
        if o['dir'] == 'v':
            if t in HEADERS or (3 <= len(t) <= 6 and HEADER_RE.match(t)):
                margin.append(o)
            elif o['h'] < 0.2 and o['y'] > 0.6 and NUMV_RE.match(t):
                hnum.append(o)
            else:
                body.append(o)
        elif o['dir'] == 'h' and o['y'] > 0.8:
            hnum.append(o)
    body.sort(key=lambda o: -o['x'])
    if not body:
        out = {"page": n, "columns": [], "margin": [o['text'] for o in margin],
               "pagenum": [o['text'] for o in hnum], "n_body": 0, "n_old": 0}
        with open(f"{WORK}/raw/page_{tag}.json", "w") as f:
            json.dump(out, f, ensure_ascii=False)
        return out
    centers = [o['x'] + o['w'] / 2 for o in body]
    best = [(-1, "") for _ in body]

    im = Image.open(img).convert("L"); W, H = im.size
    variants = [("asis", img, lambda x: x)]
    sq = f"{WORK}/pages/_sq_{tag}.png"
    canvas = Image.new("L", (H, H), 255); canvas.paste(im, ((H - W) // 2, 0)); canvas.save(sq)
    off = (H - W) / 2
    variants.append(("sq", sq, lambda x: (x * H - off) / W))
    p150 = f"{WORK}/pages/_150_{tag}.png"
    im.resize((int(W * 150 / DPI), int(H * 150 / DPI)), Image.LANCZOS).save(p150)
    variants.append(("150", p150, lambda x: x))

    for name, path, xform in variants:
        for o in ocr_image(path):
            if o['h'] < 0.4:
                continue
            cx = xform(o['x'] + o['w'] / 2)
            j = min(range(len(centers)), key=lambda k: abs(centers[k] - cx))
            if abs(centers[j] - cx) < 0.018:
                s = score(o['text'])
                if s > best[j][0]:
                    best[j] = (s, o['text'])
    for v in (sq, p150):
        os.remove(v)

    cdir = f"{WORK}/crops/{tag}"; os.makedirs(cdir, exist_ok=True)
    missing = [j for j in range(len(body)) if best[j][0] < 3 and body[j]['h'] > 0.4]
    if missing:
        paths = []
        for j in missing:
            o = body[j]
            for a in [0, -3, 3, -5, 5, -8, 8]:
                m = 0.002
                crop = im.crop((max(0, int((o['x'] - m) * W)), max(0, int((o['y'] - m) * H)),
                                min(W, int((o['x'] + o['w'] + m) * W)), min(H, int((o['y'] + o['h'] + m) * H))))
                if a:
                    crop = crop.rotate(a, expand=True, fillcolor=255, resample=Image.BICUBIC)
                w, h = crop.size; side = max(w, h)
                sqc = Image.new("L", (side, side), 255); sqc.paste(crop, ((side - w) // 2, (side - h) // 2))
                p = f"{cdir}/{j}_{a}.png"; sqc.save(p); paths.append(p)
        r = run([f"{BIN}/batch_ocr_bin", LANG], inp="\n".join(paths))
        for l in r.stdout.splitlines():
            if not l.strip(): continue
            d = json.loads(l)
            j = int(os.path.basename(d['path']).split('_')[0])
            s = score(d['text'])
            if s > best[j][0]:
                best[j] = (s, d['text'])
    for f in os.listdir(cdir):
        os.remove(os.path.join(cdir, f))
    os.rmdir(cdir)

    still = [j for j in range(len(body)) if best[j][0] < 3 and body[j]['h'] > 0.4]
    if still:
        os.makedirs(cdir, exist_ok=True)
        for j in still:
            cx = centers[j]; half = 0.09
            x0 = max(0, int((cx - half) * W)); x1 = min(W, int((cx + half) * W))
            crop = im.crop((x0, 0, x1, H))
            w, h = crop.size; side = max(w, h)
            sqc = Image.new("L", (side, side), 255); sqc.paste(crop, ((side - w) // 2, 0))
            p = f"{cdir}/strip_{j}.png"; sqc.save(p)
            cands = [o for o in ocr_image(p) if o['h'] > 0.4]
            if cands:
                o = min(cands, key=lambda o: abs(o['x'] + o['w'] / 2 - 0.5))
                s = score(o['text'])
                if s > best[j][0]:
                    best[j] = (s, o['text'])
        for f in os.listdir(cdir):
            os.remove(os.path.join(cdir, f))
        os.rmdir(cdir)

    cols = []
    for o, (s, t) in zip(body, best):
        text = t if s >= 3 else (o['text'] or "")
        cols.append({"x": o['x'], "y": o['y'], "w": o['w'], "h": o['h'],
                     "text": text, "src": "old" if s >= 3 else "new", "para": o['para']})
    out = {"page": n, "columns": cols, "margin": [o['text'] for o in margin],
           "pagenum": [o['text'] for o in hnum], "n_body": len(body),
           "n_old": sum(1 for c in cols if c['src'] == 'old')}
    with open(f"{WORK}/raw/page_{tag}.json", "w") as f:
        json.dump(out, f, ensure_ascii=False)
    return out

if __name__ == "__main__":
    out = process_page(int(sys.argv[1]) - 1)
    print(f"page {out['page']}: {out['n_body']} cols, old={out['n_old']}, margin={out['margin']}, num={out['pagenum']}")