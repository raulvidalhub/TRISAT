import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from trisat_hw.zed_f9p import f9p_bridge
from trisat_hw.zed_f9p.f9p_stream import F9pStream, build_ubx_msg


MON_VER_POLL = bytes.fromhex("B5 62 0A 04 00 00 0E 34")
NMEA = b"$GNTXT,01,01,02,Test*65\r\n"


class TestF9pStream(unittest.TestCase):
    def test_handles_all_read_boundaries_in_mixed_stream(self):
        # Delimiters inside a valid UBX payload belong to that packet.
        ubx = build_ubx_msg(0x02, 0x15, MON_VER_POLL + bytes(range(256)))
        traffic = b"noise\xb5" + NMEA + ubx + MON_VER_POLL
        for split in range(len(traffic) + 1):
            with self.subTest(split=split):
                stream = F9pStream()
                first = list(stream.feed(traffic[:split]))
                second = list(stream.feed(traffic[split:]))
                self.assertEqual(first + second, [NMEA, ubx, MON_VER_POLL])

    def test_recovers_after_checksum_error_and_bad_nmea(self):
        bad_checksum = MON_VER_POLL[:-1] + b"\x00"
        traffic = bad_checksum + b"$GNTXT,truncated" + MON_VER_POLL + b"$\xff\n" + NMEA
        self.assertEqual(list(F9pStream().feed(traffic)), [MON_VER_POLL, NMEA])

    def test_recovers_when_bad_length_overlaps_next_packet(self):
        bad_length = MON_VER_POLL[:4] + b"\x04\x00" + MON_VER_POLL[6:]
        self.assertEqual(list(F9pStream().feed(bad_length + MON_VER_POLL)), [MON_VER_POLL])

    def test_recovers_incomplete_frame_after_serial_timeout(self):
        stream = F9pStream()
        bad_length = MON_VER_POLL[:4] + b"\xff\xff"
        self.assertEqual(list(stream.feed(bad_length + MON_VER_POLL + NMEA)), [])
        self.assertEqual(list(stream.feed(b"")), [MON_VER_POLL, NMEA])

    def test_bounds_incomplete_nmea(self):
        stream = F9pStream()
        self.assertEqual(list(stream.feed(b"$" + b"A" * 2048 + MON_VER_POLL[:1])), [])
        self.assertEqual(list(stream.feed(MON_VER_POLL[1:])), [MON_VER_POLL])


class TestF9pBridge(unittest.TestCase):
    def test_forwards_only_complete_frames_and_configures_the_current_port(self):
        ubx = build_ubx_msg(0x02, 0x13, b"\x00\n\xff")
        bad_checksum = MON_VER_POLL[:-1] + b"\x00"
        bad_length = MON_VER_POLL[:4] + b"\xff\xff"
        serial_port = Mock(in_waiting=4096)
        serial_port.read.side_effect = [
            NMEA[:6], NMEA[6:] + ubx[:7], ubx[7:] + bad_checksum,
            bad_length + MON_VER_POLL, b"", KeyboardInterrupt,
        ]
        serial = SimpleNamespace(Serial=Mock(return_value=serial_port))
        udp = Mock()
        with (
            patch.dict(sys.modules, {"serial": serial}),
            patch.object(f9p_bridge, "find_f9p_port", return_value="/dev/cu.usbmodem-test"),
            patch.object(f9p_bridge.socket, "socket", return_value=udp),
            patch("builtins.print"),
        ):
            f9p_bridge.main()

        commands = [write.args[0] for write in serial_port.write.call_args_list]
        self.assertEqual(commands[0], MON_VER_POLL)
        self.assertEqual(commands[-1], bytes.fromhex("B5 62 06 01 03 00 02 13 01 20 6C"))
        self.assertEqual(list(F9pStream().feed(b"".join(commands))), commands)
        self.assertEqual(udp.sendto.call_args_list, [
            call(payload, (host, 9090))
            for payload in (NMEA.replace(b"\r\n", b"\n"), b"RAW:" + ubx, b"RAW:" + MON_VER_POLL)
            for host in ("127.0.0.1", "255.255.255.255")
        ])
        serial_port.close.assert_called_once_with()
        udp.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
