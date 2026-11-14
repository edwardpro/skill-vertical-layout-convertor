# Vertical-CJK OCR pipeline: design & pitfalls

Target: old scanned books, traditional Chinese, **vertical typesetting read right-to-left**.
Engine: macOS Vision (no network, no third-party OCR). Two complementary APIs:

| API | binary | strength | weakness |
|---|---|---|---|
| `RecognizeDocumentsRequest` (new) | `doc_ocr_bin` | reliable column/line detection, `dir=topToBottom`, paragraph ids | glyph accuracy ~90% on old typeface |
| `VNRecognizeTextRequest` (legacy, `.accurate`) | `ocr_bin` / `batch_ocr_bin` | higher glyph accuracy | flaky full-page detection on tall-narrow pages |

**Hybrid rule:** use the NEW api for *structure* (column boxes, order, paragraph ids) and the
LEGACY api for *text*, matched to columns by x-center. Never trust one API alone.

## Per-page flow (`run_page.py`)
1. Render PDF page at 200 dpi (pymupdf). 300 dpi and contrast/sharpen/binarize do **not** help —
   Vision glyph confusion is the bottleneck, not resolution. Don't waste time preprocessing.
2. `doc_ocr_bin` → observations. Classify each vertical line:
   - running header / book title → `margin` (match by TEXT, e.g. `^我.{0,2}軍$`, not by x position:
     headers alternate left/right on odd/even printed pages).
   - short numeric line low on page → `pagenum`.
   - else → `body`. Sort body by **-x** (right-to-left).
3. Legacy full-page variants: as-is, **square-padded** (fixes tall-narrow detection), 150 dpi.
   Match each tall observation to nearest column center (|Δx|<0.018); keep highest CJK score.
   Reject any result containing kana (wrong-language hallucination).
4. Still-missing columns: per-column crops, square-padded, deskew angles [0,±3,±5,±8], batched
   through `batch_ocr_bin`. Then strip-context recovery (wide vertical strip, target centered).
5. Fallback to new-API text. Write `raw/page_NNN.json`
   `{page, columns[{x,y,w,h,text,src,para}], margin, pagenum, n_body, n_old}`.

`n_old` (columns recovered by legacy) is the quality signal; ~12/12 means a clean page.

## Paragraph reconstruction (`assemble.py`)
- Columns right-to-left; each column top-to-bottom.
- New paragraph when a column is tall (`h>0.3`), its `para` id increases, and its top `y` is
  below the page's tall-column top threshold (indent). Otherwise append to previous paragraph.
- Cross-page: if a page's first paragraph is a continuation (`starts[0]==False`), merge into the
  previous page's trailing buffer.
- Chapter/section headings: **anchor to the printed TOC**, not to OCR. OCR mangles numerals
  (七→亡, 八→爪). Build `anchors[pdf_page]` from config; detect a title column by fuzzy char-set
  overlap (`_sim>=0.5`, short height, no trailing punctuation) and emit the canonical TOC title.
- Strip leaked running-header / page-number fragments and misread quotes (`L`→`」`) in `norm()`.

## Correction dictionary (the accuracy lever)
Raw char accuracy is ~90–95%. Linguistic correction via a replace-dictionary lifts proofread
pages to ~99%. Method:
1. Read a page image, transcribe ground truth, diff against assembled text.
2. Add **global-safe** pairs (形近字 confusions like 昀→的, 部除→部隊) that apply book-wide.
3. Add **context-specific** pairs only where verified against the image (proper nouns, villages,
   rivers). Never guess proper nouns from the dictionary alone — verify on the image.
4. Re-assemble; re-measure. Iterate per chapter.
`assets/seed_corrections.json` ships generic-safe pairs; build a per-book `corrections.json`.

## Measuring accuracy (`measure.py`)
Char-level `difflib` matching-block ratio of GT vs (a) raw concatenated columns and
(b) assembled Markdown page region. Align by GT head/tail so cross-page merges don't skew.
Report both numbers honestly; unproofread pages stay ~90–95%.

## Batch (`drive.py`)
ThreadPoolExecutor (6–8 workers), resumable (skips existing `raw/page_NNN.json`).
~4 s/page. Run in background; poll `raw/` count, don't block.