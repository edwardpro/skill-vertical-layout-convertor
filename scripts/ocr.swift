import Foundation
import Vision
import AppKit

// Usage: swift ocr.swift <image> [lang]
// Outputs JSON lines: {"text": ..., "x": ..., "y": ..., "w": ..., "h": ...}
// Coordinates: normalized, top-left origin.

let args = CommandLine.arguments
guard args.count >= 2 else {
    FileHandle.standardError.write("usage: ocr.swift <image> [lang]\n".data(using: .utf8)!)
    exit(1)
}
let path = args[1]
let lang = args.count >= 3 ? args[2] : "zh-Hant"

guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot load image\n".data(using: .utf8)!)
    exit(1)
}

let request = VNRecognizeTextRequest()
let env = ProcessInfo.processInfo.environment
request.recognitionLevel = (env["OCR_LEVEL"] == "fast") ? .fast : .accurate
request.recognitionLanguages = [lang]
request.usesLanguageCorrection = env["OCR_CORRECTION"] != "0"
if let rev = env["OCR_REV"], let r = Int(rev) {
    request.revision = r
}
if env["OCR_AUTO_LANG"] == "1" {
    request.automaticallyDetectsLanguage = true
}

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do {
    try handler.perform([request])
} catch {
    FileHandle.standardError.write("vision error: \(error)\n".data(using: .utf8)!)
    exit(1)
}

let results = request.results ?? []
FileHandle.standardError.write("observations: \(results.count)\n".data(using: .utf8)!)
for obs in results {
    guard let cand = obs.topCandidates(1).first else { continue }
    let bb = obs.boundingBox // normalized, bottom-left origin
    let dict: [String: Any] = [
        "text": cand.string,
        "x": bb.origin.x,
        "y": 1.0 - bb.origin.y - bb.height,
        "w": bb.width,
        "h": bb.height,
        "conf": cand.confidence
    ]
    if let data = try? JSONSerialization.data(withJSONObject: dict),
       let s = String(data: data, encoding: .utf8) {
        print(s)
    }
}