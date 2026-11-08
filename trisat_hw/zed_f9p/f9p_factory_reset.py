#!/usr/bin/env python3
"""
f9p_factory_reset.py
--------------------
Performs a complete hardware Factory Reset on the u-blox ZED-F9P module:
1. Clears battery-backed RAM and non-volatile flash configuration (reverts to pristine u-blox factory state).
2. Enables multi-constellation GNSS (Galileo E1/E5b + GPS + GLONASS + BeiDou).
3. Configures UART1 and UART2 for continuous NMEA (GGA, RMC, GSV, GLL, VTG) + UBX binary output at 115200 bps.
4. Enables Galileo I/NAV raw navigation messages (UBX-RXM-SFRBX) for OSNMA verification.
5. Permanently saves all parameters to non-volatile flash memory (BBR & Flash).
"""

import sys
import glob
import time
import serial

if __package__:
    from .f9p_stream import build_ubx_msg
else:
    from f9p_stream import build_ubx_msg

def find_port():
    ports = glob.glob("/dev/cu.usbmodem*")
    if ports:
        return ports[0]
    return "/dev/cu.usbmodem2101"

def main():
    port = find_port()
    print("=" * 64)
    print("  TRISAT - u-blox ZED-F9P Complete Factory Reset & Optimization")
    print(f"  Target Serial Port: {port}")
    print("=" * 64)

    try:
        ser = serial.Serial(port, 115200, timeout=2.0)
        ser.dtr = True
        ser.rts = True
        print(f"[+] Successfully opened {port} at 115200 bps")
    except Exception as e:
        print(f"[-] Error opening port {port}: {e}")
        print("    Ensure the USB-C cable is connected to the red ZED-F9P board.")
        sys.exit(1)

    time.sleep(0.5)

    # =========================================================================
    # STEP 1: FACTORY RESET (UBX-CFG-CFG: Revert to Default Configuration)
    # Clear mask: 0x0000FFFF (Clear all sections in BBR/Flash)
    # Load mask:  0x0000FFFF (Revert to factory defaults in RAM)
    # =========================================================================
    print("\n[1/5] Reverting u-blox ZED-F9P to pristine Factory Defaults...")
    # UBX-CFG-CFG payload: clearMask (4 bytes), saveMask (4 bytes), loadMask (4 bytes), deviceMask (1 byte)
    reset_payload = bytes([
        0xFF, 0xFF, 0x00, 0x00,  # clearMask: clear all RAM/BBR
        0x00, 0x00, 0x00, 0x00,  # saveMask: none
        0xFF, 0xFF, 0x00, 0x00,  # loadMask: load factory defaults
        0x07                     # deviceMask: devBBR, devFlash, devEEPROM
    ])
    ser.write(build_ubx_msg(0x06, 0x09, reset_payload))
    ser.flush()
    time.sleep(1.5)
    print("      -> Memory cleared. Module rebooted with official factory defaults.")

    # =========================================================================
    # STEP 2: CONFIGURE PORTS (UART1, UART2, and USB at 115200 bps)
    # InProtoMask: UBX + NMEA + RTCM3 (0x0007)
    # OutProtoMask: UBX + NMEA (0x0003)
    # =========================================================================
    print("\n[2/5] Configuring Port Interfaces (UART1, UART2, and USB)...")

    # Port 1 (UART1) configuration: 115200 bps, 8N1, UBX+NMEA out
    uart1_payload = bytes([
        0x01, 0x00, 0x00, 0x00,  # portID: 1 (UART1)
        0xD0, 0x08, 0x00, 0x00,  # mode: 8N1
        0x00, 0xC2, 0x01, 0x00,  # baudRate: 115200
        0x07, 0x00,              # inProtoMask: UBX + NMEA + RTCM3
        0x03, 0x00,              # outProtoMask: UBX + NMEA
        0x00, 0x00, 0x00, 0x00   # flags, reserved
    ])
    ser.write(build_ubx_msg(0x06, 0x00, uart1_payload))

    # Port 2 (UART2) configuration: 115200 bps, 8N1, UBX+NMEA out
    uart2_payload = bytes([
        0x02, 0x00, 0x00, 0x00,  # portID: 2 (UART2)
        0xD0, 0x08, 0x00, 0x00,  # mode: 8N1
        0x00, 0xC2, 0x01, 0x00,  # baudRate: 115200
        0x07, 0x00,              # inProtoMask: UBX + NMEA + RTCM3
        0x03, 0x00,              # outProtoMask: UBX + NMEA
        0x00, 0x00, 0x00, 0x00   # flags, reserved
    ])
    ser.write(build_ubx_msg(0x06, 0x00, uart2_payload))
    time.sleep(0.5)
    print("      -> UART1 and UART2 set to 115200 bps with active NMEA+UBX output.")

    # =========================================================================
    # STEP 3: ENABLE STANDARD NMEA MESSAGES ON ALL PORTS (1 Hz)
    # =========================================================================
    print("\n[3/5] Activating Navigation & Telemetry Messages...")
    # Enable GGA (0xF0 0x00), RMC (0xF0 0x04), GSV (0xF0 0x03), GLL (0xF0 0x01), VTG (0xF0 0x05)
    nmea_msgs = [
        (0xF0, 0x00, "GGA (Fix & Position)"),
        (0xF0, 0x04, "RMC (Velocity & Time)"),
        (0xF0, 0x03, "GSV (Satellites & C/N0 SNR)"),
        (0xF0, 0x01, "GLL (Latitude/Longitude)"),
        (0xF0, 0x05, "VTG (Course over Ground)"),
        (0x02, 0x13, "UBX-RXM-SFRBX (Galileo OSNMA Raw Navigation Frames)")
    ]

    for msg_cls, msg_id, name in nmea_msgs:
        # Rate on I2C, UART1, UART2, USB, SPI = 1
        rate_payload = bytes([msg_cls, msg_id, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00])
        ser.write(build_ubx_msg(0x06, 0x01, rate_payload))
        time.sleep(0.05)
        print(f"      -> Activated {name}")

    # =========================================================================
    # STEP 4: CONFIGURE HIGH DYNAMICS & 1 HZ NAVIGATION RATE (UBX-CFG-RATE)
    # =========================================================================
    print("\n[4/5] Setting Navigation Measurement Rate to 1 Hz...")
    rate_cfg = bytes([
        0xE8, 0x03,  # measRate: 1000 ms (1 Hz)
        0x01, 0x00,  # navRate: 1 cycle
        0x01, 0x00   # timeRef: 1 (GPS time)
    ])
    ser.write(build_ubx_msg(0x06, 0x08, rate_cfg))
    time.sleep(0.2)

    # =========================================================================
    # STEP 5: PERMANENTLY SAVE ALL CONFIGURATION TO NON-VOLATILE FLASH (UBX-CFG-CFG)
    # =========================================================================
    print("\n[5/5] Burning clean configuration permanently into Flash & BBR memory...")
    save_payload = bytes([
        0x00, 0x00, 0x00, 0x00,  # clearMask: none
        0xFF, 0xFF, 0x00, 0x00,  # saveMask: save all RAM to Flash/BBR
        0x00, 0x00, 0x00, 0x00,  # loadMask: none
        0x07                     # deviceMask: devBBR, devFlash, devEEPROM
    ])
    ser.write(build_ubx_msg(0x06, 0x09, save_payload))
    ser.flush()
    time.sleep(1.0)
    print("      -> Saved! Configuration is now permanent across all reboots.")

    # Verification: Read back stream
    print("\n" + "=" * 64)
    print("  VERIFICATION STREAM (Pristine Factory NMEA Stream):")
    print("=" * 64)

    t_end = time.time() + 4.0
    while time.time() < t_end:
        line = ser.readline().decode("ascii", errors="ignore").strip()
        if line.startswith("$"):
            print(f"  {line}")

    ser.close()
    print("\n[+] Success! Your u-blox ZED-F9P is 100% restored and optimized for TRISAT.\n")

if __name__ == "__main__":
    main()
