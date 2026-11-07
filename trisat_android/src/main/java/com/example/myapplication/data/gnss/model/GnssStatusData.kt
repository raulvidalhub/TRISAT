package com.example.myapplication.data.gnss.model

data class GnssStatusData(
    val satellites: List<SatelliteDetail> = emptyList(),
    val isMock: Boolean = false,
    val timestampMillis: Long = System.currentTimeMillis(),
    val receivedAtElapsedMillis: Long? = null
) {
    val satelliteCount: Int
        get() = satellites.size

    val usedInFixCount: Int
        get() = satellites.count { it.usedInFix }

    val averageCn0DbHz: Float
        get() = if (satellites.isNotEmpty()) {
            satellites.map { it.cn0DbHz }.average().toFloat()
        } else 0f

    val constellationCounts: Map<ConstellationType, Int>
        get() = satellites.groupBy { it.constellation }
            .mapValues { it.value.size }
}
