import os
import unittest
from pathlib import Path

from trisat_sdr.osnma_replay import verify_recording
from trisat_sdr.replay_sbf import read_pages


@unittest.skipUnless(os.environ.get("TRISAT_OSNMA_EXAMPLE"), "OSNMAlib example directory is required")
class TestPublicOsnmaReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example = Path(os.environ["TRISAT_OSNMA_EXAMPLE"])
        cls.pages = list(read_pages(cls.example / "current_config.sbf"))

    def verify(self, pages):
        return verify_recording(
            pages,
            self.example / "OSNMA_MerkleTree.xml",
            self.example / "OSNMA_PublicKey_2.xml",
        ).totals()

    def test_verifies_recorded_navigation(self):
        self.assertEqual(len(self.pages), 50_277)
        self.assertEqual(self.verify(self.pages), {
            4: 467, 6: 260, 13: 243, 15: 538, 18: 70, 19: 445,
            21: 522, 23: 415, 27: 418, 29: 372, 30: 543, 34: 418,
        })

    def test_without_osnma_bits_verifies_no_tags(self):
        from bitstring import BitArray

        # SBF omits six even-page tail bits before the 40-bit OSNMA field.
        control = []
        for page in self.pages:
            if page["band"] == "E1-B":
                bits = BitArray(hex=page["payload_hex"])
                bits[132:172] = BitArray(length=40)
                page = {**page, "payload_hex": bits.hex}
            control.append(page)

        self.assertEqual(self.verify(control), {})
