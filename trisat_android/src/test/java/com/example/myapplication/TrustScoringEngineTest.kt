package com.example.myapplication

import com.example.myapplication.data.gnss.engine.TrustScoringEngine
import com.example.myapplication.data.gnss.mock.MockGnssGenerator
import com.example.myapplication.data.gnss.model.ConstellationType
import com.example.myapplication.data.gnss.model.GnssMeasurementDetail
import com.example.myapplication.data.gnss.model.GnssMeasurementsData
import com.example.myapplication.data.gnss.model.GnssStatusData
import com.example.myapplication.data.gnss.model.LocationData
import com.example.myapplication.data.gnss.model.OsnmaStatus
import com.example.myapplication.data.gnss.model.SatelliteDetail
import com.example.myapplication.data.gnss.model.ThreatScenario
import com.example.myapplication.data.gnss.model.ThreatType
import com.example.myapplication.data.gnss.model.TrustAssessmentSource
import com.example.myapplication.data.gnss.model.TrustLevel
import com.example.myapplication.data.gnss.model.TrustReport
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
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
    fun testOrbitalDemoAgcDropsUnderJammingAndRecoversInNominalScenario() = runBlocking {
        val status = generator.createGnssStatusFlow().first()
        val location = LocationData()
        val nominalSample = generator.createOrbitalSample(ThreatScenario.NOMINAL, status.timestampMillis)
        val jammedSample = generator.createOrbitalSample(ThreatScenario.RF_JAMMING, status.timestampMillis)
        val restoredSample = generator.createOrbitalSample(ThreatScenario.NOMINAL, status.timestampMillis)

        assertTrue(jammedSample.isMock)
        assertTrue(jammedSample.measurements.isEmpty())
        assertTrue(jammedSample.averageAgcDb in -16.9..-16.1)
        assertTrue(nominalSample.averageAgcDb in -1.4..-1.0)
        assertTrue(restoredSample.averageAgcDb in -1.4..-1.0)

        val nominal = engine.evaluateTrust(status, nominalSample, location)
        val jammed = engine.evaluateTrust(status, jammedSample, location)
        val restored = engine.evaluateTrust(status, restoredSample, location)

        assertEquals(TrustAssessmentSource.SIMULATION, jammed.assessmentSource)
        assertEquals(20f, jammed.subScores.agcInterferenceScore, 0f)
        assertTrue(ThreatType.RF_JAMMING_ELEVATED in jammed.threatsDetected)
        assertTrue(jammed.overallScore < nominal.overallScore)
        assertEquals(TrustLevel.LOW_TRUST, jammed.assessedTrustLevel)
        assertTrue(jammed.intelligenceLogs.any { it.tag == "JAMMING_DETECTOR" && it.message.startsWith("Simulated RF interference") })

        assertEquals(100f, restored.subScores.agcInterferenceScore, 0f)
        assertFalse(ThreatType.RF_JAMMING_ELEVATED in restored.threatsDetected)
        assertEquals(nominal.overallScore, restored.overallScore, 0f)
    }

    @Test
    fun testSimulatedAgcIsIgnoredInReceiverMeasurements() {
        val measurements = GnssMeasurementsData(simulatedAgcDb = -16.5)
        val report = engine.evaluateTrust(GnssStatusData(), measurements, LocationData())

        assertTrue(measurements.agcLevelsDb.isEmpty())
        assertFalse(ThreatType.RF_JAMMING_ELEVATED in report.threatsDetected)
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
    fun testOrbitalDemoClockChangesTrustWithoutRawSatelliteMeasurements() = runBlocking {
        val status = generator.createGnssStatusFlow().first()
        val location = LocationData()
        val nominalSample = generator.createOrbitalSample(ThreatScenario.NOMINAL, status.timestampMillis)
        val attackSample = generator.createOrbitalSample(ThreatScenario.CLOCK_DRIFT_ATTACK, status.timestampMillis)

        assertTrue(attackSample.isMock)
        assertTrue(attackSample.measurements.isEmpty())
        assertTrue(requireNotNull(attackSample.driftNanosPerSecond) in 381.0..389.0)
        assertEquals(3, attackSample.hardwareClockDiscontinuityCount)
        assertEquals(0, nominalSample.hardwareClockDiscontinuityCount)

        val nominal = engine.evaluateTrust(status, nominalSample, location)
        val attack = engine.evaluateTrust(status, attackSample, location)

        assertEquals(TrustAssessmentSource.SIMULATION, attack.assessmentSource)
        assertTrue(ThreatType.CLOCK_DRIFT_ANOMALY in attack.threatsDetected)
        assertTrue(ThreatType.CLOCK_DRIFT_ANOMALY !in nominal.threatsDetected)
        assertEquals(100f, nominal.subScores.clockStabilityScore, 0f)
        assertEquals(35f, attack.subScores.clockStabilityScore, 0f)
        assertEquals(6.5f, nominal.overallScore - attack.overallScore, 0.001f)
        assertTrue(attack.intelligenceLogs.any { it.tag == "CLOCK_MONITOR" && it.message.startsWith("Simulated clock drift") })
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

    @Test
    fun testEvaluationLogReportsMediumTrustWithoutClaimingAnomaly() {
        val status = GnssStatusData(satellites = listOf(SatelliteDetail(
            svid = 1, constellation = ConstellationType.GPS, cn0DbHz = 22f,
            elevationDegrees = 45f, azimuthDegrees = 90f, usedInFix = true
        )))
        val measurements = GnssMeasurementsData(measurements = listOf(GnssMeasurementDetail(
            svid = 1, constellation = ConstellationType.GPS, state = 0,
            receivedSvTimeNanos = 1L, cn0DbHz = 22.0
        )))
        val report = engine.evaluateTrust(status, measurements, LocationData())
        val log = report.intelligenceLogs.single { it.tag == "ENGINE_EVAL" }

        assertTrue(report.threatsDetected.isEmpty())
        assertEquals(TrustLevel.MEDIUM_TRUST, report.trustLevel)
        assertEquals(TrustLevel.MEDIUM_TRUST, report.assessedTrustLevel)
        assertEquals(TrustAssessmentSource.RECEIVER, report.assessmentSource)
        assertEquals("WARNING", log.severity)
        assertTrue(log.message.contains("No anomaly triggers detected."))
        assertTrue(log.message.contains("Calculated trust level MEDIUM TRUST"))
    }

    @Test
    fun testEvaluationLogMarksMissingDataAsProvisional() = runBlocking {
        generator.setScenario(ThreatScenario.NOMINAL)
        val status = generator.createGnssStatusFlow().first()
        val measurements = generator.createGnssMeasurementsFlow().first()
        val location = LocationData()

        val reports = listOf(
            engine.evaluateTrust(GnssStatusData(), GnssMeasurementsData(), location),
            engine.evaluateTrust(GnssStatusData(), measurements, location),
            engine.evaluateTrust(status.copy(isMock = false), GnssMeasurementsData(), location)
        )
        for (report in reports) {
            val log = report.intelligenceLogs.single { it.tag == "ENGINE_EVAL" }
            assertNull(report.assessedTrustLevel)
            assertEquals("WARNING", log.severity)
            assertTrue(log.message.contains("Insufficient GNSS data"))
            assertTrue(log.message.contains("Provisional trust level ${report.trustLevel.name.replace('_', ' ')}"))
        }
    }

    @Test
    fun testSimulatedSkyCanBeAssessedWithoutRawMeasurements() = runBlocking {
        generator.setScenario(ThreatScenario.NOMINAL)
        val status = generator.createGnssStatusFlow().first()
        val measurements = generator.createGnssMeasurementsFlow().first()
        val location = LocationData()

        assertNull(TrustReport().assessedTrustLevel)

        for (rawInput in listOf(GnssMeasurementsData(), measurements)) {
            val simulated = engine.evaluateTrust(status, rawInput, location)
            assertEquals(TrustAssessmentSource.SIMULATION, simulated.assessmentSource)
            assertEquals(simulated.trustLevel, simulated.assessedTrustLevel)
            assertTrue(simulated.intelligenceLogs.single { it.tag == "ENGINE_EVAL" }.message.contains("Simulated trust level"))
        }

        val mixedReports = listOf(
            engine.evaluateTrust(status, measurements.copy(isMock = false), location),
            engine.evaluateTrust(status.copy(isMock = false), measurements, location)
        )
        for (report in mixedReports) {
            assertNull(report.assessedTrustLevel)
            assertTrue(report.intelligenceLogs.single { it.tag == "ENGINE_EVAL" }.message.contains("Provisional trust level"))
        }
    }

    @Test
    fun testEvaluationLogDistinguishesNominalAndDetectedAnomalies() = runBlocking {
        generator.setScenario(ThreatScenario.NOMINAL)
        val nominal = engine.evaluateTrust(
            generator.createGnssStatusFlow().first(),
            generator.createGnssMeasurementsFlow().first(),
            generator.createLocationFlow().first()
        ).intelligenceLogs.single { it.tag == "ENGINE_EVAL" }
        assertEquals("INFO", nominal.severity)
        assertTrue(nominal.message.contains("No anomaly triggers detected."))
        assertTrue(nominal.message.contains("Simulated trust level HIGH TRUST"))

        generator.setScenario(ThreatScenario.SPOOFING_SIMULATOR)
        val spoofing = engine.evaluateTrust(
            generator.createGnssStatusFlow().first(),
            generator.createGnssMeasurementsFlow().first(),
            generator.createLocationFlow().first()
        ).intelligenceLogs.single { it.tag == "ENGINE_EVAL" }
        assertEquals("ALERT", spoofing.severity)
        assertTrue(spoofing.message.contains("anomaly trigger(s) detected."))
        assertTrue(spoofing.message.contains("Simulated trust level LOW TRUST"))
    }
}
