# Book config schema (`assemble.py <config.json>`)

All page numbers are **PDF pages (1-based)** unless named `printed_*`.
`printed = pdf - pdf_page_offset`. Derive chapters/sections by reading the printed TOC images.

```json
{
  "work": "/abs/work/dir",            // holds pages/ raw/ images/; default cwd
  "out": "/abs/out/book.md",          // default work/<title>.md
  "title": "我與紅軍", "author": "龔楚 著", "publisher": "南風出版社",
  "dpi": 200,
  "pdf_page_offset": 61,              // printed p.1 == pdf p.62
  "corrections": "/abs/corrections.json",   // optional per-book dictionary
  "front_matter": [ {"title":"張序","start":4,"end":7},
                    {"title":"自序","start":8,"end":18},
                    {"title":"導言","start":19,"end":24} ],
  "plates": { "start":25, "end":50, "captions": ["…", "…"] },   // optional
  "map_captions": ["…"],                                            // optional
  "toc": true,
  "body": { "start":62, "end":515 },
  "chapters": [
    { "title":"少年生活的回憶", "printed_start":1,
      "sections":[ {"title":"我的童年","printed_page":1},
                   {"title":"到軍營中去","printed_page":4} ] }
  ]
}
```

Notes:
- `chapters[].sections` order = section order; numbering auto (一…十七 via `cn()`).
- Anchors are `printed_start+offset` / `printed_page+offset`; headings emit canonical titles.
- If a book has no clean TOC, set `chapters:[]` and `toc:false`; headings fall back to OCR text.
- `plates` copies `pages/pNNN_<dpi>.png` → `images/plate_NNN.png` and embeds them.