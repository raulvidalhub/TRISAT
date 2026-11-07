import SwiftUI
import CoreLocation

struct DashboardView: View {
    @ObservedObject var viewModel: GnssViewModel
    @Environment(\.horizontalSizeClass) var horizontalSizeClass
    @State private var isCopied: Bool = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                // Header Banner Logo
                HStack {
                    Spacer()
                    Image("AppLogo")
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: horizontalSizeClass == .regular ? 420 : .infinity)
                    Spacer()
                }
                .padding(.horizontal)
                .padding(.top, 8)

                if horizontalSizeClass == .regular {
                    // iPad 2-Column Side-by-Side Layout
                    HStack(alignment: .top, spacing: 18) {
                        // Left Column: Skyplot, Filters, & Constellation Stats Grid
                        VStack(spacing: 16) {
                            skyPlotSection(height: 320)
                            constellationSummaryGridSection
                        }
                        .frame(maxWidth: .infinity)

                        // Right Column: Telemetry, DOP Geometry, & MiniMap
                        VStack(spacing: 16) {
                            positionTelemetrySection
                            dopGeometrySection
                            MiniMapView(coordinate: viewModel.currentCoordinate)
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .padding(.horizontal)
                } else {
                    // iPhone 1-Column Vertical Layout
                    VStack(spacing: 16) {
                        skyPlotSection(height: 220)
                        positionTelemetrySection
                        constellationSummaryGridSection
                        dopGeometrySection
                        MiniMapView(coordinate: viewModel.currentCoordinate)
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.bottom, 24)
        }
        .onAppear { viewModel.start() }
    }

    // MARK: - Component Sections

    private func skyPlotSection(height: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 10) {
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
            HStack(spacing: 8) {
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
                        Text(String(format: "%.1f h (±12h)", viewModel.timeOffsetHours))
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
                .padding(.vertical, 4)
        }
        .padding()
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    private var positionTelemetrySection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "location.fill")
                    .foregroundColor(.blue)
                Text("Position & Telemetry")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(isCopied ? "COPIED!" : "DISPLAYED POSITION")
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
                    .font(.caption)
                    .fontWeight(.bold)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(8)
                }
                
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
                    .font(.caption)
                    .fontWeight(.bold)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(Color.gray.opacity(0.2))
                    .foregroundColor(.primary)
                    .cornerRadius(8)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.gray.opacity(0.12))
        .cornerRadius(14)
    }

    // MARK: - iPad High-Value Feature Cards

    private var constellationSummaryGridSection: some View {
        VStack(alignment: .leading, spacing: 10) {
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

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                ConstellationStatTile(name: "Galileo", count: viewModel.displayedSatellites.filter { $0.constellation == .galileo }.count, avgCno: "41.5 dB-Hz", color: .cyan)
                ConstellationStatTile(name: "GPS", count: viewModel.displayedSatellites.filter { $0.constellation == .gps }.count, avgCno: "39.2 dB-Hz", color: .orange)
                ConstellationStatTile(name: "GLONASS", count: viewModel.displayedSatellites.filter { $0.constellation == .glonass }.count, avgCno: "36.8 dB-Hz", color: .red)
                ConstellationStatTile(name: "BeiDou", count: viewModel.displayedSatellites.filter { $0.constellation == .beidou }.count, avgCno: "38.0 dB-Hz", color: .green)
            }
        }
        .padding()
        .background(Color.gray.opacity(0.08))
        .cornerRadius(14)
    }

    private var dopGeometrySection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "scope")
                    .foregroundColor(.blue)
                Text("DOP Geometry Quality")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text("EXCELLENT 3D")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.blue.opacity(0.2))
                    .foregroundColor(.blue)
                    .cornerRadius(6)
            }

            HStack(spacing: 12) {
                DopMetricTile(label: "HDOP", value: "0.85", sub: "Horizontal")
                DopMetricTile(label: "VDOP", value: "1.10", sub: "Vertical")
                DopMetricTile(label: "PDOP", value: "1.38", sub: "3D Position")
            }
        }
        .padding()
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
                    .font(.caption2)
                    .fontWeight(.bold)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(isSelected ? color.opacity(0.25) : Color.gray.opacity(0.15))
            .foregroundColor(isSelected ? color : Color.gray)
            .cornerRadius(6)
        }
    }
}

struct ConstellationStatTile: View {
    let name: String
    let count: Int
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
            Text("Avg C/N0: \(avgCno)")
                .font(.system(size: 10))
                .foregroundColor(.secondary)
        }
        .padding(10)
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
