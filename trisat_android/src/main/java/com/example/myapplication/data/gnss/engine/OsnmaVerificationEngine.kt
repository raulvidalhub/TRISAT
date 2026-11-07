package com.example.myapplication.data.gnss.engine

import com.example.myapplication.data.gnss.model.GalileoInavMessage
import com.example.myapplication.data.gnss.model.OsnmaStatus

class OsnmaVerificationEngine {

    /** Reports reception only. The current pipeline does not verify received OSNMA tags. */
    fun verifyOsnma(inavMessages: List<GalileoInavMessage>): OsnmaStatus {
        return if (inavMessages.any { it.isGalileoInav && it.rawBytes.isNotEmpty() }) {
            OsnmaStatus.UNAUTHENTICATED
        } else {
            OsnmaStatus.NOT_AVAILABLE
        }
    }
}
