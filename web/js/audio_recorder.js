// ═══════════════════════════════════════════════
// AUDIO RECORDER  (MediaRecorder → WAV → Python)
// ═══════════════════════════════════════════════

function _setRecStatus(text, color) {
  const el = document.getElementById('analyze-status');
  if (!el) return;
  el.textContent = text;
  el.style.color = color || 'var(--text-dim)';
}

const AR = (() => {
  let capturing = false;
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

  return { start, stop, isCapturing };
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

// ── Latency input binding ──
document.getElementById('rec-latency').addEventListener('input', e => {
  S.latencyMs = Math.max(0, parseFloat(e.target.value) || 0);
  if (S.spectrogramVisible) render();
});
