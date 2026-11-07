"""Frame checksum-validated Septentrio SBF blocks from files or streams."""

import binascii
import struct

WEEK_MS = 604_800_000
_HEADER = struct.Struct("<HHH")


def gps_time_ms(sample):
    return sample["gps_week"] * WEEK_MS + sample["tow_ms"]


class SbfFramer:
    def __init__(self, block_types=None):
        self._buffer = bytearray()
        self._block_types = block_types

    def feed(self, chunk, *, final=False):
        """Yield complete blocks and hold a partial block until more bytes arrive."""
        data = self._buffer
        data.extend(chunk)
        offset = 0
        while (start := data.find(b"$@", offset)) != -1:
            if start + 8 > len(data):
                offset = start
                break
            crc, block_id, length = _HEADER.unpack_from(data, start + 2)
            end = start + length
            if length >= 8 and not length % 4:
                if end > len(data) and not final:
                    offset = start
                    break
                if end <= len(data) and binascii.crc_hqx(data[start + 4 : end], 0) == crc:
                    offset = end
                    kind = block_id & 0x1FFF
                    if self._block_types is None or kind in self._block_types:
                        yield kind, bytes(data[start:end])
                    continue
            # A damaged length must not hide a later valid block.
            offset = start + 1
        else:
            # The next chunk can finish the two-byte synchronization marker.
            offset = len(data) - int(offset < len(data) and data.endswith(b"$"))
        if final:
            data.clear()
        else:
            del data[:offset]


def read_blocks(path, block_types):
    """Yield requested SBF blocks in file order, recovering after corruption."""
    framer = SbfFramer(block_types)
    with path.open("rb") as stream:
        while chunk := stream.read(65_536):
            yield from framer.feed(chunk)
        yield from framer.feed(b"", final=True)
