// ═══════════════════════════════════════════════
// CRUD
// ═══════════════════════════════════════════════
function findPointCollision(array,beat,excludeId){
  const b=trimBeatNumber(Math.max(0,beat));
  for(const ev of array){
    if(ev.id===excludeId)continue;
    if(Math.abs(trimBeatNumber(parseBeat(ev.beat))-b)<1e-4)return ev;
  }
  return null;
}

function notesOverlap(startA,durA,noteA,startB,durB,noteB){
  return noteA===noteB&&startA<startB+durB&&startA+durA>startB;
}
function hasCollision(beat,dur,note,excludeId){
  for(const ev of S.pluck){
    if(ev.id===excludeId)continue;
    if(notesOverlap(beat,dur,note,parseBeat(ev.beat),ev.duration_b,ev.note))return true;
  }
  return false;
}
function clampDurationToNext(beat,note,maxDur,excludeId){
  let clamped=maxDur;
  for(const ev of S.pluck){
    if(ev.id===excludeId)continue;
    if(ev.note!==note)continue;
    const s=parseBeat(ev.beat);
    if(s>beat&&s<beat+clamped)clamped=s-beat;
  }
  return clamped;
}
function addNote(b,n){
  const dur=clampDurationToNext(b,n,gridStep(),null);
  if(hasCollision(b,dur,n,null))return null;
  const ev=ensureSlideShape({id:S.nextId++,note:n,duration_b:dur,speed:SPEED_DEFAULT,slide:0,beat:beatLabel(b),string_index:null});
  S.pluck.push(ev); selPluck(ev.id); syncJSON(); return ev;
}
function rmPluck(id){
  S.pluck=S.pluck.filter(e=>e.id!==id);
  S.selPluckIds.delete(id);
  if(S.selPluck===id){S.selPluck=null;closeInsp()}
  syncJSON();
}
function addChord(b){
  const existing=findPointCollision(S.chord,b,null);
  if(existing){selChord(existing.id);return existing;}
  const ev={id:S.nextId++,chord:'Em',beat:beatLabel(b)};
  S.chord.push(ev); selChord(ev.id); syncJSON(); return ev;
}
function addMidi(b){
  const existing=findPointCollision(S.midi,b,null);
  if(existing){selMidi(existing.id);return existing;}
  const ev={id:S.nextId++,address:'/cc',args:[7,64],interp:0,beat:beatLabel(b)};
  S.midi.push(ev); selMidi(ev.id); syncJSON(); return ev;
}

// ═══════════════════════════════════════════════
// SELECTION
// ═══════════════════════════════════════════════
function selPluck(id){
  clearMidiCurveSelection();
  S.selPluckIds=new Set([id]);
  S.selPluck=id; S.selChord=null; S.selMidi=null;
  const ev=S.pluck.find(e=>e.id===id);
  if(ev)openInsp(ev);
}
function selChord(id){clearMidiCurveSelection();S.selChord=id;S.selPluck=null;S.selMidi=null;closeInsp()}
function selMidi(id){clearMidiCurveSelection();S.selMidi=id;S.selPluck=null;S.selChord=null;closeInsp()}
function clearPluckSelection(){
  S.selPluck=null;
  S.selPluckIds.clear();
  closeInsp();
}
function deselectAll(){S.selPluck=null;S.selPluckIds.clear();S.selChord=null;S.selMidi=null;clearMidiCurveSelection();closeInsp()}

// ═══════════════════════════════════════════════
// INSPECTOR
// ═══════════════════════════════════════════════
function openInsp(ev){
  document.getElementById('insp').classList.add('open');
  refreshInspNote(ev); refreshInspDur(ev);
  document.getElementById('i-speed').value=ev.speed;
  document.getElementById('i-sv').textContent=ev.speed;
  document.getElementById('i-slide').checked=ev.slide===1;
  document.getElementById('i-slide-lbl').textContent=ev.slide?'In':'Off';
  document.getElementById('i-str-ov').value=ev.string_index!==null?ev.string_index:'';
  if(typeof updateInspectorAnalysis==='function') updateInspectorAnalysis();
}
function refreshInspNote(ev){
  const s=strOf(ev.note);
  document.getElementById('i-note').textContent=noteName(ev.note);
  document.getElementById('i-note').style.color=s.color;
  document.getElementById('i-midi').textContent=ev.note;
  document.getElementById('i-str').textContent=s.name;
  document.getElementById('i-str').style.color=s.color;
}
function refreshInspDur(ev){
  document.getElementById('i-dur').value=ev.duration_b;
  document.getElementById('i-trem').classList.toggle('on',hasTremolo(ev));
}
function closeInsp(){document.getElementById('insp').classList.remove('open')}

function updSpeed(v){
  const ev=S.pluck.find(e=>e.id===S.selPluck);if(!ev)return;
  ev.speed=clampSpeed(v);
  document.getElementById('i-speed').value=ev.speed;
  document.getElementById('i-sv').textContent=ev.speed;
  syncJSON(); render();
}
function updSlide(c){
  const ev=S.pluck.find(e=>e.id===S.selPluck);if(!ev)return;
  ev.slide=c?1:0;
  document.getElementById('i-slide-lbl').textContent=c?'In':'Off';
  syncJSON(); render();
}
function updDur(v){
  const ev=S.pluck.find(e=>e.id===S.selPluck);if(!ev)return;
  const raw=Math.max(0.0625,parseFloat(v)||0.5);
  const beat=parseBeat(ev.beat);
  ev.duration_b=clampDurationToNext(beat,ev.note,raw,ev.id);
  document.getElementById('i-dur').value=ev.duration_b;
  document.getElementById('i-trem').classList.toggle('on',hasTremolo(ev));
  syncJSON(); render();
}
function updStrOv(v){
  const ev=S.pluck.find(e=>e.id===S.selPluck);if(!ev)return;
  ev.string_index=v===''?null:parseInt(v);
  syncJSON();
}
function delSelNote(){if(S.selPluck!==null){rmPluck(S.selPluck);render()}}

function toggleSlideForSelectedPluckEvents(){
  const selected=getSelectedPluckEvents();
  if(!selected.length)return false;
  const allOn=selected.every(ev=>ev.slide===1);
  const next=allOn?0:1;
  for(const ev of selected)ev.slide=next;

  if(S.selPluck!==null&&selected.length===1){
    const sel=S.pluck.find(e=>e.id===S.selPluck);
    if(sel){
      document.getElementById('i-slide').checked=sel.slide===1;
      document.getElementById('i-slide-lbl').textContent=sel.slide?'In':'Off';
    }
  }

  syncJSON();
  render();
  return true;
}

function delSelectedPluckEvents(){
  const ids=S.selPluckIds.size?[...S.selPluckIds]:(S.selPluck!==null?[S.selPluck]:[]);
  if(!ids.length)return false;
  const idSet=new Set(ids);
  S.pluck=S.pluck.filter(ev=>!idSet.has(ev.id));
  S.selPluck=null;
  S.selPluckIds.clear();
  closeInsp();
  syncJSON();
  render();
  return true;
}

function delSelectedMidiCurvePoints(){
  if(!hasMidiCurveSelection())return false;
  for(const laneKey of MIDI_AUTOMATION_KEYS){
    const key=String(laneKey);
    const selected=S.selMidiCurvePoints[key];
    if(!selected||!selected.size)continue;
    const points=S.midiCurves[key]||[];
    S.midiCurves[key]=points.filter(point=>!selected.has(midiCurvePointKey(point.beat)));
  }
  clearMidiCurveSelection();
  syncJSON();
  render();
  return true;
}

// ═══════════════════════════════════════════════
// CHORD POPUP
// ═══════════════════════════════════════════════
function showCPop(ev,px,py){
  const p=document.getElementById('cpop');
  p.style.left=px+'px'; p.style.top=py+'px'; p.classList.add('on');
  
  const m=ev.chord.match(/^([A-G][#b]?)(.*)$/);
  const root=m?m[1]:'E';
  const qual=m?m[2]:'';
  
  const rSel=document.getElementById('cp-chord-root');
  if(![...rSel.options].some(o=>o.value===root)){
    let r=root;
    if(r==='Db')r='C#';else if(r==='Eb')r='D#';else if(r==='Gb')r='F#';else if(r==='Ab')r='G#';else if(r==='Bb')r='A#';
    rSel.value=r;
  }else rSel.value=root;
  
  const qSel=document.getElementById('cp-chord-quality');
  if(![...qSel.options].some(o=>o.value===qual)){
    const opt=document.createElement('option');
    opt.value=qual; opt.text=qual; qSel.add(opt);
  }
  qSel.value=qual;

  document.getElementById('cp-beat').value=ev.beat;
  setTimeout(()=>{
    const r=p.getBoundingClientRect();
    if(r.bottom>window.innerHeight)p.style.top=(py-r.height-8)+'px';
    if(r.right>window.innerWidth)p.style.left=(px-r.width)+'px';
  },0);
}
function closeCPop(){document.getElementById('cpop').classList.remove('on')}
function updChord(k,v){
  const ev=S.chord.find(e=>e.id===S.selChord);if(!ev)return;
  if(k==='beat'&&findPointCollision(S.chord,parseBeat(v),ev.id))return;
  ev[k]=v; syncJSON(); render();
}
function updChordSplit(){
  const ev=S.chord.find(e=>e.id===S.selChord);if(!ev)return;
  const root=document.getElementById('cp-chord-root').value;
  const qual=document.getElementById('cp-chord-quality').value;
  ev.chord=root+qual;
  syncJSON(); render();
}
function delChord(){
  if(S.selChord===null)return;
  S.chord=S.chord.filter(e=>e.id!==S.selChord);
  S.selChord=null; closeCPop(); syncJSON(); render();
}

// ═══════════════════════════════════════════════
// MIDI POPUP
// ═══════════════════════════════════════════════
function showMPop(ev,px,py){
  const p=document.getElementById('mpop');
  p.style.left=px+'px'; p.style.top=py+'px'; p.classList.add('on');
  document.getElementById('mp-addr').value=ev.address;
  document.getElementById('mp-args').value=ev.args.join(', ');
  document.getElementById('mp-interp').checked=ev.interp===1;
  setTimeout(()=>{
    const r=p.getBoundingClientRect();
    if(r.bottom>window.innerHeight)p.style.top=(py-r.height-8)+'px';
    if(r.right>window.innerWidth)p.style.left=(px-r.width)+'px';
  },0);
}
function closeMPop(){document.getElementById('mpop').classList.remove('on')}
function updMidi(k,v){
  const ev=S.midi.find(e=>e.id===S.selMidi);if(!ev)return;
  if(k==='args'){ev.args=v.split(',').map(s=>{const n=parseFloat(s.trim());return isNaN(n)?0:n})}
  else{ev[k]=v}
  dedupeMidiCCCollisions(ev.id);
  syncJSON(); render();
}
function delMidi(){
  if(S.selMidi===null)return;
  S.midi=S.midi.filter(e=>e.id!==S.selMidi);
  S.selMidi=null; closeMPop(); syncJSON(); render();
}

function showMLPop(lane,px,py){
  if(lane<0||lane>=MIDI_AUTOMATION_KEYS.length)return;
  S.midiLaneMenuLane=lane;
  const laneKey=automationLaneKey(lane);
  const p=document.getElementById('mlpop');
  p.style.left=px+'px';
  p.style.top=py+'px';
  p.classList.add('on');
  document.getElementById('ml-label').textContent=isTempoLaneKey(laneKey)?'Tempo Automation':`CC${laneKey} Automation`;
  const range=getAutomationLaneRange(laneKey);
  const minInput=document.getElementById('ml-min');
  const maxInput=document.getElementById('ml-max');
  minInput.value=range.min;
  maxInput.value=range.max;
  minInput.min=isTempoLaneKey(laneKey)?String(TEMPO_MIN):'0';
  minInput.max=isTempoLaneKey(laneKey)?String(TEMPO_MAX):'127';
  maxInput.min=isTempoLaneKey(laneKey)?String(TEMPO_MIN):'0';
  maxInput.max=isTempoLaneKey(laneKey)?String(TEMPO_MAX):'127';
  minInput.step='1';
  maxInput.step='1';
  const muted=!!S.midiCurveMuted[String(laneKey)];
  document.getElementById('ml-mute').textContent=muted?'Unmute Automation':'Mute Automation';
  setTimeout(()=>{
    const r=p.getBoundingClientRect();
    if(r.bottom>window.innerHeight)p.style.top=(py-r.height-8)+'px';
    if(r.right>window.innerWidth)p.style.left=(px-r.width)+'px';
  },0);
}

function closeMLPop(){
  document.getElementById('mlpop').classList.remove('on');
}

function clearSelectedMidiAutomationLane(){
  if(!Number.isInteger(S.midiLaneMenuLane))return;
  const lane=S.midiLaneMenuLane;
  if(lane<0||lane>=MIDI_AUTOMATION_KEYS.length)return;
  const laneKey=automationLaneKey(lane);
  S.midiCurves[String(laneKey)]=[];
  closeMLPop();
  syncJSON();
  render();
}

function toggleSelectedMidiAutomationMute(){
  if(!Number.isInteger(S.midiLaneMenuLane))return;
  const lane=S.midiLaneMenuLane;
  if(lane<0||lane>=MIDI_AUTOMATION_KEYS.length)return;
  const key=String(automationLaneKey(lane));
  S.midiCurveMuted[key]=!S.midiCurveMuted[key];
  const muted=!!S.midiCurveMuted[key];
  document.getElementById('ml-mute').textContent=muted?'Unmute Automation':'Mute Automation';
  closeMLPop();
  syncJSON();
  render();
}

function setSelectedMidiAutomationRange(which,valueRaw){
  if(!Number.isInteger(S.midiLaneMenuLane))return;
  const lane=S.midiLaneMenuLane;
  if(lane<0||lane>=MIDI_AUTOMATION_KEYS.length)return;
  const key=String(automationLaneKey(lane));
  const defaultRange=isTempoLaneKey(key)
    ?{min:TEMPO_MIN,max:TEMPO_MAX}
    :{min:0,max:127};
  const hardMin=defaultRange.min;
  const hardMax=defaultRange.max;
  const parsed=parseFloat(valueRaw);
  if(!Number.isFinite(parsed))return;

  const current=getAutomationLaneRange(key);
  let min=current.min;
  let max=current.max;
  if(which==='min')min=Math.round(parsed);
  if(which==='max')max=Math.round(parsed);

  min=clamp(min,hardMin,hardMax);
  max=clamp(max,hardMin,hardMax);
  if(max<=min){
    if(which==='min')max=Math.min(hardMax,min+1);
    else min=Math.max(hardMin,max-1);
  }
  if(max<=min){
    min=hardMin;
    max=Math.min(hardMax,hardMin+1);
  }

  S.automationLaneRanges[key]={min,max};
  const points=S.midiCurves[key]||[];
  S.midiCurves[key]=normalizeMidiCurvePoints(points,key);

  const minInput=document.getElementById('ml-min');
  const maxInput=document.getElementById('ml-max');
  minInput.value=min;
  maxInput.value=max;

  syncJSON();
  render();
}

function selectedMidiCurvePoints(){
  const points=[];
  for(const laneKey of MIDI_AUTOMATION_KEYS){
    const key=String(laneKey);
    const selected=S.selMidiCurvePoints[key];
    if(!selected||!selected.size)continue;
    for(const point of S.midiCurves[key]||[]){
      if(!selected.has(midiCurvePointKey(point.beat)))continue;
      const value=isTempoLaneKey(key)
        ?clamp(Math.round(point.value),TEMPO_MIN,TEMPO_MAX)
        :clamp(Math.round(point.value),0,127);
      points.push({key,beat:trimBeatNumber(point.beat),value});
    }
  }
  return points.sort((a,b)=>a.beat-b.beat||String(a.key).localeCompare(String(b.key))||a.value-b.value);
}

function copySelectedTimelineEvents(){
  const selectedPluck=getSelectedPluckEvents();
  const selectedCurves=selectedMidiCurvePoints();
  if(!selectedPluck.length&&!selectedCurves.length)return false;

  if(selectedPluck.length){
    const events=selectedPluck
      .map(ev=>({
        beat:parseBeat(ev.beat),
        note:ev.note,
        duration_b:ev.duration_b,
        speed:ev.speed,
        slide:ev.slide,
        slideIn:ev.slideIn,
        slideOut:ev.slideOut,
        string_index:ev.string_index,
      }))
      .sort((a,b)=>a.beat-b.beat||a.note-b.note);
    const originBeat=Math.min(...events.map(e=>e.beat));
    const originNote=Math.min(...events.map(e=>e.note));
    S.clipboardPluck={originBeat,originNote,events};
  }else{
    S.clipboardPluck=null;
  }

  if(selectedCurves.length){
    const originBeat=Math.min(...selectedCurves.map(point=>point.beat));
    S.clipboardMidiCurves={originBeat,points:selectedCurves};
  }else{
    S.clipboardMidiCurves=null;
  }

  return true;
}

function pasteTimelineEvents(){
  const clipPluck=S.clipboardPluck;
  const clipCurves=S.clipboardMidiCurves;
  const hasPluckClip=!!(clipPluck&&clipPluck.events&&clipPluck.events.length);
  const hasCurveClip=!!(clipCurves&&clipCurves.points&&clipCurves.points.length);
  if(!hasPluckClip&&!hasCurveClip)return false;

  const originBeat=hasPluckClip?clipPluck.originBeat:clipCurves.originBeat;
  const targetBeat=S.pasteAnchor?S.pasteAnchor.beat:(originBeat+1);

  const createdPluck=[];
  const createdCurveSelection=createEmptyMidiCurveSelection();

  if(hasPluckClip){
    for(const src of clipPluck.events){
      const b=targetBeat+(src.beat-clipPluck.originBeat);
      if(b<0||b>=totalBeats())continue;
      const n=clampNote(src.note);
      const ev=ensureSlideShape({
        id:S.nextId++,
        note:n,
        duration_b:src.duration_b,
        speed:src.speed,
        slide:src.slide,
        slideIn:src.slideIn,
        slideOut:src.slideOut,
        beat:beatLabel(normalizeBeat(b)),
        string_index:src.string_index,
      });
      S.pluck.push(ev);
      createdPluck.push(ev.id);
    }
  }

  if(hasCurveClip){
    for(const src of clipCurves.points){
      const b=targetBeat+(src.beat-clipCurves.originBeat);
      if(b<0||b>=totalBeats())continue;
      const beat=normalizeBeat(b);
      upsertMidiCurvePoint(src.key,beat,clampAutomationValue(src.key,src.value));
      createdCurveSelection[String(src.key)].add(midiCurvePointKey(beat));
    }
  }

  if(!createdPluck.length&&!hasCurveClip)return false;

  S.selPluckIds=new Set(createdPluck);
  S.selPluck=createdPluck.length===1?createdPluck[0]:null;
  S.selChord=null;
  S.selMidi=null;
  S.selMidiCurvePoints=createdCurveSelection;

  if(S.selPluck!==null&&!hasMidiCurveSelection()){
    const ev=S.pluck.find(e=>e.id===S.selPluck);
    if(ev)openInsp(ev);
  }else{
    closeInsp();
  }

  syncJSON();
  render();
  return true;
}

function selectAllEditableEvents(){
  if(!S.pluck.length&&!MIDI_AUTOMATION_KEYS.some(key=>(S.midiCurves[String(key)]||[]).length))return false;
  S.selPluckIds=new Set(S.pluck.map(ev=>ev.id));
  S.selPluck=null;
  S.selChord=null;
  S.selMidi=null;
  const allCurveSelection=createEmptyMidiCurveSelection();
  for(const laneKey of MIDI_AUTOMATION_KEYS){
    for(const point of S.midiCurves[String(laneKey)]||[]){
      allCurveSelection[String(laneKey)].add(midiCurvePointKey(point.beat));
    }
  }
  S.selMidiCurvePoints=allCurveSelection;
  closeInsp();
  render();
  return true;
}

function getSelectedPluckEvents(){
  const ids=S.selPluckIds.size?[...S.selPluckIds]:(S.selPluck!==null?[S.selPluck]:[]);
  if(!ids.length)return [];
  const idSet=new Set(ids);
  return S.pluck.filter(ev=>idSet.has(ev.id));
}

function copySelectedPluckEvents(){
  return copySelectedTimelineEvents();
}

function pastePluckEvents(){
  return pasteTimelineEvents();
}
