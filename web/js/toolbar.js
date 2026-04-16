// ═══════════════════════════════════════════════
// TABS
// ═══════════════════════════════════════════════
function setActiveTab(tabRaw){
  const requested=String(tabRaw||'create');
  const validTabs=new Set(['create','automation','record']);
  const tab=validTabs.has(requested)?requested:'create';
  S.activeTab=tab;
  document.querySelectorAll('.tab-btn').forEach(btn=>{
    btn.classList.toggle('active',btn.dataset.tab===tab);
  });
  document.querySelectorAll('.tab-content').forEach(content=>{
    content.style.display=content.id===`tab-${tab}`?'flex':'none';
  });
  if(typeof onTabChanged==='function')onTabChanged(tab);
  if(typeof resize==='function') resize(); else render();
}

document.querySelectorAll('.tab-btn').forEach(btn=>{
  btn.addEventListener('click',()=>setActiveTab(btn.dataset.tab));
});

window.setActiveTab=setActiveTab;

// ═══════════════════════════════════════════════
// ZOOM BUTTONS
// ═══════════════════════════════════════════════
document.getElementById('zoom-in').addEventListener('click',()=>{const oz=S.zoom;S.zoom=clamp(S.zoom*1.25,18,320);S.scrollX+=S.playBeat*(S.zoom-oz);render()});
document.getElementById('zoom-out').addEventListener('click',()=>{const oz=S.zoom;S.zoom=clamp(S.zoom/1.25,18,320);S.scrollX+=S.playBeat*(S.zoom-oz);render()});
document.getElementById('btn-note-preview').addEventListener('click',()=>{
  S.notePreview=!S.notePreview;
  const btn=document.getElementById('btn-note-preview');
  btn.classList.toggle('on',S.notePreview);
  btn.title=S.notePreview?'Note preview (on)':'Note preview (off)';
});
document.getElementById('btn-snap').addEventListener('click',()=>{
  S.snapEnabled=!S.snapEnabled;
  const btn=document.getElementById('btn-snap');
  btn.classList.toggle('on',S.snapEnabled);
  btn.title=S.snapEnabled?'Snap to grid (on)':'Snap to grid (off)';
});
document.getElementById('btn-cycle').addEventListener('click',()=>{
  S.cycleEnabled=!S.cycleEnabled;
  syncCycleControls();
  render();
});
document.getElementById('cycle-start').addEventListener('input',e=>{
  S.cycleStartBar=clamp(parseFloat(e.target.value)||1,1,S.measures);
  if(S.cycleEndBar<S.cycleStartBar)S.cycleEndBar=S.cycleStartBar;
  syncCycleControls();
  render();
});
document.getElementById('cycle-end').addEventListener('input',e=>{
  S.cycleEndBar=clamp(parseFloat(e.target.value)||S.cycleStartBar,S.cycleStartBar,S.measures);
  syncCycleControls();
  render();
});

// ═══════════════════════════════════════════════
// GRID CONTROL
// ═══════════════════════════════════════════════
function updateGridCtrl(){
  document.getElementById('grid-label').textContent=GRID_STEPS[S.gridIdx].label;
  document.getElementById('grid-prev').disabled=S.gridIdx<=0;
  document.getElementById('grid-next').disabled=S.gridIdx>=GRID_STEPS.length-1;
}
document.getElementById('grid-prev').addEventListener('click',()=>{
  if(S.gridIdx>0){S.gridIdx--;updateGridCtrl();render();}
});
document.getElementById('grid-next').addEventListener('click',()=>{
  if(S.gridIdx<GRID_STEPS.length-1){S.gridIdx++;updateGridCtrl();render();}
});
updateGridCtrl();

function setEditMode(mode){
  S.editMode=mode==='draw'?'draw':'select';
  const penBtn=document.getElementById('btn-mode-draw');
  const isDraw=S.editMode==='draw';
  penBtn.classList.toggle('on',isDraw);
  penBtn.title=isDraw?'Draw mode (pen on)':'Select mode (pen off)';
  document.getElementById('roll-wrap').style.cursor=isDraw?'default':'crosshair';
  canvas.style.cursor=isDraw?'default':'crosshair';
  if(!isDraw)closeInsp();
}

document.getElementById('btn-mode-draw').addEventListener('click',()=>{
  setEditMode(S.editMode==='draw'?'select':'draw');
  render();
});

function openSettingsPop(){
  const p=document.getElementById('settings-pop');
  p.style.left='18px';
  p.style.top='62px';
  p.classList.add('on');
  document.getElementById('btn-settings').classList.add('on');
}

function closeSettingsPop(){
  document.getElementById('settings-pop').classList.remove('on');
  document.getElementById('btn-settings').classList.remove('on');
}

document.getElementById('btn-settings').addEventListener('click',()=>{
  const p=document.getElementById('settings-pop');
  if(p.classList.contains('on'))closeSettingsPop();
  else openSettingsPop();
});

document.addEventListener('pointerdown',e=>{
  const p=document.getElementById('settings-pop');
  const btn=document.getElementById('btn-settings');
  if(!p.contains(e.target)&&!btn.contains(e.target))closeSettingsPop();
});

// ═══════════════════════════════════════════════
// TOOLBAR BINDINGS
// ═══════════════════════════════════════════════
document.getElementById('song-name').addEventListener('input',e=>{S.songName=e.target.value;syncJSON()});
document.getElementById('bpm').addEventListener('input',e=>{S.bpm=Math.max(1,parseFloat(e.target.value)||120);syncJSON()});
document.getElementById('key-root').addEventListener('change',e=>{S.keyRoot=e.target.value;syncJSON()});
document.getElementById('key-mode').addEventListener('change',e=>{S.keyMode=e.target.value;syncJSON()});
document.getElementById('time-sig').addEventListener('change',e=>{
  const nextTimeSig=e.target.value;
  const prevTimeSig=S.timeSig;
  if(String(nextTimeSig)===String(prevTimeSig))return;
  remapEventBeatsForTimeSigChange(prevTimeSig,nextTimeSig);
  S.timeSig=nextTimeSig;
  syncCycleControls();
  render();
  syncJSON();
});
document.getElementById('measures').addEventListener('input',e=>{S.measures=clamp(parseInt(e.target.value)||8,1,256);syncCycleControls();render();syncJSON()});

setActiveTab(S.activeTab||'create');
