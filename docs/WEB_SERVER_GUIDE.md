# 🌐 TRISAT Web Server & Dashboard Guide

Welcome to the **TRISAT Web Server & Real-Time SDR Dashboard Guide**. This document describes how to launch, configure, and use the cross-platform Web Dashboard (`http://127.0.0.1:8085`) that runs alongside the TRISAT Software-Defined Radio (SDR) and multi-constellation telemetry engines.

---

## 1. Overview & Architecture

The TRISAT Web Dashboard is an integrated, lightweight, real-time HTTP & Server-Sent Events (SSE) server implemented in pure Python (`trisat_sdr/ui/web_dashboard.py`) with zero external web framework dependencies (built directly on Python's standard library `http.server`).

It provides a single-page, dark-mode cockpit for real-time visualization of:
* **Dual-HackRF Front-End Status:** Master SDR #0 (E1/L1 @ 1575.42 MHz) and Slave SDR #1 (E6 @ 1278.75 MHz, E5a, E5b, or E5 AltBOC) with 10 MHz CLKOUT/CLKIN clock synchronization.
* **RF Spectrum & Waterfall:** Live interactive HTML5 Canvas RF power spectral density (PSD) and real-time waterfall display.
* **4-Constellation Tracking Grid:** Carrier-to-noise ratio ($C/N_0$), Doppler shift, elevation, and azimuth across Galileo, GPS, GLONASS, and BeiDou.
* **Demodulated Navigation Frames:** Live binary & hex stream of Galileo E1-B I/NAV, E6 HAS, E5, and GPS L1 LNAV pages.
* **Galileo OSNMA Cryptographic Engine:** Real-time ECDSA P-256 DSM-KROOT authentication, one-way TESLA key chain traversal ($K_i \rightarrow K_0$), and Annex A test vector validation.
* **Galileo HAS-UA Engine:** Precise Point Positioning (PPP) Single-Differenced Extended Kalman Filter (EKF), Reed-Solomon $RS(255, 32)$ decoding, DIA Baarda $w$-test outlier exclusion, NTCM-G ionospheric corrections, and 33-column `.sol` trajectory logging.
* **Galileo OS SIS v2.2 Services:** I/NAV Reduced Clock & Ephemeris Data (WT16 RedCED), Reed-Solomon Outer FEC (WT17–20), Secondary Synchronization Pattern (SSP), and Emergency Warning Satellite Service (EWSS-CAMF).

---

## 2. How to Launch the Web Server

You can launch the TRISAT Web Server using either the native TRISAT macOS application or directly from the Terminal.

### Option A: From the TRISAT macOS Application (Recommended)
1. Open **TRISAT** on your Mac (`open ./build/TRISAT.app` or from Xcode).
2. Go to the **Settings** tab.
3. In the **TRISAT-SDR Dual-HackRF & Local Bridges** card:
   * Select your desired secondary SDR band (e.g., `E6B/C (HAS PPP SL1)`).
   * Click **`Start TRISAT-SDR`** (launches the in-process telemetry engine and background Python SDR daemon).
   * Click **`Web Dashboard (:8085)`**.
4. Your default web browser will automatically open:
   ```text
   http://127.0.0.1:8085
   ```

---

### Option B: From the Terminal (macOS / Linux / Windows)
Open a terminal in the root of the TRISAT repository and run:

```bash
# Default: Master E1 (1575.42 MHz) + Slave E6 HAS (1278.75 MHz) on port 8085
python3 trisat_sdr/main.py
```

Terminal will display:
```text
==============================================================================
 🛰️  TRISAT-SDR | Software-Defined Multi-Band GNSS Receiver (v1.0.0)
    Portable Engine: macOS · GNU/Linux · Windows
==============================================================================
 [SDR #0 MASTER] HackRF One #0 (Primary E1/L1)
    Band: GAL_E1 (1575.42 MHz) | Fs: 8.184 MS/s | Bias-T: ON | CLKOUT: 10MHz
    CMD : hackrf_transfer -d 0 -r /dev/stdout -f 1575420000 -s 8184000 -a 1
 [SDR #1 SLAVE ] HackRF One #1 (Secondary High-Precision)
    Band: GAL_E6 (1278.75 MHz) | Fs: 8.184 MS/s | Bias-T: ON | CLKIN : SYNC
    CMD : hackrf_transfer -d 1 -r /dev/stdout -f 1278750000 -s 8184000 -a 1
------------------------------------------------------------------------------
 [BRIDGE] UDP Stream : udp://127.0.0.1:5005
 [BRIDGE] TCP Server : tcp://127.0.0.1:5006
 [WEB UI] Dashboard  : http://127.0.0.1:8085 (mirrored on :8080)
==============================================================================
[+] TRISAT-SDR Pipeline Active (Dual-HackRF E1 + GAL_E6). Press Ctrl+C to stop.
```

---

## 3. Command-Line Options & Band Switching

You can customize the web port, secondary HackRF frequency band, and telemetry output with command-line flags:

```bash
# Run with Galileo E5b (Dual-Frequency I/NAV) on custom port 8090
python3 trisat_sdr/main.py --band2 GAL_E5B --web-port 8090

# Run with Galileo E5 AltBOC wideband (1191.795 MHz)
python3 trisat_sdr/main.py --band2 GAL_E5_ALTBOC

# Run in Single-SDR mode (Master E1 only)
python3 trisat_sdr/main.py --single-sdr

# Run in headless mode (terminal output only, no web server)
python3 trisat_sdr/main.py --headless

# Run for a fixed number of epochs and exit (e.g. 10 epochs for unit testing)
python3 trisat_sdr/main.py --epochs 10
```

### Supported Secondary Frequency Bands (`--band2`):
| Band Key | Center Frequency | Target Service / Modulation |
| :--- | :---: | :--- |
| `GAL_E6` *(default)* | 1278.75 MHz | Galileo High Accuracy Service (HAS PPP SL1 / $BPSK(5)$) |
| `GAL_E5A` | 1176.45 MHz | Galileo F/NAV + GPS L5 ($QPSK(10)$) |
| `GAL_E5B` | 1207.14 MHz | Galileo I/NAV Dual-Frequency ($QPSK(10)$) |
| `GAL_E5_ALTBOC` | 1191.795 MHz | Full Coherent E5 Wideband ($AltBOC(15,10)$) |

---

## 4. REST APIs & Integration

External tools can use these JSON endpoints. Unknown paths return HTTP `404` with an `error` field. The dashboard HTML is served at `/`.

### `GET /api/status`
Returns the current telemetry snapshot, including SDR configuration, tracked satellites, PVT, OSNMA, and HAS-UA fields.
```bash
curl -s http://127.0.0.1:8085/api/status | jq .
```

### `POST /api/set_band?band=<BAND_KEY>`
Updates the configured band for the secondary SDR and returns HTTP `200` with `{"status": "ok"}`. Use a key from `GNSS_BANDS`, such as one of the four listed above. Omitting `band` selects `GAL_E6`. An empty, unknown, or repeated `band` parameter returns HTTP `400` with an `error` field and leaves the configuration as it was.

```bash
# Switch secondary SDR to E5b in real time
curl -X POST "http://127.0.0.1:8085/api/set_band?band=GAL_E5B"
```

---

## 5. Troubleshooting & FAQ

### Port 8085 Already in Use
If port 8085 is occupied by another process, launch on an alternative port:
```bash
python3 trisat_sdr/main.py --web-port 8090
```
Or kill the existing process:
```bash
lsof -ti :8085 | xargs kill -9 2>/dev/null
```

### Accessing the Dashboard from Another Device on LAN
By default, the server binds to `0.0.0.0` (all interfaces). You can open the dashboard from an iPad, iPhone, or laptop on the same local Wi-Fi network by browsing to:
```text
http://<YOUR_MAC_IP_ADDRESS>:8085
```
*(Find your Mac's IP in System Settings $\rightarrow$ Network, or run `ipconfig getifaddr en0` in Terminal).*

### HackRF Hardware Not Detected
If physical HackRF SDRs are not connected via USB, TRISAT-SDR automatically operates in high-fidelity **Keplerian & Cryptographic Simulation Mode**, generating authentic raw Galileo I/NAV pages, valid CRC-24Q words, and HAS corrections so you can test all features offline.
