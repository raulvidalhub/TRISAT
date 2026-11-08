package com.example.myapplication.data.gnss.model

data class TrustReport(
    val overallScore: Float = 100f,
    val trustLevel: TrustLevel = TrustLevel.HIGH_TRUST,
    val subScores: TrustSubScores = TrustSubScores(),
    val threatsDetected: List<ThreatType> = emptyList(),
    val activeThreatWarnings: List<String> = emptyList(),
    val estimatedHdop: Float = 1.2f,
    val estimatedVdop: Float = 1.6f,
    val osnmaStatus: OsnmaStatus = OsnmaStatus.NOT_AVAILABLE,
    val intelligenceLogs: List<IntelligenceLogEntry> = emptyList(),
    val timestampMillis: Long = System.currentTimeMillis()
)
