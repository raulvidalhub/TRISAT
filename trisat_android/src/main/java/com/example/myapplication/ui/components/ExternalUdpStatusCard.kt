package com.example.myapplication.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.myapplication.data.gnss.udp.ExternalUdpStage
import com.example.myapplication.data.gnss.udp.ExternalUdpStatus

@Composable
internal fun ExternalUdpStatusCard(status: ExternalUdpStatus) {
    val label = when (status.stage) {
        ExternalUdpStage.OFF -> "Listener stopped"
        ExternalUdpStage.STARTING -> "Starting listener"
        ExternalUdpStage.LISTENING -> "Listening for NMEA"
        ExternalUdpStage.RECEIVING -> "Receiving NMEA"
        ExternalUdpStage.STALE -> "NMEA data stale"
        ExternalUdpStage.UNAVAILABLE -> "UDP listener unavailable"
    }
    val level = when (status.stage) {
        ExternalUdpStage.STALE, ExternalUdpStage.UNAVAILABLE -> StatusLevel.WARNING
        else -> StatusLevel.INFO
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text("External telemetry · UDP port ${status.port}", style = MaterialTheme.typography.titleSmall)
            StatusBadge(text = label, level = level)
            Text(
                "UDP datagrams ${status.datagramsReceived} · NMEA accepted ${status.nmeaReceived}",
                style = MaterialTheme.typography.bodySmall
            )
            status.lastSentenceType?.let { type ->
                Text("Last accepted NMEA was $type. Source unverified.", style = MaterialTheme.typography.bodySmall)
            }
            if (status.stage == ExternalUdpStage.UNAVAILABLE) {
                Text("Select External Receiver again to retry.", style = MaterialTheme.typography.bodySmall)
            }
            Text(
                "Trust evaluation pending. Raw GNSS measurements are required.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
