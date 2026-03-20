// ═══════════════════════════════════════════════
// SPECTROGRAM
// ═══════════════════════════════════════════════

// Precomputed dB→color lookup table (128 stops, −80…−20 dBFS)
const _specColorLUT = (() => {
  const lut = [];
  for (let i = 0; i < 128; i++) {
    const t = i / 127;
    let r, g, b;
    if (t < 0.25) {
      const f = t / 0.25;
      r = 0; g = 0; b = Math.round(120 + f * 135);
    } else if (t < 0.5) {
      const f = (t - 0.25) / 0.25;
      r = 0; g = Math.round(f * 220); b = Math.round(255 - f * 255);
    } else if (t < 0.75) {
      const f = (t - 0.5) / 0.25;
      r = Math.round(f * 255); g = 220; b = 0;
    } else {
      const f = (t - 0.75) / 0.25;
      r = 255; g = Math.round(220 - f * 220); b = 0;
    }
    lut.push(`rgb(${r},${g},${b})`);
  }
  return lut;
})();

function _dbToColor(db) {
  const idx = Math.round(Math.max(0, Math.min(127, (db + 80) / 60 * 127)));
  return _specColorLUT[idx];
}

// Cache note→frequency-bin mapping (recomputed only when params change)
let _specBinCache = null;
let _specBinCacheKey = null;

function _getNoteBinCache(params) {
  const key = `${params.fftSize},${params.sampleRate},${params.minBin}`;
  if (_specBinCacheKey === key) return _specBinCache;
  const cache = {};
  for (let n = MIDI_MIN; n <= MIDI_MAX; n++) {
    const f = 440 * Math.pow(2, (n - 69) / 12);
    cache[n] = Math.round(f * params.fftSize / params.sampleRate) - params.minBin;
  }
  _specBinCache = cache;
  _specBinCacheKey = key;
  return cache;
}

function drawSpectrogram() {
  const frames = S.spectrogramFrames;
  const params = S.spectrogramParams;
  if (!frames || !frames.length || !params) return;

  const isPython = params.source === 'python';
  const bps = S.bpm / 60;

  // Frame width in pixels: use actual hop size for Python, 16ms intervals for browser
  let frameBeats;
  if (isPython && params.hopSamples && params.sampleRate) {
    frameBeats = (params.hopSamples / params.sampleRate) * bps;
  } else {
    frameBeats = 0.016 * bps; // browser 16ms intervals
  }
  const frameW = Math.max(1, Math.ceil(S.zoom * frameBeats) + 1);

  const binCache = isPython ? null : _getNoteBinCache(params);
  const dataLen = frames[0].data.length;
  // Python frames: latency already baked in. Browser frames: shift left by latency.
  const latencyBeats = isPython ? 0 : (S.latencyMs || 0) / (secondsPerBeat() * 1000);

  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, CHORD_H, CW - LABEL_W, rollH());
  ctx.clip();
  ctx.globalAlpha = 0.62;

  for (const frame of frames) {
    const x = beatToX(frame.beat - latencyBeats);
    if (x + frameW < LABEL_W || x > CW) continue;

    for (let n = MIDI_MIN; n <= MIDI_MAX; n++) {
      let db;
      if (isPython) {
        db = frame.data[n - MIDI_MIN];
      } else {
        const bin = binCache[n];
        if (bin < 0 || bin >= dataLen) continue;
        db = frame.data[bin];
      }
      ctx.fillStyle = _dbToColor(db);
      ctx.fillRect(x, noteToY(n) + 1, frameW, noteH - 2);
    }
  }

  ctx.globalAlpha = 1;
  ctx.restore();
}

function drawNoteAnalysisOverlay() {
  const analysis = S.noteAnalysis;
  if (!analysis || !Object.keys(analysis).length) return;

  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, 0, CW - LABEL_W, canvasH());
  ctx.clip();

  for (const ev of S.pluck) {
    const a = analysis[ev.id];
    if (!a) continue;
    const b = parseBeat(ev.beat);
    const x = beatToX(b);
    const y = noteToY(ev.note);
    const w = Math.max(8, ev.duration_b * S.zoom);
    if (x + w < LABEL_W || x > CW) continue;

    // Colored outline around the entire note block (green = hit, red = missed)
    const color = a.hit ? '#22c55e' : '#ef4444';
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.globalAlpha = 0.95;
    ctx.strokeRect(Math.max(LABEL_W, x), y, Math.min(CW, x + w) - Math.max(LABEL_W, x), noteH);
    ctx.globalAlpha = 1;

    // Badge circle with ✓ or ✗
    const r = Math.min(7, noteH / 2 - 1);
    const bx = x + r + 2, by = y + noteH / 2;
    ctx.beginPath();
    ctx.arc(bx, by, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 0.8;
    ctx.stroke();

    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.8;
    if (a.hit) {
      ctx.beginPath();
      ctx.moveTo(bx - r * 0.4, by);
      ctx.lineTo(bx - r * 0.05, by + r * 0.4);
      ctx.lineTo(bx + r * 0.5, by - r * 0.4);
      ctx.stroke();
    } else {
      const d = r * 0.35;
      ctx.beginPath(); ctx.moveTo(bx - d, by - d); ctx.lineTo(bx + d, by + d); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(bx + d, by - d); ctx.lineTo(bx - d, by + d); ctx.stroke();
    }
  }

  ctx.restore();
}

// ── Spectrogram & clear-recording button bindings ──
document.getElementById('btn-spectrogram').addEventListener('click', () => {
  S.spectrogramVisible = !S.spectrogramVisible;
  document.getElementById('btn-spectrogram').classList.toggle('on', S.spectrogramVisible);
  render();
});
document.getElementById('btn-clear-recording').addEventListener('click', () => {
  S.spectrogramFrames = [];
  S.spectrogramParams = null;
  S.noteAnalysis = {};
  S.audioWavB64 = null;
  S.recStartBeat = 0;
  const statusEl = document.getElementById('analyze-status');
  if (statusEl) statusEl.textContent = '';
  render();
  if (typeof updateInspectorAnalysis === 'function') updateInspectorAnalysis();
});
