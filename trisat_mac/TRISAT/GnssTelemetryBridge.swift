import Foundation
import Network
import CoreLocation
import Combine

/// High-performance UDP Telemetry Bridge service utilizing Apple Network.framework NWListener
class GnssTelemetryBridge: ObservableObject {
    @Published var isListening: Bool = false
    @Published var listenerPort: UInt16 = 9090
    @Published var statusText: String = "Disconnected"
    @Published var packetsReceivedCount: Int = 0

    private var listener: NWListener?
    private weak var viewModel: GnssViewModel?
    private weak var bluetoothManager: BluetoothManager?

    init(viewModel: GnssViewModel? = nil, bluetoothManager: BluetoothManager? = nil) {
        self.viewModel = viewModel
        self.bluetoothManager = bluetoothManager
        startUdpListener(port: 9090)
    }

    func configure(viewModel: GnssViewModel, bluetoothManager: BluetoothManager) {
        self.viewModel = viewModel
        self.bluetoothManager = bluetoothManager
    }

    func startUdpListener(port: UInt16 = 9090) {
        stopUdpListener()
        self.listenerPort = port

        do {
            let params = NWParameters.udp
            params.allowLocalEndpointReuse = true

            guard let nwPort = NWEndpoint.Port(rawValue: port) else { return }
            let newListener = try NWListener(using: params, on: nwPort)

            newListener.stateUpdateHandler = { [weak self] state in
                DispatchQueue.main.async {
                    switch state {
                    case .ready:
                        self?.isListening = true
                        self?.statusText = "Listening on :\(port)"
                    case .failed(let err):
                        self?.isListening = false
                        self?.statusText = "Disconnected (\(err.localizedDescription))"
                    case .cancelled:
                        self?.isListening = false
                        self?.statusText = "Disconnected"
                    default:
                        break
                    }
                }
            }

            newListener.newConnectionHandler = { [weak self] connection in
                self?.handleIncomingConnection(connection)
            }

            newListener.start(queue: .global(qos: .userInitiated))
            self.listener = newListener

        } catch {
            DispatchQueue.main.async {
                self.statusText = "Failed to start UDP Listener: \(error.localizedDescription)"
            }
        }
    }

    func stopUdpListener() {
        listener?.cancel()
        listener = nil
        DispatchQueue.main.async {
            self.isListening = false
            self.statusText = "Disconnected"
        }
    }

    private func handleIncomingConnection(_ connection: NWConnection) {
        connection.start(queue: .global(qos: .userInitiated))
        receiveNextPacket(connection)
    }

    private func receiveNextPacket(_ connection: NWConnection) {
        connection.receiveMessage { [weak self] content, context, isComplete, error in
            if let data = content, !data.isEmpty {
                DispatchQueue.main.async {
                    self?.packetsReceivedCount += 1
                    self?.statusText = "Streaming Telemetry"
                    self?.processIncomingTelemetryData(data)
                }
            }
            if error == nil {
                self?.receiveNextPacket(connection)
            }
        }
    }

    private func processIncomingTelemetryData(_ data: Data) {
        guard let datagramStr = String(data: data, encoding: .ascii) ?? String(data: data, encoding: .utf8) else { return }

        let lines = datagramStr.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }

            if trimmed.hasPrefix("RAW:") {
                let hexContent = String(trimmed.dropFirst(4))
                parseBinaryDatagram(hexContent)
            } else if trimmed.hasPrefix("$") {
                parseNmeaSentence(trimmed)
            }
        }
    }

    private func parseNmeaSentence(_ text: String) {
        if bluetoothManager?.nmeaSentences.count ?? 0 >= 100 {
            bluetoothManager?.nmeaSentences.removeFirst()
        }
        bluetoothManager?.nmeaSentences.append(text)
        bluetoothManager?.onNmeaLineReceived?(text)
        bluetoothManager?.isConnected = true
        bluetoothManager?.connectedPeripheralName = "SXblue II GPS (USB Daemon :9090)"

        if text.contains("$GPGGA") || text.contains("$GNGGA") {
            let parts = text.components(separatedBy: ",")
            if parts.count >= 10 {
                if let lat = parseNmeaCoord(parts[2], dir: parts[3]),
                   let lon = parseNmeaCoord(parts[4], dir: parts[5]) {
                    let fixQuality = parts[6]
                    let numSats = parts[7]
                    let hdop = parts[8]
                    let alt = parts[9]

                    let fixDesc: String = {
                        switch fixQuality {
                        case "1": return "GPS Fix"
                        case "2": return "DGPS Fix (SXblue)"
                        case "4": return "RTK Fixed"
                        case "5": return "RTK Float"
                        default: return "Fix Quality \(fixQuality)"
                        }
                    }()

                    viewModel?.currentCoordinate = CLLocationCoordinate2D(latitude: lat, longitude: lon)
                    let latDir = lat >= 0 ? "N" : "S"
                    let lonDir = lon >= 0 ? "E" : "W"
                    viewModel?.locationText = String(format: "%.6f° %@, %.6f° %@", abs(lat), latDir, abs(lon), lonDir)
                    viewModel?.accuracyText = "Fix: \(fixDesc) | Sats: \(numSats) | HDOP: \(hdop) | Alt: \(alt)m"
                }
            }
        }

        if text.contains("$GAGSV") || text.contains("$GPGSV") {
            parseGsvSentence(text)
        }

        if text.contains("$GALINAV") || text.contains("$RAWNAV") {
            parseInavSentence(text)
        }
    }

    private func parseGsvSentence(_ text: String) {
        let parts = text.components(separatedBy: ",")
        guard parts.count >= 8 else { return }

        let isGalileo = text.contains("$GAGSV")
        let constKind: GnssConstellation = isGalileo ? .galileo : .gps

        var parsedSats: [SatelliteInfo] = []
        var idx = 4
        while idx + 3 < parts.count {
            let svidStr = parts[idx]
            let elevStr = parts[idx+1]
            let azimStr = parts[idx+2]
            let cnoStr = parts[idx+3].components(separatedBy: "*")[0]

            if let svid = Int(svidStr),
               let elev = Double(elevStr),
               let azim = Double(azimStr),
               let cno = Int(cnoStr) {
                let sat = SatelliteInfo(
                    id: "\(constKind.rawValue)_UDP_\(svid)",
                    svid: svid,
                    elevation: elev,
                    azimuth: azim,
                    cno: cno,
                    isGalileo: isGalileo,
                    constellation: constKind,
                    usedInFix: true,
                    hasInav: isGalileo
                )
                parsedSats.append(sat)
            }
            idx += 4
        }

        if !parsedSats.isEmpty {
            guard let vm = viewModel else { return }
            vm.externalSatellites.removeAll(where: { $0.constellation == constKind })
            vm.externalSatellites.append(contentsOf: parsedSats)
            vm.updateSatellites()
        }
    }

    private func parseInavSentence(_ text: String) {
        let parts = text.components(separatedBy: ",")
        guard parts.count >= 4,
              let svid = Int(parts[1]), (1...36).contains(svid),
              let submsgId = Int(parts[2]),
              let payload = GalileoINavMessage.decodeHexPayload(parts[3].components(separatedBy: "*")[0])
        else { return }

        let msg = GalileoINavMessage(
            svid: svid,
            submessageId: submsgId,
            data: payload,
            status: 0,
            timestamp: Date()
        )

        if viewModel?.messages.count ?? 0 >= 100 {
            viewModel?.messages.removeFirst()
        }
        viewModel?.messages.append(msg)
    }

    private func parseBinaryDatagram(_ hexString: String) {
        bluetoothManager?.logDebug("RAW $BIN Datagram: \(hexString.prefix(32))...")
    }

    private func parseNmeaCoord(_ rawVal: String, dir: String) -> Double? {
        guard let num = Double(rawVal), num > 0 else { return nil }
        let deg = floor(num / 100.0)
        let min = num - (deg * 100.0)
        var decimal = deg + (min / 60.0)
        if dir == "S" || dir == "W" { decimal = -decimal }
        return decimal
    }
}
