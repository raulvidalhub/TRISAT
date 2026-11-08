"""Offline Galileo E1-B tracking from contiguous recorded IQ samples."""

import math
from dataclasses import dataclass

from .codes import GALILEO_E1_PERIOD_MS, HAS_NUMPY, np, sample_code_waveform


@dataclass(frozen=True)
class E1bTrackInterval:
    svid: int
    start_sample: int
    end_sample: int
    locked: bool
    doppler_hz: float
    code_phase_samples: float
    prompt_to_noise: float
    carrier_coherence: float


class E1bFileTracker:
    """Follow code and carrier over 50 consecutive 4 ms data symbols at a time."""

    SYMBOL_SECONDS = GALILEO_E1_PERIOD_MS / 1000
    BLOCK_SYMBOLS = 50
    MIN_FINAL_SYMBOLS = 25
    DELAY_RADIUS = 3
    CARRIER_HZ = 1_575_420_000
    FREQUENCY_FFT_SIZE = 512

    def __init__(self, acquisition, sample_rate_hz, sample_offset, doppler_step_hz):
        if not HAS_NUMPY:
            raise RuntimeError("E1-B IQ tracking requires NumPy.")
        self.svid = acquisition.svid
        self.sample_rate_hz = sample_rate_hz
        self.period = sample_rate_hz * self.SYMBOL_SECONDS
        # Keep equal halves for polarity-independent carrier estimation.
        self.samples = 2 * (round(self.period) // 2)
        self.doppler_hz = acquisition.doppler_hz
        self.next_sample = sample_offset + acquisition.code_phase_samples + self._symbol_step()
        self._max_residual_hz = doppler_step_hz / 2 + 15.0
        self._replica = np.asarray(sample_code_waveform(
            "GAL_E1", self.svid, sample_rate_hz, duration_ms=self.samples * 1000 / sample_rate_hz
        ), dtype=np.float32)
        self._energy = float(np.sum(self._replica ** 2))
        self._sample_indices = np.arange(self.samples)
        self._symbol_indices = np.arange(self.BLOCK_SYMBOLS)
        self._residual_bins = np.fft.fftfreq(self.FREQUENCY_FFT_SIZE, self.SYMBOL_SECONDS) / 2

    def _symbol_step(self):
        # Carrier Doppler also changes the apparent code rate.
        return self.period / (1 + self.doppler_hz / self.CARRIER_HZ)

    @property
    def keep_from(self):
        return round(self.next_sample) - self.DELAY_RADIUS

    def step(self, iq, sample_offset, eof=False):
        """Consume one complete interval, or a shorter final one at EOF."""
        step = self._symbol_step()
        starts = np.rint(self.next_sample + self._symbol_indices * step).astype(np.int64)
        if eof:
            starts = starts[starts + self.samples + self.DELAY_RADIUS <= sample_offset + len(iq)]
        if len(starts) < self.MIN_FINAL_SYMBOLS or starts[-1] + self.samples + self.DELAY_RADIUS > sample_offset + len(iq):
            return None
        if self.keep_from < sample_offset:
            raise ValueError("Missing IQ samples at the next E1-B tracking interval.")

        indices = starts[:, None] - sample_offset + self._sample_indices
        local = self._replica * np.exp((-2j * math.pi * self.doppler_hz / self.sample_rate_hz) * self._sample_indices)
        local = local.astype(np.complex64).reshape(2, -1)
        offsets = range(-self.DELAY_RADIUS, self.DELAY_RADIUS + 1)
        halves = np.stack([
            np.einsum("ijk,jk->ij", iq[indices + delay].reshape(len(starts), 2, -1), local)
            for delay in offsets
        ])
        powers = np.mean(np.abs(halves.sum(axis=2)) ** 2, axis=1)
        peak = int(np.argmax(powers))
        delay = offsets[peak]
        prompt_to_noise = float(powers[peak]) / max(
            float(np.mean(np.abs(iq[indices]) ** 2)) * self._energy, 1e-30
        )

        first, second = halves[peak].T
        times = (starts - starts[0]) / self.sample_rate_hz
        prompts = (first + second) * np.exp(-2j * math.pi * self.doppler_hz * times)
        residual, coherence = self._carrier_error(first, second, prompts, times)
        interior = 0 < peak < len(powers) - 1
        locked = interior and prompt_to_noise >= 2.5 and coherence >= 0.50
        phase = self.next_sample
        if locked:
            # Interpolate the local correlation peak for a fractional-sample code update.
            early, middle, late = powers[peak - 1:peak + 2]
            curvature = early + late - 2 * middle
            fraction = float(0.5 * (early - late) / curvature) if curvature < 0 else 0.0
            phase += delay + fraction
            self.doppler_hz += residual
            self._max_residual_hz = 20.0
        self.next_sample = phase + len(starts) * self._symbol_step()
        return E1bTrackInterval(
            self.svid, int(starts[0]), min(round(self.next_sample), sample_offset + len(iq)), locked,
            self.doppler_hz, phase % self.period, prompt_to_noise, coherence,
        )

    def _carrier_error(self, first, second, prompts, times):
        # BPSK data polarity disappears on squaring. Half-symbol correlation
        # disambiguates the 125 Hz aliases of the resulting frequency estimate.
        coarse = np.angle(np.vdot(first, second)) / (math.pi * self.SYMBOL_SECONDS)
        alias_spacing = 1 / (2 * self.SYMBOL_SECONDS)
        alias_center = coarse if self._max_residual_hz > alias_spacing / 2 else 0.0
        bins = self._residual_bins + np.rint((alias_center - self._residual_bins) / alias_spacing) * alias_spacing
        spectrum = np.abs(np.fft.fft(prompts ** 2, n=self.FREQUENCY_FFT_SIZE))
        residual = float(bins[np.argmax(np.where(np.abs(bins) <= self._max_residual_hz, spectrum, -1))])
        coherence = float(abs(np.sum(prompts ** 2 * np.exp(-4j * math.pi * residual * times)))) / max(
            float(np.sum(np.abs(prompts) ** 2)), 1e-30
        )
        return residual, coherence
