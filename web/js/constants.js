// ═══════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════
const MIDI_MIN=40, MIDI_MAX=73, NOTE_COUNT=34;
const noteH_DEFAULT=14, noteH_MIN=6, noteH_MAX=50;
let noteH=noteH_DEFAULT;
const LABEL_W=54, CHORD_H=30;
const MIDI_GENERAL_LANE_H=24;
const MIDI_AUTOMATION_LANE_H=30;
const TEMPO_AUTOMATION_KEY='tempo';
const TEMPO_MIN=20;
const TEMPO_MAX=300;
const MIDI_AUTOMATION_CCS=[1,2,3,4,7];
const MIDI_AUTOMATION_KEYS=[TEMPO_AUTOMATION_KEY,...MIDI_AUTOMATION_CCS.map(cc=>String(cc))];
const MIDI_LANE_COUNT=1+MIDI_AUTOMATION_KEYS.length;
const MIDI_AUTOMATION_TOTAL_H=MIDI_AUTOMATION_KEYS.length*MIDI_AUTOMATION_LANE_H;
const MIDI_GENERAL_LANE_INDEX=MIDI_AUTOMATION_KEYS.length;
const MIDI_H=MIDI_AUTOMATION_TOTAL_H+MIDI_GENERAL_LANE_H;
const rollH=()=>NOTE_COUNT*noteH;
const SLIDERLESS_H=24;
const SLIDERLESS_TOTAL=6*SLIDERLESS_H;
const canvasH=()=>{
  if(typeof S!=='undefined'&&S.activeTab!=='automation') return CHORD_H+rollH()+SLIDERLESS_TOTAL;
  return CHORD_H+rollH()+SLIDERLESS_TOTAL+MIDI_H;
};
const SUBDIV=4; // used by formatBeat/parseBeat for 3-part display only
const GRID_STEPS=[
  {label:'1/16t',beats:1/6},
  {label:'1/16', beats:1/4},
  {label:'1/8t', beats:1/3},
  {label:'1/8',  beats:1/2},
  {label:'1/4t', beats:2/3},
  {label:'1/4',  beats:1  },
  {label:'1/2t', beats:4/3},
  {label:'1/2',  beats:2  },
  {label:'1',    beats:4  },
];
const SPEED_MIN=1, SPEED_MAX=10, SPEED_DEFAULT=6;
const IMPORT_KEY='guitarbot_startup_import_json';

const STRINGS=[
  {min:40,max:52,name:"E2",color:"#ef4444",dim:"#3b050566"}, // Low E
  {min:45,max:57,name:"A2",color:"#f97316",dim:"#3b170566"}, // A
  {min:50,max:62,name:"D3",color:"#eab308",dim:"#3b2d0566"}, // D
  {min:55,max:67,name:"G3",color:"#22c55e",dim:"#053b1466"}, // G
  {min:59,max:71,name:"B3",color:"#3b82f6",dim:"#051a3b66"}, // B
  {min:64,max:76,name:"E4",color:"#a855f7",dim:"#1e053b66"}, // High E
];

const NOTE_NAMES=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
const noteName=m=>NOTE_NAMES[m%12]+(Math.floor(m/12)-1);
// lowestFretCandidate: among all strings that can play midi note m,
// return the index of the one requiring the fewest frets from open.
const lowestFretCandidate=m=>{
  let best=-1, bestFret=Infinity;
  STRINGS.forEach((s,i)=>{
    if(m>=s.min&&m<=s.max){
      const fret=m-s.min;
      if(fret<bestFret){bestFret=fret;best=i;}
    }
  });
  return best>=0?best:0;
};
// strOf: returns the STRINGS entry for a note, respecting explicit string_index
// when called with an event object, or falling back to lowestFretCandidate.
const strOf=(mOrEv,stringIdx)=>{
  // Called as strOf(midiNote) or strOf(midiNote, stringIndex)
  const m=typeof mOrEv==='object'?mOrEv.note:mOrEv;
  const idx=typeof mOrEv==='object'
    ?(mOrEv.string_index!=null?parseInt(mOrEv.string_index,10):null)
    :(stringIdx!=null?stringIdx:null);
  if(idx!=null&&idx>=0&&idx<STRINGS.length)return STRINGS[idx];
  // Chord-pluck shorthand (note 0..5 = string index)
  if(m>=0&&m<=5)return STRINGS[m]||STRINGS[0];
  return STRINGS[lowestFretCandidate(m)];
};
const createEmptyMidiCurves=()=>Object.fromEntries(MIDI_AUTOMATION_KEYS.map(key=>[String(key),[]]));
const createEmptyMidiCurveMuteState=()=>Object.fromEntries(MIDI_AUTOMATION_KEYS.map(key=>[String(key),false]));
const createEmptyMidiCurveSelection=()=>Object.fromEntries(MIDI_AUTOMATION_KEYS.map(key=>[String(key),new Set()]));
const createDefaultAutomationLaneRanges=()=>Object.fromEntries(
  MIDI_AUTOMATION_KEYS.map(key=>{
    const k=String(key);
    if(k===TEMPO_AUTOMATION_KEY)return [k,{min:TEMPO_MIN,max:TEMPO_MAX}];
    return [k,{min:0,max:127}];
  })
);
