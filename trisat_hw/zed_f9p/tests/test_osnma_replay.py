"""Replay GSC Annex B vectors through the actual F9P packet decoder."""

import csv
import io
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path
from struct import pack, unpack
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from trisat_hw.zed_f9p.f9p_stream import build_ubx_msg
from trisat_hw.zed_f9p.osnma_replay import timed_inav

ANNEX_B = os.environ.get("TRISAT_OSNMA_ANNEX_B")
GALILEO_EPOCH = datetime(1999, 8, 22)
CONFIGURATIONS = {
    1: ("16_AUG_2023_GST_05_00_01", datetime(2023, 8, 16, 5, 0, 1), "20230803105953"),
    2: ("27_JUL_2023_GST_00_00_01", datetime(2023, 7, 27, 0, 0, 1), "20230720113300"),
}


def sfrbx(svid, page):
    padded = page[:15] + b"\x00" + page[15:] + b"\x00"
    payload = bytes((2, svid, 1, 0, 8, 0, 2, 0)) + pack("<8I", *unpack(">8I", padded))
    return build_ubx_msg(2, 0x13, payload)


def fix_crc(bits):
    # Independent polynomial division over the 196 ICD-protected bits.
    dividend = int(bits[:114] + bits[120:202] + "0" * 24, 2)
    while dividend.bit_length() > 24:
        dividend ^= 0x1864CFB << (dividend.bit_length() - 25)
    return bits[:202] + f"{dividend:024b}" + bits[226:]


def alter_page(page, control):
    bits = f"{int.from_bytes(page, 'big'):0240b}"
    if control == "no_osnma":
        bits = bits[:138] + "0" * 40 + bits[178:]
    elif control == "navigation" and page[0] & 0x3F in (1, 2, 3, 4):
        # Alter a navigation data bit without changing the word type or IODnav.
        bits = bits[:24] + str(1 - int(bits[24])) + bits[25:]
    else:
        return page
    return int(fix_crc(bits), 2).to_bytes(30, "big")


class TestTimedInav(unittest.TestCase):
    def test_rejects_missing_invalid_or_unordered_time(self):
        for record in ({}, {"galileo_week": True, "tow_s": 1, "ubx_hex": ""},
                       {"galileo_week": 1234, "tow_s": 2, "ubx_hex": ""},
                       {"galileo_week": 1234, "tow_s": 604801, "ubx_hex": ""}):
            with self.subTest(record=record), self.assertRaises(ValueError):
                list(timed_inav([json.dumps(record)]))

        records = [json.dumps({"galileo_week": 1234, "tow_s": tow, "ubx_hex": ""})
                   for tow in (3, 1)]
        with self.assertRaisesRegex(ValueError, "out of order"):
            list(timed_inav(records))

    def test_transport_and_page_crc_are_both_required(self):
        bits = fix_crc("0" * 120 + "10" + "0" * 118)
        page = int(bits, 2).to_bytes(30, "big")
        clean = sfrbx(4, page)
        bad_ubx = clean[:-1] + bytes([clean[-1] ^ 1])
        bad_page = sfrbx(4, page[:3] + bytes([page[3] ^ 1]) + page[4:])
        records = [json.dumps({"galileo_week": 1234, "tow_s": 1, "ubx_hex": frame.hex()})
                   for frame in (bad_ubx, bad_page, clean, clean)]
        self.assertEqual(list(timed_inav(records)), [(4, 1234, 1, page, "E1-B", True)])


@unittest.skipUnless(ANNEX_B, "set TRISAT_OSNMA_ANNEX_B to the official Annex B ZIP")
class TestOfficialOsnmaReplay(unittest.TestCase):
    def replay(self, configuration, control=None):
        name, start, key_date = CONFIGURATIONS[configuration]
        start_seconds = int((start - GALILEO_EPOCH).total_seconds())
        with TemporaryDirectory() as directory, ZipFile(ANNEX_B) as archive:
            root = Path(directory)
            prefix = f"Test_vectors/cryptographic_material/Merkle_tree_{configuration}"
            tree = root / "merkle.xml"
            key = root / "public.xml"
            tree.write_bytes(archive.read(f"{prefix}/MerkleTree/OSNMA_MerkleTree_{key_date}_newPKID_{configuration}.xml"))
            key.write_bytes(archive.read(f"{prefix}/PublicKey/OSNMA_PublicKey_{key_date}_newPKID_{configuration}.xml"))
            member = f"Test_vectors/osnma_test_vectors/configuration_{configuration}/{name}.csv"
            with io.TextIOWrapper(archive.open(member), encoding="utf-8") as source:
                satellites = {}
                for row in csv.DictReader(source):
                    nav = bytes.fromhex(row["NavBitsHEX"])
                    self.assertEqual(int(row["NumNavBits"]), len(nav) * 8)
                    satellites[int(row["SVID"])] = nav

            capture = root / "capture.jsonl"
            with capture.open("w", encoding="utf-8") as output:
                for offset in range(0, max(map(len, satellites.values())), 30):
                    week, tow = divmod(start_seconds + (offset // 30) * 2, 604_800)
                    for svid, nav in satellites.items():
                        page = nav[offset:offset + 30]
                        if page:
                            frame = sfrbx(svid, alter_page(page, control))
                            output.write(json.dumps({
                                "galileo_week": week, "tow_s": tow, "ubx_hex": frame.hex(),
                            }) + "\n")

            result = subprocess.run(
                [sys.executable, "-m", "trisat_hw.zed_f9p.osnma_replay", str(capture),
                 "--merkle-tree", str(tree), "--public-key", str(key)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_configuration_1_and_2(self):
        for configuration, expected in ((1, 12_418), (2, 11_325)):
            with self.subTest(configuration=configuration):
                result = self.replay(configuration)
                self.assertEqual(sum(result["verified_tags_by_svid"].values()), expected, result)
                self.assertEqual(result["failed_tags_by_svid"], {})

    def test_erased_osnma_bits_do_not_authenticate(self):
        result = self.replay(1, "no_osnma")
        self.assertEqual(result["verified_tags_by_svid"], {})
        self.assertEqual(result["failed_tags_by_svid"], {})

    def test_modified_navigation_fails_tags_with_valid_crcs(self):
        result = self.replay(1, "navigation")
        self.assertEqual(sum(result["failed_tags_by_svid"].values()), 11_364)
        self.assertEqual(sum(result["verified_tags_by_svid"].values()), 1_054)


if __name__ == "__main__":
    unittest.main()
