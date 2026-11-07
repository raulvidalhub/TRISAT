"""Read checksum-validated blocks from a local Septentrio recording."""

import binascii
import mmap
import struct

WEEK_MS = 604_800_000
_HEADER = struct.Struct("<HHH")


def gps_time_ms(sample):
    return sample["gps_week"] * WEEK_MS + sample["tow_ms"]


def read_blocks(path, block_types):
    """Yield requested SBF blocks in file order, recovering after corruption."""
    with path.open("rb") as stream:
        if not stream.seek(0, 2):
            return
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            offset = 0
            while (start := data.find(b"$@", offset)) != -1:
                if start + 8 > len(data):
                    break
                crc, block_id, length = _HEADER.unpack_from(data, start + 2)
                end = start + length
                if (
                    length < 8
                    or length % 4
                    or end > len(data)
                    or binascii.crc_hqx(data[start + 4 : end], 0) != crc
                ):
                    # A damaged length must not hide a later valid block.
                    offset = start + 1
                    continue
                offset = end
                block_type = block_id & 0x1FFF
                if block_type in block_types:
                    yield block_type, data[start:end]
