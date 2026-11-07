package com.example.myapplication.data.gnss.engine

import com.example.myapplication.data.gnss.model.TrustAssessmentSource
import com.example.myapplication.data.gnss.model.TrustReport

internal object ReceiverTrustFreshness {
    private const val MAX_INPUT_AGE_MILLIS = 5_000L

    fun inputExpiry(receivedAtElapsedMillis: Long?, nowElapsedMillis: Long): Long? {
        if (receivedAtElapsedMillis == null) return null
        val age = nowElapsedMillis - receivedAtElapsedMillis
        return if (age in 0 until MAX_INPUT_AGE_MILLIS) {
            receivedAtElapsedMillis + MAX_INPUT_AGE_MILLIS
        } else {
            null
        }
    }

    fun track(
        evaluated: TrustReport,
        previous: TrustReport,
        satelliteStatusExpiry: Long?,
        rawMeasurementsExpiry: Long?
    ): TrustReport = when {
        evaluated.assessmentSource == TrustAssessmentSource.SIMULATION -> evaluated
        evaluated.assessmentSource == TrustAssessmentSource.RECEIVER &&
                satelliteStatusExpiry != null && rawMeasurementsExpiry != null ->
            evaluated.copy(
                receiverInputsExpireAtElapsedMillis = minOf(satelliteStatusExpiry, rawMeasurementsExpiry)
            )
        previous.assessmentSource == TrustAssessmentSource.RECEIVER ->
            previous.copy(isReceiverDataStale = true)
        evaluated.assessmentSource == TrustAssessmentSource.RECEIVER -> TrustReport()
        else -> evaluated
    }

    fun expire(report: TrustReport, nowElapsedMillis: Long): TrustReport {
        val expiresAt = report.receiverInputsExpireAtElapsedMillis ?: return report
        return if (nowElapsedMillis >= expiresAt && !report.isReceiverDataStale) {
            report.copy(isReceiverDataStale = true)
        } else {
            report
        }
    }
}
