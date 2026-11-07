package com.example.myapplication.data.gnss.model

enum class GnssReceiverMode(
    val id: Int,
    val title: String,
    val badge: String,
    val subtitle: String
) {
    INTERNAL_TLE(
        id = 0,
        title = "Internal + TLE",
        badge = "INTERNAL + TLE",
        subtitle = "Hardware GNSS HAL with automatic CelesTrak TLE orbit fallback"
    ),
    EXTERNAL_HARDWARE(
        id = 1,
        title = "External Receiver / UDP",
        badge = "EXTERNAL / UDP",
        subtitle = "Listen for NMEA telemetry from a local bridge on UDP port 9090"
    ),
    SIMULATION_TLE(
        id = 2,
        title = "Orbital Simulation & SDR Lab",
        badge = "TLE SIMULATION",
        subtitle = "Pure Keplerian SGP4 orbit simulation across 4 constellations with 24h scrubbing"
    );

    companion object {
        fun fromId(id: Int): GnssReceiverMode {
            return entries.find { it.id == id } ?: INTERNAL_TLE
        }
    }
}
