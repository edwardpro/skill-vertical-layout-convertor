#!/usr/bin/env python3
"""Assemble per-page OCR JSONs into a single Markdown book, driven by a config.

Usage: assemble.py <config.json>
See references/config.md for the schema. Pages are PDF page numbers (1-based).
Printed page = PDF page - pdf_page_offset.
"""
import json, os, re, shutil, sys

CJK = re.compile(r'[一-鿿]')
CHAP_RE = re.compile(r'^第.{1,2}章')
SEC_RE = re.compile(r'^[一二三四五六七八九十]{1,3}\s+\S{2,}')
HEADER_LEAK = re.compile(r'^我[與奥爽与][紅红][平算爺軍耳双單]+$')
NUMONLY = re.compile(r'^[一二三四五六七八九十百〇0-9.·]+$')
HEADER_FRAG = re.compile(r'我[與奥与][紅红][双軍耳單单]+|袋與紅單|我與紅第[一二三四五六七八九十式]+')
PAGENUM_FRAG = re.compile(r'一[弐式克貳參参肆伍陸柒捌玖拾][0-9iIlOo:·一二三四五六七八九十百〇克]{0,5}|111:O|一1式')
CN_NUM = "一二三四五六七八九十"

def cn(n):
    return CN_NUM[n - 1] if n <= 10 else '十' + CN_NUM[n - 11]

def _sim(title, t):
    a = set(re.sub(r'[\s—|.·-]', '', title))
    b = set(re.sub(r'[\s—|.·-]', '', t))
    return len(a & b) / len(a) if a else 0

class Assembler:
    def __init__(self, cfg):
        self.cfg = cfg
        self.work = cfg.get("work") or os.getcwd()
        self.seed = {}
        seed = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "seed_corrections.json")
        if os.path.exists(seed):
            self.seed = json.load(open(seed))
        self.corr = {}
        cp = cfg.get("corrections")
        if cp and os.path.exists(cp):
            self.corr = json.load(open(cp))

    def norm(self, t):
        t = re.sub(r'\s+', '', t)
        t = HEADER_FRAG.sub('', t)
        t = PAGENUM_FRAG.sub('', t)
        t = re.sub(r'(?<=[。！？])L(?=[一-鿿])', '」', t)
        t = re.sub(r'(?<=[一-鿿])L(?=[一-鿿])', '', t)
        t = re.sub(r'[。！？]1$', lambda m: m.group(0)[0], t)
        t = t.replace('•', '。').replace('﹒', '。').replace('｡', '。')
        t = re.sub(r'(?<=[一-鿿])\.(?=[一-鿿])', '。', t)
        t = re.sub(r'(?<=[一-鿿]),(?=[一-鿿])', '，', t)
        t = re.sub(r'(?<=[一二三四五六七八九])0(?=[一二三四五六七八九〇年])', '〇', t)
        for a, b in self.corr.items():
            t = t.replace(a, b)
        for a, b in self.seed.items():
            t = t.replace(a, b)
        return t

    def load(self, n):
        p = f"{self.work}/raw/page_{n:03d}.json"
        if not os.path.exists(p):
            return None
        return json.load(open(p))

    def page_paras(self, d, sec_titles=()):
        cols = d['columns']
        if not cols:
            return [], []
        tall = [c['y'] for c in cols if c['h'] > 0.5]
        thr = (min(tall) if tall else min(c['y'] for c in cols)) + 0.018
        paras, starts = [], []
        prev_para = -1
        for c in cols:
            t = c['text']
            if not t:
                continue
            ts = re.sub(r'\s', '', t)
            if HEADER_LEAK.match(ts):
                prev_para = c['para']; continue
            if NUMONLY.match(ts) and len(ts) < 4:
                prev_para = c['para']; continue
            if CHAP_RE.match(t) and c['h'] < 0.5:
                paras.append(('chap', t)); starts.append(True); prev_para = c['para']; continue
            if t in ('張序', '自序', '導言') and c['h'] < 0.2:
                prev_para = c['para']; continue
            if c['h'] < 0.5 and not ts.endswith(('。', '，', '；', '：', '」', '？', '！')):
                if [st for st in sec_titles if len(ts) <= len(st) + 4 and _sim(st, ts) >= 0.5]:
                    paras.append(('sec', t)); starts.append(True); prev_para = c['para']; continue
            if SEC_RE.match(t) and c['h'] < 0.4 and c['y'] < 0.4:
                paras.append(('sec', t)); starts.append(True); prev_para = c['para']; continue
            if not CJK.search(t) and len(t) < 4:
                continue
            new = c['h'] > 0.3 and c['para'] > prev_para and c['y'] > thr
            if new or not paras or isinstance(paras[-1], tuple):
                paras.append(self.norm(t)); starts.append(new)
            else:
                paras[-1] += self.norm(t)
            prev_para = c['para']
        return paras, starts

    def run(self):
        cfg = self.cfg
        md = []
        md.append(f"# {cfg.get('title','')}\n\n{cfg.get('author','')}\n\n{cfg.get('publisher','')}\n")
        md.append("> 整理說明：本文件由原書（繁體豎排）掃描頁經 OCR 自動識別、按豎排從右至左順序還原段落後整理而成；插圖頁以原頁圖像嵌入。個別字詞可能存在識別誤差。\n")
        imgdir = os.path.join(self.work, "images")
        os.makedirs(imgdir, exist_ok=True)

        def emit_range(title, a, b, level="##"):
            md.append(f"\n{level} {title}\n")
            buf = []
            def flush():
                if buf:
                    md.append("\n" + "".join(buf) + "\n"); buf.clear()
            for n in range(a, b + 1):
                d = self.load(n)
                if d is None: continue
                md.append(f"<!-- pdf p.{n} -->")
                paras, starts = self.page_paras(d)
                for i, p in enumerate(paras):
                    if isinstance(p, tuple):
                        flush(); continue
                    if i == 0 and not starts[i] and buf: buf.append(p)
                    elif starts[i] or not buf: flush(); buf.append(p)
                    else: buf.append(p)
            flush()

        for fm in cfg.get("front_matter", []):
            emit_range(fm["title"], fm["start"], fm["end"])

        plates = cfg.get("plates")
        if plates:
            md.append("\n## 插圖\n")
            for n in range(plates["start"], plates["end"] + 1):
                src = f"{self.work}/pages/p{n:03d}_{cfg.get('dpi',200)}.png"
                dst = f"{imgdir}/plate_{n:03d}.png"
                if os.path.exists(src) and not os.path.exists(dst):
                    shutil.copyfile(src, dst)
                md.append(f"\n![插圖 原書第{n}頁](images/plate_{n:03d}.png)\n")
            if plates.get("captions"):
                md.append("\n### 插圖目錄\n")
                for c in plates["captions"]: md.append(f"- {c}")
        if cfg.get("map_captions"):
            md.append("\n### 地圖目錄\n")
            for c in cfg["map_captions"]: md.append(f"- {c}")

        chapters = cfg.get("chapters", [])
        if cfg.get("toc", True) and chapters:
            md.append("\n## 目錄\n")
            md.append("- " + "\n- ".join(fm["title"] for fm in cfg.get("front_matter", [])))
            for ci, ch in enumerate(chapters, 1):
                md.append(f"- 第{cn(ci)}章 {ch['title']}（{ch['printed_start']}）")
                for si, s in enumerate(ch.get("sections", []), 1):
                    md.append(f"  - {cn(si)} {s['title']}（{s['printed_page']}）")
            md.append("")

        off = cfg.get("pdf_page_offset", 0)
        anchors = {}
        for ci, ch in enumerate(chapters, 1):
            anchors.setdefault(ch["printed_start"] + off, []).append(('chap', ci, ch["title"]))
            for si, s in enumerate(ch.get("sections", []), 1):
                anchors.setdefault(s["printed_page"] + off, []).append(('sec', si, s["title"]))

        body = cfg.get("body", {})
        buf = []
        def flush():
            if buf:
                md.append("\n" + "".join(buf) + "\n"); buf.clear()
        for n in range(body.get("start", 1), body.get("end", 0) + 1):
            d = self.load(n)
            if d is None: continue
            md.append(f"<!-- pdf p.{n} -->")
            sec_titles = [a[2] for a in anchors.get(n, []) if a[0] == 'sec']
            paras, starts = self.page_paras(d, sec_titles)
            for i, p in enumerate(paras):
                if isinstance(p, tuple):
                    flush()
                    kind, t = p
                    if kind == 'chap':
                        hit = [a for a in anchors.get(n, []) if a[0] == 'chap']
                        md.append(f"\n## 第{cn(hit[0][1])}章 {hit[0][2]}\n" if hit else f"\n## {self.norm(t)}\n")
                    else:
                        hit = [a for a in anchors.get(n, []) if a[0] == 'sec']
                        md.append(f"\n### {cn(hit[0][1])} {hit[0][2]}\n" if hit else f"\n### {self.norm(t)}\n")
                    continue
                if i == 0 and not starts[i] and buf: buf.append(p)
                elif starts[i] or not buf: flush(); buf.append(p)
                else: buf.append(p)
        flush()

        out = cfg.get("out") or os.path.join(self.work, cfg.get("title", "book") + ".md")
        with open(out, "w") as f:
            f.write("\n".join(md))
        print("wrote", out, os.path.getsize(out), "bytes")
        return out

if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    Assembler(cfg).run()