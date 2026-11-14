import Foundation
import Vision
import AppKit

// Usage: doc_ocr <image> [lang]
// JSON lines per text line: {"text","x","y","w","h","dir","conf","para"}
// Coords normalized top-left origin.

let args = CommandLine.arguments
guard args.count >= 2 else { exit(1) }
let path = args[1]
let lang = args.count >= 3 ? args[2] : "zh-Hant"

guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot load image\n".data(using: .utf8)!)
    exit(1)
}

func run() async {
    var request = RecognizeDocumentsRequest()
    request.textRecognitionOptions.recognitionLanguages = [Locale.Language(identifier: lang)]
    request.textRecognitionOptions.useLanguageCorrection = true
    request.textRecognitionOptions.automaticallyDetectLanguage = false
    do {
        let results = try await request.perform(on: cg)
        var lineCount = 0
        for doc in results {
            for (pi, para) in doc.document.paragraphs.enumerated() {
                for line in para.lines {
                    let tl = line.topLeft, tr = line.topRight, bl = line.bottomLeft, br = line.bottomRight
                    let minX = min(tl.x, tr.x, bl.x, br.x)
                    let maxX = max(tl.x, tr.x, bl.x, br.x)
                    let minY = min(tl.y, tr.y, bl.y, br.y)
                    let maxY = max(tl.y, tr.y, bl.y, br.y)
                    var dir = "h"
                    if let d = line.textDirection {
                        switch d {
                        case .topToBottom: dir = "v"
                        case .rightToLeft: dir = "rtl"
                        default: dir = "h"
                        }
                    }
                    let dict: [String: Any] = [
                        "text": line.transcript,
                        "x": minX, "y": 1.0 - maxY,
                        "w": maxX - minX, "h": maxY - minY,
                        "dir": dir, "conf": line.confidence, "para": pi,
                        "tl": [tl.x, tl.y], "tr": [tr.x, tr.y],
                        "bl": [bl.x, bl.y], "br": [br.x, br.y]
                    ]
                    if let data = try? JSONSerialization.data(withJSONObject: dict),
                       let s = String(data: data, encoding: .utf8) {
                        print(s)
                    }
                    lineCount += 1
                }
            }
        }
        FileHandle.standardError.write("lines: \(lineCount)\n".data(using: .utf8)!)
    } catch {
        FileHandle.standardError.write("error: \(error)\n".data(using: .utf8)!)
        exit(1)
    }
}

let sem = DispatchSemaphore(value: 0)
Task { await run(); sem.signal() }
sem.wait()