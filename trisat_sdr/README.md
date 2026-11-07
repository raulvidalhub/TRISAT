# TRISAT-SDR — Multi-Band Software-Defined GNSS Receiver

`trisat_sdr/` is the cross-platform (**macOS, GNU/Linux, and Windows**) Software-Defined Radio (SDR) GNSS receiver of the **TRISAT** ecosystem, designed specifically to operate with **one or two synchronized HackRF One units** (as well as RTL-SDR, PlutoSDR, USRP via SoapySDR, or baseband IQ files) across the following bands:

* **Galileo E1B/C ($1575.42\text{ MHz}$, $\text{CBOC}(6,1,1/11)$):** PCPS acquisition, 5-correlator DLL/PLL tracking ($VE, E, P, L, VL$), **I/NAV** page demodulation ($250\text{ bps}$), **CRC-24Q** integrity verification, and extraction of the **40 cryptographic OSNMA bits (`HKROOT` + `MACK`)**.
* **Galileo E6B/C ($1278.75\text{ MHz}$, $\text{BPSK}(5)$):** **C/NAV** page demodulation ($1000\text{ sps}$) and extraction of **Galileo HAS (High Accuracy Service PPP)** centimeter-level orbit and clock corrections.
* **Galileo E5a ($1176.45\text{ MHz}$), E5b ($1207.14\text{ MHz}$), and E5 Full AltBOC(15,10) ($1191.795\text{ MHz}$):** Ionosphere-free ($\text{Iono-Free}$) dual-frequency combination with E1, alongside F/NAV and I/NAV demodulation.
* **GPS L1 C/A ($1575.42\text{ MHz}$, $\text{BPSK}(1)$):** Simultaneous acquisition and tracking on the same RF front-end as Galileo E1.

---

## 🔗 Dual-HackRF Hardware Interconnection (E1 + E6 / E5)

With **two HackRF One units**, you can simultaneously receive **Galileo E1 (OSNMA)** on the primary HackRF and **Galileo E6 (HAS)** or **Galileo E5** on the secondary HackRF while maintaining phase and clock coherence:

1. **Clock Synchronization (`10 MHz`):** Connect a short SMA coaxial cable from the **`CLKOUT`** port of **HackRF #0 (Master)** to the **`CLKIN`** port of **HackRF #1 (Slave)**.
2. **Active Antenna Powering (`Bias-T 3.3V`):** Connect your multi-band active GNSS antenna (L1/E1 + L5/E5 + E6) via an RF power splitter (with DC block on one branch) or use two active antennas. `TRISAT-SDR` automatically enables **Bias-T (`-b 1`)** on both HackRF units.

---

## 🚀 Running `TRISAT-SDR` (macOS / Linux / Windows)

No mandatory external dependencies are required to run (includes a pure Python radix-2 FFT engine and automatically accelerates with `NumPy`, `SoapySDR`, or `hackrf_transfer` when installed):

```bash
# 1. Start the Dual-SDR receiver + Interactive Web Dashboard (http://127.0.0.1:8085)
python3 trisat_sdr/main.py

# 2. Select the secondary HackRF band (GAL_E6, GAL_E5A, GAL_E5B, GAL_E5_ALTBOC)
python3 trisat_sdr/main.py --band2 GAL_E5_ALTBOC

# 3. Headless console mode streaming frames over UDP, TCP, and Virtual Serial Port
python3 trisat_sdr/main.py --headless
```

---

## 📡 Telemetry Bridge to TRISAT (`trisat_ios` / macOS / `trisat_android`)

`TRISAT-SDR` broadcasts all demodulated frames in real time across three simultaneous channels:
1. **UDP Server (`127.0.0.1:5005`)** and **TCP Server (`0.0.0.0:5006`)**
2. **POSIX Virtual Serial Port (`PTY`, e.g. `/dev/ttys004`) on macOS/Linux**, selectable directly from `MacSerialPortManager` within the native macOS/iOS app.
3. **Broadcast Frame Formats:**
   * `$GALINAV,<svid>,<wordType>,<hex30Bytes>,<osnmaHkroot><osnmaMack>*CS`
   * `$GALE6HAS,<svid>,<pageId>,<orbitCorrCm>,<hexPayload>*CS`
   * `$GALE5,<band>,<svid>,<pageType>,<hexPayload>*CS`
   * `$GNGGA`, `$GAGSV`, `$GPGSV`, and JSON objects compatible with the TRISAT BLE bridge.

## Replay a Septentrio SBF capture

Open a local recording containing `GALRawINAV` blocks from the repository root:

```bash
python -m trisat_sdr.replay_sbf path/to/recording.sbf
```

Open the printed loopback URL, select a Galileo satellite, then play, step through, or jump to a page. Use `--port` to choose another port or `--jsonl` to export the same sequence as JSON lines. The viewer checks the SBF block CRC and displays the receiver-reported navigation CRC separately. It displays the recorded 234-bit pages and the GPS week/time of week. The original recording remains local.

### Optional offline OSNMA verification

Install the dependencies of a local [OSNMAlib](https://github.com/Algafix/OSNMA) checkout into the Python environment used by TRISAT and make the checkout importable. This adapter was tested with Python 3.12 and OSNMAlib commit `25aa61de15ea0ffc0bf1bc62ff8214d5898e89e2`. Use trusted [Galileo key material](https://www.gsc-europa.eu/galileo/services/galileo-open-service-navigation-message-authentication-osnma/galileo-osnma-idd) appropriate to the date of the capture.

Example in PowerShell from the TRISAT checkout:

```powershell
$env:PYTHONPATH = 'C:\path\to\OSNMA'
python -m trisat_sdr.replay_sbf 'C:\path\to\recording.sbf' --merkle-tree 'C:\path\to\MerkleTree.xml' --public-key 'C:\path\to\PublicKey.xml'
```

Both XML files are required to enable verification. The viewer then shows verified-tag counts per target satellite, broken down by ADKD, as results become available in replay order. With `--jsonl`, the same result is included as `osnma_verification`. The verifier works offline and uses the capture timestamps. A verified tag applies to navigation data, while the CRC and position remain separate observations.

### Optional dual-antenna measurements

If the recording includes `AttEuler` or `AuxAntPositions`, the viewer shows the receiver's heading and pitch or its measured Main–Aux1 separation, along with each solution status and sample timestamp. If `AuxAntPositions` was logged separately, pass the synchronized auxiliary SBF from the same receiver and session. This uses the auxiliary file as the source for the baseline.

```powershell
python -m trisat_sdr.replay_sbf 'C:\path\to\recording.sbf' --baseline-file 'C:\path\to\auxiliary.sbf'
```

For each I/NAV page, the viewer uses the latest sample at or before the page's GPS timestamp, up to two seconds old. If no sample meets that condition, the viewer shows “No recent sample”. With `--jsonl`, the corresponding `antenna_attitude` object contains `attitude` and `baseline` entries, each of which can be `null`.

### Optional receiver-reported position

If the main recording includes `PVTGeodetic`, the viewer shows the receiver's latitude, longitude, ellipsoidal height, datum, and solution type. It uses the same two-second GPS timestamp window as the antenna measurements. A 2D fix displays latitude and longitude. A missing or invalid fix leaves the coordinates blank and shows the receiver error code when available.

For these recordings, `--jsonl` adds a `receiver_position` field with the matched sample or `null` when there is no recent sample. The export can include the recorded coordinates.

### Optional Galileo signal quality

If the main recording contains `MeasEpoch`, the viewer shows the receiver's Galileo C/N₀ in dB-Hz by satellite, band and antenna. The satellite selector also filters this table. For each page the viewer uses the most recent measurement epoch at or before that page, up to two seconds old. The table lists the bands present in that epoch and shows a dash for missing antenna values. A new epoch replaces the previous one, including when it has no usable measurements or the receiver marks it as scrambled.

For these recordings, `--jsonl` adds `galileo_signal_quality`, with the full matched Galileo epoch or `null` when there is no recent epoch. Each signal has a `cn0_dbhz` object keyed by the available antennas (`main`, `aux1`, `aux2`).

## Use a Mosaic-H over USB

Install `pyserial` and configure the receiver to output `PVTGeodetic`, `MeasEpoch`, and `GALRawINAV` over its USB serial interface. The live dashboard reads the configured port and writes checksum-validated SBF blocks to a new local file. In RxControl or the receiver web interface, use an available output stream and the USB connection that corresponds to your COM port.

```powershell
python -m pip install pyserial
python -m trisat_sdr.live_sbf --serial COM9 --capture session.sbf --seconds 30
python -m trisat_sdr.replay_sbf session.sbf
```

Open the local URL printed by `live_sbf`. The panel displays receiver position and Galileo C/N₀ from the main and Aux1 antennas, with the GPS timestamp of each sample. Values expire two seconds after receipt. Use Ctrl+C to finish a capture without a time limit. Run the replay command after the recording closes. OSNMA tag verification is available during replay with trusted key material.
