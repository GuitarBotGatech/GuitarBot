// ═══════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════
let S={
  songName:"Untitled Song", bpm:120, keyRoot:"E", keyMode:"minor",
  timeSig:"4/4", measures:8,
  pluck:[], harmonic:[], chord:[], midi:[],
  midiCurves:createEmptyMidiCurves(),
  midiCurveMuted:createEmptyMidiCurveMuteState(),
    selMidiCurvePoints:createEmptyMidiCurveSelection(),
  automationLaneRanges:createDefaultAutomationLaneRanges(),
  nextId:1, zoom:80, scrollX:0,
  playing:false, playBeat:0,
  cycleEnabled:false,
  cycleStartBar:1,
  cycleEndBar:2,
  activeTab:'create',
  sections:[],
  sectionTimeline:[],
  sectionNextId:1,
  sectionNextTimelineId:1,
  sectionSelectedTimelineItemId:null,
  sectionSelectedTimelineItemIds:[],
  sectionClipboard:null,
  editMode:'select',
  snapEnabled:true,
  notePreview:true,
  gridIdx:1,
  stringSoloIndex:null,
  activeTab:'create',
  stringMuted:[false,false,false,false,false,false],
  selPluckIds:new Set(),
  clipboardPluck:null,
    clipboardMidiCurves:null,
  historyUndo:[],
  historyRedo:[],
  historySuspend:false,
  pasteAnchor:null,
  midiLaneMenuLane:null,
  focusedCCLane:null,
  selPluck:null, selChord:null, selMidi:null,
  spectrogramFrames:[],
  spectrogramParams:null,
  noteAnalysis:{},
  spectrogramVisible:false,
  recordingActive:false,
  latencyMs:80,
  latencyDriftMsPerMin:0,
  audioWavB64:null,
  recStartBeat:0,
  midiRecordingActive:false,
  midiRecStartBeat:0,
  midiQuantize:false,
  midiInputDeviceName:null,
};

function beatsPerMeasureFromTimeSig(timeSigRaw){
  const parts=String(timeSigRaw||'4/4').split('/');
  const numerator=parseInt(parts[0],10);
  return Math.max(1,Number.isFinite(numerator)?numerator:4);
}
const bpm=()=>beatsPerMeasureFromTimeSig(S.timeSig);
const totalBeats=()=>S.measures*bpm();
const beatToX=b=>LABEL_W+b*S.zoom-S.scrollX;
const xToBeat=x=>(x-LABEL_W+S.scrollX)/S.zoom;
// Sliderless lanes: note 0..5 map to lanes top-to-bottom as string 5..0
// (highest string at top, lowest at bottom, matching visual guitar layout)
const noteToY=n=>{
  const nh=activeNoteH();
  if(n>=0&&n<=5)
    return CHORD_H+rollH()+(5-n)*SLIDERLESS_H+(SLIDERLESS_H-nh)/2;
  return CHORD_H+(MIDI_MAX-n)*nh;
};
const yToNote=y=>{
  if(S.activeTab!=='automation'){
    const slTop=CHORD_H+rollH();
    if(y>=slTop&&y<slTop+SLIDERLESS_TOTAL){
      const lane=Math.floor((y-slTop)/SLIDERLESS_H);
      return 5-lane; // lane 0 → note 5 (E4), lane 5 → note 0 (E2)
    }
  }
  const nh=activeNoteH();
  return Math.max(MIDI_MIN,Math.min(MIDI_MAX,MIDI_MAX-Math.floor((y-CHORD_H)/nh)));
};
const clampNote=n=>{
  if(n>=0&&n<=5)return Math.round(clamp(n,0,5));
  return clamp(n,MIDI_MIN,MIDI_MAX);
};
const midiTopY=()=>CHORD_H+rollH()+(S.activeTab==='automation'?0:SLIDERLESS_TOTAL);
const hasFocusedCCLane=()=>Number.isInteger(S.focusedCCLane)&&S.focusedCCLane>=0&&S.focusedCCLane<MIDI_AUTOMATION_KEYS.length;
const midiLaneVisible=index=>!hasFocusedCCLane()||index===S.focusedCCLane;
const midiLaneTop=index=>{
  if(hasFocusedCCLane())return midiTopY();
  return index===MIDI_GENERAL_LANE_INDEX?midiTopY()+MIDI_AUTOMATION_TOTAL_H:midiTopY()+(index*MIDI_AUTOMATION_LANE_H);
};
const midiLaneHeight=index=>{
  if(!midiLaneVisible(index))return 0;
  if(hasFocusedCCLane())return MIDI_H;
  return index===MIDI_GENERAL_LANE_INDEX?MIDI_GENERAL_LANE_H:MIDI_AUTOMATION_LANE_H;
};
function midiLaneAtY(cy){
  const rel=cy-midiTopY();
  if(rel<0||rel>=MIDI_H)return-1;
  if(hasFocusedCCLane())return S.focusedCCLane;
  if(rel<MIDI_AUTOMATION_TOTAL_H)return Math.min(MIDI_AUTOMATION_KEYS.length-1,Math.floor(rel/MIDI_AUTOMATION_LANE_H));
  return MIDI_GENERAL_LANE_INDEX;
}
const automationLaneKey=lane=>{
  if(!Number.isInteger(lane)||lane<0||lane>=MIDI_AUTOMATION_KEYS.length)return null;
  return String(MIDI_AUTOMATION_KEYS[lane]);
};
const isTempoLaneKey=key=>String(key)===TEMPO_AUTOMATION_KEY;
function getAutomationLaneRange(key){
  const laneKey=String(key);
  const fallback=isTempoLaneKey(laneKey)
    ?{min:TEMPO_MIN,max:TEMPO_MAX}
    :{min:0,max:127};
  const src=S.automationLaneRanges?.[laneKey];
  let min=Number.isFinite(parseFloat(src?.min))?parseFloat(src.min):fallback.min;
  let max=Number.isFinite(parseFloat(src?.max))?parseFloat(src.max):fallback.max;
  min=Math.round(min);
  max=Math.round(max);
  if(max<=min)max=min+1;
  return {min,max};
}
function clampAutomationValue(key,value){
  const range=getAutomationLaneRange(key);
  return clamp(Math.round(parseFloat(value)||0),range.min,range.max);
}
const midiValueFromY=(cy,lane)=>{
  const key=automationLaneKey(lane);
  if(!key)return 0;
  const range=getAutomationLaneRange(key);
  const norm=(1-clamp((cy-midiLaneTop(lane))/Math.max(1,midiLaneHeight(lane)),0,1));
  return Math.round(range.min+(norm*(range.max-range.min)));
};
const midiYFromValue=(value,lane)=>{
  const key=automationLaneKey(lane);
  if(!key)return midiLaneTop(lane);
  const range=getAutomationLaneRange(key);
  const norm=clamp((parseFloat(value)-range.min)/Math.max(1,(range.max-range.min)),0,1);
  return midiLaneTop(lane)+(1-norm)*midiLaneHeight(lane);
};
const laneForCC=cc=>{
  const index=MIDI_AUTOMATION_CCS.indexOf(parseInt(cc,10));
  return index>=0?index+1:-1;
};
const tempoLane=()=>0;
const gridStep=()=>GRID_STEPS[S.gridIdx].beats;
const snap=b=>{const gs=gridStep();return Math.round(b/gs)*gs;};
const snapCellStart=b=>{const gs=gridStep();return Math.floor(b/gs)*gs;};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

const trimBeatNumber=v=>parseFloat(Number(v).toFixed(4));
const midiCurvePointKey=beat=>trimBeatNumber(Math.max(0,parseFloat(beat)||0)).toFixed(4);
const normalizeBeat=b=>S.snapEnabled?snap(b):trimBeatNumber(b);
const normalizePlacementBeat=b=>S.snapEnabled?snapCellStart(b):trimBeatNumber(b);
const minDurationBeats=()=>S.snapEnabled?gridStep():0.02;
const noteDurationSeconds=ev=>ev.duration_b*(60/Math.max(1,S.bpm));
const secondsPerBeat=()=>{
  const parts=String(S.timeSig||'4/4').split('/');
  const denominator=parseFloat(parts[1]);
  const beatUnit=Number.isFinite(denominator)&&denominator>0?denominator:4;
  return (60/Math.max(1,S.bpm))*(4/beatUnit);
};
const secondsToBeat=t=>trimBeatNumber(Math.max(0,parseFloat(t)||0)/secondsPerBeat());
const secondsToDurationBeats=t=>Math.max(0.02,trimBeatNumber((parseFloat(t)||0)/secondsPerBeat()));
const beatsToSeconds=b=>Math.max(0,parseFloat(b)||0)*secondsPerBeat();
const latencyMsAtBeat=(beat,referenceBeat=S.recStartBeat)=>{
  const base=Math.max(0,parseFloat(S.latencyMs)||0);
  const driftPerMin=parseFloat(S.latencyDriftMsPerMin)||0;
  const elapsedBeats=Math.max(0,(parseFloat(beat)||0)-(parseFloat(referenceBeat)||0));
  const elapsedMinutes=(elapsedBeats*secondsPerBeat())/60;
  return Math.max(0,base+(driftPerMin*elapsedMinutes));
};
const formatTimelineSeconds=s=>{
  const total=Math.max(0,parseFloat(s)||0);
  if(total<60)return `${parseFloat(total.toFixed(2)).toString()}s`;
  const mins=Math.floor(total/60);
  const secs=Math.floor(total%60);
  return `${mins}:${String(secs).padStart(2,'0')}`;
};
const secondsTickStep=()=>{
  const pxPerSecond=S.zoom/Math.max(1e-6,secondsPerBeat());
  const minPx=72;
  const candidates=[0.25,0.5,1,2,5,10,15,30,60,120];
  for(const step of candidates){
    if(pxPerSecond*step>=minPx)return step;
  }
  return candidates[candidates.length-1];
};
const hasTremolo=ev=>{
  if(!ev)return false;
  const durationS=noteDurationSeconds(ev);
  const speed=clampSpeed(ev.speed);
  return durationS>=TREMOLO_DURATION_THRESHOLD_S&&speed>0;
};
const hasMidiCurveSelection=()=>MIDI_AUTOMATION_KEYS.some(key=>(S.selMidiCurvePoints[String(key)]?.size||0)>0);
const isMidiCurvePointSelected=(key,point)=>{
  const set=S.selMidiCurvePoints[String(key)];
  if(!set||!point)return false;
  return set.has(midiCurvePointKey(point.beat));
};
function clearMidiCurveSelection(){
  S.selMidiCurvePoints=createEmptyMidiCurveSelection();
}
const clampSpeed=v=>{
  const parsed=parseInt(v,10);
  const safe=Number.isFinite(parsed)?parsed:SPEED_DEFAULT;
  return clamp(safe,SPEED_MIN,SPEED_MAX);
};
const speedToVelocity=s=>Math.round(((clampSpeed(s)-SPEED_MIN)/(SPEED_MAX-SPEED_MIN))*127);

function stringLaneBounds(index){
  let topNote=-1, bottomNote=Infinity;
  for(let n=MIDI_MIN;n<=MIDI_MAX;n++){
    if(strOf(n)===STRINGS[index]){
      topNote=Math.max(topNote,n);
      bottomNote=Math.min(bottomNote,n);
    }
  }
  if(topNote===-1)return null;
  const top=noteToY(topNote);
  const bottom=noteToY(bottomNote)+activeNoteH();
  return {top,bottom,height:Math.max(0,bottom-top)};
}

function stringTrackControlRects(index){
  const bounds=stringLaneBounds(index);
  if(!bounds)return null;
  const pad=3;
  const labelH = 7;
  const btnH = 16;
  const btnW = 20;
  const gap = 4;
  const stackH = btnH * 2 + gap;
  const wrap = document.getElementById('roll-wrap');
  const scrollY = wrap ? wrap.scrollTop : 0;
  
  const blockH = labelH + 8 + stackH;
  const minStartY = bounds.top + pad;
  const maxStartY = bounds.bottom - pad - blockH;
  const stickyY = Math.min(maxStartY, Math.max(minStartY, scrollY + pad));

  const label = {x: 6, y: stickyY + 1, w: LABEL_W - 12, h: labelH};
  const startY = stickyY + labelH + 8;
  const solo = {x: 6, y: startY, w: btnW, h: btnH};
  const mute = {x: 6, y: startY + btnH + gap, w: btnW, h: btnH};
  return {label,solo,mute,bounds};
}
function normalizeImportedSpeed(raw){
  const n=parseFloat(raw);
  if(!Number.isFinite(n))return SPEED_DEFAULT;
  if(n>SPEED_MAX){
    const scaled=Math.round((n/127)*(SPEED_MAX-SPEED_MIN)+SPEED_MIN);
    return clampSpeed(scaled);
  }
  return clampSpeed(n);
}

function ensureSlideShape(ev){
  if(!ev)return ev;
  ev.slide=ev.slide===1?1:0;
  // TODO: keep placeholders for future independent slide-in / slide-out semantics.
  ev.slideIn=ev.slideIn===1?1:0;
  ev.slideOut=ev.slideOut===1?1:0;
  return ev;
}

function beatLabelWithTimeSig(b,timeSigRaw){
  const normalized=Math.max(0,trimBeatNumber(b));
  const m=beatsPerMeasureFromTimeSig(timeSigRaw);
  let barIndex=Math.floor(normalized/m);
  let inBar=normalized-(barIndex*m);
  if(Math.abs(inBar-m)<1e-4){
    barIndex+=1;
    inBar=0;
  }
  let beatWhole=Math.floor(inBar)+1;
  const frac=inBar-Math.floor(inBar);
  const subFloat=frac*SUBDIV;
  const subRounded=Math.round(subFloat);
  const isGrid=Math.abs(subFloat-subRounded)<1e-4;
  if(isGrid){
    let subIndex=subRounded+1;
    if(subIndex>SUBDIV){
      beatWhole+=1;
      subIndex=1;
    }
    if(beatWhole>m){
      barIndex+=1;
      beatWhole=1;
    }
    return `${barIndex+1}.${beatWhole}.${subIndex}`;
  }
  // Non-SUBDIV position (e.g. triplets): store as raw beat with sentinel
  // to avoid dot-collision in parseBeat (e.g. "1.1.1667" misread as 3-part)
  return `~${trimBeatNumber(normalized)}`;
}
function beatLabel(b){
  return beatLabelWithTimeSig(b,S.timeSig);
}
function parseBeatWithTimeSig(s,timeSigRaw){
  if(!s)return 0;
  const str=String(s);
  if(str.startsWith('~'))return parseFloat(str.slice(1))||0;
  const p=str.split('.');
  const bar=parseInt(p[0])||1;
  const beatsPerBar=beatsPerMeasureFromTimeSig(timeSigRaw);
  if(p.length>=3){
    const beat=parseInt(p[1])||1;
    const sub=parseInt(p[2])||1;
    return (bar-1)*beatsPerBar+(beat-1)+(sub-1)/SUBDIV;
  }
  const beat=parseFloat(p[1])||1;
  return (bar-1)*beatsPerBar+(beat-1);
}
function parseBeat(s){
  return parseBeatWithTimeSig(s,S.timeSig);
}

function remapEventBeatsForTimeSigChange(fromTimeSig,toTimeSig){
  if(String(fromTimeSig||'')===String(toTimeSig||''))return;
  const remapEvent=ev=>{
    if(!ev||ev.beat===undefined||ev.beat===null)return;
    const current=String(ev.beat).trim();
    if(!current)return;
    const absoluteBeat=parseBeatWithTimeSig(current,fromTimeSig);
    ev.beat=beatLabelWithTimeSig(absoluteBeat,toTimeSig);
  };
  S.pluck.forEach(remapEvent);
  (S.harmonic||[]).forEach(remapEvent);
  S.chord.forEach(remapEvent);
  S.midi.forEach(remapEvent);
}

function getCycleRange(){
  if(!S.cycleEnabled)return null;
  const m=bpm();
  const startBar=clamp(parseFloat(S.cycleStartBar)||1,1,S.measures);
  const endBar=clamp(parseFloat(S.cycleEndBar)||startBar,startBar,S.measures);
  const startBeat=trimBeatNumber((startBar-1)*m);
  const endBeat=trimBeatNumber(endBar*m);
  if(endBeat<=startBeat)return null;
  return {startBar,endBar,startBeat,endBeat};
}

function setCycleRangeFromBeats(startBeatRaw,endBeatRaw,enable=true){
  const m=bpm();
  const maxBeat=Math.max(0,S.measures*m);
  let startBeat=clamp(parseFloat(startBeatRaw)||0,0,maxBeat);
  let endBeat=clamp(parseFloat(endBeatRaw)||0,0,maxBeat);
  if(endBeat<startBeat){
    const tmp=startBeat;
    startBeat=endBeat;
    endBeat=tmp;
  }
  const minDur=minDurationBeats();
  if(endBeat-startBeat<minDur)endBeat=Math.min(maxBeat,startBeat+minDur);
  if(endBeat<=startBeat)return false;

  S.cycleStartBar=(startBeat/m)+1;
  S.cycleEndBar=endBeat/m;
  if(enable)S.cycleEnabled=true;
  syncCycleControls();
  return true;
}

function syncCycleControls(){
  const maxBars=Math.max(1,S.measures);
  const roundVal=v=>Math.round(parseFloat(v)*100)/100;
  S.cycleStartBar=clamp(roundVal(S.cycleStartBar)||1,1,maxBars);
  S.cycleEndBar=clamp(roundVal(S.cycleEndBar)||S.cycleStartBar,S.cycleStartBar,maxBars);

  const btn=document.getElementById('btn-cycle');
  const inStart=document.getElementById('cycle-start');
  const inEnd=document.getElementById('cycle-end');
  if(!btn||!inStart||!inEnd)return;

  btn.classList.toggle('on',S.cycleEnabled);
  btn.title=S.cycleEnabled?'Cycle bar (on)':'Cycle bar (off)';
  inStart.disabled=!S.cycleEnabled;
  inEnd.disabled=!S.cycleEnabled;
  inStart.max=maxBars;
  inEnd.max=maxBars;
  inStart.value=S.cycleStartBar;
  inEnd.value=S.cycleEndBar;

  if(typeof syncSectionControls==='function')syncSectionControls();
}
