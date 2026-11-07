import SwiftUI
import MapKit

struct MapLocationItem: Identifiable {
    let id = UUID()
    let coordinate: CLLocationCoordinate2D
}

struct MiniMapView: View {
    let coordinate: CLLocationCoordinate2D

    @State private var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
        span: MKCoordinateSpan(latitudeDelta: 0.008, longitudeDelta: 0.008)
    )

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "map.fill")
                    .foregroundColor(.cyan)
                Text("Geospatial Position Map")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                Spacer()
                Text("DISPLAYED POSITION")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.cyan)
            }

            Map(coordinateRegion: $region, annotationItems: [MapLocationItem(coordinate: coordinate)]) { item in
                MapMarker(coordinate: item.coordinate, tint: .cyan)
            }
            .frame(height: 160)
            .cornerRadius(12)
        }
        .padding(12)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(14)
        .onAppear {
            region.center = coordinate
        }
        .onChange(of: coordinate.latitude) { _ in
            region.center = coordinate
        }
    }
}
