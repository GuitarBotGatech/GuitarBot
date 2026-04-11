// ═══════════════════════════════════════════════
// KARPLUS-STRONG AUDIO WORKLET PROCESSOR
// ═══════════════════════════════════════════════
// Uses a single circular buffer with a fractional (linearly-interpolated)
// read pointer, so the delay length — and therefore pitch — can be changed
// smoothly without clicks.  This is what makes pitch glide / slide work.
//
// Messages accepted on this.port:
//   { type:'trigger', frequency, decay }
//       Seed delay line with white noise at the given frequency; start output.
//   { type:'slide', startFrequency, targetFrequency, durationS, decay }
//       Seed at startFrequency, then glide to targetFrequency over durationS
//       seconds.  Used for notes with slide=1.
//   { type:'stop' }
//       Silence the output.

class KarplusStrongProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    // Fixed buffer large enough for the lowest note (~20 Hz)
    this._size = Math.ceil(sampleRate / 20) + 8;
    this._buf  = new Float32Array(this._size);

    this._wp        = 0;      // write pointer (integer)
    this._delayLen  = 100.0;  // current fractional delay length (= sampleRate / freq)
    this._targetLen = 100.0;  // glide destination delay length
    this._glideSteps = 0;     // remaining samples over which to interpolate
    this._decay     = 0.996;
    this._active    = false;

    this.port.onmessage = ({ data }) => {
      switch (data.type) {

        case 'trigger': {
          const N = sampleRate / Math.max(20, data.frequency);
          this._decay     = data.decay ?? 0.996;
          this._delayLen  = N;
          this._targetLen = N;
          this._glideSteps = 0;
          this._seedNoise(N);
          this._active = true;
          break;
        }

        case 'slide': {
          // Seed at the starting pitch, then schedule a glide to the target pitch.
          // The caller should send this once; the worklet does the rest sample-by-sample.
          const startN  = sampleRate / Math.max(20, data.startFrequency);
          const targetN = sampleRate / Math.max(20, data.targetFrequency);
          this._decay      = data.decay ?? 0.996;
          this._delayLen   = startN;
          this._targetLen  = targetN;
          this._glideSteps = Math.max(1, Math.round(data.durationS * sampleRate));
          this._seedNoise(startN);
          this._active = true;
          break;
        }

        case 'stop':
          this._active = false;
          break;
      }
    };
  }

  // Fill the most recent ceil(N)+2 slots in the circular buffer with white noise.
  _seedNoise(N) {
    const count = Math.ceil(N) + 2;
    for (let i = 0; i < count; i++) {
      this._buf[(this._wp - i + this._size) % this._size] = Math.random() * 2 - 1;
    }
  }

  // Linear-interpolated fractional read from the circular buffer.
  _readAt(floatPos) {
    const wrapped = ((floatPos % this._size) + this._size) % this._size;
    const i0  = Math.floor(wrapped) % this._size;
    const frac = wrapped - Math.floor(wrapped);
    const i1  = (i0 + 1) % this._size;
    return this._buf[i0] * (1 - frac) + this._buf[i1] * frac;
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    if (!out) return true;

    if (!this._active) {
      out.fill(0);
      return true;
    }

    const size  = this._size;
    const decay = this._decay;

    for (let i = 0; i < out.length; i++) {

      // ── Glide: smoothly interpolate delay length toward target ──────────
      if (this._glideSteps > 0) {
        this._delayLen += (this._targetLen - this._delayLen) / this._glideSteps;
        this._glideSteps--;
      }

      const N  = this._delayLen;
      const wp = this._wp;

      // ── Fractional Karplus-Strong feedback ─────────────────────────────
      // Read the two adjacent samples used by the averaging low-pass filter.
      const r0 = this._readAt(wp - N);
      const r1 = this._readAt(wp - N - 1);

      out[i] = r0;

      // Low-pass (averaging) filter feeds back into the delay line.
      this._buf[wp] = decay * 0.5 * (r0 + r1);
      this._wp = (wp + 1) % size;
    }

    return true; // keep processor alive
  }
}

registerProcessor('karplus-strong', KarplusStrongProcessor);
