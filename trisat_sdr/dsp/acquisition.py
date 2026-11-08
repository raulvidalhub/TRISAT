"""
Parallel Code Phase Search (PCPS) FFT Acquisition Engine for TRISAT-SDR.
Supports Galileo E1B/C (CBOC), Galileo E5a/E5b (AltBOC/BPSK(10)),
Galileo E6B/C (BPSK(5) HAS), and GPS L1 C/A.
Automatically uses NumPy FFT when installed, with a built-in pure-Python
Cooley-Tukey radix-2 FFT fallback for zero-dependency portability across
macOS, GNU/Linux, and Windows.
"""

import cmath
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .codes import HAS_NUMPY, np, sample_code_waveform


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

    def _get_replica_fft(self, band_id: str, svid: int, fft_len: int):
        key = (band_id, svid, fft_len, int(self.sample_rate_hz))
        if key in self._code_fft_cache:
            return self._code_fft_cache[key]

        # Coherent window: 1 ms for GPS L1 / E5 / E6, or 4 ms (or truncated to fft_len) for E1
        dur_ms = (fft_len / self.sample_rate_hz) * 1e3
        replica = sample_code_waveform(band_id, svid, self.sample_rate_hz, duration_ms=dur_ms)
        if len(replica) < fft_len:
            replica = replica + [0.0] * (fft_len - len(replica))
        else:
            replica = replica[:fft_len]

        if HAS_NUMPY:
            arr = np.array(replica, dtype=np.complex64)
            spec_conj = np.conj(np.fft.fft(arr))
            self._code_fft_cache[key] = spec_conj
            return spec_conj
        else:
            c_rep = [complex(v, 0.0) for v in replica]
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
        # Use a fast radix-2 window (e.g. 1024 or 2048 samples) for real-time responsiveness
        target_len = min(len(iq_samples), 2048 if HAS_NUMPY else 512)
        fft_len = _next_power_of_two(target_len)
        if fft_len > len(iq_samples):
            fft_len >>= 1
        fft_len = max(fft_len, 256)

        x_slice = list(iq_samples[:fft_len])
        # The final capture block can be shorter than the minimum FFT window.
        x_slice.extend([0j] * (fft_len - len(x_slice)))
        code_fft_conj = self._get_replica_fft(band_id, svid, fft_len)

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
            n_idx = np.arange(fft_len, dtype=np.float32)
            for fd in doppler_bins:
                carrier = np.exp(-1j * (2.0 * math.pi * fd / self.sample_rate_hz) * n_idx)
                x_fft = np.fft.fft(x_arr * carrier)
                corr = np.fft.ifft(x_fft * code_fft_conj)
                mag_sq = np.abs(corr) ** 2
                peak_idx = int(np.argmax(mag_sq))
                peak_val = float(mag_sq[peak_idx])
                total_power_accum += float(np.sum(mag_sq))
                total_cells += fft_len
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
                    for n in range(fft_len)
                ]
                x_fft = _radix2_fft(mixed, inverse=False)
                prod = [x_fft[k] * code_fft_conj[k] for k in range(fft_len)]
                corr = _radix2_fft(prod, inverse=True)
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
        # Coherent integration bandwidth B_coh ~ sample_rate_hz / fft_len
        bw_hz = self.sample_rate_hz / fft_len
        cn0_dbhz = min(56.0, max(25.0, snr_db + 10.0 * math.log10(bw_hz) - 18.0))
        acquired = snr_db >= self.threshold_snr_db

        # Downsample profile to 64 points for compact UI rendering
        step = max(1, len(best_profile) // 64)
        compact_profile = [round(best_profile[i] / noise_floor, 2) for i in range(0, len(best_profile), step)][:64]
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
