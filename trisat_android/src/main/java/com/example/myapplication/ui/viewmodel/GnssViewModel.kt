package com.example.myapplication.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.data.gnss.model.GalileoInavMessage
import com.example.myapplication.data.gnss.model.GnssMeasurementsData
import com.example.myapplication.data.gnss.model.GnssReceiverMode
import com.example.myapplication.data.gnss.model.GnssStatusData
import com.example.myapplication.data.gnss.model.LocationData
import com.example.myapplication.data.gnss.model.ThreatScenario
import com.example.myapplication.data.gnss.model.TrustReport
import com.example.myapplication.data.gnss.repository.LocationGnssManager
import com.example.myapplication.data.gnss.tle.TleDownloader
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class GnssViewModel(application: Application) : AndroidViewModel(application) {

    val gnssManager = LocationGnssManager(application)

    val receiverMode: StateFlow<GnssReceiverMode> = gnssManager.receiverMode
    val timeOffsetHours: StateFlow<Float> = gnssManager.timeOffsetHours
    val tleDownloader: TleDownloader = gnssManager.tleDownloader

    val gnssStatusState: StateFlow<GnssStatusData> = gnssManager.gnssStatusData
    val gnssMeasurementsState: StateFlow<GnssMeasurementsData> = gnssManager.gnssMeasurementsData
    val inavMessagesState: StateFlow<List<GalileoInavMessage>> = gnssManager.inavMessages
    val hasInavSupportState: StateFlow<Boolean> = gnssManager.hasInavSupport
    val locationState: StateFlow<LocationData> = gnssManager.locationData
    val positionHistoryState: StateFlow<List<LocationData>> = gnssManager.positionHistory
    val lastAGnssResetTimeState: StateFlow<Long> = gnssManager.lastAGnssResetTime
    val trustReportState: StateFlow<TrustReport> = gnssManager.trustReportData
    val activeScenarioState: StateFlow<ThreatScenario> = gnssManager.activeScenario
    val isMockMode: StateFlow<Boolean> = gnssManager.isMockMode
    val isMonitoringActive: StateFlow<Boolean> = gnssManager.isMonitoringActive
    internal val externalUdpStatus = gnssManager.externalUdpStatus
    val permissionGranted: StateFlow<Boolean> = gnssManager.permissionGranted
    val isBleServerActive: StateFlow<Boolean> = gnssManager.isBleServerActive

    init {
        gnssManager.startMonitoring()
    }

    fun startMonitoring() {
        gnssManager.startMonitoring()
    }

    fun stopMonitoring() {
        gnssManager.stopMonitoring()
    }

    fun setReceiverMode(mode: GnssReceiverMode) {
        gnssManager.setReceiverMode(mode)
    }

    fun setTimeOffsetHours(offset: Float) {
        gnssManager.setTimeOffsetHours(offset)
    }

    fun fetchTleOrbits() {
        viewModelScope.launch {
            tleDownloader.fetchAllTleOrbits()
            if (receiverMode.value == GnssReceiverMode.SIMULATION_TLE) {
                gnssManager.updateTleSimulation()
            }
        }
    }

    fun toggleMockMode(forceMock: Boolean) {
        gnssManager.setForceMockMode(forceMock)
    }

    fun toggleBleServer(enable: Boolean): Boolean {
        return gnssManager.toggleBleServer(enable)
    }

    fun selectThreatScenario(scenario: ThreatScenario) {
        gnssManager.setThreatScenario(scenario)
    }

    fun recalibrate() {
        gnssManager.resetAGnssData()
    }

    fun resetAGnssData() {
        gnssManager.resetAGnssData()
    }

    fun clearPositionHistory() {
        gnssManager.clearPositionHistory()
    }

    fun refreshPermissions() {
        gnssManager.hasLocationPermission()
    }

    override fun onCleared() {
        gnssManager.stopMonitoring()
    }
}
