// ═══════════════════════════════════════════════
// MIDI INPUT  (Web MIDI → live monitor + recording)
// ═══════════════════════════════════════════════

const MIDI_DEVICE_STORAGE_KEY='guitarbot_midi_input_v1';

const MIDIInput=(()=>{
  let access=null;
  let currentPort=null;            // the MIDIInput we're listening to
  const activeVoices=new Map();    // midiNote → Synth item (for live monitor + release)
  const inFlight=new Map();        // midiNote → {startBeat,speed}  (during recording)
  let armed=false;                 // toggled by btn-midi-record
  let recordedEvents=[];           // events committed during the current take

  function _setStatus(text,color){
    const el=document.getElementById('midi-status');
    if(!el)return;
    el.textContent=text||'';
    el.style.color=color||'var(--text-dim)';
  }

  function _updateBtn(){
    const btn=document.getElementById('btn-midi-record');
    if(!btn)return;
    btn.classList.toggle('active',armed);
    btn.title=armed?'Stop MIDI recording':'Record MIDI keyboard';
  }

  // ── Device list ─────────────────────────────────────────────────
  function _populateDevices(){
    const sel=document.getElementById('midi-device');
    if(!sel||!access)return;
    const remembered=localStorage.getItem(MIDI_DEVICE_STORAGE_KEY)||'';
    const prev=sel.value;
    sel.innerHTML='';
    const none=document.createElement('option');
    none.value=''; none.textContent='— no MIDI input —';
    sel.appendChild(none);
    const inputs=[...access.inputs.values()];
    for(const inp of inputs){
      const opt=document.createElement('option');
      opt.value=inp.id;
      opt.textContent=inp.name||inp.id;
      sel.appendChild(opt);
    }
    // Prefer previously-selected device, then remembered by name, else first input
    let pick='';
    if(prev&&inputs.some(i=>i.id===prev))pick=prev;
    else if(remembered){
      const match=inputs.find(i=>(i.name||'')===remembered);
      if(match)pick=match.id;
    }
    if(!pick&&inputs.length)pick=inputs[0].id;
    sel.value=pick;
    _selectDevice(pick);
  }

  function _selectDevice(portId){
    if(currentPort){
      try{currentPort.onmidimessage=null;}catch(_e){}
      currentPort=null;
    }
    if(!portId||!access){
      _setStatus('No input selected');
      return;
    }
    const port=access.inputs.get(portId);
    if(!port){_setStatus('Device not found','#ef4444');return;}
    port.onmidimessage=_onMidiMessage;
    currentPort=port;
    S.midiInputDeviceName=port.name||'';
    try{localStorage.setItem(MIDI_DEVICE_STORAGE_KEY,S.midiInputDeviceName);}catch(_e){}
    _setStatus(`Connected: ${port.name}`,'#22c55e');
  }

  // ── MIDI message parsing ───────────────────────────────────────
  // Web MIDI delivers 3-byte channel voice messages in e.data.
  // status high nibble: 0x9 = note on, 0x8 = note off.
  // Note on with velocity 0 is also treated as note off (running-status convention).
  function _onMidiMessage(e){
    const [status,d1,d2]=e.data;
    const type=status&0xF0;
    if(type!==0x90&&type!==0x80)return;
    const note=d1, velocity=d2;
    if(type===0x90&&velocity>0)_noteOn(note,velocity);
    else _noteOff(note);
  }

  function _noteOn(note,velocity){
    // Range check mirrors addNoteExact — drop out-of-range silently
    if(note<MIDI_MIN||note>MIDI_MAX)return;

    // Live monitor: stop any previous voice for this note, trigger a new one
    const prev=activeVoices.get(note);
    if(prev)Synth.release(prev);

    Synth.ensure().then(()=>{
      // Placeholder-long duration; we stop via release() on note-off.
      const speed=Math.max(SPEED_MIN,Math.min(SPEED_MAX,Math.round((velocity/127)*SPEED_MAX)));
      const item=Synth.trigger(note,3.0,velocity,speed,0);
      if(item)activeVoices.set(note,item);
    });

    if(armed&&S.playing){
      // Latency compensation: subtract calibrated input latency
      const latencyBeats=latencyMsAtBeat(S.playBeat)/1000/secondsPerBeat();
      const startBeat=Math.max(0,S.playBeat-latencyBeats);
      const speed=Math.max(SPEED_MIN,Math.min(SPEED_MAX,Math.round((velocity/127)*SPEED_MAX)));
      inFlight.set(note,{startBeat,speed});
    }
  }

  function _noteOff(note){
    const voice=activeVoices.get(note);
    if(voice){Synth.release(voice);activeVoices.delete(note);}

    if(armed&&S.playing){
      const held=inFlight.get(note);
      if(held){
        inFlight.delete(note);
        const latencyBeats=latencyMsAtBeat(S.playBeat)/1000/secondsPerBeat();
        const endBeat=Math.max(held.startBeat+0.02,S.playBeat-latencyBeats);
        const ev=addNoteExact(note,held.startBeat,endBeat-held.startBeat,held.speed);
        if(ev)recordedEvents.push(ev.id);
      }
    }
  }

  // ── Recording lifecycle ────────────────────────────────────────
  function toggleRecording(){
    if(armed)finalizeRecording();
    else startRecording();
  }

  function startRecording(){
    if(armed)return;
    if(!currentPort){_setStatus('Select a MIDI device first','#ef4444');return;}
    armed=true;
    recordedEvents=[];
    inFlight.clear();
    S.midiRecordingActive=true;
    S.midiRecStartBeat=S.playBeat;
    _updateBtn();
    _setStatus('Recording…','#ef4444');
    if(!S.playing)document.getElementById('btn-play').click();
  }

  // Close any in-flight notes at the current playhead, then commit.
  // Called from btn-midi-record toggle and from stopPlay().
  function finalizeRecording(){
    if(!armed)return;
    const now=S.playBeat;
    for(const [note,held] of inFlight){
      const endBeat=Math.max(held.startBeat+0.02,now);
      const ev=addNoteExact(note,held.startBeat,endBeat-held.startBeat,held.speed);
      if(ev)recordedEvents.push(ev.id);
    }
    inFlight.clear();
    armed=false;
    S.midiRecordingActive=false;
    _updateBtn();
    if(recordedEvents.length){
      _setStatus(`Recorded ${recordedEvents.length} note(s)`,'#22c55e');
      syncJSON();
      render();
    }else{
      _setStatus('No notes recorded','var(--text-dim)');
    }
    recordedEvents=[];
  }

  // ── Init ───────────────────────────────────────────────────────
  async function init(){
    if(!navigator.requestMIDIAccess){
      _setStatus('Web MIDI not supported in this browser','#ef4444');
      return;
    }
    try{
      access=await navigator.requestMIDIAccess({sysex:false});
    }catch(err){
      _setStatus(`MIDI access denied: ${err.message}`,'#ef4444');
      return;
    }
    _populateDevices();
    access.onstatechange=()=>_populateDevices();
  }

  return {init,toggleRecording,finalizeRecording,selectDevice:_selectDevice};
})();

// ── Bindings ──────────────────────────────────────────────────────
document.getElementById('btn-midi-record').addEventListener('click',()=>{
  if(!navigator.requestMIDIAccess){
    alert('Web MIDI is not supported in this browser. Try Chrome or Edge.');
    return;
  }
  MIDIInput.toggleRecording();
});

document.getElementById('midi-device').addEventListener('change',e=>{
  MIDIInput.selectDevice(e.target.value);
});

document.getElementById('btn-midi-quantize').addEventListener('click',()=>{
  S.midiQuantize=!S.midiQuantize;
  const btn=document.getElementById('btn-midi-quantize');
  btn.classList.toggle('on',S.midiQuantize);
  btn.title=S.midiQuantize?'Quantize on record (on)':'Quantize on record (off)';
});

// Kick off permission flow on first user gesture anywhere on the page
// so the device list is ready by the time the user opens the Record tab.
(function(){
  const once=()=>{
    document.removeEventListener('pointerdown',once);
    MIDIInput.init();
  };
  document.addEventListener('pointerdown',once,{once:true});
})();
