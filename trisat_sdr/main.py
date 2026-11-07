#!/usr/bin/env python3
"""
TRISAT-SDR Main Entry Point (macOS, GNU/Linux, Windows).
Supports:
  - Interactive Web Dashboard + Real-Time Telemetry Bridge (`python3 main.py`)
  - Headless CLI Console Streamer (`python3 main.py --headless`)
  - Single-shot Diagnostic & Frame Dump (`python3 main.py --epochs 5`)
  - Secondary HackRF Band Selection (`--band2 GAL_E6 | GAL_E5A | GAL_E5B | GAL_E5_ALTBOC`)
"""

import argparse
import os
import sys
import time

# Ensure parent repo root is on sys.path so `trisat_sdr.*` package imports resolve cleanly
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from trisat_sdr.config import GNSS_BANDS, ReceiverConfig  # noqa: E402
from trisat_sdr.receiver import TrisatSdrReceiver  # noqa: E402
from trisat_sdr.ui.web_dashboard import TrisatWebDashboardServer  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TRISAT-SDR: Dual-HackRF Multi-Band GNSS Software Receiver (E1/E5/E6/L1)"
    )
    parser.add_argument(
        "--band1",
        default="GAL_E1",
        choices=list(GNSS_BANDS.keys()),
        help="Primary SDR (#0) GNSS band (default: GAL_E1 at 1575.42 MHz)",
    )
    parser.add_argument(
        "--band2",
        default="GAL_E6",
        choices=list(GNSS_BANDS.keys()),
        help="Secondary SDR (#1) GNSS band (default: GAL_E6 at 1278.75 MHz for HAS, or GAL_E5A/E5B/E5_ALTBOC)",
    )
    parser.add_argument(
        "--single-sdr",
        action="store_true",
        help="Disable Dual-HackRF mode and run with a single SDR front-end",
    )
    parser.add_argument(
        "--udp-host",
        default="127.0.0.1",
        help="Target host for UDP telemetry stream (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=5005,
        help="Target UDP port for NMEA/$GALINAV/JSON telemetry (default: 5005)",
    )
    parser.add_argument(
        "--tcp-port",
        type=int,
        default=5006,
        help="Listen TCP port for NMEA/$GALINAV/JSON clients (default: 5006)",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8085,
        help="Port for the Cross-Platform Web UI Dashboard (default: 8085, also mirrors on 8080)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in terminal CLI mode without starting the Web Dashboard",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=0,
        help="Run a fixed number of epochs and exit (0 = run continuously)",
    )
    parser.add_argument(
        "--emit-legacy-simulation",
        action="store_true",
        help="Also emit simulated legacy NMEA and navigation frames for a dedicated test client",
    )
    return parser.parse_args()


def print_banner(snap: dict, web_url: str = "") -> None:
    p0 = snap["primary_sdr"]
    p1 = snap["secondary_sdr"]
    br = snap["bridge"]
    print("=" * 78)
    print(" 🛰️  TRISAT-SDR | Software-Defined Multi-Band GNSS Receiver (v1.0.0)")
    print("    Portable Engine: macOS · GNU/Linux · Windows")
    print(f"    Data source: {snap['source'].upper()}")
    print("=" * 78)
    print(f" [SDR #0 MASTER] {p0['label']}")
    print(f"    Band: {p0['band_name']} ({p0['center_freq_mhz']} MHz) |Fs: {p0['sample_rate_msps']} MS/s | Bias-T: ON | CLKOUT: 10MHz")
    print(f"    CMD : {p0['cli_cmd']}")
    if snap["dual_sdr_enabled"]:
        print(f" [SDR #1 SLAVE ] {p1['label']}")
        print(f"    Band: {p1['band_name']} ({p1['center_freq_mhz']} MHz) |Fs: {p1['sample_rate_msps']} MS/s | Bias-T: ON | CLKIN : SYNC")
        print(f"    CMD : {p1['cli_cmd']}")
    print("-" * 78)
    print(f" [BRIDGE] UDP Stream : udp://{br['udp_target']}")
    print(f" [BRIDGE] TCP Server : tcp://{br['tcp_listen']}")
    print(f" [BRIDGE] Serial PTY : {br['pty_serial_device']}  <-- Connectable from TRISAT macOS App!")
    if web_url:
        print(f" [WEB UI] Dashboard  : {web_url}")
    print("=" * 78)


def main() -> int:
    args = parse_args()

    cfg = ReceiverConfig()
    cfg.dual_sdr_enabled = not args.single_sdr
    cfg.primary_sdr.band_id = args.band1
    cfg.primary_sdr.sample_rate_hz = GNSS_BANDS[args.band1].recommended_sample_rate_hz
    cfg.secondary_sdr.band_id = args.band2
    cfg.secondary_sdr.sample_rate_hz = GNSS_BANDS[args.band2].recommended_sample_rate_hz
    cfg.telemetry.udp_host = args.udp_host
    cfg.telemetry.udp_port = args.udp_port
    cfg.telemetry.tcp_port = args.tcp_port
    cfg.telemetry.emit_nmea = args.emit_legacy_simulation
    cfg.telemetry.emit_galinav_raw = args.emit_legacy_simulation
    cfg.web_ui_port = args.web_port

    receiver = TrisatSdrReceiver(cfg)
    receiver.streamer.start()
    receiver.initialize_acquisition()

    web_server = None
    web_url = ""
    if not args.headless and args.epochs == 0:
        web_server = TrisatWebDashboardServer(receiver, host=cfg.web_ui_host, port=cfg.web_ui_port)
        web_url = web_server.start(background=True)

    snap = receiver.step_epoch()
    print_banner(snap, web_url=web_url)

    try:
        target_epochs = args.epochs
        while True:
            snap = receiver.step_epoch()
            pvt = snap["pvt"]
            frms = snap["decoded_frames"]
            latest_frm = frms[0] if frms else None

            line = (
                f"[Epoch {snap['epoch']:04d}] Mode: {pvt['solution_mode']} | "
                f"Demo position: ({pvt['latitude_deg']:.6f}, {pvt['longitude_deg']:.6f}) ±{pvt['horizontal_accuracy_m']:.2f}m | "
                f"Demo satellites: {pvt['num_sats_used']} | OSNMA: simulated"
            )
            print(line)
            if latest_frm:
                print(f"   ↳ Demo frame: {latest_frm['nmea_custom_sentence'][:76]}...")

            if target_epochs > 0 and snap["epoch"] >= target_epochs:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[TRISAT-SDR] Stopping receiver and closing SDR & Bridge streams...")
    finally:
        if web_server:
            web_server.stop()
        receiver.stop_background()

    return 0


if __name__ == "__main__":
    sys.exit(main())
