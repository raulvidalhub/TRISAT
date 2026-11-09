import Foundation
import Network
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
        if data.starts(with: F9pTelemetry.rawPrefix) {
            if let page = F9pTelemetry.decodeDatagram(data) {
                appendInav(page)
            }
            return
        }

        guard let text = String(data: data, encoding: .ascii) else { return }
        for line in text.components(separatedBy: .newlines) {
            let sentence = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard sentence.hasPrefix("$") else { continue }
            if let page = F9pTelemetry.decodeSentence(sentence) {
                appendInav(page)
            }
            if bluetoothManager?.nmeaSentences.count ?? 0 >= 100 {
                bluetoothManager?.nmeaSentences.removeFirst()
            }
            bluetoothManager?.nmeaSentences.append(sentence)
            bluetoothManager?.onNmeaLineReceived?(sentence)
            bluetoothManager?.isConnected = true
            bluetoothManager?.connectedPeripheralName = "External GNSS (UDP :9090)"
        }
    }

    private func appendInav(_ page: F9pTelemetry.Page) {
        viewModel?.handleInavMessage(GalileoINavMessage(
            svid: page.svid, submessageId: page.wordType, data: page.data,
            status: 0, timestamp: Date(), band: page.band
        ))
    }
}
