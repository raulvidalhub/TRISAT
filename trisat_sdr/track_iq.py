"""Measure Galileo E1-B tracking intervals in a local raw IQ recording."""

from __future__ import annotations

import argparse
import csv
import math
from collections import deque
from dataclasses import asdict, dataclass

from .config import ReceiverConfig, SdrChannelConfig
from .drivers.sdr_driver import IQ_FILE_FORMATS, SdrStreamSource
from .dsp.acquisition import PcpsAcquisitionEngine
from .dsp.codes import HAS_NUMPY, np
from .dsp.e1b_tracking import E1bFileTracker, E1bTrackInterval


@dataclass
class TrackSummary:
    first_lock: int | None = None
    last_lock: int | None = None
    locked_samples: int = 0
    longest_lock: int = 0
    losses: int = 0
    _run_samples: int = 0

    def add(self, interval):
        if interval.locked:
            if self.first_lock is None:
                self.first_lock = interval.start_sample
            self.last_lock = interval.end_sample
            duration = interval.end_sample - interval.start_sample
            self.locked_samples += duration
            self._run_samples += duration
            self.longest_lock = max(self.longest_lock, self._run_samples)
        elif self._run_samples:
            self.losses += 1
            self._run_samples = 0


def track_capture(config, acquisition_offsets, doppler_max_hz, on_interval=None):
    """Read the file once, seed new channels from PCPS, and follow each to EOF."""
    if not HAS_NUMPY:
        raise RuntimeError("E1-B IQ tracking requires NumPy.")
    if config.driver != "file" or config.band_id != "GAL_E1":
        raise ValueError("E1-B IQ tracking requires a Galileo E1 file source.")
    source = SdrStreamSource(config)
    engine = PcpsAcquisitionEngine(config.sample_rate_hz, doppler_max_hz)
    pending = deque(sorted(set(acquisition_offsets)))
    trackers = {}
    summaries = {}
    offset = 0
    iq = np.empty(0, dtype=np.complex64)
    while True:
        chunk = source.read_iq_samples(engine.e1b_window_samples * 16)
        iq = np.concatenate((iq, np.asarray(chunk, dtype=np.complex64)))
        end = offset + len(iq)
        while pending and pending[0] + engine.e1b_window_samples <= end:
            start = pending.popleft()
            window = iq[start - offset:start - offset + engine.e1b_window_samples]
            for acquired in engine.acquire_galileo_e1b(window):
                if acquired.acquired and acquired.svid not in trackers:
                    trackers[acquired.svid] = E1bFileTracker(
                        acquired, config.sample_rate_hz, start, engine.doppler_step_hz
                    )
                    summaries[acquired.svid] = TrackSummary()
        for svid, tracker in trackers.items():
            while interval := tracker.step(iq, offset, eof=not chunk):
                summaries[svid].add(interval)
                if on_interval is not None:
                    on_interval(interval)
        if not chunk:
            if pending:
                raise ValueError("An acquisition offset has fewer than 8 ms of IQ before EOF.")
            return end, summaries
        keep = min([end, *pending, *(tracker.keep_from for tracker in trackers.values())])
        iq = iq[keep - offset:]
        offset = keep


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Local Galileo E1 IQ recording")
    parser.add_argument("--sample-rate-hz", type=float, default=4_000_000)
    parser.add_argument("--iq-format", choices=IQ_FILE_FORMATS, default="int16")
    parser.add_argument("--doppler-max-hz", type=float, default=ReceiverConfig.doppler_search_max_hz)
    parser.add_argument("--acquire-at", action="append", type=float, metavar="SECONDS",
                        help="Seed new channels at this file time. Repeat to add more times (default: 0).")
    parser.add_argument("--csv", help="Write measured per-channel intervals to a new CSV file")
    args = parser.parse_args()
    times = args.acquire_at if args.acquire_at is not None else [0.0]
    if not math.isfinite(args.sample_rate_hz) or args.sample_rate_hz < 1000:
        parser.error("--sample-rate-hz must be finite and at least 1000 Hz")
    if not 0 <= args.doppler_max_hz < args.sample_rate_hz / 2:
        parser.error("--doppler-max-hz must be nonnegative and below half the sample rate")
    if any(not math.isfinite(t) or t < 0 for t in times):
        parser.error("--acquire-at times must be finite and nonnegative")
    config = SdrChannelConfig(driver="file", sample_rate_hz=args.sample_rate_hz,
                              iq_file_path=args.file, iq_format=args.iq_format)
    offsets = [round(t * args.sample_rate_hz) for t in times]
    try:
        if args.csv:
            with open(args.csv, "x", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(E1bTrackInterval.__dataclass_fields__))
                writer.writeheader()
                count, summaries = track_capture(config, offsets, args.doppler_max_hz,
                                                 lambda interval: writer.writerow(asdict(interval)))
        else:
            count, summaries = track_capture(config, offsets, args.doppler_max_hz)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"{error}\n")

    rate = args.sample_rate_hz
    print(f"Read {count} IQ samples ({count / rate:.3f} s) to EOF.")
    print("PRN   first lock   last lock   longest lock   total lock   losses")
    for svid, result in sorted(summaries.items()):
        first = "--" if result.first_lock is None else f"{result.first_lock / rate:.3f} s"
        last = "--" if result.last_lock is None else f"{result.last_lock / rate:.3f} s"
        print(f"E{svid:02d}  {first:>10}  {last:>10}  {result.longest_lock / rate:10.3f} s  "
              f"{result.locked_samples / rate:8.3f} s  {result.losses:6}")


if __name__ == "__main__":
    main()
