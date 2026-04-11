// ═══════════════════════════════════════════════
// TRANSPORT
// ═══════════════════════════════════════════════

// Mirrors tune.py constants exactly
const TREMOLO_DURATION_THRESHOLD=0.500; // seconds — matches tune.TREMOLO_DURATION_THRESHOLD
const PICKER_PLUCK_MOTION_POINTS=11;    // matches tune.PICKER_PLUCK_MOTION_POINTS
const ROBOT_TIME_STEP=0.005;            // matches tune.TIME_STEP

// Replicates GuitarBotParser.interpPick tremolo period formula
function tremoloPickPeriodS(speed){
  const s=Math.min(10,Math.max(1,Math.round(speed)||6));
  const fillPts=Math.min(30,Math.floor(30-(s-1)*25/9))-4;
  return(fillPts+PICKER_PLUCK_MOTION_POINTS)*ROBOT_TIME_STEP;
}

const Synth={
  ctx:null,
  master:null,
  active:new Set(),        // items: { node, g, timerIds:[] }
  workletReady:false,

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

  // speed: robot speed value 1-10 (matches ev.speed in pluck events)
  trigger(note,durS=0.2,vel=90,speed=6){
    if(!this.ctx||!this.master)return;
    const now=this.ctx.currentTime;
    const freq=this.midiToFreq(note);
    const d=Math.max(0.05,durS);
    const amp=0.3+Math.min(1,Math.max(0,vel/127))*0.7;
    const isTremolo=d>=TREMOLO_DURATION_THRESHOLD;

    if(this.workletReady){
      // ── Karplus-Strong string synthesis ──────────────────
      // Lower notes get a slightly higher decay → longer sustain, like a real string
      const decay=Math.min(0.9998,0.996+(1-Math.min(1,freq/800))*0.003);

      const node=new AudioWorkletNode(this.ctx,'karplus-strong');
      const g=this.ctx.createGain();
      node.connect(g); g.connect(this.master);

      // Initial pick
      node.port.postMessage({type:'trigger',frequency:freq,decay});

      const timerIds=[];

      if(isTremolo){
        // ── Tremolo: schedule repeated re-picks at the robot's computed rate ──
        // Each re-trigger re-seeds the KS delay line → re-attack on each pick stroke
        const periodS=tremoloPickPeriodS(speed);
        const numPicks=Math.floor(d/periodS);
        for(let i=1;i<numPicks;i++){
          timerIds.push(setTimeout(()=>{
            node.port.postMessage({type:'trigger',frequency:freq,decay});
          },Math.round(i*periodS*1000)));
        }
        // Flat gain for the full duration, short fade at the end
        g.gain.setValueAtTime(amp,now);
        g.gain.setValueAtTime(amp,now+Math.max(0.01,d-0.05));
        g.gain.exponentialRampToValueAtTime(0.0001,now+d);
      }else{
        // ── Single pluck: natural KS decay ───────────────────
        const fadeStart=Math.max(now+0.01,now+d-0.05);
        g.gain.setValueAtTime(amp,now);
        g.gain.setValueAtTime(amp,fadeStart);
        g.gain.exponentialRampToValueAtTime(0.0001,now+d);
      }

      const item={node,g,timerIds};
      timerIds.push(setTimeout(()=>{
        node.port.postMessage({type:'stop'});
        try{node.disconnect();g.disconnect();}catch(_e){}
        this.active.delete(item);
      },(d+0.15)*1000));
      this.active.add(item);

    }else{
      // ── Fallback: triangle oscillator ────────────────────
      const rel=Math.min(0.12,Math.max(0.03,d*0.45));
      const atk=0.005;
      const fallAmp=0.05+Math.min(1,Math.max(0,vel/127))*0.2;
      const osc=this.ctx.createOscillator();
      const g=this.ctx.createGain();
      osc.type='triangle';
      osc.frequency.setValueAtTime(freq,now);
      g.gain.setValueAtTime(0.0001,now);
      g.gain.exponentialRampToValueAtTime(fallAmp,now+atk);
      g.gain.setValueAtTime(fallAmp,now+Math.max(atk,d-rel));
      g.gain.exponentialRampToValueAtTime(0.0001,now+d);
      osc.connect(g); g.connect(this.master);
      osc.start(now); osc.stop(now+d+0.01);
      const item={node:osc,g,timerIds:[]};
      osc.onended=()=>this.active.delete(item);
      this.active.add(item);
    }
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
  }
};

function triggerPluckEventsBetween(prevBeat,nextBeat){
  if(nextBeat<=prevBeat)return;
  const bps=S.bpm/60;
  for(const ev of S.pluck){
    const eb=parseBeat(ev.beat);
    if(eb>=prevBeat&&eb<nextBeat){
      const durS=(ev.duration_b??0.5)/bps;
      Synth.trigger(ev.note,durS,speedToVelocity(ev.speed),ev.speed??6);
    }
  }
}

let playIv=null, playT0=null, playB0=0;

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
      if(wrapped<prevBeat){
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
  S.playing=false; clearInterval(playIv); playIv=null;
  Synth.stopAll();
  S.playBeat=0; document.getElementById('btn-play').classList.remove('on');
  document.getElementById('pos').textContent='1.1'; render();
}
