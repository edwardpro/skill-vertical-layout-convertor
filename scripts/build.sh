#!/bin/bash
# Compile the three Vision OCR helpers into <out-dir> (default: ./bin).
# Usage: build.sh [out-dir]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HERE/../bin}"
mkdir -p "$OUT"
for name in ocr doc_ocr batch_ocr; do
  swiftc -O "$HERE/$name.swift" -o "$OUT/${name}_bin" 2>/dev/null
  echo "built $OUT/${name}_bin"
done