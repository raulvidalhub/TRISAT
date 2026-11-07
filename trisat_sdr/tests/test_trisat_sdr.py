"""
Automated Unit & Integration Tests for TRISAT-SDR.
Verifies:
  1. PRN spreading codes (GPS L1 C/A, Galileo E1 CBOC, Galileo E5a/E5b, Galileo E6 HAS)
  2. PCPS FFT Acquisition Engine (both NumPy and pure-Python radix-2 FFT)
  3. 5-Tap DLL/PLL Tracking Channel
  4. Galileo CRC-24Q & Frame Decoders ($GALINAV + OSNMA, $GALE6HAS, $GALE5)
  5. Dual-HackRF Receiver Pipeline & Telemetry Bridge
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from trisat_sdr.bridge.telemetry_streamer import TelemetryStreamer, format_gngga_sentence, format_gsv_sentences  # noqa: E402
from trisat_sdr.config import ReceiverConfig  # noqa: E402
from trisat_sdr.dsp.acquisition import PcpsAcquisitionEngine  # noqa: E402
from trisat_sdr.dsp.codes import (  # noqa: E402
    generate_galileo_e1_code,
    generate_galileo_e5_code,
    generate_galileo_e6_code,
    generate_gps_l1ca_code,
    sample_code_waveform,
)
from trisat_sdr.nav.frame_decoder import GnssFrameDecoder, compute_crc24q  # noqa: E402
from trisat_sdr.nav.galileo_advanced_services import GalileoAdvancedServicesEngine  # noqa: E402
from trisat_sdr.nav.has_ua_engine import GalileoHasUaEngine, NtcmGIonosphereModel  # noqa: E402
from trisat_sdr.nav.osnma_engine import GalileoOsnmaEngine  # noqa: E402
from trisat_sdr.receiver import TrisatSdrReceiver  # noqa: E402


class TestTrisatSdr(unittest.TestCase):
    def test_prn_code_lengths_and_balance(self):
        l1 = generate_gps_l1ca_code(1)
        self.assertEqual(len(l1), 1023)
        self.assertTrue(all(c in (-1, 1) for c in l1))

        e1b = generate_galileo_e1_code(11, component="B")
        self.assertEqual(len(e1b), 4092)

        e5a = generate_galileo_e5_code(11, band="E5A")
        self.assertEqual(len(e5a), 10230)

        e6b = generate_galileo_e6_code(11, component="B")
        self.assertEqual(len(e6b), 5115)

    def test_cboc_and_bpsk_waveform_sampling(self):
        wf_e1 = sample_code_waveform("GAL_E1", svid=2, sample_rate_hz=4.092e6, duration_ms=1.0)
        self.assertEqual(len(wf_e1), 4092)
        wf_e6 = sample_code_waveform("GAL_E6", svid=2, sample_rate_hz=8.184e6, duration_ms=1.0)
        self.assertEqual(len(wf_e6), 8184)

    def test_crc24q_and_frame_decoder(self):
        decoder = GnssFrameDecoder()
        inav = decoder.decode_channel_frame("GAL_E1", "GALILEO", 11, [1, 0, 1, 1], 47.5)
        self.assertEqual(inav.frame_type, "INAV_E1B")
        self.assertEqual(len(inav.hex_payload), 60)  # 30 bytes = 60 hex chars
        self.assertEqual(len(inav.osnma_hkroot_hex), 2)
        self.assertEqual(len(inav.osnma_mack_hex), 8)
        self.assertTrue(inav.nmea_custom_sentence.startswith("$GALINAV,11,"))

        # Verify CRC-24Q over full 30-byte frame equals 0 residue or matches last 3 bytes
        raw_bytes = bytes.fromhex(inav.hex_payload)
        computed_crc = compute_crc24q(raw_bytes[:27])
        self.assertEqual(f"{computed_crc:06X}", inav.crc24q_hex)

        e6_has = decoder.decode_channel_frame("GAL_E6", "GALILEO", 24, [0, 1, 0, 1], 46.2)
        self.assertEqual(e6_has.frame_type, "CNAV_E6_HAS")
        self.assertTrue(e6_has.nmea_custom_sentence.startswith("$GALE6HAS,24,"))

    def test_euspa_osnma_engine_annex_a_vectors(self):
        osnma = GalileoOsnmaEngine()
        summary = osnma.get_summary()
        self.assertEqual(summary.status, "simulated")
        self.assertFalse(summary.merkle_root_verified)
        self.assertFalse(summary.dsm_kroot_ecdsa_verified)
        self.assertFalse(summary.tesla_chain_verified)
        self.assertFalse(summary.macseq_verified)
        self.assertTrue(summary.annex_a_selftest_passed)

        # Generating a demo tag does not authenticate any received satellite.
        hkroot_hex, mack_hex = osnma.generate_simulated_subframe_tag(
            svid=11, navdata_bytes=b"\x01\x02\x03\x04\x05\x06\x07\x08", tow_sf=345660
        )
        self.assertEqual(len(hkroot_hex), 2)
        self.assertEqual(len(mack_hex), 8)
        self.assertEqual(osnma.get_summary().authenticated_svids, [])
        self.assertEqual(osnma.get_summary().verified_tags_count, 0)

    def test_euspa_has_ua_engine_and_ntcm_g(self):
        has_ua = GalileoHasUaEngine()
        report = has_ua.process_epoch(
            lat_deg=40.4168,
            lon_deg=-3.7038,
            alt_m=667.0,
            gal_sats=[(2, 62.0, 48.0), (11, 54.0, 47.0), (24, 41.0, 45.5), (31, 29.0, 43.0)],
            gps_sats=[(3, 58.0, 46.5), (17, 44.0, 44.0)],
        )
        self.assertEqual(report.solving_mode, 2)
        self.assertEqual(report.status_flag_8bit, 0b00000011)
        self.assertFalse(report.dia_outlier_rejected)
        self.assertEqual(len(report.sol_line_33col.split()), 33)

        # Test NTCM-G 12-coefficient single-frequency ionospheric delay
        delay_m, vtec_tecu = NtcmGIonosphereModel.compute_slant_delay_m(
            user_lat_deg=40.4168,
            user_lon_deg=-3.7038,
            elev_deg=52.0,
            azim_deg=145.0,
        )
        self.assertGreater(delay_m, 0.5)
        self.assertLess(delay_m, 40.0)
        self.assertGreater(vtec_tecu, 1.0)

    def test_galileo_advanced_services_inav_ewss_tsm(self):
        adv = GalileoAdvancedServicesEngine()
        rep = adv.evaluate(rx_lat=40.4168, rx_lon=-3.7038)
        self.assertTrue(rep.wt16_redced_active)
        self.assertTrue(rep.rs_ced_reconstructed)
        self.assertTrue(rep.ewss_alert.receiver_inside_alert_zone)
        self.assertIn("SL2 Operational", rep.wt44_tsm_service_level)

    def test_dual_hackrf_receiver_and_band_switching(self):
        cfg = ReceiverConfig()
        cfg.telemetry.udp_enabled = False
        cfg.telemetry.tcp_enabled = False
        cfg.telemetry.pty_serial_enabled = False

        rx = TrisatSdrReceiver(cfg)
        acqs = rx.initialize_acquisition()
        self.assertGreaterEqual(len(acqs), 8)

        snap = rx.step_epoch()
        self.assertEqual(snap["source"], "simulated")
        self.assertTrue(snap["pvt"]["valid_fix"])
        self.assertEqual(snap["pvt"]["osnma_authenticated_sats"], 0)
        self.assertEqual(snap["pvt"]["has_corrected_sats"], 0)
        self.assertIn("HAS", snap["pvt"]["solution_mode"])
        self.assertTrue(snap["osnma"]["annex_a_selftest_passed"])
        self.assertEqual(snap["has_ua"]["solving_mode"], 2)

        # Switch HackRF #1 dynamically to Galileo E5a
        rx.switch_secondary_band("GAL_E5A", dual_enabled=True)
        snap_e5 = rx.step_epoch()
        self.assertEqual(snap_e5["secondary_sdr"]["band_id"], "GAL_E5A")
        self.assertIn("E5", snap_e5["pvt"]["solution_mode"])

        gga = format_gngga_sentence(rx.latest_pvt)
        self.assertTrue(gga.startswith("$GNGGA,"))
        self.assertEqual(gga.split(",")[6], "0")
        gsv = format_gsv_sentences(rx.latest_pvt.satellites)
        self.assertGreaterEqual(len(gsv), 1)

        # Default transport emits only messages with explicit simulated provenance.
        streamer = TelemetryStreamer(ReceiverConfig().telemetry)
        with patch.object(streamer, "_broadcast_line") as broadcast:
            streamer.publish_decoded_frame(rx.decoded_frames[0])
            streamer.publish_pvt(rx.latest_pvt)
        packets = [json.loads(call.args[0]) for call in broadcast.call_args_list]
        self.assertEqual(len(packets), 3)
        self.assertTrue(all(packet["source"] == "simulated" for packet in packets))
        self.assertEqual(packets[1]["osnmaSats"], 0)
        self.assertTrue(all(not sat["osnma"] for sat in packets[2]["satellites"]))


if __name__ == "__main__":
    unittest.main()
