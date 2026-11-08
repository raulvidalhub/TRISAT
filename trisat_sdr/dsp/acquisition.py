"""
Parallel Code Phase Search (PCPS) FFT Acquisition Engine for TRISAT-SDR.
Supports Galileo E1-B (CBOC), Galileo E5a/E5b (AltBOC/BPSK(10)),
Galileo E6B/C (BPSK(5) HAS), and GPS L1 C/A.
Automatically uses NumPy FFT when installed, with a built-in pure-Python
Cooley-Tukey radix-2 FFT fallback for zero-dependency portability across
macOS, GNU/Linux, and Windows.
"""

import cmath
import math
from dataclasses import dataclass, field
from typing import List, Sequence

from .codes import (
    GALILEO_E1_CHIP_RATE,
    GALILEO_E1_PERIOD_MS,
    GALILEO_E1_SVIDS,
    HAS_NUMPY,
    np,
    sample_code_waveform,
)


@dataclass
class AcquisitionResult:
    """Result of a PCPS 2D Doppler + Code Phase search for a single satellite."""
    band_id: str
    constellation: str
    svid: int
    acquired: bool
    doppler_hz: float
    code_phase_samples: int
    code_phase_chips: float
    cn0_dbhz: float
    peak_metric: float
    correlation_profile: List[float] = field(default_factory=list)


def _next_power_of_two(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


def _radix2_fft(x: List[complex], inverse: bool = False) -> List[complex]:
    """Iterative Cooley-Tukey radix-2 FFT / IFFT for pure-Python fallback."""
    n = len(x)
    if n <= 1:
        return list(x)

    # Bit-reversal permutation
    j = 0
    a = list(x)
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]

    length = 2
    sign = 1.0 if inverse else -1.0
    while length <= n:
        ang = sign * 2.0 * math.pi / length
        wlen = complex(math.cos(ang), math.sin(ang))
        half = length >> 1
        for i in range(0, n, length):
            w = 1.0 + 0.0j
            for k in range(i, i + half):
                u = a[k]
                v = a[k + half] * w
                a[k] = u + v
                a[k + half] = u - v
                w *= wlen
        length <<= 1

    if inverse:
        inv_n = 1.0 / n
        a = [val * inv_n for val in a]
    return a


class PcpsAcquisitionEngine:
    """
    Frequency-domain Parallel Code Phase Search (PCPS) GNSS Acquisition Engine.
    Computes:
      R(f_d, tau) = | IFFT( FFT(x[n] * e^{-j 2 pi f_d n / f_s}) * conj(FFT(c[n])) ) |^2
    """

    def __init__(
        self,
        sample_rate_hz: float = 4.092e6,
        doppler_max_hz: float = 5000.0,
        doppler_step_hz: float = 250.0,
        threshold_snr_db: float = 11.5,
    ):
        self.sample_rate_hz = sample_rate_hz
        self.doppler_max_hz = doppler_max_hz
        self.doppler_step_hz = doppler_step_hz
        self.threshold_snr_db = threshold_snr_db
        self._code_fft_cache: dict = {}

    @property
    def e1b_window_samples(self) -> int:
        """Two primary periods allow the search to span an unknown symbol boundary."""
        return 2 * round(self.sample_rate_hz * GALILEO_E1_PERIOD_MS / 1000)

    def acquire_galileo_e1b(self, iq_samples: Sequence[complex]) -> List[AcquisitionResult]:
        """Search all assigned E1-B codes and confirm weaker candidates after subtraction."""
        def search(samples: Sequence[complex], svid: int) -> AcquisitionResult:
            return self.acquire_satellite(samples, "GAL_E1", "GALILEO", svid, 4092)

        results = [search(iq_samples, svid) for svid in GALILEO_E1_SVIDS]
        candidates = sorted(
            (index for index, result in enumerate(results) if result.acquired),
            key=lambda index: results[index].peak_metric,
            reverse=True,
        )
        if len(candidates) < 2:
            return results

        residual = list(iq_samples[:self.e1b_window_samples])
        for rank, index in enumerate(candidates):
            if rank > 0:
                original = results[index]
                confirmed = search(residual, original.svid)
                # A different peak in the residual does not confirm the original detection.
                confirmed.acquired = confirmed.acquired and self._e1b_peaks_match(original, confirmed)
                results[index] = confirmed
            if results[index].acquired and rank < len(candidates) - 1:
                self._subtract_e1b_signal(residual, results[index])
        return results

    def _e1b_peaks_match(self, original: AcquisitionResult, confirmed: AcquisitionResult) -> bool:
        period = self.e1b_window_samples // 2
        phase_delta = abs(original.code_phase_samples - confirmed.code_phase_samples)
        phase_delta = min(phase_delta, period - phase_delta)
        chip_samples = math.ceil(self.sample_rate_hz / GALILEO_E1_CHIP_RATE)
        doppler_delta = abs(original.doppler_hz - confirmed.doppler_hz)
        return phase_delta <= chip_samples and doppler_delta <= self.doppler_step_hz

    def _subtract_e1b_signal(self, residual: List[complex], result: AcquisitionResult) -> None:
        """Fit the detected code and one complex gain per symbol to the search window."""
        period = self.e1b_window_samples // 2
        replica = sample_code_waveform(
            "GAL_E1", result.svid, self.sample_rate_hz, duration_ms=period * 1000 / self.sample_rate_hz
        )
        phase = result.code_phase_samples
        radians_per_sample = math.tau * result.doppler_hz / self.sample_rate_hz

        # The winning lag contains a full symbol. Its two halves estimate the
        # carrier phase drift left by the coarse Doppler bin.
        half = period // 2
        despread = [
            residual[phase + i] * replica[i] * cmath.exp(-1j * radians_per_sample * i)
            for i in range(2 * half)
        ]
        if half:
            first = sum(despread[:half])
            second = sum(despread[half:])
            radians_per_sample += cmath.phase(second * first.conjugate()) / half

        # Independent gains allow a data polarity change at every code boundary.
        carrier_code = [chip * cmath.exp(1j * radians_per_sample * i) for i, chip in enumerate(replica)]
        first_symbol = phase - period if phase else 0
        for symbol_start in range(first_symbol, len(residual), period):
            start = max(symbol_start, 0)
            stop = min(symbol_start + period, len(residual))
            template = carrier_code[start - symbol_start:stop - symbol_start]
            energy = sum(abs(value) ** 2 for value in template)
            gain = sum(residual[i] * value.conjugate() for i, value in enumerate(template, start)) / energy
            for i, value in enumerate(template, start):
                residual[i] -= gain * value

    def _get_replica_fft(self, band_id: str, svid: int, replica_len: int, fft_len: int):
        key = (band_id, svid, replica_len, fft_len, self.sample_rate_hz)
        if key in self._code_fft_cache:
            return self._code_fft_cache[key]

        dur_ms = (replica_len / self.sample_rate_hz) * 1e3
        replica = sample_code_waveform(band_id, svid, self.sample_rate_hz, duration_ms=dur_ms)

        if HAS_NUMPY:
            arr = np.array(replica, dtype=np.complex64)
            spec_conj = np.conj(np.fft.fft(arr, n=fft_len))
            self._code_fft_cache[key] = spec_conj
            return spec_conj
        else:
            c_rep = [complex(v, 0.0) for v in replica]
            c_rep.extend([0j] * (fft_len - len(c_rep)))
            spec = _radix2_fft(c_rep, inverse=False)
            spec_conj = [ val.conjugate() for val in spec ]
            self._code_fft_cache[key] = spec_conj
            return spec_conj

    def acquire_satellite(
        self,
        iq_samples: Sequence[complex],
        band_id: str,
        constellation: str,
        svid: int,
        code_length_chips: int,
    ) -> AcquisitionResult:
        """Runs PCPS acquisition across Doppler bins for a single satellite PRN/SVID."""
        is_e1b = band_id == "GAL_E1"
        if is_e1b:
            window_len = self.e1b_window_samples
            if window_len == 0 or len(iq_samples) < window_len:
                return AcquisitionResult(band_id, constellation, svid, False, 0.0, 0, 0.0, 0.0, 0.0)
            # A padded one-period replica allows linear correlation at each lag
            # that fits in the input window, without wrapping the IQ samples.
            replica_len = window_len // 2
            fft_len = window_len if HAS_NUMPY else _next_power_of_two(window_len)
        else:
            target_len = min(len(iq_samples), 2048 if HAS_NUMPY else 512)
            fft_len = _next_power_of_two(target_len)
            if fft_len > len(iq_samples):
                fft_len >>= 1
            fft_len = max(fft_len, 256)
            window_len = replica_len = fft_len
        x_slice = list(iq_samples[:window_len])
        x_slice.extend([0j] * (window_len - len(x_slice)))
        code_fft_conj = self._get_replica_fft(band_id, svid, replica_len, fft_len)

        doppler_bins: List[float] = []
        f = -self.doppler_max_hz
        while f <= self.doppler_max_hz + 1e-6:
            doppler_bins.append(f)
            f += self.doppler_step_hz

        best_peak = 0.0
        best_doppler = 0.0
        best_phase = 0
        best_profile: List[float] = []
        total_power_accum = 0.0
        total_cells = 0

        if HAS_NUMPY:
            x_arr = np.array(x_slice, dtype=np.complex64)
            n_idx = np.arange(window_len, dtype=np.float64 if is_e1b else np.float32)
            for fd in doppler_bins:
                carrier = np.exp(-1j * (2.0 * math.pi * fd / self.sample_rate_hz) * n_idx)
                x_fft = np.fft.fft(x_arr * carrier, n=fft_len)
                corr = np.fft.ifft(x_fft * code_fft_conj)[:replica_len]
                mag_sq = np.abs(corr) ** 2
                peak_idx = int(np.argmax(mag_sq))
                peak_val = float(mag_sq[peak_idx])
                total_power_accum += float(np.sum(mag_sq))
                total_cells += replica_len
                if peak_val > best_peak:
                    best_peak = peak_val
                    best_doppler = fd
                    best_phase = peak_idx
                    best_profile = [float(v) for v in mag_sq]
        else:
            for fd in doppler_bins:
                w_step = -2.0 * math.pi * fd / self.sample_rate_hz
                mixed = [
                    x_slice[n] * complex(math.cos(w_step * n), math.sin(w_step * n))
                    for n in range(window_len)
                ]
                mixed.extend([0j] * (fft_len - window_len))
                x_fft = _radix2_fft(mixed, inverse=False)
                prod = [x_fft[k] * code_fft_conj[k] for k in range(fft_len)]
                corr = _radix2_fft(prod, inverse=True)[:replica_len]
                mag_sq = [c.real * c.real + c.imag * c.imag for c in corr]
                for idx, val in enumerate(mag_sq):
                    total_power_accum += val
                    total_cells += 1
                    if val > best_peak:
                        best_peak = val
                        best_doppler = fd
                        best_phase = idx
                        best_profile = mag_sq

        noise_floor = max((total_power_accum - best_peak) / max(1, total_cells - 1), 1e-12)
        peak_metric = best_peak / noise_floor
        snr_db = 10.0 * math.log10(max(peak_metric, 1.0))
        # Coherent bandwidth depends on the replica, not the zero-padded FFT.
        bw_hz = self.sample_rate_hz / replica_len
        cn0_dbhz = min(56.0, max(25.0, snr_db + 10.0 * math.log10(bw_hz) - 18.0))
        threshold_db = self.threshold_snr_db
        distinct_peak = True
        if is_e1b:
            # Under white Gaussian noise each normalized power cell is approximately
            # exponential. Apply a union bound over the full search for a nominal
            # noise-only false-alarm budget of 1e-3 (including all SVIDs).
            search_cells = len(GALILEO_E1_SVIDS) * max(total_cells, 1)
            threshold_db = max(threshold_db, 10.0 * math.log10(math.log(search_cells / 1e-3)))
            # Exclude the main peak and nearby CBOC side lobes. Require a 3 dB
            # margin over other phases so a flat cross-correlation cannot lock.
            guard = math.ceil(self.sample_rate_hz / GALILEO_E1_CHIP_RATE)
            second_peak = max((
                power for phase, power in enumerate(best_profile)
                if guard < abs(phase - best_phase) < replica_len - guard
            ), default=0.0)
            distinct_peak = best_peak > 2.0 * second_peak
        acquired = snr_db >= threshold_db and distinct_peak

        # Downsample profile to 64 points for compact UI rendering
        step = max(1, len(best_profile) // 64)
        compact_profile = [round(best_profile[i] / noise_floor, 2) for i in range(0, len(best_profile), step)][:64]
        if is_e1b:
            chips = best_phase * GALILEO_E1_CHIP_RATE / self.sample_rate_hz
        else:
            chips = (best_phase / float(fft_len)) * code_length_chips

        return AcquisitionResult(
            band_id=band_id,
            constellation=constellation,
            svid=svid,
            acquired=acquired,
            doppler_hz=round(best_doppler, 1),
            code_phase_samples=best_phase,
            code_phase_chips=round(chips, 2),
            cn0_dbhz=round(cn0_dbhz, 1),
            peak_metric=round(snr_db, 2),
            correlation_profile=compact_profile,
        )
