package com.example.myapplication.data.gnss.mock

import com.example.myapplication.data.gnss.model.ConstellationType
import com.example.myapplication.data.gnss.model.GnssMeasurementDetail
import com.example.myapplication.data.gnss.model.GnssMeasurementsData
import com.example.myapplication.data.gnss.model.GnssStatusData
import com.example.myapplication.data.gnss.model.LocationData
import com.example.myapplication.data.gnss.model.SatelliteDetail
import com.example.myapplication.data.gnss.model.ThreatScenario
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.delay
import java.util.Locale
import kotlin.random.Random

class MockGnssGenerator {

    var activeScenario: ThreatScenario = ThreatScenario.NOMINAL
        private set

    fun setScenario(scenario: ThreatScenario) {
        activeScenario = scenario
    }

    private data class InitialSat(
        val svid: Int,
        val constellation: ConstellationType,
        val baseCn0: Float,
        val baseElev: Float,
        val baseAzim: Float,
        val carrierFreqHz: Double,
        val usedInFix: Boolean
    )

    private val baseSatellites = listOf(
        // GPS Satellites
        InitialSat(2, ConstellationType.GPS, 42.5f, 68f, 124f, 1575420000.0, true),
        InitialSat(8, ConstellationType.GPS, 38.0f, 42f, 210f, 1575420000.0, true),
        InitialSat(14, ConstellationType.GPS, 44.2f, 81f, 45f, 1176450000.0, true), // L5
        InitialSat(22, ConstellationType.GPS, 35.8f, 25f, 305f, 1575420000.0, false),
        InitialSat(31, ConstellationType.GPS, 41.0f, 58f, 175f, 1575420000.0, true),

        // Galileo Satellites
        InitialSat(5, ConstellationType.GALILEO, 46.1f, 75f, 180f, 1575420000.0, true), // E1
        InitialSat(11, ConstellationType.GALILEO, 41.3f, 54f, 95f, 1176450000.0, true), // E5a
        InitialSat(19, ConstellationType.GALILEO, 39.0f, 38f, 240f, 1575420000.0, true),
        InitialSat(24, ConstellationType.GALILEO, 43.8f, 62f, 275f, 1176450000.0, true),
        InitialSat(30, ConstellationType.GALILEO, 40.5f, 49f, 30f, 1575420000.0, true),

        // BeiDou Satellites
        InitialSat(3, ConstellationType.BEIDOU, 39.5f, 48f, 150f, 1561098000.0, true), // B1I
        InitialSat(9, ConstellationType.BEIDOU, 37.2f, 33f, 88f, 1561098000.0, false),
        InitialSat(16, ConstellationType.BEIDOU, 42.1f, 60f, 215f, 1561098000.0, true),
        InitialSat(22, ConstellationType.BEIDOU, 40.8f, 52f, 320f, 1561098000.0, true),

        // GLONASS Satellites
        InitialSat(4, ConstellationType.GLONASS, 40.1f, 51f, 310f, 1602000000.0, true),
        InitialSat(12, ConstellationType.GLONASS, 34.5f, 22f, 40f, 1602000000.0, false),
        InitialSat(18, ConstellationType.GLONASS, 36.4f, 29f, 140f, 1602000000.0, true),

        // QZSS Satellite
        InitialSat(1, ConstellationType.QZSS, 43.0f, 70f, 165f, 1575420000.0, true),

        // SBAS Satellite
        InitialSat(127, ConstellationType.SBAS, 38.5f, 35f, 195f, 1575420000.0, false)
    )

    fun createGnssStatusFlow(periodMillis: Long = 1000L): Flow<GnssStatusData> = flow {
        while (true) {
            val now = System.currentTimeMillis()
            val scenario = activeScenario

            val simulatedSats = baseSatellites.map { sat ->
                val currentCn0 = when (scenario) {
                    ThreatScenario.SPOOFING_SIMULATOR -> {
                        // All satellites broadcast identical flat power (e.g. 53.2 dB-Hz with minimal 0.05 noise)
                        53.2f + (Random.nextFloat() - 0.5f) * 0.1f
                    }
                    ThreatScenario.RF_JAMMING -> {
                        // Depressed signal power due to jammer noise floor saturation
                        (20.5f + (Random.nextFloat() - 0.5f) * 2.0f).coerceIn(15f, 26f)
                    }
                    else -> {
                        val noiseCn0 = (Random.nextFloat() - 0.5f) * 2.2f
                        (sat.baseCn0 + noiseCn0).coerceIn(18.0f, 50.0f)
                    }
                }

                val noiseElev = (Random.nextFloat() - 0.5f) * 0.4f
                val noiseAzim = (Random.nextFloat() - 0.5f) * 0.6f

                SatelliteDetail(
                    svid = sat.svid,
                    constellation = sat.constellation,
                    cn0DbHz = String.format(Locale.US, "%.1f", currentCn0).toFloat(),
                    elevationDegrees = (sat.baseElev + noiseElev).coerceIn(5f, 90f),
                    azimuthDegrees = (sat.baseAzim + noiseAzim) % 360f,
                    carrierFrequencyHz = sat.carrierFreqHz,
                    hasCarrierFrequency = true,
                    usedInFix = sat.usedInFix,
                    hasAlmanacData = true,
                    hasEphemerisData = true,
                    hasBasebandCn0 = true,
                    basebandCn0DbHz = (currentCn0 - 1.5f).coerceAtLeast(15.0f)
                )
            }

            emit(
                GnssStatusData(
                    satellites = simulatedSats,
                    isMock = true,
                    timestampMillis = now
                )
            )
            delay(periodMillis)
        }
    }

    internal fun createOrbitalSample(
        scenario: ThreatScenario,
        timestampMillis: Long
    ): GnssMeasurementsData = createClockSample(scenario, timestampMillis).copy(
        simulatedAgcDb = createAgcLevel(scenario)
    )

    private fun createClockSample(
        scenario: ThreatScenario,
        timestampMillis: Long
    ): GnssMeasurementsData {
        val isClockAttack = scenario == ThreatScenario.CLOCK_DRIFT_ATTACK
        val drift = if (isClockAttack) {
            385.0 + (Random.nextDouble() - 0.5) * 8.0
        } else {
            -12.4 + (Random.nextDouble() - 0.5) * 0.8
        }

        return GnssMeasurementsData(
            clockTimeNanos = System.nanoTime(),
            clockHardwareClockDiscontinuityCount = if (isClockAttack) 3 else 0,
            fullBiasNanos = -1318283401239082341L,
            biasNanos = -45.2 + (Random.nextDouble() - 0.5) * 1.2,
            biasUncertaintyNanos = 2.4,
            driftNanosPerSecond = drift,
            driftUncertaintyNanosPerSecond = 0.15,
            isMock = true,
            timestampMillis = timestampMillis
        )
    }

    private fun createAgcLevel(scenario: ThreatScenario): Double =
        if (scenario == ThreatScenario.RF_JAMMING) {
            -16.5 + (Random.nextDouble() - 0.5) * 0.8
        } else {
            -1.2 + (Random.nextDouble() - 0.5) * 0.4
        }

    fun createGnssMeasurementsFlow(periodMillis: Long = 1000L): Flow<GnssMeasurementsData> = flow {
        while (true) {
            val scenario = activeScenario
            val clockSample = createClockSample(scenario, System.currentTimeMillis())
            val clockNanos = clockSample.clockTimeNanos
            val agcBaseDb = createAgcLevel(scenario)

            val rawMeasurements = baseSatellites.map { sat ->
                val pseudorangeRate = -450.0 + (Random.nextDouble() - 0.5) * 25.0
                val prUncertainty = 0.02 + Random.nextDouble() * 0.05
                val agc = agcBaseDb + (Random.nextDouble() - 0.5) * 0.4

                val cn0 = when (scenario) {
                    ThreatScenario.SPOOFING_SIMULATOR -> 53.2 + (Random.nextDouble() - 0.5) * 0.1
                    ThreatScenario.RF_JAMMING -> 20.5 + (Random.nextDouble() - 0.5) * 2.0
                    else -> sat.baseCn0 + (Random.nextDouble() - 0.5) * 2.0
                }

                GnssMeasurementDetail(
                    svid = sat.svid,
                    constellation = sat.constellation,
                    state = 16383,
                    receivedSvTimeNanos = (clockNanos % 604800000000000L) + Random.nextLong(1000, 50000),
                    cn0DbHz = cn0,
                    pseudorangeRateMetersPerSecond = pseudorangeRate,
                    pseudorangeRateUncertaintyMetersPerSecond = prUncertainty,
                    accumulatedDeltaRangeState = 1,
                    accumulatedDeltaRangeMeters = 12450.32 + (Random.nextDouble() - 0.5) * 100.0,
                    carrierFrequencyHz = sat.carrierFreqHz.toFloat(),
                    automaticGainControlLevelDb = agc,
                    hasAgc = true,
                    multipathIndicator = if (cn0 < 38.0) 1 else 2,
                    snrInDb = (cn0 - 10.0).coerceAtLeast(10.0)
                )
            }

            emit(clockSample.copy(measurements = rawMeasurements))
            delay(periodMillis)
        }
    }

    fun createLocationFlow(periodMillis: Long = 1000L): Flow<LocationData> = flow {
        var baseLat = 37.774929
        var baseLng = -122.419416
        val baseAlt = 125.4

        while (true) {
            val now = System.currentTimeMillis()
            baseLat += (Random.nextDouble() - 0.48) * 0.00001
            baseLng += (Random.nextDouble() - 0.48) * 0.00001
            val speed = (1.2f + (Random.nextFloat() - 0.5f) * 0.2f).coerceAtLeast(0f)
            val bearing = (42.5f + (Random.nextFloat() - 0.5f) * 2.0f) % 360f

            emit(
                LocationData(
                    latitude = baseLat,
                    longitude = baseLng,
                    altitude = baseAlt,
                    speed = speed,
                    bearing = bearing,
                    accuracy = 1.8f + Random.nextFloat() * 0.6f,
                    verticalAccuracyMeters = 2.2f + Random.nextFloat() * 0.5f,
                    speedAccuracyMetersPerSecond = 0.1f,
                    bearingAccuracyDegrees = 1.2f,
                    elapsedRealtimeNanos = System.nanoTime(),
                    timestampMillis = now,
                    provider = "mock_gnss",
                    isMock = true,
                    hasFix = true
                )
            )
            delay(periodMillis)
        }
    }
}
