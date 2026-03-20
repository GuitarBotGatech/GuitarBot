// ═══════════════════════════════════════════════
// ANALYSIS
// ═══════════════════════════════════════════════
const HIT_DB_THRESHOLD  = -50;  // dBFS minimum to count as "hit"
const HIT_WINDOW_BEFORE = 0.1;  // beats before note onset to search
const HIT_WINDOW_AFTER  = 0.5;  // beats after note onset to search

function _setAnalyzeStatus(text, color) {
  const el = document.getElementById('analyze-status');
  if (!el) return;
  el.textContent = text;
  el.style.color = color || 'var(--text-dim)';
}

// ── Python-backend analysis (preferred) ─────────────────────────────────────

async function analyzeAllNotes() {
  if (S.audioWavB64) {
    await _analyzeViaPython();
  } else {
    _analyzeAllNotesJS();
  }
}

async function _analyzeViaPython() {
  if (!S.pluck.length) { _setAnalyzeStatus('No notes', '#ef4444'); return; }

  _setAnalyzeStatus('Analyzing…', 'var(--text-dim)');
  try {
    const payload = {
      audio_b64:      S.audioWavB64,
      events:         S.pluck,
      bpm:            S.bpm,
      time_sig:       S.timeSig,
      latency_ms:     S.latencyMs,
      rec_start_beat: S.recStartBeat,
    };
    const resp = await fetch('http://127.0.0.1:8765/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Analysis failed');

    S.noteAnalysis = data.noteAnalysis;

    if (data.spectrogram) {
      S.spectrogramFrames = data.spectrogram.frames;
      S.spectrogramParams = {
        source:     'python',
        midiMin:    data.spectrogram.midiMin,
        midiMax:    data.spectrogram.midiMax,
        hopSamples: data.spectrogram.hopSamples,
        sampleRate: data.spectrogram.sampleRate,
      };
      S.spectrogramVisible = true;
      const specBtn = document.getElementById('btn-spectrogram');
      if (specBtn) specBtn.classList.add('on');
    }

    const total = Object.keys(S.noteAnalysis).length;
    const hits  = Object.values(S.noteAnalysis).filter(a => a.hit).length;
    const color = hits === total ? '#22c55e' : hits === 0 ? '#ef4444' : '#f59e0b';
    _setAnalyzeStatus(`${hits}/${total} hit`, color);

    render();
    updateInspectorAnalysis();

  } catch (err) {
    console.error('analyzeAllNotes error:', err);
    _setAnalyzeStatus('Error: ' + err.message, '#ef4444');
  }
}

// ── JS fallback analysis (uses S.spectrogramFrames from old recorder) ────────

function _analyzeAllNotesJS() {
  try {
    const frames = S.spectrogramFrames;
    const params = S.spectrogramParams;

    if (!frames || !frames.length || !params) {
      _setAnalyzeStatus('No recording', '#ef4444');
      return;
    }

    if (!S.pluck.length) {
      _setAnalyzeStatus('No notes', '#ef4444');
      return;
    }

    const { fftSize, sampleRate, minBin } = params;
    const dataLen = frames[0].data.length;
    const latencyBeats = (S.latencyMs || 0) / (secondsPerBeat() * 1000);
    const result = {};

    for (const ev of S.pluck) {
      const noteBeat = parseBeat(ev.beat);
      const wStart = noteBeat + latencyBeats - HIT_WINDOW_BEFORE;
      const wEnd   = noteBeat + latencyBeats + HIT_WINDOW_AFTER;
      const wFrames = frames.filter(f => f.beat >= wStart && f.beat <= wEnd);

      if (!wFrames.length) {
        result[ev.id] = { hit: false, confidence: 0, peak: -Infinity, tremoloHz: null };
        continue;
      }

      const f0 = 440 * Math.pow(2, (ev.note - 69) / 12);
      const centerBin = Math.round(f0 * fftSize / sampleRate) - minBin;
      const lo = Math.max(0, centerBin - 1);
      const hi = Math.min(dataLen - 1, centerBin + 2);

      let peak = -Infinity;
      for (const fr of wFrames) {
        for (let b = lo; b <= hi; b++) {
          if (fr.data[b] > peak) peak = fr.data[b];
        }
      }

      const hit = peak > HIT_DB_THRESHOLD;
      const confidence = hit ? Math.min(1, (peak - HIT_DB_THRESHOLD) / 30) : 0;

      let tremoloHz = null;
      if (ev.duration_b > 0.5) {
        const durEnd = noteBeat + latencyBeats + ev.duration_b;
        const noteFrames = frames.filter(f => f.beat >= noteBeat + latencyBeats && f.beat <= durEnd);
        if (noteFrames.length >= 20) {
          tremoloHz = _measureTremoloRate(noteFrames, centerBin, dataLen);
        }
      }

      result[ev.id] = { hit, confidence, peak, tremoloHz };
    }

    S.noteAnalysis = result;

    const total = Object.keys(result).length;
    const hits  = Object.values(result).filter(a => a.hit).length;
    const color = hits === total ? '#22c55e' : hits === 0 ? '#ef4444' : '#f59e0b';
    _setAnalyzeStatus(`${hits}/${total} hit`, color);

    if (!S.spectrogramVisible && frames.length) {
      S.spectrogramVisible = true;
      const specBtn = document.getElementById('btn-spectrogram');
      if (specBtn) specBtn.classList.add('on');
    }

    render();
    updateInspectorAnalysis();

  } catch (err) {
    console.error('analyzeAllNotes error:', err);
    _setAnalyzeStatus('Error!', '#ef4444');
  }
}

function _measureTremoloRate(frames, bin, dataLen) {
  const lo = Math.max(0, bin - 1);
  const hi = Math.min(dataLen - 1, bin + 2);

  const envelope = frames.map(fr => {
    let sum = 0, count = 0;
    for (let b = lo; b <= hi; b++) {
      const lin = Math.pow(10, fr.data[b] / 20);
      sum += lin * lin;
      count++;
    }
    return count ? Math.sqrt(sum / count) : 0;
  });

  const maxAmp = Math.max(...envelope);
  if (maxAmp < 1e-10) return null;
  const norm = envelope.map(v => v / maxAmp - 0.5);

  const N = norm.length;
  const maxLag = Math.floor(N * 0.8);
  const acorr = new Float32Array(maxLag);
  for (let lag = 2; lag < maxLag; lag++) {
    let sum = 0;
    for (let i = 0; i < N - lag; i++) sum += norm[i] * norm[i + lag];
    acorr[lag] = sum / (N - lag);
  }

  let bestLag = -1, bestVal = 0.3;
  for (let lag = 3; lag < maxLag - 1; lag++) {
    if (acorr[lag] > acorr[lag - 1] && acorr[lag] > acorr[lag + 1] && acorr[lag] > bestVal) {
      bestVal = acorr[lag];
      bestLag = lag;
    }
  }

  if (bestLag < 0) return null;
  const hz = (1000 / 16) / bestLag;
  if (hz < 1 || hz > 20) return null;
  return Math.round(hz * 10) / 10;
}

function updateInspectorAnalysis() {
  const row   = document.getElementById('i-analysis-row');
  const hitEl = document.getElementById('i-hit-status');
  const tremEl = document.getElementById('i-tremolo-rate');
  if (!row || !hitEl || !tremEl) return;

  const selId = S.selPluck;
  if (selId == null || !Object.keys(S.noteAnalysis).length) {
    row.style.display = 'none';
    return;
  }

  const a = S.noteAnalysis[selId];
  if (!a) { row.style.display = 'none'; return; }

  row.style.display = '';
  hitEl.textContent = a.hit
    ? `Hit  (${Math.round(a.confidence * 100)}% conf)`
    : `Missed  (peak ${Math.round(a.peak)} dBFS)`;
  hitEl.style.color = a.hit ? '#22c55e' : '#ef4444';
  tremEl.textContent = a.tremoloHz != null ? `Tremolo: ${a.tremoloHz} Hz` : '';
}

// ── Analyze button binding ──
document.getElementById('btn-analyze').addEventListener('click', () => {
  analyzeAllNotes();
});
