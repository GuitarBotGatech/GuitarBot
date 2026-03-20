// ═══════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════
const MIDI_MIN=40, MIDI_MAX=68, NOTE_COUNT=29;
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
const SLIDERLESS_TOTAL=3*SLIDERLESS_H;
const canvasH=()=>CHORD_H+rollH()+SLIDERLESS_TOTAL+MIDI_H;
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
  {min:40,max:49,name:"E String",color:"#f59e0b",dim:"#3b200566"},
  {min:50,max:58,name:"D String",color:"#14b8a6",dim:"#0a3b3666"},
  {min:59,max:68,name:"B String",color:"#a855f7",dim:"#3b107866"},
];

const NOTE_NAMES=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
const noteName=m=>NOTE_NAMES[m%12]+(Math.floor(m/12)-1);
const strOf=m=>{
  if(m===0) return STRINGS[0];
  if(m===2) return STRINGS[1];
  if(m===4) return STRINGS[2];
  return STRINGS.find(s=>m>=s.min&&m<=s.max)||STRINGS[0];
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
