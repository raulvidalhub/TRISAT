package com.example.myapplication.data.gnss.model

enum class OsnmaStatus(
    val label: String,
    val description: String
) {
    VERIFIED(
        label = "VERIFIED",
        description = "Galileo E1B cryptographic navigation message signature authenticated via Root Key."
    ),
    UNAUTHENTICATED(
        label = "I/NAV RECEIVED - UNVERIFIED",
        description = "Galileo navigation data was received. Cryptographic verification is pending or unavailable."
    ),
    FAILED(
        label = "AUTH FAILED",
        description = "Galileo cryptographic signature verification failed - potential message tampering."
    ),
    SIMULATED(
        label = "SIMULATED",
        description = "OSNMA scenario from the simulator."
    ),
    SIMULATED_FAILURE(
        label = "SIMULATED AUTH FAILURE",
        description = "The selected scenario injects an OSNMA failure."
    ),
    NOT_AVAILABLE(
        label = "NO I/NAV DATA",
        description = "No Galileo I/NAV messages are available for OSNMA verification."
    )
}
