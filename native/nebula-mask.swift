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

do {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard let source = CGImageSourceCreateWithData(data as CFData, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NSError(domain: "NebulaMask", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "Cannot decode mask input"])
    }
    let handler = VNImageRequestHandler(cgImage: image)
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
    let ci = CIImage(cvPixelBuffer: buffer)
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
