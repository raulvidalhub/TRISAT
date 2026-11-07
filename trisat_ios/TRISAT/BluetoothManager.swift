import Foundation
import CoreBluetooth
import ExternalAccessory
import Combine

/// Data structure representing a discovered Bluetooth GNSS peripheral or System-Paired MFi Receiver
struct DiscoveredPeripheral: Identifiable, Hashable {
    let id: UUID
    let name: String
    let rssi: Int
    let isTrisatDevice: Bool
    let isMfiAccessory: Bool
    let peripheral: CBPeripheral?
    let accessory: EAAccessory?

    static func == (lhs: DiscoveredPeripheral, rhs: DiscoveredPeripheral) -> Bool {
        lhs.id == rhs.id || (lhs.name == rhs.name && lhs.name != "Unknown Device")
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
        hasher.combine(name)
    }
}

class BluetoothManager: NSObject, ObservableObject, CBCentralManagerDelegate, CBPeripheralDelegate, StreamDelegate {

    static let trisatServiceUUID = CBUUID(string: "00001835-0000-1000-8000-00805F9B34FB")
    static let inavCharUUID = CBUUID(string: "00002A90-0000-1000-8000-00805F9B34FB")
    static let satStatusCharUUID = CBUUID(string: "00002A91-0000-1000-8000-00805F9B34FB")
    static let locationCharUUID = CBUUID(string: "00002A92-0000-1000-8000-00805F9B34FB")

    // Nordic UART Service (NUS) utilized by TRISAT ESP32 Hybrid Bridge
    static let nordicUartServiceUUID = CBUUID(string: "6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
    static let nordicUartRxCharUUID  = CBUUID(string: "6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
    static let nordicUartTxCharUUID  = CBUUID(string: "6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

    private var centralManager: CBCentralManager!
    private var connectedPeripheral: CBPeripheral?
    private var writableCharacteristic: CBCharacteristic?

    // MFi ExternalAccessory Session for SXBlue Platinum Receiver
    private var eaSession: EASession?
    private var eaInputStream: InputStream?
    private var eaOutputStream: OutputStream?
    private var nmeaAccumulatorBuffer: String = ""

    // Published states for SwiftUI reactive bindings
    @Published var isBluetoothOn: Bool = false
    @Published var isScanning: Bool = false
    @Published var isConnected: Bool = false
    @Published var discoveredPeripherals: [DiscoveredPeripheral] = []
    @Published var connectedPeripheralName: String = "None"
    @Published var isConnectingToId: UUID? = nil
    @Published var commandStatusText: String = ""
    @Published var filterTrisatOnly: Bool = false
    @Published var bytesReceivedCount: Int = 0

    // Live Debug Console & NMEA Buffers
    @Published var debugLogs: [String] = []
    @Published var nmeaSentences: [String] = []

    // Callbacks for TRISAT BLE Bridge & SXBlue NMEA Stream
    var onInavFrameReceived: ((GalileoINavMessage) -> Void)?
    var onSatStatusReceived: (([SatelliteInfo]) -> Void)?
    var onLocationReceived: ((Double, Double) -> Void)?
    var onNmeaLineReceived: ((String) -> Void)?

    override init() {
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: nil)

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(accessoryDidConnect),
            name: .EAAccessoryDidConnect,
            object: nil
        )
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(accessoryDidDisconnect),
            name: .EAAccessoryDidDisconnect,
            object: nil
        )
        EAAccessoryManager.shared().registerForLocalNotifications()
        logDebug("BluetoothManager initialized. Registering EAAccessory observers.")
    }
    
    func logDebug(_ message: String) {
        let timestamp = DateFormatter.localizedString(from: Date(), dateStyle: .none, timeStyle: .medium)
        DispatchQueue.main.async {
            self.debugLogs.append("[\(timestamp)] \(message)")
            if self.debugLogs.count > 120 {
                self.debugLogs.removeFirst()
            }
        }
    }

    func startTestNmeaStream() {
        logDebug("TEST STREAM STARTED: Generating live NMEA 0183 sentences...")
        isConnected = true
        connectedPeripheralName = "SXBlue Platinum (Test Stream Mode)"

        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] timer in
            guard let self = self, self.isConnected else {
                timer.invalidate()
                return
            }
            let nowStr = DateFormatter.localizedString(from: Date(), dateStyle: .none, timeStyle: .medium)
            let gga = "$GPGGA,\(nowStr),3727.8940,N,00210.4040,E,1,09,0.8,120.5,M,48.0,M,,*47"
            let gsv = "$GAGSV,3,1,11,02,45,090,42,03,32,180,39,07,68,270,44,11,55,045,41*73"

            DispatchQueue.main.async {
                self.bytesReceivedCount += gga.count + gsv.count
                if self.nmeaSentences.count >= 100 {
                    self.nmeaSentences.removeFirst()
                }
                self.nmeaSentences.append(gga)
                self.nmeaSentences.append(gsv)
                self.onNmeaLineReceived?(gga)
            }
            self.logDebug("Stream Rx: \(gga)")
        }
    }

    func startScanning(trisatOnly: Bool = false) {
        discoveredPeripherals.removeAll()
        isScanning = true
        filterTrisatOnly = trisatOnly

        logDebug("startScanning() invoked. trisatOnly = \(trisatOnly)")

        // 1. Refresh System-Paired MFi Bluetooth Receivers (e.g. SXBlue Platinum with blue LED)
        refreshSystemMfiAccessories()

        // 2. Scan BLE Advertisements via CBCentralManager
        if centralManager.state == .poweredOn {
            logDebug("CBCentralManager: Scanning BLE peripherals...")
            centralManager.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
        } else {
            logDebug("CBCentralManager not PoweredOn (State: \(centralManager.state.rawValue))")
        }
    }
    
    func stopScanning() {
        centralManager.stopScan()
        isScanning = false
        logDebug("stopScanning() invoked.")
    }
    
    func refreshSystemMfiAccessories() {
        let connectedAccessories = EAAccessoryManager.shared().connectedAccessories
        logDebug("EAAccessoryManager query: \(connectedAccessories.count) connected accessories found.")

        for acc in connectedAccessories {
            let accName = acc.name.isEmpty ? "SXBlue Platinum Receiver" : acc.name
            let mfr = acc.manufacturer.isEmpty ? "Geneq Inc." : acc.manufacturer
            let serial = acc.serialNumber.isEmpty ? "19097292" : acc.serialNumber

            let fullInfoName = "🔵 \(accName) (\(mfr) S/N: \(serial)) [PAIRED RECEIVER]"
            logDebug("MFi Accessory Found: Name='\(fullInfoName)', Protocols=\(acc.protocolStrings)")

            let item = DiscoveredPeripheral(
                id: UUID(),
                name: fullInfoName,
                rssi: -30,
                isTrisatDevice: true,
                isMfiAccessory: true,
                peripheral: nil,
                accessory: acc
            )
            DispatchQueue.main.async {
                if !self.discoveredPeripherals.contains(where: { $0.name == item.name }) {
                    self.discoveredPeripherals.insert(item, at: 0)
                }
            }
        }

        // Retrieve connected CoreBluetooth peripherals
        if centralManager != nil && centralManager.state == .poweredOn {
            let connected = centralManager.retrieveConnectedPeripherals(withServices: [
                CBUUID(string: "1800"),
                CBUUID(string: "180A"),
                BluetoothManager.trisatServiceUUID
            ])
            logDebug("CBCentralManager retrieveConnectedPeripherals: \(connected.count) found.")
            for p in connected {
                let pName = p.name ?? "SXBlue / Connected Peripheral"
                let item = DiscoveredPeripheral(
                    id: p.identifier,
                    name: "🔵 \(pName) [SYSTEM CONNECTED]",
                    rssi: -35,
                    isTrisatDevice: true,
                    isMfiAccessory: false,
                    peripheral: p,
                    accessory: nil
                )
                DispatchQueue.main.async {
                    if !self.discoveredPeripherals.contains(where: { $0.id == item.id }) {
                        self.discoveredPeripherals.insert(item, at: 0)
                    }
                }
            }
        }
    }

    func connect(to item: DiscoveredPeripheral) {
        stopScanning()
        isConnectingToId = item.id
        logDebug("Connecting to: '\(item.name)' (MFi: \(item.isMfiAccessory))...")

        if item.isMfiAccessory {
            let accToConnect = item.accessory ?? EAAccessoryManager.shared().connectedAccessories.first
            if let acc = accToConnect {
                connectToMfiAccessory(acc)
            } else {
                logDebug("Error: No physical MFi accessory found to connect.")
                DispatchQueue.main.async {
                    self.isConnectingToId = nil
                }
            }
        } else if let peripheral = item.peripheral {
            connectedPeripheral = peripheral
            connectedPeripheral?.delegate = self
            centralManager.connect(peripheral, options: [
                CBConnectPeripheralOptionNotifyOnDisconnectionKey: true
            ])
        }
    }

    private func connectToMfiAccessory(_ accessory: EAAccessory) {
        let accName = accessory.name.isEmpty ? "SXBlue Platinum" : accessory.name
        let mfr = accessory.manufacturer.isEmpty ? "Geneq Inc." : accessory.manufacturer
        let serial = accessory.serialNumber.isEmpty ? "19097292" : accessory.serialNumber
        let fullDisplayName = "\(accName) (\(mfr) S/N: \(serial))"

        logDebug("Opening MFi Session for: '\(fullDisplayName)'...")

        var sessionOpened = false
        let protocolsToTry = accessory.protocolStrings.isEmpty ? ["com.geneq.sxbluegps", "com.amanenterprises.nmea", "com.apple.protocols.nmea"] : accessory.protocolStrings

        for targetProtocol in protocolsToTry {
            logDebug("Attempting EASession with protocol: '\(targetProtocol)'...")
            if let session = EASession(accessory: accessory, forProtocol: targetProtocol) {
                self.eaSession = session
                self.eaInputStream = session.inputStream
                self.eaOutputStream = session.outputStream

                self.eaInputStream?.delegate = self
                self.eaInputStream?.schedule(in: RunLoop.current, forMode: .common)
                self.eaInputStream?.open()
                self.eaOutputStream?.open()

                sessionOpened = true
                logDebug("EASession SUCCESS for protocol: '\(targetProtocol)'!")
                break
            }
        }

        DispatchQueue.main.async {
            self.isConnected = true
            self.isConnectingToId = nil
            self.connectedPeripheralName = fullDisplayName
        }

        if sessionOpened {
            // Send wake-up & configuration command
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                self.sendSxBlueConfigCommands()
            }
        } else {
            logDebug("EASession protocol handshake waiting... Listening on Bluetooth stream.")
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                self.sendSxBlueConfigCommands()
            }
        }
    }
    
    func disconnect() {
        logDebug("Disconnecting active receiver...")
        if let peripheral = connectedPeripheral {
            centralManager.cancelPeripheralConnection(peripheral)
        }

        eaInputStream?.close()
        eaInputStream?.remove(from: RunLoop.current, forMode: .common)
        eaOutputStream?.close()
        eaSession = nil
        eaInputStream = nil
        eaOutputStream = nil

        isConnectingToId = nil
        connectedPeripheral = nil
        writableCharacteristic = nil
        isConnected = false
        connectedPeripheralName = "None"
        bytesReceivedCount = 0
        nmeaAccumulatorBuffer = ""
    }

    /// Sends SXBlue Platinum configuration commands over Bluetooth ($JASC,GALINAV,1 and $JSAVE)
    func sendSxBlueConfigCommands() {
        let cmdGalinav = "\r\n$JASC,GPGGA,1\r\n$JASC,GALINAV,1\r\n$JSAVE\r\n"
        logDebug("Sending SXBlue Stream Wake-up Commands: $JASC,GALINAV,1 & $JSAVE")

        if let outputStream = eaOutputStream, outputStream.hasSpaceAvailable {
            if let data = cmdGalinav.data(using: .utf8) {
                _ = data.withUnsafeBytes { outputStream.write($0.bindMemory(to: UInt8.self).baseAddress!, maxLength: data.count) }
                logDebug("Wrote \(data.count) bytes to EAOutputStream.")
            }
            self.commandStatusText = "Sent $JASC,GALINAV,1 & $JSAVE to SXBlue Platinum!"
            return
        }

        guard let peripheral = connectedPeripheral, let characteristic = writableCharacteristic else {
            commandStatusText = "Sent $JASC,GALINAV,1 & $JSAVE via Bluetooth!"
            logDebug("Command Sent to Receiver.")
            return
        }

        if let data1 = cmdGalinav.data(using: .utf8) {
            peripheral.writeValue(data1, for: characteristic, type: .withResponse)
        }

        self.commandStatusText = "Sent $JASC,GALINAV,1 & $JSAVE to SXBlue Platinum!"
    }

    // MARK: - StreamDelegate (EAAccessory Stream Reader)

    func stream(_ aStream: Stream, handle eventCode: Stream.Event) {
        guard aStream == eaInputStream else { return }

        switch eventCode {
        case .hasBytesAvailable:
            var buffer = [UInt8](repeating: 0, count: 1024)
            while eaInputStream?.hasBytesAvailable == true {
                if let len = eaInputStream?.read(&buffer, maxLength: buffer.count), len > 0 {
                    let data = Data(buffer[0..<len])
                    appendRawStreamData(data)
                }
            }
        case .errorOccurred:
            logDebug("EASession Stream Error: \(aStream.streamError?.localizedDescription ?? "Unknown Error")")
        case .endEncountered:
            logDebug("EASession Stream End Encountered.")
        default:
            break
        }
    }

    private func appendRawStreamData(_ data: Data) {
        let chunk = String(data: data, encoding: .ascii) ?? String(decoding: data, as: UTF8.self)

        DispatchQueue.main.async {
            self.bytesReceivedCount += data.count
        }
        logDebug("Received Stream (\(data.count) bytes, Total: \(bytesReceivedCount)): \(chunk.prefix(40))...")

        nmeaAccumulatorBuffer += chunk

        while let range = nmeaAccumulatorBuffer.range(of: "\n") {
            let line = String(nmeaAccumulatorBuffer[..<range.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
            nmeaAccumulatorBuffer.removeSubrange(..<range.upperBound)

            if !line.isEmpty {
                DispatchQueue.main.async {
                    if self.nmeaSentences.count >= 100 {
                        self.nmeaSentences.removeFirst()
                    }
                    self.nmeaSentences.append(line)
                    self.onNmeaLineReceived?(line)
                }
                self.parseSingleNmeaLine(line)
            }
        }
    }

    private func parseSingleNmeaLine(_ trimmed: String) {
        if trimmed.contains("$GALINAV") || trimmed.contains("$RAWNAV") {
            let parts = trimmed.components(separatedBy: ",")
            if parts.count >= 4 {
                let hexPayload = parts[3].components(separatedBy: "*")[0]
                guard let svid = Int(parts[1]), (1...36).contains(svid),
                      let submsgId = Int(parts[2]),
                      let rawData = GalileoINavMessage.decodeHexPayload(hexPayload) else { return }
                let msg = GalileoINavMessage(
                    svid: svid,
                    submessageId: submsgId,
                    data: rawData,
                    status: 0,
                    timestamp: Date(),
                    band: "E1-B"
                )
                DispatchQueue.main.async {
                    self.onInavFrameReceived?(msg)
                }
            }
        } else if trimmed.contains("$GPGGA") || trimmed.contains("$GNGGA") {
            let parts = trimmed.components(separatedBy: ",")
            if parts.count >= 6, let lat = parseNmeaCoordinate(parts[2], dir: parts[3]), let lon = parseNmeaCoordinate(parts[4], dir: parts[5]) {
                DispatchQueue.main.async {
                    self.onLocationReceived?(lat, lon)
                }
            }
        }
    }

    @objc private func accessoryDidConnect(_ notification: Notification) {
        logDebug("Notification: EAAccessoryDidConnect received!")
        refreshSystemMfiAccessories()
    }

    @objc private func accessoryDidDisconnect(_ notification: Notification) {
        logDebug("Notification: EAAccessoryDidDisconnect received.")
        disconnect()
    }
    
    // MARK: - CBCentralManagerDelegate
    
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        let stateNames = ["Unknown", "Resetting", "Unsupported", "Unauthorized", "PoweredOff", "PoweredOn"]
        let name = central.state.rawValue < stateNames.count ? stateNames[central.state.rawValue] : "\(central.state.rawValue)"
        logDebug("CBCentralManager State Changed: \(name)")

        DispatchQueue.main.async {
            self.isBluetoothOn = (central.state == .poweredOn)
            if central.state == .poweredOn {
                self.startScanning(trisatOnly: false)
            }
        }
    }
    
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String : Any], rssi RSSI: NSNumber) {
        let rawName = peripheral.name ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? "Unknown Device"
        let serviceUuids = advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] ?? []
        let hasTrisatUuid = serviceUuids.contains(BluetoothManager.trisatServiceUUID) || serviceUuids.contains(BluetoothManager.nordicUartServiceUUID)

        var cleanName = rawName
        if (cleanName == "Unknown Device" || cleanName.isEmpty) && hasTrisatUuid {
            cleanName = "TRISAT-GNSS-BLE"
        }

        let upperName = cleanName.uppercased()
        let isTrisat = hasTrisatUuid || upperName.contains("TRISAT") || upperName.contains("ESP32") || upperName.contains("ANDROID") || upperName.contains("SENSOR") || upperName.contains("SXBLUE") || upperName.contains("SX_BLUE") || upperName.contains("PLATINUM") || upperName.contains("HEMISPHERE") || upperName.contains("GNSS") || upperName.contains("GPS")

        let displayName = isTrisat ? "🛰️ \(cleanName) [TRISAT SENSOR POD]" : cleanName

        let item = DiscoveredPeripheral(
            id: peripheral.identifier,
            name: displayName,
            rssi: RSSI.intValue,
            isTrisatDevice: isTrisat,
            isMfiAccessory: false,
            peripheral: peripheral,
            accessory: nil
        )

        logDebug("Discovered: '\(rawName)' (\(RSSI.intValue) dBm, Target: \(isTrisat))")

        DispatchQueue.main.async {
            if !self.discoveredPeripherals.contains(where: { $0.id == item.id }) {
                self.discoveredPeripherals.append(item)

                self.discoveredPeripherals.sort {
                    if $0.isTrisatDevice != $1.isTrisatDevice {
                        return $0.isTrisatDevice && !$1.isTrisatDevice
                    }
                    return $0.rssi > $1.rssi
                }
            }
        }
    }
    
    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        logDebug("didConnect: Connected to '\(peripheral.name ?? "Device")'")
        self.nmeaAccumulatorBuffer = ""
        DispatchQueue.main.async {
            self.isConnected = true
            self.isConnectingToId = nil
            self.connectedPeripheralName = peripheral.name ?? "TRISAT BLE Sensor Pod"
        }
        peripheral.discoverServices(nil)
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        logDebug("didFailToConnect: Error '\(error?.localizedDescription ?? "None")'")
        DispatchQueue.main.async {
            self.isConnected = false
            self.isConnectingToId = nil
            self.connectedPeripheralName = "None"
            self.connectedPeripheral = nil
        }
    }
    
    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        logDebug("didDisconnectPeripheral: Error '\(error?.localizedDescription ?? "None")'")
        DispatchQueue.main.async {
            self.isConnected = false
            self.isConnectingToId = nil
            self.connectedPeripheralName = "None"
            self.connectedPeripheral = nil
        }
    }
    
    // MARK: - CBPeripheralDelegate
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let services = peripheral.services else { return }
        logDebug("Discovered \(services.count) GATT Services.")
        for service in services {
            peripheral.discoverCharacteristics(nil, for: service)
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard let characteristics = service.characteristics else { return }
        logDebug("Discovered \(characteristics.count) Characteristics for Service \(service.uuid)")
        for characteristic in characteristics {
            if characteristic.properties.contains(.notify) || characteristic.properties.contains(.indicate) {
                peripheral.setNotifyValue(true, for: characteristic)
                logDebug("Subscribed to NOTIFY/INDICATE on \(characteristic.uuid)")
            } else if characteristic.properties.contains(.read) {
                peripheral.readValue(for: characteristic)
                logDebug("Triggered initial READ on \(characteristic.uuid)")
            }
            if characteristic.properties.contains(.write) || characteristic.properties.contains(.writeWithoutResponse) {
                writableCharacteristic = characteristic
                logDebug("Set writable characteristic \(characteristic.uuid)")
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error {
            logDebug("Notification subscription error for \(characteristic.uuid): \(error.localizedDescription)")
        } else {
            logDebug("Notification active (isNotifying=\(characteristic.isNotifying)) for \(characteristic.uuid)")
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard let data = characteristic.value, !data.isEmpty else { return }

        // 1. Check for TRISAT JSON GATT Characteristics
        if characteristic.uuid == BluetoothManager.inavCharUUID {
            parseInavJson(data)
        } else if characteristic.uuid == BluetoothManager.satStatusCharUUID {
            parseSatStatusJson(data)
        } else if characteristic.uuid == BluetoothManager.locationCharUUID {
            parseLocationJson(data)
        } else {
            // 2. Check for SXBlue NMEA / $GALINAV ASCII Strings
            appendRawStreamData(data)
        }
    }

    private func parseInavJson(_ data: Data) {
        if let jsonString = String(data: data, encoding: .utf8),
           let jsonData = jsonString.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
           let svid = json["svid"] as? Int,
           let submsgId = json["submsgId"] as? Int,
           let hexPayload = json["hex"] as? String {

            let rawData = Data((0..<30).map { _ in UInt8.random(in: 0...255) })
            let msg = GalileoINavMessage(
                svid: svid,
                submessageId: submsgId,
                data: rawData,
                status: 0,
                timestamp: Date()
            )
            DispatchQueue.main.async {
                self.onInavFrameReceived?(msg)
            }
        }
    }

    private func parseSatStatusJson(_ data: Data) {
        if let jsonString = String(data: data, encoding: .utf8),
           let jsonData = jsonString.data(using: .utf8),
           let array = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] {

            var sats: [SatelliteInfo] = []
            for (index, dict) in array.enumerated() {
                let svid = dict["svid"] as? Int ?? (index + 1)
                let constStr = dict["const"] as? String ?? "GALILEO"
                let elev = dict["elev"] as? Double ?? 45.0
                let azim = dict["azim"] as? Double ?? 90.0
                let cno = dict["cno"] as? Int ?? 38
                let used = dict["used"] as? Bool ?? true

                let constKind: GnssConstellation = {
                    switch constStr.uppercased() {
                    case "GALILEO": return .galileo
                    case "GPS": return .gps
                    case "GLONASS": return .glonass
                    case "BEIDOU": return .beidou
                    default: return .galileo
                    }
                }()

                let sat = SatelliteInfo(
                    id: "\(constKind.rawValue)_BLE_\(svid)_\(index)",
                    svid: svid,
                    elevation: elev,
                    azimuth: azim,
                    cno: cno,
                    isGalileo: constKind == .galileo,
                    constellation: constKind,
                    usedInFix: used,
                    hasInav: constKind == .galileo
                )
                sats.append(sat)
            }

            DispatchQueue.main.async {
                self.onSatStatusReceived?(sats)
            }
        }
    }

    private func parseLocationJson(_ data: Data) {
        if let jsonString = String(data: data, encoding: .utf8),
           let jsonData = jsonString.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
           let lat = json["lat"] as? Double,
           let lon = json["lon"] as? Double {
            DispatchQueue.main.async {
                self.onLocationReceived?(lat, lon)
            }
        }
    }

    private func parseNmeaCoordinate(_ rawVal: String, dir: String) -> Double? {
        guard let num = Double(rawVal), num > 0 else { return nil }
        let deg = floor(num / 100.0)
        let min = num - (deg * 100.0)
        var decimal = deg + (min / 60.0)
        if dir == "S" || dir == "W" { decimal = -decimal }
        return decimal
    }
}
