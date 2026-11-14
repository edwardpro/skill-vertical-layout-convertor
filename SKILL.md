---
name: skill-vertical-layout-convertor
description: OCR a full vertical-typeset (right-to-left) traditional-Chinese PDF book into a single structured Markdown file using a macOS Vision hybrid pipeline, then proofread and report char accuracy. Use when the user asks to OCR/convert/extract a scanned vertical CJK book (豎排/竖排/繁體/古籍/old scanned PDF) to Markdown/text, reconstruct Chinese paragraphs from vertical columns, or verify OCR accuracy. macOS only (Apple Vision).
---

# Vertical-Layout CJK Book → Markdown

## Overview
Convert an entire scanned vertical-typeset Chinese book (read right-to-left) into one Markdown
document with correct column order, paragraph breaks, chapter/section headings, and embedded
plates; then sample-proofread against page images and report honest char accuracy. macOS Vision
only — no network OCR.

## When to use
Vertical (豎排) traditional-Chinese scanned PDFs. For horizontal or modern born-digital PDFs,
prefer plain text extraction / standard OCR instead.

## Workflow

### 1. Setup (once per machine)
```bash
bash scripts/build.sh            # compiles ocr_bin / doc_ocr_bin / batch_ocr_bin into ./bin
python3 -m venv venv && ./venv/bin/pip install pymupdf pillow
```
Requires macOS with Vision `RecognizeDocumentsRequest` (macOS 15+). Swift via `swiftc`.

### 2. Per-book working dir + batch OCR
Create a work dir; export env; run the resumable parallel batch in background:
```bash
export VLO_PDF=/abs/book.pdf VLO_WORK=/abs/work VLO_BIN=/abs/skill/bin VLO_LANG=zh-Hant
mkdir -p "$VLO_WORK"
./venv/bin/python scripts/drive.py 8 1 <total_pages> > "$VLO_WORK/drive.log" 2>&1 &
```
Poll `ls "$VLO_WORK"/raw/page_*.json | wc -l`; ~4 s/page. Read `references/pipeline.md` for the
hybrid design and why each stage exists before tweaking anything.

### 3. Build the book config from the printed TOC
Render and READ the TOC / front-matter / plate pages; transcribe chapter & section titles with
their **printed** page numbers; determine `pdf_page_offset` (printed p.1 ↔ pdf p.N).
Write `config.json` per `references/config.md`. Do not guess proper nouns — read the images.

### 4. Assemble
```bash
./venv/bin/python scripts/assemble.py config.json
```
Produces the Markdown: front matter, plates (embedded), TOC, and body with anchor-based
headings, right-to-left column order, indent-based paragraphs, cross-page merge.

### 5. Proofread + measure (the accuracy lever)
Pick sample pages spread across the book. For each: READ the page PNG, transcribe ground truth
to `gt.txt`, then:
```bash
./venv/bin/python scripts/measure.py "$VLO_WORK" <pdf_page> gt.txt <out.md>
```
Diff GT vs assembled text; add verified pairs to a per-book `corrections.json` (global-safe
形近字 pairs book-wide; context-specific pairs only after image verification). Re-assemble and
re-measure. `assets/seed_corrections.json` provides generic-safe starting pairs.
Report raw vs corrected accuracy honestly; unproofread pages remain ~90–95%.

## Resources
- `scripts/build.sh`, `ocr.swift`, `doc_ocr.swift`, `batch_ocr.swift` — Vision helpers.
- `scripts/run_page.py` — single-page hybrid pipeline (env-driven).
- `scripts/drive.py` — parallel resumable batch.
- `scripts/assemble.py` — config-driven Markdown assembly.
- `scripts/measure.py` — char-accuracy sampling.
- `references/pipeline.md` — design rationale, classification rules, pitfalls, correction method.
- `references/config.md` — config schema + example.
- `assets/seed_corrections.json` — generic-safe OCR confusion pairs.