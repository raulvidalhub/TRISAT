import unittest
from unittest.mock import Mock, patch

from trisat_sdr.bridge.telemetry_streamer import TelemetryStreamer
from trisat_sdr.config import ReceiverConfig, TelemetryBridgeConfig
from trisat_sdr.receiver import TrisatSdrReceiver


class TestTelemetryCounters(unittest.TestCase):
    def test_generated_lines_are_visible_without_any_transport(self):
        config = ReceiverConfig()
        config.telemetry = TelemetryBridgeConfig(
            udp_enabled=False, tcp_enabled=False, pty_serial_enabled=False
        )
        receiver = TrisatSdrReceiver(config)
        streamer = receiver.streamer
        streamer.start()
        self.addCleanup(streamer.stop)

        line = "$GNGGA,test"
        streamer._broadcast_line(line)
        bridge = receiver.get_status_snapshot()["bridge"]

        self.assertEqual(bridge["messages_generated"], 1)
        self.assertEqual(bridge["bytes_generated"], len(b"$GNGGA,test\r\n"))
        self.assertEqual(bridge["recent_nmea"], [line])
        self.assertEqual(bridge["packets_sent"], 0)
        self.assertEqual(bridge["bytes_sent"], 0)
        for stats in bridge["transports"].values():
            self.assertEqual(stats, {"attempts": 0, "packets_sent": 0, "bytes_sent": 0})

    def test_counts_each_udp_destination_and_tcp_client_separately(self):
        config = TelemetryBridgeConfig(udp_port=5005)
        streamer = TelemetryStreamer(config)
        payload = b"{}\r\n"
        udp = Mock()

        def sendto(data, address):
            if address[1] == 9090:
                raise OSError("UDP write failed")
            return len(data)

        udp.sendto.side_effect = sendto
        tcp_ok = Mock()
        tcp_busy = Mock()
        tcp_busy.sendall.side_effect = BlockingIOError("TCP send buffer full")
        streamer._udp_sock = udp
        streamer._tcp_clients.extend([tcp_ok, tcp_busy])
        self.addCleanup(streamer.stop)

        streamer._broadcast_line("{}")
        stats = streamer.get_stats_snapshot()

        udp.sendto.assert_any_call(payload, (config.udp_host, config.udp_port))
        udp.sendto.assert_any_call(payload, (config.udp_host, 9090))
        tcp_ok.sendall.assert_called_once_with(payload)
        tcp_busy.sendall.assert_called_once_with(payload)
        self.assertEqual(streamer.connected_tcp_clients_count, 1)
        self.assertEqual(stats["messages_generated"], 1)
        self.assertEqual(stats["transports"], {
            "udp": {"attempts": 2, "packets_sent": 1, "bytes_sent": len(payload)},
            "tcp": {"attempts": 2, "packets_sent": 1, "bytes_sent": len(payload)},
        })
        self.assertEqual(stats["packets_sent"], 2)
        self.assertEqual(stats["bytes_sent"], 2 * len(payload))

    def test_udp_port_9090_is_counted_once_and_stopped_socket_is_skipped(self):
        streamer = TelemetryStreamer(TelemetryBridgeConfig(
            udp_port=9090, tcp_enabled=False, pty_serial_enabled=False
        ))
        udp = Mock()
        udp.sendto.return_value = len(b"{}\r\n")
        with patch("trisat_sdr.bridge.telemetry_streamer.socket.socket", return_value=udp):
            streamer.start()
        try:
            streamer._broadcast_line("{}")
        finally:
            streamer.stop()
        streamer._broadcast_line("{}")

        udp.sendto.assert_called_once_with(b"{}\r\n", ("127.0.0.1", 9090))
        stats = streamer.get_stats_snapshot()
        self.assertEqual(stats["messages_generated"], 2)
        self.assertEqual(stats["transports"]["udp"]["attempts"], 1)
        self.assertEqual(streamer.packets_sent, 1)
        self.assertEqual(streamer.bytes_sent, len(b"{}\r\n"))
