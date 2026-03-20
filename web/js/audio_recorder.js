// ═══════════════════════════════════════════════
// AUDIO RECORDER  (MediaRecorder → WAV → Python)
// ═══════════════════════════════════════════════

function _setRecStatus(text, color) {
  const el = document.getElementById('analyze-status');
  if (!el) return;
  el.textContent = text;
  el.style.color = color || 'var(--text-dim)';
}

const LATENCY_STORAGE_KEY = 'guitarbot_latency_config_v1';
const LEGACY_LATENCY_STORAGE_KEY = 'guitarbot_latency_ms';
const CAL_EVENT_TIME_S = 0.55;
const CAL_CAPTURE_MS = 2200;
const CAL_LONG_EVENT_TIMES_S = [0.55, 2.8, 5.1, 7.4, 9.7];
const CAL_LONG_CAPTURE_MS = 12500;
const CAL_NOTE = 40; // open low E

function _syncLatencyInputs() {
  const baseInput = document.getElementById('set-latency-ms');
  const driftInput = document.getElementById('set-latency-drift');
  if (baseInput) baseInput.value = Math.round(S.latencyMs || 0);
  if (driftInput) driftInput.value = (Math.round((S.latencyDriftMsPerMin || 0) * 10) / 10).toString();
}

function _applyLatencyConfig(baseMs, driftMsPerMin, persist = true) {
  const base = Math.max(0, Math.round(parseFloat(baseMs) || 0));
  const drift = Math.round((parseFloat(driftMsPerMin) || 0) * 10) / 10;
  S.latencyMs = base;
  S.latencyDriftMsPerMin = drift;
  _syncLatencyInputs();
  if (persist) {
    try {
      localStorage.setItem(LATENCY_STORAGE_KEY, JSON.stringify({ baseMs: base, driftMsPerMin: drift }));
      localStorage.setItem(LEGACY_LATENCY_STORAGE_KEY, String(base));
    } catch (_e) {}
  }
  if (S.spectrogramVisible) render();
}

function _loadLatencyMs() {
  let base = null;
  let drift = 0;
  try {
    const raw = localStorage.getItem(LATENCY_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Number.isFinite(parseFloat(parsed?.baseMs))) base = parseFloat(parsed.baseMs);
      if (Number.isFinite(parseFloat(parsed?.driftMsPerMin))) drift = parseFloat(parsed.driftMsPerMin);
    }
  } catch (_e) {}

  if (base === null) {
    try {
      const legacy = parseFloat(localStorage.getItem(LEGACY_LATENCY_STORAGE_KEY));
      if (Number.isFinite(legacy)) base = legacy;
    } catch (_e) {}
  }

  if (base === null) base = 80;
  _applyLatencyConfig(base, drift, false);
}

const AR = (() => {
  let capturing = false;
  let calibrating = false;
  let mediaRecorder = null;
  let chunks = [];
  let recStartBeat = 0;
  let stream = null;

  async function start(_beat) {
    if (capturing) return;

    // Try to upload song to the bot — proceed with recording even if upload fails
    try {
      const ok = await uploadToBot();
      if (!ok) {
        if (!confirm('Upload to bot failed. Record anyway (mic only)?')) return;
      }
    } catch (_e) {
      if (!confirm('Bot server unreachable. Record anyway (mic only)?')) return;
    }

    // Ensure AudioContext exists (needed later for decodeAudioData)
    await Synth.ensure();
    const actx = Synth.ctx;
    if (!actx) { alert('Audio context unavailable.'); return; }

    // Require HTTPS or localhost for getUserMedia
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert(
        'Microphone API not available.\n\n'
        + 'Serve the page over HTTPS or localhost.\n'
        + 'File:// URLs cannot access the microphone.'
      );
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
        video: false,
      });
    } catch (e) {
      alert('Microphone access denied: ' + e.message);
      return;
    }

    chunks = [];
    let effectiveStartBeat = S.playBeat;
    const cycleRange = getCycleRange();
    if (!S.playing && cycleRange && (effectiveStartBeat < cycleRange.startBeat || effectiveStartBeat >= cycleRange.endBeat)) {
      effectiveStartBeat = cycleRange.startBeat;
      if (typeof setPlayheadBeat === 'function') {
        setPlayheadBeat(effectiveStartBeat);
      } else {
        S.playBeat = effectiveStartBeat;
      }
    }
    recStartBeat = effectiveStartBeat;

    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
    mediaRecorder.onstop = () => {
      if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
      _processRecording(actx, recStartBeat);
    };
    mediaRecorder.start(100); // collect a chunk every 100 ms

    capturing = true;
    S.recordingActive = true;
    S.recStartBeat = recStartBeat;
    _updateBtn();

    // Start sequencer playback so the playhead advances
    if (!S.playing) {
      document.getElementById('btn-play').click();
    }
  }

  function stop() {
    if (!capturing) return;
    capturing = false;
    S.recordingActive = false;

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop(); // triggers onstop → _processRecording
    }
    stopPlay();
    _updateBtn();
    render();
  }

  function _setCalibrating(active) {
    const btn = document.getElementById('btn-calibrate-latency');
    if (!btn) return;
    btn.classList.toggle('active', active);
    btn.disabled = active;
    btn.title = active ? 'Calibrating latency…' : 'Calibrate latency';
  }

  async function _captureCalibrationWavB64(actx, eventTimesSec, captureMs) {
    const localStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      video: false,
    });

    return await new Promise((resolve, reject) => {
      const localChunks = [];
      const recorder = new MediaRecorder(localStream);
      recorder.ondataavailable = e => { if (e.data.size > 0) localChunks.push(e.data); };
      recorder.onerror = e => reject(e.error || new Error('MediaRecorder error'));
      recorder.onstop = async () => {
        try {
          localStream.getTracks().forEach(t => t.stop());
          const blob = new Blob(localChunks, { type: localChunks[0]?.type || 'audio/webm' });
          const arrayBuf = await blob.arrayBuffer();
          const audioBuf = await actx.decodeAudioData(arrayBuf);
          const wavBuf = _encodeWav(audioBuf);
          resolve(_arrayBufToBase64(wavBuf));
        } catch (err) {
          reject(err);
        }
      };

      recorder.start(100);
      setTimeout(async () => {
        try { await fetch('http://127.0.0.1:8765/reset', { method: 'POST' }); } catch (_e) {}
        try {
          const calEvents = eventTimesSec.map(ts => ({
            note: CAL_NOTE,
            duration_s: 0.12,
            speed: 8,
            slide: 0,
            string_index: 0,
            timestamp: ts,
          }));
          await fetch('http://127.0.0.1:8765/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              song: {
                name: 'Latency Calibration',
                meta: {
                  key: 'E minor',
                  time_signature: S.timeSig,
                  bpm: S.bpm,
                  tempo_curve: [{ time: 0.0, bpm: S.bpm }],
                },
                tracks: [{ name: 'pluck_main', type: 'pluck', events: calEvents }],
              },
            }),
          });
        } catch (_e) {
          // Let analysis fail with a useful message if upload endpoint is unavailable.
        }
      }, 120);

      setTimeout(() => {
        if (recorder.state !== 'inactive') recorder.stop();
      }, captureMs);
    });
  }

  function _estimateLatencyMs(frames, midiMin, secondsPerBeatVal, targetSec) {
    if (!Array.isArray(frames) || !frames.length) return null;
    const noteIdx = CAL_NOTE - (Number.isFinite(midiMin) ? midiMin : MIDI_MIN);
    if (noteIdx < 0) return null;

    const windowStart = targetSec - 0.05;
    const windowEnd = targetSec + 1.6;
    const candidates = [];
    for (const frame of frames) {
      const tSec = (parseFloat(frame.beat) || 0) * secondsPerBeatVal;
      if (tSec < windowStart || tSec > windowEnd) continue;
      if (!Array.isArray(frame.data) || noteIdx >= frame.data.length) continue;
      candidates.push({ tSec, db: parseFloat(frame.data[noteIdx]) || -200 });
    }
    if (!candidates.length) return null;

    let peakDb = -Infinity;
    let peakT = candidates[0].tSec;
    for (const c of candidates) {
      if (c.db > peakDb) {
        peakDb = c.db;
        peakT = c.tSec;
      }
    }

    const onsetThreshold = Math.max(-55, peakDb - 10);
    const onset = candidates.find(c => c.tSec >= targetSec - 0.02 && c.db >= onsetThreshold);
    const detectedSec = onset ? onset.tSec : peakT;
    const latencyMs = Math.max(0, (detectedSec - targetSec) * 1000);
    return Math.round(latencyMs);
  }

  function _fitLatencyDrift(eventTimesSec, latencyMsValues) {
    const n = Math.min(eventTimesSec.length, latencyMsValues.length);
    if (n < 2) return null;
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
    for (let i = 0; i < n; i++) {
      const x = eventTimesSec[i];
      const y = latencyMsValues[i];
      sumX += x; sumY += y; sumXY += x * y; sumXX += x * x;
    }
    const denom = (n * sumXX) - (sumX * sumX);
    if (Math.abs(denom) < 1e-9) return null;
    const slopeMsPerSec = ((n * sumXY) - (sumX * sumY)) / denom;
    const interceptMs = (sumY - slopeMsPerSec * sumX) / n;
    return {
      baseMs: Math.max(0, Math.round(interceptMs)),
      driftMsPerMin: Math.round((slopeMsPerSec * 60) * 10) / 10,
    };
  }

  async function _runCalibration(eventTimesSec, captureMs, isLong) {
    if (capturing || calibrating) return;
    calibrating = true;
    _setCalibrating(true);
    _setRecStatus(isLong ? 'Long calibration…' : 'Quick calibration…', 'var(--text-dim)');

    try {
      await Synth.ensure();
      const actx = Synth.ctx;
      if (!actx) throw new Error('Audio context unavailable');

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone API unavailable (use localhost/https)');
      }

      const wavB64 = await _captureCalibrationWavB64(actx, eventTimesSec, captureMs);
      const events = eventTimesSec.map((ts, idx) => ({
        id: `latency-cal-${idx}`,
        note: CAL_NOTE,
        beat: `~${trimBeatNumber(ts / Math.max(1e-6, secondsPerBeat()))}`,
        duration_b: 0.25,
        speed: 8,
        slide: 0,
      }));
      const analysisPayload = {
        audio_b64: wavB64,
        events,
        bpm: S.bpm,
        time_sig: S.timeSig,
        latency_ms: 0,
        latency_drift_ms_per_min: 0,
        rec_start_beat: 0,
      };

      const resp = await fetch('http://127.0.0.1:8765/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(analysisPayload),
      });
      const data = await resp.json().catch(() => ({ ok: false, error: 'Invalid analysis response' }));
      if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP ${resp.status}`);

      const spb = secondsPerBeat();
      const estimates = [];
      for (const ts of eventTimesSec) {
        const est = _estimateLatencyMs(data.spectrogram?.frames || [], data.spectrogram?.midiMin, spb, ts);
        if (Number.isFinite(est)) estimates.push(est);
      }
      if (!estimates.length) throw new Error('Could not detect pluck onset (check input level)');

      if (isLong) {
        if (estimates.length < 3) throw new Error('Long calibration needs at least 3 detected pings');
        const fit = _fitLatencyDrift(eventTimesSec.slice(0, estimates.length), estimates);
        if (!fit) throw new Error('Could not fit latency drift');
        _applyLatencyConfig(fit.baseMs, fit.driftMsPerMin, true);
        _setRecStatus(`Latency: ${fit.baseMs} ms, drift: ${fit.driftMsPerMin} ms/min`, '#22c55e');
      } else {
        const estimate = estimates[0];
        _applyLatencyConfig(estimate, S.latencyDriftMsPerMin, true);
        _setRecStatus(`Latency calibrated: ${estimate} ms`, '#22c55e');
      }
    } catch (err) {
      console.error('Latency calibration failed:', err);
      _setRecStatus(`Calibration failed: ${err.message}`, '#ef4444');
    } finally {
      calibrating = false;
      _setCalibrating(false);
    }
  }

  async function calibrateLatencyQuick() {
    await _runCalibration([CAL_EVENT_TIME_S], CAL_CAPTURE_MS, false);
  }

  async function calibrateLatencyLong() {
    await _runCalibration(CAL_LONG_EVENT_TIMES_S, CAL_LONG_CAPTURE_MS, true);
  }

  async function _processRecording(actx, startBeat) {
    _setRecStatus('Processing…', 'var(--text-dim)');
    try {
      const blob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
      chunks = [];
      const arrayBuf = await blob.arrayBuffer();
      const audioBuf = await actx.decodeAudioData(arrayBuf);
      const wavBuf = _encodeWav(audioBuf);
      S.audioWavB64 = _arrayBufToBase64(wavBuf);
      S.recStartBeat = startBeat;
      _setRecStatus('Encoded — analyzing…', 'var(--text-dim)');
      // Auto-analyze with Python backend
      if (typeof analyzeAllNotes === 'function') analyzeAllNotes();
    } catch (err) {
      console.error('Audio processing failed:', err);
      _setRecStatus('Encode error', '#ef4444');
    }
  }

  // ── WAV encoding helpers ──────────────────────

  function _encodeWav(audioBuffer) {
    const sr = audioBuffer.sampleRate;
    const samples = audioBuffer.numberOfChannels > 1
      ? _mixdownToMono(audioBuffer)
      : audioBuffer.getChannelData(0);
    const numSamples = samples.length;
    const dataSize = numSamples * 2; // 16-bit mono
    const buf = new ArrayBuffer(44 + dataSize);
    const v = new DataView(buf);
    _writeStr(v, 0, 'RIFF');
    v.setUint32(4, 36 + dataSize, true);
    _writeStr(v, 8, 'WAVE');
    _writeStr(v, 12, 'fmt ');
    v.setUint32(16, 16, true);      // PCM chunk size
    v.setUint16(20, 1, true);       // PCM format
    v.setUint16(22, 1, true);       // mono
    v.setUint32(24, sr, true);
    v.setUint32(28, sr * 2, true);  // byte rate
    v.setUint16(32, 2, true);       // block align
    v.setUint16(34, 16, true);      // bits per sample
    _writeStr(v, 36, 'data');
    v.setUint32(40, dataSize, true);
    let offset = 44;
    for (let i = 0; i < numSamples; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }
    return buf;
  }

  function _mixdownToMono(audioBuffer) {
    const len = audioBuffer.length;
    const out = new Float32Array(len);
    for (let ch = 0; ch < audioBuffer.numberOfChannels; ch++) {
      const data = audioBuffer.getChannelData(ch);
      for (let i = 0; i < len; i++) out[i] += data[i];
    }
    for (let i = 0; i < len; i++) out[i] /= audioBuffer.numberOfChannels;
    return out;
  }

  function _writeStr(view, offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  }

  function _arrayBufToBase64(buf) {
    const bytes = new Uint8Array(buf);
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  function isCapturing() { return capturing; }

  function _updateBtn() {
    const btn = document.getElementById('btn-record');
    if (!btn) return;
    btn.classList.toggle('active', capturing);
    btn.title = capturing ? 'Stop recording' : 'Upload to bot + record audio';
  }

  return { start, stop, isCapturing, calibrateLatencyQuick, calibrateLatencyLong };
})();

// ── Record button binding ──
document.getElementById('btn-record').addEventListener('click', () => {
  if (AR.isCapturing()) {
    AR.stop();
  } else {
    AR.start(S.playBeat).catch(err => {
      console.error('Recording failed:', err);
      _setRecStatus('Rec error', '#ef4444');
    });
  }
});

document.getElementById('btn-calibrate-latency-quick').addEventListener('click', () => {
  AR.calibrateLatencyQuick();
});

document.getElementById('btn-calibrate-latency-long').addEventListener('click', () => {
  AR.calibrateLatencyLong();
});

// ── Latency settings input bindings ──
document.getElementById('set-latency-ms').addEventListener('input', e => {
  _applyLatencyConfig(e.target.value, S.latencyDriftMsPerMin, true);
});
document.getElementById('set-latency-drift').addEventListener('input', e => {
  _applyLatencyConfig(S.latencyMs, e.target.value, true);
});

_loadLatencyMs();
