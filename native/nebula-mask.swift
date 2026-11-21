// Local, stateless masks. One PNG on stdin, one grayscale PNG on stdout.
// A fresh request per frame makes random seeking agree with sequential export.
import Foundation
import Vision
import CoreImage
import ImageIO

func emptyMask(width: Int, height: Int) throws -> CVPixelBuffer {
    var buffer: CVPixelBuffer?
    CVPixelBufferCreate(nil, width, height, kCVPixelFormatType_OneComponent8, nil, &buffer)
    guard let buffer else { throw NSError(domain: "NebulaMask", code: 3) }
    CVPixelBufferLockBaseAddress(buffer, [])
    memset(CVPixelBufferGetBaseAddress(buffer), 0, CVPixelBufferGetDataSize(buffer))
    CVPixelBufferUnlockBaseAddress(buffer, [])
    return buffer
}

func foreground(_ image: CGImage) throws -> CIImage {
    let handler = VNImageRequestHandler(cgImage: image)
    let request = VNGenerateForegroundInstanceMaskRequest()
    try handler.perform([request])
    let buffer: CVPixelBuffer
    if let result = request.results?.first, !result.allInstances.isEmpty {
        buffer = try result.generateScaledMaskForImage(forInstances: result.allInstances, from: handler)
    } else {
        buffer = try emptyMask(width: image.width, height: image.height)
    }
    let ci = CIImage(cvPixelBuffer: buffer)
    return ci.transformed(by: CGAffineTransform(scaleX: CGFloat(image.width) / ci.extent.width,
                                                y: CGFloat(image.height) / ci.extent.height))
}

func crowdMask(_ image: CGImage) throws -> CIImage {
    let width = CGFloat(image.width), height = CGFloat(image.height)
    let bounds = CGRect(x: 0, y: 0, width: width, height: height)
    var result = try foreground(image)
    // Prominence changes as people cross. Give smaller figures their own
    // detection context instead of relying on one full-frame selection.
    let request = VNDetectHumanRectanglesRequest()
    request.upperBodyOnly = false
    try VNImageRequestHandler(cgImage: image).perform([request])
    let people = (request.results ?? []).filter { $0.confidence >= 0.35 }
        .sorted { $0.confidence > $1.confidence }.prefix(16)
    for person in people {
        let box = person.boundingBox
        let body = CGRect(x: box.minX * width, y: (1 - box.maxY) * height,
                          width: box.width * width, height: box.height * height)
        let cropRect = body.insetBy(dx: -body.width * 0.12, dy: -body.height * 0.04)
            .intersection(bounds).integral
        guard let crop = image.cropping(to: cropRect) else { continue }
        let local = try foreground(crop)
        // Fade only the artificial crop boundary; retain real canvas edges.
        let w = crop.width, h = crop.height
        let feather = max(1, min(8, Double(min(w, h)) * 0.08))
        var pixels = [UInt8](repeating: 255, count: w * h)
        for y in 0..<h {
            for x in 0..<w {
                var distance = feather
                if cropRect.minX > 0 { distance = min(distance, Double(x)) }
                if cropRect.maxX < width { distance = min(distance, Double(w - 1 - x)) }
                if cropRect.minY > 0 { distance = min(distance, Double(y)) }
                if cropRect.maxY < height { distance = min(distance, Double(h - 1 - y)) }
                let t = max(0, min(1, distance / feather))
                pixels[y * w + x] = UInt8(255 * t * t * (3 - 2 * t))
            }
        }
        guard let provider = CGDataProvider(data: Data(pixels) as CFData),
              let window = CGImage(width: w, height: h, bitsPerComponent: 8, bitsPerPixel: 8,
                bytesPerRow: w, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: [],
                provider: provider, decode: nil, shouldInterpolate: false, intent: .defaultIntent) else {
            throw NSError(domain: "NebulaMask", code: 6)
        }
        let softened = local.applyingFilter("CIMultiplyCompositing",
            parameters: [kCIInputBackgroundImageKey: CIImage(cgImage: window)])
        let shifted = softened.transformed(by: CGAffineTransform(
            translationX: cropRect.minX, y: height - cropRect.maxY))
        result = shifted.applyingFilter("CIMaximumCompositing",
            parameters: [kCIInputBackgroundImageKey: result])
    }
    return result.cropped(to: bounds)
}

do {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard let source = CGImageSourceCreateWithData(data as CFData, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NSError(domain: "NebulaMask", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "Cannot decode mask input"])
    }
    let handler = VNImageRequestHandler(cgImage: image)
    let ci: CIImage
    if CommandLine.arguments.dropFirst().first == "crowd" {
        ci = try crowdMask(image)
    } else {
        let buffer: CVPixelBuffer
        if CommandLine.arguments.dropFirst().first == "people" {
            let request = VNGeneratePersonSegmentationRequest()
            request.qualityLevel = .accurate
            request.outputPixelFormat = kCVPixelFormatType_OneComponent8
            try handler.perform([request])
            if let result = request.results?.first {
                buffer = result.pixelBuffer
            } else {
                buffer = try emptyMask(width: image.width, height: image.height)
            }
        } else {
            let request = VNGenerateForegroundInstanceMaskRequest()
            try handler.perform([request])
            if let result = request.results?.first, !result.allInstances.isEmpty {
                buffer = try result.generateScaledMaskForImage(forInstances: result.allInstances, from: handler)
            } else {
                buffer = try emptyMask(width: image.width, height: image.height)
            }
        }
        ci = CIImage(cvPixelBuffer: buffer)
    }
    let context = CIContext(options: [.workingColorSpace: NSNull()])
    guard let cg = context.createCGImage(ci, from: ci.extent, format: .L8,
                                        colorSpace: CGColorSpaceCreateDeviceGray()),
          let output = CFDataCreateMutable(nil, 0),
          let destination = CGImageDestinationCreateWithData(output, "public.png" as CFString, 1, nil) else {
        throw NSError(domain: "NebulaMask", code: 4)
    }
    CGImageDestinationAddImage(destination, cg, nil)
    guard CGImageDestinationFinalize(destination) else { throw NSError(domain: "NebulaMask", code: 5) }
    FileHandle.standardOutput.write(output as Data)
} catch {
    FileHandle.standardError.write(Data(("Local subject mask failed: \(error)\n").utf8))
    exit(1)
}
