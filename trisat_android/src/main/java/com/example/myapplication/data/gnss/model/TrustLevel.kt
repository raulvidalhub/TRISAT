package com.example.myapplication.data.gnss.model

enum class TrustLevel(
    val displayName: String,
    val description: String,
    val minScore: Float,
    val maxScore: Float
) {
    HIGH_TRUST(
        displayName = "HIGH TRUST",
        description = "The GNSS diagnostic score is in the high range.",
        minScore = 80.0f,
        maxScore = 100.0f
    ),
    MEDIUM_TRUST(
        displayName = "MEDIUM TRUST",
        description = "The GNSS diagnostic score is in the medium range.",
        minScore = 50.0f,
        maxScore = 79.99f
    ),
    LOW_TRUST(
        displayName = "LOW TRUST",
        description = "The GNSS diagnostic score is in the low range. Review the measurements and alerts.",
        minScore = 0.0f,
        maxScore = 49.99f
    );

    companion object {
        fun fromScore(score: Float): TrustLevel {
            return when {
                score >= 80.0f -> HIGH_TRUST
                score >= 50.0f -> MEDIUM_TRUST
                else -> LOW_TRUST
            }
        }
    }
}
