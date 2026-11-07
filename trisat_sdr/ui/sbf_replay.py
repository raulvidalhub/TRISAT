"""Local browser viewer for a recorded Galileo I/NAV session."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ..sbf import gps_time_ms

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TRISAT · SBF replay</title>
<style>
  :root { color-scheme: dark; font: 16px system-ui, sans-serif; background: #101924; color: #eef5fb; }
  main { max-width: 44rem; margin: 3rem auto; padding: 0 1rem; }
  .source { color: #5eead4; font-weight: 700; }
  .controls { display: flex; flex-wrap: wrap; gap: .7rem; align-items: center; }
  button, select, input { font: inherit; padding: .35rem .65rem; }
  input { width: 6rem; }
  section { border: 1px solid #476074; border-radius: .65rem; padding: 1rem 1.3rem; margin-top: 1.5rem; }
  dt { color: #b6ccd9; margin-top: .6rem; } dd { margin: 0; }
  .signal-table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  .signal-table th, .signal-table td { padding: .35rem; border-bottom: 1px solid #476074; text-align: left; }
  .signal-table :is(th, td):nth-child(n+3) { text-align: right; }
  code { overflow-wrap: anywhere; }
</style>
<main>
  <div class="source">RECORDED RECEIVER DATA · REPLAY</div>
  <h1>Galileo I/NAV</h1>
  <p>Inspect pages in the order they were captured by the receiver.</p>
  <div class="controls">
    <label for="satellite">Satellite</label>
    <select id="satellite"><option value="">All Galileo satellites</option></select>
    <button id="previous" disabled>Previous</button>
    <button id="play" disabled>Play</button>
    <button id="next" disabled>Next</button>
    <button id="last" disabled>Last</button>
  </div>
  <form id="jump" class="controls">
    <label for="jump-page">Go to page</label>
    <input id="jump-page" type="number" min="1" step="1" required disabled>
    <button id="jump-submit" disabled>Go</button>
  </form>
  <p id="progress" role="status">Loading recording…</p>
  <section aria-label="Recorded navigation page">
    <dl>
      <dt>Satellite and signal</dt><dd id="signal">—</dd>
      <dt>Receiver timestamp</dt><dd id="timestamp">—</dd>
      <dt>Navigation CRC reported by receiver</dt><dd id="crc">—</dd>
      <dt>OSNMA on this page</dt><dd id="osnma">—</dd>
      <dt>Recorded page (234 bits)</dt><dd><code id="payload">—</code></dd>
    </dl>
  </section>
  <section id="signal-quality" hidden aria-labelledby="signal-quality-title">
    <h2 id="signal-quality-title">Galileo signal quality</h2>
    <p>Receiver-reported C/N₀ in dB-Hz, by satellite, band and antenna.</p>
    <p id="signal-quality-status"></p>
    <table class="signal-table" id="signal-quality-table" aria-label="Galileo C/N₀ measurements">
      <thead>
        <tr>
          <th scope="col">Satellite</th><th scope="col">Band</th>
          <th scope="col">Main</th><th scope="col">Aux1</th><th scope="col" id="signal-quality-aux2">Aux2</th>
        </tr>
      </thead>
      <tbody id="signal-quality-rows"></tbody>
    </table>
  </section>
  <section id="receiver-position" hidden aria-labelledby="position-title">
    <h2 id="position-title">Receiver-reported position</h2>
    <p>Recorded PVT solution from the receiver. OSNMA tag verification is shown separately.</p>
    <dl>
      <dt>Position solution</dt><dd id="position-solution"></dd>
      <dt>Latitude</dt><dd id="latitude"></dd>
      <dt>Longitude</dt><dd id="longitude"></dd>
      <dt>Ellipsoidal height</dt><dd id="position-height"></dd>
      <dt>Coordinate datum</dt><dd id="position-datum"></dd>
      <dt>Position sample</dt><dd id="position-sample"></dd>
    </dl>
  </section>
  <section id="antenna-attitude" hidden aria-labelledby="antenna-title">
    <h2 id="antenna-title">Receiver attitude and antennas</h2>
    <dl>
      <dt>Heading</dt><dd id="heading"></dd>
      <dt>Pitch</dt><dd id="pitch"></dd>
      <dt>Attitude solution</dt><dd id="attitude-solution"></dd>
      <dt>Attitude sample</dt><dd id="attitude-sample"></dd>
      <dt>Main–Aux1 separation</dt><dd id="separation"></dd>
      <dt>Baseline solution</dt><dd id="baseline-solution"></dd>
      <dt>Baseline sample</dt><dd id="baseline-sample"></dd>
    </dl>
  </section>
  <section id="verification" hidden aria-labelledby="verification-title">
    <h2 id="verification-title">OSNMA tag verification · Offline</h2>
    <p>OSNMAlib results for this satellite through the displayed point in the recording.</p>
    <dl>
      <dt>Verified tags</dt><dd id="verified-tags"></dd>
      <dt>Tags by data type</dt><dd id="verified-types"></dd>
      <dt>Subframe of latest verification</dt><dd id="verification-time"></dd>
    </dl>
    <p>Verification uses the timestamps in the capture. These results describe navigation tags. The page CRC is shown separately.</p>
  </section>
</main>
<script>
  const element = id => document.getElementById(id);
  const satelliteName = svid => 'E' + String(svid).padStart(2, '0');
  const satellite = element('satellite');
  const jumpPage = element('jump-page'), jumpSubmit = element('jump-submit');
  const previous = element('previous'), play = element('play'), next = element('next'), last = element('last');
  let index = 0, total = 0, timer, sequence = 0, playing = false;

  async function request(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error('Could not read the recording.');
    return response.json();
  }

  function pause() {
    playing = false;
    clearTimeout(timer);
    play.textContent = 'Play';
  }

  function showVerification(verification) {
    element('verification').hidden = !verification;
    if (!verification) return;
    element('verified-tags').textContent = verification.verified_tags ?
      String(verification.verified_tags) : 'None yet';
    element('verified-types').textContent = Object.entries(verification.by_adkd)
      .map(([adkd, count]) => 'ADKD ' + adkd + ': ' + count).join(' · ') || '—';
    const time = verification.processed_subframe;
    element('verification-time').textContent = time ?
      'Galileo week ' + time.galileo_week + ' · GST TOW ' + time.tow_s + ' s' : '—';
  }

  const solutionLabels = {
    fixed: 'Fixed ambiguities',
    float: 'Float ambiguities',
    insufficient_measurements: 'Insufficient measurements',
    not_requested: 'Attitude disabled on receiver',
    unavailable: 'No solution'
  };
  const positionLabels = {
    standalone: 'Standalone',
    differential: 'Differential',
    fixed_location: 'Fixed location',
    rtk_fixed: 'RTK fixed',
    rtk_float: 'RTK float',
    sbas: 'SBAS aided',
    moving_base_rtk_fixed: 'Moving-base RTK fixed',
    moving_base_rtk_float: 'Moving-base RTK float',
    ppp: 'Precise point positioning (PPP)',
    unavailable: 'No position solution',
    unknown: 'Unknown position mode'
  };

  function sampleTime(sample) {
    return 'GPS week ' + sample.gps_week + ' · TOW ' + (sample.tow_ms / 1000).toFixed(3) +
      ' s · ' + sample.age_ms + ' ms before this page';
  }

  function showSignalQuality(sample) {
    element('signal-quality').hidden = sample === undefined;
    if (sample === undefined) return;
    const selected = satellite.value;
    const signals = sample?.signals.filter(signal => !selected || signal.svid === Number(selected)) || [];
    let status = 'No recent measurement epoch';
    if (sample) {
      status = sampleTime(sample);
      if (sample.scrambled) status += ' · Measurements marked as scrambled by the receiver';
      else if (!signals.length) status += ' · No Galileo signals for this selection';
    }
    element('signal-quality-status').textContent = status;
    element('signal-quality-table').hidden = !signals.length;
    const showAux2 = signals.some(signal => signal.cn0_dbhz.aux2 != null);
    element('signal-quality-aux2').hidden = !showAux2;
    const antennas = showAux2 ? ['main', 'aux1', 'aux2'] : ['main', 'aux1'];
    const rows = signals.map(signal => {
      const row = document.createElement('tr');
      const levels = antennas.map(antenna => signal.cn0_dbhz[antenna]?.toFixed(2) ?? '—');
      for (const value of [satelliteName(signal.svid), signal.band, ...levels]) {
        row.insertCell().textContent = value;
      }
      return row;
    });
    element('signal-quality-rows').replaceChildren(...rows);
  }

  function showPosition(sample) {
    element('receiver-position').hidden = sample === undefined;
    if (sample === undefined) return;
    let solution = 'No recent sample';
    if (sample) {
      solution = positionLabels[sample.solution];
      if (sample.error_code) solution += ' (receiver error ' + sample.error_code + ')';
      if (sample.solution === 'unknown') solution += ' (' + sample.mode_code + ')';
      if (sample.dimensions) solution += ' · ' + sample.dimensions + 'D';
    }
    const degrees = value => value == null ? '—' : value.toFixed(6) + '°';
    const datum = sample?.datum_code;
    element('position-solution').textContent = solution;
    element('latitude').textContent = degrees(sample?.latitude_deg);
    element('longitude').textContent = degrees(sample?.longitude_deg);
    element('position-height').textContent = sample?.ellipsoidal_height_m == null ? '—' :
      sample.ellipsoidal_height_m.toFixed(2) + ' m';
    element('position-datum').textContent = datum == null ? '—' :
      datum === 0 ? 'WGS84/ITRS' : 'SBF datum ' + datum;
    element('position-sample').textContent = sample ? sampleTime(sample) : '—';
  }

  function showAttitude(motion) {
    element('antenna-attitude').hidden = !motion;
    if (!motion) return;
    const {attitude, baseline} = motion;
    const angle = value => value == null ? '—' : value.toFixed(2) + '°';
    const missing = 'No recent sample';
    element('heading').textContent = angle(attitude?.heading_deg);
    element('pitch').textContent = angle(attitude?.pitch_deg);
    element('attitude-solution').textContent = attitude ? solutionLabels[attitude.solution] : missing;
    element('attitude-sample').textContent = attitude ? sampleTime(attitude) : '—';
    element('separation').textContent = baseline?.distance_m == null ? '—' :
      (baseline.distance_m * 100).toFixed(1) + ' cm';
    element('baseline-solution').textContent = baseline ? solutionLabels[baseline.solution] : missing;
    element('baseline-sample').textContent = baseline ?
      (baseline.source === 'auxiliary' ? 'Auxiliary recording · ' : '') + sampleTime(baseline) : '—';
  }

  async function show(target) {
    const requestId = ++sequence;
    clearTimeout(timer);
    try {
      const query = new URLSearchParams({index: target, svid: satellite.value});
      const result = await request('/api/pages?' + query);
      if (requestId !== sequence) return;
      index = target;
      total = result.count;
      const frame = result.page;
      element('progress').textContent = 'Page ' + (index + 1) + ' of ' + total;
      element('signal').textContent = satelliteName(frame.svid) + ' · ' + frame.band;
      element('timestamp').textContent = 'GPS week ' + frame.gps_week + ' · TOW ' +
        (frame.tow_ms / 1000).toFixed(3) + ' s';
      element('crc').textContent = frame.navigation_crc_passed ? 'Passed' : 'Failed';
      element('osnma').textContent = frame.osnma_status === 'unverified' ?
        'Received I/NAV · Unverified' : 'Unavailable on this signal';
      element('payload').textContent = frame.payload_hex;
      showVerification(result.osnma_verification);
      showAttitude(result.antenna_attitude);
      showPosition(result.receiver_position);
      showSignalQuality(result.galileo_signal_quality);
      jumpPage.max = total;
      jumpPage.value = index + 1;
      jumpPage.disabled = jumpSubmit.disabled = false;
      previous.disabled = index === 0;
      next.disabled = index + 1 === total;
      last.disabled = next.disabled;
      play.disabled = total < 2;
      if (playing && !next.disabled) {
        timer = setTimeout(() => show(index + 1), Math.min(result.delay_ms, 2147483647));
      } else if (playing) {
        pause();
      }
    } catch (error) {
      if (requestId !== sequence) return;
      pause();
      element('progress').textContent = error.message;
    }
  }

  satellite.onchange = () => { pause(); show(0); };
  previous.onclick = () => { pause(); show(index - 1); };
  next.onclick = () => { pause(); show(index + 1); };
  last.onclick = () => { pause(); show(total - 1); };
  element('jump').onsubmit = event => {
    event.preventDefault();
    pause();
    show(jumpPage.valueAsNumber - 1);
  };
  play.onclick = () => {
    if (playing) {
      pause();
    } else {
      playing = true;
      play.textContent = 'Pause';
      show(index + 1 < total ? index : 0);
    }
  };

  request('/api/satellites').then(result => {
    for (const svid of result.satellites) {
      const option = document.createElement('option');
      option.value = svid;
      option.textContent = satelliteName(svid);
      satellite.appendChild(option);
    }
    show(0);
  }).catch(error => { element('progress').textContent = error.message; });
</script>
</html>
"""


def serve_replay(pages, port, verification=None, receiver=None):
    """Serve one selected capture over loopback."""
    by_satellite = {}
    for index, page in enumerate(pages):
        by_satellite.setdefault(str(page["svid"]), []).append(index)
    satellites = sorted(int(svid) for svid in by_satellite)
    all_indices = range(len(pages))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *args):
            pass

        def respond(self, status, content_type, body):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def respond_json(self, result, status=200):
            self.respond(status, "application/json", json.dumps(result).encode("utf-8"))

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/":
                self.respond(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
            elif url.path == "/api/satellites":
                result = {"satellites": satellites}
                if verification is not None:
                    result["full_recording_verified_tags"] = verification.totals()
                self.respond_json(result)
            elif url.path == "/api/pages":
                params = parse_qs(url.query)
                svid = params.get("svid", [""])[0]
                selected = by_satellite.get(svid, []) if svid else all_indices
                try:
                    index = int(params.get("index", ["0"])[0])
                    if not 0 <= index < len(selected):
                        raise ValueError
                except ValueError:
                    self.respond_json({"error": "Page or satellite not found"}, 400)
                    return

                capture_index = selected[index]
                page = pages[capture_index]
                delay_ms = 0
                if index + 1 < len(selected):
                    following = pages[selected[index + 1]]
                    delay_ms = max(0, gps_time_ms(following) - gps_time_ms(page))
                result = {"count": len(selected), "page": page, "delay_ms": delay_ms}
                if verification is not None:
                    result["osnma_verification"] = verification.at(capture_index, page["svid"])
                if receiver is not None:
                    result.update(receiver.at(page))
                self.respond_json(result)
            else:
                self.respond_json({"error": "Not found"}, 404)

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"SBF replay: http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()
