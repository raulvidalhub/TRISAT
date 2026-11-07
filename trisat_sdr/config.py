"""
Configuration models and GNSS Frequency Band definitions for TRISAT-SDR.
Supports Galileo E1B/C, E5a, E5b, E5 AltBOC, E6B/C (HAS), and GPS L1 C/A,
including Dual-HackRF synchronized operation (Master CLKOUT -> Slave CLKIN).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class GnssBandSpec:
    """RF and Baseband specification for a GNSS signal band."""
    band_id: str
    name: str
    constellation: str
    center_freq_hz: float
    code_rate_cps: float
    code_length_chips: int
    modulation: str
    symbol_rate_sps: int
    nav_message_type: str
    recommended_sample_rate_hz: float
    description: str


GNSS_BANDS: Dict[str, GnssBandSpec] = {
    "GAL_E1": GnssBandSpec(
        band_id="GAL_E1",
        name="Galileo E1B/C",
        constellation="GALILEO",
        center_freq_hz=1575.42e6,
        code_rate_cps=1.023e6,
        code_length_chips=4092,
        modulation="CBOC(6,1,1/11)",
        symbol_rate_sps=250,
        nav_message_type="I/NAV + OSNMA",
        recommended_sample_rate_hz=4.092e6,
        description="Galileo Open Service E1B (I/NAV data with 40-bit OSNMA) & E1C (Pilot)"
    ),
    "GAL_E5A": GnssBandSpec(
        band_id="GAL_E5A",
        name="Galileo E5a-I/Q",
        constellation="GALILEO",
        center_freq_hz=1176.45e6,
        code_rate_cps=10.23e6,
        code_length_chips=10230,
        modulation="BPSK(10) / AltBOC",
        symbol_rate_sps=50,
        nav_message_type="F/NAV",
        recommended_sample_rate_hz=10.23e6,
        description="Galileo E5a Open Service (F/NAV data + Pilot) for dual-frequency iono-free PVT"
    ),
    "GAL_E5B": GnssBandSpec(
        band_id="GAL_E5B",
        name="Galileo E5b-I/Q",
        constellation="GALILEO",
        center_freq_hz=1207.14e6,
        code_rate_cps=10.23e6,
        code_length_chips=10230,
        modulation="BPSK(10) / AltBOC",
        symbol_rate_sps=250,
        nav_message_type="I/NAV (E5b)",
        recommended_sample_rate_hz=10.23e6,
        description="Galileo E5b Open Service (I/NAV data + Pilot)"
    ),
    "GAL_E5_ALTBOC": GnssBandSpec(
        band_id="GAL_E5_ALTBOC",
        name="Galileo E5 Full AltBOC(15,10)",
        constellation="GALILEO",
        center_freq_hz=1191.795e6,
        code_rate_cps=10.23e6,
        code_length_chips=10230,
        modulation="AltBOC(15,10)",
        symbol_rate_sps=250,
        nav_message_type="F/NAV + I/NAV",
        recommended_sample_rate_hz=20.0e6,
        description="Full wideband Galileo E5a+E5b coherent AltBOC(15,10) (20 MHz HackRF mode)"
    ),
    "GAL_E6": GnssBandSpec(
        band_id="GAL_E6",
        name="Galileo E6B/C (HAS)",
        constellation="GALILEO",
        center_freq_hz=1278.75e6,
        code_rate_cps=5.115e6,
        code_length_chips=5115,
        modulation="BPSK(5)",
        symbol_rate_sps=1000,
        nav_message_type="C/NAV (HAS + CAS)",
        recommended_sample_rate_hz=8.184e6,
        description="Galileo High Accuracy Service (HAS PPP corrections) & Commercial Auth (E6B/C)"
    ),
    "GPS_L1": GnssBandSpec(
        band_id="GPS_L1",
        name="GPS L1 C/A",
        constellation="GPS",
        center_freq_hz=1575.42e6,
        code_rate_cps=1.023e6,
        code_length_chips=1023,
        modulation="BPSK(1)",
        symbol_rate_sps=50,
        nav_message_type="LNAV",
        recommended_sample_rate_hz=4.092e6,
        description="Legacy GPS Standard Positioning Service L1 C/A (shared RF front-end with E1)"
    ),
}


@dataclass
class SdrChannelConfig:
    """Configuration for a single physical SDR RF front-end (e.g. HackRF #0 or HackRF #1)."""
    channel_index: int = 0
    driver: str = "auto"          # "auto", "hackrf", "soapysdr", "rtlsdr", "file", "simulator"
    device_serial: Optional[str] = None
    band_id: str = "GAL_E1"
    sample_rate_hz: float = 4.092e6
    lna_gain_db: int = 32         # HackRF IF LNA gain (0..40 dB in 8 dB steps)
    vga_gain_db: int = 28         # HackRF Baseband VGA gain (0..62 dB in 2 dB steps)
    rf_amp_enable: bool = False   # HackRF 14 dB RF amplifier
    bias_tee_enable: bool = True  # 3.3V antenna phantom power for active GNSS antenna
    clkout_enable: bool = False   # Enable 10 MHz reference output (Master HackRF #0)
    use_external_clkin: bool = False  # Expect 10 MHz reference input (Slave HackRF #1)
    iq_file_path: Optional[str] = None
    iq_format: str = "int8"       # "int8" (HackRF native), "uint8" (RTL-SDR), "int16", "float32"


@dataclass
class TelemetryBridgeConfig:
    """Configuration for streaming GNSS frames and telemetry to TRISAT apps."""
    udp_enabled: bool = True
    udp_host: str = "127.0.0.1"
    udp_port: int = 5005
    tcp_enabled: bool = True
    tcp_bind_host: str = "0.0.0.0"
    tcp_port: int = 5006
    pty_serial_enabled: bool = True
    emit_nmea: bool = False
    emit_galinav_raw: bool = False
    emit_trisat_json: bool = True


@dataclass
class ReceiverConfig:
    """Top-level configuration for TRISAT-SDR."""
    dual_sdr_enabled: bool = True
    primary_sdr: SdrChannelConfig = field(
        default_factory=lambda: SdrChannelConfig(
            channel_index=0,
            driver="auto",
            band_id="GAL_E1",
            sample_rate_hz=4.092e6,
            lna_gain_db=32,
            vga_gain_db=30,
            bias_tee_enable=True,
            clkout_enable=True,
            use_external_clkin=False,
        )
    )
    secondary_sdr: SdrChannelConfig = field(
        default_factory=lambda: SdrChannelConfig(
            channel_index=1,
            driver="auto",
            band_id="GAL_E6",  # Can switch dynamically between GAL_E6, GAL_E5A, GAL_E5B, GAL_E5_ALTBOC
            sample_rate_hz=8.184e6,
            lna_gain_db=32,
            vga_gain_db=30,
            bias_tee_enable=True,
            clkout_enable=False,
            use_external_clkin=True,
        )
    )
    also_acquire_gps_l1_on_primary: bool = True
    acq_threshold_snr_db: float = 11.5
    doppler_search_max_hz: float = 5000.0
    doppler_search_step_hz: float = 250.0
    coherent_integration_ms: int = 4
    telemetry: TelemetryBridgeConfig = field(default_factory=TelemetryBridgeConfig)
    web_ui_host: str = "127.0.0.1"
    web_ui_port: int = 8085
    reference_lat: float = 40.416775   # Default reference (Madrid, Spain - adjustable)
    reference_lon: float = -3.703790
    reference_alt_m: float = 650.0
