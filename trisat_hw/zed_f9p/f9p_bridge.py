#!/usr/bin/env python3
"""
f9p_bridge.py
-------------
High-performance telemetry bridge for u-blox ZED-F9P receiver.
Auto-detects USB ports (/dev/cu.usbmodem*) and broadcasts NMEA + UBX frames
via UDP (:9090) across localhost and local LAN (for iPhone/iPad on Wi-Fi).
"""

import sys
import glob
import socket

if __package__:
    from .f9p_stream import F9pStream, build_ubx_msg
else:
    from f9p_stream import F9pStream, build_ubx_msg

UDP_PORT = 9090
MAX_UDP_PAYLOAD = 65_507

def find_f9p_port():
    candidates = glob.glob("/dev/cu.usbmodem*")
    if candidates:
        return candidates[0]
    return None

def main():
    port = find_f9p_port()
    if not port:
        print("[-] Error: No u-blox ZED-F9P detected on USB (/dev/cu.usbmodem*).")
        print("    Please connect the USB-C cable directly to the red ZED-F9P board.")
        sys.exit(1)

    import serial

    print("=" * 64)
    print("  TRISAT - u-blox ZED-F9P USB Native Telemetry Bridge")
    print(f"  Target UDP: Broadcast on port :{UDP_PORT}")
    print(f"  Serial Port: {port}")
    print("=" * 64)

    # Setup UDP socket with broadcast enabled so iPhone/iPad on local Wi-Fi can receive
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
        ser.dtr = True
        ser.rts = True
        print(f"[+] Connected to {port} at 115200 bps")
    except Exception as e:
        sock.close()
        print(f"[-] Error opening {port}: {e}")
        sys.exit(1)

    try:
        ser.write(build_ubx_msg(0x0A, 0x04))  # Poll hardware version.
        # The three-byte CFG-MSG sets the rate for the current port (USB).
        # Enable NMEA GSV, GGA, RMC, GSA, GST, and the raw UBX-RXM-SFRBX message.
        messages = (
            (0xF0, 0x03), (0xF0, 0x00), (0xF0, 0x04),
            (0xF0, 0x02), (0xF0, 0x07), (0x02, 0x13),
        )
        for msg_class, msg_id in messages:
            ser.write(build_ubx_msg(0x06, 0x01, bytes((msg_class, msg_id, 1))))
        ser.flush()

        print(f"[+] Live streaming active (Localhost & Wi-Fi Broadcast :{UDP_PORT}). Press Ctrl+C to stop.\n")
        stream = F9pStream()
        while True:
            chunk = ser.read(min(ser.in_waiting, 4096) or 1)
            for frame in stream.feed(chunk):
                if frame.startswith(b"$"):
                    ascii_str = frame.decode("ascii").strip()
                    print(f"[NMEA] {ascii_str}")
                    payload = (ascii_str + "\n").encode("ascii")
                else:
                    payload = b"RAW:" + frame
                    if len(payload) > MAX_UDP_PAYLOAD:
                        continue
                    hex_str = " ".join(f"{byte:02X}" for byte in frame[:16])
                    print(f"[UBX-RAW] {hex_str}...")
                sock.sendto(payload, ("127.0.0.1", UDP_PORT))
                sock.sendto(payload, ("255.255.255.255", UDP_PORT))

    except KeyboardInterrupt:
        print("\n[+] Bridge stopped by user.")
    finally:
        ser.close()
        sock.close()

if __name__ == "__main__":
    main()
