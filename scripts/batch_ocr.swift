import Foundation
import Vision
import AppKit

// Reads image paths from stdin (one per line). For each, runs legacy accurate
// VNRecognizeTextRequest and prints {"path":..., "text":...} keeping tall observations.
let lang = CommandLine.arguments.count >= 2 ? CommandLine.arguments[1] : "zh-Hant"

while let line = readLine(strippingNewline: true) {
    let path = line.trimmingCharacters(in: .whitespaces)
    if path.isEmpty { continue }
    var text = ""
    autoreleasepool {
        guard let img = NSImage(contentsOfFile: path),
              let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return }
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        req.recognitionLanguages = [lang]
        req.usesLanguageCorrection = true
        let handler = VNImageRequestHandler(cgImage: cg, options: [:])
        try? handler.perform([req])
        let obs = (req.results ?? []).filter { $0.boundingBox.height > 0.5 }
            .sorted { $0.boundingBox.origin.y > $1.boundingBox.origin.y }
        text = obs.compactMap { $0.topCandidates(1).first?.string }.joined()
    }
    let dict: [String: Any] = ["path": path, "text": text]
    if let data = try? JSONSerialization.data(withJSONObject: dict),
       let s = String(data: data, encoding: .utf8) {
        print(s)
        fflush(stdout)
    }
}