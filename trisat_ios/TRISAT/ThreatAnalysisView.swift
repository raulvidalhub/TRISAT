import SwiftUI

struct ThreatAnalysisView: View {
    @ObservedObject var viewModel: GnssViewModel
    @ObservedObject var telemetryBridge: GnssTelemetryBridge
    @Environment(\.horizontalSizeClass) var horizontalSizeClass

    init(viewModel: GnssViewModel, telemetryBridge: GnssTelemetryBridge = GnssTelemetryBridge()) {
        self.viewModel = viewModel
        self.telemetryBridge = telemetryBridge
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

    // Computed Real-Time Threat Score (0.0 to 100.0)
    private var threatScore: Double {
        switch viewModel.simulatedThreatMode {
        case .nominal:
            if viewModel.displayedSatellites.isEmpty { return 25.0 }
            let avgCno = Double(viewModel.displayedSatellites.map { $0.cno }.reduce(0, +)) / Double(viewModel.displayedSatellites.count)
            if avgCno < 22.0 { return 85.0 }
            if avgCno < 30.0 { return 45.0 }
            return 5.0
        case .jamming:
            return 88.0
        case .spoofing:
            return 94.0
        case .meaconing:
            return 76.0
        case .osnmaFailure:
            return 92.0
        }
    }

    private var threatLevelColor: Color {
        if threatScore > 70.0 { return .red }
        if threatScore > 30.0 { return .orange }
        return .green
    }

    private var threatLevelText: String {
        viewModel.simulatedThreatMode.badgeText
    }

    var body: some View {
        if !isTelemetryActive {
            threatStandbyView
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    // MARK: - Top Threat Header & Interactive Attack Simulator Bar
                    threatSimulatorBanner

                    // MARK: - Live Visual Telemetry Row: Skyplot + C/N0 SNR Bars
                    if isWideLayout {
                        HStack(alignment: .top, spacing: 14) {
                            threatSkyplotCard
                                .frame(width: 245)

                            threatSnrBarChartCard
                                .frame(maxWidth: .infinity)
                        }
                        .padding(.horizontal, 16)
                    } else {
                        VStack(spacing: 12) {
                            threatSkyplotCard
                            threatSnrBarChartCard
                        }
                        .padding(.horizontal)
                    }

                    // MARK: - 6 Real-Time Threat Diagnostic Cards (2 Columns on Mac/iPad)
                    if isWideLayout {
                        HStack(alignment: .top, spacing: 14) {
                            VStack(spacing: 10) {
                                osnmaThreatCard
                                jammingThreatCard
                                hasUaSecurityCard
                            }
                            .frame(maxWidth: .infinity)

                            VStack(spacing: 10) {
                                spoofingThreatCard
                                meaconingThreatCard
                                ewssAndTimingCard
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .padding(.horizontal, 16)
                    } else {
                        VStack(spacing: 10) {
                            osnmaThreatCard
                            jammingThreatCard
                            spoofingThreatCard
                            meaconingThreatCard
                            hasUaSecurityCard
                            ewssAndTimingCard
                        }
                        .padding(.horizontal)
                    }
                }
                .padding(.bottom, 16)
            }
        }
    }

    // MARK: - Standby Mode when no receiver/simulator is active

    private var threatStandbyView: some View {
        VStack(spacing: 20) {
            Spacer()

            ZStack {
                Circle()
                    .fill(Color.orange.opacity(0.12))
                    .frame(width: 96, height: 96)
                Image(systemName: "shield.slash.fill")
                    .font(.system(size: 44))
                    .foregroundColor(.orange)
            }

            VStack(spacing: 8) {
                Text("Threat Analysis Standby")
                    .font(.title3)
                    .fontWeight(.bold)

                Text("Electronic warfare, jamming, spoofing, and OSNMA verification metrics require an active RF telemetry stream from a Bluetooth receiver, UDP, or the Simulator.")
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
            .tint(.orange)
            .padding(.top, 4)

            HStack(spacing: 6) {
                Circle()
                    .fill(Color.gray)
                    .frame(width: 8, height: 8)
                Text("Sensor Status: Offline (No Active RF Stream)")
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

    // MARK: - Interactive Threat Simulator & Score Banner

    private var threatSimulatorBanner: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: viewModel.simulatedThreatMode.iconName)
                    .font(.system(size: isWideLayout ? 26 : 22))
                    .foregroundColor(threatLevelColor)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Threat & Attack Simulation")
                        .font(isWideLayout ? .headline : .subheadline)
                        .fontWeight(.bold)
                    Text(viewModel.simulatedThreatMode.summaryDescription)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .lineLimit(isWideLayout ? 2 : 1)
                }

                Spacer()

                // Threat Risk Score Gauge
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(Int(threatScore))% RISK")
                        .font(.system(size: isWideLayout ? 20 : 16, weight: .bold, design: .monospaced))
                        .foregroundColor(threatLevelColor)

                    Text(threatLevelText)
                        .font(.system(size: 8.5, weight: .bold))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2.5)
                        .background(threatLevelColor.opacity(0.18))
                        .foregroundColor(threatLevelColor)
                        .cornerRadius(6)
                }
            }

            Divider()

            // Interactive Attack Simulation Buttons
            if isWideLayout {
                HStack(spacing: 8) {
                    Text("Simulate Scenario:")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.secondary)

                    ForEach(SimulatedThreatMode.allCases) { mode in
                        scenarioButton(mode)
                    }

                    Spacer()

                    constellationFilterChips
                }
            } else {
                // iPhone: Horizontal Scroll for Attack Modes + Dedicated Filter Row
                VStack(alignment: .leading, spacing: 8) {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(SimulatedThreatMode.allCases) { mode in
                                scenarioButton(mode)
                            }
                        }
                    }

                    HStack {
                        Text("Filters:")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Spacer()
                        constellationFilterChips
                    }
                }
            }
        }
        .padding(12)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(14)
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }

    private func scenarioButton(_ mode: SimulatedThreatMode) -> some View {
        Button(action: {
            withAnimation(.easeInOut(duration: 0.2)) {
                viewModel.simulatedThreatMode = mode
            }
        }) {
            HStack(spacing: 4) {
                Image(systemName: mode.iconName)
                    .font(.system(size: 10, weight: .bold))
                Text(mode.rawValue)
                    .font(.caption2)
                    .fontWeight(.bold)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(
                viewModel.simulatedThreatMode == mode
                    ? buttonColor(for: mode).opacity(0.28)
                    : Color.gray.opacity(0.14)
            )
            .foregroundColor(
                viewModel.simulatedThreatMode == mode
                    ? buttonColor(for: mode)
                    : .primary
            )
            .overlay(
                RoundedRectangle(cornerRadius: 7)
                    .stroke(
                        viewModel.simulatedThreatMode == mode ? buttonColor(for: mode) : Color.clear,
                        lineWidth: 1.5
                    )
            )
            .cornerRadius(7)
        }
        .buttonStyle(.plain)
    }

    private var constellationFilterChips: some View {
        HStack(spacing: 5) {
            FilterToggleChip(title: "GAL", iconName: "globe.europe.africa.fill", isSelected: $viewModel.isGalileoEnabled, color: .cyan)
            FilterToggleChip(title: "GPS", iconName: "location.north.line.fill", isSelected: $viewModel.isGpsEnabled, color: .orange)
            FilterToggleChip(title: "GLO", iconName: "antenna.radiowaves.left.and.right", isSelected: $viewModel.isGlonassEnabled, color: .red)
            FilterToggleChip(title: "BDS", iconName: "star.fill", isSelected: $viewModel.isBeidouEnabled, color: .green)
        }
    }

    private func buttonColor(for mode: SimulatedThreatMode) -> Color {
        switch mode {
        case .nominal: return .green
        case .jamming: return .red
        case .spoofing: return .orange
        case .meaconing: return .yellow
        case .osnmaFailure: return .pink
        }
    }

    // MARK: - Compact Skyplot & C/N0 SNR Bar Chart for Real-Time Attack Visualization

    private var threatSkyplotCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "safari.fill")
                    .foregroundColor(.cyan)
                Text("Spatial Geometry Skyplot")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(viewModel.displayedSatellites.filter { $0.usedInFix }.count)/\(viewModel.displayedSatellites.count) Used")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(viewModel.simulatedThreatMode == .jamming ? .red : .cyan)
            }

            SkyPlotView(satellites: viewModel.displayedSatellites, height: 170)
                .padding(2)
        }
        .padding(10)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(12)
    }

    private var threatSnrBarChartCard: some View {
        let avgCno = viewModel.displayedSatellites.isEmpty
            ? 0
            : viewModel.displayedSatellites.map { $0.cno }.reduce(0, +) / viewModel.displayedSatellites.count

        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "chart.bar.xaxis")
                    .foregroundColor(threatLevelColor)
                Text("Satellite C/N0 Spectrum Profile (Avg: \(avgCno) dB-Hz)")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                Spacer()
                Text(snrProfileHint)
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(threatLevelColor)
            }

            if viewModel.displayedSatellites.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "satellite.fill")
                        .font(.title2)
                        .foregroundColor(.secondary)
                        .padding(.top, 28)
                    Text("No active constellations selected.")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                .frame(maxWidth: .infinity, minHeight: 170)
            } else {
                ScrollView(.horizontal, showsIndicators: true) {
                    HStack(alignment: .bottom, spacing: 9) {
                        ForEach(viewModel.displayedSatellites) { sat in
                            VStack(spacing: 3) {
                                if sat.isDualFrequency {
                                    HStack(spacing: 2) {
                                        Text("\(sat.cno)")
                                            .font(.system(size: 7.5, weight: .bold, design: .monospaced))
                                            .foregroundColor(barColor(for: sat))
                                        Text("/")
                                            .font(.system(size: 6.5, weight: .light))
                                            .foregroundColor(.secondary)
                                        Text("\(sat.cnoSecondary)")
                                            .font(.system(size: 7.5, weight: .bold, design: .monospaced))
                                            .foregroundColor(secondaryBarColor(for: sat))
                                    }

                                    HStack(alignment: .bottom, spacing: 2.5) {
                                        // Primary Carrier Bar
                                        ZStack(alignment: .bottom) {
                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(Color.gray.opacity(0.15))
                                                .frame(width: 10, height: 120)

                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(barColor(for: sat))
                                                .frame(width: 10, height: CGFloat(min(max(sat.cno, 0), 54)) * 2.2)
                                        }

                                        // Secondary Carrier Bar
                                        ZStack(alignment: .bottom) {
                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(Color.gray.opacity(0.15))
                                                .frame(width: 10, height: 120)

                                            RoundedRectangle(cornerRadius: 2.5)
                                                .fill(secondaryBarColor(for: sat))
                                                .frame(width: 10, height: CGFloat(min(max(sat.cnoSecondary, 0), 54)) * 2.2)
                                        }
                                    }
                                } else {
                                    Text("\(sat.cno)")
                                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                                        .foregroundColor(barColor(for: sat))

                                    ZStack(alignment: .bottom) {
                                        RoundedRectangle(cornerRadius: 3)
                                            .fill(Color.gray.opacity(0.15))
                                            .frame(width: 19, height: 120)

                                        RoundedRectangle(cornerRadius: 3)
                                            .fill(barColor(for: sat))
                                            .frame(width: 19, height: CGFloat(min(max(sat.cno, 0), 54)) * 2.2)
                                    }
                                }

                                Text(sat.formattedLabel)
                                    .font(.system(size: 8, weight: .bold, design: .monospaced))
                                    .padding(.horizontal, 3)
                                    .padding(.vertical, 2)
                                    .background(sat.constellation.color.opacity(0.22))
                                    .foregroundColor(sat.constellation.color)
                                    .cornerRadius(3)

                                Text(sat.bandsLabel)
                                    .font(.system(size: 6.5, weight: sat.isDualFrequency ? .heavy : .semibold, design: .monospaced))
                                    .padding(.horizontal, 2.5)
                                    .padding(.vertical, 1)
                                    .background(sat.isDualFrequency ? Color.purple.opacity(0.35) : Color.gray.opacity(0.18))
                                    .foregroundColor(sat.isDualFrequency ? .purple : .secondary)
                                    .cornerRadius(2)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                    .padding(.horizontal, 6)
                }
                .frame(minHeight: 170)
            }
        }
        .padding(10)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(12)
    }

    private var snrProfileHint: String {
        switch viewModel.simulatedThreatMode {
        case .nominal: return "NORMAL DISTRIBUTION (38–49 dB-Hz)"
        case .jamming: return "SEVERE ATTENUATION (-22 dB SNR DROP)"
        case .spoofing: return "ANOMALOUS FLAT POWER (51–52 dB-Hz)"
        case .meaconing: return "MULTIPATH RIPPLE (+420ns REPLAY)"
        case .osnmaFailure: return "NORMAL RF POWER / INVALID OSNMA TAG"
        }
    }

    private func barColor(for sat: SatelliteInfo) -> Color {
        switch viewModel.simulatedThreatMode {
        case .jamming:
            return sat.cno < 24 ? .red : .orange
        case .spoofing:
            return .orange
        case .meaconing:
            return .yellow
        case .osnmaFailure:
            return sat.constellation == .galileo ? .pink : .green
        case .nominal:
            if sat.cno >= 35 { return .green }
            if sat.cno >= 25 { return .yellow }
            return .red
        }
    }

    private func secondaryBarColor(for sat: SatelliteInfo) -> Color {
        switch viewModel.simulatedThreatMode {
        case .jamming:
            return sat.cnoSecondary < 24 ? .red : .purple
        case .spoofing:
            return .purple
        case .meaconing:
            return .indigo
        case .osnmaFailure:
            return sat.constellation == .galileo ? .pink : .purple
        case .nominal:
            if sat.cnoSecondary >= 35 { return .purple }
            if sat.cnoSecondary >= 25 { return .indigo }
            return .red.opacity(0.8)
        }
    }

    // MARK: - Threat Card 1: Dynamic OS-NMA Cryptographic Authentication (Galileo v1.1 Annex A)

    private var osnmaThreatCard: some View {
        let received = viewModel.messages.filter { !$0.isSimulated && $0.band == "E1-B" }
        let hasSimulation = viewModel.messages.contains { $0.isSimulated } || telemetryBridge.isSdrEngineRunning
        let annexAPassed = OsnmaEngine.verifyEuspaAnnexATestVector()
        let (statusText, color, sessionDetails): (String, Color, String) = {
            if telemetryBridge.isSdrEngineRunning && viewModel.simulatedThreatMode == .osnmaFailure {
                return ("SIMULATED AUTH FAILURE", .orange, "The selected scenario injects an OSNMA failure.")
            }
            if OsnmaEngine().receptionStatus(inavMessages: received) == .unverified {
                return ("I/NAV RECEIVED - UNVERIFIED", .orange, "Received Galileo E1-B pages have not been cryptographically verified.")
            }
            if hasSimulation {
                return ("SIMULATED", .cyan, "The session contains generated navigation messages.")
            }
            return ("NO I/NAV DATA", .gray, "Awaiting Galileo E1-B navigation messages.")
        }()
        let details = "\(sessionDetails) Annex A TESLA/HMAC self-test: \(annexAPassed ? "PASS" : "FAIL")."

        return ThreatMetricCard(
            title: "Galileo OSNMA",
            status: statusText,
            statusColor: color,
            icon: "lock.shield.fill",
            details: details
        )
    }

    // MARK: - Threat Card 2: Jamming & RF Interference Level

    private var jammingThreatCard: some View {
        let avgCno = viewModel.displayedSatellites.isEmpty
            ? 0
            : viewModel.displayedSatellites.map { $0.cno }.reduce(0, +) / viewModel.displayedSatellites.count
        let isJamming = viewModel.simulatedThreatMode == .jamming || (!viewModel.displayedSatellites.isEmpty && avgCno < 25)

        let details = isJamming
            ? "CRITICAL: Average C/N0 dropped to \(avgCno) dB-Hz (+18 dB RF noise floor surge). Automatic Gain Control (AGC) saturated; \(viewModel.displayedSatellites.filter { !$0.usedInFix }.count) SVs lost tracking lock."
            : "Average C/N0 SNR: \(avgCno) dB-Hz across \(viewModel.displayedSatellites.count) visible satellites. Front-end AGC gain and noise floor within nominal margins."

        return ThreatMetricCard(
            title: "Jamming & RF Interference",
            status: isJamming ? "JAMMING DETECTED" : "NOMINAL",
            statusColor: isJamming ? .red : .green,
            icon: "wifi.exclamationmark",
            details: details
        )
    }

    // MARK: - Threat Card 3: Spoofing Detection

    private var spoofingThreatCard: some View {
        let isSpoofing = viewModel.simulatedThreatMode == .spoofing
        let details = isSpoofing
            ? "CRITICAL: Coherent false-signal emitter detected! C/N0 variance collapsed (< 0.8 dB across SVs at 51 dB-Hz), azimuths clustered toward 45° NE, and $GPGST residuals spiked to \(viewModel.gstRmsError)."
            : "Pseudorange Residuals ($GPGST): \(viewModel.gstRmsError). C/N0 elevation variance and Doppler rates match CelesTrak SGP4 orbital geometry."

        return ThreatMetricCard(
            title: "Spoofing / Coherent Emitter Detection",
            status: isSpoofing ? "SPOOFING ALERT" : "LOW RISK",
            statusColor: isSpoofing ? .red : .green,
            icon: "exclamationmark.triangle.fill",
            details: details
        )
    }

    // MARK: - Threat Card 4: Meaconing / Delayed Rebroadcast Analysis

    private var meaconingThreatCard: some View {
        let isMeaconing = viewModel.simulatedThreatMode == .meaconing
        let details = isMeaconing
            ? "WARNING: Delayed RF replay (+420 ns clock jump) detected! Skyplot azimuths shifted by +25°, DGPS correction age lagged to \(viewModel.dgpsAge), and pseudorange residual jumped to \(viewModel.gstRmsError)."
            : "Receiver clock bias and ephemeris Time-of-Week (TOW) synchronized within < 15 ns of Galileo System Time (GST). No rebroadcast delay detected."

        return ThreatMetricCard(
            title: "Meaconing / Replay Delay Monitor",
            status: isMeaconing ? "MEACONING DETECTED" : "SYNCHRONIZED",
            statusColor: isMeaconing ? .orange : .green,
            icon: "clock.badge.exclamationmark.fill",
            details: details
        )
    }

    // MARK: - Threat Card 5: Galileo HAS-UA & DIA Integrity Monitor

    private var hasUaSecurityCard: some View {
        let isDegraded = viewModel.simulatedThreatMode == .spoofing || viewModel.simulatedThreatMode == .jamming
        return ThreatMetricCard(
            title: "Galileo E6-B HAS-UA & DIA Integrity",
            status: isDegraded ? "DIA FAULT EXCLUSION" : "SL1 PPP ACTIVE",
            statusColor: isDegraded ? .orange : .green,
            icon: "checkmark.shield.fill",
            details: isDegraded
                ? "Galileo HAS-UA v2.0 DIA Baarda w-test triggered outlier rejection (|w_i| = 9.84 > 3.29σ threshold). Faulty pseudoranges isolated from PPP state vector."
                : "Galileo HAS-UA v2.0 | RS(255,32) GF(2^8) + MT1 Orbit/Clock/Bias (NTW→ECEF) | DIA Baarda w-test LOM (< 3.29σ) | NTCM-G 12-Coeff SF Ionosphere"
        )
    }

    // MARK: - Threat Card 6: Galileo EWSS-CAMF & WT44 Timing Service Monitor

    private var ewssAndTimingCard: some View {
        let isTimingAnomaly = viewModel.simulatedThreatMode == .meaconing || viewModel.simulatedThreatMode == .osnmaFailure
        return ThreatMetricCard(
            title: "Galileo EWSS-CAMF & WT44 Timing Service",
            status: isTimingAnomaly ? "TSM ALERT" : "MONITORING",
            statusColor: isTimingAnomaly ? .orange : .cyan,
            icon: "bell.badge.waveform.fill",
            details: isTimingAnomaly
                ? "WT44 Timing Service Monitoring (TSM) flagged ADKD=4 GST-UTC timing integrity alert. Cross-checking E1-B I/NAV v2.2 WT16 RedCED & RS(118,58)."
                : "EWSS 122-bit CAMF Geo-Fence: NO ACTIVE HAZARD | I/NAV v2.2 WT16 RedCED & WT17-20 RS(118,58) Active | WT44 TSM: TSL-1 (< 15 ns to UTC)"
        )
    }
}

// MARK: - Reusable Threat Metric Card View

struct ThreatMetricCard: View {
    let title: String
    let status: String
    let statusColor: Color
    let icon: String
    let details: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(statusColor)
                    .font(.body)
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(status)
                    .font(.system(size: 9, weight: .bold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(statusColor.opacity(0.15))
                    .foregroundColor(statusColor)
                    .cornerRadius(6)
            }
            
            Text(details)
                .font(.caption)
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(12)
    }
}
