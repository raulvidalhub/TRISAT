"""Verify OSNMA offline from timed ZED-F9P Galileo E1-B UBX packets."""

import argparse
import json
from pathlib import Path

from trisat_sdr.osnma_replay import verify_timed_pages

from .f9p_stream import calculate_checksum
from .galileo_inav import decode_sfrbx

SECONDS_PER_WEEK = 604_800
SFRBX_HEADER = bytes.fromhex("B5 62 02 13 28 00")


def timed_inav(records):
    """Decode JSONL records whose GST denotes the first transmitted symbol."""
    previous_epoch = None
    seen = {}
    for line_number, line in enumerate(records, 1):
        if not line.strip():
            continue
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

        if len(frame) != 48 or not frame.startswith(SFRBX_HEADER):
            continue
        if calculate_checksum(frame[:-2]) != frame[-2:]:
            continue
        page = decode_sfrbx(frame[6:-2])
        if page is None or page.band != "E1-B":
            continue
        if page.svid in seen:
            if seen[page.svid] != page.pages:
                raise ValueError(f"Line {line_number}: conflicting pages for one satellite and epoch.")
            continue
        seen[page.svid] = page.pages
        yield page.svid, week, tow, page.pages, page.band, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="GST-timed UBX packets in JSON Lines format")
    parser.add_argument("--merkle-tree", type=Path, required=True, help="Trusted Galileo Merkle tree XML")
    parser.add_argument("--public-key", type=Path, required=True, help="Trusted Galileo public key XML")
    args = parser.parse_args()

    try:
        with args.capture.open(encoding="utf-8") as records:
            timeline = verify_timed_pages(timed_inav(records), args.merkle_tree, args.public_key)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")

    print(json.dumps({
        "source": "recorded_zed_f9p_inav",
        "verified_tags_by_svid": timeline.totals(),
        "failed_tags_by_svid": timeline.failures(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
