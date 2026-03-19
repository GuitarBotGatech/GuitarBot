// ═══════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════
let S={
  songName:"Untitled Song", bpm:120, keyRoot:"E", keyMode:"minor",
  timeSig:"4/4", measures:8,
  pluck:[], chord:[], midi:[],
  midiCurves:createEmptyMidiCurves(),
  midiCurveMuted:createEmptyMidiCurveMuteState(),
  nextId:1, zoom:80, scrollX:0,
  playing:false, playBeat:0,
  cycleEnabled:false,
  cycleStartBar:1,
  cycleEndBar:2,
  editMode:'select',
  snapEnabled:true,
  gridIdx:1,
  selPluckIds:new Set(),
  clipboardPluck:null,
  pasteAnchor:null,
  midiLaneMenuLane:null,
  focusedCCLane:null,
  selPluck:null, selChord:null, selMidi:null,
};

const bpm=()=>{const[n]=S.timeSig.split('/').map(Number);return n};
const totalBeats=()=>S.measures*bpm();
const beatToX=b=>LABEL_W+b*S.zoom-S.scrollX;
const xToBeat=x=>(x-LABEL_W+S.scrollX)/S.zoom;
const noteToY=n=>CHORD_H+(MIDI_MAX-n)*noteH;
const yToNote=y=>MIDI_MAX-Math.floor((y-CHORD_H)/noteH);
const midiTopY=()=>CHORD_H+rollH();
const hasFocusedCCLane=()=>Number.isInteger(S.focusedCCLane)&&S.focusedCCLane>=0&&S.focusedCCLane<MIDI_AUTOMATION_CCS.length;
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
  if(rel<MIDI_AUTOMATION_TOTAL_H)return Math.min(MIDI_AUTOMATION_CCS.length-1,Math.floor(rel/MIDI_AUTOMATION_LANE_H));
  return MIDI_GENERAL_LANE_INDEX;
}
const midiValueFromY=(cy,lane)=>Math.round((1-clamp((cy-midiLaneTop(lane))/Math.max(1,midiLaneHeight(lane)),0,1))*127);
const midiYFromValue=(value,lane)=>midiLaneTop(lane)+(1-clamp((parseFloat(value)||0)/127,0,1))*midiLaneHeight(lane);
const laneForCC=cc=>{
  const index=MIDI_AUTOMATION_CCS.indexOf(parseInt(cc,10));
  return index>=0?index:-1;
};
const gridStep=()=>GRID_STEPS[S.gridIdx].beats;
const snap=b=>{const gs=gridStep();return Math.round(b/gs)*gs;};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

const trimBeatNumber=v=>parseFloat(Number(v).toFixed(4));
const normalizeBeat=b=>S.snapEnabled?snap(b):trimBeatNumber(b);
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
const hasTremolo=ev=>noteDurationSeconds(ev)>0.5;
const clampSpeed=v=>clamp(parseInt(v)||SPEED_DEFAULT,SPEED_MIN,SPEED_MAX);
const speedToVelocity=s=>Math.round(((clampSpeed(s)-SPEED_MIN)/(SPEED_MAX-SPEED_MIN))*127);
function normalizeImportedSpeed(raw){
  const n=parseFloat(raw);
  if(!Number.isFinite(n))return SPEED_DEFAULT;
  if(n>SPEED_MAX){
    const scaled=Math.round((n/127)*(SPEED_MAX-SPEED_MIN)+SPEED_MIN);
    return clampSpeed(scaled);
  }
  return clampSpeed(n);
}

function beatLabel(b){
  const normalized=Math.max(0,trimBeatNumber(b));
  const m=bpm();
  const bar=Math.floor(normalized/m)+1;
  const inBar=normalized-((bar-1)*m);
  const beatWhole=Math.floor(inBar)+1;
  const frac=inBar-Math.floor(inBar);
  const subFloat=frac*SUBDIV;
  const subRounded=Math.round(subFloat);
  const isGrid=Math.abs(subFloat-subRounded)<1e-4;
  if(isGrid){
    return `${bar}.${beatWhole}.${subRounded+1}`;
  }
  // Non-SUBDIV position (e.g. triplets): store as raw beat with sentinel
  // to avoid dot-collision in parseBeat (e.g. "1.1.1667" misread as 3-part)
  return `~${trimBeatNumber(normalized)}`;
}
function parseBeat(s){
  if(!s)return 0;
  const str=String(s);
  if(str.startsWith('~'))return parseFloat(str.slice(1))||0;
  const p=str.split('.');
  const bar=parseInt(p[0])||1;
  if(p.length>=3){
    const beat=parseInt(p[1])||1;
    const sub=parseInt(p[2])||1;
    return (bar-1)*bpm()+(beat-1)+(sub-1)/SUBDIV;
  }
  const beat=parseFloat(p[1])||1;
  return (bar-1)*bpm()+(beat-1);
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
}
