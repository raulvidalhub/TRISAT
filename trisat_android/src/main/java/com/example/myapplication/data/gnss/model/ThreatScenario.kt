package com.example.myapplication.data.gnss.model

enum class ThreatScenario(
    val displayName: String,
    val description: String
) {
    NOMINAL(
        displayName = "Nominal Open Sky",
        description = "Clean multi-constellation GNSS signals, valid OSNMA authentication, normal AGC."
    ),
    SPOOFING_SIMULATOR(
        displayName = "Spoofing Simulator Attack",
        description = "Uniform C/N0 power across channels, high power output, spoofing signatures."
    ),
    RF_JAMMING(
        displayName = "RF Jamming Attack",
        description = "Extreme AGC gain suppression (-16.5 dB), C/N0 signal degradation across bands."
    ),
    CLOCK_DRIFT_ATTACK(
        displayName = "Clock Drift & Manipulation",
        description = "Simulated drift near 385 ns/s and three clock discontinuities."
    ),
    OSNMA_FAILURE(
        displayName = "Galileo OSNMA Auth Failure",
        description = "Galileo cryptographic signature mismatch and authentication failure."
    )
}
