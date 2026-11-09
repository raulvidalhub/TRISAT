import Foundation
import CoreLocation
import Combine

@MainActor
class GnssViewModel: ObservableObject {
    private let repository: GnssRepository
    let bluetoothManager: BluetoothManager
    let tleDownloader = TleDownloader()
    private var cancellables = Set<AnyCancellable>()
    
    @Published var locationText: String = "Searching coordinates..."
    @Published var accuracyText: String = "Acc: ±-- m"
    @Published var currentCoordinate: CLLocationCoordinate2D = CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194)
    @Published var messages: [GalileoINavMessage] = []

    // Mode: 0 = Internal + TLE, 1 = External BLE / USB Bridge, 2 = TLE Simulation
    @Published var selectedMode: Int = 1
    var externalSatellites: [SatelliteInfo] = []
    var skySourceLabel: String {
        selectedMode == 1 && !externalSatellites.isEmpty ? "EXTERNAL TELEMETRY" : "PREDICTED SKY"
    }
    @Published var timeOffsetHours: Double = 0.0

    // Constellation Filters
    @Published var isGalileoEnabled: Bool = true
    @Published var isGpsEnabled: Bool = true
    @Published var isGlonassEnabled: Bool = true
    @Published var isBeidouEnabled: Bool = true

    // Differential & NMEA Telemetry Metrics
    @Published var fixTypeDesc: String = "Autonomous GNSS"
    @Published var numSatellitesInFix: Int = 0
    @Published var hdopValue: String = "--"
    @Published var pdopValue: String = "--"
    @Published var vdopValue: String = "--"
    @Published var dgpsAge: String = "N/A"
    @Published var dgpsStationId: String = "N/A"
    @Published var gstRmsError: String = "N/A"
    @Published var gstLatLonErr: String = "N/A"

    // Computed Satellites for Skyplot & SNR Bar Chart
    @Published var displayedSatellites: [SatelliteInfo] = []

    // Persistent Anti-Flickering Satellite Store (Key: SatID, Value: (Info, LastSeenTimestamp))
    private var satelliteStore: [String: (info: SatelliteInfo, lastSeen: Date)] = [:]

    init(repository: GnssRepository = GnssRepository(), bluetoothManager: BluetoothManager = BluetoothManager()) {
        self.repository = repository
        self.bluetoothManager = bluetoothManager
        setupBindings()
    }
    
    func start() {
        repository.requestPermissions()
        updateSatellites()
    }
    
    func stop() {
        repository.stopLocationUpdates()
    }

    func clearMessages() {
        DispatchQueue.main.async {
            self.messages.removeAll()
            self.repository.clearMessages()
        }
    }

    func updateSatellites() {
        let coord = currentCoordinate

        let allSats: [SatelliteInfo]
        if selectedMode == 1 && !externalSatellites.isEmpty {
            allSats = externalSatellites
        } else if selectedMode == 2 {
            allSats = Sgp4OrbitPropagator.propagateToSkyplot(tles: tleDownloader.parsedTles, timeOffsetHours: timeOffsetHours, observerLocation: coord)
        } else {
            allSats = Sgp4OrbitPropagator.propagateToSkyplot(tles: tleDownloader.parsedTles, timeOffsetHours: 0.0, observerLocation: coord)
        }

        displayedSatellites = allSats.filter { sat in
            switch sat.constellation {
            case .galileo: return isGalileoEnabled
            case .gps: return isGpsEnabled
            case .glonass: return isGlonassEnabled
            case .beidou: return isBeidouEnabled
            }
        }
    }
    
    func handleInavMessage(_ message: GalileoINavMessage) {
        repository.appendRealInavMessage(message)
    }

    private func setupBindings() {
        repository.$lastLocation
            .compactMap { $0 }
            .receive(on: DispatchQueue.main)
            .sink { [weak self] loc in
                let lat = loc.coordinate.latitude
                let lon = loc.coordinate.longitude

                let latDir = lat >= 0 ? "N" : "S"
                let lonDir = lon >= 0 ? "E" : "W"

                if self?.selectedMode == 0 {
                    self?.currentCoordinate = loc.coordinate
                    self?.locationText = String(format: "%.6f° %@, %.6f° %@", abs(lat), latDir, abs(lon), lonDir)
                    self?.accuracyText = String(format: "Acc: ±%.1f m | Alt: %.1f m", loc.horizontalAccuracy, loc.altitude)
                    self?.updateSatellites()
                }
            }
            .store(in: &cancellables)
        
        repository.$capturedMessages
            .receive(on: DispatchQueue.main)
            .assign(to: &$messages)

        bluetoothManager.onInavFrameReceived = { [weak self] message in
            self?.handleInavMessage(message)
        }

        bluetoothManager.onNmeaLineReceived = { [weak self] line in
            guard let self = self else { return }

            // 1. Parse $GPGGA / $GNGGA (Coordinates, Fix Quality, DGPS Age, Station ID)
            if line.contains("$GPGGA") || line.contains("$GNGGA") {
                self.parseGgaSentence(line)
            }

            // 2. Parse $GPGST (Pseudorange Noise & RMS Error Statistics)
            if line.contains("$GPGST") || line.contains("$GNGST") {
                self.parseGstSentence(line)
            }

            // 3. Parse $GPGSA / $GNGSA (DOP Dilution of Precision)
            if line.contains("$GPGSA") || line.contains("$GNGSA") {
                self.parseGsaSentence(line)
            }

            // 4. Parse $GAGSV / $GPGSV / $GLGSV / $BDGSV (Satellites with Anti-Flicker)
            if line.contains("$GAGSV") || line.contains("$GPGSV") || line.contains("$GLGSV") || line.contains("$BDGSV") {
                self.parseGsvLine(line)
            }
        }

        Publishers.CombineLatest4($selectedMode, $timeOffsetHours, $isGalileoEnabled, $isGpsEnabled)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] mode, _, _, _ in
                if mode == 1 {
                    self?.repository.clearMessages()
                }
                self?.updateSatellites()
            }
            .store(in: &cancellables)

        Publishers.CombineLatest($isGlonassEnabled, $isBeidouEnabled)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in self?.updateSatellites() }
            .store(in: &cancellables)
    }

    private func parseGgaSentence(_ line: String) {
        guard let parts = F9pTelemetry.ggaFields(line) else { return }
        guard F9pTelemetry.measuredFix(parts[6]) else {
            fixTypeDesc = "No measured fix"
            numSatellitesInFix = 0
            hdopValue = "--"
            locationText = "Waiting for a measured fix"
            accuracyText = "No measured fix"
            return
        }

        if let lat = parseNmeaCoord(parts[2], dir: parts[3]),
           let lon = parseNmeaCoord(parts[4], dir: parts[5]) {
            let fixQuality = parts[6]
            let numSats = Int(parts[7]) ?? 0
            let hdop = parts[8]
            let alt = parts[9]

            self.numSatellitesInFix = numSats
            self.hdopValue = hdop.isEmpty ? "--" : hdop

            self.fixTypeDesc = {
                switch fixQuality {
                case "1": return "GPS Autonomous"
                case "2": return "DGPS Differential (SXblue)"
                case "4": return "RTK Fixed (Centimeter)"
                case "5": return "RTK Float"
                default: return "Fix Mode \(fixQuality)"
                }
            }()

            if parts.count >= 14 {
                let age = parts[11]
                let station = parts[12].components(separatedBy: "*")[0]
                self.dgpsAge = age.isEmpty ? "N/A" : "\(age)s"
                self.dgpsStationId = station.isEmpty ? "N/A" : station
            }

            self.currentCoordinate = CLLocationCoordinate2D(latitude: lat, longitude: lon)
            let latDir = lat >= 0 ? "N" : "S"
            let lonDir = lon >= 0 ? "E" : "W"
            self.locationText = String(format: "%.6f° %@, %.6f° %@", abs(lat), latDir, abs(lon), lonDir)
            self.accuracyText = "Fix: \(fixTypeDesc) | Sats: \(numSats) | HDOP: \(hdopValue) | Alt: \(alt)m"
        }
    }

    private func parseGstSentence(_ line: String) {
        let parts = line.components(separatedBy: ",")
        if parts.count >= 8 {
            let rms = parts[2]
            let latErr = parts[6]
            let lonErr = parts[7].components(separatedBy: "*")[0]

            if let rmsVal = Double(rms) {
                self.gstRmsError = String(format: "±%.2f m", rmsVal)
            }
            if let latE = Double(latErr), let lonE = Double(lonErr) {
                self.gstLatLonErr = String(format: "Lat ±%.2fm, Lon ±%.2fm", latE, lonE)
            }
        }
    }

    private func parseGsaSentence(_ line: String) {
        let parts = line.components(separatedBy: ",")
        if parts.count >= 17 {
            let pdop = parts[15]
            let hdop = parts[16]
            let vdop = parts.count >= 18 ? parts[17].components(separatedBy: "*")[0] : "--"

            self.pdopValue = pdop.isEmpty ? "--" : pdop
            self.hdopValue = hdop.isEmpty ? "--" : hdop
            self.vdopValue = vdop.isEmpty ? "--" : vdop
        }
    }

    private func parseGsvLine(_ text: String) {
        let parts = text.components(separatedBy: ",")
        guard parts.count >= 8 else { return }

        let constKind: GnssConstellation
        if text.contains("$GAGSV") { constKind = .galileo }
        else if text.contains("$GPGSV") { constKind = .gps }
        else if text.contains("$GLGSV") { constKind = .glonass }
        else { constKind = .beidou }

        let now = Date()
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
                let key = "\(constKind.rawValue)_\(svid)"
                let sat = SatelliteInfo(
                    id: key,
                    svid: svid,
                    elevation: elev,
                    azimuth: azim,
                    cno: cno,
                    isGalileo: constKind == .galileo,
                    constellation: constKind,
                    usedInFix: cno > 20,
                    hasInav: constKind == .galileo
                )
                satelliteStore[key] = (info: sat, lastSeen: now)
            }
            idx += 4
        }

        // Retain satellites for 30 seconds to prevent any screen flickering
        let activeThreshold = Date().addingTimeInterval(-30.0)
        satelliteStore = satelliteStore.filter { $0.value.lastSeen > activeThreshold }

        let activeSats = satelliteStore.values.map { $0.info }

        // Keep received satellites separate from the predicted sky.
        externalSatellites = activeSats.sorted {
            if $0.constellation != $1.constellation {
                return $0.constellation.rawValue < $1.constellation.rawValue
            }
            return $0.svid < $1.svid
        }
        updateSatellites()
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
