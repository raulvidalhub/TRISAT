package com.example.myapplication

import com.example.myapplication.data.gnss.engine.ReceiverTrustFreshness
import com.example.myapplication.data.gnss.model.TrustAssessmentSource
import com.example.myapplication.data.gnss.model.TrustLevel
import com.example.myapplication.data.gnss.model.TrustReport
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReceiverTrustFreshnessTest {
    private val pending = TrustReport()
    private val receiver = TrustReport(
        trustLevel = TrustLevel.HIGH_TRUST,
        assessmentSource = TrustAssessmentSource.RECEIVER,
        timestampMillis = 100_000L
    )

    @Test
    fun waitsForBothInputsBeforeTheFirstReceiverAssessment() {
        val statusExpiry = ReceiverTrustFreshness.inputExpiry(1_000L, 2_000L)
        val report = ReceiverTrustFreshness.track(receiver, pending, statusExpiry, null)

        assertNull(report.assessedTrustLevel)
        assertNull(report.lastReceiverAssessmentMillis)
        assertFalse(report.isReceiverDataStale)
    }

    @Test
    fun expiresAtFiveSecondsAfterTheOlderInputEvenIfTrustWasReevaluated() {
        val statusExpiry = ReceiverTrustFreshness.inputExpiry(1_000L, 5_999L)
        val rawExpiry = ReceiverTrustFreshness.inputExpiry(5_999L, 5_999L)
        val fresh = ReceiverTrustFreshness.track(receiver, pending, statusExpiry, rawExpiry)

        assertEquals(TrustLevel.HIGH_TRUST, ReceiverTrustFreshness.expire(fresh, 5_999L).assessedTrustLevel)
        assertNull(ReceiverTrustFreshness.inputExpiry(1_000L, 6_000L))
        val stale = ReceiverTrustFreshness.expire(fresh, 6_000L)
        assertTrue(stale.isReceiverDataStale)
        assertNull(stale.assessedTrustLevel)
        assertEquals(receiver.timestampMillis, stale.lastReceiverAssessmentMillis)
    }

    @Test
    fun losingEitherInputKeepsTheLastTimeAndFreshInputsRestoreTrust() {
        val fresh = ReceiverTrustFreshness.track(receiver, pending, 6_000L, 6_500L)
        val stale = ReceiverTrustFreshness.track(pending, fresh, null, 7_000L)
        assertTrue(stale.isReceiverDataStale)
        assertEquals(receiver.timestampMillis, stale.lastReceiverAssessmentMillis)

        val onlySatelliteStatus = ReceiverTrustFreshness.track(pending, stale, 12_000L, null)
        assertNull(onlySatelliteStatus.assessedTrustLevel)
        assertEquals(receiver.timestampMillis, onlySatelliteStatus.lastReceiverAssessmentMillis)

        val newReport = receiver.copy(timestampMillis = 107_000L)
        val recovered = ReceiverTrustFreshness.track(newReport, onlySatelliteStatus, 12_000L, 12_500L)
        assertFalse(recovered.isReceiverDataStale)
        assertEquals(TrustLevel.HIGH_TRUST, recovered.assessedTrustLevel)
        assertEquals(newReport.timestampMillis, recovered.lastReceiverAssessmentMillis)
    }

    @Test
    fun simulationsHaveNoReceiverExpiry() {
        val previous = ReceiverTrustFreshness.track(receiver, pending, 6_000L, 6_000L)
        val simulated = receiver.copy(assessmentSource = TrustAssessmentSource.SIMULATION)
        val report = ReceiverTrustFreshness.track(simulated, previous, null, null)
        val afterWaiting = ReceiverTrustFreshness.expire(report, 60_000L)

        assertEquals(TrustLevel.HIGH_TRUST, afterWaiting.assessedTrustLevel)
        assertFalse(afterWaiting.isReceiverDataStale)
        assertNull(afterWaiting.lastReceiverAssessmentMillis)
    }
}
