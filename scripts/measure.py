#!/usr/bin/env python3
"""Char-level accuracy of one assembled page against a human-transcribed ground truth.

Usage: measure.py <work-dir> <pdf-page> <gt.txt> [md-path]
  gt.txt  = ground-truth transcription of the page (or a contiguous excerpt),
            read right-to-left, top-to-bottom, whitespace ignored.
Prints raw (concatenated OCR columns) and corrected (assembled Markdown) accuracy.
"""
import json, os, re, sys, difflib

def acc(gt, seg):
    sm = difflib.SequenceMatcher(None, gt, seg)
    return sum(b.size for b in sm.get_matching_blocks()) / len(gt) if gt else 0

def main():
    work, page, gtp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    gt = re.sub(r'\s', '', open(gtp).read())
    d = json.load(open(f"{work}/raw/page_{page:03d}.json"))
    raw = re.sub(r'\s', '', ''.join(c['text'] for c in d['columns']))
    mdpath = sys.argv[4] if len(sys.argv) > 4 else None
    if not mdpath:
        cands = [f for f in os.listdir(work) if f.endswith('.md')]
        mdpath = os.path.join(work, cands[0]) if cands else None
    md_raw = open(mdpath).read() if mdpath else ""
    m = re.search(rf'<!-- pdf p\.{page} -->(.*?)(?=<!-- pdf p\.|\Z)', md_raw, re.S)
    mdseg = re.sub(r'\s', '', m.group(1)) if m else ""
    # align by first/last few chars of GT so merged cross-page paragraphs don't skew
    def align(seg):
        if not seg: return ""
        i = seg.find(gt[:6]); j = seg.find(gt[-6:])
        if i >= 0 and j >= i: return seg[i:j + 6]
        return seg
    print(f"page {page}: GT {len(gt)} chars")
    print(f"raw      {acc(gt, align(raw)):.3f}")
    print(f"corrected {acc(gt, align(mdseg)):.3f}")

if __name__ == "__main__":
    main()