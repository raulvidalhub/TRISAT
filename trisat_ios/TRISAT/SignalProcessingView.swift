import SwiftUI

struct SignalProcessingView: View {
    @ObservedObject var viewModel: GnssViewModel
    @ObservedObject var telemetryBridge: GnssTelemetryBridge
    @ObservedObject var bluetoothManager: BluetoothManager
    @Environment(\.horizontalSizeClass) var horizontalSizeClass

    init(viewModel: GnssViewModel, telemetryBridge: GnssTelemetryBridge = GnssTelemetryBridge(), bluetoothManager: BluetoothManager? = nil) {
        self.viewModel = viewModel
        self.telemetryBridge = telemetryBridge
        self.bluetoothManager = bluetoothManager ?? viewModel.bluetoothManager
    }

    private var isWideLayout: Bool {
        #if os(macOS)
        return true
        #else
        return horizontalSizeClass == .regular
        #endif
    }

    private var isTelemetryActive: Bool {
        if viewModel.selectedMode == 0 { return false }
        return viewModel.isTelemetryActive || telemetryBridge.isSdrEngineRunning
    }

    var body: some View {
        if !isTelemetryActive {
            telemetryStandbyView
        } else {
            GeometryReader { geometry in
            let availableHeight = geometry.size.height
            // Header (~110) + Row 1 (~255) + Spacing & padding (~35) = ~400
            let dynamicCardHeight = isWideLayout ? max(260, availableHeight - 400) : 260

            ScrollView(isWideLayout ? [] : .vertical) {
                VStack(alignment: .leading, spacing: 12) {
                    // MARK: - Clean Read-Only Telemetry Header & Metrics
                    topMetricsHeader

                    if isWideLayout {
                        // macOS & iPad: Clean 2x2 Grid Fitted to Desktop Screen
                        VStack(spacing: 12) {
                            // ROW 1: Compact Open Skyplot + C/N0 SNR Bar Chart
                            HStack(alignment: .top, spacing: 14) {
                                openSkyplotCard
                                    .frame(width: 260)

                                snrBarChartCard
                                    .frame(maxWidth: .infinity)
                            }

                            // ROW 2: NMEA Live Terminal + Galileo I/NAV Subframe Cards (Fills all remaining height)
                            HStack(alignment: .top, spacing: 14) {
                                nmeaStreamCard(contentHeight: dynamicCardHeight)
                                    .frame(maxWidth: .infinity)

                                galileoInavCard(contentHeight: dynamicCardHeight)
                                    .frame(maxWidth: .infinity)
                            }
                        }
                        .padding(.horizontal, 16)
                    } else {
                        // Compact Vertical Flow
                        VStack(spacing: 14) {
                            openSkyplotCard
                            snrBarChartCard
                            nmeaStreamCard(contentHeight: 260)
                            galileoInavCard(contentHeight: 260)
                        }
                        .padding(.horizontal)
                    }
                }
                .padding(.bottom, 12)
            }
        }
    }
}

    // MARK: - Standby Mode when no receiver/simulator is active

    private var telemetryStandbyView: some View {
        VStack(spacing: 20) {
            Spacer()

            ZStack {
                Circle()
                    .fill(Color.cyan.opacity(0.12))
                    .frame(width: 96, height: 96)
                Image(systemName: "waveform.path.ecg")
                    .font(.system(size: 44))
                    .foregroundColor(.cyan)
            }

            VStack(spacing: 8) {
                Text("Signal Processing Standby")
                    .font(.title3)
                    .fontWeight(.bold)

                Text("Awaiting raw GNSS telemetry stream.\nConnect a Bluetooth receiver, stream UDP data (:9090), or launch the Simulator.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 36)
            }

            Button(action: {
                viewModel.selectedMode = 2
                telemetryBridge.startTrisatSdrEngine()
            }) {
                Label("Start Simulator", systemImage: "play.fill")
                    .font(.subheadline.weight(.semibold))
            }
            .buttonStyle(.borderedProminent)
            .tint(.cyan)
            .padding(.top, 4)

            HStack(spacing: 6) {
                Circle()
                    .fill(Color.orange)
                    .frame(width: 8, height: 8)
                Text("Receiver Status: No Active Telemetry")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 6)
            .background(Color.gray.opacity(0.1))
            .cornerRadius(12)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        #if os(macOS)
        .background(Color(NSColor.windowBackgroundColor))
        #else
        .background(Color(UIColor.systemBackground))
        #endif
    }

    // MARK: - Header: Clean Telemetry Status & Differential Metrics (Config Moved to Settings)

    private var topMetricsHeader: some View {
        VStack(alignment: .leading, spacing: 8) {
            if isWideLayout {
                // Desktop / iPad: Wide Single-Row Header
                HStack {
                    sourceStatusBlock
                    Spacer()
                    constellationFilterChips
                }
            } else {
                // iPhone: 2-Row Header (Status on Top, Filter Chips below)
                VStack(alignment: .leading, spacing: 6) {
                    sourceStatusBlock
                    constellationFilterChips
                }
            }

            // Differential & Precision Metrics Badges
            if isWideLayout {
                HStack(spacing: 10) {
                    metricsGrid
                }
            } else {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 6) {
                    metricsGrid
                }
            }
        }
        .padding(12)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }

    private var sourceStatusBlock: some View {
        HStack(spacing: 8) {
            Image(systemName: (bluetoothManager.isConnected || telemetryBridge.isSdrEngineRunning) ? "checkmark.circle.fill" : "antenna.radiowaves.left.and.right")
                .font(.title3)
                .foregroundColor((bluetoothManager.isConnected || telemetryBridge.isSdrEngineRunning) ? .green : .cyan)

            VStack(alignment: .leading, spacing: 2) {
                Text(telemetryBridge.isSdrEngineRunning ? "Active: Simulator" : (bluetoothManager.isConnected ? "Active: \(bluetoothManager.connectedPeripheralName)" : "Source: Internal Receiver / UDP (:9090)"))
                    .font(.subheadline)
                    .bold()
                    .lineLimit(1)
                Text(telemetryBridge.isSdrEngineRunning ? "Streaming Live Galileo + GPS Telemetry & I/NAV" : "Multi-Constellation Telemetry, C/N0 & I/NAV Monitor")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Button(telemetryBridge.isSdrEngineRunning ? "Stop Sim" : "Start Sim") {
                if telemetryBridge.isSdrEngineRunning {
                    telemetryBridge.stopTrisatSdrEngine()
                } else {
                    viewModel.selectedMode = 2
                    telemetryBridge.startTrisatSdrEngine()
                }
            }
            .font(.caption2)
            .buttonStyle(.borderedProminent)
            .tint(telemetryBridge.isSdrEngineRunning ? .red : .cyan)
        }
    }

    private var constellationFilterChips: some View {
        HStack(spacing: 6) {
            FilterToggleChip(title: "Galileo", iconName: "globe.europe.africa.fill", isSelected: $viewModel.isGalileoEnabled, color: .cyan)
            FilterToggleChip(title: "GPS", iconName: "location.north.line.fill", isSelected: $viewModel.isGpsEnabled, color: .orange)
            FilterToggleChip(title: "GLONASS", iconName: "antenna.radiowaves.left.and.right", isSelected: $viewModel.isGlonassEnabled, color: .red)
            FilterToggleChip(title: "BeiDou", iconName: "star.fill", isSelected: $viewModel.isBeidouEnabled, color: .green)
        }
    }

    @ViewBuilder
    private var metricsGrid: some View {
        metricCard(title: "Fix Mode", value: viewModel.fixTypeDesc, icon: "location.fill", color: .green)
        metricCard(title: "Sats in Fix / HDOP", value: "\(viewModel.numSatellitesInFix) Sats | HDOP \(viewModel.hdopValue)", icon: "satellite.fill", color: .cyan)
        metricCard(title: "Carrier Bands", value: viewModel.isDualFrequencyActive ? "Dual E1+E5b (\(viewModel.numDualFrequencySatellites) SVs)" : "Single-Band E1/L1", icon: "waveform.path.badge.plus", color: .purple)
        metricCard(title: "Correction Source", value: "ID: \(viewModel.dgpsStationId) (\(viewModel.dgpsAge))", icon: "checkmark.shield.fill", color: .orange)
        metricCard(title: "Pseudorange Error", value: viewModel.gstRmsError, icon: "chart.xyaxis.line", color: .purple)
    }

    private func metricCard(title: String, value: String, icon: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.caption2)
                    .foregroundColor(color)
                Text(title)
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(.secondary)
            }
            Text(value)
                .font(.system(size: 11, weight: .bold, design: .monospaced))
                .foregroundColor(.primary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(8)
        .background(color.opacity(0.08))
        .cornerRadius(8)
    }

    // MARK: - Quadrant 1: Compact Open Sky Polar Skyplot

    private var openSkyplotCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "circle.circle")
                    .foregroundColor(.cyan)
                Text("Open Sky Radar")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(viewModel.displayedSatellites.count) Sats")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(.cyan)
            }

            SkyPlotView(satellites: viewModel.displayedSatellites, height: 195)
                .padding(4)
        }
        .padding(12)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    // MARK: - Quadrant 2: Satellite C/N0 SNR Bar Chart

    private var snrBarChartCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundColor(.green)
                Text("Signal Strength C/N0 (dB-Hz)")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                Spacer()
                HStack(spacing: 8) {
                    legendDot(label: "E1/L1", color: .green)
                    legendDot(label: "E5b/L2 (2F)", color: .purple)
                    legendDot(label: "Galileo", color: .cyan)
                    legendDot(label: "GPS", color: .orange)
                }
            }

            if viewModel.displayedSatellites.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "satellite")
                        .font(.system(size: 30))
                        .foregroundColor(.cyan)
                        .padding(.top, 24)
                    Text("Awaiting Satellite Telemetry...")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Button(telemetryBridge.isSdrEngineRunning ? "Stop Simulator" : "Start Simulator") {
                        if telemetryBridge.isSdrEngineRunning {
                            telemetryBridge.stopTrisatSdrEngine()
                        } else {
                            viewModel.selectedMode = 2
                            telemetryBridge.startTrisatSdrEngine()
                        }
                    }
                    .font(.caption)
                    .buttonStyle(.borderedProminent)
                    .tint(.cyan)
                    Spacer()
                }
                .frame(maxWidth: .infinity, minHeight: 195)
            } else {
                ScrollView(.horizontal, showsIndicators: true) {
                    HStack(alignment: .bottom, spacing: 10) {
                        ForEach(viewModel.displayedSatellites) { sat in
                            VStack(spacing: 4) {
                                if sat.isDualFrequency {
                                    HStack(spacing: 2) {
                                        Text("\(sat.cno)")
                                            .font(.system(size: 8, weight: .bold, design: .monospaced))
                                            .foregroundColor(snrColor(sat.cno))
                                        Text("/")
                                            .font(.system(size: 7, weight: .light))
                                            .foregroundColor(.secondary)
                                        Text("\(sat.cnoSecondary)")
                                            .font(.system(size: 8, weight: .bold, design: .monospaced))
                                            .foregroundColor(secondarySnrColor(sat.cnoSecondary))
                                    }

                                    HStack(alignment: .bottom, spacing: 3) {
                                        // Primary Carrier Bar (E1 / L1 / B1 / G1)
                                        ZStack(alignment: .bottom) {
                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(Color.gray.opacity(0.15))
                                                .frame(width: 11, height: 140)

                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(snrColor(sat.cno))
                                                .frame(width: 11, height: CGFloat(min(max(sat.cno, 0), 54)) * 2.55)
                                        }

                                        // Secondary Carrier Bar (E5b / L2 / B2 / G2)
                                        ZStack(alignment: .bottom) {
                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(Color.gray.opacity(0.15))
                                                .frame(width: 11, height: 140)

                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(secondarySnrColor(sat.cnoSecondary))
                                                .frame(width: 11, height: CGFloat(min(max(sat.cnoSecondary, 0), 54)) * 2.55)
                                        }
                                    }
                                } else {
                                    Text("\(sat.cno)")
                                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                                        .foregroundColor(snrColor(sat.cno))

                                    ZStack(alignment: .bottom) {
                                        RoundedRectangle(cornerRadius: 3)
                                            .fill(Color.gray.opacity(0.15))
                                            .frame(width: 20, height: 140)

                                        RoundedRectangle(cornerRadius: 3)
                                            .fill(snrColor(sat.cno))
                                            .frame(width: 20, height: CGFloat(min(max(sat.cno, 0), 54)) * 2.55)
                                    }
                                }

                                Text(sat.formattedLabel)
                                    .font(.system(size: 8, weight: .bold, design: .monospaced))
                                    .padding(.horizontal, 4)
                                    .padding(.vertical, 2)
                                    .background(sat.constellation.color.opacity(0.22))
                                    .foregroundColor(sat.constellation.color)
                                    .cornerRadius(3)

                                Text(sat.bandsLabel)
                                    .font(.system(size: 7, weight: sat.isDualFrequency ? .heavy : .semibold, design: .monospaced))
                                    .padding(.horizontal, 3)
                                    .padding(.vertical, 1)
                                    .background(sat.isDualFrequency ? Color.purple.opacity(0.35) : Color.gray.opacity(0.18))
                                    .foregroundColor(sat.isDualFrequency ? .purple : .secondary)
                                    .cornerRadius(2.5)
                            }
                        }
                    }
                    .padding(.vertical, 6)
                    .padding(.horizontal, 8)
                }
                .frame(minHeight: 195)
            }
        }
        .padding(12)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    private func legendDot(label: String, color: Color) -> some View {
        HStack(spacing: 3) {
            Circle()
                .fill(color)
                .frame(width: 6, height: 6)
            Text(label)
                .font(.system(size: 9, weight: .semibold))
                .foregroundColor(.secondary)
        }
    }

    // MARK: - Quadrant 3: ASCII NMEA Live Stream Terminal

    private func nmeaStreamCard(contentHeight: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "terminal.fill")
                    .foregroundColor(.green)
                Text("ASCII NMEA Stream ($GNGGA, $GAGSV, $GNGST, $GALINAV, $GALE6HAS)")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                Spacer()
                if !bluetoothManager.nmeaSentences.isEmpty {
                    Button("Clear") {
                        bluetoothManager.nmeaSentences.removeAll()
                    }
                    .font(.caption2)
                    .foregroundColor(.red)
                    .buttonStyle(.plain)
                }
            }

            if bluetoothManager.nmeaSentences.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "terminal")
                        .font(.system(size: 30))
                        .foregroundColor(.cyan)
                        .padding(.top, 24)
                    Text("Waiting for NMEA datagrams...")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
                .cornerRadius(10)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 3) {
                            ForEach(Array(bluetoothManager.nmeaSentences.enumerated()), id: \.offset) { index, sentence in
                                Text(sentence)
                                    .font(.system(size: 10.5, design: .monospaced))
                                    .foregroundColor(.green)
                                    .id(index)
                            }
                        }
                        .padding(8)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black)
                    .cornerRadius(10)
                    .onChange(of: bluetoothManager.nmeaSentences.count) { _ in
                        if let lastIdx = bluetoothManager.nmeaSentences.indices.last {
                            proxy.scrollTo(lastIdx, anchor: .bottom)
                        }
                    }
                }
            }
        }
        .padding(12)
        .frame(height: contentHeight)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    // MARK: - Quadrant 4: Galileo I/NAV Subframe Cards

    private func galileoInavCard(contentHeight: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "lock.shield.fill")
                    .foregroundColor(.cyan)
                Text("Galileo I/NAV Subframes (\(viewModel.messages.count))")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                Spacer()
                if !viewModel.messages.isEmpty {
                    Button("Clear") {
                        viewModel.clearMessages()
                    }
                    .font(.caption2)
                    .foregroundColor(.red)
                    .buttonStyle(.plain)
                }
            }

            if viewModel.messages.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "lock.shield")
                        .font(.system(size: 30))
                        .foregroundColor(.cyan)
                        .padding(.top, 24)
                    Text("Waiting for 250-bit I/NAV subframes...")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.gray.opacity(0.05))
                .cornerRadius(10)
            } else {
                ScrollView {
                    LazyVStack(spacing: 6) {
                        ForEach(viewModel.messages.reversed()) { msg in
                            INavMessageCard(message: msg)
                        }
                    }
                    .padding(4)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.gray.opacity(0.05))
                .cornerRadius(10)
            }
        }
        .padding(12)
        .frame(height: contentHeight)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    // MARK: - Helper Formatting Methods

    private func snrColor(_ cno: Int) -> Color {
        if cno >= 49 && viewModel.simulatedThreatMode == .spoofing { return .orange }
        if cno >= 35 { return .green }
        if cno >= 25 { return .yellow }
        return .red
    }

    private func secondarySnrColor(_ cno: Int) -> Color {
        if cno >= 49 && viewModel.simulatedThreatMode == .spoofing { return .pink }
        if cno >= 35 { return .purple }
        if cno >= 25 { return .indigo }
        return .red.opacity(0.85)
    }
}
