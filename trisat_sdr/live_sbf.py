"""Show a live Septentrio USB stream in the TRISAT dashboard and record it."""

import argparse
from pathlib import Path
from threading import Lock
from time import monotonic

from .sbf import SbfFramer, gps_time_ms
from .sbf_measurements import MEAS_EPOCH
from .sbf_receiver import MAX_SAMPLE_AGE_MS, PVT_GEODETIC, receiver_sample
from .ui.web_dashboard import TrisatWebDashboardServer

LIVE_FIELDS = {PVT_GEODETIC: "receiver_position", MEAS_EPOCH: "galileo_signal_quality"}


class LiveReceiver:
    def __init__(self):
        self._samples = {}
        self._lock = Lock()

    def accept(self, kind, block):
        field = LIVE_FIELDS.get(kind)
        if field is None:
            return
        sample = receiver_sample(kind, block)
        if sample is None:
            return
        with self._lock:
            previous = self._samples.get(field)
            if previous is None or gps_time_ms(sample) > gps_time_ms(previous[0]):
                self._samples[field] = (sample, monotonic())

    def get_status_snapshot(self):
        with self._lock:
            samples = self._samples.copy()
        now = monotonic()
        snapshot = {"source": "septentrio_live", "stream_state": "stale" if samples else "waiting"}
        for field in LIVE_FIELDS.values():
            snapshot[field] = None
            if field in samples:
                sample, received = samples[field]
                age_ms = int((now - received) * 1000)
                if age_ms <= MAX_SAMPLE_AGE_MS:
                    snapshot[field] = {**sample, "age_ms": age_ms}
                    snapshot["stream_state"] = "receiving"
        return snapshot


def capture_session(serial_port, recording, receiver, seconds=None):
    framer = SbfFramer()
    deadline = None if seconds is None else monotonic() + seconds
    while True:
        finished = deadline is not None and monotonic() >= deadline
        chunk = b"" if finished else serial_port.read(min(serial_port.in_waiting, 32_768) or 1)
        # A serial read can time out in the middle of a block.
        for kind, block in framer.feed(chunk, final=finished):
            recording.write(block)
            receiver.accept(kind, block)
        if finished:
            return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="USB serial port, for example COM9")
    parser.add_argument("--capture", required=True, type=Path, help="New local .sbf capture file")
    parser.add_argument("--port", type=int, default=8085, help="Local dashboard port (default: 8085)")
    parser.add_argument("--seconds", type=int, help="Stop recording after this many seconds")
    args = parser.parse_args()
    if args.seconds is not None and args.seconds <= 0:
        parser.error("--seconds must be positive.")
    try:
        import serial
    except ImportError:
        parser.error("Install pyserial to read the USB port: python -m pip install pyserial")

    receiver = LiveReceiver()
    dashboard = TrisatWebDashboardServer(receiver, port=args.port, live_sbf=True)
    try:
        with serial.Serial(args.serial, 115200, timeout=0.5) as port, args.capture.open("xb") as recording:
            url = dashboard.start()
            try:
                print(f"Mosaic-H live dashboard: {url}", flush=True)
                capture_session(port, recording, receiver, args.seconds)
            finally:
                dashboard.stop()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
