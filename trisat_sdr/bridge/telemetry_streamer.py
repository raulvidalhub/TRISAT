"""
Telemetry Streamer Bridge for TRISAT-SDR.
Broadcasts live demodulated GNSS frames and PVT solutions to:
  1. UDP Unicast/Broadcast (default 127.0.0.1:5005)
  2. TCP Multi-Client Server (default 0.0.0.0:5006)

An optional POSIX PTY device can be allocated on macOS or Linux. Serial output
is currently unavailable.

Emits:
  - Standard NMEA 0183: $GNGGA, $GPGGA, $GAGSV, $GPGSV
  - TRISAT Raw Navigation Sentences:
      $GALINAV,<svid>,<wordType>,<hex30Bytes>,<osnma40BitHex>*CS
      $GALE6HAS,<svid>,<pageId>,<orbitCorrCm>,<hexPayload>*CS
      $GALE5,<band>,<svid>,<pageType>,<hexPayload>*CS
  - TRISAT JSON GATT-compatible objects (matching TrisatBleServer.kt & BluetoothManager.swift)
"""

from dataclasses import asdict, dataclass
import json
import math
import os
import socket
import threading
import time
from typing import List, Optional

from ..config import TelemetryBridgeConfig
from ..nav.frame_decoder import DecodedGnssFrame
from ..nav.pvt_solver import PvtSolution, SatelliteSkyPosition


def _nmea_checksum(body: str) -> str:
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return f"{cs:02X}"


def _decimal_to_nmea_coord(deg_val: float, is_lat: bool = True) -> tuple:
    hemi = ("N" if deg_val >= 0 else "S") if is_lat else ("E" if deg_val >= 0 else "W")
    abs_val = abs(deg_val)
    degrees = int(math.floor(abs_val))
    minutes = (abs_val - degrees) * 60.0
    if is_lat:
        return f"{degrees:02d}{minutes:07.4f}", hemi
    else:
        return f"{degrees:03d}{minutes:07.4f}", hemi


def format_gngga_sentence(pvt: PvtSolution) -> str:
    """Formats a standard NMEA 0183 $GNGGA sentence from a PvtSolution."""
    utc_str = time.strftime("%H%M%S.00", time.gmtime())
    lat_str, lat_dir = _decimal_to_nmea_coord(pvt.latitude_deg, is_lat=True)
    lon_str, lon_dir = _decimal_to_nmea_coord(pvt.longitude_deg, is_lat=False)
    # PVT is simulated. Legacy NMEA must not report a real fix.
    fix_qual = 0
    body = (
        f"GNGGA,{utc_str},{lat_str},{lat_dir},{lon_str},{lon_dir},"
        f"{fix_qual},{pvt.num_sats_used:02d},{pvt.hdop:.1f},{pvt.altitude_m:.1f},M,48.0,M,,"
    )
    return f"${body}*{_nmea_checksum(body)}"


def format_gsv_sentences(satellites: List[SatelliteSkyPosition]) -> List[str]:
    """Formats $GAGSV (Galileo) and $GPGSV (GPS) NMEA 0183 sentences."""
    sentences: List[str] = []
    for talker, const_name in (("GA", "GALILEO"), ("GP", "GPS")):
        sats = [s for s in satellites if s.constellation == const_name]
        if not sats:
            continue
        total_msgs = math.ceil(len(sats) / 4.0)
        for msg_idx in range(total_msgs):
            chunk = sats[msg_idx * 4 : (msg_idx + 1) * 4]
            fields = [f"{talker}GSV", str(total_msgs), str(msg_idx + 1), f"{len(sats):02d}"]
            for s in chunk:
                fields.extend([
                    f"{s.svid:02d}",
                    f"{int(round(s.elevation_deg)):02d}",
                    f"{int(round(s.azimuth_deg)):03d}",
                    f"{int(round(s.cn0_dbhz)):02d}",
                ])
            body = ",".join(fields)
            sentences.append(f"${body}*{_nmea_checksum(body)}")
    return sentences


@dataclass
class _TransportCounters:
    attempts: int = 0
    packets_sent: int = 0
    bytes_sent: int = 0


class TelemetryStreamer:
    """
    Streams NMEA 0183, $GALINAV, $GALE6HAS, and TRISAT JSON packets over UDP and TCP.
    """

    def __init__(self, config: TelemetryBridgeConfig):
        self.config = config
        self._udp_sock: Optional[socket.socket] = None
        self._tcp_server: Optional[socket.socket] = None
        self._tcp_clients: List[socket.socket] = []
        self._tcp_lock = threading.Lock()
        self._running = False

        # POSIX Virtual Serial Port (PTY) on macOS / Linux
        self.pty_master_fd: Optional[int] = None
        self.pty_slave_path: Optional[str] = None

        self._stats_lock = threading.Lock()
        self._messages_generated = 0
        self._bytes_generated = 0
        self._transport_counters = {"udp": _TransportCounters(), "tcp": _TransportCounters()}
        self.recent_nmea_log: List[str] = []

    def start(self) -> None:
        self._running = True

        # 1. Initialize UDP Socket
        if self.config.udp_enabled:
            try:
                self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            except Exception:
                self._udp_sock = None

        # 2. Initialize TCP Server
        if self.config.tcp_enabled:
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind((self.config.tcp_bind_host, self.config.tcp_port))
                srv.listen(8)
                srv.settimeout(1.0)
                self._tcp_server = srv
                threading.Thread(target=self._accept_tcp_loop, daemon=True).start()
            except Exception:
                self._tcp_server = None

        # 3. Initialize POSIX PTY Virtual Serial Port on macOS / Linux
        if self.config.pty_serial_enabled and hasattr(os, "openpty"):
            try:
                master_fd, slave_fd = os.openpty()
                self.pty_master_fd = master_fd
                self.pty_slave_path = os.ttyname(slave_fd)
            except Exception:
                self.pty_master_fd = None
                self.pty_slave_path = None

    def stop(self) -> None:
        self._running = False
        udp_sock = self._udp_sock
        self._udp_sock = None
        if udp_sock:
            try:
                udp_sock.close()
            except Exception:
                pass
        if self._tcp_server:
            try:
                self._tcp_server.close()
            except Exception:
                pass
        with self._tcp_lock:
            for c in self._tcp_clients:
                try:
                    c.close()
                except Exception:
                    pass
            self._tcp_clients.clear()
        if self.pty_master_fd is not None:
            try:
                os.close(self.pty_master_fd)
            except Exception:
                pass
            self.pty_master_fd = None

    def _accept_tcp_loop(self) -> None:
        while self._running and self._tcp_server:
            try:
                client, _ = self._tcp_server.accept()
                client.setblocking(False)
                with self._tcp_lock:
                    self._tcp_clients.append(client)
            except socket.timeout:
                continue
            except Exception:
                break

    def _broadcast_line(self, line: str) -> None:
        text = line.strip()
        payload = (text + "\r\n").encode("utf-8")
        payload_size = len(payload)
        with self._stats_lock:
            self._messages_generated += 1
            self._bytes_generated += payload_size
            if line.startswith("$"):
                self.recent_nmea_log.append(text)
                if len(self.recent_nmea_log) > 80:
                    self.recent_nmea_log.pop(0)

        # Send over UDP (both configured port e.g. 5005 and TRISAT macOS/iOS bridge port 9090)
        udp_sock = self._udp_sock
        if udp_sock and self.config.udp_enabled:
            target_ports = {self.config.udp_port, 9090}
            for port in target_ports:
                try:
                    written = udp_sock.sendto(payload, (self.config.udp_host, port))
                except Exception:
                    written = 0
                self._record_attempt("udp", written if written == payload_size else 0)

        # Send to connected TCP clients
        if self.config.tcp_enabled:
            dead: List[socket.socket] = []
            with self._tcp_lock:
                for client in self._tcp_clients:
                    try:
                        client.sendall(payload)
                    except Exception:
                        self._record_attempt("tcp", 0)
                        dead.append(client)
                    else:
                        self._record_attempt("tcp", payload_size)
                for d in dead:
                    self._tcp_clients.remove(d)

    def _record_attempt(self, transport: str, bytes_sent: int) -> None:
        with self._stats_lock:
            counters = self._transport_counters[transport]
            counters.attempts += 1
            if bytes_sent:
                counters.packets_sent += 1
                counters.bytes_sent += bytes_sent

    @property
    def packets_sent(self) -> int:
        with self._stats_lock:
            return sum(counters.packets_sent for counters in self._transport_counters.values())

    @property
    def bytes_sent(self) -> int:
        with self._stats_lock:
            return sum(counters.bytes_sent for counters in self._transport_counters.values())

    def get_stats_snapshot(self) -> dict:
        with self._stats_lock:
            return {
                "messages_generated": self._messages_generated,
                "bytes_generated": self._bytes_generated,
                "packets_sent": sum(counters.packets_sent for counters in self._transport_counters.values()),
                "bytes_sent": sum(counters.bytes_sent for counters in self._transport_counters.values()),
                "transports": {name: asdict(counters) for name, counters in self._transport_counters.items()},
                "recent_nmea": self.recent_nmea_log[-18:],
            }

    def publish_decoded_frame(self, frame: DecodedGnssFrame) -> None:
        """Broadcasts a decoded navigation frame ($GALINAV / $GALE6HAS / $GALE5 + JSON)."""
        if self.config.emit_galinav_raw:
            self._broadcast_line(frame.nmea_custom_sentence)

        if self.config.emit_trisat_json:
            # Compatible with TrisatBleServer.kt / BluetoothManager.swift JSON schema
            json_packet = {
                "type": "inav_frame" if frame.band_id == "GAL_E1" else "gnss_frame",
                "source": "simulated",
                "band": frame.band_id,
                "const": frame.constellation,
                "svid": frame.svid,
                "submsgId": frame.word_or_page_id,
                "hex": frame.hex_payload,
                "crc24q": frame.crc24q_hex,
                "osnmaHkroot": frame.osnma_hkroot_hex,
                "osnmaMack": frame.osnma_mack_hex,
                "hasOrbitCorrCm": frame.has_orbit_corr_cm,
                "ts": frame.timestamp_ms,
            }
            self._broadcast_line(json.dumps(json_packet))

    def publish_pvt(self, pvt: PvtSolution) -> None:
        """Broadcasts NMEA $GNGGA, $GAGSV/$GPGSV, and TRISAT JSON location & sat_status."""
        if self.config.emit_nmea:
            self._broadcast_line(format_gngga_sentence(pvt))
            for gsv in format_gsv_sentences(pvt.satellites):
                self._broadcast_line(gsv)

        if self.config.emit_trisat_json:
            loc_json = {
                "type": "location",
                "source": "simulated",
                "mode": pvt.solution_mode,
                "lat": pvt.latitude_deg,
                "lon": pvt.longitude_deg,
                "alt": pvt.altitude_m,
                "acc": pvt.horizontal_accuracy_m,
                "hdop": pvt.hdop,
                "pdop": pvt.pdop,
                "osnmaSats": pvt.osnma_authenticated_sats,
                "hasSats": pvt.has_corrected_sats,
            }
            self._broadcast_line(json.dumps(loc_json))

            sats_array = [
                {
                    "svid": s.svid,
                    "const": s.constellation,
                    "band": s.band_id,
                    "elev": s.elevation_deg,
                    "azim": s.azimuth_deg,
                    "cno": int(round(s.cn0_dbhz)),
                    "used": s.used_in_fix,
                    "osnma": s.has_osnma,
                    "hasPpp": s.has_e6_ppp,
                }
                for s in pvt.satellites
            ]
            self._broadcast_line(json.dumps({"type": "sat_status", "source": "simulated", "satellites": sats_array}))

    @property
    def connected_tcp_clients_count(self) -> int:
        with self._tcp_lock:
            return len(self._tcp_clients)
