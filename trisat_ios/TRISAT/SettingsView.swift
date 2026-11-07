import SwiftUI

struct SettingsView: View {
    @ObservedObject var bluetoothManager: BluetoothManager
    @ObservedObject var viewModel: GnssViewModel
    @ObservedObject var telemetryBridge: GnssTelemetryBridge

    @Environment(\.horizontalSizeClass) var horizontalSizeClass
    @State private var showBlePickerSheet: Bool = false
    @State private var selectedBleDeviceName: String = ""
    @State private var selectedBridgeOption: Int = 1

    #if os(macOS)
    @ObservedObject var macSerialManager: MacSerialPortManager

    init(bluetoothManager: BluetoothManager, viewModel: GnssViewModel, telemetryBridge: GnssTelemetryBridge = GnssTelemetryBridge(), macSerialManager: MacSerialPortManager = MacSerialPortManager()) {
        self.bluetoothManager = bluetoothManager
        self.viewModel = viewModel
        self.telemetryBridge = telemetryBridge
        self.macSerialManager = macSerialManager
    }
    #else
    init(bluetoothManager: BluetoothManager, viewModel: GnssViewModel, telemetryBridge: GnssTelemetryBridge = GnssTelemetryBridge()) {
        self.bluetoothManager = bluetoothManager
        self.viewModel = viewModel
        self.telemetryBridge = telemetryBridge
    }
    #endif

    private var isWideLayout: Bool {
        #if os(macOS)
        return true
        #else
        return horizontalSizeClass == .regular
        #endif
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                // Top Header Banner
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Settings & Hardware Configuration")
                            .font(.headline)
                            .bold()
                        Text("Select an operating mode to configure telemetry and constellation tracking")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)

                // MARK: - Central 3-Mode Primary Selector
                modeSelectorHeader

                // MARK: - Mode-Specific View Panels (Mutually Exclusive)
                VStack(spacing: 14) {
                    switch viewModel.selectedMode {
                    case 0:
                        // 1. Internal GPS + CelesTrak TLE 24h Keplerian Orbit Simulator
                        internalTleSection
                    case 1:
                        // 2. External Bluetooth GNSS Receivers (BLE Nordic UART & MFi)
                        bluetoothSection
                    case 2:
                        // 3. UDP Telemetry Stream (:9090) & SDR Engine
                        udpServerSection
                    default:
                        internalTleSection
                    }
                }
                .padding(.horizontal, 16)

                // Quick Diagnostics & About (Stacked vertically)
                VStack(spacing: 12) {
                    osnmaSection
                    aboutSection
                }
                .padding(.horizontal, 16)
                .padding(.top, 6)
            }
            .padding(.bottom, 20)
        }
        .sheet(isPresented: $showBlePickerSheet) {
            BleDevicePickerSheet(bluetoothManager: bluetoothManager)
        }
        .onAppear {
            #if os(macOS)
            macSerialManager.onLineReceived = { line in
                DispatchQueue.main.async {
                    bluetoothManager.isConnected = true
                    bluetoothManager.connectedPeripheralName = macSerialManager.connectedPortName
                    if bluetoothManager.nmeaSentences.count >= 100 {
                        bluetoothManager.nmeaSentences.removeFirst()
                    }
                    bluetoothManager.nmeaSentences.append(line)
                    bluetoothManager.onNmeaLineReceived?(line)
                }
            }
            #endif
        }
    }

    // MARK: - Primary 3-Mode Segmented Selector

    private var modeSelectorHeader: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker("Operating Mode", selection: $viewModel.selectedMode) {
                Text("🛰️ Internal + TLE").tag(0)
                Text("📡 Bluetooth").tag(1)
                Text("🌐 UDP").tag(2)
            }
            .pickerStyle(.segmented)
            .onChange(of: viewModel.selectedMode) { newMode in
                viewModel.updateSatellites()
                if newMode == 0 {
                    if telemetryBridge.isSdrEngineRunning {
                        telemetryBridge.stopTrisatSdrEngine(quiet: true)
                    }
                    telemetryBridge.stopPingEngine()
                } else if newMode == 1 {
                    telemetryBridge.stopPingEngine()
                    if !bluetoothManager.isConnected {
                        bluetoothManager.startScanning(trisatOnly: false)
                    }
                } else if newMode == 2 {
                    if !telemetryBridge.isListening {
                        telemetryBridge.startUdpListener(port: 9090)
                    } else {
                        telemetryBridge.startPingEngine()
                    }
                }
            }
        }
        .padding(.horizontal, 16)
    }

    // MARK: - MODE 1: Internal GPS + CelesTrak TLE 24-Hour Orbit Propagator

    private var internalTleSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "globe.americas.fill")
                    .foregroundColor(.cyan)
                Text("Internal GNSS + CelesTrak TLE (24h Orbit)")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text("\(viewModel.displayedSatellites.count) SATS VISIBLE")
                    .font(.system(size: 9, weight: .bold))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(Color.cyan.opacity(0.2))
                    .foregroundColor(.cyan)
                    .cornerRadius(6)
            }

            // 4-Constellation TLE Catalog Badges
            HStack(spacing: 8) {
                tleCountBadge(name: "Galileo", count: viewModel.tleDownloader.galileoCount, color: .cyan)
                tleCountBadge(name: "GPS", count: viewModel.tleDownloader.gpsCount, color: .orange)
                tleCountBadge(name: "GLONASS", count: viewModel.tleDownloader.glonassCount, color: .red)
                tleCountBadge(name: "BeiDou", count: viewModel.tleDownloader.beidouCount, color: .green)
            }

            // Interactive Constellation Filter Toggles
            HStack(spacing: 6) {
                FilterToggleChip(title: "Galileo", iconName: "globe.europe.africa.fill", isSelected: $viewModel.isGalileoEnabled, color: .cyan)
                FilterToggleChip(title: "GPS", iconName: "location.north.line.fill", isSelected: $viewModel.isGpsEnabled, color: .orange)
                FilterToggleChip(title: "GLONASS", iconName: "antenna.radiowaves.left.and.right", isSelected: $viewModel.isGlonassEnabled, color: .red)
                FilterToggleChip(title: "BeiDou", iconName: "star.fill", isSelected: $viewModel.isBeidouEnabled, color: .green)
            }

            SkyPlotView(satellites: viewModel.displayedSatellites, height: 210)
                .padding(.vertical, 2)

            // 24-Hour Keplerian Orbit Propagation Slider (±12h)
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Image(systemName: "clock.arrow.circlepath")
                        .foregroundColor(.cyan)
                    Text("24h Time Scrubbing (Keplerian Orbit Offset):")
                        .font(.caption)
                        .fontWeight(.semibold)
                    Spacer()
                    Text(String(format: "%+.1f h", viewModel.timeOffsetHours))
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.cyan)
                    if viewModel.timeOffsetHours != 0.0 {
                        Button("Reset 0h") {
                            viewModel.timeOffsetHours = 0.0
                            viewModel.updateSatellites()
                        }
                        .font(.caption2)
                        .buttonStyle(.plain)
                        .foregroundColor(.orange)
                    }
                }

                Slider(value: $viewModel.timeOffsetHours, in: -12.0...12.0, step: 0.5) { _ in
                    viewModel.updateSatellites()
                }
            }
            .padding(10)
            .background(Color.cyan.opacity(0.08))
            .cornerRadius(10)

            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(viewModel.tleDownloader.downloadStatusText)
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundColor(.cyan)
                    Text("Updated: \(viewModel.tleDownloader.formattedLastDownloadDate)")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }
                Spacer()
                Button(action: {
                    Task {
                        await viewModel.tleDownloader.fetchAllTleOrbits()
                        viewModel.updateSatellites()
                    }
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.clockwise.icloud")
                        Text(viewModel.tleDownloader.isDownloading ? "Syncing..." : "Refresh TLEs")
                    }
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.blue.opacity(0.2))
                    .foregroundColor(.blue)
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
                .disabled(viewModel.tleDownloader.isDownloading)
            }
        }
        .padding(14)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(16)
    }

    private func tleCountBadge(name: String, count: Int, color: Color) -> some View {
        VStack(spacing: 2) {
            Text(name)
                .font(.system(size: 9, weight: .bold))
                .foregroundColor(.secondary)
            Text("\(count)")
                .font(.system(size: 12, weight: .bold, design: .monospaced))
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 5)
        .background(color.opacity(0.1))
        .cornerRadius(6)
    }

    // MARK: - MODE 2: External Hardware & Bluetooth GNSS Receivers

    private var bluetoothSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            #if os(macOS)
            // USB Connected Receivers (u-blox / SXBlue) FIRST on macOS!
            macSerialSection

            Divider()
            #endif

            HStack {
                Image(systemName: "antenna.radiowaves.left.and.right")
                    .foregroundColor(.blue)
                Text("Bluetooth GNSS Receivers (BLE / MFi)")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(bluetoothManager.isConnected ? "CONNECTED" : "DISCONNECTED")
                    .font(.system(size: 9, weight: .bold))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(bluetoothManager.isConnected ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                    .foregroundColor(bluetoothManager.isConnected ? .green : .red)
                    .cornerRadius(6)
            }

            if bluetoothManager.isConnected {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Active Receiver:")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text(bluetoothManager.connectedPeripheralName)
                            .font(.caption)
                            .fontWeight(.bold)
                            .lineLimit(1)
                    }
                    Spacer()
                    Button("Disconnect") {
                        #if os(macOS)
                        macSerialManager.disconnect()
                        #endif
                        bluetoothManager.disconnect()
                        viewModel.resetHardwareTelemetry()
                    }
                    .font(.caption)
                    .buttonStyle(.bordered)
                    .tint(.red)
                }
                .padding(10)
                .background(Color.green.opacity(0.1))
                .cornerRadius(10)
            }

            HStack {
                Text("Discovered Devices (\(bluetoothManager.discoveredPeripherals.count)):")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                Button(bluetoothManager.isScanning ? "Stop Scan" : "Scan BLE") {
                    if bluetoothManager.isScanning {
                        bluetoothManager.stopScanning()
                    } else {
                        bluetoothManager.startScanning(trisatOnly: false)
                    }
                }
                .font(.caption)
                .buttonStyle(.borderedProminent)
                .tint(.blue)
            }

            if !bluetoothManager.discoveredPeripherals.isEmpty {
                VStack(spacing: 8) {
                    ForEach(bluetoothManager.discoveredPeripherals) { item in
                        Button(action: {
                            bluetoothManager.connect(to: item)
                        }) {
                            HStack {
                                Image(systemName: "wave.3.right")
                                    .foregroundColor(.blue)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.name)
                                        .font(.subheadline)
                                        .fontWeight(.semibold)
                                        .foregroundColor(.primary)
                                        .lineLimit(1)
                                    Text("RSSI: \(item.rssi) dBm")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                            .padding(10)
                            .background(Color.gray.opacity(0.1))
                            .cornerRadius(10)
                        }
                        .buttonStyle(.plain)
                    }
                }
            } else if bluetoothManager.isScanning {
                HStack {
                    Spacer()
                    ProgressView("Scanning nearby Bluetooth GNSS receivers...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                .padding(.vertical, 16)
            } else {
                Text("Tap 'Scan BLE' to search for Bluetooth GNSS receivers.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.vertical, 8)
            }
        }
        .padding(14)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(16)
    }

    // MARK: - MODE 3: UDP Telemetry Stream & SDR Engine

    private var udpServerSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "network")
                    .foregroundColor(.green)
                Text("UDP Telemetry Stream (:9090)")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(telemetryBridge.isListening ? "UDP STREAM ACTIVE" : "STOPPED")
                    .font(.system(size: 9, weight: .bold))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(telemetryBridge.isListening ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                    .foregroundColor(telemetryBridge.isListening ? .green : .red)
                    .cornerRadius(6)
            }

            Text("Listens on UDP Port 9090 for incoming NMEA sentences and raw binary frames from the ESP32 Wi-Fi AP, Raspberry Pi station, or TRISAT-SDR engine.")
                .font(.caption)
                .foregroundColor(.secondary)

            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Listening Port:")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("UDP :\(telemetryBridge.listenerPort)")
                        .font(.subheadline)
                        .bold()
                }
                Spacer()
                Button(telemetryBridge.isListening ? "Stop Listener" : "Start Listener (:9090)") {
                    if telemetryBridge.isListening {
                        telemetryBridge.stopUdpListener()
                    } else {
                        telemetryBridge.startUdpListener(port: 9090)
                    }
                }
                .font(.caption)
                .buttonStyle(.borderedProminent)
                .tint(telemetryBridge.isListening ? .red : .green)
            }
            .padding(10)
            .background(Color.gray.opacity(0.1))
            .cornerRadius(10)

            HStack {
                Text(telemetryBridge.statusText)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                Spacer()
                Text("Datagrams Rx: \(telemetryBridge.packetsReceivedCount)")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.cyan)
            }

            Divider()

            // In-Device Telemetry & Constellation Simulator (iOS & macOS)
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Telemetry Simulator")
                            .font(.subheadline)
                            .fontWeight(.bold)
                        Text("Simulates live Galileo & GPS constellations, NMEA sentences ($GAGSV, $GPGSV, $GNGGA), C/N0 SNR and I/NAV frames on device")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                    Button(telemetryBridge.isSdrEngineRunning ? "Stop Simulator" : "Start Simulator") {
                        if telemetryBridge.isSdrEngineRunning {
                            telemetryBridge.stopTrisatSdrEngine()
                        } else {
                            telemetryBridge.startTrisatSdrEngine()
                        }
                    }
                    .font(.caption)
                    .buttonStyle(.borderedProminent)
                    .tint(telemetryBridge.isSdrEngineRunning ? .red : .cyan)
                }

                if telemetryBridge.isSdrEngineRunning {
                    HStack(spacing: 8) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 8, height: 8)
                        Text("Simulator active: Streaming Galileo + GPS satellites to Signal Processing & Skyplot at 1 Hz")
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .foregroundColor(.green)
                    }
                }

                #if os(macOS)
                Divider()
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("u-blox ZED-F9P USB Bridge (Red Board):")
                            .font(.caption)
                            .fontWeight(.semibold)
                        Text("Routes USB /dev/cu.usbmodem* directly into UDP :9090 (Available to Mac & iPhone on Wi-Fi)")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                    Button(telemetryBridge.isF9pBridgeRunning ? "Stop F9P Bridge" : "Launch F9P Bridge") {
                        if telemetryBridge.isF9pBridgeRunning {
                            telemetryBridge.stopF9pBridge()
                        } else {
                            telemetryBridge.startF9pBridge()
                        }
                    }
                    .font(.caption)
                    .buttonStyle(.borderedProminent)
                    .tint(telemetryBridge.isF9pBridgeRunning ? .red : .green)
                }

                Divider()
                HStack {
                    Text("TRISAT-SDR Dual-HackRF Backend:")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                    Button("Open Web Dashboard") {
                        telemetryBridge.openWebDashboard()
                    }
                    .font(.caption2)
                    .buttonStyle(.bordered)
                }
                #endif
            }
            .padding(12)
            .background(telemetryBridge.isSdrEngineRunning ? Color.cyan.opacity(0.1) : Color.gray.opacity(0.06))
            .cornerRadius(12)
        }
        .padding(14)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(16)
    }

    // MARK: - Section: macOS Hardware Serial Ports

    #if os(macOS)
    private var macSerialSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "cable.connector.horizontal")
                    .foregroundColor(.green)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Direct USB Receivers (u-blox / SXBlue)")
                        .font(.subheadline)
                        .fontWeight(.bold)
                    Text("Plug & Play USB CDC-ACM & Serial Ports (/dev/cu.*)")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Button(action: { macSerialManager.refreshPortsAndAutoConnect() }) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                        .font(.caption2)
                }
                .buttonStyle(.bordered)
            }

            if !macSerialManager.availablePorts.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Picker("USB Serial Port", selection: $macSerialManager.selectedPortPath) {
                            ForEach(macSerialManager.availablePorts) { port in
                                Text(port.name).tag(port.path)
                            }
                        }
                        .labelsHidden()
                        .pickerStyle(.menu)

                        if macSerialManager.isConnected {
                            Button("Disconnect") {
                                macSerialManager.disconnect()
                                bluetoothManager.isConnected = false
                                bluetoothManager.connectedPeripheralName = "None"
                                viewModel.resetHardwareTelemetry()
                            }
                            .font(.caption)
                            .buttonStyle(.borderedProminent)
                            .tint(.red)
                        } else {
                            Button("Connect") {
                                macSerialManager.connectToSelectedPort()
                            }
                            .font(.caption)
                            .buttonStyle(.borderedProminent)
                            .tint(.green)
                        }
                    }

                    if let err = macSerialManager.lastError {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(.orange)
                                .font(.caption)
                            Text(err)
                                .font(.caption2)
                                .foregroundColor(.red)
                                .lineLimit(2)
                        }
                        .padding(.vertical, 2)
                    }

                    if macSerialManager.isConnected {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(Color.green)
                                .frame(width: 8, height: 8)
                            Text("Connected to: \(macSerialManager.connectedPortName) (115200 bps)")
                                .font(.caption2)
                                .fontWeight(.semibold)
                                .foregroundColor(.green)
                        }

                        // Hardware Constellation Quick Switcher
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Receiver Tracking Mode:")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundColor(.secondary)
                            HStack(spacing: 8) {
                                Button("🇪🇺 Galileo Only (OSNMA)") {
                                    macSerialManager.configureReceiverGalileoOnly()
                                }
                                .font(.caption2)
                                .buttonStyle(.bordered)

                                Button("🛰️ Multi-GNSS (GPS+GAL+GLO+BDS)") {
                                    macSerialManager.configureReceiverAllConstellations()
                                }
                                .font(.caption2)
                                .buttonStyle(.bordered)
                            }
                        }
                        .padding(.top, 4)
                    }
                }
            } else {
                Text("No direct USB serial ports found.")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(12)
        .background(macSerialManager.isConnected ? Color.green.opacity(0.08) : Color.gray.opacity(0.06))
        .cornerRadius(12)
    }
    #endif

    // MARK: - Section: OSNMA & About Cards

    private var osnmaSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "key.fill")
                    .foregroundColor(.orange)
                Text("OSNMA Engine")
                    .font(.subheadline)
                    .fontWeight(.bold)
            }

            HStack {
                Text("Root Key")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Text("Galileo HKROOT v1.1")
                    .font(.caption2)
                    .fontWeight(.bold)
            }

            HStack {
                Text("ECDSA / MAC")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Text("P-256 / HMAC-256")
                    .font(.caption2)
                    .fontWeight(.bold)
            }

            HStack {
                Text("HAS Decoder")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Text("RS(255,32) SL1")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.cyan)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    private var aboutSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "info.circle.fill")
                    .foregroundColor(.gray)
                Text("TRISAT Engine")
                    .font(.subheadline)
                    .fontWeight(.bold)
            }

            HStack {
                Text("Version")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Text("2.0.4 (Multiplatform)")
                    .font(.caption2)
                    .fontWeight(.bold)
            }

            HStack {
                Text("Platform")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                #if os(macOS)
                Text("macOS Native")
                    .font(.caption2)
                    .fontWeight(.bold)
                #else
                Text("iOS Native")
                    .font(.caption2)
                    .fontWeight(.bold)
                #endif
            }

            HStack {
                Text("Architecture")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Text("Tri-Band / Tri-Service")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.green)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }
}
