import Foundation

/// Decodes the F9P bridge's binary UDP packets and Galileo I/NAV sentences.
enum F9pTelemetry {
    static let rawPrefix = Data("RAW:".utf8)
    struct Page: Equatable {
        let svid: Int
        let wordType: Int
        let data: Data
        let band: String
    }

    static func decodeDatagram(_ data: Data) -> Page? {
        guard data.count == 52 else { return nil }
        let bytes = Array(data)
        guard bytes.prefix(10).elementsEqual([0x52, 0x41, 0x57, 0x3A, 0xB5, 0x62, 2, 0x13, 40, 0])
        else { return nil }

        var a: UInt8 = 0
        var b: UInt8 = 0
        for byte in bytes[6..<50] {
            a = a &+ byte
            b = b &+ a
        }
        guard bytes[50] == a, bytes[51] == b, bytes[10] == 2,
              (1...36).contains(bytes[11]), bytes[14] == 8, bytes[16] == 2
        else { return nil }

        let band: String
        switch bytes[12] {
        case 1: band = "E1-B"
        case 5: band = "E5b-I"
        default: return nil
        }

        var pages: [UInt8] = []
        for word in stride(from: 18, to: 50, by: 4) {
            let first = word + (word == 30 || word == 46 ? 1 : 0)
            pages.append(contentsOf: bytes[first..<(word + 4)].reversed())
        }
        let wordType = Int(pages[0] & 0x3F)
        guard validPage(pages) else { return nil }
        return Page(svid: Int(bytes[11]), wordType: wordType, data: Data(pages), band: band)
    }

    static func decodeSentence(_ line: String) -> Page? {
        let fields = line.split(separator: "*", maxSplits: 1, omittingEmptySubsequences: false)
        guard let body = fields.first else { return nil }
        let parts = body.split(separator: ",", omittingEmptySubsequences: false)
        guard (4...5).contains(parts.count), parts[0] == "$GALINAV" || parts[0] == "$RAWNAV",
              let svid = Int(parts[1]), (1...36).contains(svid),
              let wt = Int(parts[2]), (0...63).contains(wt),
              let bytes = hexBytes(parts[3])
        else { return nil }

        if parts.count == 5, parts[4].count != 10 || hexBytes(parts[4]) == nil {
            // The optional legacy fifth field is a 40-bit OSNMA hex string.
            // The F9P/ESP32 format instead puts the signal name here.
            let band = String(parts[4])
            guard parts[0] == "$GALINAV", band == "E1-B" || band == "E5b-I",
                  validChecksum(line), validPage(bytes), wt == Int(bytes[0] & 0x3F)
            else { return nil }
            return Page(svid: svid, wordType: wt, data: Data(bytes), band: band)
        }

        return Page(svid: svid, wordType: wt, data: Data(bytes), band: "E1-B")
    }

    /// NMEA fix qualities for measured position solutions. Zero and estimated fixes are excluded.
    static func measuredFix(_ quality: String) -> Bool {
        return ["1", "2", "3", "4", "5"].contains(quality)
    }

    static func ggaFields(_ sentence: String) -> [String]? {
        guard validChecksum(sentence) else { return nil }
        let fields = sentence.components(separatedBy: ",")
        guard fields.count >= 10, fields[0] == "$GPGGA" || fields[0] == "$GNGGA" else { return nil }
        return fields
    }

    static func withChecksum(_ body: String) -> String {
        body + String(format: "*%02X", body.utf8.dropFirst().reduce(0, ^))
    }

    static func validChecksum(_ sentence: String) -> Bool {
        let parts = sentence.split(separator: "*", omittingEmptySubsequences: false)
        guard parts.count == 2, parts[0].hasPrefix("$"), parts[1].count == 2,
              let checksum = UInt8(parts[1], radix: 16)
        else { return false }
        return parts[0].utf8.dropFirst().reduce(0, ^) == checksum
    }

    private static func hexBytes(_ hex: Substring) -> [UInt8]? {
        guard !hex.isEmpty, hex.utf8.count.isMultiple(of: 2),
              hex.utf8.allSatisfy({ (48...57).contains($0) || (65...70).contains($0) || (97...102).contains($0) })
        else { return nil }
        var bytes: [UInt8] = []
        var index = hex.startIndex
        while index != hex.endIndex {
            guard let end = hex.index(index, offsetBy: 2, limitedBy: hex.endIndex),
                  let byte = UInt8(hex[index..<end], radix: 16)
            else { return nil }
            bytes.append(byte)
            index = end
        }
        return bytes
    }

    private static func validPage(_ bytes: [UInt8]) -> Bool {
        guard bytes.count == 30, bytes[0] >> 6 == 0, bytes[15] >> 6 == 2 else { return false }
        func bit(_ index: Int) -> UInt32 {
            UInt32((bytes[index / 8] >> (7 - index % 8)) & 1)
        }

        // Vertical Galileo CRC-24Q covers 114 even bits and 82 odd bits.
        var crc: UInt32 = 0
        for range in [0..<114, 120..<202] {
            for index in range {
                let feedback = (crc >> 23) ^ bit(index)
                crc = (crc << 1) & 0xFFFFFF
                if feedback != 0 { crc ^= 0x864CFB }
            }
        }
        let received = (202..<226).reduce(UInt32(0)) { ($0 << 1) | bit($1) }
        return crc == received
    }
}
