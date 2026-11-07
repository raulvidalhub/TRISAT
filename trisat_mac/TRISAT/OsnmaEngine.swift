import Foundation

/// OS-NMA Cryptographic Authentication Engine for iOS
enum OsnmaAuthStatus {
    case unverified
    case notAvailable
}

class OsnmaEngine {

    /// Reports reception. The received pages have not been authenticated.
    func receptionStatus(inavMessages: [GalileoINavMessage]) -> OsnmaAuthStatus {
        return inavMessages.contains { !$0.data.isEmpty } ? .unverified : .notAvailable
    }
}
