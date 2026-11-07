"""Read Galileo I/NAV pages from a local Septentrio SBF recording."""

import argparse
import json
import struct
from pathlib import Path

from .sbf import WEEK_MS, read_blocks
from .sbf_attitude import AttitudeTimeline

GAL_RAW_INAV = 4023
GAL_BANDS = {17: "E1-B", 21: "E5b-I"}


def read_pages(path):
    """Yield valid SBF Galileo I/NAV blocks in their recorded order."""
    for _, block in read_blocks(path, {GAL_RAW_INAV}):
        if len(block) < 52:
            continue

        tow_ms, week, svid, nav_crc, _, signal = struct.unpack_from(
            "<IHBBBB", block, 8
        )
        band = GAL_BANDS.get(signal & 0x1F)
        if (
            band is None
            or not 71 <= svid <= 106
            or week == 65535
            or tow_ms >= WEEK_MS
        ):
            continue

        words = struct.unpack_from("<8I", block, 20)
        bits = struct.pack(">8I", *words)
        # SBF stores 234 decoded bits in eight words. Keep the final
        # two data bits, zero-pad for hex display, and omit word padding.
        payload = bits[:29] + bytes([bits[29] & 0xC0])
        yield {
            "source": "recorded",
            "receiver": "Septentrio SBF",
            "gps_week": week,
            "tow_ms": tow_ms,
            "svid": svid - 70,
            "band": band,
            "navigation_crc_passed": nav_crc == 1,
            "osnma_status": "unverified" if band == "E1-B" else "not_applicable",
            "bit_length": 234,
            "payload_hex": payload.hex().upper(),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Local .sbf recording")
    parser.add_argument("--jsonl", action="store_true", help="Print pages as JSON lines")
    parser.add_argument("--port", type=int, default=8085, help="Local web port (default: 8085)")
    parser.add_argument("--baseline-file", type=Path, help="Auxiliary SBF from the same receiver and session")
    parser.add_argument("--merkle-tree", type=Path, help="Trusted Galileo Merkle tree XML for offline OSNMA")
    parser.add_argument("--public-key", type=Path, help="Trusted Galileo public key XML for offline OSNMA")
    args = parser.parse_args()
    if (args.merkle_tree is None) != (args.public_key is None):
        parser.error("Offline OSNMA requires both --merkle-tree and --public-key.")

    try:
        pages = read_pages(args.file)
        motion = AttitudeTimeline(args.file, args.baseline_file)
        verification = None
        if args.merkle_tree is not None:
            from .osnma_replay import verify_recording

            pages = list(pages)
            verification = verify_recording(pages, args.merkle_tree, args.public_key)
        if args.jsonl:
            for index, page in enumerate(pages):
                if verification is not None:
                    page = {**page, "osnma_verification": verification.at(index, page["svid"])}
                if motion.has_data:
                    page = {**page, "antenna_attitude": motion.at(page)}
                print(json.dumps(page))
        else:
            from .ui.sbf_replay import serve_replay

            frames = list(pages)
            if not frames:
                parser.error("The recording contains no supported Galileo I/NAV blocks.")
            serve_replay(frames, args.port, verification, motion)
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
