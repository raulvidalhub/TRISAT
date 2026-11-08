"""Optional offline OSNMAlib adapter for recorded Galileo I/NAV."""

import json
import shutil
from bisect import bisect_right
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

GPS_TO_GALILEO_WEEK = 1024


class VerificationTimeline:
    """Cumulative verified-tag counts indexed by their availability in playback."""

    def __init__(self, statuses, available_at):
        self._history = {}
        counts = {}
        self._failures = Counter()
        if len(statuses) != len(available_at):
            raise ValueError("statuses and available_at must have the same length")
        for status, index in zip(statuses, available_at):
            week, tow = status["metadata"]["GST_subframe"]
            affected = set()
            for tag in status["verified_OSNMA_material"]["tags"]:
                svid = tag["prn_d"]
                if not 1 <= svid <= 36:
                    continue
                if tag["verification"] is False:
                    self._failures[svid] += 1
                elif tag["verification"] is True:
                    counts.setdefault(svid, Counter())[tag["adkd"]] += 1
                    affected.add(svid)
            for svid in affected:
                self._history.setdefault(svid, []).append((index, {
                    "verified_tags": sum(counts[svid].values()),
                    "by_adkd": dict(counts[svid]),
                    "processed_subframe": {"galileo_week": week, "tow_s": tow},
                }))

    def at(self, index, svid):
        history = self._history.get(svid, [])
        indices = [entry[0] for entry in history]
        past = bisect_right(indices, index)
        if past:
            return history[past - 1][1]
        return {"verified_tags": 0, "by_adkd": {}, "processed_subframe": None}

    def totals(self):
        return {
            svid: history[-1][1]["verified_tags"]
            for svid, history in sorted(self._history.items())
        }

    def failures(self):
        return dict(sorted(self._failures.items()))


def verify_recording(pages, merkle_tree, public_key):
    """Verify recorded Septentrio SBF pages with OSNMAlib."""

    def timed_pages():
        from bitstring import BitArray

        for page in pages:
            if page["gps_week"] < GPS_TO_GALILEO_WEEK:
                raise ValueError("The SBF recording does not contain a full GPS week number.")
            bits = BitArray(hex=page["payload_hex"])[:234]
            # Septentrio omits the six even-page tail bits.
            bits.insert("0b000000", 114)
            yield (
                page["svid"], page["gps_week"] - GPS_TO_GALILEO_WEEK,
                page["tow_ms"] // 1000 - 2, bits, page["band"],
                page["navigation_crc_passed"],
            )

    return verify_timed_pages(timed_pages(), merkle_tree, public_key)


def verify_timed_pages(pages, merkle_tree, public_key):
    """Verify timed 240-bit I/NAV pages with caller-provisioned trust anchors."""
    try:
        from bitstring import BitArray
        from osnma.input_formats.base_classes import DataFormat, GAL_BAND
        from osnma.receiver.receiver import OSNMAReceiver
    except ImportError as exc:
        raise ValueError(f"OSNMAlib or a dependency is unavailable: {exc}") from exc

    class RecordedPages:
        provides_independent_clock = False

        def __iter__(self):
            for self.index, (svid, week, tow, payload, band, crc) in enumerate(pages):
                yield DataFormat(svid, week, tow, BitArray(payload), GAL_BAND(band), crc)

    feed = RecordedPages()
    available_at = []

    class PlaybackReceiver(OSNMAReceiver):
        def _do_status_log(self):
            super()._do_status_log()
            # OSNMAlib reports a subframe when the following page is consumed.
            # Index by that page so the viewer cannot reveal later results early.
            available_at.append(feed.index)

    with TemporaryDirectory(prefix="trisat-osnma-") as directory:
        root = Path(directory)
        shutil.copyfile(merkle_tree, root / "merkle.xml")
        shutil.copyfile(public_key, root / "public_key.xml")
        receiver = PlaybackReceiver(feed, {
            "exec_path": root,
            "merkle_name": "merkle.xml",
            "pubk_name": "public_key.xml",
            "log_console": False,
            "do_verbose_log": False,
        })
        if not receiver.receiver_state.pkr_dict:
            raise ValueError("OSNMAlib could not load the supplied public key.")
        receiver.start()

        status_path = next(root.glob("logs_*/status_log.json"), None)
        statuses = json.loads(status_path.read_text(encoding="utf-8")) if status_path else []
        if len(statuses) != len(available_at):
            raise ValueError("OSNMAlib did not produce a complete replay timeline.")
        return VerificationTimeline(statuses, available_at)
