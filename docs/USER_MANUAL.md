# TRISAT - Multiplatform User Manual & Technical Reference Guide

Welcome to the **TRISAT (Authenticated Earth Intelligence)** multiplatform application manual. This document explains the repository architecture, features, GNSS testing workflows, and OSNMA verification tools provided by TRISAT across Android, iOS, iPadOS, and macOS ecosystems.

---

## 1. Application Overview & Repository Structure

TRISAT is a **multiplatform GNSS intelligence solution** designed for **Galileo OSNMA (Open Service Navigation Message Authentication) testing**, multi-constellation GNSS signal analysis, anti-spoofing diagnostic evaluation, and spatial coordinate verification.

### Repository Layout:
* 📂 **`trisat_ios/`**: Native iOS & iPadOS Application (Swift, SwiftUI, CoreLocation, CoreBluetooth, MapKit, CryptoKit).
* 📂 **`trisat_mac/`**: Native macOS Application (Swift, SwiftUI, Network.framework, POSIX serial port).
* 📂 **`trisat_android/`**: Native Android Application (Kotlin, Jetpack Compose, Android GNSS HAL Location APIs).
* 📂 **`trisat_hw/`**: Hardware firmwares, drivers, and telemetry bridges for physical GNSS receivers:
  * `esp32/esp32_hybrid_bridge/`: ESP32 DevKit firmware bridging u-blox ZED-F9P via Bluetooth Low Energy (Nordic UART NUS) and Wi-Fi UDP (`:9090`).
  * `zed_f9p/`: Python USB-CDC bridge daemon and factory restore scripts for u-blox ZED-F9P.
  * `sxblue/`: Python USB driver and EEPROM configurator for Geneq SXblue sub-meter receivers.
* 📂 **`trisat_sdr/`**: Software-Defined Radio engine (Python 3, Dual-HackRF, E1 OSNMA, E6 HAS-UA, Web UI `:8085`).
* 📂 **`docs/`**: Comprehensive documentation suite (`USER_MANUAL.md`, `WEB_SERVER_GUIDE.md`).
* 📂 **`notebooks/`**: Interactive computational notebooks for OSNMA Annex A and HAS PPP.
* 📄 **`README.md`**: Project overview, feature summary, and build instructions.

---

## 2. Core Capabilities

* **Anti-Flicker Open Sky Polar Skyplot:** Interactive 360° skyplot with constellation color coding (Galileo Cyan, GPS Amber, GLONASS Red, BeiDou Green) with a persistent 30-second satellite cache that **completely eliminates flickering**.
* **Satellite C/N0 Signal Strength Bar Chart:** Real-time vertical SNR bar chart displaying carrier-to-noise ratio in dB-Hz color-coded by signal quality (Green $\ge 35$ dB-Hz, Yellow $\ge 25$ dB-Hz, Red $< 25$ dB-Hz) with constellation PRN badges (`E02`, `G08`, `R05`, `B12`).
* **Geneq SXblue USB Telemetry Bridge:** Low-level PyUSB/libusb driver interfacing with the Geneq SXblue FTDI USB chip (`VID: 0x0403`, `PID: 0xb5a0`) at 19200 bps, broadcasting JSON and raw NMEA/$BIN datagrams to `127.0.0.1:9090` via `Network.framework`.
* **Galileo I/NAV & OSNMA Receiver Test:** Direct extraction and inspection of raw Galileo `TYPE_GAL_I` navigation frames and 250-bit subframe pages.
* **CelesTrak TLE Orbital Propagator & 24h Time Slider:** Download real-time satellite orbital elements and simulate constellation geometries across a 24-hour window ($\pm 12\text{h}$).
* **Differential DGPS / RTK Telemetry Analysis:** Real-time decoding of `$GPGGA` differential fix mode, base station ID, correction age (seconds), HDOP/PDOP, and `$GPGST` pseudorange RMS error statistics.
* **Geospatial Navigator Exporter:** Dynamic hemisphere coordinates (`N`/`S` and `E`/`W`), clean decimal clipboard copying, and direct Apple Maps / Google Maps intent launching.

---

## 3. Screen & Feature Guide

### 📱 Dashboard Tab
1. **Open Sky Satellite View (Skyplot):**
   * Displays satellites in polar coordinates (Azimuth $0^\circ - 360^\circ$, Elevation $0^\circ - 90^\circ$).
   * Interactive filter chips allow toggling individual constellations (Galileo, GPS, GLONASS, BeiDou) on or off.
   * **Adaptive Layout:** 1-column vertical on iPhone; 2-column side-by-side on iPad & macOS with 320pt large Skyplot!
2. **Constellation Signal Matrix:**
   * Grid summary showing visible satellite count and average signal power ($C/N_0$) across Galileo, GPS, GLONASS, and BeiDou networks.
3. **DOP Geometry Quality Card:**
   * Displays HDOP, VDOP, PDOP, and 3D Geometry Quality indicator.
4. **Embedded Geospatial Mini Map:**
   * Live interactive MapKit view displaying current GPS/Galileo position pin marked `GNSS LIVE`.

---

### 📶 Signal Processing Tab

The **Signal Processing** tab provides a clean, desktop-fitted 2×2 view of all telemetric, RF, and navigation streams (all hardware/SDR configuration controls are centralized in the **Settings** tab):

1. **Top Differential & Telemetry Status Header:**
   * **Active Source & Constellation Filters:** Displays the active receiver source and interactive filter chips (`Galileo`, `GPS`, `GLONASS`, `BeiDou`).
   * **Fix Mode:** *Galileo E6 HAS PPP (SL1)*, *DGPS Differential (SXblue)*, *GPS Autonomous*, *RTK Fixed (Centimeter)*.
   * **Sats in Fix / HDOP:** Live satellite count and Horizontal Dilution of Precision.
   * **Correction Source:** Station / Service ID (e.g. `E6-HAS-MT1` or `0124`) and correction age in seconds.
   * **Pseudorange Error:** RMS pseudorange noise error and DIA Baarda $w$-test statistics.
2. **Open Sky Radar:**
   * Compact polar radar displaying 4-constellation satellite positions ($\bigcirc$) without flickering.
3. **Satellite Signal Strength C/N0 Bar Chart:**
   * Vertical SNR bars in dB-Hz color-coded green/yellow/red with constellation legend and PRN badges (`E02`, `G08`, `R05`, `B12`).
4. **ASCII NMEA Telemetry Stream:**
   * Full-width monospaced green terminal scrolling incoming `$GNGGA`, `$GPGGA`, `$GAGSV`, `$GPGST`, `$GALINAV`, and `$GALE6HAS` sentences.
5. **Galileo I/NAV & E6 HAS Subframes:**
   * Live cards showing demodulated 240-bit Galileo I/NAV v2.2 pages (`WT 1..6, 16, 17..20, 22, 44`), `CRC-24Q` parity status, and 40-bit OSNMA (`HKROOT` + `MACK`) fields.

---

### 🛡️ Threat Analysis Tab
1. **Interactive Attack Simulation Bar & Threat Score Gauge:**
   * Real-time 0–100% Threat Risk Score with one-click interactive attack simulation buttons:
     * **Nominal:** Clean multi-constellation RF spectrum and valid Galileo OSNMA v1.1 TESLA tags.
     * **Jamming:** Simulates broadband L1/E1/E6 noise floor injection (+18 dB AGC saturation), dropping $C/N_0$ by ~22 dB-Hz and degrading 3D fix geometry.
     * **Spoofing:** Simulates a coherent false-signal emitter with anomalously flat high $C/N_0$ (51–52 dB-Hz), spatial azimuth clustering, and $\pm 48.5\text{ m}$ `$GPGST` pseudorange residual divergence.
     * **Meaconing:** Simulates a delayed RF rebroadcast attack (+420 ns clock jump) with skyplot rotation and DGPS age lag.
     * **OSNMA Fail:** Simulates Galileo E1-B I/NAV navigation data manipulation with a forged 40-bit OSNMA MACK tag caught by HMAC-SHA-256 verification.
2. **Embedded Spatial Skyplot & C/N0 Spectrum Bar Chart:**
   * Displays the live polar **Skyplot** and **Satellite $C/N_0$ Bar Chart** side-by-side inside Threat Analysis so you can visually inspect the spatial and spectral impact of each simulated attack in real time.
3. **6 Diagnostic Security Cards:**
   * **Galileo OSNMA Cryptographic Auth (v1.1)**, **Jamming & RF Interference**, **Spoofing / Coherent Emitter Detection**, **Meaconing / Replay Delay Monitor**, **Galileo E6-B HAS-UA & DIA Integrity**, and **Galileo EWSS-CAMF & WT44 Timing Service**.

---

### ⚙️ Settings Tab
All hardware, telemetry, and constellation orbital controls are centralized in the **Settings** tab via three mutually exclusive operating modes:

1. **Operating Mode Selector:**
   * **`🛰️ Internal + TLE` (Mode 0):** Internal iPhone / Mac GPS (CoreLocation) coordinates combined with the 116-satellite CelesTrak SGP4 24-hour orbital propagator. Signal Processing and Threat Analysis views enter a clean Standby mode.
   * **`📡 Bluetooth` (Mode 1):** Connects to the external physical **TRISAT ESP32 Hybrid Bridge** via BLE Nordic UART Service (`TRISAT-GNSS-BLE`) or MFi receivers. Automatically activates when Bluetooth connects and streams real-time `$GNGGA`, `$GAGSV`, `$GPGSV`, and paced `$GALINAV` subframes.
   * **`🌐 UDP` (Mode 2):** Connects to localhost/Wi-Fi UDP port `9090` or launches the internal Swift telemetry simulator (`Start Simulator`) with multi-frequency Galileo E1/E6 + GPS L1/L5 dynamic carrier streams.
2. **CelesTrak 4-Constellation TLE Orbits & Live Skyplot Preview:**
   * Built-in 116-satellite 4-constellation Keplerian Walker catalog (`30 Galileo`, `31 GPS`, `24 GLONASS`, `31 BeiDou`) with live CelesTrak cloud refresh, interactive constellation filter chips, and a $\pm 12\text{h}$ Keplerian orbit time-offset slider.
3. **Bluetooth GNSS Receivers & Hardware USB Serial Ports:**
   * Dedicated BLE scanner listing discovered devices with RSSI metrics and single-tap connection.
   * On macOS: Direct POSIX `/dev/cu.usbserial*` (CH340 ESP32 bridge) and `/dev/cu.usbmodem*` (u-blox CDC) port selectors.

---

## 4. Hardware Receiver Setup & Deployment

### 1️⃣ SparkFun u-blox ZED-F9P + ESP32 Hybrid Bridge (BLE & WiFi)
The recommended portable setup for iOS field testing:
* **Connections:**
  * u-blox ZED-F9P TX1 $\to$ ESP32 GPIO 19 (RX2)
  * u-blox ZED-F9P RX1 $\leftarrow$ ESP32 GPIO 18 (TX2)
  * Baud rate: 115200 bps
* **Firmware:** Located in `trisat_hw/esp32/esp32_hybrid_bridge/esp32_hybrid_bridge.ino`.
* **Flash with Arduino IDE:**
  1. Open `trisat_hw/esp32/esp32_hybrid_bridge/esp32_hybrid_bridge.ino`.
  2. Select board **ESP32 Dev Module**, speed **115200**, and serial port `/dev/cu.usbserial-*`.
  3. Upload sketch.
* **Operation:**
  * Power the unit via USB.
  * In the TRISAT iOS app, open **Settings** $\to$ **Bluetooth**, tap **Scan BLE**, and select **`🛰️ TRISAT-GNSS-BLE`**.
  * The app will automatically connect, switch to Mode 1, and stream live NMEA sentences and paced Galileo I/NAV frames.

### 2️⃣ Geneq SXblue USB Receiver (macOS)
Because Geneq SXblue USB receivers use a custom FTDI Product ID (`VID: 0x0403, PID: 0xb5a0`), macOS does not generate a standard `/dev/cu.usbserial` node.
1. Run the bridge launcher:
   ```bash
   sudo ./trisat_hw/sxblue/run_bridge.sh
   ```
2. Open TRISAT macOS (`open build/TRISAT.app` or Run from Xcode).
3. The app will ingest UDP telemetry on port `9090`.

### 3️⃣ Direct USB u-blox ZED-F9P Bridge (macOS)
For bench testing the ZED-F9P directly on a Mac via USB-C:
```bash
python3 trisat_hw/zed_f9p/f9p_bridge.py
```
This script configures the u-blox ZED-F9P for high-rate NMEA and binary `UBX-RXM-SFRBX` output, forwarding all packets to UDP `:9090`.

### Android external UDP diagnostics

Connect Android to the bridge's network and select **Settings → External Receiver / UDP**. The listener opens port `9090` in this mode. The bridge can send one checksummed NMEA sentence per datagram to the phone's IP address or broadcast on the same subnet.

The dashboard counts UDP datagrams and accepted NMEA sentences separately. **Receiving NMEA** means supported sentences such as GGA, RMC or GSV passed their checksums. **NMEA data stale** appears after five seconds without an accepted sentence. NMEA reception has unverified provenance. Trust evaluation stays pending because it requires raw GNSS measurements.

---

## 5. How to Test OSNMA on a Physical Device

### Android Device (`trisat_android`):
1. Build and install the APK:
   ```bash
   ./gradlew assembleDebug
   ```
2. Open TRISAT outdoors under clear open sky and grant location permissions.
3. Go to **Signal Processing** $\rightarrow$ **Galileo I/NAV & OSNMA Receiver Test**.
4. **Result:**
   * **Green Badge (`I/NAV CAPABLE (OSNMA OK)`)**: Device delivers raw Galileo `TYPE_GAL_I` navigation frames.
   * **Orange Badge (`NO I/NAV DETECTED`)**: Device hardware driver does not expose raw I/NAV pages required for OSNMA.

### iOS / macOS Target (`trisat_ios` / `trisat_mac`):
1. Open `trisat_mac/TRISAT.xcodeproj` or `trisat_ios/TRISAT.xcodeproj` in Xcode.
2. Build and run the app (`Cmd + R`).
3. Connect the SXblue receiver over USB daemon or Bluetooth LE to stream raw Galileo I/NAV frames into the app.
