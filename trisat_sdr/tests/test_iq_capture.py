"""Regression tests for sequential playback of interleaved IQ captures."""

import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trisat_sdr.config import ReceiverConfig, SdrChannelConfig
from trisat_sdr.drivers.sdr_driver import SdrStreamSource
from trisat_sdr.receiver import TrisatSdrReceiver


class TestIqCaptureReader(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.capture = Path(directory.name) / "samples.iq"

    def source(self, fmt="int8"):
        return SdrStreamSource(SdrChannelConfig(
            driver="file", iq_file_path=str(self.capture), iq_format=fmt,
        ))

    def test_varying_read_sizes_preserve_all_pairs_in_supported_formats(self):
        for fmt, layout, bias, scale in (
            ("int8", "bb", 0, 128),
            ("uint8", "BB", 127.5, 127.5),
            ("int16", "<hh", 0, 32768),
            ("float32", "<ff", 0, 1),
        ):
            with self.subTest(format=fmt):
                pairs = [(i, 50 - i) for i in range(13)]
                self.capture.write_bytes(b"".join(struct.pack(layout, *p) for p in pairs))
                reader = self.source(fmt)
                sizes = (2, 0, 5, 1, 3, 6, 1, 8)
                blocks = [reader.read_iq_samples(size) for size in sizes]
                self.assertEqual([len(block) for block in blocks], [2, 0, 5, 1, 3, 2, 0, 0])
                self.assertEqual(
                    [sample for block in blocks for sample in block],
                    [complex((i - bias) / scale, (q - bias) / scale) for i, q in pairs],
                )

    def test_complete_final_pair_without_wrapping(self):
        self.capture.write_bytes(bytes((1, 2, 3, 4)))
        reader = self.source()
        self.assertEqual(reader.read_iq_samples(1), [complex(1, 2) / 128])
        self.assertEqual(reader.read_iq_samples(1), [complex(3, 4) / 128])
        self.assertEqual(reader.read_iq_samples(1), [])
        self.assertEqual(reader.read_iq_samples(2), [])

    def test_incomplete_tail_and_empty_capture_do_not_invent_samples(self):
        self.capture.write_bytes(struct.pack("<hh", -512, 1024) + b"\x12\x34\x56")
        reader = self.source("int16")
        self.assertEqual(reader.read_iq_samples(10), [complex(-512, 1024) / 32768])
        self.assertEqual(reader.read_iq_samples(1), [])
        self.capture.write_bytes(b"")
        self.assertEqual(self.source().read_iq_samples(8), [])

    def test_missing_file_is_reported_and_retry_starts_at_first_pair(self):
        reader = self.source()
        with self.assertRaises(FileNotFoundError):
            reader.read_iq_samples(2)
        self.capture.write_bytes(bytes((11, 13, 17, 19)))
        self.assertEqual(reader.read_iq_samples(1), [complex(11, 13) / 128])
        self.assertEqual(reader.read_iq_samples(3), [complex(17, 19) / 128])

    def test_invalid_format_and_count_are_rejected(self):
        self.capture.write_bytes(bytes((1, 2)))
        with self.assertRaisesRegex(ValueError, "format"):
            self.source("complex128").read_iq_samples(1)
        reader = self.source()
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            reader.read_iq_samples(-1)
        self.assertEqual(reader.read_iq_samples(1), [complex(1, 2) / 128])

    def test_receiver_reads_acquisition_tracking_and_final_short_block_in_order(self):
        pairs = [(i, -i) for i in range(1024 + 512 + 1)]
        self.capture.write_bytes(b"".join(struct.pack("<hh", *pair) for pair in pairs))
        config = ReceiverConfig()
        config.primary_sdr.driver = "file"
        config.primary_sdr.band_id = "GAL_E6"
        config.primary_sdr.iq_file_path = str(self.capture)
        config.primary_sdr.iq_format = "int16"
        config.dual_sdr_enabled = False
        config.telemetry.udp_enabled = False
        config.telemetry.tcp_enabled = False
        receiver = TrisatSdrReceiver(config)
        source = receiver.primary_stream

        with patch.object(source, "compute_power_spectrum_db", wraps=source.compute_power_spectrum_db) as spectrum:
            receiver.initialize_acquisition()
            for epoch in (1, 2):
                snapshot = receiver.step_epoch()
                self.assertEqual(snapshot["epoch"], epoch)
                self.assertTrue(snapshot["tracking_channels"])
            with self.assertRaises(EOFError):
                receiver.step_epoch()

        blocks = [call.args[0] for call in spectrum.call_args_list]
        self.assertEqual([len(block) for block in blocks], [1024, 512, 1, 0])
        self.assertEqual(
            [sample for block in blocks for sample in block],
            [complex(i, q) / 32768 for i, q in pairs],
        )
        self.assertEqual(receiver.get_status_snapshot()["epoch"], 2)

    def test_secondary_band_change_keeps_capture_position(self):
        pairs = [(i, -i) for i in range(1024 + 1024 + 1)]
        self.capture.write_bytes(b"".join(struct.pack("<hh", *pair) for pair in pairs))
        config = ReceiverConfig(doppler_search_max_hz=0)
        config.secondary_sdr.driver = "file"
        config.secondary_sdr.iq_file_path = str(self.capture)
        config.secondary_sdr.iq_format = "int16"
        receiver = TrisatSdrReceiver(config)
        source = receiver.secondary_stream

        with patch.object(source, "compute_power_spectrum_db", wraps=source.compute_power_spectrum_db) as spectrum:
            receiver.initialize_acquisition()
            receiver.switch_secondary_band("GAL_E5A")
        self.assertIs(receiver.secondary_stream, source)
        self.assertEqual(source.band_spec.band_id, "GAL_E5A")

        blocks = [call.args[0] for call in spectrum.call_args_list]
        blocks.append(source.read_iq_samples(2))
        self.assertEqual([len(block) for block in blocks], [1024, 1024, 1])
        self.assertEqual(
            [sample for block in blocks for sample in block],
            [complex(i, q) / 32768 for i, q in pairs],
        )

    def test_short_non_e1b_capture_is_supported_during_acquisition(self):
        self.capture.write_bytes(bytes((1, 2, 3, 4)))
        config = ReceiverConfig()
        config.primary_sdr.driver = "file"
        config.primary_sdr.band_id = "GAL_E6"
        config.primary_sdr.iq_file_path = str(self.capture)
        config.dual_sdr_enabled = False
        receiver = TrisatSdrReceiver(config)
        self.assertTrue(receiver.initialize_acquisition())
        with self.assertRaises(EOFError):
            receiver.step_epoch()


if __name__ == "__main__":
    unittest.main()
