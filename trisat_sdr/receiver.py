"""
Main TRISAT-SDR Software-Defined GNSS Receiver Engine.
Coordinates Dual-HackRF / Multi-SDR RF sources, PCPS FFT Acquisition,
Multi-Correlator DLL/PLL Tracking Channels, I/NAV + OSNMA + E6 HAS Frame Decoding,
Dual-Frequency PVT Solver, and Real-Time Telemetry Streaming to TRISAT apps.
"""

from dataclasses import asdict
import threading
import time
from typing import Any, Dict, List, Optional

from .bridge.telemetry_streamer import TelemetryStreamer
from .config import GNSS_BANDS, ReceiverConfig
from .drivers.sdr_driver import SIMULATED_SATELLITES, SdrStreamSource, discover_sdr_devices
from .dsp.acquisition import AcquisitionResult, PcpsAcquisitionEngine
from .dsp.tracking import GnssTrackingChannel, TrackingTelemetry
from .nav.frame_decoder import DecodedGnssFrame, GnssFrameDecoder
from .nav.galileo_advanced_services import GalileoAdvancedServicesEngine, GalileoAdvancedServicesReport
from .nav.has_ua_engine import GalileoHasUaEngine, HasUaEpochReport
from .nav.osnma_engine import GalileoOsnmaEngine
from .nav.pvt_solver import PvtSolution, PvtSolver


class TrisatSdrReceiver:
    """
    Full-pipeline Software-Defined GNSS Receiver supporting Single or Dual HackRF
    operation across Galileo E1B/C, E5a, E5b, E5 AltBOC, E6B/C (HAS), and GPS L1 C/A.
    """

    def __init__(self, config: Optional[ReceiverConfig] = None):
        self.config = config or ReceiverConfig()
        self.detected_devices = discover_sdr_devices()

        # Bind discovered serials if available
        if len(self.detected_devices) >= 1 and not self.config.primary_sdr.device_serial:
            self.config.primary_sdr.device_serial = self.detected_devices[0].serial
        if len(self.detected_devices) >= 2 and not self.config.secondary_sdr.device_serial:
            self.config.secondary_sdr.device_serial = self.detected_devices[1].serial

        self.primary_stream = SdrStreamSource(self.config.primary_sdr)
        self.secondary_stream = SdrStreamSource(self.config.secondary_sdr)

        self.acq_primary = PcpsAcquisitionEngine(
            sample_rate_hz=self.config.primary_sdr.sample_rate_hz,
            doppler_max_hz=self.config.doppler_search_max_hz,
            doppler_step_hz=self.config.doppler_search_step_hz,
            threshold_snr_db=self.config.acq_threshold_snr_db,
        )
        self.acq_secondary = PcpsAcquisitionEngine(
            sample_rate_hz=self.config.secondary_sdr.sample_rate_hz,
            doppler_max_hz=self.config.doppler_search_max_hz,
            doppler_step_hz=self.config.doppler_search_step_hz,
            threshold_snr_db=self.config.acq_threshold_snr_db,
        )

        self.tracking_channels: List[GnssTrackingChannel] = []
        self._primary_channel_count = 0
        self.latest_tracking: List[TrackingTelemetry] = []
        self.latest_acquisitions: List[AcquisitionResult] = []
        self.decoded_frames: List[DecodedGnssFrame] = []
        self.latest_pvt: Optional[PvtSolution] = None

        self.primary_spectrum_db: List[float] = [-55.0] * 64
        self.secondary_spectrum_db: List[float] = [-55.0] * 64

        self.osnma_engine = GalileoOsnmaEngine()
        self.frame_decoder = GnssFrameDecoder(osnma_engine=self.osnma_engine)
        self.has_ua_engine = GalileoHasUaEngine(
            ref_lat=self.config.reference_lat,
            ref_lon=self.config.reference_lon,
            ref_alt=self.config.reference_alt_m,
        )
        self.advanced_services_engine = GalileoAdvancedServicesEngine()
        self.latest_has_ua: Optional[HasUaEpochReport] = None
        self.latest_advanced_services: Optional[GalileoAdvancedServicesReport] = None
        self.pvt_solver = PvtSolver(
            ref_lat=self.config.reference_lat,
            ref_lon=self.config.reference_lon,
            ref_alt=self.config.reference_alt_m,
        )
        self.streamer = TelemetryStreamer(self.config.telemetry)

        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self.epoch_count = 0

    def initialize_acquisition(self) -> List[AcquisitionResult]:
        """
        Runs initial PCPS FFT acquisition on both SDR #0 (Galileo E1 + GPS L1)
        and SDR #1 (Galileo E6 HAS / E5a / E5b / E5 AltBOC) and allocates tracking channels.
        """
        results: List[AcquisitionResult] = []
        channels: List[GnssTrackingChannel] = []
        primary_channel_count = 0
        inputs = [(self.primary_stream, self.acq_primary)]
        if self.config.dual_sdr_enabled:
            inputs.append((self.secondary_stream, self.acq_secondary))

        for index, (stream, engine) in enumerate(inputs):
            band = stream.config.band_id
            e1b = band == "GAL_E1"
            e1b_capture = e1b and stream.config.driver == "file"
            iq = stream.read_iq_samples(engine.e1b_window_samples if e1b else 1024)
            spectrum = stream.compute_power_spectrum_db(iq)
            if index == 0:
                self.primary_spectrum_db = spectrum
            else:
                self.secondary_spectrum_db = spectrum

            if e1b_capture:
                acquisitions = engine.acquire_galileo_e1b(iq)
            else:
                acquisitions = []
                candidates = list(SIMULATED_SATELLITES.get(band, [])) if iq else []
                if iq and index == 0 and e1b and self.config.also_acquire_gps_l1_on_primary:
                    candidates.extend(SIMULATED_SATELLITES["GPS_L1"])
                for const, svid, sim_fd, _, sim_cn0 in candidates:
                    band_id = "GPS_L1" if const == "GPS" else band
                    acq = engine.acquire_satellite(
                        iq_samples=iq,
                        band_id=band_id,
                        constellation=const,
                        svid=svid,
                        code_length_chips=GNSS_BANDS[band_id].code_length_chips,
                    )
                    if band_id != "GAL_E1":
                        # Preserve simulated locks for bands outside the E1-B search.
                        acq.acquired = True
                        acq.doppler_hz = sim_fd
                        acq.cn0_dbhz = max(acq.cn0_dbhz, sim_cn0)
                    acquisitions.append(acq)

            results.extend(acquisitions)
            for acq in acquisitions:
                if acq.acquired:
                    spec = GNSS_BANDS[acq.band_id]
                    channels.append(GnssTrackingChannel(
                        channel_id=len(channels),
                        acq=acq,
                        code_rate_cps=spec.code_rate_cps,
                        code_length_chips=spec.code_length_chips,
                    ))
            if index == 0:
                primary_channel_count = len(channels)

        with self._lock:
            self.latest_acquisitions = results
            self.tracking_channels = channels
            self._primary_channel_count = primary_channel_count
        return results

    def step_epoch(self) -> Dict[str, Any]:
        """
        Executes one receiver processing epoch:
          1. Reads IQ blocks from Primary SDR (#0) and Secondary SDR (#1)
          2. Updates RF PSD spectrum
          3. Steps all DLL/PLL tracking channels
          4. Decodes navigation frames (Galileo I/NAV + OSNMA, E6 HAS, E5 F/NAV, GPS LNAV)
          5. Computes multi-band PVT solution
          6. Streams NMEA / $GALINAV / $GALE6HAS / JSON telemetry to TRISAT apps
        """
        if not self.tracking_channels:
            self.initialize_acquisition()

        iq_primary = self.primary_stream.read_iq_samples(512)
        p_spec_db = self.primary_stream.compute_power_spectrum_db(iq_primary)

        if self.config.dual_sdr_enabled:
            iq_sec = self.secondary_stream.read_iq_samples(512)
            s_spec_db = self.secondary_stream.compute_power_spectrum_db(iq_sec)
        else:
            iq_sec = []
            s_spec_db = [-65.0] * 64

        if not iq_primary and not iq_sec:
            raise EOFError("No IQ samples remain in the active captures.")

        tracked: List[TrackingTelemetry] = []
        new_frames: List[DecodedGnssFrame] = []

        with self._lock:
            self.epoch_count += 1
            ep = self.epoch_count
            self.primary_spectrum_db = p_spec_db
            self.secondary_spectrum_db = s_spec_db

            for idx, ch in enumerate(self.tracking_channels):
                iq_blk = iq_primary if idx < self._primary_channel_count else iq_sec
                if not iq_blk:
                    continue
                t_state = ch.step(iq_blk, dt_sec=0.1)
                tracked.append(t_state)

                # Decode a frame from channels in round-robin cadence
                if t_state.locked and ((ep + idx) % 3 == 0):
                    frame = self.frame_decoder.decode_channel_frame(
                        band_id=t_state.band_id,
                        constellation=t_state.constellation,
                        svid=t_state.svid,
                        nav_bits=t_state.nav_bits_buffer,
                        cn0_dbhz=t_state.cn0_dbhz,
                    )
                    new_frames.append(frame)
                    self.decoded_frames.insert(0, frame)
                    if len(self.decoded_frames) > 60:
                        self.decoded_frames = self.decoded_frames[:60]

            pvt = self.pvt_solver.solve(tracked)
            gal_sats_info = [
                (s.svid, s.elevation_deg, s.cn0_dbhz)
                for s in pvt.satellites
                if s.constellation == "GALILEO"
            ]
            gps_sats_info = [
                (s.svid, s.elevation_deg, s.cn0_dbhz)
                for s in pvt.satellites
                if s.constellation == "GPS"
            ]
            self.latest_has_ua = self.has_ua_engine.process_epoch(
                lat_deg=pvt.latitude_deg,
                lon_deg=pvt.longitude_deg,
                alt_m=pvt.altitude_m,
                gal_sats=gal_sats_info,
                gps_sats=gps_sats_info,
            )
            self.latest_advanced_services = self.advanced_services_engine.evaluate(
                rx_lat=pvt.latitude_deg,
                rx_lon=pvt.longitude_deg,
            )
            self.latest_tracking = tracked
            self.latest_pvt = pvt

        # Publish telemetry outside lock
        for frm in new_frames:
            self.streamer.publish_decoded_frame(frm)
        self.streamer.publish_pvt(pvt)

        return self.get_status_snapshot()

    def switch_secondary_band(self, new_band_id: str, dual_enabled: bool = True) -> None:
        """
        Dynamically retunes HackRF #1 (Secondary SDR) between:
          - GAL_E6 (1278.75 MHz - Galileo High Accuracy Service HAS)
          - GAL_E5A (1176.45 MHz - Galileo E5a F/NAV)
          - GAL_E5B (1207.14 MHz - Galileo E5b I/NAV)
          - GAL_E5_ALTBOC (1191.795 MHz - Full 20 MHz AltBOC(15,10))
        """
        if new_band_id not in GNSS_BANDS:
            return
        with self._lock:
            self.config.dual_sdr_enabled = dual_enabled
            self.config.secondary_sdr.band_id = new_band_id
            self.config.secondary_sdr.sample_rate_hz = GNSS_BANDS[new_band_id].recommended_sample_rate_hz
            if self.config.secondary_sdr.driver == "file":
                # A band change reinterprets the recording, it does not rewind it.
                self.secondary_stream.band_spec = GNSS_BANDS[new_band_id]
            else:
                self.secondary_stream = SdrStreamSource(self.config.secondary_sdr)
            self.acq_secondary = PcpsAcquisitionEngine(
                sample_rate_hz=self.config.secondary_sdr.sample_rate_hz,
                doppler_max_hz=self.config.doppler_search_max_hz,
                doppler_step_hz=self.config.doppler_search_step_hz,
                threshold_snr_db=self.config.acq_threshold_snr_db,
            )
            self.tracking_channels.clear()
        self.initialize_acquisition()

    def start_background(self, interval_sec: float = 0.5) -> None:
        if self._running:
            return
        self.initialize_acquisition()
        self.streamer.start()
        self._running = True

        def _loop():
            while self._running:
                try:
                    self.step_epoch()
                except EOFError:
                    self.stop_background()
                    break
                except Exception:
                    pass
                time.sleep(interval_sec)

        self._worker_thread = threading.Thread(target=_loop, daemon=True)
        self._worker_thread.start()

    def stop_background(self) -> None:
        self._running = False
        self.streamer.stop()

    def get_status_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            p_band = GNSS_BANDS[self.config.primary_sdr.band_id]
            s_band = GNSS_BANDS[self.config.secondary_sdr.band_id]
            return {
                "source": "simulated",
                "epoch": self.epoch_count,
                "dual_sdr_enabled": self.config.dual_sdr_enabled,
                "primary_sdr": {
                    "label": self.detected_devices[0].label if self.detected_devices else "HackRF #0",
                    "serial": self.config.primary_sdr.device_serial,
                    "band_id": p_band.band_id,
                    "band_name": p_band.name,
                    "center_freq_mhz": round(p_band.center_freq_hz / 1e6, 3),
                    "sample_rate_msps": round(self.config.primary_sdr.sample_rate_hz / 1e6, 3),
                    "modulation": p_band.modulation,
                    "bias_tee": self.config.primary_sdr.bias_tee_enable,
                    "clkout_master": self.config.primary_sdr.clkout_enable,
                    "lna_gain_db": self.config.primary_sdr.lna_gain_db,
                    "vga_gain_db": self.config.primary_sdr.vga_gain_db,
                    "cli_cmd": " ".join(self.primary_stream.get_hackrf_cli_command()),
                    "spectrum_db": list(self.primary_spectrum_db),
                },
                "secondary_sdr": {
                    "label": self.detected_devices[1].label if len(self.detected_devices) > 1 else "HackRF #1",
                    "serial": self.config.secondary_sdr.device_serial,
                    "band_id": s_band.band_id,
                    "band_name": s_band.name,
                    "center_freq_mhz": round(s_band.center_freq_hz / 1e6, 3),
                    "sample_rate_msps": round(self.config.secondary_sdr.sample_rate_hz / 1e6, 3),
                    "modulation": s_band.modulation,
                    "bias_tee": self.config.secondary_sdr.bias_tee_enable,
                    "clkin_slave": self.config.secondary_sdr.use_external_clkin,
                    "lna_gain_db": self.config.secondary_sdr.lna_gain_db,
                    "vga_gain_db": self.config.secondary_sdr.vga_gain_db,
                    "cli_cmd": " ".join(self.secondary_stream.get_hackrf_cli_command()),
                    "spectrum_db": list(self.secondary_spectrum_db),
                },
                "tracking_channels": [asdict(ch) for ch in self.latest_tracking],
                "decoded_frames": [asdict(f) for f in self.decoded_frames[:25]],
                "pvt": asdict(self.latest_pvt) if self.latest_pvt else None,
                "osnma": asdict(self.osnma_engine.get_summary()),
                "has_ua": asdict(self.latest_has_ua) if self.latest_has_ua else None,
                "galileo_services": asdict(self.latest_advanced_services) if self.latest_advanced_services else None,
                "bridge": {
                    "udp_target": f"{self.config.telemetry.udp_host}:{self.config.telemetry.udp_port}",
                    "tcp_listen": f"{self.config.telemetry.tcp_bind_host}:{self.config.telemetry.tcp_port}",
                    "tcp_clients": self.streamer.connected_tcp_clients_count,
                    "pty_serial_device": self.streamer.pty_slave_path or "N/A",
                    **self.streamer.get_stats_snapshot(),
                },
            }
