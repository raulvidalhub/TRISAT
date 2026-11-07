# TRISAT Hardware Bridges & Receivers (`trisat_hw`)

This directory houses the hardware firmware, drivers, and local telemetry bridges for physical GNSS receivers supported by the **TRISAT** multiplatform suite (iOS, macOS, Android).

---

## 📁 Directory Structure

```text
trisat_hw/
├── esp32/
│   ├── esp32_hybrid_bridge/       # Arduino firmware: BLE Nordic UART + WiFi UDP :9090
│   │   └── esp32_hybrid_bridge.ino
│   └── esp32_sniffer/             # Hardware UART/SPI logic analyzer & baud detector
│       └── esp32_sniffer.ino
│
├── zed_f9p/                       # SparkFun u-blox ZED-F9P High-Precision GNSS
│   ├── f9p_bridge.py              # USB-CDC daemon (/dev/cu.usbmodem*) to UDP :9090
│   └── f9p_factory_reset.py       # Configuration restore and persistent Flash optimizer
│
└── sxblue/                        # Geneq SXblue Sub-Meter Survey Receiver
    ├── sxblue_reader.py           # USB FTDI reader daemon to UDP 127.0.0.1:9090
    ├── sxblue_config.py           # EEPROM programmer for Galileo I/NAV ($JBIN)
    ├── run_bridge.sh              # Elevated launcher script for macOS
    └── PDFs/ & SDK/               # Original Geneq manuals and manufacturer SDK
```

---

## 1. ESP32 Hybrid Telemetry Bridge (`trisat_hw/esp32/esp32_hybrid_bridge`)

The **ESP32 Hybrid Bridge** is the recommended wireless adapter for portable field testing with an iPhone or iPad. It bridges high-rate NMEA and binary Galileo navigation messages from the u-blox ZED-F9P across Bluetooth Low Energy and Wi-Fi.

### Hardware Specifications & Pinout:
* **Microcontroller:** ESP32-D0WDQ6 DevKit (with CH340 or CP2102 USB UART).
* **GNSS Receiver:** SparkFun GPS-RTK-SMA (u-blox ZED-F9P, firmware HPG 1.13+).
* **Physical UART Wiring:**
  * **ESP32 GPIO 19 (RX2)** $\leftarrow$ **u-blox TX1** (Orange wire)
  * **ESP32 GPIO 18 (TX2)** $\to$ **u-blox RX1** (White wire)
  * **GND** $\leftrightarrow$ **GND**
  * **Baud Rate:** 115200 bps (8N1) with an expanded 4096-byte hardware ring buffer (`Serial2.setRxBufferSize(4096)`).

### Transmission Protocols:
1. **Bluetooth Low Energy (Nordic UART Service - NUS):**
   * Service UUID: `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`
   * RX Char UUID: `6E400002-B5A3-F393-E0A9-E50E24DCCA9E`
   * TX Char UUID: `6E400003-B5A3-F393-E0A9-E50E24DCCA9E`
   * Advertises as: `TRISAT-GNSS-BLE`
   * **Paced Galileo I/NAV Delivery:** Demodulates binary `UBX-RXM-SFRBX` frames (Class `0x02`, ID `0x13`) from the u-blox receiver and formats `$GALINAV` sentences. Transmits **1 subframe every 1200 ms** over BLE with 4 ms inter-chunk pacing to guarantee zero packet drops in the iOS CoreBluetooth stack.
   * **Filtered NMEA Stream:** Forwards essential `$GNGGA`, `$GAGSV`, and `$GPGSV` sentences over BLE to maintain high responsiveness.
2. **Wi-Fi SoftAP & UDP Broadcast:**
   * SSID: `TRISAT-GNSS`
   * Password: `trisat4ever`
   * Broadcast Target: `192.168.4.255:9090`
   * Streams all raw NMEA sentences and `$GALINAV` frames via UDP datagrams.
3. **USB Serial Monitor:**
   * Concurrent USB mirror at 115200 bps for debugging on Mac or PC.

### Flashing Instructions (Arduino IDE):
1. Install the **ESP32 Board Package** in Arduino IDE (`esp32 by Espressif Systems`).
2. Open [`esp32_hybrid_bridge/esp32_hybrid_bridge.ino`](esp32_hybrid_bridge/esp32_hybrid_bridge.ino).
3. Select Board: **ESP32 Dev Module**.
4. Select Port: `/dev/cu.usbserial-*` (or `/dev/cu.wchusbserial*`).
5. Upload the sketch.

---

## 2. u-blox ZED-F9P Direct USB (`trisat_hw/zed_f9p`)

Used for direct USB-C connection between the SparkFun ZED-F9P board and a Mac or Linux laptop.

* **Hardware:** SparkFun GPS-RTK-SMA board connected directly via USB-C (`/dev/cu.usbmodem*`).
* **Run Telemetry Daemon:**
  ```bash
  python3 trisat_hw/zed_f9p/f9p_bridge.py
  ```
  Requests NMEA GSV, GGA, RMC, GSA, GST, and `UBX-RXM-SFRBX` output on the connected USB port. The bridge forwards complete NMEA sentences and checksum-validated UBX packets to UDP port `9090` on localhost and the local network. Each UBX datagram starts with `RAW:`.

* **Test without a receiver:**
  ```bash
  python3 -m unittest discover -s trisat_hw/zed_f9p/tests -v
  ```

* **Factory Restore:**
  ```bash
  python3 trisat_hw/zed_f9p/f9p_factory_reset.py
  ```
  Restores default 38400 bps u-blox settings if communication is ever lost.

---

## 3. Geneq SXblue Sub-Meter Receiver (`trisat_hw/sxblue`)

Used for professional GIS receivers featuring custom FTDI USB chips (`VID: 0x0403, PID: 0xb5a0`).

* **One-Time EEPROM Configuration:**
  ```bash
  sudo python3 trisat_hw/sxblue/sxblue_config.py
  ```
  Programs the SXblue EEPROM to output `$JBIN,94` and `$JBIN,95` Galileo navigation pages.

* **Run Daemon:**
  ```bash
  sudo ./trisat_hw/sxblue/run_bridge.sh
  # or:
  sudo python3 trisat_hw/sxblue/sxblue_reader.py
  ```
  Reads raw FTDI packets and broadcasts NMEA sentences to `127.0.0.1:9090`.
