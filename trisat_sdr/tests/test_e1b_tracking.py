"""End-to-end tracking of a recorded signal with a deliberate dropout."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from trisat_sdr.config import SdrChannelConfig
from trisat_sdr.dsp import acquisition, codes
from trisat_sdr.track_iq import track_capture
from trisat_sdr.tests.test_galileo_e1b_acquisition import make_iq


@unittest.skipUnless(codes.HAS_NUMPY, "E1-B file tracking requires NumPy")
class TestE1bFileTracking(unittest.TestCase):
    def test_file_lock_drops_when_signal_disappears_and_resumes(self):
        np = codes.np
        rate = 4_000_000
        period = rate * 4 // 1000
        delay = 180
        doppler = 630
        symbols = 205
        waveform = np.asarray(make_iq(12, rate, delay, 0, noise_std=0))
        samples = np.arange(symbols * period)
        signal = np.tile(waveform, (symbols + 1) // 2)[:len(samples)]
        signal *= np.exp(2j * np.pi * doppler * samples / rate)
        # Blank precisely one 50-symbol tracking interval, leaving only noise.
        signal[delay + 101 * period - 8:delay + 151 * period + 8] = 0
        rng = np.random.default_rng(15)
        signal += 2 * (rng.normal(size=len(signal)) + 1j * rng.normal(size=len(signal)))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.iq"
            signal.astype("<c8").tofile(path)
            config = SdrChannelConfig(driver="file", iq_file_path=str(path), iq_format="float32",
                                      sample_rate_hz=rate)
            intervals = []
            with patch.object(acquisition, "GALILEO_E1_SVIDS", (12,)):
                read, summaries = track_capture(config, [0], 750, intervals.append)

        self.assertEqual(read, len(samples))
        self.assertEqual([interval.locked for interval in intervals], [True, True, False, True])
        self.assertTrue(all(a.end_sample == b.start_sample for a, b in zip(intervals, intervals[1:])))
        self.assertTrue(all(abs(interval.doppler_hz - doppler) < 5 for interval in intervals if interval.locked))
        summary = summaries[12]
        self.assertEqual(summary.losses, 1)
        self.assertAlmostEqual(summary.longest_lock / rate, 0.4, places=4)
        self.assertAlmostEqual(summary.locked_samples / rate, 0.6, places=4)
