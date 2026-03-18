// ═══════════════════════════════════════════════
// TRANSPORT
// ═══════════════════════════════════════════════
const Synth={
  ctx:null,
  master:null,
  active:new Set(),
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
    return this.ctx.state==='running';
  },
  midiToFreq(m){return 440*Math.pow(2,(m-69)/12)},
  trigger(note,durS=0.2,vel=90){
    if(!this.ctx||!this.master)return;
    const now=this.ctx.currentTime;
    const d=Math.max(0.03,durS);
    const rel=Math.min(0.12,Math.max(0.03,d*0.45));
    const atk=0.005;
    const amp=0.05+Math.min(1,Math.max(0,vel/127))*0.2;

    const osc=this.ctx.createOscillator();
    const g=this.ctx.createGain();
    osc.type='triangle';
    osc.frequency.setValueAtTime(this.midiToFreq(note),now);

    g.gain.setValueAtTime(0.0001,now);
    g.gain.exponentialRampToValueAtTime(amp,now+atk);
    g.gain.setValueAtTime(amp,now+Math.max(atk,d-rel));
    g.gain.exponentialRampToValueAtTime(0.0001,now+d);

    osc.connect(g); g.connect(this.master);
    osc.start(now);
    osc.stop(now+d+0.01);

    this.active.add(osc);
    osc.onended=()=>{this.active.delete(osc)};
  },
  stopAll(){
    for(const osc of this.active){
      try{osc.stop();}catch(_e){}
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
      Synth.trigger(ev.note,durS,speedToVelocity(ev.speed));
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
