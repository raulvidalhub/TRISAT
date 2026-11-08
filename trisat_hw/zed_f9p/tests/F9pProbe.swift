import Foundation

@main
enum F9pProbe {
    static func main() {
        while let line = readLine() {
            if line.hasPrefix("gga ") {
                let fields = F9pTelemetry.ggaFields(String(line.dropFirst(4)))
                print(fields.map { F9pTelemetry.measuredFix($0[6]) ? "measured" : "no fix" } ?? "-")
                continue
            }

            let page: F9pTelemetry.Page?
            if line.hasPrefix("raw ") {
                let hex = Array(line.dropFirst(4))
                let data = Data(stride(from: 0, to: hex.count, by: 2).map {
                    UInt8(String(hex[$0...$0 + 1]), radix: 16)!
                })
                page = F9pTelemetry.decodeDatagram(data)
            } else {
                page = F9pTelemetry.decodeSentence(line)
            }

            if let page {
                let hex = page.data.map { String(format: "%02X", $0) }.joined()
                print("\(page.svid)|\(page.wordType)|\(hex)|\(page.band)")
            } else {
                print("-")
            }
        }
    }
}
