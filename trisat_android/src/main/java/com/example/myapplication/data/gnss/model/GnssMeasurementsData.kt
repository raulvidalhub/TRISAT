package com.example.myapplication.data.gnss.model

data class GnssMeasurementsData(
    val clockTimeNanos: Long = 0L,
    val clockHardwareClockDiscontinuityCount: Int = 0,
    val fullBiasNanos: Long? = null,
    val biasNanos: Double? = null,
    val biasUncertaintyNanos: Double? = null,
    val driftNanosPerSecond: Double? = null,
    val driftUncertaintyNanosPerSecond: Double? = null,
    val measurements: List<GnssMeasurementDetail> = emptyList(),
    val isMock: Boolean = false,
    val timestampMillis: Long = System.currentTimeMillis(),
    val simulatedAgcDb: Double? = null
) {
    val hardwareClockDiscontinuityCount: Int
        get() = clockHardwareClockDiscontinuityCount

    internal val agcLevelsDb: List<Double>
        get() {
            if (isMock && simulatedAgcDb != null) return listOf(simulatedAgcDb)
            return measurements.filter { it.hasAgc }.map { it.automaticGainControlLevelDb }
        }

    val averageAgcDb: Double
        get() = agcLevelsDb.takeIf { it.isNotEmpty() }?.average() ?: 0.0
}
