package com.example.myapplication

import com.example.myapplication.data.gnss.engine.TrustScoringEngine
import com.example.myapplication.data.gnss.mock.MockGnssGenerator
import com.example.myapplication.data.gnss.model.ConstellationType
import com.example.myapplication.data.gnss.model.GnssMeasurementsData
import com.example.myapplication.data.gnss.model.GnssStatusData
import com.example.myapplication.data.gnss.model.LocationData
import com.example.myapplication.data.gnss.model.OsnmaStatus
import com.example.myapplication.data.gnss.model.SatelliteDetail
import com.example.myapplication.data.gnss.model.ThreatScenario
import com.example.myapplication.data.gnss.model.ThreatType
import com.example.myapplication.data.gnss.model.TrustLevel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TrustScoringEngineTest {

    private val engine = TrustScoringEngine()
    private val generator = MockGnssGenerator()

    @Test
    fun testNominalSignalTrustScoring() = runBlocking {
        generator.setScenario(ThreatScenario.NOMINAL)
        val status = generator.createGnssStatusFlow().first()
        val measurements = generator.createGnssMeasurementsFlow().first()
        val location = generator.createLocationFlow().first()

        val report = engine.evaluateTrust(status, measurements, location)

        assertNotNull(report)
        assertEquals(TrustLevel.HIGH_TRUST, report.trustLevel)
        assertTrue("Overall score should be >= 80%", report.overallScore >= 80f)
        assertTrue("No threats should be detected in nominal scenario", report.threatsDetected.isEmpty())
        assertTrue("Active warnings should be empty", report.activeThreatWarnings.isEmpty())
        assertEquals(OsnmaStatus.SIMULATED, report.osnmaStatus)
        assertEquals(
            OsnmaStatus.NOT_AVAILABLE,
            engine.evaluateTrust(status.copy(isMock = false), measurements, location.copy(isMock = false)).osnmaStatus
        )
        assertTrue("Intelligence logs should be generated", report.intelligenceLogs.isNotEmpty())
    }

    @Test
    fun testSpoofingSimulatorDetection() = runBlocking {
        generator.setScenario(ThreatScenario.SPOOFING_SIMULATOR)
        val status = generator.createGnssStatusFlow().first()
        val measurements = generator.createGnssMeasurementsFlow().first()
        val location = generator.createLocationFlow().first()

        val report = engine.evaluateTrust(status, measurements, location)

        assertNotNull(report)
        assertTrue("Should detect spoofing simulator threat", report.threatsDetected.contains(ThreatType.SPOOFING_SIMULATOR_DETECTED))
        assertTrue("Overall score should be reduced (< 65%)", report.overallScore < 65f)
        assertTrue("Signal authenticity subscore should drop", report.subScores.signalAuthenticityScore < 50f)
        assertTrue("Active warnings should mention spoofing", report.activeThreatWarnings.any { it.contains("uniform C/N0", ignoreCase = true) || it.contains("high C/N0", ignoreCase = true) })
    }

    @Test
    fun testRfJammingDetection() = runBlocking {
        generator.setScenario(ThreatScenario.RF_JAMMING)
        val status = generator.createGnssStatusFlow().first()
        val measurements = generator.createGnssMeasurementsFlow().first()
        val location = generator.createLocationFlow().first()

        val report = engine.evaluateTrust(status, measurements, location)

        assertNotNull(report)
        assertTrue("Should detect RF jamming threat", report.threatsDetected.contains(ThreatType.RF_JAMMING_ELEVATED))
        assertTrue("AGC subscore should drop under jamming", report.subScores.agcInterferenceScore < 50f)
        assertTrue("Warnings should mention AGC or RF interference", report.activeThreatWarnings.any { it.contains("AGC", ignoreCase = true) || it.contains("Interference", ignoreCase = true) })
    }

    @Test
    fun testClockDriftAnomalyDetection() = runBlocking {
        generator.setScenario(ThreatScenario.CLOCK_DRIFT_ATTACK)
        val status = generator.createGnssStatusFlow().first()
        val measurements = generator.createGnssMeasurementsFlow().first()
        val location = generator.createLocationFlow().first()

        val report = engine.evaluateTrust(status, measurements, location)

        assertNotNull(report)
        assertTrue("Should detect clock drift threat", report.threatsDetected.contains(ThreatType.CLOCK_DRIFT_ANOMALY))
        assertTrue("Clock stability subscore should drop", report.subScores.clockStabilityScore < 60f)
    }

    @Test
    fun testOsnmaAuthenticationFailure() = runBlocking {
        generator.setScenario(ThreatScenario.NOMINAL)
        val status = generator.createGnssStatusFlow().first()
        val measurements = generator.createGnssMeasurementsFlow().first()
        val location = generator.createLocationFlow().first()

        val report = engine.evaluateTrust(
            gnssStatus = status,
            gnssMeasurements = measurements,
            location = location,
            osnmaOverride = OsnmaStatus.SIMULATED_FAILURE
        )

        assertNotNull(report)
        assertEquals(OsnmaStatus.SIMULATED_FAILURE, report.osnmaStatus)
        assertFalse(report.threatsDetected.contains(ThreatType.UNAUTHENTICATED_SIGNAL))
        assertEquals(0f, report.subScores.osnmaAuthScore, 0.01f)
    }

    @Test
    fun testConstellationDiversityScoring() {
        // Single constellation test
        val singleConstSats = listOf(
            SatelliteDetail(svid = 1, constellation = ConstellationType.GPS, cn0DbHz = 40f, elevationDegrees = 45f, azimuthDegrees = 90f, usedInFix = true),
            SatelliteDetail(svid = 2, constellation = ConstellationType.GPS, cn0DbHz = 38f, elevationDegrees = 30f, azimuthDegrees = 180f, usedInFix = true),
            SatelliteDetail(svid = 3, constellation = ConstellationType.GPS, cn0DbHz = 42f, elevationDegrees = 60f, azimuthDegrees = 270f, usedInFix = true),
            SatelliteDetail(svid = 4, constellation = ConstellationType.GPS, cn0DbHz = 35f, elevationDegrees = 20f, azimuthDegrees = 310f, usedInFix = true),
            SatelliteDetail(svid = 5, constellation = ConstellationType.GPS, cn0DbHz = 39f, elevationDegrees = 50f, azimuthDegrees = 40f, usedInFix = true),
            SatelliteDetail(svid = 6, constellation = ConstellationType.GPS, cn0DbHz = 41f, elevationDegrees = 55f, azimuthDegrees = 120f, usedInFix = true),
            SatelliteDetail(svid = 7, constellation = ConstellationType.GPS, cn0DbHz = 37f, elevationDegrees = 25f, azimuthDegrees = 220f, usedInFix = true)
        )

        val status = GnssStatusData(satellites = singleConstSats)
        val measurements = GnssMeasurementsData()
        val location = LocationData()

        val report = engine.evaluateTrust(status, measurements, location)

        assertEquals(40f, report.subScores.constellationDiversityScore, 0.01f)
        assertTrue("Should flag constellation spoofing or single constellation dependency", report.threatsDetected.contains(ThreatType.CONSTELLATION_SPOOFING))
    }

    @Test
    fun testDopEstimation() {
        val wellDispersedSats = listOf(
            SatelliteDetail(svid = 1, constellation = ConstellationType.GPS, cn0DbHz = 40f, elevationDegrees = 75f, azimuthDegrees = 45f, usedInFix = true),
            SatelliteDetail(svid = 2, constellation = ConstellationType.GPS, cn0DbHz = 38f, elevationDegrees = 30f, azimuthDegrees = 135f, usedInFix = true),
            SatelliteDetail(svid = 3, constellation = ConstellationType.GALILEO, cn0DbHz = 42f, elevationDegrees = 40f, azimuthDegrees = 225f, usedInFix = true),
            SatelliteDetail(svid = 4, constellation = ConstellationType.BEIDOU, cn0DbHz = 35f, elevationDegrees = 50f, azimuthDegrees = 315f, usedInFix = true)
        )

        val status = GnssStatusData(satellites = wellDispersedSats)
        val report = engine.evaluateTrust(status, GnssMeasurementsData(), LocationData())

        assertTrue("Estimated HDOP should be reasonable (< 3.0)", report.estimatedHdop < 3.0f)
        assertTrue("Geometry subscore should be high", report.subScores.geometryDopScore >= 80f)
    }
}
