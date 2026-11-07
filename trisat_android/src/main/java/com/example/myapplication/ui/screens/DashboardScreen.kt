package com.example.myapplication.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import com.example.myapplication.R
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.BarChart
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.DeleteSweep
import androidx.compose.material.icons.rounded.FilterList
import androidx.compose.material.icons.rounded.GppBad
import androidx.compose.material.icons.rounded.GppGood
import androidx.compose.material.icons.rounded.Key
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.Navigation
import androidx.compose.material.icons.rounded.Public
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.SatelliteAlt
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material.icons.rounded.SignalCellular4Bar
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.myapplication.data.gnss.model.GnssReceiverMode
import com.example.myapplication.data.gnss.model.LocationData
import com.example.myapplication.data.gnss.model.ThreatScenario
import com.example.myapplication.data.gnss.model.ThreatType
import com.example.myapplication.data.gnss.model.TrustLevel
import com.example.myapplication.data.gnss.model.TrustSubScores
import com.example.myapplication.ui.components.LocationPermissionHandler
import com.example.myapplication.ui.components.StatusBadge
import com.example.myapplication.ui.components.StatusLevel
import com.example.myapplication.ui.components.TrustabilityGaugeMeter
import com.example.myapplication.ui.theme.TRISATTheme
import com.example.myapplication.ui.viewmodel.GnssViewModel
import androidx.compose.material3.Slider
import java.util.Locale

@Composable
fun DashboardScreen(
    gnssViewModel: GnssViewModel = viewModel(),
    onNavigateToSignal: () -> Unit = {},
    onNavigateToThreats: () -> Unit = {}
) {
    val receiverMode by gnssViewModel.receiverMode.collectAsState()
    val timeOffsetHours by gnssViewModel.timeOffsetHours.collectAsState()
    val trustReport by gnssViewModel.trustReportState.collectAsState()
    val gnssStatus by gnssViewModel.gnssStatusState.collectAsState()
    val locationData by gnssViewModel.locationState.collectAsState()
    val activeScenario by gnssViewModel.activeScenarioState.collectAsState()
    val permissionGranted by gnssViewModel.permissionGranted.collectAsState()
    val isMockMode by gnssViewModel.isMockMode.collectAsState()
    val inavMessages by gnssViewModel.inavMessagesState.collectAsState()
    val positionHistory by gnssViewModel.positionHistoryState.collectAsState()
    val lastAGnssResetTime by gnssViewModel.lastAGnssResetTimeState.collectAsState()

    val inavSvidSet = remember(inavMessages) {
        inavMessages.filter { it.isGalileoInav }.map { it.svid }.toSet()
    }

    val trustLevel = trustReport.trustLevel

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp),
        contentPadding = PaddingValues(top = 16.dp, bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 0. TRISAT Image Banner Card with Mode Badge
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceContainer
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.trisat_logo),
                            contentDescription = "TRISAT Logo",
                            modifier = Modifier
                                .height(38.dp)
                                .clip(RoundedCornerShape(8.dp)),
                            contentScale = ContentScale.Fit
                        )

                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = when (receiverMode) {
                                GnssReceiverMode.INTERNAL_TLE -> MaterialTheme.colorScheme.primaryContainer
                                GnssReceiverMode.EXTERNAL_HARDWARE -> MaterialTheme.colorScheme.secondaryContainer
                                GnssReceiverMode.SIMULATION_TLE -> MaterialTheme.colorScheme.tertiaryContainer
                            }
                        ) {
                            Text(
                                text = if (gnssStatus.isMock) "SIMULATED SKY VIEW" else receiverMode.badge,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.ExtraBold,
                                color = when (receiverMode) {
                                    GnssReceiverMode.INTERNAL_TLE -> MaterialTheme.colorScheme.onPrimaryContainer
                                    GnssReceiverMode.EXTERNAL_HARDWARE -> MaterialTheme.colorScheme.onSecondaryContainer
                                    GnssReceiverMode.SIMULATION_TLE -> MaterialTheme.colorScheme.onTertiaryContainer
                                }
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Text(
                        text = "TRISAT — Multi-Constellation GNSS & Security Suite",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = when {
                            !locationData.hasFix -> "Position: no fix"
                            locationData.isMock -> "Position: simulated"
                            else -> "Position: reported by device"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        // Location Permission Banner
        if (!permissionGranted && receiverMode != GnssReceiverMode.SIMULATION_TLE) {
            item {
                LocationPermissionHandler(
                    isPermissionGranted = permissionGranted,
                    isMockMode = isMockMode,
                    onPermissionResult = { granted ->
                        if (granted) {
                            gnssViewModel.refreshPermissions()
                            gnssViewModel.toggleMockMode(false)
                            gnssViewModel.startMonitoring()
                        }
                    }
                )
            }
        }

        // TLE Simulation 24h Time Scrubbing Slider Card (Active in Mode 2)
        if (receiverMode == GnssReceiverMode.SIMULATION_TLE) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceContainer
                    )
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Orbit Propagation Offset:",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = String.format(Locale.US, "%+.1f h (±12h)", timeOffsetHours),
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.ExtraBold,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                        Slider(
                            value = timeOffsetHours,
                            onValueChange = { gnssViewModel.setTimeOffsetHours(it) },
                            valueRange = -12f..12f,
                            steps = 47,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
                        )
                    }
                }
            }
        }

        // 1. Open Sky Satellite View (Skyplot)
        item {
            com.example.myapplication.ui.components.SkyplotCard(
                satellites = gnssStatus.satellites,
                inavSvidSet = inavSvidSet
            )
        }

        // 2. Active Threats Banner / Alert Cards
        if (trustReport.threatsDetected.isNotEmpty()) {
            item {
                Text(
                    text = if (gnssStatus.isMock) {
                        "Simulated Anomalies (${trustReport.threatsDetected.size})"
                    } else {
                        "Active Threats Detected (${trustReport.threatsDetected.size})"
                    },
                    style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold),
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(start = 4.dp)
                )
            }

            items(trustReport.threatsDetected) { threat ->
                DashboardThreatAlertCard(threat = threat, onClick = onNavigateToThreats)
            }
        }

        // 2. Position History & Error Statistics Module
        item {
            PositionHistoryCard(
                positionHistory = positionHistory,
                lastAGnssResetTime = lastAGnssResetTime,
                onClearHistory = { gnssViewModel.clearPositionHistory() },
                onRemoveAGnss = { gnssViewModel.resetAGnssData() }
            )
        }
    }
}

@Composable
fun PositionHistoryCard(
    positionHistory: List<LocationData>,
    lastAGnssResetTime: Long,
    onClearHistory: () -> Unit,
    onRemoveAGnss: () -> Unit
) {
    val sampleCount = positionHistory.size
    val horizontalRms = remember(positionHistory) {
        if (positionHistory.isEmpty()) 1.2f
        else kotlin.math.sqrt(positionHistory.map { (it.accuracy * it.accuracy).toDouble() }.average()).toFloat()
    }
    val verticalRms = remember(positionHistory) {
        if (positionHistory.isEmpty()) 2.1f
        else kotlin.math.sqrt(positionHistory.map {
            val vert = if (it.verticalAccuracyMeters > 0) it.verticalAccuracyMeters else it.accuracy * 1.5f
            (vert * vert).toDouble()
        }.average()).toFloat()
    }
    val rms3d = remember(horizontalRms, verticalRms) {
        kotlin.math.sqrt((horizontalRms * horizontalRms + verticalRms * verticalRms).toDouble()).toFloat()
    }

    val isRecentlyReset = System.currentTimeMillis() - lastAGnssResetTime < 5000L

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    modifier = Modifier.weight(1f),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Rounded.LocationOn,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column {
                        Text(
                            text = "Position History & Error Stats",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            maxLines = 1,
                            softWrap = false
                        )
                        Text(
                            text = "$sampleCount Position Samples Evaluated",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            softWrap = false
                        )
                    }
                }

                StatusBadge(
                    text = if (isRecentlyReset) "A-GNSS PURGED" else "SAMPLES ACTIVE",
                    level = if (isRecentlyReset) StatusLevel.WARNING else StatusLevel.SECURE
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                RawMetricTile(
                    label = "Horizontal Error",
                    value = "${String.format(Locale.US, "%.2f", horizontalRms)} m",
                    subtitle = "2D RMS Error",
                    icon = Icons.Rounded.Map,
                    modifier = Modifier.weight(1f)
                )

                Spacer(modifier = Modifier.width(10.dp))

                RawMetricTile(
                    label = "Vertical Error",
                    value = "${String.format(Locale.US, "%.2f", verticalRms)} m",
                    subtitle = "1D Height Error",
                    icon = Icons.Rounded.Navigation,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                RawMetricTile(
                    label = "3D Position Error",
                    value = "${String.format(Locale.US, "%.2f", rms3d)} m",
                    subtitle = "RMS 3D Fix Error",
                    icon = Icons.Rounded.Speed,
                    modifier = Modifier.weight(1f)
                )

                Spacer(modifier = Modifier.width(10.dp))

                RawMetricTile(
                    label = "Sample Count",
                    value = "$sampleCount",
                    subtitle = "Epochs Logged",
                    icon = Icons.Rounded.Timer,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Button(
                    onClick = onRemoveAGnss,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary
                    )
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Remove A-GNSS", fontSize = 11.sp, maxLines = 1, softWrap = false)
                }

                OutlinedButton(
                    onClick = onClearHistory,
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(
                        imageVector = Icons.Rounded.DeleteSweep,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Clear History", fontSize = 11.sp, maxLines = 1, softWrap = false)
                }
            }
        }
    }
}

@Composable
fun DashboardThreatAlertCard(
    threat: ThreatType,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Rounded.GppBad,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onErrorContainer,
                modifier = Modifier.size(28.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = threat.title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = threat.description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun DashboardScreenPreview() {
    TRISATTheme {
        DashboardScreen()
    }
}
