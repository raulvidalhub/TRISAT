"""Frame mixed NMEA and UBX traffic from the ZED-F9P serial port."""

import re

UBX_SYNC = b"\xb5\x62"
MESSAGE_START = re.compile(rb"\$|\xb5\x62")
MAX_NMEA_LENGTH = 1024


def calculate_checksum(message):
    """Calculate CK_A and CK_B over the class, ID, length, and payload."""
    ck_a = ck_b = 0
    for byte in message[2:]:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return bytes((ck_a, ck_b))


def build_ubx_msg(msg_class, msg_id, payload=b""):
    header = UBX_SYNC + bytes((msg_class, msg_id)) + len(payload).to_bytes(2, "little")
    message = header + payload
    return message + calculate_checksum(message)


class F9pStream:
    def __init__(self):
        self._buffer = bytearray()

    def feed(self, chunk):
        """Yield complete frames in order. An empty read signals a serial timeout."""
        self._buffer.extend(chunk)
        buffer = self._buffer
        while buffer:
            start = MESSAGE_START.search(buffer)
            if start is None:
                if chunk and buffer[-1] == UBX_SYNC[0]:
                    del buffer[:-1]
                else:
                    buffer.clear()
                return
            del buffer[:start.start()]

            if buffer.startswith(UBX_SYNC):
                if len(buffer) >= 6:
                    length = int.from_bytes(buffer[4:6], "little") + 8
                    if len(buffer) >= length:
                        frame = bytes(buffer[:length])
                        if calculate_checksum(frame[:-2]) == frame[-2:]:
                            del buffer[:length]
                            yield frame
                        else:
                            # A damaged length may overlap the next frame.
                            del buffer[:1]
                        continue
            else:
                end = buffer.find(b"\n") + 1
                following = MESSAGE_START.search(buffer, 1)
                if following is not None and (not end or following.start() < end):
                    del buffer[:following.start()]
                    continue
                if end:
                    frame = bytes(buffer[:end])
                    del buffer[:end]
                    sentence = frame.rstrip(b"\r\n")
                    if end <= MAX_NMEA_LENGTH and all(32 <= byte <= 126 for byte in sentence):
                        yield frame
                    continue
                if len(buffer) >= MAX_NMEA_LENGTH:
                    del buffer[:1]
                    continue

            if chunk:
                return
            # The link went idle. Search past the incomplete frame for any
            # complete messages it may have hidden.
            del buffer[:1]
