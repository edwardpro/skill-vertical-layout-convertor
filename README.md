# skill-vertical-layout-convertor

OCR an entire **vertical-typeset (right-to-left) traditional-Chinese book** from a scanned PDF
into a single, structured **Markdown** document — with correct column order, reconstructed
paragraphs, canonical chapter/section headings, and embedded plate images — then sample-proofread
against the page images and report honest character-level accuracy.

A [Qoder](https://qoder.com) Skill powered exclusively by **Apple Vision** (on-device, no network
OCR, no third-party engines).

## Features & Capabilities

- **Vertical CJK layout handling.** Columns are read right-to-left, each column top-to-bottom;
  paragraph starts are detected from top-edge indent, and paragraphs that span page boundaries
  are merged automatically.
- **Hybrid Vision pipeline.** Combines two complementary macOS Vision APIs:
  - `RecognizeDocumentsRequest` (new) for reliable column/line *structure* and paragraph ids;
  - `VNRecognizeTextRequest` (legacy, `.accurate`) for higher-quality *glyph recognition*,
    matched to columns by x-position.
  Robustness stages: square-padding for tall-narrow pages, multi-DPI variants, per-column
  adaptive deskew, and strip-context recovery.
- **Running header / page-number separation.** Classified by text content (not position), so
  alternating left/right headers and numerals never leak into the body; residual fragments and
  misread quotation marks are cleaned during assembly.
- **TOC-anchored headings.** Chapter and section titles are taken from the printed table of
  contents (config), not from error-prone OCR numerals, and located on the page by fuzzy matching.
- **Config-driven assembly.** One JSON config describes front matter, plates, maps, TOC, body
  range, page offset, and chapters/sections — reusable for any vertical book.
- **Correction dictionary.** A replace-dictionary of verified OCR confusion pairs lifts raw
  ~90–95% character accuracy to ~99% on proofread pages. Ships with a generic-safe seed; build a
  per-book dictionary as you proofread.
- **Accuracy measurement.** Char-level `difflib` scoring of a human-transcribed ground truth
  against both raw OCR and the assembled Markdown, reported side by side.
- **Parallel, resumable batch OCR.** Thread-pool driver (~4 s/page) that skips already-processed
  pages, safe to interrupt and restart.

## Requirements

- macOS 15+ (for Vision `RecognizeDocumentsRequest`).
- Swift toolchain (`swiftc`) to build the OCR helpers.
- Python 3 with `pymupdf` and `pillow`.

## Installation

As a Qoder Skill, copy or symlink this directory into `~/.qoder/skills/` (user-level) or
`<project>/.qoder/skills/` (project-level), then restart the session or run `/skills reload`.
Invoke with `/skill-vertical-layout-convertor`.

Or use the scripts directly (below).

## Usage

### 1. Build the OCR helpers and prepare Python

```bash
bash scripts/build.sh                 # -> ./bin/{ocr,doc_ocr,batch_ocr}_bin
python3 -m venv venv
./venv/bin/pip install pymupdf pillow
```

### 2. Batch-OCR the whole book (background, resumable)

```bash
export VLO_PDF=/abs/path/book.pdf
export VLO_WORK=/abs/path/workdir      # holds pages/ raw/ images/
export VLO_BIN=/abs/path/skill/bin
export VLO_LANG=zh-Hant                # recognition language
mkdir -p "$VLO_WORK"
./venv/bin/python scripts/drive.py 8 1 <total_pages> > "$VLO_WORK/drive.log" 2>&1 &
```

Environment variables: `VLO_PDF` (source PDF), `VLO_WORK` (working dir), `VLO_BIN` (helper
binaries), `VLO_LANG` (default `zh-Hant`), `VLO_DPI` (render DPI, default 200), `VLO_TOTAL`
(default end page for `drive.py`).

Single page, for debugging: `./venv/bin/python scripts/run_page.py <pdf-page>`.

### 3. Describe the book in a config

Read the printed TOC / front-matter / plate pages and write `config.json`
(schema and example in [`references/config.md`](references/config.md)): title/author/publisher,
`pdf_page_offset` (printed p.1 ↔ PDF p.N), front-matter ranges, plate range + captions, map
captions, body range, and chapters with sections and their **printed** page numbers.

### 4. Assemble the Markdown

```bash
./venv/bin/python scripts/assemble.py config.json
```

Outputs one Markdown file: front matter, embedded plates, reproduced TOC, and the full body with
anchor-based headings and reconstructed paragraphs.

### 5. Proofread and measure accuracy

For sample pages spread across the book: read the page image, transcribe ground truth to
`gt.txt`, then

```bash
./venv/bin/python scripts/measure.py "$VLO_WORK" <pdf-page> gt.txt <out.md>
# page 250: GT 212 chars
# raw       0.910
# corrected 0.991
```

Diff the ground truth against the assembled text and add verified pairs to a per-book
`corrections.json` (referenced from the config). Global-safe confusion pairs apply book-wide;
context-specific pairs (proper nouns, places) only after checking the image. Re-assemble and
re-measure. `assets/seed_corrections.json` provides generic-safe starting pairs.

## Project structure

```
SKILL.md                     # skill trigger + workflow
scripts/
  build.sh                   # compile the three Vision helpers
  ocr.swift                  # legacy accurate VNRecognizeTextRequest (JSON lines)
  doc_ocr.swift              # RecognizeDocumentsRequest (structure + direction + paragraphs)
  batch_ocr.swift            # batched legacy recognition over stdin paths
  run_page.py                # single-page hybrid pipeline
  drive.py                   # parallel resumable batch
  assemble.py                # config-driven Markdown assembly
  measure.py                 # char-accuracy sampling
references/
  pipeline.md                # design rationale, classification rules, pitfalls
  config.md                  # config schema + example
assets/
  seed_corrections.json      # generic-safe OCR confusion pairs
```

## Notes & limitations

- macOS only; relies on Apple Vision. For horizontal or born-digital PDFs, prefer plain text
  extraction / standard OCR instead.
- Raw accuracy on old typefaces is ~90–95%; ~99% is achieved on pages covered by the correction
  dictionary. Unproofread pages retain residual errors — the tool reports this honestly.
- Higher DPI and image preprocessing do not improve Vision glyph accuracy; the correction
  dictionary is the effective accuracy lever.