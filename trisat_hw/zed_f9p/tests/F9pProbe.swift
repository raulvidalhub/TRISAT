import Foundation

@main
enum F9pProbe {
    static func main() {
        var framer = F9pTelemetry.SerialFramer()
        while let line = readLine() {
            if line.hasPrefix("serial ") {
                let events = framer.feed(bytes(String(line.dropFirst(7))))
                let rendered = events.map { event in
                    switch event {
                    case .line(let sentence): return sentence
                    case .page(let page): return render(page)
                    }
                }
                print(rendered.isEmpty ? "-" : rendered.joined(separator: ";"))
                continue
            }

            if line.hasPrefix("gga ") {
                let fields = F9pTelemetry.ggaFields(String(line.dropFirst(4)))
                print(fields.map { F9pTelemetry.measuredFix($0[6]) ? "measured" : "no fix" } ?? "-")
                continue
            }

            let page: F9pTelemetry.Page?
            if line.hasPrefix("raw ") {
                page = F9pTelemetry.decodeDatagram(Data(bytes(String(line.dropFirst(4)))))
            } else {
                page = F9pTelemetry.decodeSentence(line)
            }

            print(page.map(render) ?? "-")
        }
    }

    private static func bytes(_ hex: String) -> [UInt8] {
        let chars = Array(hex)
        return stride(from: 0, to: chars.count, by: 2).map {
            UInt8(String(chars[$0...$0 + 1]), radix: 16)!
        }
    }

    private static func render(_ page: F9pTelemetry.Page) -> String {
        let hex = page.data.map { String(format: "%02X", $0) }.joined()
        return "\(page.svid)|\(page.wordType)|\(hex)|\(page.band)"
    }
}
