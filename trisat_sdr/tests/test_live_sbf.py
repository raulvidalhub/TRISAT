import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from trisat_sdr.live_sbf import LiveReceiver, capture_session
from trisat_sdr.sbf import SbfFramer
from trisat_sdr.sbf_receiver import PVT_GEODETIC
from trisat_sdr.tests.test_sbf_replay import inav, meas_epoch, pvt_geodetic
from trisat_sdr.ui.web_dashboard import TrisatWebDashboardServer


class TestLiveSbf(unittest.TestCase):
    def test_records_complete_blocks_from_mixed_serial_reads(self):
        navigation = inav(tow=1000)
        position = pvt_geodetic(1000)
        measurement = meas_epoch(1000, [(72, 17, 120, [])])
        damaged = bytearray(navigation)
        damaged[-1] ^= 1
        serial = Mock(in_waiting=4096)
        serial.read.side_effect = [
            b"USB2>\r\n" + navigation[:1], navigation[1:] + position[:12],
            b"", position[12:] + damaged + measurement, KeyboardInterrupt,
        ]
        recording = io.BytesIO()
        receiver = LiveReceiver()
        with self.assertRaises(KeyboardInterrupt):
            capture_session(serial, recording, receiver)
        self.assertEqual(recording.getvalue(), navigation + position + measurement)
        state = receiver.get_status_snapshot()
        self.assertEqual(state["source"], "septentrio_live")
        self.assertEqual(state["receiver_position"]["solution"], "standalone")
        self.assertEqual(state["galileo_signal_quality"]["signals"][0]["cn0_dbhz"], {"main": 40.0})

    def test_recovers_complete_block_after_corrupt_length_at_end(self):
        framer = SbfFramer()
        block = inav()
        false_header = block[:6] + b"\xfc\xff"
        self.assertEqual(list(framer.feed(false_header + block)), [])
        self.assertEqual(list(framer.feed(b"", final=True)), [(4023, block)])

    def test_ignores_older_samples_and_expires_stale_telemetry(self):
        receiver = LiveReceiver()
        with patch("trisat_sdr.live_sbf.monotonic", return_value=10.0) as clock:
            self.assertEqual(receiver.get_status_snapshot()["stream_state"], "waiting")
            receiver.accept(PVT_GEODETIC, pvt_geodetic(2000))
            clock.return_value = 11.0
            receiver.accept(PVT_GEODETIC, pvt_geodetic(1000, error=1))
            receiver.accept(PVT_GEODETIC, pvt_geodetic(2000, error=1))
            latest = receiver.get_status_snapshot()["receiver_position"]
            self.assertEqual((latest["tow_ms"], latest["age_ms"], latest["error_code"]), (2000, 1000, 0))
            clock.return_value = 12.1
            snapshot = receiver.get_status_snapshot()
            self.assertEqual(snapshot["stream_state"], "stale")
            self.assertIsNone(snapshot["receiver_position"])

    def test_dashboard_serves_live_mode_and_rejects_retuning(self):
        dashboard = TrisatWebDashboardServer(LiveReceiver(), port=0, live_sbf=True)
        url = dashboard.start()
        self.addCleanup(dashboard.stop)
        with urlopen(url, timeout=5) as response:
            body = response.read()
        self.assertIn(b'<body class="live-sbf">', body)
        self.assertIn(b"<title>TRISAT-SDR | Mosaic-H live</title>", body)
        with urlopen(url + "api/status", timeout=5) as response:
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
            self.assertEqual(json.load(response)["source"], "septentrio_live")
        request = Request(url + "api/set_band?band=GAL_E5B", method="POST")
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=5)
        self.assertEqual(error.exception.code, 405)
        request = Request(url + "api/status", headers={"Host": "example.com"})
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=5)
        self.assertEqual(error.exception.code, 403)
