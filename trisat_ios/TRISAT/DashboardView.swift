import SwiftUI
import CoreLocation

struct DashboardView: View {
    @ObservedObject var viewModel: GnssViewModel
    @Environment(\.horizontalSizeClass) var horizontalSizeClass
    @State private var isCopied: Bool = false

    private var isWideLayout: Bool {
        #if os(macOS)
        return true
        #else
        return horizontalSizeClass == .regular
        #endif
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                // Compact Desktop Header Banner
                topHeaderBanner

                if isWideLayout {
                    // macOS & iPad 2-Column Side-by-Side Layout Fitted to Screen
                    HStack(alignment: .top, spacing: 14) {
                        // Left Column: Skyplot, Constellation Filters, & Constellation Matrix
                        VStack(spacing: 12) {
                            skyPlotSection(height: 250)
                            constellationSummaryGridSection
                        }
                        .frame(maxWidth: .infinity)

                        // Right Column: Position Telemetry, DOP Geometry, & Geospatial Map
                        VStack(spacing: 12) {
                            positionTelemetrySection
                            dopGeometrySection
                            MiniMapView(coordinate: viewModel.currentCoordinate)
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .padding(.horizontal, 16)
                } else {
                    // Compact 1-Column Vertical Layout
                    VStack(spacing: 14) {
                        skyPlotSection(height: 220)
                        positionTelemetrySection
                        constellationSummaryGridSection
                        dopGeometrySection
                        MiniMapView(coordinate: viewModel.currentCoordinate)
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.bottom, 16)
        }
        .onAppear { viewModel.start() }
    }

    // MARK: - Top Compact Banner

    private var topHeaderBanner: some View {
        Group {
            if isWideLayout {
                // macOS & iPad: Wide Single-Row Banner
                HStack(spacing: 14) {
                    Image("AppLogo")
                        .resizable()
                        .scaledToFit()
                        .frame(height: 52)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("TRISAT — Multi-Constellation GNSS & Security Suite")
                            .font(.headline)
                            .fontWeight(.bold)
                        Text("Galileo OSNMA v1.1 • E6 HAS-UA v2.0 • 4-Constellation Skyplot & CelesTrak SGP4")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    // Quick Mode & Threat Status Pills
                    headerPills
                }
            } else {
                // iPhone: Clean 2-Row Vertical Layout (Prevents title squishing)
                VStack(alignment: .leading, spacing: 8) {
                    // Line 1: Logo on the left, Mode & Threat pills on the right
                    HStack {
                        Image("AppLogo")
                            .resizable()
                            .scaledToFit()
                            .frame(height: 38)

                        Spacer()

                        headerPills
                    }

                    // Line 2: Full-width Title & Subtitle
                    VStack(alignment: .leading, spacing: 2) {
                        Text("TRISAT — Multi-Constellation GNSS & Security Suite")
                            .font(.subheadline)
                            .fontWeight(.bold)
                            .fixedSize(horizontal: false, vertical: true)

                        Text("Galileo OSNMA v1.1 • E6 HAS-UA v2.0 • 4-Constellation SGP4")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(12)
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }

    private var headerPills: some View {
        HStack(spacing: 6) {
            Text(modeBadgeTitle)
                .font(.system(size: 9.5, weight: .bold))
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.cyan.opacity(0.18))
                .foregroundColor(.cyan)
                .cornerRadius(6)

            if viewModel.simulatedThreatMode != .nominal {
                Text(viewModel.simulatedThreatMode.badgeText)
                    .font(.system(size: 9.5, weight: .bold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.red.opacity(0.22))
                    .foregroundColor(.red)
                    .cornerRadius(6)
            }
        }
    }

    private var modeBadgeTitle: String {
        switch viewModel.selectedMode {
        case 0: return "DEVICE + PREDICTED SKY"
        case 1: return "EXTERNAL TELEMETRY"
        case 2: return "UDP / SIMULATOR"
        default: return "MODE: ACTIVE"
        }
    }

    // MARK: - Component Sections

    private func skyPlotSection(height: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "globe.americas.fill")
                    .foregroundColor(.cyan)
                Text("Open Sky Satellite View")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(viewModel.skySourceLabel)
                    .font(.caption2)
                    .fontWeight(.bold)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.green.opacity(0.2))
                    .foregroundColor(.green)
                    .cornerRadius(6)
            }

            // Constellation Filter Toggles with SF Symbol Icons
            HStack(spacing: 6) {
                FilterToggleChip(title: "Galileo", iconName: "globe.europe.africa.fill", isSelected: $viewModel.isGalileoEnabled, color: .cyan)
                FilterToggleChip(title: "GPS", iconName: "location.north.line.fill", isSelected: $viewModel.isGpsEnabled, color: .orange)
                FilterToggleChip(title: "GLONASS", iconName: "antenna.radiowaves.left.and.right", isSelected: $viewModel.isGlonassEnabled, color: .red)
                FilterToggleChip(title: "BeiDou", iconName: "star.fill", isSelected: $viewModel.isBeidouEnabled, color: .green)
            }

            // TLE Simulation 24h Time Scrubbing Slider (Mode 2)
            if viewModel.selectedMode == 2 {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Orbit Propagation Offset:")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(String(format: "%+.1f h (±12h)", viewModel.timeOffsetHours))
                            .font(.caption2)
                            .fontWeight(.bold)
                            .foregroundColor(.cyan)
                    }
                    
                    Slider(value: $viewModel.timeOffsetHours, in: -12.0...12.0, step: 0.5) { _ in
                        viewModel.updateSatellites()
                    }
                }
                .padding(.vertical, 4)
                .padding(.horizontal, 8)
                .background(Color.cyan.opacity(0.1))
                .cornerRadius(8)
            }

            SkyPlotView(satellites: viewModel.displayedSatellites, height: height)
                .padding(.vertical, 2)
        }
        .padding(12)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    private var positionTelemetrySection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "location.fill")
                    .foregroundColor(.blue)
                Text("Position & Telemetry")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(isCopied ? "COPIED!" : "3D FIX (\(viewModel.numSatellitesInFix) SVs)")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(isCopied ? Color.green.opacity(0.2) : Color.blue.opacity(0.2))
                    .foregroundColor(isCopied ? .green : .blue)
                    .cornerRadius(6)
            }

            Text(viewModel.locationText)
                .font(.system(.body, design: .monospaced))
                .fontWeight(.semibold)

            Text(viewModel.accuracyText)
                .font(.caption)
                .foregroundColor(.gray)
                .lineLimit(1)

            HStack(spacing: 10) {
                Button(action: {
                    let lat = viewModel.currentCoordinate.latitude
                    let lon = viewModel.currentCoordinate.longitude
                    let coordStr = String(format: "%.6f, %.6f", lat, lon)
                    #if os(iOS)
                    UIPasteboard.general.string = coordStr
                    #elseif os(macOS)
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(coordStr, forType: .string)
                    #endif
                    isCopied = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                        isCopied = false
                    }
                }) {
                    HStack {
                        Image(systemName: "doc.on.doc")
                        Text("Copy Coords")
                    }
                    .font(.caption.weight(.bold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
                
                Button(action: {
                    let lat = viewModel.currentCoordinate.latitude
                    let lon = viewModel.currentCoordinate.longitude
                    if let url = URL(string: "https://maps.apple.com/?q=\(lat),\(lon)&ll=\(lat),\(lon)") {
                        #if os(iOS)
                        UIApplication.shared.open(url)
                        #elseif os(macOS)
                        NSWorkspace.shared.open(url)
                        #endif
                    }
                }) {
                    HStack {
                        Image(systemName: "map")
                        Text("Apple Maps")
                    }
                    .font(.caption.weight(.bold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                    .background(Color.gray.opacity(0.2))
                    .foregroundColor(.primary)
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.gray.opacity(0.12))
        .cornerRadius(14)
    }

    // MARK: - Constellation & DOP Feature Cards

    private var constellationSummaryGridSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundColor(.cyan)
                Text("Constellation Signal Matrix")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text("4 NETWORKS")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                let galSats = viewModel.displayedSatellites.filter { $0.constellation == .galileo }
                let gpsSats = viewModel.displayedSatellites.filter { $0.constellation == .gps }
                let gloSats = viewModel.displayedSatellites.filter { $0.constellation == .glonass }
                let bdsSats = viewModel.displayedSatellites.filter { $0.constellation == .beidou }

                ConstellationStatTile(
                    name: "Galileo",
                    count: galSats.count,
                    dualCount: galSats.filter { $0.isDualFrequency }.count,
                    avgCno: viewModel.averageCno(for: .galileo),
                    color: .cyan
                )
                ConstellationStatTile(
                    name: "GPS",
                    count: gpsSats.count,
                    dualCount: gpsSats.filter { $0.isDualFrequency }.count,
                    avgCno: viewModel.averageCno(for: .gps),
                    color: .orange
                )
                ConstellationStatTile(
                    name: "GLONASS",
                    count: gloSats.count,
                    dualCount: gloSats.filter { $0.isDualFrequency }.count,
                    avgCno: viewModel.averageCno(for: .glonass),
                    color: .red
                )
                ConstellationStatTile(
                    name: "BeiDou",
                    count: bdsSats.count,
                    dualCount: bdsSats.filter { $0.isDualFrequency }.count,
                    avgCno: viewModel.averageCno(for: .beidou),
                    color: .green
                )
            }
        }
        .padding(12)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    private var dopGeometrySection: some View {
        let isDegraded = viewModel.simulatedThreatMode == .jamming || viewModel.simulatedThreatMode == .spoofing
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "scope")
                    .foregroundColor(isDegraded ? .orange : .blue)
                Text("DOP Geometry Quality")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(isDegraded ? "DEGRADED GEOMETRY" : "EXCELLENT 3D")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background((isDegraded ? Color.orange : Color.blue).opacity(0.2))
                    .foregroundColor(isDegraded ? .orange : .blue)
                    .cornerRadius(6)
            }

            HStack(spacing: 10) {
                DopMetricTile(label: "HDOP", value: viewModel.hdopValue, sub: "Horizontal")
                DopMetricTile(label: "VDOP", value: viewModel.vdopValue, sub: "Vertical")
                DopMetricTile(label: "PDOP", value: viewModel.pdopValue, sub: "3D Position")
            }
        }
        .padding(12)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(14)
    }
}

struct FilterToggleChip: View {
    let title: String
    let iconName: String
    @Binding var isSelected: Bool
    let color: Color

    var body: some View {
        Button(action: { isSelected.toggle() }) {
            HStack(spacing: 4) {
                Image(systemName: iconName)
                    .font(.system(size: 10, weight: .bold))
                Text(title)
                    .font(.system(size: 11, weight: .bold))
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 4)
            .padding(.vertical, 6)
            .background(isSelected ? color.opacity(0.25) : Color.gray.opacity(0.15))
            .foregroundColor(isSelected ? color : Color.gray)
            .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }
}

struct ConstellationStatTile: View {
    let name: String
    let count: Int
    var dualCount: Int = 0
    let avgCno: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Circle()
                    .fill(color)
                    .frame(width: 8, height: 8)
                Text(name)
                    .font(.caption)
                    .fontWeight(.bold)
                Spacer()
                Text("\(count) SVs")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(color)
            }
            HStack {
                Text("Avg: \(avgCno)")
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
                Spacer()
                if dualCount > 0 {
                    Text("\(dualCount) 2F")
                        .font(.system(size: 8.5, weight: .black))
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(color.opacity(0.25))
                        .foregroundColor(color)
                        .cornerRadius(4)
                }
            }
        }
        .padding(8)
        .background(color.opacity(0.12))
        .cornerRadius(10)
    }
}

struct DopMetricTile: View {
    let label: String
    let value: String
    let sub: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption2)
                .fontWeight(.bold)
                .foregroundColor(.secondary)
            Text(value)
                .font(.system(.subheadline, design: .monospaced))
                .fontWeight(.bold)
            Text(sub)
                .font(.system(size: 9))
                .foregroundColor(.gray)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(8)
        .background(Color.gray.opacity(0.12))
        .cornerRadius(8)
    }
}
