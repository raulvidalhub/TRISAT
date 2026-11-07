import binascii
import struct
import tempfile
import unittest
from pathlib import Path

from trisat_sdr.osnma_replay import VerificationTimeline
from trisat_sdr.replay_sbf import read_pages
from trisat_sdr.sbf_attitude import AttitudeTimeline


def sbf_block(block_id, body):
    header_and_body = struct.pack("<HH", block_id, len(body) + 8) + body
    return b"$@" + struct.pack("<H", binascii.crc_hqx(header_and_body, 0)) + header_and_body


def inav(svid=72, signal=17, nav_crc=1, tow=1000):
    metadata = struct.pack("<IHBBBBH", tow, 2443, svid, nav_crc, 0, signal, 0)
    words = struct.pack("<8I", 0x01020304, *([0] * 6), 0x00FFFFFF)
    return sbf_block(4023, metadata + words)


def att_euler(tow, heading=169.5, pitch=-1.5, mode=2, error=0, week=2443):
    body = struct.pack("<IHBBHH6f", tow, week, 13, error, mode, 0, heading, pitch, -2e10, 0, 0, 0)
    return sbf_block(5938, body)


def aux_ant(tow, east=0.6, north=0, up=0.8, ambiguity=0, error=0, antenna=1):
    subblock = struct.pack("<4B6d", 13, error, ambiguity, antenna, east, north, up, 0, 0, 0)
    return sbf_block(5942, struct.pack("<IHBB", tow, 2443, 1, len(subblock)) + subblock)


class TestAttitudeTimeline(unittest.TestCase):
    def timeline(self, recording, auxiliary=None):
        with tempfile.TemporaryDirectory() as folder:
            main = Path(folder) / "test.sbf"
            main.write_bytes(recording)
            baseline = None
            if auxiliary is not None:
                baseline = Path(folder) / "auxiliary.sbf"
                baseline.write_bytes(auxiliary)
            return AttitudeTimeline(main, baseline)

    def test_uses_latest_recorded_attitude_without_filling_gaps(self):
        timeline = self.timeline(att_euler(2000, error=1) + att_euler(1000))
        self.assertIsNone(timeline.at({"gps_week": 2443, "tow_ms": 999})["attitude"])
        fixed = timeline.at({"gps_week": 2443, "tow_ms": 1300})["attitude"]
        self.assertEqual(fixed, {"gps_week": 2443, "tow_ms": 1000, "age_ms": 300,
                                 "heading_deg": 169.5, "pitch_deg": -1.5, "solution": "fixed"})
        missing = timeline.at({"gps_week": 2443, "tow_ms": 4000})["attitude"]
        self.assertEqual(missing["solution"], "insufficient_measurements")
        self.assertIsNone(missing["heading_deg"])
        self.assertIsNone(timeline.at({"gps_week": 2443, "tow_ms": 4001})["attitude"])

    def test_matches_across_gps_weeks(self):
        timeline = self.timeline(att_euler(604799000, mode=1))
        sample = timeline.at({"gps_week": 2444, "tow_ms": 500})["attitude"]
        self.assertEqual((sample["solution"], sample["age_ms"]), ("float", 1500))

    def test_reads_baseline_in_either_recording_and_skips_invalid_values(self):
        time = {"gps_week": 2443, "tow_ms": 1000}
        main = att_euler(1000) + aux_ant(1000)
        baseline = self.timeline(main).at(time)["baseline"]
        self.assertEqual((baseline["distance_m"], baseline["source"]), (1.0, "main"))
        auxiliary = aux_ant(1200, east=-2e10) + aux_ant(1100, ambiguity=1) + aux_ant(1000, antenna=2)
        timeline = self.timeline(main, auxiliary)
        self.assertIsNone(timeline.at(time)["baseline"])
        baseline = timeline.at({**time, "tow_ms": 1150})["baseline"]
        self.assertEqual((baseline["distance_m"], baseline["solution"], baseline["source"]),
                         (1.0, "float", "auxiliary"))
        self.assertIsNone(timeline.at({**time, "tow_ms": 1200})["baseline"]["distance_m"])
        with self.assertRaisesRegex(ValueError, "no Main–Aux1 position samples"):
            self.timeline(main, aux_ant(1000, antenna=2))


class TestSbfReplay(unittest.TestCase):
    def replay(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.sbf"
            path.write_bytes(data)
            return list(read_pages(path))

    def test_recorded_pages_are_deterministic_and_preserve_order(self):
        recording = inav(tow=2000) + sbf_block(4007, b"private!") + inav(73, 21, 0, 1000)
        frames = self.replay(recording)
        self.assertEqual(frames, self.replay(recording))
        self.assertEqual([frame["svid"] for frame in frames], [2, 3])
        self.assertEqual([frame["tow_ms"] for frame in frames], [2000, 1000])
        self.assertEqual(frames[0]["source"], "recorded")
        self.assertEqual(frames[0]["osnma_status"], "unverified")
        self.assertEqual(frames[0]["payload_hex"], "01020304" + "00" * 25 + "C0")
        self.assertEqual(frames[0]["bit_length"], 234)
        self.assertFalse(frames[1]["navigation_crc_passed"])
        self.assertEqual(frames[1]["band"], "E5b-I")
        self.assertEqual(frames[1]["osnma_status"], "not_applicable")

    def test_resynchronizes_after_bad_crc_and_bad_length(self):
        bad_crc = bytearray(inav(svid=72))
        bad_crc[-1] ^= 1
        bad_length = bytearray(inav(svid=73))
        struct.pack_into("<H", bad_length, 6, 65532)
        good = inav(svid=74)
        frames = self.replay(bytes(bad_crc) + bytes(bad_length) + good + good[:6])
        self.assertEqual([frame["svid"] for frame in frames], [4])

    def test_skips_missing_timestamps_and_unsupported_signals(self):
        self.assertEqual(self.replay(inav(tow=0xFFFFFFFF) + inav(signal=20)), [])
        self.assertEqual(self.replay(b""), [])

    def test_verified_tags_appear_at_their_processing_point_and_count_for_the_target(self):
        statuses = [
            {
                "metadata": {"GST_subframe": [1419, 30]},
                "verified_OSNMA_material": {"tags": [
                    {"prn_a": 7, "prn_d": 2, "adkd": 0, "verification": True},
                    {"prn_a": 7, "prn_d": 2, "adkd": 4, "verification": False},
                ]},
            },
            {
                "metadata": {"GST_subframe": [1419, 60]},
                "verified_OSNMA_material": {"tags": [
                    {"prn_a": 7, "prn_d": 2, "adkd": 12, "verification": True},
                    {"prn_a": 2, "prn_d": 7, "adkd": 0, "verification": True},
                    {"prn_a": 2, "prn_d": 255, "adkd": 0, "verification": True},
                ]},
            },
        ]
        timeline = VerificationTimeline(statuses, [6, 12])
        self.assertEqual(timeline.at(5, 2)["verified_tags"], 0)
        self.assertEqual(timeline.at(6, 2)["by_adkd"], {0: 1})
        self.assertEqual(timeline.at(11, 7)["verified_tags"], 0)
        self.assertEqual(timeline.at(12, 2)["by_adkd"], {0: 1, 12: 1})
        self.assertEqual(timeline.at(12, 2)["processed_subframe"], {
            "galileo_week": 1419, "tow_s": 60,
        })
        self.assertEqual(timeline.totals(), {2: 2, 7: 1})
