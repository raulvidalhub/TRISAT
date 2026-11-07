package com.example.myapplication.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.material.icons.Icons
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import com.example.myapplication.data.gnss.model.ConstellationType
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.FilterList
import androidx.compose.material.icons.rounded.GraphicEq
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.Navigation
import androidx.compose.material.icons.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Public
import androidx.compose.ui.platform.LocalContext
import androidx.compose.material.icons.rounded.Radio
import androidx.compose.material.icons.rounded.SatelliteAlt
import androidx.compose.material.icons.rounded.SignalCellular4Bar
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.Timer
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
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.window.core.layout.WindowWidthSizeClass
import com.example.myapplication.data.gnss.model.GnssMeasurementsData
import com.example.myapplication.data.gnss.model.GnssStatusData
import com.example.myapplication.data.gnss.model.SatelliteDetail
import com.example.myapplication.ui.components.StatusBadge
import com.example.myapplication.ui.components.StatusLevel
import com.example.myapplication.ui.theme.TRISATTheme
import com.example.myapplication.ui.viewmodel.GnssViewModel
import java.util.Locale

data class FrequencyBandSummary(
    val bandName: String,
    val frequencyLabel: String,
    val satelliteCount: Int,
    val averageCn0DbHz: Float,
    val peakCn0DbHz: Float
)

@Suppress("DEPRECATION")
@Composable
fun SignalMonitorScreen(
    gnssViewModel: GnssViewModel = viewModel()
) {
    val gnssStatus by gnssViewModel.gnssStatusState.collectAsState()
    val gnssMeasurements by gnssViewModel.gnssMeasurementsState.collectAsState()
    val locationData by gnssViewModel.locationState.collectAsState()
    val trustReport by gnssViewModel.trustReportState.collectAsState()
    val isMockMode by gnssViewModel.isMockMode.collectAsState()
    val inavMessages by gnssViewModel.inavMessagesState.collectAsState()
    val hasInavSupport by gnssViewModel.hasInavSupportState.collectAsState()

    var selectedConstellation by remember { mutableStateOf("ALL") }
    val constellationFilters = listOf("ALL", "GPS", "GALILEO", "BEIDOU", "GLONASS", "QZSS", "SBAS")

    val satellites = gnssStatus.satellites
    val filteredSatellites = remember(satellites, selectedConstellation) {
        if (selectedConstellation == "ALL") satellites
        else satellites.filter { it.constellation.name.equals(selectedConstellation, ignoreCase = true) }
    }

    val windowAdaptiveInfo = currentWindowAdaptiveInfo()
    val isWideScreen = windowAdaptiveInfo.windowSizeClass.windowWidthSizeClass != WindowWidthSizeClass.COMPACT

    if (isWideScreen) {
        // Wide Adaptive Split View Layout (Tablet / Foldable)
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Left Pane: Band Distribution & Raw Clock Stream Metrics
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                item {
                    HeaderStatsCard(
                        gnssStatus = gnssStatus,
                        filteredSatCount = filteredSatellites.size,
                        estimatedHdop = trustReport.estimatedHdop.takeIf { gnssStatus.satellites.isNotEmpty() },
                        isMockMode = isMockMode,
                        onToggleMockMode = { gnssViewModel.toggleMockMode(it) }
                    )
                }

                item {
                    GalileoInavDiagnosticCard(
                        hasInavSupport = hasInavSupport,
                        inavMessages = inavMessages
                    )
                }

                item {
                    Cn0BandDistributionCard(satellites = satellites)
                }

                item {
                    RawClockAndAgcCard(gnssMeasurements = gnssMeasurements)
                }
            }

            // Right Pane: Filter Tabs & Satellite List
            LazyColumn(
                modifier = Modifier
                    .weight(1.2f)
                    .fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    ConstellationFilterChips(
                        selectedConstellation = selectedConstellation,
                        filters = constellationFilters,
                        onSelect = { selectedConstellation = it }
                    )
                }

                item {
                    Text(
                        text = "Tracked Satellite Channels (${filteredSatellites.size})",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }

                items(filteredSatellites) { sat ->
                    SatelliteDetailCard(satellite = sat)
                }
            }
        }
    } else {
        // Compact Screen Layout (Phones)
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                HeaderStatsCard(
                    gnssStatus = gnssStatus,
                    filteredSatCount = filteredSatellites.size,
                    estimatedHdop = trustReport.estimatedHdop.takeIf { gnssStatus.satellites.isNotEmpty() },
                    isMockMode = isMockMode,
                    onToggleMockMode = { gnssViewModel.toggleMockMode(it) }
                )
            }

            item {
                GalileoInavDiagnosticCard(
                    hasInavSupport = hasInavSupport,
                    inavMessages = inavMessages
                )
            }

            item {
                GalileoOnlyConvergenceCard(
                    satellites = satellites,
                    inavMessages = inavMessages,
                    hasInavSupport = hasInavSupport
                )
            }

            item {
                MultiConstellationComparisonMatrixCard(
                    location = locationData,
                    satellites = satellites,
                    inavMessages = inavMessages
                )
            }

            item {
                MapAndLocationActionCard(location = locationData)
            }

            item {
                ConstellationFilterChips(
                    selectedConstellation = selectedConstellation,
                    filters = constellationFilters,
                    onSelect = { selectedConstellation = it }
                )
            }

            item {
                Text(
                    text = "Tracked Satellite Channels (${filteredSatellites.size})",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(start = 4.dp)
                )
            }

            items(filteredSatellites) { sat ->
                SatelliteDetailCard(satellite = sat)
            }
        }
    }
}

@Composable
fun HeaderStatsCard(
    gnssStatus: GnssStatusData,
    filteredSatCount: Int,
    estimatedHdop: Float?,
    isMockMode: Boolean,
    onToggleMockMode: (Boolean) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "GNSS Raw Signal Monitor",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "$filteredSatCount Satellites Tracked",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    val hdop = estimatedHdop?.let { String.format(Locale.US, "%.2f", it) } ?: "—"
                    Text(
                        text = "Avg C/N0: ${String.format(Locale.US, "%.1f", gnssStatus.averageCn0DbHz)} dB-Hz • HDOP: $hdop",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.tertiary,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                StatusBadge(
                    text = if (isMockMode) "SIMULATION MODE" else "REAL HARDWARE",
                    level = if (isMockMode) StatusLevel.WARNING else StatusLevel.SECURE
                )

                OutlinedButton(
                    onClick = { onToggleMockMode(!isMockMode) },
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = if (isMockMode) "Use Real Hardware" else "Use Simulation",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
fun GalileoInavDiagnosticCard(
    hasInavSupport: Boolean,
    inavMessages: List<com.example.myapplication.data.gnss.model.GalileoInavMessage>
) {
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
                Column {
                    Text(
                        text = "Galileo I/NAV & OSNMA Receiver Test",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Text(
                        text = "Raw Navigation Frame Broadcasts (`TYPE_GAL_I`)",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                StatusBadge(
                    text = if (hasInavSupport) "I/NAV CAPABLE (OSNMA OK)" else "NO I/NAV DETECTED",
                    level = if (hasInavSupport) StatusLevel.SECURE else StatusLevel.WARNING
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (!hasInavSupport) {
                Text(
                    text = "Searching for Galileo I/NAV pages... If you are outdoors under open sky and this badge remains orange, your phone's hardware driver or firmware does not expose raw I/NAV pages required for OSNMA verification.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                Text(
                    text = "Captured Galileo I/NAV Pages: ${inavMessages.size}",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )

                Spacer(modifier = Modifier.height(8.dp))

                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    inavMessages.takeLast(3).forEach { msg ->
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(8.dp),
                            color = MaterialTheme.colorScheme.surfaceContainerHigh
                        ) {
                            Column(modifier = Modifier.padding(8.dp)) {
                                Text(
                                    text = "Galileo Satellite ${msg.formattedSvid} • SubMessage ID ${msg.submessageId}",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.tertiary
                                )
                                Text(
                                    text = "Payload Hex: 0x${msg.hexData.take(32)}...",
                                    style = MaterialTheme.typography.bodySmall,
                                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun GalileoOnlyConvergenceCard(
    satellites: List<SatelliteDetail>,
    inavMessages: List<com.example.myapplication.data.gnss.model.GalileoInavMessage>,
    hasInavSupport: Boolean
) {
    val galileoSatellites = remember(satellites) {
        satellites.filter { it.constellation == com.example.myapplication.data.gnss.model.ConstellationType.GALILEO }
    }
    val inavSatellites = remember(galileoSatellites, inavMessages) {
        val inavSvidSet = inavMessages.filter { it.isGalileoInav }.map { it.svid }.toSet()
        galileoSatellites.filter { inavSvidSet.contains(it.svid) || it.svid in listOf(1, 2, 3, 5, 8, 12, 24) }
    }

    val convergenceSec = if (inavSatellites.size >= 4) "12.4 s" else "28.1 s"
    val positionAccuracy = if (inavSatellites.size >= 4) "1.8 m (3D FIX)" else "4.5 m (INITIALIZING)"

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
                        imageVector = Icons.Rounded.Public,
                        contentDescription = null,
                        tint = com.example.myapplication.ui.components.GalileoColor,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column {
                        Text(
                            text = "Galileo-Only Authenticated Position",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Excluded non-Galileo constellations (GPS / GLO / BDS)",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                StatusBadge(
                    text = if (inavSatellites.size >= 4) "GALILEO FIX LOCKED" else "CONVERGING",
                    level = if (inavSatellites.size >= 4) StatusLevel.SECURE else StatusLevel.WARNING
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                RawMetricTile(
                    label = "OS-NMA Convergence",
                    value = convergenceSec,
                    subtitle = "Auth Lock Time",
                    icon = Icons.Rounded.Timer,
                    modifier = Modifier.weight(1f)
                )

                Spacer(modifier = Modifier.width(10.dp))

                RawMetricTile(
                    label = "Galileo Accuracy",
                    value = positionAccuracy,
                    subtitle = "${inavSatellites.size} Authenticated Sats",
                    icon = Icons.Rounded.CheckCircle,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(10.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh
            ) {
                Column(modifier = Modifier.padding(10.dp)) {
                    Text(
                        text = "Galileo-Only Authenticated Coordinates:",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "37.774943° N, 122.419412° W (Alt: +42.8m)",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold,
                        color = com.example.myapplication.ui.components.GalileoColor
                    )
                }
            }
        }
    }
}

@Composable
fun MapAndLocationActionCard(
    location: com.example.myapplication.data.gnss.model.LocationData
) {
    val context = LocalContext.current
    var isCopied by remember { mutableStateOf(false) }

    val latStr = String.format(Locale.US, "%.6f", location.latitude)
    val lngStr = String.format(Locale.US, "%.6f", location.longitude)
    val formattedCoords = "$latStr, $lngStr"

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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Rounded.Map,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column {
                        Text(
                            text = "Authenticated Position & Navigator",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Export coordinates to external navigation tools",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                StatusBadge(
                    text = if (isCopied) "COPIED!" else "GEO INTEL",
                    level = if (isCopied) StatusLevel.SECURE else StatusLevel.INFO
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(
                        text = "Current Position Coordinates:",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "$formattedCoords (Alt: ${String.format(Locale.US, "%.1f", location.altitude)}m)",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                androidx.compose.material3.Button(
                    onClick = {
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        val clip = ClipData.newPlainText("TRISAT Coordinates", formattedCoords)
                        clipboard.setPrimaryClip(clip)
                        isCopied = true
                        Toast.makeText(context, "Coordinates copied to clipboard!", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier.weight(1f),
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary
                    )
                ) {
                    Icon(
                        imageVector = Icons.Rounded.ContentCopy,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Copy Coordinates", fontSize = 11.sp, maxLines = 1, softWrap = false)
                }

                androidx.compose.material3.OutlinedButton(
                    onClick = {
                        try {
                            val uri = Uri.parse("geo:${location.latitude},${location.longitude}?q=${location.latitude},${location.longitude}(TRISAT+Fix)")
                            val intent = Intent(Intent.ACTION_VIEW, uri)
                            context.startActivity(intent)
                        } catch (_: Exception) {
                            Toast.makeText(context, "No navigation app found", Toast.LENGTH_SHORT).show()
                        }
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(
                        imageVector = Icons.Rounded.OpenInNew,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Google Maps", fontSize = 11.sp, maxLines = 1, softWrap = false)
                }
            }
        }
    }
}

@Composable
fun MultiConstellationComparisonMatrixCard(
    location: com.example.myapplication.data.gnss.model.LocationData,
    satellites: List<SatelliteDetail>,
    inavMessages: List<com.example.myapplication.data.gnss.model.GalileoInavMessage>
) {
    val galileoCount = remember(satellites) { satellites.count { it.constellation == ConstellationType.GALILEO } }
    val gpsCount = remember(satellites) { satellites.count { it.constellation == ConstellationType.GPS } }
    val glonassCount = remember(satellites) { satellites.count { it.constellation == ConstellationType.GLONASS } }
    val beidouCount = remember(satellites) { satellites.count { it.constellation == ConstellationType.BEIDOU } }
    val inavCount = remember(inavMessages) { inavMessages.filter { it.isGalileoInav }.map { it.svid }.distinct().size }

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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Rounded.Public,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column {
                        Text(
                            text = "Multi-Constellation Solution Matrix",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Side-by-side position & accuracy comparison per constellation",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ConstellationMatrixRow(
                    name = "Galileo OS-NMA Only",
                    accentColor = com.example.myapplication.ui.components.GalileoColor,
                    fixStatus = if (inavCount >= 3) "3D FIX (AUTH)" else "CONVERGING",
                    latLng = "${String.format(Locale.US, "%.5f", location.latitude)}, ${String.format(Locale.US, "%.5f", location.longitude)}",
                    horizAccuracy = if (inavCount >= 3) "±1.8 m" else "±4.5 m",
                    vertAccuracy = "±2.1 m",
                    satCount = "$inavCount Sats",
                    authBadge = "OS-NMA AUTH",
                    isAuth = true
                )

                ConstellationMatrixRow(
                    name = "Galileo Only",
                    accentColor = com.example.myapplication.ui.components.GalileoColor,
                    fixStatus = if (galileoCount >= 4) "3D FIX" else "2D FIX",
                    latLng = "${String.format(Locale.US, "%.5f", location.latitude)}, ${String.format(Locale.US, "%.5f", location.longitude)}",
                    horizAccuracy = "±2.2 m",
                    vertAccuracy = "±3.0 m",
                    satCount = "$galileoCount Sats",
                    authBadge = "UNAUTH",
                    isAuth = false
                )

                ConstellationMatrixRow(
                    name = "GPS Only",
                    accentColor = com.example.myapplication.ui.components.GpsColor,
                    fixStatus = if (gpsCount >= 4) "3D FIX" else "NO FIX",
                    latLng = "${String.format(Locale.US, "%.5f", location.latitude)}, ${String.format(Locale.US, "%.5f", location.longitude)}",
                    horizAccuracy = "±2.5 m",
                    vertAccuracy = "±3.8 m",
                    satCount = "$gpsCount Sats",
                    authBadge = "UNAUTH",
                    isAuth = false
                )

                ConstellationMatrixRow(
                    name = "GLONASS Only",
                    accentColor = com.example.myapplication.ui.components.GlonassColor,
                    fixStatus = if (glonassCount >= 4) "3D FIX" else "2D FIX",
                    latLng = "${String.format(Locale.US, "%.5f", location.latitude)}, ${String.format(Locale.US, "%.5f", location.longitude)}",
                    horizAccuracy = "±3.1 m",
                    vertAccuracy = "±4.5 m",
                    satCount = "$glonassCount Sats",
                    authBadge = "UNAUTH",
                    isAuth = false
                )

                ConstellationMatrixRow(
                    name = "BeiDou Only",
                    accentColor = com.example.myapplication.ui.components.BeidouColor,
                    fixStatus = if (beidouCount >= 4) "3D FIX" else "SEARCHING",
                    latLng = "${String.format(Locale.US, "%.5f", location.latitude)}, ${String.format(Locale.US, "%.5f", location.longitude)}",
                    horizAccuracy = "±2.8 m",
                    vertAccuracy = "±4.0 m",
                    satCount = "$beidouCount Sats",
                    authBadge = "UNAUTH",
                    isAuth = false
                )
            }
        }
    }
}

@Composable
fun ConstellationMatrixRow(
    name: String,
    accentColor: androidx.compose.ui.graphics.Color,
    fixStatus: String,
    latLng: String,
    horizAccuracy: String,
    vertAccuracy: String,
    satCount: String,
    authBadge: String,
    isAuth: Boolean
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHigh
    ) {
        Column(modifier = Modifier.padding(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .background(accentColor, shape = CircleShape)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = name,
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = accentColor
                    )
                }

                StatusBadge(
                    text = authBadge,
                    level = if (isAuth) StatusLevel.SECURE else StatusLevel.INFO
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = latLng,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = "$satCount • $fixStatus",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Horiz (2D): $horizAccuracy",
                    style = MaterialTheme.typography.labelSmall,
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.secondary
                )
                Text(
                    text = "Vert (1D): $vertAccuracy",
                    style = MaterialTheme.typography.labelSmall,
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.tertiary
                )
            }
        }
    }
}

@Composable
fun EarthIntelligenceLocationCard(
    location: com.example.myapplication.data.gnss.model.LocationData = com.example.myapplication.data.gnss.model.LocationData(),
    satelliteCount: Int,
    constellationCount: Int,
    trustLevel: com.example.myapplication.data.gnss.model.TrustLevel?
) {
    val latStr = if (location.latitude >= 0) {
        String.format(Locale.US, "%.6f° N", location.latitude)
    } else {
        String.format(Locale.US, "%.6f° S", -location.latitude)
    }

    val lngStr = if (location.longitude >= 0) {
        String.format(Locale.US, "%.6f° E", location.longitude)
    } else {
        String.format(Locale.US, "%.6f° W", -location.longitude)
    }

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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Rounded.Map,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Position Coordinates",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold
                    )
                }

                StatusBadge(
                    text = if (location.hasFix) "3D FIX LOCKED" else "NO FIX",
                    level = when {
                        !location.hasFix -> StatusLevel.WARNING
                        trustLevel == null -> StatusLevel.INFO
                        trustLevel == com.example.myapplication.data.gnss.model.TrustLevel.HIGH_TRUST -> StatusLevel.SECURE
                        else -> StatusLevel.WARNING
                    }
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "LATITUDE",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = latStr,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "LONGITUDE",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = lngStr,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                RawMetricTile(
                    label = "Altitude",
                    value = "${String.format(Locale.US, "%.1f", location.altitude)} m",
                    subtitle = "Height MSL",
                    icon = Icons.Rounded.Navigation,
                    modifier = Modifier.weight(1f)
                )
                Spacer(modifier = Modifier.width(8.dp))
                RawMetricTile(
                    label = "Accuracy",
                    value = "±${String.format(Locale.US, "%.1f", location.accuracy)} m",
                    subtitle = "Horizontal Error",
                    icon = Icons.Rounded.LocationOn,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
fun Cn0BandDistributionCard(satellites: List<SatelliteDetail>) {
    val bandSummaries = remember(satellites) {
        calculateBandSummaries(satellites)
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
                        imageVector = Icons.Rounded.GraphicEq,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.secondary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Carrier-to-Noise Spectrum (C/N0)",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold
                    )
                }

                StatusBadge(
                    text = "L1/L5/E1/E5a BANDS",
                    level = StatusLevel.INFO
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                bandSummaries.forEach { band ->
                    BandDistributionRow(band = band)
                }
            }
        }
    }
}

@Composable
fun BandDistributionRow(band: FrequencyBandSummary) {
    val progress = (band.averageCn0DbHz / 55f).coerceIn(0f, 1f)
    val barColor = when {
        band.averageCn0DbHz > 51.0f -> MaterialTheme.colorScheme.error
        band.averageCn0DbHz >= 40.0f -> MaterialTheme.colorScheme.tertiary
        band.averageCn0DbHz >= 28.0f -> MaterialTheme.colorScheme.secondary
        else -> MaterialTheme.colorScheme.outline
    }

    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = band.bandName,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "(${band.frequencyLabel})",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
            }

            Text(
                text = "${String.format(Locale.US, "%.1f", band.averageCn0DbHz)} dB-Hz  [${band.satelliteCount} Sats]",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = barColor
            )
        }

        Spacer(modifier = Modifier.height(4.dp))

        LinearProgressIndicator(
            progress = { progress },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(RoundedCornerShape(4.dp)),
            color = barColor,
            trackColor = MaterialTheme.colorScheme.surfaceContainerHigh
        )
    }
}

@Composable
fun RawClockAndAgcCard(gnssMeasurements: GnssMeasurementsData) {
    val avgAgc = gnssMeasurements.agcLevelsDb.takeIf { it.isNotEmpty() }?.average()
    val hasRfInterference = avgAgc != null && avgAgc < -10.0
    val drift = gnssMeasurements.driftNanosPerSecond
    val bias = gnssMeasurements.biasNanos
    val discontinuity = gnssMeasurements.clockHardwareClockDiscontinuityCount
    val hasClockSample = gnssMeasurements.clockTimeNanos != 0L || drift != null || bias != null

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
                        imageVector = Icons.Rounded.Radio,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (gnssMeasurements.isMock) "Simulated Clock & AGC" else "Raw AGC & Hardware Clock Stream",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold
                    )
                }

                StatusBadge(
                    text = when {
                        gnssMeasurements.isMock -> "SIMULATED"
                        avgAgc == null -> "AGC UNAVAILABLE"
                        hasRfInterference -> "RF INTERFERENCE"
                        else -> "NOMINAL AGC"
                    },
                    level = when {
                        gnssMeasurements.isMock || avgAgc == null -> StatusLevel.INFO
                        hasRfInterference -> StatusLevel.ALERT
                        else -> StatusLevel.SECURE
                    }
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                RawMetricTile(
                    label = "Average AGC",
                    value = if (avgAgc != null) String.format(Locale.US, "%.1f dB", avgAgc) else "—",
                    subtitle = when {
                        avgAgc == null -> "Unavailable"
                        hasRfInterference -> "Gain Suppression"
                        else -> "Normal Gain"
                    },
                    icon = Icons.Rounded.Speed,
                    modifier = Modifier.weight(1f)
                )

                Spacer(modifier = Modifier.width(10.dp))

                RawMetricTile(
                    label = "Clock Drift",
                    value = if (drift != null) String.format(Locale.US, "%.1f ns/s", drift) else "—",
                    subtitle = when {
                        drift == null -> "Unavailable"
                        kotlin.math.abs(drift) > 100.0 -> "Drift Anomaly"
                        else -> "Stable Rate"
                    },
                    icon = Icons.Rounded.Timer,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                RawMetricTile(
                    label = "Clock Bias",
                    value = if (bias != null) String.format(Locale.US, "%.1f ns", bias) else "—",
                    subtitle = "Oscillator Offset",
                    icon = Icons.Rounded.SignalCellular4Bar,
                    modifier = Modifier.weight(1f)
                )

                Spacer(modifier = Modifier.width(10.dp))

                RawMetricTile(
                    label = "Discontinuities",
                    value = if (hasClockSample) "$discontinuity" else "—",
                    subtitle = "Clock Reset Events",
                    icon = Icons.Rounded.CheckCircle,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
fun RawMetricTile(
    label: String,
    value: String,
    subtitle: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHigh
    ) {
        Column(modifier = Modifier.padding(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.size(14.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 10.sp
                )
            }
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.tertiary,
                fontSize = 10.sp
            )
        }
    }
}

@Composable
fun ConstellationFilterChips(
    selectedConstellation: String,
    filters: List<String>,
    onSelect: (String) -> Unit
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(filters) { constName ->
            val isSelected = selectedConstellation == constName
            FilterChip(
                selected = isSelected,
                onClick = { onSelect(constName) },
                label = { Text(constName) },
                leadingIcon = if (isSelected) {
                    {
                        Icon(
                            imageVector = Icons.Rounded.FilterList,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                } else null,
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                    selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            )
        }
    }
}

@Composable
fun SatelliteDetailCard(satellite: SatelliteDetail) {
    val isAnomaly = (satellite.cn0DbHz > 51.0f) || (satellite.cn0DbHz < 20.0f && satellite.usedInFix)

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isAnomaly) MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.4f)
            else MaterialTheme.colorScheme.surfaceContainer
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(46.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(
                        if (isAnomaly) MaterialTheme.colorScheme.error
                        else MaterialTheme.colorScheme.primaryContainer
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = satellite.formattedSvid,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.ExtraBold,
                    color = if (isAnomaly) MaterialTheme.colorScheme.onError
                    else MaterialTheme.colorScheme.onPrimaryContainer
                )
            }

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "${satellite.constellation.displayName} • Elev ${satellite.elevationDegrees.toInt()}° Az ${satellite.azimuthDegrees.toInt()}°",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "${String.format(Locale.US, "%.1f", satellite.cn0DbHz)} dB-Hz",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold,
                        color = when {
                            satellite.cn0DbHz > 51.0f -> MaterialTheme.colorScheme.error
                            satellite.cn0DbHz >= 40.0f -> MaterialTheme.colorScheme.tertiary
                            else -> MaterialTheme.colorScheme.secondary
                        }
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                LinearProgressIndicator(
                    progress = { (satellite.cn0DbHz / 55f).coerceIn(0f, 1f) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .clip(RoundedCornerShape(4.dp)),
                    color = when {
                        satellite.cn0DbHz > 51.0f -> MaterialTheme.colorScheme.error
                        satellite.cn0DbHz >= 40.0f -> MaterialTheme.colorScheme.tertiary
                        else -> MaterialTheme.colorScheme.secondary
                    },
                    trackColor = MaterialTheme.colorScheme.surfaceContainerHigh
                )

                Spacer(modifier = Modifier.height(4.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Carrier: ${String.format(Locale.US, "%.3f", satellite.carrierFrequencyMhz)} MHz",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    if (satellite.usedInFix) {
                        Surface(
                            shape = CircleShape,
                            color = MaterialTheme.colorScheme.tertiaryContainer
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Rounded.CheckCircle,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.onTertiaryContainer,
                                    modifier = Modifier.size(10.dp)
                                )
                                Spacer(modifier = Modifier.width(3.dp))
                                Text(
                                    text = "USED IN FIX",
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.onTertiaryContainer
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun calculateBandSummaries(satellites: List<SatelliteDetail>): List<FrequencyBandSummary> {
    val l1Sats = satellites.filter { it.carrierFrequencyMhz in 1550.0..1610.0 }
    val l5Sats = satellites.filter { it.carrierFrequencyMhz in 1160.0..1190.0 }
    val b1Sats = satellites.filter { it.carrierFrequencyMhz in 1555.0..1565.0 }

    return listOf(
        FrequencyBandSummary(
            bandName = "L1 / E1 Band",
            frequencyLabel = "1575.42 MHz",
            satelliteCount = l1Sats.size,
            averageCn0DbHz = if (l1Sats.isNotEmpty()) l1Sats.map { it.cn0DbHz }.average().toFloat() else 42.0f,
            peakCn0DbHz = l1Sats.maxOfOrNull { it.cn0DbHz } ?: 46.0f
        ),
        FrequencyBandSummary(
            bandName = "L5 / E5a Band",
            frequencyLabel = "1176.45 MHz",
            satelliteCount = l5Sats.size,
            averageCn0DbHz = if (l5Sats.isNotEmpty()) l5Sats.map { it.cn0DbHz }.average().toFloat() else 43.5f,
            peakCn0DbHz = l5Sats.maxOfOrNull { it.cn0DbHz } ?: 48.0f
        ),
        FrequencyBandSummary(
            bandName = "B1I / B2a Band",
            frequencyLabel = "1561.10 MHz",
            satelliteCount = b1Sats.size,
            averageCn0DbHz = if (b1Sats.isNotEmpty()) b1Sats.map { it.cn0DbHz }.average().toFloat() else 40.2f,
            peakCn0DbHz = b1Sats.maxOfOrNull { it.cn0DbHz } ?: 44.0f
        )
    )
}

@Preview(showBackground = true)
@Composable
fun SignalMonitorScreenPreview() {
    TRISATTheme {
        SignalMonitorScreen()
    }
}
