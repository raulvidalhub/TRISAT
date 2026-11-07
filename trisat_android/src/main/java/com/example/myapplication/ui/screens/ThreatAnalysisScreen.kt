package com.example.myapplication.ui.screens

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.FilterList
import androidx.compose.material.icons.rounded.GppBad
import androidx.compose.material.icons.rounded.GppGood
import androidx.compose.material.icons.rounded.Key
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Shield
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.Terminal
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
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.window.core.layout.WindowWidthSizeClass
import com.example.myapplication.data.gnss.model.IntelligenceLogEntry
import com.example.myapplication.data.gnss.model.OsnmaStatus
import com.example.myapplication.data.gnss.model.ThreatScenario
import com.example.myapplication.data.gnss.model.TrustAssessmentSource
import com.example.myapplication.data.gnss.model.TrustLevel
import com.example.myapplication.data.gnss.model.TrustSubScores
import com.example.myapplication.ui.components.StatusBadge
import com.example.myapplication.ui.components.StatusLevel
import com.example.myapplication.ui.components.TrustabilityGaugeMeter
import com.example.myapplication.ui.theme.TRISATTheme
import com.example.myapplication.ui.viewmodel.GnssViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.sqrt

@Suppress("DEPRECATION")
@Composable
fun ThreatAnalysisScreen(
    gnssViewModel: GnssViewModel = viewModel()
) {
    val trustReport by gnssViewModel.trustReportState.collectAsState()
    val activeScenario by gnssViewModel.activeScenarioState.collectAsState()
    val gnssStatus by gnssViewModel.gnssStatusState.collectAsState()
    val locationData by gnssViewModel.locationState.collectAsState()
    val gnssMeasurements by gnssViewModel.gnssMeasurementsState.collectAsState()

    val trustLevel = trustReport.assessedTrustLevel
    val isSimulatedAssessment = trustReport.assessmentSource == TrustAssessmentSource.SIMULATION
    val subScores = trustReport.subScores
    val threats = trustReport.threatsDetected
    val osnmaStatus = trustReport.osnmaStatus

    val windowAdaptiveInfo = currentWindowAdaptiveInfo()
    val isWideScreen = windowAdaptiveInfo.windowSizeClass.windowWidthSizeClass != WindowWidthSizeClass.COMPACT

    if (isWideScreen) {
        // Wide Screen Layout (Tablet / Foldable)
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Left Pane: Anti-Spoofing Overview & Interactive Controls & DOP / OSNMA
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                item {
                    AntiSpoofingOverviewCard(
                        trustLevel = trustLevel,
                        isSimulated = isSimulatedAssessment,
                        threatCount = threats.size,
                        activeScenario = activeScenario,
                        onSelectScenario = { scenario -> gnssViewModel.selectThreatScenario(scenario) }
                    )
                }

                item {
                    RawClockAndAgcCard(gnssMeasurements = gnssMeasurements)
                }

                if (gnssStatus.satellites.isNotEmpty()) {
                    item {
                        DopGeometryBreakdownCard(
                            hdop = trustReport.estimatedHdop,
                            vdop = trustReport.estimatedVdop
                        )
                    }
                }

                item {
                    OsnmaAuthenticationCard(osnmaStatus = osnmaStatus)
                }

                if (trustLevel != null) {
                    item {
                        SubScoresBreakdownCard(subScores = subScores)
                    }
                }
            }

            // Right Pane: Live Threat Logs
            LazyColumn(
                modifier = Modifier
                    .weight(1.1f)
                    .fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    Text(
                        text = if (isSimulatedAssessment) {
                            "Simulation Event Log (${trustReport.intelligenceLogs.size} Events)"
                        } else {
                            "Real-Time Intelligence Threat Feed (${trustReport.intelligenceLogs.size} Events)"
                        },
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }

                items(trustReport.intelligenceLogs.reversed()) { log ->
                    IntelligenceLogCard(entry = log)
                }
            }
        }
    } else {
        // Compact Phone Layout
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            if (trustLevel != null) {
                item {
                    TrustabilityGaugeCard(
                        score = trustReport.overallScore,
                        trustLevel = trustLevel,
                        isSimulated = isSimulatedAssessment
                    )
                }
            }

            item {
                AntiSpoofingOverviewCard(
                    trustLevel = trustLevel,
                    isSimulated = isSimulatedAssessment,
                    threatCount = threats.size,
                    activeScenario = activeScenario,
                    onSelectScenario = { scenario -> gnssViewModel.selectThreatScenario(scenario) }
                )
            }

            item {
                RawClockAndAgcCard(gnssMeasurements = gnssMeasurements)
            }

            item {
                com.example.myapplication.ui.screens.EarthIntelligenceLocationCard(
                    location = locationData,
                    satelliteCount = gnssStatus.satelliteCount,
                    constellationCount = gnssStatus.constellationCounts.size,
                    trustLevel = trustLevel
                )
            }

            item {
                com.example.myapplication.ui.screens.Cn0BandDistributionCard(satellites = gnssStatus.satellites)
            }

            if (trustLevel != null) {
                item {
                    Text(
                        text = "Weighted Diagnostic Sub-Scores",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(start = 4.dp)
                    )
                }

                item {
                    SubScoresBreakdownCard(subScores = subScores)
                }
            }

            item {
                Text(
                    text = "DOP Geometry & Anti-Jamming Verification",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(start = 4.dp, top = 4.dp)
                )
            }

            if (gnssStatus.satellites.isNotEmpty()) {
                item {
                    DopGeometryBreakdownCard(
                        hdop = trustReport.estimatedHdop,
                        vdop = trustReport.estimatedVdop
                    )
                }
            }

            item {
                OsnmaAuthenticationCard(osnmaStatus = osnmaStatus)
            }

            item {
                Text(
                    text = if (isSimulatedAssessment) "Simulation Event Log" else "Real-Time Threat Intelligence Event Logs",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(start = 4.dp, top = 8.dp)
                )
            }

            items(trustReport.intelligenceLogs.reversed()) { log ->
                IntelligenceLogCard(entry = log)
            }
        }
    }
}

@Composable
fun TrustabilityGaugeCard(
    score: Float,
    trustLevel: TrustLevel,
    isSimulated: Boolean
) {
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
                .padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Rounded.Shield,
                        contentDescription = "Trustability Engine",
                        tint = when (trustLevel) {
                            TrustLevel.HIGH_TRUST -> MaterialTheme.colorScheme.tertiary
                            TrustLevel.MEDIUM_TRUST -> MaterialTheme.colorScheme.secondary
                            TrustLevel.LOW_TRUST -> MaterialTheme.colorScheme.error
                        },
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (isSimulated) "Simulated Trustability" else "Trustability Overview",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }

                StatusBadge(
                    text = trustLevel.displayName,
                    level = when (trustLevel) {
                        TrustLevel.HIGH_TRUST -> StatusLevel.SECURE
                        TrustLevel.MEDIUM_TRUST -> StatusLevel.WARNING
                        TrustLevel.LOW_TRUST -> StatusLevel.ALERT
                    }
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            TrustabilityGaugeMeter(
                score = score,
                trustLevel = trustLevel
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = trustLevel.description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 8.dp)
            )
        }
    }
}

@Composable
fun AntiSpoofingOverviewCard(
    trustLevel: TrustLevel?,
    isSimulated: Boolean,
    threatCount: Int,
    activeScenario: ThreatScenario,
    onSelectScenario: (ThreatScenario) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = when (trustLevel) {
                null, TrustLevel.HIGH_TRUST -> MaterialTheme.colorScheme.surfaceContainer
                TrustLevel.MEDIUM_TRUST -> MaterialTheme.colorScheme.surfaceContainerHigh
                TrustLevel.LOW_TRUST -> MaterialTheme.colorScheme.errorContainer
            }
        )
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = when (trustLevel) {
                        null -> Icons.Rounded.Shield
                        TrustLevel.HIGH_TRUST -> Icons.Rounded.GppGood
                        else -> Icons.Rounded.GppBad
                    },
                    contentDescription = null,
                    tint = when (trustLevel) {
                        null -> MaterialTheme.colorScheme.onSurfaceVariant
                        TrustLevel.HIGH_TRUST -> MaterialTheme.colorScheme.tertiary
                        TrustLevel.MEDIUM_TRUST -> MaterialTheme.colorScheme.secondary
                        TrustLevel.LOW_TRUST -> MaterialTheme.colorScheme.onErrorContainer
                    },
                    modifier = Modifier.size(38.dp)
                )
                Spacer(modifier = Modifier.width(14.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = when {
                            trustLevel == null -> "Evaluation pending"
                            isSimulated -> "Simulated assessment"
                            threatCount == 0 -> "No active anomalies"
                            else -> "Anomalies detected ($threatCount)"
                        },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (trustLevel == TrustLevel.LOW_TRUST) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = when {
                            trustLevel == null -> "Waiting for enough GNSS data to assess trust."
                            isSimulated -> "Anomaly indicators in this simulation: $threatCount"
                            threatCount == 0 -> "No anomaly indicators in the available measurements."
                            else -> "Review the event log for details."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = if (trustLevel == TrustLevel.LOW_TRUST) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                if (trustLevel != null) {
                    StatusBadge(
                        text = trustLevel.displayName,
                        level = when (trustLevel) {
                            TrustLevel.HIGH_TRUST -> StatusLevel.SECURE
                            TrustLevel.MEDIUM_TRUST -> StatusLevel.WARNING
                            TrustLevel.LOW_TRUST -> StatusLevel.ALERT
                        }
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "Simulated Threat Scenario",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = if (trustLevel == TrustLevel.LOW_TRUST) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.primary
            )

            Spacer(modifier = Modifier.height(8.dp))

            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(ThreatScenario.entries) { scenario ->
                    val isSelected = activeScenario == scenario
                    FilterChip(
                        selected = isSelected,
                        onClick = { onSelectScenario(scenario) },
                        label = { Text(scenario.displayName, fontSize = 12.sp) },
                        leadingIcon = if (isSelected) {
                            {
                                Icon(
                                    imageVector = Icons.Rounded.CheckCircle,
                                    contentDescription = null,
                                    modifier = Modifier.size(14.dp)
                                )
                            }
                        } else null
                    )
                }
            }
        }
    }
}

@Composable
fun DopGeometryBreakdownCard(
    hdop: Float,
    vdop: Float
) {
    val pdop = sqrt(hdop * hdop + vdop * vdop)
    val geometryRating = when {
        hdop <= 2.0f -> "EXCELLENT"
        hdop <= 3.5f -> "GOOD"
        hdop <= 5.0f -> "MODERATE"
        else -> "POOR GEOMETRY"
    }

    val ratingLevel = when {
        hdop <= 2.0f -> StatusLevel.SECURE
        hdop <= 5.0f -> StatusLevel.WARNING
        else -> StatusLevel.ALERT
    }

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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Rounded.Shield,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Dilution of Precision (DOP) Geometry",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold
                    )
                }

                StatusBadge(
                    text = geometryRating,
                    level = ratingLevel
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                DopMetricBox(
                    label = "HDOP (Horizontal)",
                    value = String.format(Locale.US, "%.2f", hdop),
                    status = if (hdop < 2.5) "Optimal Spread" else "Cluster Warning",
                    modifier = Modifier.weight(1f)
                )

                Spacer(modifier = Modifier.width(10.dp))

                DopMetricBox(
                    label = "VDOP (Vertical)",
                    value = String.format(Locale.US, "%.2f", vdop),
                    status = if (vdop < 3.0) "Vertical Fix Clear" else "High Uncertainty",
                    modifier = Modifier.weight(1f)
                )

                Spacer(modifier = Modifier.width(10.dp))

                DopMetricBox(
                    label = "PDOP (Position)",
                    value = String.format(Locale.US, "%.2f", pdop),
                    status = "Combined Geometry",
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
fun DopMetricBox(
    label: String,
    value: String,
    status: String,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHigh
    ) {
        Column(modifier = Modifier.padding(10.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 10.sp
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = status,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.tertiary,
                fontSize = 10.sp
            )
        }
    }
}

@Composable
fun OsnmaAuthenticationCard(osnmaStatus: OsnmaStatus) {
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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Rounded.Key,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.tertiary,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Galileo OSNMA",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold
                    )
                }

                val level = when (osnmaStatus) {
                    OsnmaStatus.VERIFIED -> StatusLevel.SECURE
                    OsnmaStatus.UNAUTHENTICATED -> StatusLevel.WARNING
                    OsnmaStatus.FAILED -> StatusLevel.ALERT
                    OsnmaStatus.SIMULATED_FAILURE -> StatusLevel.WARNING
                    OsnmaStatus.SIMULATED, OsnmaStatus.NOT_AVAILABLE -> StatusLevel.INFO
                }

                StatusBadge(
                    text = osnmaStatus.label,
                    level = level
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = osnmaStatus.description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(modifier = Modifier.height(10.dp))

            Surface(
                shape = RoundedCornerShape(10.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh
            ) {
                Column(modifier = Modifier.padding(10.dp)) {
                    Text(
                        text = "E1B Navigation Message Cryptography:",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Text(
                        text = "Session status: ${osnmaStatus.label}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }
        }
    }
}

@Composable
fun SubScoresBreakdownCard(subScores: TrustSubScores) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            SubScoreBarRow(label = "Signal Power & C/N0 (25%)", score = subScores.signalAuthenticityScore)
            SubScoreBarRow(label = "AGC & RF Interference (20%)", score = subScores.agcInterferenceScore)
            SubScoreBarRow(label = "Multi-Constellation Diversity (15%)", score = subScores.constellationDiversityScore)
            SubScoreBarRow(label = "Geometry & DOP (15%)", score = subScores.geometryDopScore)
            SubScoreBarRow(label = "Clock Drift & Stability (10%)", score = subScores.clockStabilityScore)
            SubScoreBarRow(label = "OSNMA Cryptographic Auth (15%)", score = subScores.osnmaAuthScore)
        }
    }
}

@Composable
fun SubScoreBarRow(label: String, score: Float) {
    val scoreClamped = score.coerceIn(0f, 100f)
    val color = when {
        scoreClamped >= 80f -> MaterialTheme.colorScheme.tertiary
        scoreClamped >= 50f -> MaterialTheme.colorScheme.secondary
        else -> MaterialTheme.colorScheme.error
    }

    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium
            )
            Text(
                text = "${scoreClamped.toInt()}%",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = color
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        LinearProgressIndicator(
            progress = { scoreClamped / 100f },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(3.dp)),
            color = color,
            trackColor = MaterialTheme.colorScheme.surfaceContainerHigh
        )
    }
}

@Composable
fun IntelligenceLogCard(entry: IntelligenceLogEntry) {
    val formatter = SimpleDateFormat("HH:mm:ss.SSS", Locale.US)
    val timeStr = formatter.format(Date(entry.timestampMillis))

    val statusLevel = when (entry.severity) {
        "SECURE" -> StatusLevel.SECURE
        "WARNING" -> StatusLevel.WARNING
        "ALERT" -> StatusLevel.ALERT
        else -> StatusLevel.INFO
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(14.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "[${entry.tag}] $timeStr",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                StatusBadge(
                    text = entry.severity,
                    level = statusLevel
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = entry.message,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
fun ThreatAnalysisScreenPreview() {
    TRISATTheme {
        ThreatAnalysisScreen()
    }
}
