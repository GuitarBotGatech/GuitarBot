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
  const k=e.key.toLowerCase();
  if((e.ctrlKey||e.metaKey)&&!e.altKey&&k==='z'&&!e.shiftKey){
    e.preventDefault();
    undoHistory();
    return;
  }
  if((e.ctrlKey||e.metaKey)&&!e.altKey&&k==='z'&&e.shiftKey){
    e.preventDefault();
    redoHistory();
    return;
  }

  const tag=document.activeElement?.tagName;
  if(tag==='INPUT'||tag==='SELECT'||tag==='TEXTAREA')return;
  if(!e.ctrlKey&&!e.metaKey&&!e.altKey&&e.key>='1'&&e.key<='6'){
    const stringIdx=parseInt(e.key,10)-1;
    if(setStringOverrideForSelected(stringIdx)){
      e.preventDefault();
    }
    return;
  }
  if(e.key==='Escape'&&hasFocusedCCLane()){
    S.focusedCCLane=null;
    render();
    return;
  }
  if(!e.ctrlKey&&!e.metaKey&&!e.altKey&&k==='s'){
    if(toggleSlideForSelectedPluckEvents()){
      e.preventDefault();
    }
    return;
  }
  if(k==='b'){setEditMode(S.editMode==='draw'?'select':'draw');render();return;}
  if((e.ctrlKey||e.metaKey)&&k==='a'){
    e.preventDefault();
    selectAllEditableEvents();
    return;
  }
  if((e.ctrlKey||e.metaKey)&&k==='c'){
    if(copySelectedTimelineEvents())e.preventDefault();
    return;
  }
  if((e.ctrlKey||e.metaKey)&&k==='v'){
    if(pasteTimelineEvents())e.preventDefault();
    return;
  }

  if(e.key!=='Delete'&&e.key!=='Backspace')return;
  if(delSelectedPluckEvents())return;
  if(delSelectedMidiCurvePoints())return;
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
  S.stringSoloIndex=null;
  S.stringMuted=STRINGS.map(()=>false);
  S.pluck=[];
  S.harmonic=[];
  S.chord=[];
  S.midi=[];
  S.midiCurves=createEmptyMidiCurves();
  S.midiCurveMuted=createEmptyMidiCurveMuteState();
  S.automationLaneRanges=createDefaultAutomationLaneRanges();
  S.midiLaneMenuLane=null;
  S.focusedCCLane=null;
  S.nextId=1;
  S.selPluckIds.clear();
  S.clipboardPluck=null;
  S.clipboardMidiCurves=null;
  S.pasteAnchor=null;
  S.selPluck=null;
  S.selChord=null;
  S.selMidi=null;
  clearMidiCurveSelection();
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
    ensureSlideShape({id:S.nextId++,note:52,duration_b:0.5,speed:6,slide:0,beat:"1.2",string_index:null}),
    ensureSlideShape({id:S.nextId++,note:55,duration_b:0.5,speed:7,slide:0,beat:"1.4",string_index:null}),
    ensureSlideShape({id:S.nextId++,note:59,duration_b:0.5,speed:6,slide:1,beat:"2.2",string_index:null}),
    ensureSlideShape({id:S.nextId++,note:62,duration_b:0.25,speed:9,slide:0,beat:"2.4",string_index:null}),
    ensureSlideShape({id:S.nextId++,note:52,duration_b:1.0,speed:6,slide:0,beat:"3.1",string_index:null}),
    ensureSlideShape({id:S.nextId++,note:55,duration_b:0.5,speed:7,slide:0,beat:"4.1",string_index:null}),
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
  if(mode==='recent'){
    const raw=localStorage.getItem('guitarbot_autosave');
    if(raw){
      try{
        loadJSON(JSON.parse(raw));
        return;
      }catch(_e){}
    }
    applyNewProject();
    return;
  }
  if(mode==='import'){
    const raw=localStorage.getItem(IMPORT_KEY);
    if(raw){
      try{
        const parsed=JSON.parse(raw);
        if(parsed&&typeof parsed==='object'&&typeof parsed.kind==='string'){
          if(parsed.kind==='json'){
            loadJSON(JSON.parse(String(parsed.data||'{}')));
          }else if(parsed.kind==='midi'){
            const b64=String(parsed.data||'');
            const binary=atob(b64);
            const bytes=new Uint8Array(binary.length);
            for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
            importMidiFromArrayBuffer(bytes.buffer,parsed.name||'Imported.mid');
          }else{
            throw new Error('Unknown import payload type');
          }
        }else{
          loadJSON(parsed);
        }
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
  const wrap = document.getElementById('roll-wrap');
  if (wrap) wrap.addEventListener('scroll', ()=>render());
  applyStartupMode();
  render();
  syncJSON();
}
init();