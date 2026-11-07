"""Decode receiver-reported Galileo C/N₀ from SBF MeasEpoch blocks."""

MEAS_EPOCH = 4027
GALILEO_BANDS = {17: "E1", 19: "E6", 20: "E5a", 21: "E5b", 22: "E5 AltBOC"}
ANTENNAS = ("main", "aux1", "aux2")


def _add_signal(signals, svid, signal_type, cn0, e6b_used):
    band = GALILEO_BANDS.get(signal_type & 0x1F)
    antenna = signal_type >> 5
    if band is None or antenna >= len(ANTENNAS):
        return
    if band == "E6":
        band = "E6-B" if e6b_used else "E6-C"
    levels = signals.setdefault((svid, band), {})
    if cn0 != 255:
        # All Galileo signal types use the 10 dB-Hz offset.
        levels.setdefault(ANTENNAS[antenna], cn0 * 0.25 + 10)


def signal_quality(block, timestamp):
    if len(block) < 20:
        return None
    count, size1, size2, flags = block[14:18]
    if flags & 0x80:
        return {**timestamp, "scrambled": True, "signals": []}
    if count and size1 < 20:
        return None

    signals = {}
    e6b_used = bool(flags & 0x40)
    offset = 20
    for _ in range(count):
        nested_start = offset + size1
        if nested_start > len(block):
            return None
        nested_count = block[offset + 19]
        end = nested_start + nested_count * size2
        if (nested_count and size2 < 12) or end > len(block):
            return None
        svid = block[offset + 2] - 70
        if 1 <= svid <= 36:
            _add_signal(signals, svid, block[offset + 1], block[offset + 15], e6b_used)
            for index in range(nested_count):
                sub = nested_start + index * size2
                _add_signal(signals, svid, block[sub], block[sub + 2], e6b_used)
        offset = end

    return {
        **timestamp,
        "scrambled": False,
        "signals": [
            {"svid": svid, "band": band, "cn0_dbhz": levels}
            for (svid, band), levels in sorted(signals.items())
        ],
    }
