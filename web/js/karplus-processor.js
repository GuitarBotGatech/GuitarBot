// ═══════════════════════════════════════════════
// KARPLUS-STRONG AUDIO WORKLET PROCESSOR
// ═══════════════════════════════════════════════
// Runs in the audio rendering thread.
// Triggered via port message: { type:'trigger', frequency, decay }
// Stopped via port message:   { type:'stop' }

class KarplusStrongProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf    = null;  // circular delay line
    this._pos    = 0;
    this._decay  = 0.996;
    this._active = false;

    this.port.onmessage = ({ data }) => {
      if (data.type === 'trigger') {
        // Delay-line length sets pitch: N ≈ sampleRate / freq
        const N = Math.max(2, Math.round(sampleRate / data.frequency));
        this._buf = new Float32Array(N);
        // Seed with white noise burst
        for (let i = 0; i < N; i++) this._buf[i] = Math.random() * 2 - 1;
        this._pos    = 0;
        this._decay  = data.decay ?? 0.996;
        this._active = true;
      } else if (data.type === 'stop') {
        this._active = false;
        this._buf    = null;
      }
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    if (!out) return true;

    if (!this._active || !this._buf) {
      out.fill(0);
      return true;
    }

    const N     = this._buf.length;
    const decay = this._decay;

    for (let i = 0; i < out.length; i++) {
      const cur  = this._pos;
      const next = (cur + 1) % N;

      // Output current sample
      out[i] = this._buf[cur];

      // Averaging low-pass filter feeds back into the delay line
      this._buf[cur] = decay * 0.5 * (this._buf[cur] + this._buf[next]);

      this._pos = next;
    }

    return true; // keep processor alive
  }
}

registerProcessor('karplus-strong', KarplusStrongProcessor);
