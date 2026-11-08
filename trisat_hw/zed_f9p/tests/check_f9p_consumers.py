"""Cross-check the Apple and ESP32 production parsers against the PR #10 fixtures."""

import subprocess
import sys
import unittest

from trisat_hw.zed_f9p.f9p_stream import build_ubx_msg
from trisat_hw.zed_f9p.tests.test_galileo_inav import E1B_PAGES, E5B_PAGE, sfrbx

SWIFT, CPP = sys.argv[1:]
sys.argv = sys.argv[:1]


def exchange(program, lines):
    result = subprocess.run(
        [program], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True,
    )
    return result.stdout.splitlines()


def ubx(payload):
    return build_ubx_msg(2, 0x13, payload)


def sentence(body):
    checksum = 0
    for byte in body[1:].encode("ascii"):
        checksum ^= byte
    return f"{body}*{checksum:02X}"


class TestF9pConsumers(unittest.TestCase):
    def test_published_pages_on_usb_and_esp32(self):
        frames, expected_sentences, expected_pages = [], [], []
        for (wt, even, odd), signal, band in (
            *((page, 1, "E1-B") for page in E1B_PAGES),
            (E5B_PAGE, 5, "E5b-I"),
        ):
            frames.append(ubx(sfrbx(even, odd, signal=signal)))
            expected_sentences.append(sentence(f"$GALINAV,2,{wt},{even + odd},{band}"))
            expected_pages.append(f"2|{wt}|{even + odd}|{band}")
        esp32_sentences = exchange(CPP, [frame.hex() for frame in frames])
        self.assertEqual(esp32_sentences, expected_sentences)
        self.assertEqual(exchange(SWIFT, ["raw " + (b"RAW:" + f).hex() for f in frames]), expected_pages)
        self.assertEqual(exchange(SWIFT, esp32_sentences), expected_pages)

    def test_invalid_binary_packets(self):
        _, even, odd = E1B_PAGES[0]
        payload = sfrbx(even, odd)
        good = ubx(payload)
        corrupted_ubx = good[:-1] + bytes([good[-1] ^ 1])
        # Alter the I/NAV data, but give the modified packet a valid UBX checksum.
        corrupted_crc = ubx(payload[:10] + bytes([payload[10] ^ 0x20]) + payload[11:])
        invalid = [
            corrupted_ubx, corrupted_crc, ubx(payload[:-1]), ubx(sfrbx(odd, even)),
            ubx(sfrbx("4" + even[1:], odd)), ubx(sfrbx(even, odd, signal=3)),
            ubx(payload[:1] + bytes([0]) + payload[2:]),
            ubx(payload[:4] + bytes([7]) + payload[5:]),
            ubx(payload[:6] + bytes([1]) + payload[7:]),
            build_ubx_msg(1, 0x13, payload),
        ]
        self.assertEqual(exchange(CPP, [f.hex() for f in invalid]), ["-"] * len(invalid))
        self.assertEqual(
            exchange(SWIFT, ["raw " + (b"RAW:" + f).hex() for f in [*invalid, good[:-1], good + b"\n"]]),
            ["-"] * (len(invalid) + 2),
        )
        expected = sentence(f"$GALINAV,2,2,{even + odd},E1-B")
        self.assertEqual(
            exchange(CPP, [corrupted_ubx.hex(), good[:20].hex(), good[20:].hex()]),
            ["-", "-", expected],
        )

    def test_mixed_serial_stream_and_fragmentation(self):
        wt, even, odd = E1B_PAGES[0]
        frame = ubx(sfrbx(even, odd))
        bad = frame[:-1] + bytes([frame[-1] ^ 1])
        nmea = sentence("$GNGGA,103001.00,4025.0065,N,00342.2274,W,0,0,,,,,,,")
        esp = sentence(f"$GALINAV,2,{wt},{even + odd},E1-B")
        expected = f"2|{wt}|{even + odd}|E1-B"
        fragments = [
            b"[ESP32 diagnostic]\n" + frame[:1],
            frame[1:19],
            frame[19:] + bad + (nmea + "\r\n").encode(),
            esp[:20].encode(),
            (esp[20:] + "\n").encode(),
        ]
        self.assertEqual(
            exchange(SWIFT, ["serial " + f.hex() for f in fragments]),
            ["-", "-", expected + ";" + nmea, "-", expected + ";" + esp],
        )

    def test_ssp_is_outside_the_page_crc(self):
        wt, even, odd = E1B_PAGES[0]
        payload = bytearray(sfrbx(even, odd))
        payload[38] ^= 0x20
        frame = ubx(payload)
        modified_odd = odd[:26] + f"{int(odd[26:28], 16) ^ 0x20:02X}" + odd[28:]
        result = exchange(CPP, [frame.hex()])
        self.assertEqual(result, [sentence(f"$GALINAV,2,{wt},{even + modified_odd},E1-B")])
        expected = f"2|{wt}|{even + modified_odd}|E1-B"
        self.assertEqual(exchange(SWIFT, ["raw " + (b"RAW:" + frame).hex(), *result]), [expected] * 2)

    def test_invalid_galinav_sentences_and_legacy_input(self):
        wt, even, odd = E1B_PAGES[0]
        data = even + odd
        valid = sentence(f"$GALINAV,2,{wt},{data},E1-B")
        corrupted_text = valid[:-2] + f"{int(valid[-2:], 16) ^ 1:02X}"
        invalid = [
            corrupted_text, valid.split("*")[0],
            sentence(f"$GALINAV,2,63,{data},E1-B"),
            sentence(f"$GALINAV,2,{wt},{data},E5a-I"),
            sentence(f"$GALINAV,2,{wt},{data[:-2]},E1-B"),
            sentence(f"$GALINAV,2,{wt},{data[:4]}00{data[6:]},E1-B"),
        ]
        legacy = "$GALINAV,2,2,0123,827BB238C8*3F"
        self.assertEqual(exchange(SWIFT, [*invalid, legacy]), ["-"] * len(invalid) + ["2|2|0123|E1-B"])

    def test_gga_fix_quality_and_checksum(self):
        body = "$GNGGA,103001.00,4025.0065,N,00342.2274,W,{},18,0.68,667.0,M,48.0,M,,"
        rtk = sentence(body.format(4))
        bad_checksum = rtk[:-2] + f"{int(rtk[-2:], 16) ^ 1:02X}"
        self.assertEqual(
            exchange(SWIFT, ["gga " + s for s in (rtk, sentence(body.format(0)), sentence(body.format(6)), bad_checksum)]),
            ["measured", "no fix", "no fix", "-"],
        )


if __name__ == "__main__":
    unittest.main()
