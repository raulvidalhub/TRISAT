"""Read Galileo I/NAV pages from a local Septentrio SBF recording."""

import argparse
import binascii
import json
import mmap
import struct
from pathlib import Path

SYNC = b"$@"
HEADER = struct.Struct("<HHH")
GAL_RAW_INAV = 4023
GAL_BANDS = {17: "E1-B", 21: "E5b-I"}


def read_pages(path):
    """Yield valid SBF Galileo I/NAV blocks in their recorded order."""
    with path.open("rb") as stream:
        if not stream.seek(0, 2):
            return
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            offset = 0
            while (start := data.find(SYNC, offset)) != -1:
                if start + 8 > len(data):
                    break
                crc, block_id, length = HEADER.unpack_from(data, start + 2)
                end = start + length
                if (
                    length < 8
                    or length % 4
                    or end > len(data)
                    or binascii.crc_hqx(data[start + 4 : end], 0) != crc
                ):
                    # Search again from the next byte so a damaged length
                    # cannot cause a valid following block to be skipped.
                    offset = start + 1
                    continue
                offset = end

                if block_id & 0x1FFF != GAL_RAW_INAV or length < 52:
                    continue

                tow_ms, week, svid, nav_crc, _, signal = struct.unpack_from(
                    "<IHBBBB", data, start + 8
                )
                band = GAL_BANDS.get(signal & 0x1F)
                if (
                    band is None
                    or not 71 <= svid <= 106
                    or week == 65535
                    or tow_ms >= 604_800_000
                ):
                    continue

                words = struct.unpack_from("<8I", data, start + 20)
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
    parser.add_argument("--merkle-tree", type=Path, help="Trusted Galileo Merkle tree XML for offline OSNMA")
    parser.add_argument("--public-key", type=Path, help="Trusted Galileo public key XML for offline OSNMA")
    args = parser.parse_args()
    if (args.merkle_tree is None) != (args.public_key is None):
        parser.error("Offline OSNMA requires both --merkle-tree and --public-key.")

    try:
        pages = read_pages(args.file)
        verification = None
        if args.merkle_tree is not None:
            from .osnma_replay import verify_recording

            pages = list(pages)
            verification = verify_recording(pages, args.merkle_tree, args.public_key)
        if args.jsonl:
            for index, page in enumerate(pages):
                if verification is not None:
                    page = {**page, "osnma_verification": verification.at(index, page["svid"])}
                print(json.dumps(page))
        else:
            from .ui.sbf_replay import serve_replay

            frames = list(pages)
            if not frames:
                parser.error("The recording contains no supported Galileo I/NAV blocks.")
            serve_replay(frames, args.port, verification)
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
