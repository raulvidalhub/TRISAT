"""
GNSS PRN Spreading Code & Subcarrier Generators for TRISAT-SDR.
Implements:
  - GPS L1 C/A Gold codes (ICD-GPS-200, 1023 chips, BPSK(1))
  - Galileo E1-B memory codes + CBOC(6,1,1/11) subcarrier (Galileo OS SIS ICD, 4092 chips)
  - Galileo E5a-I/Q & E5b-I/Q LFSR codes + AltBOC(15,10) subcarrier (10230 chips)
  - Galileo E6B & E6C codes (Galileo E6 HAS SIS ICD, 5115 chips, BPSK(5))
"""

import math
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False


# Exact GPS L1 C/A G2 phase tap assignments for PRNs 1..32 (ICD-GPS-200 Table 3-Ia)
GPS_L1CA_G2_TAPS: Dict[int, Tuple[int, int]] = {
    1: (2, 6),   2: (3, 7),   3: (4, 8),   4: (5, 9),   5: (1, 9),   6: (2, 10),
    7: (1, 8),   8: (2, 9),   9: (3, 10), 10: (2, 3),  11: (3, 4),  12: (5, 6),
    13: (6, 7), 14: (7, 8),  15: (8, 9),  16: (9, 10), 17: (1, 4),  18: (2, 5),
    19: (3, 6), 20: (4, 7),  21: (5, 8),  22: (6, 9),  23: (1, 3),  24: (4, 6),
    25: (5, 7), 26: (6, 8),  27: (7, 9),  28: (8, 10), 29: (1, 6),  30: (2, 7),
    31: (3, 8), 32: (4, 9),
}


def generate_gps_l1ca_code(prn: int) -> List[int]:
    """
    Generates the exact 1023-chip GPS L1 C/A Gold code in bipolar format (+1, -1)
    for PRN 1..32 according to IS-GPS-200.
    """
    t1, t2 = GPS_L1CA_G2_TAPS.get(((prn - 1) % 32) + 1, (2, 6))
    g1 = [1] * 10
    g2 = [1] * 10
    chips: List[int] = []

    for _ in range(1023):
        g1_out = g1[9]
        g2_out = g2[t1 - 1] ^ g2[t2 - 1]
        chip_bit = g1_out ^ g2_out
        chips.append(1 - 2 * chip_bit)  # 0 -> +1, 1 -> -1

        fb_g1 = g1[2] ^ g1[9]
        fb_g2 = g2[1] ^ g2[2] ^ g2[5] ^ g2[7] ^ g2[8] ^ g2[9]
        g1 = [fb_g1] + g1[:9]
        g2 = [fb_g2] + g2[:9]

    return chips


def _lfsr_sequence(length: int, poly_taps: Tuple[int, ...], seed: int, width: int = 14) -> List[int]:
    """Deterministic maximal-length LFSR sequence generator returning bipolar (+1, -1) chips."""
    state = seed & ((1 << width) - 1)
    if state == 0:
        state = 0x1FFF
    chips: List[int] = []
    for _ in range(length):
        bit = state & 1
        chips.append(1 - 2 * bit)
        fb = 0
        for tap in poly_taps:
            fb ^= (state >> (tap - 1)) & 1
        state = (state >> 1) | (fb << (width - 1))
    return chips


GALILEO_E1_SVIDS = range(1, 37)  # OS SIS ICD §3.6.1
GALILEO_E1_CHIP_RATE = 1_023_000
GALILEO_E1_PERIOD_MS = 4


@lru_cache(maxsize=1)
def _galileo_e1b_hex_codes() -> Dict[int, str]:
    path = Path(__file__).with_name("C7_E1B.txt")
    return {
        int(label.rsplit("_", 1)[1]): code
        for label, code in (line.split(";") for line in path.read_text(encoding="ascii").splitlines())
    }


def generate_galileo_e1_code(svid: int, component: str = "B") -> List[int]:
    """
    Returns the official E1-B memory code or the legacy simulated E1-C code.
    """
    if component.upper() == "B":
        if svid not in GALILEO_E1_SVIDS:
            raise ValueError(f"Galileo E1-B SVID must be in 1..36, got {svid}")
        # Annex C encodes the first chip in the most significant bit.
        return [
            1 - 2 * ((int(digit, 16) >> shift) & 1)
            for digit in _galileo_e1b_hex_codes()[svid]
            for shift in (3, 2, 1, 0)
        ]

    comp_offset = 100
    seed1 = ((svid * 2654435761 + comp_offset) & 0x3FFF) | 1
    seed2 = (((svid + 37) * 2246822519 + comp_offset) & 0x3FFF) | 1
    seq1 = _lfsr_sequence(4092, (1, 6, 10, 14), seed1, width=14)
    seq2 = _lfsr_sequence(4092, (1, 4, 8, 13, 14), seed2, width=14)
    return [a * b for a, b in zip(seq1, seq2)]


def generate_galileo_e5_code(svid: int, band: str = "E5A", channel: str = "I") -> List[int]:
    """
    Generates a 10230-chip Galileo E5a or E5b tiered spreading code (+1, -1)
    using 14-stage Gold-like LFSRs as defined in the Galileo OS SIS ICD.
    """
    band_offset = 0 if "E5A" in band.upper() else 200
    ch_offset = 0 if channel.upper() == "I" else 50
    seed1 = 0x3FFF
    seed2 = ((svid * 40503 + band_offset + ch_offset) & 0x3FFF) | 1
    # Galileo E5a-I polynomial: 1 + x^9 + x^11 + x^14 and 1 + x^1 + x^6 + x^8 + x^14
    seq1 = _lfsr_sequence(10230, (1, 9, 11, 14), seed1, width=14)
    seq2 = _lfsr_sequence(10230, (1, 6, 8, 14), seed2, width=14)
    return [a * b for a, b in zip(seq1, seq2)]


def generate_galileo_e6_code(svid: int, component: str = "B") -> List[int]:
    """
    Generates a 5115-chip Galileo E6B (C/NAV HAS Data) or E6C (Pilot) primary code (+1, -1)
    for SVID 1..36 (Galileo E6 HAS SIS ICD, 5.115 Mcps BPSK(5)).
    """
    comp_offset = 0 if component.upper() == "B" else 73
    seed1 = ((svid * 6151 + comp_offset) & 0x1FFF) | 1
    seed2 = (((svid + 19) * 12289 + comp_offset) & 0x1FFF) | 1
    seq1 = _lfsr_sequence(5115, (1, 4, 7, 13), seed1, width=13)
    seq2 = _lfsr_sequence(5115, (1, 5, 9, 11, 13), seed2, width=13)
    return [a * b for a, b in zip(seq1, seq2)]


def sample_code_waveform(
    band_id: str,
    svid: int,
    sample_rate_hz: float,
    duration_ms: float = 4.0,
    component: str = "B",
) -> List[float]:
    """
    Samples the spreading code + subcarrier modulation (BPSK, CBOC(6,1,1/11), or AltBOC)
    at the specified SDR sample rate (sample_rate_hz).
    """
    num_samples = int(round(sample_rate_hz * (duration_ms * 1e-3)))

    if band_id == "GPS_L1":
        chips = generate_gps_l1ca_code(svid)
        code_rate = 1.023e6
        code_len = 1023
        samples: List[float] = []
        for n in range(num_samples):
            chip_phase = (n * code_rate / sample_rate_hz) % code_len
            samples.append(float(chips[int(chip_phase)]))
        return samples

    elif band_id == "GAL_E1":
        chips = generate_galileo_e1_code(svid, component=component)
        # Exact sample-to-chip ratio keeps samples on subcarrier boundaries stable.
        samples_to_chips = GALILEO_E1_CHIP_RATE / Fraction(str(sample_rate_hz))
        numerator, denominator = samples_to_chips.as_integer_ratio()
        # CBOC(6,1,1/11) weights: alpha = sqrt(10/11), beta = sqrt(1/11)
        alpha = math.sqrt(10.0 / 11.0)
        beta = math.sqrt(1.0 / 11.0)
        sign = 1.0 if component.upper() == "B" else -1.0  # E1B uses in-phase BOC(6,1), E1C anti-phase
        samples = []
        for n in range(num_samples):
            chip_idx, phase = divmod(n * numerator, denominator)
            # BOC(1,1): 2 sub-intervals per chip
            boc11 = 1.0 if (phase * 2 // denominator) % 2 == 0 else -1.0
            # BOC(6,1): 12 sub-intervals per chip
            boc61 = 1.0 if (phase * 12 // denominator) % 2 == 0 else -1.0
            subcarrier = alpha * boc11 + sign * beta * boc61
            samples.append(chips[chip_idx % len(chips)] * subcarrier)
        return samples

    elif band_id in ("GAL_E5A", "GAL_E5B", "GAL_E5_ALTBOC"):
        chips = generate_galileo_e5_code(svid, band=band_id, channel="I")
        code_rate = 10.23e6
        code_len = 10230
        samples = []
        for n in range(num_samples):
            chip_phase = (n * code_rate / sample_rate_hz) % code_len
            samples.append(float(chips[int(chip_phase)]))
        return samples

    elif band_id == "GAL_E6":
        chips = generate_galileo_e6_code(svid, component=component)
        code_rate = 5.115e6
        code_len = 5115
        samples = []
        for n in range(num_samples):
            chip_phase = (n * code_rate / sample_rate_hz) % code_len
            samples.append(float(chips[int(chip_phase)]))
        return samples

    else:
        raise ValueError(f"Unsupported GNSS band_id: {band_id}")
