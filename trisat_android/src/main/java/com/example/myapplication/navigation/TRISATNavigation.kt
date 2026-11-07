package com.example.myapplication.navigation

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Public
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.NavigationRailItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.window.core.layout.WindowWidthSizeClass
import com.example.myapplication.ui.components.TRISATTopBar
import com.example.myapplication.ui.screens.DashboardScreen
import com.example.myapplication.ui.screens.SettingsScreen
import com.example.myapplication.ui.screens.SignalMonitorScreen
import com.example.myapplication.ui.screens.ThreatAnalysisScreen
import com.example.myapplication.ui.viewmodel.GnssViewModel

@Suppress("DEPRECATION")
@Composable
fun TRISATMainApp() {
    val gnssViewModel: GnssViewModel = viewModel()
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) {
        gnssViewModel.gnssManager.refreshReceiverTrust()
    }

    var currentScreenRoute by rememberSaveable { mutableStateOf(Screen.Dashboard.route) }
    val currentScreen = Screen.items.find { it.route == currentScreenRoute } ?: Screen.Dashboard

    val windowAdaptiveInfo = currentWindowAdaptiveInfo()
    val isWideScreen = windowAdaptiveInfo.windowSizeClass.windowWidthSizeClass != WindowWidthSizeClass.COMPACT

    if (isWideScreen) {
        // Tablet / Large Screen / Wide Landscape Layout with Navigation Rail
        Row(modifier = Modifier.fillMaxSize()) {
            NavigationRail(
                containerColor = MaterialTheme.colorScheme.surfaceContainer,
                header = {
                    Surface(
                        modifier = Modifier.padding(vertical = 16.dp),
                        color = Color.Transparent
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                imageVector = Icons.Rounded.Public,
                                contentDescription = "TRISAT",
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(32.dp)
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "TRISAT",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.ExtraBold,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                }
            ) {
                Spacer(modifier = Modifier.weight(1f))
                Screen.items.forEach { screen ->
                    NavigationRailItem(
                        selected = currentScreenRoute == screen.route,
                        onClick = { currentScreenRoute = screen.route },
                        icon = { Icon(imageVector = screen.icon, contentDescription = screen.title) },
                        label = { Text(screen.title) },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.onPrimary,
                            selectedTextColor = MaterialTheme.colorScheme.primary,
                            indicatorColor = MaterialTheme.colorScheme.primary
                        )
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
            }

            Scaffold(
                topBar = { TRISATTopBar(currentScreen = currentScreen) },
                modifier = Modifier.weight(1f)
            ) { innerPadding ->
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                ) {
                    ScreenContent(
                        currentScreen = currentScreen,
                        onNavigate = { route -> currentScreenRoute = route }
                    )
                }
            }
        }
    } else {
        // Compact Screen Layout with Bottom Navigation Bar
        Scaffold(
            topBar = { TRISATTopBar(currentScreen = currentScreen) },
            bottomBar = {
                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surfaceContainer
                ) {
                    Screen.items.forEach { screen ->
                        NavigationBarItem(
                            selected = currentScreenRoute == screen.route,
                            onClick = { currentScreenRoute = screen.route },
                            icon = { Icon(imageVector = screen.icon, contentDescription = screen.title) },
                            label = {
                                Text(
                                    text = screen.title,
                                    fontSize = 11.sp,
                                    fontWeight = if (currentScreenRoute == screen.route) FontWeight.Bold else FontWeight.Normal
                                )
                            },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = MaterialTheme.colorScheme.onPrimary,
                                selectedTextColor = MaterialTheme.colorScheme.primary,
                                indicatorColor = MaterialTheme.colorScheme.primary
                            )
                        )
                    }
                }
            }
        ) { innerPadding ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
            ) {
                ScreenContent(
                    currentScreen = currentScreen,
                    onNavigate = { route -> currentScreenRoute = route }
                )
            }
        }
    }
}

@Composable
fun ScreenContent(
    currentScreen: Screen,
    onNavigate: (String) -> Unit
) {
    AnimatedContent(
        targetState = currentScreen,
        transitionSpec = { fadeIn() togetherWith fadeOut() },
        label = "screen_transition"
    ) { screen ->
        when (screen) {
            Screen.Dashboard -> DashboardScreen(
                onNavigateToSignal = { onNavigate(Screen.SignalMonitor.route) },
                onNavigateToThreats = { onNavigate(Screen.ThreatAnalysis.route) }
            )
            Screen.SignalMonitor -> SignalMonitorScreen()
            Screen.ThreatAnalysis -> ThreatAnalysisScreen()
            Screen.Settings -> SettingsScreen()
        }
    }
}
