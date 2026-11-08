"""
Interactive Cross-Platform Web Dashboard for TRISAT-SDR.
Uses Python's standard `http.server` so it runs out-of-the-box on macOS,
GNU/Linux, and Windows without requiring external web server libraries.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlsplit

from ..config import GNSS_BANDS


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>TRISAT-SDR | Dual-HackRF Multi-Band GNSS Software Receiver</title>
<style>
  :root {
    --bg: #070b14;
    --card: #0f172a;
    --border: #1e293b;
    --cyan: #06b6d4;
    --green: #10b981;
    --amber: #f59e0b;
    --purple: #a855f7;
    --red: #ef4444;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    padding: 16px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 20px;
    background: linear-gradient(90deg, #0f172a, #0b2639);
    border: 1px solid var(--cyan);
    border-radius: 12px;
    margin-bottom: 16px;
  }
  .title-block h1 { font-size: 20px; letter-spacing: 0.5px; color: #38bdf8; }
  .title-block p { font-size: 12px; color: var(--muted); margin-top: 3px; }
  .badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
  }
  .badge-green { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; }
  .badge-cyan { background: rgba(6,182,212,0.2); color: #22d3ee; border: 1px solid #06b6d4; }
  .badge-amber { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #f59e0b; }
  .badge-purple { background: rgba(168,85,247,0.2); color: #c084fc; border: 1px solid #a855f7; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .grid-3 { display: grid; grid-template-columns: 1.2fr 1fr 1.2fr; gap: 16px; margin-bottom: 16px; }
  @media (max-width: 1100px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }

  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
  }
  .card h2 {
    font-size: 13px;
    text-transform: uppercase;
    color: #38bdf8;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .kv-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    padding: 4px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .kv-row span:first-child { color: var(--muted); }
  .kv-row span:last-child { font-weight: 600; }

  canvas {
    width: 100%;
    height: 125px;
    background: #050811;
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 8px;
  }
  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 8px;
  }
  select, button {
    background: #1e293b;
    color: var(--text);
    border: 1px solid var(--cyan);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
  }
  button:hover { background: #0e7490; }

  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #1e293b; }
  th { color: var(--muted); font-size: 11px; text-transform: uppercase; }

  .mono-box {
    background: #050811;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 10px;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 11px;
    height: 210px;
    overflow-y: auto;
    line-height: 1.5;
  }
  .cmd-line {
    background: #050811;
    padding: 6px 8px;
    border-radius: 6px;
    font-size: 10.5px;
    color: #34d399;
    margin-top: 6px;
    overflow-x: auto;
    white-space: nowrap;
  }
  #live-dashboard { display: none; }
  .live-sbf #live-dashboard { display: block; }
  .live-sbf #sdr-dashboard { display: none; }
  .live-table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  .live-table th, .live-table td { padding: .4rem; border-bottom: 1px solid #1e293b; text-align: left; }
</style>
</head>
<body>

<div id="live-dashboard">
  <header>
    <div class="title-block">
      <h1>TRISAT-SDR — Mosaic-H</h1>
      <p>Receiver data via Septentrio USB · Local SBF recording</p>
    </div>
    <span class="badge badge-cyan" id="live-state" role="status">WAITING FOR RECEIVER DATA</span>
  </header>
  <div class="grid-2">
    <section class="card" aria-labelledby="live-position-title">
      <h2 id="live-position-title">Receiver-reported position</h2>
      <div class="kv-row"><span>Position solution</span><span id="live-fix">—</span></div>
      <div class="kv-row"><span>Latitude / Longitude</span><span id="live-position">—</span></div>
      <div class="kv-row"><span>Ellipsoidal height</span><span id="live-height">—</span></div>
      <div class="kv-row"><span>Coordinate datum</span><span id="live-datum">—</span></div>
      <div class="kv-row"><span>Receiver timestamp</span><span id="live-position-time">—</span></div>
    </section>
    <section class="card" aria-labelledby="live-signals-title">
      <h2 id="live-signals-title">Galileo signal quality</h2>
      <div class="kv-row"><span>C/N₀ (dB-Hz)</span><span id="live-signals-time">—</span></div>
      <table class="live-table" aria-label="Live Galileo C/N₀ measurements">
        <thead><tr><th>Satellite</th><th>Band</th><th>Main</th><th>Aux1</th></tr></thead>
        <tbody id="live-signals"></tbody>
      </table>
    </section>
  </div>
</div>
<div id="sdr-dashboard">
<header>
  <div class="title-block">
    <h1>🛰️ TRISAT-SDR — Multi-Band GNSS Software Receiver</h1>
    <p>Portable SDR Baseband Engine (macOS · GNU/Linux · Windows) | Dual-HackRF Synchronized (E1 OSNMA + E5 AltBOC + E6 HAS)</p>
  </div>
  <div style="display:flex; gap:10px; align-items:center;">
    <span class="badge badge-amber">SIMULATED DATA</span>
    <span id="fixBadge" class="badge badge-cyan">INITIALIZING...</span>
    <span id="epochBadge" class="badge badge-cyan">EPOCH 0</span>
  </div>
</header>

<!-- Dual HackRF RF Front-End Section -->
<div class="grid-2">
  <div class="card">
    <h2>
      <span>📻 SDR #0 (Master Clock) — Galileo E1B/C + GPS L1</span>
      <span class="badge badge-cyan" id="sdr0Freq">1575.42 MHz</span>
    </h2>
    <div class="kv-row"><span>Hardware Device:</span><span id="sdr0Label">--</span></div>
    <div class="kv-row"><span>Modulation / Code:</span><span id="sdr0Mod">CBOC(6,1,1/11) + BPSK(1)</span></div>
    <div class="kv-row"><span>Sample Rate / Gains:</span><span id="sdr0Gains">--</span></div>
    <div class="kv-row"><span>Clock Sync & Bias-T (3.3V):</span><span id="sdr0Sync" style="color:#34d399;">CLKOUT MASTER (10 MHz) | BIAS-T ON</span></div>
    <div class="cmd-line" id="sdr0Cmd">hackrf_transfer ...</div>
    <canvas id="spec0Canvas" width="520" height="120"></canvas>
  </div>

  <div class="card">
    <h2>
      <span>📻 SDR #1 (Slave CLKIN Synced) — Secondary Band</span>
      <span class="badge badge-purple" id="sdr1Freq">1278.75 MHz</span>
    </h2>
    <div class="kv-row"><span>Hardware Device:</span><span id="sdr1Label">--</span></div>
    <div class="kv-row"><span>Modulation / Service:</span><span id="sdr1Mod">BPSK(5) — Galileo E6 HAS</span></div>
    <div class="kv-row"><span>Sample Rate / Gains:</span><span id="sdr1Gains">--</span></div>
    <div class="controls">
      <label style="font-size:12px; color:#94a3b8;">Retune HackRF #1 Band:</label>
      <select id="bandSelect" onchange="switchSecondaryBand()">
        <option value="GAL_E6">Galileo E6B/C (1278.75 MHz - HAS High Accuracy PPP)</option>
        <option value="GAL_E5A">Galileo E5a (1176.45 MHz - F/NAV Iono-Free)</option>
        <option value="GAL_E5B">Galileo E5b (1207.14 MHz - I/NAV Dual-Band)</option>
        <option value="GAL_E5_ALTBOC">Galileo E5 Full AltBOC(15,10) (1191.795 MHz - 20 MS/s)</option>
      </select>
    </div>
    <div class="cmd-line" id="sdr1Cmd">hackrf_transfer ...</div>
    <canvas id="spec1Canvas" width="520" height="120"></canvas>
  </div>
</div>

<!-- Middle Row: PVT + Correlator & IQ Constellation + Telemetry Bridge -->
<div class="grid-3">
  <div class="card">
    <h2>
      <span>📍 Multi-Band PVT & OSNMA / HAS Status</span>
      <span class="badge badge-green" id="pvtMode">E1 + E6 HAS</span>
    </h2>
    <div class="kv-row"><span>Latitude / Longitude:</span><span id="pvtLatLon" style="color:#38bdf8;">--</span></div>
    <div class="kv-row"><span>Altitude / Clock Bias:</span><span id="pvtAltClk">--</span></div>
    <div class="kv-row"><span>Estimated 2D / 1D Error:</span><span id="pvtAcc" style="color:#34d399;">--</span></div>
    <div class="kv-row"><span>DOP (GDOP / PDOP / HDOP):</span><span id="pvtDop">--</span></div>
    <div class="kv-row"><span>Galileo OSNMA Auth Sats:</span><span id="pvtOsnma" style="color:#22d3ee;">--</span></div>
    <div class="kv-row"><span>Galileo E6 HAS PPP Sats:</span><span id="pvtHas" style="color:#c084fc;">--</span></div>
  </div>

  <div class="card">
    <h2>
      <span>🎯 Multi-Correlator (VE,E,P,L,VL) & Costas I/Q</span>
      <span class="badge badge-amber" id="corrChLabel">CH 0</span>
    </h2>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
      <canvas id="corrCanvas" width="220" height="145" style="height:145px;"></canvas>
      <canvas id="iqCanvas" width="220" height="145" style="height:145px;"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>
      <span>🔗 TRISAT Telemetry Bridge (NMEA / $GALINAV / JSON)</span>
      <span class="badge badge-cyan" id="bridgeGenerated">0 generated</span>
    </h2>
    <div class="kv-row"><span>UDP Stream (iOS/Android/Mac):</span><span id="bridgeUdp" style="color:#34d399;">--</span></div>
    <div class="kv-row"><span>UDP local writes</span><span id="bridgeUdpWrites">--</span></div>
    <div class="kv-row"><span>TCP Server (Multi-client):</span><span id="bridgeTcp" style="color:#38bdf8;">--</span></div>
    <div class="kv-row"><span>TCP local writes</span><span id="bridgeTcpWrites">--</span></div>
    <div class="kv-row"><span>Serial output (PTY)</span><span id="bridgePty" style="color:#fbbf24;">--</span></div>
    <div style="color:var(--muted); margin-top:8px;">Recent generated NMEA</div>
    <div class="mono-box" id="nmeaBox" style="height:105px; margin-top:8px; color:#34d399;"></div>
  </div>
</div>

<!-- Bottom Row: DLL/PLL Tracking Channels & Raw Decoded Frames -->
<div class="grid-2">
  <div class="card">
    <h2><span>📡 Active Baseband DLL / PLL Tracking Channels</span></h2>
    <div style="max-height:220px; overflow-y:auto;">
      <table>
        <thead>
          <tr>
            <th>CH</th>
            <th>Band</th>
            <th>PRN/SVID</th>
            <th>C/N0 (dB-Hz)</th>
            <th>Doppler (Hz)</th>
            <th>Code Phase</th>
            <th>PLL Lock</th>
          </tr>
        </thead>
        <tbody id="trackTableBody"></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2><span>🔐 Demodulated Navigation Frames (I/NAV + OSNMA · E6 HAS · E5 · LNAV)</span></h2>
    <div class="mono-box" id="framesBox"></div>
  </div>
</div>

<!-- Security Suite Row: OSNMA Crypto + HAS-UA PPPSD + Galileo v2.2 Services -->
<div class="grid-3">
  <div class="card">
    <h2>
      <span>🛡️ Galileo OSNMA Cryptographic Engine</span>
      <span class="badge badge-amber" id="osnmaBadge">SIMULATED</span>
    </h2>
    <div class="kv-row"><span>NMA Status / Chain / CPKS:</span><span id="osnmaNmas" style="color:#34d399;">--</span></div>
    <div class="kv-row"><span>PKID / MACLT / Key & Tag:</span><span id="osnmaParams">--</span></div>
    <div class="kv-row"><span>Session authentication:</span><span id="osnmaEcdsa" style="color:#22d3ee;">--</span></div>
    <div class="kv-row"><span>Verified received keys / tags:</span><span id="osnmaTesla" style="color:#fbbf24;">--</span></div>
    <div class="kv-row"><span>Annex A Vector Test:</span><span id="osnmaAnnexA" style="color:#34d399;">--</span></div>
    <div class="cmd-line" id="osnmaKeyLine">KROOT: --</div>
  </div>

  <div class="card">
    <h2>
      <span>📐 Galileo HAS-UA (PP SEPVT + PPPSD EKF)</span>
      <span class="badge badge-purple" id="hasUaBadge">HAS SCENARIO</span>
    </h2>
    <div class="kv-row"><span>Pivot Satellites (Eq. 80):</span><span id="hasPivots" style="color:#c084fc;">--</span></div>
    <div class="kv-row"><span>Reed-Solomon RS(255,32) GF(2^8):</span><span id="hasRs">--</span></div>
    <div class="kv-row"><span>DIA Test (LOM F-test / Baarda w):</span><span id="hasDia" style="color:#34d399;">--</span></div>
    <div class="kv-row"><span>NTCM-G Iono VTEC / Tropo ZWD:</span><span id="hasAtm">--</span></div>
    <div class="kv-row"><span>GTRF 1-Sigma (Sx, Sy, Sz):</span><span id="hasSigma" style="color:#38bdf8;">--</span></div>
    <div class="cmd-line" id="hasSolLine">.sol (33-col): --</div>
  </div>

  <div class="card">
    <h2>
      <span>🚨 Galileo OS SIS v2.2 · EWSS-CAMF · TSM</span>
      <span class="badge badge-amber" id="galV22Badge">ICD v2.2</span>
    </h2>
    <div class="kv-row"><span>I/NAV WT16 RedCED (Fast TTFF):</span><span id="srvWt16" style="color:#34d399;">--</span></div>
    <div class="kv-row"><span>I/NAV WT17-20 RS(118,58) CED:</span><span id="srvRsCed">--</span></div>
    <div class="kv-row"><span>Secondary Sync Pattern (SSP):</span><span id="srvSsp" style="color:#22d3ee;">--</span></div>
    <div class="kv-row"><span>WT22 ARAIM ISM / WT44 TSM:</span><span id="srvIsmTsm">--</span></div>
    <div class="kv-row"><span>EWSS-CAMF (122b Geo-Ellipse):</span><span id="srvEwss" style="color:#fbbf24;">--</span></div>
    <div class="cmd-line" id="srvEwssHex">CAMF HEX: --</div>
  </div>
</div>

</div>
<script>
async function switchSecondaryBand() {
  const band = document.getElementById('bandSelect').value;
  await fetch('/api/set_band?band=' + encodeURIComponent(band), { method: 'POST' });
}

function drawSpectrum(canvasId, dbValues, strokeColor) {
  const c = document.getElementById(canvasId);
  if (!c || !dbValues || !dbValues.length) return;
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  for (let y = 20; y < h; y += 25) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < dbValues.length; i++) {
    const x = (i / (dbValues.length - 1)) * w;
    const norm = Math.min(1, Math.max(0, (dbValues[i] + 65) / 55));
    const y = h - 12 - norm * (h - 24);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function drawCorrelatorAndIQ(ch) {
  const cCorr = document.getElementById('corrCanvas');
  const cIq = document.getElementById('iqCanvas');
  if (!cCorr || !cIq || !ch) return;

  // 1. Draw 5-tap VE, E, P, L, VL Correlator Peak
  const ctx1 = cCorr.getContext('2d');
  const w1 = cCorr.width, h1 = cCorr.height;
  ctx1.clearRect(0, 0, w1, h1);
  const taps = ch.correlator_taps || [0.25, 0.55, 1.0, 0.55, 0.25];
  const labels = ['VE', 'E', 'P', 'L', 'VL'];
  ctx1.strokeStyle = '#22d3ee';
  ctx1.lineWidth = 2;
  ctx1.beginPath();
  for (let i = 0; i < taps.length; i++) {
    const x = 25 + (i / (taps.length - 1)) * (w1 - 50);
    const y = h1 - 24 - taps[i] * (h1 - 45);
    if (i === 0) ctx1.moveTo(x, y);
    else ctx1.lineTo(x, y);
  }
  ctx1.stroke();
  for (let i = 0; i < taps.length; i++) {
    const x = 25 + (i / (taps.length - 1)) * (w1 - 50);
    const y = h1 - 24 - taps[i] * (h1 - 45);
    ctx1.fillStyle = (i === 2) ? '#10b981' : '#38bdf8';
    ctx1.beginPath(); ctx1.arc(x, y, 4, 0, Math.PI * 2); ctx1.fill();
    ctx1.fillStyle = '#94a3b8';
    ctx1.font = '10px monospace';
    ctx1.fillText(labels[i], x - 6, h1 - 8);
  }

  // 2. Draw Costas Loop I/Q Prompt Diagram
  const ctx2 = cIq.getContext('2d');
  const w2 = cIq.width, h2 = cIq.height;
  ctx2.clearRect(0, 0, w2, h2);
  ctx2.strokeStyle = '#1e293b';
  ctx2.beginPath();
  ctx2.moveTo(w2/2, 0); ctx2.lineTo(w2/2, h2);
  ctx2.moveTo(0, h2/2); ctx2.lineTo(w2, h2/2);
  ctx2.stroke();

  const pts = ch.prompt_iq_history || [];
  for (let i = 0; i < pts.length; i++) {
    const px = w2/2 + pts[i][0] * (w2 * 0.32);
    const py = h2/2 - pts[i][1] * (h2 * 0.32);
    ctx2.fillStyle = '#fbbf24';
    ctx2.beginPath(); ctx2.arc(px, py, 3, 0, Math.PI * 2); ctx2.fill();
  }
}

function showLiveReceiver(data) {
  const set = (id, value) => { document.getElementById(id).textContent = value; };
  const time = sample => sample ? 'GPS week ' + sample.gps_week + ' · TOW ' +
    (sample.tow_ms / 1000).toFixed(3) + ' s' : '—';
  const states = {
    receiving: 'MOSAIC-H LIVE', waiting: 'WAITING FOR RECEIVER DATA',
    stale: 'NO RECENT RECEIVER DATA', disconnected: 'RECEIVER DASHBOARD DISCONNECTED'
  };
  set('live-state', states[data.stream_state]);
  const position = data.receiver_position;
  let fix = position?.solution.replaceAll('_', ' ') ?? '—';
  if (position?.dimensions) fix += ' · ' + position.dimensions + 'D';
  if (position?.error_code) fix += ' (receiver error ' + position.error_code + ')';
  set('live-fix', fix);
  set('live-position', position?.latitude_deg == null ? '—' :
    position.latitude_deg.toFixed(6) + '°, ' + position.longitude_deg.toFixed(6) + '°');
  set('live-height', position?.ellipsoidal_height_m == null ? '—' :
    position.ellipsoidal_height_m.toFixed(2) + ' m');
  const datum = position?.datum_code;
  set('live-datum', datum == null ? '—' : datum === 0 ? 'WGS84/ITRS' : 'SBF datum ' + datum);
  set('live-position-time', time(position));

  const quality = data.galileo_signal_quality;
  let qualityTime = time(quality);
  if (quality?.scrambled) qualityTime += ' · Receiver marked measurements as scrambled';
  set('live-signals-time', qualityTime);
  const rows = (quality?.signals ?? []).map(signal => {
    const row = document.createElement('tr');
    const satellite = 'E' + String(signal.svid).padStart(2, '0');
    const values = [satellite, signal.band, signal.cn0_dbhz.main?.toFixed(2) ?? '—',
      signal.cn0_dbhz.aux1?.toFixed(2) ?? '—'];
    for (const value of values) row.insertCell().textContent = value;
    return row;
  });
  document.getElementById('live-signals').replaceChildren(...rows);
}

async function pollStatus() {
  const live = document.body.classList.contains('live-sbf');
  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('Dashboard status unavailable');
    const data = await res.json();
    if (live) {
      showLiveReceiver(data);
      return;
    }

    document.getElementById('epochBadge').textContent = 'EPOCH ' + data.epoch;

    const p0 = data.primary_sdr;
    document.getElementById('sdr0Label').textContent = p0.label;
    document.getElementById('sdr0Freq').textContent = p0.center_freq_mhz + ' MHz';
    document.getElementById('sdr0Mod').textContent = p0.modulation + ' + GPS L1';
    document.getElementById('sdr0Gains').textContent = p0.sample_rate_msps + ' MS/s | LNA ' + p0.lna_gain_db + ' dB | VGA ' + p0.vga_gain_db + ' dB';
    document.getElementById('sdr0Cmd').textContent = '$ ' + p0.cli_cmd;
    drawSpectrum('spec0Canvas', p0.spectrum_db, '#06b6d4');

    const p1 = data.secondary_sdr;
    document.getElementById('sdr1Label').textContent = p1.label;
    document.getElementById('sdr1Freq').textContent = p1.center_freq_mhz + ' MHz';
    document.getElementById('sdr1Mod').textContent = p1.band_name + ' (' + p1.modulation + ')';
    document.getElementById('sdr1Gains').textContent = p1.sample_rate_msps + ' MS/s | LNA ' + p1.lna_gain_db + ' dB | VGA ' + p1.vga_gain_db + ' dB';
    document.getElementById('sdr1Cmd').textContent = '$ ' + p1.cli_cmd;
    drawSpectrum('spec1Canvas', p1.spectrum_db, '#a855f7');

    if (data.pvt) {
      const pvt = data.pvt;
      document.getElementById('fixBadge').textContent = pvt.valid_fix ? 'SIMULATED FIX' : 'SIMULATED ACQUISITION';
      document.getElementById('pvtMode').textContent = pvt.solution_mode;
      document.getElementById('pvtLatLon').textContent = pvt.latitude_deg.toFixed(6) + '°, ' + pvt.longitude_deg.toFixed(6) + '°';
      document.getElementById('pvtAltClk').textContent = pvt.altitude_m.toFixed(1) + ' m | ' + pvt.clock_bias_ns.toFixed(1) + ' ns';
      document.getElementById('pvtAcc').textContent = '±' + pvt.horizontal_accuracy_m.toFixed(2) + ' m (2D) / ±' + pvt.vertical_accuracy_m.toFixed(2) + ' m (1D)';
      document.getElementById('pvtDop').textContent = pvt.gdop + ' / ' + pvt.pdop + ' / ' + pvt.hdop;
      document.getElementById('pvtOsnma').textContent = 'Simulated OSNMA';
      document.getElementById('pvtHas').textContent = pvt.has_corrected_sats + ' Sats Corrected (E6 C/NAV)';
    }

    const br = data.bridge;
    document.getElementById('bridgeGenerated').textContent = br.messages_generated + ' generated';
    document.getElementById('bridgeUdp').textContent = 'udp://' + br.udp_target;
    document.getElementById('bridgeTcp').textContent = 'tcp://' + br.tcp_listen + ' (' + br.tcp_clients + ' clients)';
    for (const [transport, elementId] of [['udp', 'bridgeUdpWrites'], ['tcp', 'bridgeTcpWrites']]) {
      const stats = br.transports[transport];
      document.getElementById(elementId).textContent =
        stats.packets_sent + ' accepted / ' + stats.attempts + ' attempted (' + stats.bytes_sent + ' B)';
    }
    document.getElementById('bridgePty').textContent = br.pty_serial_device === 'N/A'
      ? 'Unavailable' : br.pty_serial_device + ' (output unavailable)';
    document.getElementById('nmeaBox').innerHTML = (br.recent_nmea || []).map(l => '<div>' + l + '</div>').join('');

    const chs = data.tracking_channels || [];
    if (chs.length > 0) {
      document.getElementById('corrChLabel').textContent = chs[0].band_id + ' PRN ' + chs[0].svid;
      drawCorrelatorAndIQ(chs[0]);
    }
    const tbody = document.getElementById('trackTableBody');
    tbody.innerHTML = chs.map(c => `
      <tr>
        <td>#${c.channel_id}</td>
        <td><span class="badge ${c.band_id.includes('E6') ? 'badge-purple' : (c.band_id.includes('E5') ? 'badge-amber' : 'badge-cyan')}">${c.band_id}</span></td>
        <td><b>${c.constellation === 'GALILEO' ? 'E' : 'G'}${String(c.svid).padStart(2,'0')}</b></td>
        <td style="color:#34d399; font-weight:700;">${c.cn0_dbhz.toFixed(1)}</td>
        <td>${c.carrier_doppler_hz.toFixed(1)}</td>
        <td>${c.code_phase_chips.toFixed(1)} chips</td>
        <td>${c.locked ? '🔒 LOCKED (' + c.pll_lock_indicator.toFixed(2) + ')' : 'SEARCH'}</td>
      </tr>
    `).join('');

    const frms = data.decoded_frames || [];
    document.getElementById('framesBox').innerHTML = frms.map(f => {
      let extra = '';
      if (f.osnma_hkroot_hex) {
        extra = ` <span style="color:#22d3ee;">[OSNMA HKROOT:${f.osnma_hkroot_hex} MACK:${f.osnma_mack_hex}]</span>`;
      } else if (f.frame_type === 'CNAV_E6_HAS') {
        extra = ` <span style="color:#c084fc;">[HAS dR: ${f.has_orbit_corr_cm} cm]</span>`;
      }
      return `<div style="margin-bottom:6px; border-bottom:1px solid #1e293b; padding-bottom:4px;">
        <span style="color:#fbbf24; font-weight:bold;">[${f.frame_type}]</span>
        <b>SV${String(f.svid).padStart(2,'0')}</b> Word/Page:${f.word_or_page_id}
        CRC24Q:<span style="color:#34d399;">${f.crc24q_hex}✓</span>${extra}<br/>
        <span style="color:#94a3b8;">HEX: ${f.hex_payload.substring(0, 60)}</span>
      </div>`;
    }).join('');

    if (data.osnma) {
      const o = data.osnma;
      document.getElementById('osnmaNmas').textContent = o.nmas_status + ' | CID=' + o.cid + ' | ' + o.cpks_status;
      document.getElementById('osnmaParams').textContent = 'PKID=' + o.pkid + ' | MACLT=' + o.maclt_id + ' | KS=' + o.key_size_bits + 'b TS=' + o.tag_size_bits + 'b';
      document.getElementById('osnmaEcdsa').textContent = 'No received OSNMA verification';
      document.getElementById('osnmaTesla').textContent = o.verified_keys_count + ' Keys / ' + o.verified_tags_count + ' Tags (SVs: ' + (o.authenticated_svids || []).join(',') + ')';
      document.getElementById('osnmaAnnexA').textContent = o.annex_a_selftest_passed ? '✓ PASSED (E02 WN=1248 MACSEQ=0xB08)' : 'FAILED';
      document.getElementById('osnmaKeyLine').textContent = 'Test vector KROOT: ' + o.latest_kroot_hex + ' | K_I: ' + o.latest_tesla_key_hex;
    }

    if (data.has_ua) {
      const h = data.has_ua;
      document.getElementById('hasPivots').textContent = 'Galileo E' + String(h.galileo_pivot_svid).padStart(2,'0') + ' | GPS G' + String(h.gps_pivot_svid).padStart(2,'0');
      document.getElementById('hasRs').textContent = h.rs_pages_accumulated + ' pages (' + h.rs_messages_decoded + ' MT1 decoded)';
      document.getElementById('hasDia').textContent = 'LOM=' + h.lom_test_statistic.toFixed(2) + ' | max|w|=' + h.max_baarda_w_test.toFixed(2) + ' (No Outliers)';
      document.getElementById('hasAtm').textContent = 'VTEC=' + h.ntcmg_vtec_tecu.toFixed(1) + ' TECU | ZWD=' + h.zwd_troposphere_m.toFixed(3) + ' m';
      document.getElementById('hasSigma').textContent = '±(' + h.sigma_xyz_m[0].toFixed(3) + ', ' + h.sigma_xyz_m[1].toFixed(3) + ', ' + h.sigma_xyz_m[2].toFixed(3) + ') m';
      document.getElementById('hasSolLine').textContent = '.sol: ' + h.sol_line_33col;
    }

    if (data.galileo_services) {
      const g = data.galileo_services;
      document.getElementById('srvWt16').textContent = g.wt16_redced_active ? 'ACTIVE (TTFF ' + g.wt16_ttff_sec + 's)' : 'INACTIVE';
      document.getElementById('srvRsCed').textContent = g.rs_ced_words_collected + '/8 Words -> Full CED Reconstructed';
      document.getElementById('srvSsp').textContent = g.current_ssp_id;
      document.getElementById('srvIsmTsm').textContent = 'WT22: SL3 SoL | WT44: SL2 (<=100ns)';
      const ew = g.ewss_alert;
      document.getElementById('srvEwss').textContent = ew.message_type + ' | ' + ew.severity + ' (' + ew.semi_major_km + 'x' + ew.semi_minor_km + 'km)';
      document.getElementById('srvEwssHex').textContent = 'CAMF 122b: ' + ew.camf_122bit_hex + ' [InZone: ' + ew.receiver_inside_alert_zone + ']';
    }
  } catch (e) {
    if (live) showLiveReceiver({stream_state: 'disconnected'});
  }
}

setInterval(pollStatus, 600);
pollStatus();
</script>
</body>
</html>
"""


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class TrisatWebDashboardServer:
    """Embedded HTTP Server serving the TRISAT-SDR Dashboard and JSON API."""

    def __init__(self, receiver, host: str = "127.0.0.1", port: int = 8085, *, live_sbf=False):
        self.receiver = receiver
        self.host = "127.0.0.1" if live_sbf else host
        self.port = port
        self.live_sbf = live_sbf
        self._httpd: ThreadingHTTPServer = None  # type: ignore
        self._mirror_httpd: ThreadingHTTPServer = None  # type: ignore

    def start(self, background: bool = True) -> str:
        receiver_ref = self.receiver
        live_sbf = self.live_sbf
        page = DASHBOARD_HTML
        if live_sbf:
            page = page.replace("<body>", '<body class="live-sbf">', 1)
            page = page.replace(
                "<title>TRISAT-SDR | Dual-HackRF Multi-Band GNSS Software Receiver</title>",
                "<title>TRISAT-SDR | Mosaic-H live</title>",
                1,
            )

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                pass  # Suppress noisy console access logs

            def respond(self, status, body, content_type, *, cors=False, no_store=False):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                if cors:
                    self.send_header("Access-Control-Allow-Origin", "*")
                if no_store:
                    self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def respond_json(self, status, payload, *, cors=False, no_store=False):
                body = json.dumps(payload).encode("utf-8")
                self.respond(status, body, "application/json", cors=cors, no_store=no_store)

            def do_GET(self):
                if live_sbf:
                    host = self.headers.get("Host", "").partition(":")[0].lower()
                    if host not in ("127.0.0.1", "localhost"):
                        self.send_error(403)
                        return
                path = urlsplit(self.path).path
                if path == "/":
                    self.respond(200, page.encode("utf-8"), "text/html; charset=utf-8")
                elif path == "/api/status":
                    self.respond_json(200, receiver_ref.get_status_snapshot(), cors=not live_sbf, no_store=live_sbf)
                else:
                    self.respond_json(404, {"error": "Route not found"})

            def do_POST(self):
                if live_sbf:
                    self.send_error(405)
                    return
                parsed = urlsplit(self.path)
                if parsed.path != "/api/set_band":
                    self.respond_json(404, {"error": "Route not found"})
                    return

                bands = parse_qs(parsed.query, keep_blank_values=True).get("band", ["GAL_E6"])
                if len(bands) != 1 or bands[0] not in GNSS_BANDS:
                    self.respond_json(400, {"error": "Provide one valid band key"})
                    return

                receiver_ref.switch_secondary_band(bands[0], dual_enabled=True)
                self.respond_json(200, {"status": "ok"})

        self._httpd = ReusableThreadingHTTPServer((self.host, self.port), Handler)
        mirror_port = 8080 if self.port != 8080 else 8085
        if not live_sbf:
            # Also mirror on port 8080 if primary port is 8085 (or vice versa).
            try:
                self._mirror_httpd = ReusableThreadingHTTPServer((self.host, mirror_port), Handler)
                threading.Thread(target=self._mirror_httpd.serve_forever, daemon=True).start()
            except OSError:
                self._mirror_httpd = None

        if background:
            threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        else:
            self._httpd.serve_forever()
        if live_sbf:
            return f"http://{self.host}:{self._httpd.server_port}/"
        return f"http://{self.host}:{self.port} (and http://{self.host}:{mirror_port})"

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._mirror_httpd:
            self._mirror_httpd.shutdown()
            self._mirror_httpd.server_close()
