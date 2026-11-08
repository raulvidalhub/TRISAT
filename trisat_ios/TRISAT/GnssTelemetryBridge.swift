import Foundation
import Network
import CoreLocation
import Combine
#if os(macOS)
import AppKit
#endif

/// High-performance UDP Telemetry Bridge service utilizing Apple Network.framework NWListener
class GnssTelemetryBridge: ObservableObject {
    @Published var isListening: Bool = false
    @Published var listenerPort: UInt16 = 9090
    @Published var statusText: String = "SXblue / TRISAT-SDR Bridge Idle (Port 9090)"
    @Published var packetsReceivedCount: Int = 0
    @Published var isSdrEngineRunning: Bool = false
    @Published var isF9pBridgeRunning: Bool = false
    @Published var selectedSdrBand2: String = "GAL_E6"

    private var listener: NWListener?
    private weak var viewModel: GnssViewModel?
    private weak var bluetoothManager: BluetoothManager?
    private var nativeSdrTimer: Timer?
    private var nativeEpoch: Int = 0
    #if os(macOS)
    private var sdrProcess: Process?
    private var f9pProcess: Process?
    #endif

    init(viewModel: GnssViewModel? = nil, bluetoothManager: BluetoothManager? = nil) {
        self.viewModel = viewModel
        self.bluetoothManager = bluetoothManager
        startUdpListener(port: 9090)
    }

    func configure(viewModel: GnssViewModel, bluetoothManager: BluetoothManager) {
        self.viewModel = viewModel
        self.bluetoothManager = bluetoothManager
    }

    // MARK: - Native macOS & In-Process TRISAT-SDR Engine (E1 OSNMA + E6 HAS-UA)

    func startTrisatSdrEngine(band2: String? = nil) {
        let targetBand = band2 ?? selectedSdrBand2
        selectedSdrBand2 = targetBand

        stopTrisatSdrEngine(quiet: true)

        isSdrEngineRunning = true
        statusText = "Simulator Active (Galileo E1/E6 + GPS L1/L5) [UDP :9090]"
        viewModel?.selectedMode = 2
        viewModel?.resetHardwareTelemetry()
        bluetoothManager?.nmeaSentences.removeAll()
        bluetoothManager?.isConnected = true
        bluetoothManager?.connectedPeripheralName = "TRISAT Simulator (UDP / SDR)"

        // 1. Start Native In-Process Swift Galileo HAS-UA + OSNMA Telemetry Generator (1 Hz)
        emitNativeSdrEpoch()
        nativeSdrTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            DispatchQueue.main.async {
                self?.emitNativeSdrEpoch()
            }
        }

        // 2. Also launch trisat_sdr/main.py in background on macOS for Web Dashboard (:8085)
        #if os(macOS)
        let repoRootUrl = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let scriptPath = repoRootUrl.appendingPathComponent("trisat_sdr/main.py").path
        if FileManager.default.fileExists(atPath: scriptPath) {
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            proc.arguments = [scriptPath, "--band2", targetBand, "--web-port", "8085"]
            proc.currentDirectoryURL = repoRootUrl
            proc.standardOutput = FileHandle.nullDevice
            proc.standardError = FileHandle.nullDevice
            try? proc.run()
            self.sdrProcess = proc
        }
        #endif
    }

    func stopTrisatSdrEngine(quiet: Bool = false) {
        nativeSdrTimer?.invalidate()
        nativeSdrTimer = nil

        #if os(macOS)
        if let proc = sdrProcess, proc.isRunning {
            proc.terminate()
        }
        sdrProcess = nil

        let killProc = Process()
        killProc.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        killProc.arguments = ["-f", "trisat_sdr/main.py"]
        try? killProc.run()
        killProc.waitUntilExit()
        #endif

        isSdrEngineRunning = false
        if bluetoothManager?.connectedPeripheralName.contains("Simulator") == true {
            bluetoothManager?.isConnected = false
            bluetoothManager?.connectedPeripheralName = "None"
            bluetoothManager?.nmeaSentences.removeAll()
        }
        viewModel?.hasExternalHardwareFix = false
        viewModel?.liveBridgeSatellites.removeAll()
        viewModel?.messages.removeAll()
        viewModel?.selectedMode = 0
        viewModel?.updateSatellites()

        if !quiet {
            statusText = "Simulator Stopped (UDP Listener Ready :\(listenerPort))"
        }
    }

    private func emitNativeSdrEpoch() {
        guard isSdrEngineRunning else { return }
        nativeEpoch += 1
        packetsReceivedCount += 4

        let isHasBand = (selectedSdrBand2 == "GAL_E6")
        let accMeters = isHasBand ? 0.18 : 0.42
        let modeDesc = isHasBand
            ? "DUAL-SDR E1(OSNMA) + E6(HAS PPP SL1)"
            : "DUAL-SDR E1(OSNMA) + \(selectedSdrBand2) Iono-Free"

        bluetoothManager?.isConnected = true
        bluetoothManager?.connectedPeripheralName = "TRISAT Simulator (UDP / SDR)"

        if let vm = viewModel {
            vm.isSimulatedTelemetry = true
            // Only update coordinate from SDR if the real device CoreLocation hasn't been acquired
            if !vm.hasAcquiredRealLocation {
                let baseLat = 40.416775 + Double((nativeEpoch % 7) - 3) * 0.0000008
                let baseLon = -3.703790 + Double((nativeEpoch % 5) - 2) * 0.0000008
                vm.currentCoordinate = CLLocationCoordinate2D(latitude: baseLat, longitude: baseLon)
                vm.locationText = String(format: "%.6f° N, %.6f° W", abs(baseLat), abs(baseLon))
            }
            if vm.simulatedThreatMode == .nominal && (vm.selectedMode == 1 || vm.selectedMode == 2) {
                vm.hasExternalHardwareFix = true
                vm.numSatellitesInFix = 12
                vm.accuracyText = String(format: "Simulated: ±%.2f m | Alt: 667.0 m [%@]", accMeters, modeDesc)
                vm.fixTypeDesc = "SIMULATED | \(modeDesc)"
                vm.hdopValue = "0.68"
                vm.pdopValue = "1.24"
                vm.vdopValue = "1.04"
                vm.dgpsStationId = isHasBand ? "E6-HAS-MT1 (SL1)" : "OSNMA-\(selectedSdrBand2)"
                vm.dgpsAge = "1.0s (simulated)"
                vm.gstRmsError = String(format: "%.2f m RMS", accMeters)
                vm.gstLatLonErr = "Lat: 0.08m | Lon: 0.07m | Alt: 0.14m"
            }
        }

        // Emit synthetic 30-byte Galileo I/NAV v2.2 & E6 HAS frames with valid CRC-24Q
        let wordTypesCycle = [1, 2, 3, 4, 5, 6, 16, 17, 18, 22, 44]
        let wt = wordTypesCycle[nativeEpoch % wordTypesCycle.count]
        let svid = [2, 7, 11, 19, 24, 31][nativeEpoch % 6]

        var frameBytes = [UInt8](repeating: 0, count: 30)
        frameBytes[0] = UInt8((wt & 0x3F) << 2)
        frameBytes[1] = UInt8(svid & 0xFF)
        frameBytes[2] = UInt8((nativeEpoch >> 8) & 0xFF)
        frameBytes[3] = UInt8(nativeEpoch & 0xFF)

        let isOsnmaFailSim = (viewModel?.simulatedThreatMode == .osnmaFailure)
        let annexATagBytes: [UInt8] = isOsnmaFailSim
            ? [0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            : [0x82, 0x7B, 0xB2, 0x38, 0xC8, 0x83]
        for i in 0..<annexATagBytes.count {
            frameBytes[15 + i] = annexATagBytes[i]
        }
        for i in 4..<15 {
            frameBytes[i] = UInt8((svid * 17 + i * 31 + nativeEpoch * 13) & 0xFF)
        }
        let crc = OsnmaEngine.computeCrc24q(Array(frameBytes[0..<27]))
        frameBytes[27] = UInt8((crc >> 16) & 0xFF)
        frameBytes[28] = UInt8((crc >> 8) & 0xFF)
        frameBytes[29] = UInt8(crc & 0xFF)

        let simBand = (nativeEpoch % 2 == 0) ? "E1-B" : "E5b-I"
        let inavMsg = GalileoINavMessage(
            svid: svid,
            submessageId: wt,
            data: Data(frameBytes),
            status: isOsnmaFailSim ? 1 : 0,
            timestamp: Date(),
            band: simBand,
            isSimulated: true
        )
        if viewModel?.messages.count ?? 0 >= 80 {
            viewModel?.messages.removeFirst()
        }
        viewModel?.messages.append(inavMsg)

        // Dynamic azimuth & elevation drift to show real-time orbital movement
        let azDrift = Double(nativeEpoch % 360)
        let elDrift = 4.0 * sin(Double(nativeEpoch) * 0.1)

        // Galileo Multi-Frequency GSV Sentences (E1=1, E5b=7)
        let galCno1 = 44 + (nativeEpoch % 3)
        let galCno2 = 47 - (nativeEpoch % 2)
        let galCno3 = 39 + ((nativeEpoch + 1) % 3)
        let galCno4 = 48 - (nativeEpoch % 3)
        let gagsv1 = String(format: "$GAGSV,2,1,06,02,%02d,%03d,%d,07,%02d,%03d,%d,11,%02d,%03d,%d,19,%02d,%03d,%d,1*7B",
                            max(10, min(88, Int(48 + elDrift))), Int((95 + azDrift).truncatingRemainder(dividingBy: 360)), galCno1,
                            max(10, min(88, Int(62 - elDrift))), Int((185 + azDrift).truncatingRemainder(dividingBy: 360)), galCno2,
                            max(10, min(88, Int(35 + elDrift))), Int((270 + azDrift).truncatingRemainder(dividingBy: 360)), galCno3,
                            max(10, min(88, Int(72 - elDrift))), Int((45 + azDrift).truncatingRemainder(dividingBy: 360)), galCno4)
        let gagsv2 = String(format: "$GAGSV,2,2,06,02,%02d,%03d,%d,07,%02d,%03d,%d,11,%02d,%03d,%d,19,%02d,%03d,%d,7*72",
                            max(10, min(88, Int(48 + elDrift))), Int((95 + azDrift).truncatingRemainder(dividingBy: 360)), max(25, galCno1 - 3),
                            max(10, min(88, Int(62 - elDrift))), Int((185 + azDrift).truncatingRemainder(dividingBy: 360)), max(25, galCno2 - 2),
                            max(10, min(88, Int(35 + elDrift))), Int((270 + azDrift).truncatingRemainder(dividingBy: 360)), max(25, galCno3 - 2),
                            max(10, min(88, Int(72 - elDrift))), Int((45 + azDrift).truncatingRemainder(dividingBy: 360)), max(25, galCno4 - 3))

        // GPS Multi-Frequency GSV Sentences (L1=1, L2C=6)
        let gpsCno1 = 43 + (nativeEpoch % 2)
        let gpsCno2 = 38 + ((nativeEpoch + 2) % 3)
        let gpgsv1 = String(format: "$GPGSV,2,1,04,03,55,120,%d,14,32,210,%d,17,68,070,45,22,24,300,37,1*7C", gpsCno1, gpsCno2)
        let gpgsv2 = String(format: "$GPGSV,2,2,04,03,55,120,%d,14,32,210,%d,17,68,070,41,22,24,300,33,6*78", max(25, gpsCno1 - 4), max(25, gpsCno2 - 3))

        // Append demo NMEA & $GALINAV / $GALE6HAS sentences to NMEA terminal and parse pipelines
        let hexStr = frameBytes.map { String(format: "%02X", $0) }.joined()
        let ggaLine = String(format: "$GNGGA,1030%02d.00,4025.0065,N,00342.2274,W,4,18,0.68,667.0,M,48.0,M,1.0,E6HAS*4A", nativeEpoch % 60)
        let gstLine = String(format: "$GNGST,1030%02d.00,0.18,0.09,0.07,22.5,0.08,0.07,0.14*5C", nativeEpoch % 60)
        let inavLine = "$GALINAV,\(svid),\(wt),\(hexStr),827BB238C8*3F"
        let hasLine = String(format: "$GALE6HAS,%02d,%d,-11.4,B747%02X01A55BF8C9CBFCF70422081475FD445DF0FF*7E", svid, (nativeEpoch % 15) + 1, svid)

        for sentence in [ggaLine, gstLine, gagsv1, gagsv2, gpgsv1, gpgsv2, inavLine, hasLine] {
            if bluetoothManager?.nmeaSentences.count ?? 0 >= 100 {
                bluetoothManager?.nmeaSentences.removeFirst()
            }
            bluetoothManager?.nmeaSentences.append(sentence)
            if sentence != inavLine {
                bluetoothManager?.onNmeaLineReceived?(sentence)
            }
        }
        viewModel?.updateSatellites()
    }

    func switchSdrSecondaryBand(_ band: String) {
        selectedSdrBand2 = band
        #if os(macOS)
        if let url = URL(string: "http://127.0.0.1:8085/api/set_band?band=\(band)") {
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            URLSession.shared.dataTask(with: req).resume()
        }
        if !isSdrEngineRunning && packetsReceivedCount == 0 {
            startTrisatSdrEngine(band2: band)
        } else {
            statusText = "TRISAT-SDR Simulation (E1 + \(band)) [UDP :9090 | Web :8085]"
        }
        #endif
    }

    func openWebDashboard() {
        #if os(macOS)
        if !isSdrEngineRunning && packetsReceivedCount == 0 {
            startTrisatSdrEngine(band2: selectedSdrBand2)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                if let url = URL(string: "http://127.0.0.1:8085") {
                    NSWorkspace.shared.open(url)
                }
            }
        } else if let url = URL(string: "http://127.0.0.1:8085") {
            NSWorkspace.shared.open(url)
        }
        #endif
    }

    func startF9pBridge() {
        #if os(macOS)
        stopF9pBridge()
        let repoRootUrl = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let scriptPath = repoRootUrl.appendingPathComponent("trisat_hw/zed_f9p/f9p_bridge.py").path
        if FileManager.default.fileExists(atPath: scriptPath) {
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            proc.arguments = [scriptPath]
            proc.currentDirectoryURL = repoRootUrl
            proc.standardOutput = FileHandle.nullDevice
            proc.standardError = FileHandle.nullDevice
            try? proc.run()
            self.f9pProcess = proc
            DispatchQueue.main.async {
                self.isF9pBridgeRunning = true
                self.statusText = "u-blox ZED-F9P USB Bridge Active (/dev/cu.usbmodem* -> UDP :9090)"
            }
        }
        #endif
    }

    func stopF9pBridge() {
        #if os(macOS)
        if let proc = f9pProcess, proc.isRunning {
            proc.terminate()
        }
        f9pProcess = nil

        let killProc = Process()
        killProc.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        killProc.arguments = ["-f", "f9p_bridge.py"]
        try? killProc.run()
        killProc.waitUntilExit()

        DispatchQueue.main.async {
            self.isF9pBridgeRunning = false
            self.statusText = "u-blox ZED-F9P Bridge Stopped"
        }
        #endif
    }

    func startUdpListener(port: UInt16 = 9090) {
        stopUdpListener()
        self.listenerPort = port
        startPingEngine()

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
                        self?.statusText = "Listening on UDP 127.0.0.1:\(port) [SXblue Bridge Active]"
                    case .failed(let err):
                        self?.isListening = false
                        self?.statusText = "UDP Bridge Failed: \(err.localizedDescription)"
                    case .cancelled:
                        self?.isListening = false
                        self?.statusText = "UDP Bridge Cancelled"
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
        stopPingEngine()
        listener?.cancel()
        listener = nil
        DispatchQueue.main.async {
            self.isListening = false
            self.statusText = "UDP Bridge Stopped"
        }
    }

    // MARK: - UDP Local Network Probing & ESP32 Auto-Registration

    private var pingTimer: Timer?

    func startPingEngine() {
        stopPingEngine()
        sendUdpDiscoveryPing()
        pingTimer = Timer.scheduledTimer(withTimeInterval: 2.5, repeats: true) { [weak self] _ in
            self?.sendUdpDiscoveryPing()
        }
    }

    func stopPingEngine() {
        pingTimer?.invalidate()
        pingTimer = nil
    }

    private func sendUdpDiscoveryPing() {
        // Broadcasts a small probe packet to trigger iOS Local Network permissions
        // and register this device's unicast IP with the ESP32 hybrid bridge on 192.168.4.1:9090
        let targets: [String] = ["192.168.4.1", "255.255.255.255"]
        guard let nwPort = NWEndpoint.Port(rawValue: listenerPort) else { return }

        for hostStr in targets {
            let host = NWEndpoint.Host(hostStr)
            let conn = NWConnection(host: host, port: nwPort, using: .udp)
            conn.stateUpdateHandler = { state in
                if case .ready = state {
                    let pingData = "TRISAT_PING\r\n".data(using: .utf8)!
                    conn.send(content: pingData, completion: .contentProcessed({ _ in
                        conn.cancel()
                    }))
                }
            }
            conn.start(queue: .global(qos: .utility))
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
                    self?.processIncomingTelemetryData(data)
                }
            }
            if error == nil {
                self?.receiveNextPacket(connection)
            }
        }
    }

    private func processIncomingTelemetryData(_ data: Data) {
        // If native in-process simulator is running, ignore incoming UDP packets to avoid duplicate stream collisions
        guard !isSdrEngineRunning else { return }

        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let payload = json["data"] as? String {
                parseNmeaOrBinText(payload)
            }
            if let packetType = json["type"] as? String {
                handleTrisatSdrJsonPacket(packetType: packetType, json: json)
            } else if let hexPayload = json["hex"] as? String {
                bluetoothManager?.logDebug("UDP Received $BIN Hex: \(hexPayload.prefix(40))...")
            }
        } else if let rawString = String(data: data, encoding: .ascii) ?? String(data: data, encoding: .utf8) {
            let lines = rawString.components(separatedBy: .newlines)
            for line in lines {
                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    if trimmed.hasPrefix("{"),
                       let lineData = trimmed.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                       let packetType = json["type"] as? String {
                        handleTrisatSdrJsonPacket(packetType: packetType, json: json)
                    } else {
                        parseNmeaOrBinText(trimmed)
                    }
                }
            }
        }
    }

    private func handleTrisatSdrJsonPacket(packetType: String, json: [String: Any]) {
        let isSimulated = json["source"] as? String == "simulated"
        if isSimulated && viewModel?.selectedMode != 2 { return }
        if viewModel?.selectedMode == 0 {
            viewModel?.selectedMode = 2
        }

        if packetType == "inav_frame" || packetType == "gnss_frame" {
            guard let svid = json["svid"] as? Int, (1...36).contains(svid),
                  let submsgId = json["submsgId"] as? Int,
                  let hexStr = json["hex"] as? String,
                  let payloadData = GalileoINavMessage.decodeHexPayload(hexStr) else { return }
            let msg = GalileoINavMessage(
                svid: svid,
                submessageId: submsgId,
                data: payloadData,
                status: 0,
                timestamp: Date(),
                band: packetType == "inav_frame" ? "E1-B" : (json["band"] as? String ?? "Unknown"),
                isSimulated: isSimulated
            )
            if viewModel?.messages.count ?? 0 >= 100 {
                viewModel?.messages.removeFirst()
            }
            viewModel?.messages.append(msg)
        } else if packetType == "location" {
            if let lat = json["lat"] as? Double, let lon = json["lon"] as? Double {
                let alt = json["alt"] as? Double ?? 0.0
                let acc = json["acc"] as? Double ?? 1.0
                let mode = json["mode"] as? String ?? "TRISAT-SDR"
                let source = isSimulated ? "Simulated" : "External / unverified source"
                // Only override location if device has not acquired local CoreLocation
                if let vm = viewModel, !vm.hasAcquiredRealLocation,
                   !isSimulated || !vm.hasExternalHardwareFix {
                    vm.currentCoordinate = CLLocationCoordinate2D(latitude: lat, longitude: lon)
                    let latDir = lat >= 0 ? "N" : "S"
                    let lonDir = lon >= 0 ? "E" : "W"
                    vm.locationText = String(format: "%.6f° %@, %.6f° %@", abs(lat), latDir, abs(lon), lonDir)
                    vm.accuracyText = String(format: "%@ | %@ | Acc: ±%.2f m | Alt: %.1f m", source, mode, acc, alt)
                }
            }
        }
    }

    private func parseNmeaOrBinText(_ text: String) {
        // Only ingest UDP telemetry if the user selected Mode 2 (UDP / Simulator)
        guard let vm = viewModel, vm.selectedMode == 2 else { return }

        if bluetoothManager?.nmeaSentences.count ?? 0 >= 100 {
            bluetoothManager?.nmeaSentences.removeFirst()
        }
        bluetoothManager?.nmeaSentences.append(text)

        vm.processIncomingNmea(text)
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
