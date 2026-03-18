// ═══════════════════════════════════════════════
// CLOSE POPUPS ON OUTSIDE CLICK
// ═══════════════════════════════════════════════
document.addEventListener('pointerdown',e=>{
  if(!document.getElementById('cpop').contains(e.target)&&e.target!==canvas)closeCPop();
  if(!document.getElementById('mpop').contains(e.target)&&e.target!==canvas)closeMPop();
  if(!document.getElementById('mlpop').contains(e.target)&&e.target!==canvas)closeMLPop();
});

// ═══════════════════════════════════════════════
// KEYBOARD DELETE
// ═══════════════════════════════════════════════
document.addEventListener('keydown',e=>{
  const tag=document.activeElement?.tagName;
  if(tag==='INPUT'||tag==='SELECT'||tag==='TEXTAREA')return;

  const k=e.key.toLowerCase();
  if(e.key==='Escape'&&hasFocusedCCLane()){
    S.focusedCCLane=null;
    render();
    return;
  }
  if(k==='b'){setEditMode(S.editMode==='draw'?'select':'draw');render();return;}
  if((e.ctrlKey||e.metaKey)&&k==='a'){
    e.preventDefault();
    if(!S.pluck.length)return;
    S.selPluckIds=new Set(S.pluck.map(ev=>ev.id));
    S.selPluck=null;
    S.selChord=null;
    S.selMidi=null;
    closeInsp();
    render();
    return;
  }
  if((e.ctrlKey||e.metaKey)&&k==='c'){
    if(copySelectedPluckEvents())e.preventDefault();
    return;
  }
  if((e.ctrlKey||e.metaKey)&&k==='v'){
    if(pastePluckEvents())e.preventDefault();
    return;
  }

  if(e.key!=='Delete'&&e.key!=='Backspace')return;
  if(delSelectedPluckEvents())return;
  if(S.selPluck!==null){delSelNote();render()}
  else if(S.selChord!==null){delChord()}
  else if(S.selMidi!==null){delMidi()}
});

// ═══════════════════════════════════════════════
// INIT — load example song
// ═══════════════════════════════════════════════
// alias
const state=S;

function applyNewProject(){
  S.songName='Untitled Song';
  S.bpm=120;
  S.keyRoot='E';
  S.keyMode='minor';
  S.timeSig='4/4';
  S.measures=8;
  S.playing=false;
  S.playBeat=0;
  S.cycleEnabled=false;
  S.cycleStartBar=1;
  S.cycleEndBar=2;
  S.scrollX=0;
  noteH=noteH_DEFAULT;
  S.editMode='select';
  S.snapEnabled=true;
  S.gridIdx=1;
  S.pluck=[];
  S.chord=[];
  S.midi=[];
  S.midiCurves=createEmptyMidiCurves();
  S.midiCurveMuted=createEmptyMidiCurveMuteState();
  S.midiLaneMenuLane=null;
  S.focusedCCLane=null;
  S.nextId=1;
  S.selPluckIds.clear();
  S.clipboardPluck=null;
  S.pasteAnchor=null;
  S.selPluck=null;
  S.selChord=null;
  S.selMidi=null;
  closeInsp();

  document.getElementById('song-name').value=S.songName;
  document.getElementById('bpm').value=S.bpm;
  document.getElementById('key-root').value=S.keyRoot;
  document.getElementById('key-mode').value=S.keyMode;
  document.getElementById('time-sig').value=S.timeSig;
  document.getElementById('measures').value=S.measures;
  document.getElementById('pos').textContent='1.1';
  document.getElementById('btn-snap').classList.add('on');
  document.getElementById('btn-snap').title='Snap to grid (on)';
  syncCycleControls();
  setEditMode('select');
  updateGridCtrl();
}

function applyExampleProject(){
  applyNewProject();
  S.pluck=[
    {id:S.nextId++,note:52,duration_b:0.5,speed:6,slide:0,beat:"1.2",string_index:null},
    {id:S.nextId++,note:55,duration_b:0.5,speed:7,slide:0,beat:"1.4",string_index:null},
    {id:S.nextId++,note:59,duration_b:0.5,speed:6,slide:1,beat:"2.2",string_index:null},
    {id:S.nextId++,note:62,duration_b:0.25,speed:9,slide:0,beat:"2.4",string_index:null},
    {id:S.nextId++,note:52,duration_b:1.0,speed:6,slide:0,beat:"3.1",string_index:null},
    {id:S.nextId++,note:55,duration_b:0.5,speed:7,slide:0,beat:"4.1",string_index:null},
  ];
  S.chord=[
    {id:S.nextId++,chord:"Em",beat:"1.1"},
    {id:S.nextId++,chord:"C",beat:"2.1"},
    {id:S.nextId++,chord:"G",beat:"3.1"},
    {id:S.nextId++,chord:"D",beat:"4.1"},
  ];
  S.midi=[
    {id:S.nextId++,address:"/cc",args:[7,30],interp:1,beat:"1.1"},
    {id:S.nextId++,address:"/cc",args:[7,100],interp:0,beat:"3.1"},
  ];
}

function applyStartupMode(){
  const mode=(new URLSearchParams(window.location.search).get('startup')||'example').toLowerCase();
  if(mode==='new'){
    applyNewProject();
    return;
  }
  if(mode==='import'){
    const raw=localStorage.getItem(IMPORT_KEY);
    if(raw){
      try{
        loadJSON(JSON.parse(raw));
        localStorage.removeItem(IMPORT_KEY);
        return;
      }catch(_e){
        localStorage.removeItem(IMPORT_KEY);
      }
    }
    applyNewProject();
    return;
  }
  applyExampleProject();
}

function init(){
  resize();
  window.addEventListener('resize',resize);
  applyStartupMode();
  render();
  syncJSON();
}
init();