// ═══════════════════════════════════════════════
// TRANSPORT
// ═══════════════════════════════════════════════

// Mirrors tune.py constants exactly
const TREMOLO_DURATION_THRESHOLD=0.500; // seconds — matches tune.TREMOLO_DURATION_THRESHOLD
const PICKER_PLUCK_MOTION_POINTS=11;    // matches tune.PICKER_PLUCK_MOTION_POINTS
const ROBOT_TIME_STEP=0.005;            // matches tune.TIME_STEP

// Slide timing constants — mirrors tune.py LH prep-time parameters
const LH_PREP_TIME_MIN=0.090;           // matches tune.LH_PREP_TIME_MIN
const LH_PREP_TIME_MAX=0.450;           // matches tune.LH_PREP_TIME_BEFORE_PICK
const LH_PREP_MAX_SEMITONE_DELTA=9;     // matches tune.LH_PREP_MAX_SEMITONE_DELTA

// Replicates GuitarBotParser.interpPick tremolo period formula
function tremoloPickPeriodS(speed){
  const s=Math.min(10,Math.max(1,Math.round(speed)||6));
  const fillPts=Math.min(30,Math.floor(30-(s-1)*25/9))-4;
  return(fillPts+PICKER_PLUCK_MOTION_POINTS)*ROBOT_TIME_STEP;
}

// Replicates lh_interpolate phase-2 (slider motion) duration.
// Phase 2 is ~1/3 of total prep time; prep time scales with semitone distance.
function slidePhaseDurationS(semitones){
  const ratio=Math.min(1.0,Math.abs(semitones)/LH_PREP_MAX_SEMITONE_DELTA);
  const motionTime=LH_PREP_TIME_MIN+(LH_PREP_TIME_MAX-LH_PREP_TIME_MIN)*ratio;
  return motionTime/3;
}

const Synth={
  ctx:null,
  master:null,
  active:new Set(),        // items: { node, g, timerIds:[] }
  workletReady:false,
  // Tracks the last note fired on each string (index matches STRINGS array).
  // Used to determine the slide start pitch when slide=1.
  lastNoteByString:[null,null,null],

  async ensure(){
    if(!this.ctx){
      const AC=window.AudioContext||window.webkitAudioContext;
      if(!AC)return false;
      this.ctx=new AC();
      this.master=this.ctx.createGain();
      this.master.gain.value=0.22;
      this.master.connect(this.ctx.destination);
    }
    if(this.ctx.state==='suspended'){
      try{await this.ctx.resume();}catch(_e){}
    }
    if(!this.workletReady){
      try{
        await this.ctx.audioWorklet.addModule('js/karplus-processor.js');
        this.workletReady=true;
      }catch(e){
        console.warn('Karplus worklet failed to load, falling back to oscillator:',e);
      }
    }
    return this.ctx.state==='running';
  },

  midiToFreq(m){return 440*Math.pow(2,(m-69)/12)},

  // Returns the STRINGS index (0/1/2) for a given MIDI note, or -1 if out of range.
  _stringIndex(note){return STRINGS.findIndex(s=>note>=s.min&&note<=s.max)},

  // speed  : robot speed value 1–10
  // slide  : 1 if this note has the slide flag, 0 otherwise
  trigger(note,durS=0.2,vel=90,speed=6,slide=0){
    if(!this.ctx||!this.master)return;
    const now=this.ctx.currentTime;
    const freq=this.midiToFreq(note);
    const d=Math.max(0.05,durS);
    const amp=0.3+Math.min(1,Math.max(0,vel/127))*0.7;
    const isTremolo=d>=TREMOLO_DURATION_THRESHOLD;

    // ── Determine slide start pitch ──────────────────────────────────────
    const strIdx=this._stringIndex(note);
    const prevNote=(strIdx>=0)?this.lastNoteByString[strIdx]:null;
    const doSlide=!!(slide&&prevNote!==null&&prevNote!==note);
    const slideDurS=doSlide?slidePhaseDurationS(note-prevNote):0;

    // Update last-note tracker before any early returns
    if(strIdx>=0) this.lastNoteByString[strIdx]=note;

    if(this.workletReady){
      // ── Karplus-Strong string synthesis ──────────────────────────────
      // Lower notes get a slightly higher decay → longer sustain, like a real string
      const decay=Math.min(0.9998,0.996+(1-Math.min(1,freq/800))*0.003);

      const node=new AudioWorkletNode(this.ctx,'karplus-strong');
      const g=this.ctx.createGain();
      node.connect(g); g.connect(this.master);

      if(doSlide){
        // ── Slide: seed at previous note, glide to current ───────────────
        // Mirrors the robot's Phase 1 (hold) → Phase 2 (slide) → Phase 3 (press+pick).
        // The KS worklet starts at startFreq and continuously bends the delay line
        // length to reach targetFreq over slideDurS seconds.
        node.port.postMessage({
          type:'slide',
          startFrequency:this.midiToFreq(prevNote),
          targetFrequency:freq,
          durationS:slideDurS,
          decay,
        });
      }else{
        node.port.postMessage({type:'trigger',frequency:freq,decay});
      }

      const timerIds=[];

      if(isTremolo){
        // ── Tremolo: schedule repeated re-picks at the robot's computed rate ──
        const periodS=tremoloPickPeriodS(speed);
        const numPicks=Math.floor(d/periodS);
        for(let i=1;i<numPicks;i++){
          timerIds.push(setTimeout(()=>{
            node.port.postMessage({type:'trigger',frequency:freq,decay});
          },Math.round(i*periodS*1000)));
        }
        g.gain.setValueAtTime(amp,now);
        g.gain.setValueAtTime(amp,now+Math.max(0.01,d-0.05));
        g.gain.exponentialRampToValueAtTime(0.0001,now+d);
      }else{
        // ── Single pluck (or slide): natural KS decay ────────────────────
        const fadeStart=Math.max(now+0.01,now+d-0.05);
        g.gain.setValueAtTime(amp,now);
        g.gain.setValueAtTime(amp,fadeStart);
        g.gain.exponentialRampToValueAtTime(0.0001,now+d);
      }

      const item={node,g,timerIds,isWorklet:true};
      timerIds.push(setTimeout(()=>{
        node.port.postMessage({type:'stop'});
        try{node.disconnect();g.disconnect();}catch(_e){}
        this.active.delete(item);
      },(d+0.15)*1000));
      this.active.add(item);
      return item;

    }else{
      // ── Fallback: triangle oscillator with basic portamento ───────────
      const rel=Math.min(0.12,Math.max(0.03,d*0.45));
      const atk=0.005;
      const fallAmp=0.05+Math.min(1,Math.max(0,vel/127))*0.2;
      const osc=this.ctx.createOscillator();
      const g=this.ctx.createGain();
      osc.type='triangle';
      if(doSlide){
        osc.frequency.setValueAtTime(this.midiToFreq(prevNote),now);
        osc.frequency.linearRampToValueAtTime(freq,now+slideDurS);
      }else{
        osc.frequency.setValueAtTime(freq,now);
      }
      g.gain.setValueAtTime(0.0001,now);
      g.gain.exponentialRampToValueAtTime(fallAmp,now+atk);
      g.gain.setValueAtTime(fallAmp,now+Math.max(atk,d-rel));
      g.gain.exponentialRampToValueAtTime(0.0001,now+d);
      osc.connect(g); g.connect(this.master);
      osc.start(now); osc.stop(now+d+0.01);
      const item={node:osc,g,timerIds:[],isWorklet:false};
      osc.onended=()=>this.active.delete(item);
      this.active.add(item);
      return item;
    }
  },

  // Stop a specific voice previously returned from trigger().
  // Used by MIDI live-monitor to release a held note on note-off.
  release(item){
    if(!item||!this.active.has(item))return;
    try{
      const now=this.ctx?this.ctx.currentTime:0;
      item.g.gain.cancelScheduledValues(now);
      item.g.gain.setValueAtTime(item.g.gain.value,now);
      item.g.gain.exponentialRampToValueAtTime(0.0001,now+0.08);
      if(item.isWorklet){
        setTimeout(()=>{
          try{item.node.port.postMessage({type:'stop'});item.node.disconnect();item.g.disconnect();}catch(_e){}
        },100);
      }else{
        try{item.node.stop(now+0.1);}catch(_e){}
      }
    }catch(_e){}
    for(const tid of(item.timerIds||[]))clearTimeout(tid);
    this.active.delete(item);
  },

  stopAll(){
    for(const item of this.active){
      try{
        if(item.node.port) item.node.port.postMessage({type:'stop'});
        else item.node.stop();
        item.g.gain.cancelScheduledValues(0);
        item.g.gain.setValueAtTime(0,0);
        item.node.disconnect(); item.g.disconnect();
      }catch(_e){}
      for(const tid of(item.timerIds||[])) clearTimeout(tid);
    }
    this.active.clear();
    this.lastNoteByString=[null,null,null];
  }
};

function previewPluckEvent(ev){
  if(!S.notePreview||!ev)return;
  Synth.ensure();
  const bps=S.bpm/60;
  const durS=(ev.duration_b??0.5)/bps;
  Synth.trigger(ev.note,durS,speedToVelocity(ev.speed??6),ev.speed??6,ev.slide??0);
}

function triggerPluckEventsBetween(prevBeat,nextBeat){
  if(nextBeat<=prevBeat)return;
  const bps=S.bpm/60;
  for(const ev of S.pluck){
    const eb=parseBeat(ev.beat);
    if(eb>=prevBeat&&eb<nextBeat){
      const durS=(ev.duration_b??0.5)/bps;
      Synth.trigger(ev.note,durS,speedToVelocity(ev.speed),ev.speed??6,ev.slide??0);
    }
  }
}

let playIv=null, playT0=null, playB0=0;
let prevCycleKey=null; // tracks cycle identity to detect mid-playback moves

function setPlayheadBeat(beat){
  S.playBeat=clamp(normalizeBeat(beat),0,totalBeats());
  const m=bpm(), bar=Math.floor(S.playBeat/m)+1, b=Math.floor(S.playBeat%m)+1;
  document.getElementById('pos').textContent=`${bar}.${b}`;
  if(S.playing){
    playB0=S.playBeat;
    playT0=performance.now();
  }
}

document.getElementById('btn-play').addEventListener('click',()=>{
  if(S.playing)return;
  Synth.ensure();
  const cycleRange=getCycleRange();
  if(cycleRange&&(S.playBeat<cycleRange.startBeat||S.playBeat>=cycleRange.endBeat)){
    setPlayheadBeat(cycleRange.startBeat);
  }
  S.playing=true; playT0=performance.now(); playB0=S.playBeat;
  prevCycleKey=null;
  document.getElementById('btn-play').classList.add('on');
  playIv=setInterval(()=>{
    const prevBeat=S.playBeat;
    const bps=S.bpm/60;
    const elapsed=(performance.now()-playT0)/1000*bps;
    const cycle=getCycleRange();
    if(cycle){
      const len=cycle.endBeat-cycle.startBeat;
      const absoluteBeat=playB0+elapsed;
      const wrapped=cycle.startBeat+((((absoluteBeat-cycle.startBeat)%len)+len)%len);
      const cycleKey=cycle.startBeat+'_'+cycle.endBeat;
      const cycleChanged=prevCycleKey!==null&&prevCycleKey!==cycleKey;
      prevCycleKey=cycleKey;
      if(cycleChanged){
        // Cycle moved mid-playback: re-anchor so next tick is clean, skip notes this tick
        playT0=performance.now(); playB0=wrapped;
        S.playBeat=wrapped;
      }else if(wrapped<prevBeat){
        triggerPluckEventsBetween(prevBeat,cycle.endBeat);
        triggerPluckEventsBetween(cycle.startBeat,wrapped);
      }else{
        triggerPluckEventsBetween(prevBeat,wrapped);
      }
      S.playBeat=wrapped;
      const m=bpm(), bar=Math.floor(S.playBeat/m)+1, b=Math.floor(S.playBeat%m)+1;
      document.getElementById('pos').textContent=`${bar}.${b}`;
      render();
      return;
    }

    S.playBeat=playB0+elapsed;
    triggerPluckEventsBetween(prevBeat,S.playBeat);
    if(S.playBeat>=totalBeats()){stopPlay();return;}
    const m=bpm(), bar=Math.floor(S.playBeat/m)+1, b=Math.floor(S.playBeat%m)+1;
    document.getElementById('pos').textContent=`${bar}.${b}`;
    render();
  },16);
});

document.getElementById('btn-stop').addEventListener('click',stopPlay);
function stopPlay(){
  if(typeof MIDIInput!=='undefined'&&S.midiRecordingActive)MIDIInput.finalizeRecording();
  S.playing=false; clearInterval(playIv); playIv=null;
  Synth.stopAll();
  S.playBeat=0; document.getElementById('btn-play').classList.remove('on');
  document.getElementById('pos').textContent='1.1'; render();
}
