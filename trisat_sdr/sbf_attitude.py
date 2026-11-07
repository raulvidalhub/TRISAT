"""Receiver-reported attitude and Main–Aux1 separation in SBF recordings."""

import math
import struct
from bisect import bisect_right

from .sbf import WEEK_MS, gps_time_ms, read_blocks

ATT_EULER = 5938
AUX_ANT_POSITIONS = 5942
MAX_SAMPLE_AGE_MS = 2_000
ATTITUDE_MODES = {1: "float", 2: "fixed", 3: "float", 4: "fixed"}
BASELINE_MODES = {0: "fixed", 1: "float"}


def _attitude(block, timestamp):
    if len(block) < 44:
        return None
    _, error, mode = struct.unpack_from("<BBH", block, 14)
    heading, pitch = struct.unpack_from("<ff", block, 20)
    if error & 0x80:
        solution = "not_requested"
    elif error & 3 == 1:
        solution = "insufficient_measurements"
    elif error & 3:
        solution = "unavailable"
    else:
        solution = ATTITUDE_MODES.get(mode, "unavailable")
    usable = solution in ("fixed", "float")
    return {
        **timestamp,
        "solution": solution,
        "heading_deg": heading if usable and 0 <= heading <= 360 else None,
        "pitch_deg": pitch if usable and -90 <= pitch <= 90 else None,
    }


def _baseline(block, timestamp, source):
    if len(block) < 16:
        return None
    count, size = block[14:16]
    if size < 52 or 16 + count * size > len(block):
        return None
    for offset in range(16, 16 + count * size, size):
        _, error, ambiguity, antenna = block[offset : offset + 4]
        if antenna != 1:
            continue
        solution = BASELINE_MODES.get(ambiguity, "unavailable")
        if error:
            solution = "insufficient_measurements" if error == 1 else "unavailable"
        vector = struct.unpack_from("<ddd", block, offset + 4)
        distance = math.hypot(*vector)
        usable = solution in ("fixed", "float") and all(
            value != -2e10 for value in vector
        ) and math.isfinite(distance)
        return {
            **timestamp,
            "solution": solution,
            "distance_m": distance if usable else None,
            "source": source,
        }
    return None


def _read_samples(path, block_types, source):
    for kind, block in read_blocks(path, block_types):
        if len(block) < 16:
            continue
        tow_ms, week = struct.unpack_from("<IH", block, 8)
        if week == 65535 or tow_ms >= WEEK_MS:
            continue
        timestamp = {"gps_week": week, "tow_ms": tow_ms}
        sample = (
            _attitude(block, timestamp) if kind == ATT_EULER
            else _baseline(block, timestamp, source)
        )
        if sample is not None:
            yield kind, sample


class AttitudeTimeline:
    """Look up the latest fresh receiver samples at a playback timestamp."""

    def __init__(self, recording, baseline_file=None):
        self._attitude = []
        self._baseline = []
        block_types = {ATT_EULER, AUX_ANT_POSITIONS} if baseline_file is None else {ATT_EULER}
        for kind, sample in _read_samples(recording, block_types, "main"):
            (self._attitude if kind == ATT_EULER else self._baseline).append(sample)
        if baseline_file is not None:
            self._baseline.extend(
                sample for _, sample in _read_samples(baseline_file, {AUX_ANT_POSITIONS}, "auxiliary")
            )
            if not self._baseline:
                raise ValueError("The auxiliary recording contains no Main–Aux1 position samples.")
        self._attitude.sort(key=gps_time_ms)
        self._baseline.sort(key=gps_time_ms)

    @property
    def has_data(self):
        return bool(self._attitude or self._baseline)

    @staticmethod
    def _latest(samples, now):
        index = bisect_right(samples, now, key=gps_time_ms)
        if index:
            sample = samples[index - 1]
            age = now - gps_time_ms(sample)
            if age <= MAX_SAMPLE_AGE_MS:
                return {**sample, "age_ms": age}
        return None

    def at(self, page):
        now = gps_time_ms(page)
        return {
            "attitude": self._latest(self._attitude, now),
            "baseline": self._latest(self._baseline, now),
        }
