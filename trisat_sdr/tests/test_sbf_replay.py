import binascii
import math
import struct
import tempfile
import unittest
from pathlib import Path

from trisat_sdr.osnma_replay import VerificationTimeline
from trisat_sdr.replay_sbf import read_pages
from trisat_sdr.sbf_receiver import ReceiverTimeline


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


def pvt_geodetic(tow, latitude=47.25, longitude=19.125, height=150.0, mode=1, error=0, datum=0, revision=2):
    body = bytearray(88 if revision >= 2 else 80)
    struct.pack_into("<IHBBddd", body, 0, tow, 2443, mode, error, math.radians(latitude), math.radians(longitude), height)
    body[65] = datum  # Offset 73 including the SBF header.
    return sbf_block(4007 | (revision << 13), body)


def meas_epoch(tow, measurements=(), flags=0, size1=20, size2=12):
    body = bytearray(struct.pack("<IH6B", tow, 2443, len(measurements), size1, size2, flags, 0, 0))
    for svid, signal, cn0, secondary in measurements:
        primary = bytearray(size1)
        primary[1], primary[2], primary[15], primary[19] = signal, svid, cn0, len(secondary)
        body.extend(primary)
        for sub_signal, sub_cn0 in secondary:
            subblock = bytearray(size2)
            subblock[0], subblock[2] = sub_signal, sub_cn0
            body.extend(subblock)
    body.extend(bytes(-len(body) % 4))
    return sbf_block(4027 | (1 << 13), body)


class TestReceiverTimeline(unittest.TestCase):
    def timeline(self, recording, auxiliary=None):
        with tempfile.TemporaryDirectory() as folder:
            main = Path(folder) / "test.sbf"
            main.write_bytes(recording)
            baseline = None
            if auxiliary is not None:
                baseline = Path(folder) / "auxiliary.sbf"
                baseline.write_bytes(auxiliary)
            return ReceiverTimeline(main, baseline)

    def test_uses_latest_recorded_attitude_without_filling_gaps(self):
        timeline = self.timeline(att_euler(2000, error=1) + att_euler(1000))
        self.assertIsNone(timeline.at({"gps_week": 2443, "tow_ms": 999})["antenna_attitude"]["attitude"])
        fixed = timeline.at({"gps_week": 2443, "tow_ms": 1300})["antenna_attitude"]["attitude"]
        self.assertEqual(fixed, {"gps_week": 2443, "tow_ms": 1000, "age_ms": 300,
                                 "heading_deg": 169.5, "pitch_deg": -1.5, "solution": "fixed"})
        missing = timeline.at({"gps_week": 2443, "tow_ms": 4000})["antenna_attitude"]["attitude"]
        self.assertEqual(missing["solution"], "insufficient_measurements")
        self.assertIsNone(missing["heading_deg"])
        self.assertIsNone(timeline.at({"gps_week": 2443, "tow_ms": 4001})["antenna_attitude"]["attitude"])

    def test_matches_across_gps_weeks(self):
        timeline = self.timeline(att_euler(604799000, mode=1))
        sample = timeline.at({"gps_week": 2444, "tow_ms": 500})["antenna_attitude"]["attitude"]
        self.assertEqual((sample["solution"], sample["age_ms"]), ("float", 1500))

    def test_reads_baseline_in_either_recording_and_skips_invalid_values(self):
        time = {"gps_week": 2443, "tow_ms": 1000}
        main = att_euler(1000) + aux_ant(1000)
        baseline = self.timeline(main).at(time)["antenna_attitude"]["baseline"]
        self.assertEqual((baseline["distance_m"], baseline["source"]), (1.0, "main"))
        auxiliary = pvt_geodetic(1000) + aux_ant(1200, east=-2e10) + aux_ant(1100, ambiguity=1) + aux_ant(1000, antenna=2)
        timeline = self.timeline(main, auxiliary)
        self.assertNotIn("receiver_position", timeline.at(time))
        self.assertIsNone(timeline.at(time)["antenna_attitude"]["baseline"])
        baseline = timeline.at({**time, "tow_ms": 1150})["antenna_attitude"]["baseline"]
        self.assertEqual((baseline["distance_m"], baseline["solution"], baseline["source"]),
                         (1.0, "float", "auxiliary"))
        self.assertIsNone(timeline.at({**time, "tow_ms": 1200})["antenna_attitude"]["baseline"]["distance_m"])
        with self.assertRaisesRegex(ValueError, "no Main–Aux1 position samples"):
            self.timeline(main, aux_ant(1000, antenna=2))

    def test_matches_position_by_timestamp_without_reusing_failed_fixes(self):
        timeline = self.timeline(
            att_euler(1000) + pvt_geodetic(2000, mode=0, error=1) + pvt_geodetic(1000, revision=0)
        )
        self.assertIsNone(timeline.at({"gps_week": 2443, "tow_ms": 999})["receiver_position"])
        data = timeline.at({"gps_week": 2443, "tow_ms": 1250})
        sample = data["receiver_position"]
        self.assertEqual(sample["tow_ms"], data["antenna_attitude"]["attitude"]["tow_ms"])
        self.assertEqual((sample["solution"], sample["dimensions"], sample["age_ms"]), ("standalone", 3, 250))
        self.assertAlmostEqual(sample["latitude_deg"], 47.25)
        self.assertAlmostEqual(sample["longitude_deg"], 19.125)
        self.assertEqual((sample["ellipsoidal_height_m"], sample["datum_code"]), (150.0, 0))
        failed = timeline.at({"gps_week": 2443, "tow_ms": 2000})["receiver_position"]
        self.assertEqual((failed["solution"], failed["error_code"]), ("unavailable", 1))
        self.assertIsNone(failed["latitude_deg"])
        self.assertIsNone(timeline.at({"gps_week": 2443, "tow_ms": 4001})["receiver_position"])

    def test_position_respects_two_dimensional_fixes_and_unusable_values(self):
        timeline = self.timeline(
            pvt_geodetic(1000, mode=0x84, datum=30)
            + pvt_geodetic(2000, height=-2e10)
            + pvt_geodetic(3000, latitude=float("nan"))
            + pvt_geodetic(4000, mode=9)
        )
        sample = timeline.at({"gps_week": 2443, "tow_ms": 1000})["receiver_position"]
        self.assertEqual((sample["solution"], sample["dimensions"], sample["datum_code"]), ("rtk_fixed", 2, 30))
        self.assertIsNone(sample["ellipsoidal_height_m"])
        self.assertAlmostEqual(sample["longitude_deg"], 19.125)
        missing_height = timeline.at({"gps_week": 2443, "tow_ms": 2000})["receiver_position"]
        self.assertIsNone(missing_height["ellipsoidal_height_m"])
        self.assertIsNotNone(missing_height["latitude_deg"])
        invalid = timeline.at({"gps_week": 2443, "tow_ms": 3000})["receiver_position"]
        self.assertIsNone(invalid["longitude_deg"])
        unknown = timeline.at({"gps_week": 2443, "tow_ms": 4000})["receiver_position"]
        self.assertEqual((unknown["solution"], unknown["mode_code"]), ("unknown", 9))
        self.assertIsNone(unknown["latitude_deg"])

    def test_reads_galileo_cn0_from_both_subblock_types_and_antennas(self):
        timeline = self.timeline(meas_epoch(1000, [
            (72, 17, 120, [(17 | 32, 116), (21, 108), (21 | 32, 255), (19 | 64, 100), (31, 200)]),
            (5, 0, 140, []),
            (73, 20, 105, []),
        ], flags=0x40, size1=24, size2=16))
        sample = timeline.at({"gps_week": 2443, "tow_ms": 1250})["galileo_signal_quality"]
        self.assertEqual(sample["age_ms"], 250)
        self.assertFalse(sample["scrambled"])
        self.assertEqual(sample["signals"], [
            {"svid": 2, "band": "E1", "cn0_dbhz": {"main": 40.0, "aux1": 39.0}},
            {"svid": 2, "band": "E5b", "cn0_dbhz": {"main": 37.0}},
            {"svid": 2, "band": "E6-B", "cn0_dbhz": {"aux2": 35.0}},
            {"svid": 3, "band": "E5a", "cn0_dbhz": {"main": 36.25}},
        ])

    def test_signal_quality_uses_only_the_matched_epoch(self):
        timeline = self.timeline(
            meas_epoch(1000, [(72, 17, 120, [(21, 120)])])
            + meas_epoch(2000, [(72, 17, 255, [])])
            + meas_epoch(3000, [(72, 17, 120, [])], flags=0x80)
            + meas_epoch(4000)
        )

        def at(tow):
            return timeline.at({"gps_week": 2443, "tow_ms": tow})["galileo_signal_quality"]

        self.assertIsNone(at(999))
        self.assertEqual(len(at(1000)["signals"]), 2)
        self.assertEqual(at(2000)["signals"], [{"svid": 2, "band": "E1", "cn0_dbhz": {}}])
        self.assertTrue(at(3000)["scrambled"])
        self.assertEqual(at(3000)["signals"], [])
        self.assertEqual(at(6000)["signals"], [])
        self.assertIsNone(at(6001))

    def test_discards_measurement_blocks_with_inconsistent_subblock_lengths(self):
        block = meas_epoch(1000, [(72, 17, 120, [(21, 120)])])
        for offset, value in ((15, 19), (16, 11), (39, 2)):
            with self.subTest(offset=offset):
                body = bytearray(block[8:])
                body[offset - 8] = value
                timeline = self.timeline(sbf_block(4027 | (1 << 13), body))
                self.assertNotIn("galileo_signal_quality", timeline.at({"gps_week": 2443, "tow_ms": 1000}))


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
