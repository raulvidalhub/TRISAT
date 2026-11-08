"""Verify OSNMA offline from timed ZED-F9P Galileo E1-B UBX packets."""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from trisat_sdr.osnma_replay import verify_timed_pages

from .f9p_stream import calculate_checksum
from .galileo_inav import decode_sfrbx

SECONDS_PER_WEEK = 604_800
SFRBX_HEADER = bytes.fromhex("B5 62 02 13 28 00")


@dataclass
class CaptureStats:
    records: int = 0
    accepted_pages: int = 0
    rejected_ubx: int = 0
    rejected_inav: int = 0
    duplicate_pages: int = 0
    broadcast_time_checks: int = 0
    missing_epochs: int = 0


def broadcast_time(page):
    """Return the broadcast (week, TOW), with week absent for WT6."""
    if page.word_type not in (0, 5, 6):
        return None

    # OS SIS ICD 2.2, Table 38: the 128-bit navigation word excludes
    # the two page flags in each half and the even half's six tail bits.
    bits = f"{int.from_bytes(page.pages, 'big'):0240b}"
    word = bits[2:114] + bits[122:138]
    if page.word_type == 5:  # Table 46
        return int(word[73:85], 2), int(word[85:105], 2)
    if page.word_type == 6:  # Table 47
        return None, int(word[105:125], 2)
    if word[6:8] == "10":  # Table 54: WT0 includes GST only in this format.
        return int(word[96:108], 2), int(word[108:128], 2)
    return None


def timed_inav(records, stats=None):
    """Decode JSONL records whose GST denotes the first transmitted symbol."""
    if stats is None:
        stats = CaptureStats()
    last_accepted_epoch = None
    previous_epoch = None
    seen = {}
    for line_number, line in enumerate(records, 1):
        if not line.strip():
            continue
        stats.records += 1
        try:
            record = json.loads(line)
            week, tow = record["galileo_week"], record["tow_s"]
            frame = bytes.fromhex(record["ubx_hex"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Line {line_number}: expected Galileo week, TOW and UBX hex.") from exc
        if (
            type(week) is not int or not 0 <= week < 4096
            or type(tow) is not int or not 0 < tow < SECONDS_PER_WEEK or tow % 2 != 1
        ):
            raise ValueError(f"Line {line_number}: invalid Galileo E1-B page start time.")
        epoch = (week, tow)
        if previous_epoch is not None and epoch < previous_epoch:
            raise ValueError(f"Line {line_number}: page times are out of order.")
        if epoch != previous_epoch:
            previous_epoch = epoch
            seen.clear()

        if (
            len(frame) != 48 or not frame.startswith(SFRBX_HEADER)
            or calculate_checksum(frame[:-2]) != frame[-2:]
        ):
            stats.rejected_ubx += 1
            continue
        page = decode_sfrbx(frame[6:-2])
        if page is None or page.band != "E1-B":
            stats.rejected_inav += 1
            continue
        if page.svid in seen:
            if seen[page.svid] != page.pages:
                raise ValueError(f"Line {line_number}: conflicting pages for one satellite and epoch.")
            stats.duplicate_pages += 1
            continue

        broadcast = broadcast_time(page)
        if broadcast is not None:
            broadcast_week, broadcast_tow = broadcast
            if broadcast_tow != tow or (broadcast_week is not None and broadcast_week != week):
                broadcast_epoch = (
                    f"TOW {broadcast_tow}" if broadcast_week is None
                    else f"{broadcast_week}/{broadcast_tow}"
                )
                raise ValueError(
                    f"Line {line_number}: GST mismatch for E{page.svid:02d} WT{page.word_type}. "
                    f"Capture {week}/{tow}, broadcast {broadcast_epoch}."
                )
            stats.broadcast_time_checks += 1

        absolute_epoch = week * SECONDS_PER_WEEK + tow
        if last_accepted_epoch is not None and absolute_epoch > last_accepted_epoch:
            stats.missing_epochs += (absolute_epoch - last_accepted_epoch) // 2 - 1
        last_accepted_epoch = absolute_epoch
        seen[page.svid] = page.pages
        stats.accepted_pages += 1
        yield page.svid, week, tow, page.pages, page.band, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="GST-timed UBX packets in JSON Lines format")
    parser.add_argument("--merkle-tree", type=Path, required=True, help="Trusted Galileo Merkle tree XML")
    parser.add_argument("--public-key", type=Path, required=True, help="Trusted Galileo public key XML")
    args = parser.parse_args()

    stats = CaptureStats()
    try:
        with args.capture.open(encoding="utf-8") as records:
            timeline = verify_timed_pages(timed_inav(records, stats), args.merkle_tree, args.public_key)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")

    verified, failed = timeline.totals(), timeline.failures()
    if stats.accepted_pages == 0:
        status = "no_valid_pages"
    elif failed:
        status = "tag_failures"
    elif verified:
        status = "tags_verified"
    else:
        status = "no_verifiable_tags"

    print(json.dumps({
        "source": "recorded_zed_f9p_inav",
        "status": status,
        "capture": asdict(stats),
        "verified_tags_by_svid": verified,
        "failed_tags_by_svid": failed,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
