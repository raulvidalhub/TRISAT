import Foundation
import CryptoKit

/// OS-NMA Cryptographic Authentication Engine for macOS & iOS (Galileo OSNMA SIS ICD v1.1 & RX Guidelines v1.3)
enum OsnmaAuthStatus: Equatable {
    case unverified
    case notAvailable
}

class OsnmaEngine {

    static let crc24qPoly: UInt32 = 0x1864CFB

    // Official Galileo Annex A Reference Constants (Configuration 2, Sat E02, WN=1248, TOW=345660)
    static let annexAKrootHex = "5BF8C9CBFCF70422081475FD445DF0FF"
    static let annexAK4Hex    = "69C00AA7364237A65EBF006AD8DDBC73"
    static let annexAAlphaHex = "610BDF26D77B"

    /// Computes Galileo 24-bit CRC-24Q (generator polynomial 0x1864CFB) over a byte buffer
    static func computeCrc24q(_ bytes: [UInt8]) -> UInt32 {
        var crc: UInt32 = 0
        for b in bytes {
            crc ^= (UInt32(b) << 16)
            for _ in 0..<8 {
                crc <<= 1
                if (crc & 0x1000000) != 0 {
                    crc ^= crc24qPoly
                }
            }
        }
        return crc & 0xFFFFFF
    }

    /// Performs one step of the Galileo OSNMA TESLA chain one-way function:
    /// K_I = trunc(128, SHA256(K_{I+1} || GST_{SF,I} || alpha))
    static func computeTeslaKeyStep(nextKeyHex: String, wnTarget: UInt32, towTarget: UInt32, alphaHex: String) -> String {
        guard let kNext = hexToData(nextKeyHex),
              let alpha = hexToData(alphaHex) else { return "" }
        let gst32: UInt32 = ((wnTarget & 0xFFF) << 20) | (towTarget & 0xFFFFF)
        var gstBig = gst32.bigEndian
        let gstData = Data(bytes: &gstBig, count: 4)

        var input = Data()
        input.append(kNext)
        input.append(gstData)
        input.append(alpha)

        let digest = SHA256.hash(data: input)
        return digest.prefix(16).map { String(format: "%02X", $0) }.joined()
    }

    /// Runs the official Galileo Annex A TESLA & HMAC-SHA256 verification self-test using Apple CryptoKit
    static func verifyEuspaAnnexATestVector() -> Bool {
        let k3 = computeTeslaKeyStep(nextKeyHex: annexAK4Hex, wnTarget: 1248, towTarget: 345660, alphaHex: annexAAlphaHex)
        let k2 = computeTeslaKeyStep(nextKeyHex: k3, wnTarget: 1248, towTarget: 345630, alphaHex: annexAAlphaHex)
        let k1 = computeTeslaKeyStep(nextKeyHex: k2, wnTarget: 1248, towTarget: 345600, alphaHex: annexAAlphaHex)
        let k0 = computeTeslaKeyStep(nextKeyHex: k1, wnTarget: 1248, towTarget: 345570, alphaHex: annexAAlphaHex)
        guard k0 == annexAKrootHex else { return false }

        // Verify Tag 2 (ADKD=4, CTR=3, PRN_D=2, PRN_A=2) == 0x7BB238C883
        guard let keyData = hexToData(annexAK4Hex),
              let msgData = hexToData("02024E05463C03BFFFFFFFC00000449238227897FDEFF93040") else { return false }
        let symKey = SymmetricKey(data: keyData)
        let mac = HMAC<SHA256>.authenticationCode(for: msgData, using: symKey)
        let tagHex = Data(mac).prefix(5).map { String(format: "%02X", $0) }.joined()
        return tagHex == "7BB238C883"
    }

    /// Reports reception. The received pages have not been authenticated.
    func receptionStatus(inavMessages: [GalileoINavMessage]) -> OsnmaAuthStatus {
        return inavMessages.contains { !$0.data.isEmpty } ? .unverified : .notAvailable
    }

    private static func hexToData(_ hex: String) -> Data? {
        let clean = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        guard clean.count % 2 == 0 else { return nil }
        var data = Data(capacity: clean.count / 2)
        var idx = clean.startIndex
        while idx < clean.endIndex {
            let next = clean.index(idx, offsetBy: 2)
            guard let b = UInt8(clean[idx..<next], radix: 16) else { return nil }
            data.append(b)
            idx = next
        }
        return data
    }
}
