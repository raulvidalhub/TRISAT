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

# 3. Headless console mode streaming frames over UDP and TCP
python3 trisat_sdr/main.py --headless

# 4. Search acquisition Doppler up to 15 kHz on either side of zero
python3 trisat_sdr/main.py --doppler-max-hz 15000
```

---

The current SDR pipeline produces simulated navigation frames and positioning results. The dashboard, CLI and JSON telemetry identify them as simulated, and the OSNMA Annex A self-test is reported separately from any received-message verification. IQ-file input does not make downstream navigation results measured.

When using `SdrChannelConfig(driver="file", iq_file_path=..., iq_format=...)`, each stream reads a capture once from its first I/Q pair. Read sizes may vary. The last block can be shorter than requested, and later reads return an empty list. The reader discards an incomplete trailing pair and reports file access or format errors. Construct a new stream to replay from the beginning.

### Galileo E1-B acquisition from IQ

The PCPS search for `GAL_E1` uses the Galileo E1-B data component. For a file source it searches SVIDs 1–36 with the official 4092-chip memory codes. It correlates a 4 ms CBOC replica against 8 ms of complex IQ, so the search can find a complete symbol even if the input starts between symbol boundaries. It reports delay relative to the input window and Doppler on the configured search grid. A detection requires both a peak above the noise floor and a 3 dB margin over distinct code phases. If several codes pass, the search checks each weaker candidate again after subtracting fitted replicas of stronger detections from that same window. A candidate must still pass at a peak within one chip (rounded up to whole samples, modulo the code period) and one Doppler bin of its original peak. This reduces false locks from cross-correlation without consuming more of the recording. NumPy speeds up a full search.

Configure `ReceiverConfig.primary_sdr` with `driver="file"`, `band_id="GAL_E1"`, the capture's `iq_file_path`, `iq_format`, and `sample_rate_hz`. Call `TrisatSdrReceiver(config).initialize_acquisition()` and inspect the results with `acquired=True`. The capture must contain at least 8 ms of interleaved complex samples centered on 1575.42 MHz. Acquisition sensitivity, front-end filtering, clock error, and false alarms on live RF remain to be measured. The reported C/N₀ is a heuristic estimate. Live IQ streaming and downstream tracking and navigation are outside this acquisition validation.

For IQ file acquisition, set `ReceiverConfig(doppler_search_max_hz=15000)` before creating the receiver to search from −15 kHz to +15 kHz. The default half-width is 5 kHz and the default bin spacing is 250 Hz. A wider search tests more bins per window.

`dsp/C7_E1B.txt` is the unmodified E1-B attachment from Annex C of the Galileo OS SIS ICD, Issue 2.2, November 2025, © European Union 2025. See the original document's terms of use, disclaimers and Annex H in `EUSPA/PDFs/Galileo_OS_SIS_ICD_in_force.pdf`. [Galileo OS SIS ICD](https://www.gsc-europa.eu/sites/default/files/sites/all/files/Galileo_OS_SIS_ICD_in_force.pdf)

Run the hardware-free tests from the repository root with `python -m unittest trisat_sdr.tests.test_galileo_e1b_acquisition -v`. They check the Annex C attachment and generate IQ independently from the search code with known PRNs, delay, carrier Doppler, symbol polarity changes and seeded noise. The receiver test uses a raw float32 IQ file.

### Offline Galileo E1-B tracking

With NumPy installed, run the following command from the repository root on the [CTTC recording](https://gnss-sdr.org/my-first-fix/).

```powershell
python -m trisat_sdr.track_iq 'C:\path\to\2013_04_04_GNSS_SIGNAL_at_CTTC_SPAIN.dat' --sample-rate-hz 4000000 --iq-format int16 --doppler-max-hz 15000 --acquire-at 0 --acquire-at 0.024 --acquire-at 0.144 --csv 'cttc-tracking.csv'
```

`--acquire-at` defaults to the beginning of the recording. Repeat it to acquire more channels at known offsets. The CTTC offsets above are the first acquisition windows for E12 and E19, E20, and E11 respectively. Acquired channels are followed through contiguous IQ with a local CBOC delay search and a polarity-independent carrier frequency estimate. The tracker reports lock in 200 ms intervals using measured prompt power and carrier coherence. A final interval is reported when at least 100 ms of complete symbols remain. The summary gives total and longest continuous lock time, and the CSV records the sample boundaries and lock metrics for each interval.

The offline command reports code and carrier frequency tracking separately from the simulated dashboard. Decoding I/NAV, computing position and authenticating OSNMA from the tracked IQ are separate stages.

## 📡 Telemetry Bridge to TRISAT (`trisat_ios` / macOS / `trisat_android`)

`TRISAT-SDR` sends simulated frames and telemetry as JSON with `"source": "simulated"`. For a dedicated legacy test client, pass `--emit-legacy-simulation` to also send NMEA and custom navigation sentences. Legacy sentences have no provenance field, and GGA reports no real fix. Supported transports:
1. **UDP Server (`127.0.0.1:5005`)** and **TCP Server (`0.0.0.0:5006`)**
2. **POSIX virtual serial device (`PTY`) on macOS/Linux** can be allocated. Serial output is currently unavailable.
3. **Broadcast Frame Formats:**
   * `$GALINAV,<svid>,<wordType>,<hex30Bytes>,<osnmaHkroot><osnmaMack>*CS`
   * `$GALE6HAS,<svid>,<pageId>,<orbitCorrCm>,<hexPayload>*CS`
   * `$GALE5,<band>,<svid>,<pageType>,<hexPayload>*CS`
   * `$GNGGA`, `$GAGSV`, `$GPGSV`, and JSON objects compatible with the TRISAT BLE bridge.

The dashboard and `/api/status` separate generated lines from local socket writes. Each encoded line contributes to `bridge.messages_generated` and `bytes_generated` once. Each distinct UDP destination (the configured port and port 9090) or connected TCP client counts as one attempt. The `packets_sent` and `bytes_sent` totals count complete writes accepted by the local socket, summed across destinations. The `transports` breakdown reports attempts and accepted writes by channel. Delivery to the receiving application is unverified.

## Replay a Septentrio SBF capture

Open a local recording containing `GALRawINAV` blocks from the repository root:

```bash
python -m trisat_sdr.replay_sbf path/to/recording.sbf
```

Open the printed loopback URL, select a Galileo satellite, then play or step through its pages. Use `--port` to choose another port or `--jsonl` to export the same sequence as JSON lines. The viewer checks the SBF block CRC and displays the receiver-reported navigation CRC separately. It displays the recorded 234-bit pages and the GPS week/time of week. Only I/NAV is read into the viewer. The original recording remains local.

### Optional offline OSNMA verification

Install the dependencies of a local [OSNMAlib](https://github.com/Algafix/OSNMA) checkout into the Python environment used by TRISAT and make the checkout importable. This adapter was tested with Python 3.12 and OSNMAlib commit `25aa61de15ea0ffc0bf1bc62ff8214d5898e89e2`. Use trusted [Galileo key material](https://www.gsc-europa.eu/galileo/services/galileo-open-service-navigation-message-authentication-osnma/galileo-osnma-idd) appropriate to the date of the capture.

Example in PowerShell from the TRISAT checkout:

```powershell
$env:PYTHONPATH = 'C:\path\to\OSNMA'
python -m trisat_sdr.replay_sbf 'C:\path\to\recording.sbf' --merkle-tree 'C:\path\to\MerkleTree.xml' --public-key 'C:\path\to\PublicKey.xml'
```

Both XML files are required to enable verification. The viewer then shows verified-tag counts per target satellite, broken down by ADKD, as results become available in replay order. With `--jsonl`, the same result is included as `osnma_verification`. The verifier works offline and uses the capture timestamps. A verified tag applies to navigation data, while the CRC and position remain separate observations.
