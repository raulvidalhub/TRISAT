"""Receiver-reported measurements and solutions in SBF recordings."""

import math
import struct
from bisect import bisect_right

from .sbf import WEEK_MS, gps_time_ms, read_blocks
from .sbf_measurements import MEAS_EPOCH, signal_quality

ATT_EULER = 5938
AUX_ANT_POSITIONS = 5942
PVT_GEODETIC = 4007
MAX_SAMPLE_AGE_MS = 2_000
ATTITUDE_MODES = {1: "float", 2: "fixed", 3: "float", 4: "fixed"}
BASELINE_MODES = {0: "fixed", 1: "float"}
POSITION_MODES = {
    1: "standalone",
    2: "differential",
    3: "fixed_location",
    4: "rtk_fixed",
    5: "rtk_float",
    6: "sbas",
    7: "moving_base_rtk_fixed",
    8: "moving_base_rtk_float",
    10: "ppp",
}


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


def _position(block, timestamp):
    if len(block) < 88:
        return None
    mode, error = block[14:16]
    mode_code = mode & 0x0F
    solution = "unavailable" if error or not mode_code else POSITION_MODES.get(mode_code, "unknown")
    dimensions = (2 if mode & 0x80 else 3) if solution in POSITION_MODES.values() else None

    latitude, longitude, height = struct.unpack_from("<ddd", block, 16)
    valid_coordinates = (
        dimensions is not None
        and -math.pi / 2 <= latitude <= math.pi / 2
        and -math.pi <= longitude <= math.pi
    )
    height_available = valid_coordinates and dimensions == 3 and math.isfinite(height) and height != -2e10
    datum = block[73]
    return {
        **timestamp,
        "solution": solution,
        "mode_code": mode_code,
        "error_code": error,
        "dimensions": dimensions,
        "latitude_deg": math.degrees(latitude) if valid_coordinates else None,
        "longitude_deg": math.degrees(longitude) if valid_coordinates else None,
        "ellipsoidal_height_m": height if height_available else None,
        "datum_code": datum if valid_coordinates and datum != 255 else None,
    }


def _read_samples(path, block_types, source):
    for kind, block in read_blocks(path, block_types):
        if len(block) < 16:
            continue
        tow_ms, week = struct.unpack_from("<IH", block, 8)
        if week == 65535 or tow_ms >= WEEK_MS:
            continue
        timestamp = {"gps_week": week, "tow_ms": tow_ms}
        if kind == ATT_EULER:
            sample = _attitude(block, timestamp)
        elif kind == PVT_GEODETIC:
            sample = _position(block, timestamp)
        elif kind == MEAS_EPOCH:
            sample = signal_quality(block, timestamp)
        else:
            sample = _baseline(block, timestamp, source)
        if sample is not None:
            yield kind, sample


class ReceiverTimeline:
    """Look up the latest fresh receiver samples at a playback timestamp."""

    def __init__(self, recording, baseline_file=None):
        self._samples = {ATT_EULER: [], AUX_ANT_POSITIONS: [], PVT_GEODETIC: [], MEAS_EPOCH: []}
        block_types = {ATT_EULER, PVT_GEODETIC, MEAS_EPOCH}
        if baseline_file is None:
            block_types.add(AUX_ANT_POSITIONS)
        for kind, sample in _read_samples(recording, block_types, "main"):
            self._samples[kind].append(sample)
        if baseline_file is not None:
            baseline = self._samples[AUX_ANT_POSITIONS]
            baseline.extend(
                sample for _, sample in _read_samples(baseline_file, {AUX_ANT_POSITIONS}, "auxiliary")
            )
            if not baseline:
                raise ValueError("The auxiliary recording contains no Main–Aux1 position samples.")
        for samples in self._samples.values():
            samples.sort(key=gps_time_ms)

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
        telemetry = {}
        attitude = self._samples[ATT_EULER]
        baseline = self._samples[AUX_ANT_POSITIONS]
        if attitude or baseline:
            telemetry["antenna_attitude"] = {
                "attitude": self._latest(attitude, now),
                "baseline": self._latest(baseline, now),
            }
        position = self._samples[PVT_GEODETIC]
        if position:
            telemetry["receiver_position"] = self._latest(position, now)
        quality = self._samples[MEAS_EPOCH]
        if quality:
            telemetry["galileo_signal_quality"] = self._latest(quality, now)
        return telemetry
