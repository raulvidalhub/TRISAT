import SwiftUI

/// Reusable card view to render each individual I/NAV frame with its hexadecimal payload
struct INavMessageCard: View {
    let message: GalileoINavMessage
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("SVID (PRN): Galileo E\(String(format: "%02d", message.svid))")
                    .font(.subheadline)
                    .fontWeight(.bold)
                Spacer()
                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Text("Submessage ID: \(message.submessageId) · \(message.band)")
                .font(.caption)
                .foregroundColor(.secondary)
            
            Text("Hex Payload (\(message.data.count) bytes):")
                .font(.caption2)
                .foregroundColor(.gray)
            
            Text(message.hexPayload)
                .font(.system(.caption2, design: .monospaced))
                .foregroundColor(.blue)
                .lineLimit(2)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.gray.opacity(0.08))
        .cornerRadius(8)
    }
}