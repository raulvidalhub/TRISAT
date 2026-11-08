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

* **Decoded Galileo I/NAV output:** Add `--emit-galinav` for consumers that support the following layout. The bridge keeps sending the original `RAW:` packets and sends a second datagram for each nominal E1-B or E5b-I `RXM-SFRBX` v2 page pair that passes the Galileo CRC-24Q check.

  ```text
  $GALINAV,<svid>,<word_type>,<60 hex digits>,<E1-B or E5b-I>*<checksum>
  ```

  The hex contains the two 120-bit page parts in transmission order, including their tail bits. The sentence checksum covers the ASCII body. CRC verification checks the I/NAV bits and leaves OSNMA authentication separate. The option is off by default because the current Apple I/NAV display assumes the legacy payload layout.

* **Test without a receiver:**
  ```bash
  python3 -m unittest discover -s trisat_hw/zed_f9p/tests -v
  ```
  Tests include nominal E1-B page pairs from Annex A.6.3 and a published E5b-I example, wrapped in UBX for transport testing. [Galileo OSNMA Receiver Guidelines](https://www.gsc-europa.eu/sites/default/files/sites/all/files/Galileo-OSNMA-RX-Guidelines_in_force.pdf) · [NovAtel E5b-I example](https://docs.novatel.com/OEM7/Content/Logs/GALINAVRAWDATA.htm)

* **Receiver follow-up:** With the receiver in open sky, run the bridge with `--emit-galinav`. Save the binary `RXM-SFRBX` stream and UDP datagrams from the same interval. Record the module variant and firmware, then compare SVID, signal ID and word type between the binary capture and the decoded output.

* **Factory Restore:**
  ```bash
  python3 trisat_hw/zed_f9p/f9p_factory_reset.py
  ```
  Restores default 38400 bps u-blox settings if communication is ever lost.

### Offline OSNMA verification for ZED-F9P

The F9P replay uses the same OSNMAlib verifier as the [Septentrio SBF viewer](../trisat_sdr/README.md#optional-offline-osnma-verification). It checks the UBX checksum and Galileo CRC, then passes complete E1-B pages to the verifier for DSM-KROOT, TESLA and navigation-tag verification. Each reported count is for a tag and its target SVID. A failed tag is a cryptographic mismatch. An empty count can also mean that the capture lacked enough OSNMA material to verify tags. The result describes the recorded navigation data.

Set up OSNMAlib using the [SBF replay instructions](../trisat_sdr/README.md), then run from the repository root:

```bash
python -m trisat_hw.zed_f9p.osnma_replay capture.jsonl --merkle-tree merkle.xml --public-key public.xml
```

The capture contains one JSON object per line. Each object has an integer `galileo_week`, an integer `tow_s` for the first transmitted symbol of the even E1-B page, and `ubx_hex` for the full `RXM-SFRBX` packet, including its sync bytes and checksum. For UDP captures, remove the four-byte `RAW:` prefix before hex encoding. Order the rows by GST. Satellites can share a timestamp. Identical copies at one epoch count once. Conflicting copies cause the replay to stop.

`RXM-SFRBX` and `$GALINAV` carry no page timestamp. Supply the page GST from a timing source that can correlate the capture with the transmission epoch. The replay assumes those times and the supplied Merkle tree and public key XML files are trusted. Use authenticated material appropriate to the capture date. This offline tool does not establish independent clock synchronisation or live replay protection.

When present, the broadcast GST in WT0 (time field `10`), WT5 and WT6 is compared with the capture time. WT6 checks TOW only. A mismatch, an out-of-order epoch or conflicting CRC-valid pages for one satellite and epoch stops the replay with an error and no authentication summary. This is a consistency check against the navigation bits. The input clock still requires an independent reference.

The JSON report adds a `status` and a `capture` section while retaining the per-satellite verified and failed tag counts. `no_valid_pages` means no eligible E1-B page reached the verifier. `no_verifiable_tags` means valid pages were present but no tag could be evaluated successfully or rejected. `tags_verified` indicates positive verification with no reported tag failures. `tag_failures` can coexist with verified tags for other data. The counters separate invalid UBX, rejected I/NAV and duplicate pages. `missing_epochs` counts two-second slots between the first and last accepted page where no eligible page was seen from any satellite. It cannot measure per-satellite visibility or losses before or after the accepted interval.

#### Reproduce the hardware-free validation

Download [Annex B from the European GNSS Service Centre](https://www.gsc-europa.eu/sites/default/files/sites/all/files/Test_vectors.zip) and set `TRISAT_OSNMA_ANNEX_B` to the ZIP path. Run `python -m unittest discover -s trisat_hw/zed_f9p/tests -v`. The optional tests use configurations 1 and 2 with their matching test keys. They use the official transmission time and wrap each original page in a constructed UBX packet.

| Input | Verified tags | Failed tags |
| --- | ---: | ---: |
| Configuration 1 | 12,418 | 0 |
| Configuration 2 | 11,325 | 0 |
| Configuration 1 with all 40 OSNMA bits erased | 0 | 0 |
| Configuration 1 with altered WT1–4 navigation bits | 1,054 | 11,364 |

Both altered controls recalculate the Galileo CRC and UBX checksum. The remaining verified tags in the last row cover data unaffected by the changed bits.

The same Annex B test also shifts configuration 1 by +1 s, +2 s, −30 s and one full week, removes 60 consecutive page epochs (120 s), and duplicates every page. The timestamp shifts produce an error and no summary. The gap removes 1,560 pages and reduces verified tags from 12,418 to 12,038 with zero tag failures. The duplicated run drops 46,800 redundant pages and yields exactly the same tag counts by satellite as the original.

With the physical receiver, capture `RXM-SFRBX` in open sky and establish a way to correlate every E1-B page with GST using a separate time reference. Record the firmware and timing setup. Check for missing pages, duplicates and subframe alignment before replaying with the operational keys. Confirm that tags verify after the corresponding TESLA keys arrive.

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
