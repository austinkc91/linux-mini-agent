import Vision
import AppKit
import Foundation

struct OCRResult: Codable {
    let text: String
    let confidence: Double
    let x: Int
    let y: Int
    let width: Int
    let height: Int
}

enum OCR {
    static func recognize(image: CGImage, minimumConfidence: Float = 0.5) throws -> [OCRResult] {
        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.minimumTextHeight = 0.01
        request.usesLanguageCorrection = true
        try handler.perform([request])

        guard let observations = request.results else { return [] }
        let imgW = Double(image.width)
        let imgH = Double(image.height)

        return observations.compactMap { obs -> OCRResult? in
            guard let candidate = obs.topCandidates(1).first,
                  candidate.confidence >= minimumConfidence else { return nil }
            let box = obs.boundingBox
            return OCRResult(
                text: candidate.string,
                confidence: Double(candidate.confidence),
                x: Int(box.origin.x * imgW),
                y: Int((1.0 - box.origin.y - box.height) * imgH),
                width: Int(box.width * imgW),
                height: Int(box.height * imgH)
            )
        }
    }

    static func toElements(_ results: [OCRResult]) -> [UIElement] {
        results.enumerated().map { (i, r) in
            UIElement(
                id: "O\(i + 1)", role: "ocrtext", label: r.text, value: nil,
                x: r.x, y: r.y, width: r.width, height: r.height,
                isEnabled: true, depth: 0
            )
        }
    }
}
