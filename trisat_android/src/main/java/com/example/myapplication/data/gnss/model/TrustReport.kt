package com.example.myapplication.data.gnss.model

data class TrustReport(
    val overallScore: Float = 0f,
    val trustLevel: TrustLevel = TrustLevel.LOW_TRUST,
    val subScores: TrustSubScores = TrustSubScores(),
    val threatsDetected: List<ThreatType> = emptyList(),
    val activeThreatWarnings: List<String> = emptyList(),
    val estimatedHdop: Float = 1.2f,
    val estimatedVdop: Float = 1.6f,
    val osnmaStatus: OsnmaStatus = OsnmaStatus.NOT_AVAILABLE,
    val intelligenceLogs: List<IntelligenceLogEntry> = emptyList(),
    val timestampMillis: Long = System.currentTimeMillis(),
    val assessmentSource: TrustAssessmentSource? = null,
    val isReceiverDataStale: Boolean = false,
    internal val receiverInputsExpireAtElapsedMillis: Long? = null
) {
    val assessedTrustLevel: TrustLevel?
        get() = trustLevel.takeIf { assessmentSource != null && !isReceiverDataStale }

    val lastReceiverAssessmentMillis: Long?
        get() = timestampMillis.takeIf { assessmentSource == TrustAssessmentSource.RECEIVER }
}

enum class TrustAssessmentSource {
    RECEIVER,
    SIMULATION
}
