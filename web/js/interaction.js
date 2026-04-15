// ═══════════════════════════════════════════════
// INTERACTION
// ═══════════════════════════════════════════════
let drag=null;
let seqContextClickBeat=0;
let seqContextClientX=0;
let seqContextClientY=0;
let insertSilenceBeat=0;

function hitStringTrackControl(cx,cy){
  for(let index=0;index<STRINGS.length;index++){
    const rects=stringTrackControlRects(index);
    if(!rects)continue;
    const inside=(r)=>cx>=r.x&&cx<=r.x+r.w&&cy>=r.y&&cy<=r.y+r.h;
    if(inside(rects.solo))return {index,control:'solo'};
    if(inside(rects.mute))return {index,control:'mute'};
  }
  return null;
}

function closeSequencerContextMenu(){
  const menu=document.getElementById('seq-ctx-menu');
  if(menu)menu.classList.remove('on');
}

function closeInsertSilencePopup(){
  const pop=document.getElementById('insert-silence-pop');
  if(pop)pop.classList.remove('on');
}

function placePopupNearClientPoint(pop,clientX,clientY){
  if(!pop)return;

  const margin=8;
  const left=Math.max(margin,Math.min(window.innerWidth-pop.offsetWidth-margin,clientX+8));
  const top=Math.max(margin,Math.min(window.innerHeight-pop.offsetHeight-margin,clientY+8));
  pop.style.left=`${left}px`;
  pop.style.top=`${top}px`;
}

function openSequencerContextMenu(clientX,clientY,beat){
  const menu=document.getElementById('seq-ctx-menu');
  if(!menu)return;

  seqContextClickBeat=Math.max(0,trimBeatNumber(parseFloat(beat)||0));
  seqContextClientX=clientX;
  seqContextClientY=clientY;

  closeInsertSilencePopup();
  menu.classList.add('on');
  placePopupNearClientPoint(menu,clientX,clientY);
}

function openInsertSilencePopup(clientX,clientY,beat){
  const pop=document.getElementById('insert-silence-pop');
  const barsInput=document.getElementById('insert-silence-bars');
  const atLabel=document.getElementById('insert-silence-at');
  if(!pop||!barsInput||!atLabel)return;

  insertSilenceBeat=Math.max(0,trimBeatNumber(parseFloat(beat)||0));
  atLabel.textContent=`At: ${beatLabel(insertSilenceBeat)}`;
  barsInput.value='1';

  closeSequencerContextMenu();
  pop.classList.add('on');
  placePopupNearClientPoint(pop,clientX,clientY);

  barsInput.focus();
  barsInput.select();
}

function shiftEventBeat(ev,insertBeat,deltaBeats){
  if(!ev||ev.beat===undefined||ev.beat===null)return;
  const eventBeat=parseBeat(ev.beat);
  if(eventBeat+1e-6<insertBeat)return;
  ev.beat=beatLabel(eventBeat+deltaBeats);
}

function insertSilenceAtBeat(insertBeat,barsToInsertRaw){
  const beatsPerBar=bpm();
  const barsToInsert=clamp(Math.round(parseFloat(barsToInsertRaw)||0),1,64);
  const startBeat=Math.max(0,trimBeatNumber(parseFloat(insertBeat)||0));
  const deltaBeats=barsToInsert*beatsPerBar;

  S.pluck.forEach(ev=>shiftEventBeat(ev,startBeat,deltaBeats));
  (S.harmonic||[]).forEach(ev=>shiftEventBeat(ev,startBeat,deltaBeats));
  S.chord.forEach(ev=>shiftEventBeat(ev,startBeat,deltaBeats));
  S.midi.forEach(ev=>shiftEventBeat(ev,startBeat,deltaBeats));

  for(const laneKey of MIDI_AUTOMATION_KEYS){
    const key=String(laneKey);
    const points=S.midiCurves[key]||[];
    const shifted=points.map(point=>{
      const beatVal=parseFloat(point?.beat);
      if(!Number.isFinite(beatVal)||beatVal+1e-6<startBeat)return point;
      return {...point,beat:trimBeatNumber(beatVal+deltaBeats)};
    });
    S.midiCurves[key]=normalizeMidiCurvePoints(shifted,key);
  }

  let maxBeatEnd=0;
  for(const ev of S.pluck){
    const b=parseBeat(ev.beat);
    const d=Math.max(0,parseFloat(ev.duration_b)||0);
    maxBeatEnd=Math.max(maxBeatEnd,b+d);
  }
  for(const ev of S.chord)maxBeatEnd=Math.max(maxBeatEnd,parseBeat(ev.beat));
  for(const ev of (S.harmonic||[]))maxBeatEnd=Math.max(maxBeatEnd,parseBeat(ev.beat));
  for(const ev of S.midi)maxBeatEnd=Math.max(maxBeatEnd,parseBeat(ev.beat));
  for(const laneKey of MIDI_AUTOMATION_KEYS){
    const key=String(laneKey);
    for(const point of (S.midiCurves[key]||[])){
      const b=parseFloat(point?.beat);
      if(Number.isFinite(b))maxBeatEnd=Math.max(maxBeatEnd,b);
    }
  }

  const requiredMeasures=Math.max(1,Math.ceil(maxBeatEnd/Math.max(1,beatsPerBar)));
  const requestedMeasures=S.measures+barsToInsert;
  const unclampedMeasures=Math.max(requestedMeasures,requiredMeasures);
  S.measures=clamp(Math.round(unclampedMeasures),1,64);

  if(S.cycleEnabled){
    let cycleStartBeat=(parseFloat(S.cycleStartBar)||1)-1;
    cycleStartBeat*=beatsPerBar;
    let cycleEndBeat=(parseFloat(S.cycleEndBar)||1)*beatsPerBar;

    if(cycleStartBeat+1e-6>=startBeat)cycleStartBeat+=deltaBeats;
    if(cycleEndBeat+1e-6>=startBeat)cycleEndBeat+=deltaBeats;

    S.cycleStartBar=(cycleStartBeat/beatsPerBar)+1;
    S.cycleEndBar=(cycleEndBeat/beatsPerBar);
  }

  syncCycleControls();
  syncJSON();
  render();

  if(typeof showImportToast==='function'){
    const clipped=unclampedMeasures>S.measures;
    const message=clipped
      ? `Inserted ${barsToInsert} bar${barsToInsert===1?'':'s'} of silence at ${beatLabel(startBeat)} (timeline capped at ${S.measures} bars).`
      : `Inserted ${barsToInsert} bar${barsToInsert===1?'':'s'} of silence at ${beatLabel(startBeat)}.`;
    showImportToast(message,2600);
  }
}

function applyInsertSilenceFromPopup(){
  const barsInput=document.getElementById('insert-silence-bars');
  if(!barsInput)return;
  insertSilenceAtBeat(insertSilenceBeat,barsInput.value);
  closeInsertSilencePopup();
}

document.getElementById('seq-ctx-insert-playhead').addEventListener('click',()=>{
  openInsertSilencePopup(seqContextClientX,seqContextClientY,S.playBeat);
});

document.getElementById('seq-ctx-insert-here').addEventListener('click',()=>{
  openInsertSilencePopup(seqContextClientX,seqContextClientY,seqContextClickBeat);
});

document.getElementById('insert-silence-apply').addEventListener('click',applyInsertSilenceFromPopup);
document.getElementById('insert-silence-cancel').addEventListener('click',closeInsertSilencePopup);
document.getElementById('insert-silence-close').addEventListener('click',closeInsertSilencePopup);
document.getElementById('insert-silence-bars').addEventListener('keydown',e=>{
  if(e.key==='Enter'){
    e.preventDefault();
    applyInsertSilenceFromPopup();
  }
});

document.addEventListener('pointerdown',e=>{
  const menu=document.getElementById('seq-ctx-menu');
  const silencePop=document.getElementById('insert-silence-pop');
  if(menu&&!menu.contains(e.target))closeSequencerContextMenu();
  if(silencePop&&!silencePop.contains(e.target))closeInsertSilencePopup();
});

canvas.addEventListener('contextmenu',e=>{
  e.preventDefault();
  const r=canvas.getBoundingClientRect();
  const cx=e.clientX-r.left, cy=e.clientY-r.top;
  if(cx<LABEL_W)return;

  if(typeof hideNoteWarningPopover==='function')hideNoteWarningPopover();
  closeCPop();
  closeMPop();
  closeMLPop();

  const clickedBeat=normalizePlacementBeat(Math.max(0,xToBeat(cx)));
  openSequencerContextMenu(e.clientX,e.clientY,clickedBeat);
});

canvas.addEventListener('pointerdown',e=>{
  if(e.button!==0)return;
  if(typeof hideNoteWarningPopover==='function')hideNoteWarningPopover();
  canvas.setPointerCapture(e.pointerId);
  const r=canvas.getBoundingClientRect();
  const cx=e.clientX-r.left, cy=e.clientY-r.top;
  closeCPop(); closeMPop(); closeMLPop();
  const myY=midiTopY();

  if(cy<CHORD_H){chordDown(cx,cy,e);return}
  if(cy>=myY){midiDown(cx,cy,e);return}

  // Vertical zoom drag on label column
  if(cx<LABEL_W){
    const stringCtl=hitStringTrackControl(cx,cy);
    if(stringCtl){
      if(stringCtl.control==='solo'){
        S.stringSoloIndex=(S.stringSoloIndex===stringCtl.index)?null:stringCtl.index;
      }else if(stringCtl.control==='mute'){
        S.stringMuted[stringCtl.index]=!S.stringMuted[stringCtl.index];
      }
      syncJSON();
      render();
      return;
    }
    drag={type:'vzoom',sy:e.clientY,startNoteH:noteH};
    return;
  }

  if(S.editMode==='draw'){
    const hit=hitPluck(cx,cy);
    if(hit){
      const bx=beatToX(parseBeat(hit.beat)), hw=Math.max(8,hit.duration_b*S.zoom);
      const isResizeR=cx>=bx+hw-6&&cx<=bx+hw+3;
      const isResizeL=cx>=bx-3&&cx<=bx+6;
      if(isResizeL||isResizeR){
        drag={type:'resize',id:hit.id,sx:cx,edge:isResizeL?'left':'right',os:parseBeat(hit.beat),oe:parseBeat(hit.beat)+hit.duration_b};
      } else {
        drag={type:'drag',id:hit.id,sx:cx,sy:cy,
          ob:parseBeat(hit.beat),on:hit.note,
          bo:parseBeat(hit.beat)-xToBeat(cx),
          no:hit.note-yToNote(cy)};
      }
      selPluck(hit.id);
    } else if(cx>=LABEL_W){
      const b=normalizePlacementBeat(Math.max(0,xToBeat(cx)));
      const n=clampNote(yToNote(cy));
      if(b<totalBeats() && S.activeTab !== 'automation')addNote(b,n);
      deselectAll();
    }
  } else {
    if(cx<LABEL_W)return;
    const clickedBeat=normalizePlacementBeat(Math.max(0,xToBeat(cx)));
    const clickedNote=clampNote(yToNote(cy));
    S.pasteAnchor={
      beat:clickedBeat,
      note:clickedNote,
    };
    const hit=hitPluck(cx,cy);
    if(hit){
      const start=parseBeat(hit.beat);
      const end=start+hit.duration_b;
      const x1=beatToX(start), x2=beatToX(end);
      const isResizeL=Math.abs(cx-x1)<=6;
      const isResizeR=Math.abs(cx-x2)<=6;
      if(isResizeL||isResizeR){
        drag={type:'resize',id:hit.id,sx:cx,edge:isResizeL?'left':'right',os:start,oe:end};
        selPluck(hit.id);
      } else {
        const selectedIds=S.selPluckIds.size?[...S.selPluckIds]:[];
        const shouldDragGroup=selectedIds.length>1&&S.selPluckIds.has(hit.id);
        if(!shouldDragGroup){
          selPluck(hit.id);
        }
        const ids=shouldDragGroup?selectedIds:[hit.id];
        const noteOffsets=ids.map(id=>{
          const ev=S.pluck.find(p=>p.id===id);
          return ev?{id,noteOffset:ev.note-clickedNote}:{id,noteOffset:0};
        });
        drag={
          type:'drag-group',
          ids,
          sxBeat:xToBeat(cx),
          syNote:clickedNote,
          startById:new Map(ids.map(id=>{
            const ev=S.pluck.find(p=>p.id===id);
            return [id,ev?{beat:parseBeat(ev.beat),note:ev.note}:{beat:0,note:clickedNote}];
          })),
          noteOffsets,
        };
      }
    } else {
      drag={type:'select-box',sx:cx,sy:cy,cx,cy,hitId:null,moved:false,clickBeat:clickedBeat};
    }
  }
  render();
});

canvas.addEventListener('pointermove',e=>{
  const r=canvas.getBoundingClientRect();
  const cx=e.clientX-r.left, cy=e.clientY-r.top;
  if(!drag){
    if(typeof updateNoteWarningHover==='function'&&updateNoteWarningHover(cx,cy,e.clientX,e.clientY)){
      canvas.style.cursor='pointer';
      return;
    }
    updateHoverCursor(cx,cy);
    return;
  }
  if(drag.type==='midi-curve'){
    const beat=normalizeBeat(clamp(xToBeat(cx),0,totalBeats()));
    const value=midiValueFromY(cy,drag.lane);
    if(S.snapEnabled&&typeof drag.lastBeat==='number'&&Math.abs(beat-drag.lastBeat)>1e-4){
      clearMidiCurveRange(drag.key,drag.lastBeat,beat);
    }
    upsertMidiCurvePoint(drag.key,beat,value);
    drag.lastBeat=beat;
    render();
    return;
  }
  if(drag.type==='cycle-select'){
    const cursorBeat=normalizeBeat(Math.max(0,xToBeat(cx)));
    setCycleRangeFromBeats(drag.startBeat,cursorBeat,true);
    render();
    return;
  }
  if(drag.type==='cycle-resize'){
    const cursorBeat=normalizeBeat(Math.max(0,xToBeat(cx)));
    const m=bpm();
    const cycle=getCycleRange();
    if(!cycle)return;
    const minDur=minDurationBeats();
    if(drag.edge==='left'){
      const newStartBeat=Math.min(cursorBeat,cycle.endBeat-minDur);
      S.cycleStartBar=newStartBeat/m+1;
    } else {
      const newEndBeat=Math.max(cursorBeat,cycle.startBeat+minDur);
      S.cycleEndBar=newEndBeat/m;
    }
    syncCycleControls();
    render();
    return;
  }
  if(drag.type==='cycle-move'){
    const m=bpm();
    let deltaBeats=xToBeat(cx)-drag.startBeat;
    if(S.snapEnabled)deltaBeats=snap(deltaBeats);
    const startBeat=(drag.startBar-1)*m;
    const endBeat=drag.endBar*m;
    const spanBeats=endBeat-startBeat;
    let newStartBeat=startBeat+deltaBeats;
    newStartBeat=clamp(newStartBeat,0,S.measures*m-spanBeats);
    S.cycleStartBar=newStartBeat/m+1;
    S.cycleEndBar=(newStartBeat+spanBeats)/m;
    syncCycleControls();
    render();
    return;
  }
  if(drag.type==='vzoom'){
    const dy=e.clientY-drag.sy;
    noteH=clamp(Math.round(drag.startNoteH+dy*0.3),noteH_MIN,noteH_MAX);
    resize();
    return;
  }
  if(drag.type==='select-box'){
    drag.cx=cx;
    drag.cy=cy;
    drag.moved=drag.moved||Math.abs(drag.cx-drag.sx)>3||Math.abs(drag.cy-drag.sy)>3;
    render();
    return;
  }
  if(drag.type==='drag-group'){
    const beatDelta=normalizeBeat(xToBeat(cx)-drag.sxBeat);
    const noteBase=clampNote(yToNote(cy));
    const dragSet=new Set(drag.ids);
    // Check all moves first; if any collide with non-group notes, skip entire move
    let blocked=false;
    for(const id of drag.ids){
      const ev=S.pluck.find(p=>p.id===id);
      const start=drag.startById.get(id);
      const offs=drag.noteOffsets.find(o=>o.id===id);
      if(!ev||!start||!offs)continue;
      const nb=Math.max(0,start.beat+beatDelta);
      const nn=clampNote(noteBase+offs.noteOffset);
      for(const other of S.pluck){
        if(dragSet.has(other.id))continue;
        if(notesOverlap(nb,ev.duration_b,nn,parseBeat(other.beat),other.duration_b,other.note)){blocked=true;break;}
      }
      if(blocked)break;
    }
    if(!blocked){
      for(const id of drag.ids){
        const ev=S.pluck.find(p=>p.id===id);
        const start=drag.startById.get(id);
        const offs=drag.noteOffsets.find(o=>o.id===id);
        if(!ev||!start||!offs)continue;
        ev.beat=beatLabel(Math.max(0,start.beat+beatDelta));
        ev.note=clampNote(noteBase+offs.noteOffset);
        if(S.selPluck===ev.id)refreshInspNote(ev);
      }
    }
    render();
    return;
  }
  const ev=S.pluck.find(p=>p.id===drag.id);
  if(!ev)return;
  if(drag.type==='drag'){
    const newBeat=normalizeBeat(Math.max(0,xToBeat(cx)+drag.bo));
    const newNote=clampNote(yToNote(cy)+drag.no);
    if(!hasCollision(newBeat,ev.duration_b,newNote,ev.id)){
      ev.beat=beatLabel(newBeat);
      ev.note=newNote;
    }
    if(S.selPluck===ev.id)refreshInspNote(ev);
  } else {
    const cursorBeat=normalizeBeat(Math.max(0,xToBeat(cx)));
    const minDur=minDurationBeats();
    if(drag.edge==='left'){
      const newStart=Math.min(cursorBeat,drag.oe-minDur);
      const newDur=trimBeatNumber(Math.max(minDur,drag.oe-newStart));
      if(!hasCollision(newStart,newDur,ev.note,ev.id)){
        ev.beat=beatLabel(newStart);
        ev.duration_b=newDur;
      }
    } else {
      const newEnd=Math.max(cursorBeat,drag.os+minDur);
      const newDur=trimBeatNumber(Math.max(minDur,newEnd-drag.os));
      if(!hasCollision(parseBeat(ev.beat),newDur,ev.note,ev.id)){
        ev.duration_b=newDur;
      }
    }
    if(S.selPluck===ev.id)refreshInspDur(ev);
  }
  render();
});

canvas.addEventListener('pointerleave',()=>{
  if(typeof hideNoteWarningPopover==='function')hideNoteWarningPopover();
  canvas.style.cursor=S.editMode==='draw'?'default':'crosshair';
});

canvas.addEventListener('pointerup',()=>{
  if(!drag)return;
  if(drag.type==='midi-curve'){
    syncJSON();
    drag=null;
    render();
    return;
  }
  if(drag.type==='cycle-move'||drag.type==='cycle-resize'){
    drag=null;
    render();
    return;
  }
  if(drag.type==='cycle-select'){
    drag=null;
    render();
    return;
  }
  if(drag.type==='select-box'){
    if(!drag.moved&&typeof drag.clickBeat==='number')setPlayheadBeat(drag.clickBeat);
    applySelectionBox(drag);
    drag=null;
    render();
    return;
  }
  syncJSON();
  drag=null;
});

canvas.addEventListener('dblclick',e=>{
  const r=canvas.getBoundingClientRect();
  const cx=e.clientX-r.left;
  const cy=e.clientY-r.top;

  const lane=midiLaneAtY(cy);
  if(cx<LABEL_W&&lane>=0&&lane!==MIDI_GENERAL_LANE_INDEX){
    S.focusedCCLane=(S.focusedCCLane===lane)?null:lane;
    render();
    return;
  }

  if(cx>=LABEL_W&&cy<CHORD_H){
    const b=normalizePlacementBeat(Math.max(0,xToBeat(cx)));
    if(b<totalBeats() && S.activeTab !== 'automation'){
      addChord(b);
      render();
    }
    return;
  }

  if(S.editMode==='draw')return;
  const myY=midiTopY();
  if(cx<LABEL_W||cy<CHORD_H||cy>=myY)return;

  const hit=hitPluck(cx,cy);
  if(hit){rmPluck(hit.id);render();}
});

function applySelectionBox(box){
  if(!box.moved){
    if(box.hitId!==null){
      selPluck(box.hitId);
      return;
    }
    deselectAll();
    return;
  }

  const x1=Math.min(box.sx,box.cx), x2=Math.max(box.sx,box.cx);
  const y1=Math.min(box.sy,box.cy), y2=Math.max(box.sy,box.cy);
  const ids=[];
  const selectedCurves=createEmptyMidiCurveSelection();

  for(const ev of S.pluck){
    if(S.activeTab === 'automation') break;
    const x=beatToX(parseBeat(ev.beat));
    const y=noteToY(ev.note);
    const w=Math.max(8,ev.duration_b*S.zoom);
    const nx1=x, nx2=x+w, ny1=y+1, ny2=y+noteH-1;
    const overlaps=!(nx2<x1||nx1>x2||ny2<y1||ny1>y2);
    if(overlaps)ids.push(ev.id);
  }

  for(let lane=0;lane<MIDI_AUTOMATION_KEYS.length;lane++){
    const laneKey=automationLaneKey(lane);
    if(!midiLaneVisible(lane))continue;
    const key=String(laneKey);
    for(const point of S.midiCurves[key]||[]){
      const x=beatToX(point.beat);
      const y=midiYFromValue(point.value,lane);
      const overlaps=x>=x1&&x<=x2&&y>=y1&&y<=y2;
      if(!overlaps)continue;
      selectedCurves[key].add(midiCurvePointKey(point.beat));
    }
  }

  const hasCurveSelection=MIDI_AUTOMATION_KEYS.some(key=>selectedCurves[String(key)].size>0);
  if(!ids.length&&!hasCurveSelection){
    deselectAll();
    return;
  }

  S.selPluckIds=new Set(ids);
  S.selPluck=ids.length===1?ids[0]:null;
  S.selChord=null;
  S.selMidi=null;
  S.selMidiCurvePoints=selectedCurves;
  if(ids.length)refreshInspectorForSelection();
  else closeInsp();
}

function chordDown(cx,cy,e){
  if(cx<LABEL_W)return;
  const hit=hitChord(cx,cy);
  if(hit){
    selChord(hit.id);
    showCPop(hit,e.clientX,e.clientY);
    return;
  }
  const startBeat=normalizePlacementBeat(Math.max(0,xToBeat(cx)));
  drag={type:'cycle-select',startBeat};
  setCycleRangeFromBeats(startBeat,startBeat+minDurationBeats(),true);
  render();
}
function midiDown(cx,cy,e){
  if(cx<LABEL_W)return;
  const lane=midiLaneAtY(cy);
  if(lane<0)return;
  const beat=normalizePlacementBeat(clamp(xToBeat(cx),0,totalBeats()));
  S.pasteAnchor={beat,note:MIDI_MIN};

  if(lane!==MIDI_GENERAL_LANE_INDEX){
    const laneKey=automationLaneKey(lane);
    if(S.editMode==='draw'){
      const value=midiValueFromY(cy,lane);
      upsertMidiCurvePoint(laneKey,beat,value);
      drag={type:'midi-curve',key:laneKey,lane,lastBeat:beat};
      render();
      syncJSON();
      return;
    }

    const hit=hitMidiCurvePoint(cx,cy);
    if(hit&&String(hit.key)===String(laneKey)){
      const selected=createEmptyMidiCurveSelection();
      const point=(S.midiCurves[String(laneKey)]||[])[hit.index];
      if(point)selected[String(laneKey)].add(midiCurvePointKey(point.beat));
      S.selPluckIds.clear();
      S.selPluck=null;
      S.selChord=null;
      S.selMidi=null;
      S.selMidiCurvePoints=selected;
      closeInsp();
      render();
      return;
    }

    drag={type:'select-box',sx:cx,sy:cy,cx,cy,hitId:null,moved:false,clickBeat:beat};
    render();
    return;
  }
  const hit=hitMidi(cx,cy);
  if(hit){selMidi(hit.id);showMPop(hit,e.clientX,e.clientY)}
  else if(S.editMode==='draw'){if(beat<totalBeats()){addMidi(beat);render()}}
  else {deselectAll(); render();}
}

function hitPluck(cx,cy){
  if(S.activeTab === 'automation') return null;
  for(const ev of S.pluck){
    const x=beatToX(parseBeat(ev.beat)),y=noteToY(ev.note),w=Math.max(8,ev.duration_b*S.zoom);
    if(cx>=x&&cx<=x+w&&cy>=y+1&&cy<=y+noteH-1)return ev;
  }return null;
}

function getPluckEdgeHit(cx,cy){
  const hit=hitPluck(cx,cy);
  if(!hit)return null;
  const startX=beatToX(parseBeat(hit.beat));
  const endX=startX+Math.max(8,hit.duration_b*S.zoom);
  if(Math.abs(cx-startX)<=6)return{ev:hit,edge:'left'};
  if(Math.abs(cx-endX)<=6)return{ev:hit,edge:'right'};
  return null;
}

function updateHoverCursor(cx,cy){
  const myY=midiTopY();
  if(cx>=LABEL_W&&cy<CHORD_H){
    canvas.style.cursor='crosshair';
    return;
  }
  if(cx<LABEL_W&&cy>=CHORD_H&&cy<myY){
    canvas.style.cursor='ns-resize';
    return;
  }
  if(cx<LABEL_W||cy<CHORD_H||cy>=myY){
    if(cy>=myY&&cy<myY+MIDI_H){
      const lane=midiLaneAtY(cy);
      canvas.style.cursor=lane>=0&&lane!==MIDI_GENERAL_LANE_INDEX?'crosshair':'default';
      return;
    }
    canvas.style.cursor=S.editMode==='draw'?'default':'crosshair';
    return;
  }
  const edgeHit=getPluckEdgeHit(cx,cy);
  if(edgeHit){
    canvas.style.cursor='ew-resize';
    return;
  }
  canvas.style.cursor=S.editMode==='draw'?'default':'crosshair';
}
function hitChord(cx,cy){
  if(S.activeTab === 'automation') return null;
  for(const ev of S.chord){
    const x=beatToX(parseBeat(ev.beat)),fw=Math.max(36,ev.chord.length*8+10);
    if(cx>=x-4&&cx<=x+fw&&cy>=4&&cy<=CHORD_H-4)return ev;
  }return null;
}
function hitMidi(cx,cy){
  if(midiLaneAtY(cy)!==MIDI_GENERAL_LANE_INDEX)return null;
  const cy2=midiLaneTop(MIDI_GENERAL_LANE_INDEX)+midiLaneHeight(MIDI_GENERAL_LANE_INDEX)/2;
  for(const ev of S.midi){
    const x=beatToX(parseBeat(ev.beat));
    if(Math.abs(cx-x)<10&&Math.abs(cy-cy2)<10)return ev;
  }return null;
}

function midiCCFromEvent(ev){
  if(!ev||ev.address!=='/cc'||!Array.isArray(ev.args)||ev.args.length<1)return null;
  const cc=parseInt(ev.args[0],10);
  return Number.isFinite(cc)?cc:null;
}

function findMidiCCCollision(beat,cc,excludeId=null){
  if(!Number.isFinite(cc))return null;
  const targetBeat=trimBeatNumber(Math.max(0,parseFloat(beat)||0));
  for(const ev of S.midi){
    if(excludeId!==null&&ev.id===excludeId)continue;
    if(midiCCFromEvent(ev)!==cc)continue;
    const b=trimBeatNumber(parseBeat(ev.beat));
    if(Math.abs(b-targetBeat)<1e-4)return ev;
  }
  return null;
}

function hitMidiCurvePoint(cx,cy){
  if(cx<LABEL_W)return null;
  const hitRadius=5;
  for(let lane=0;lane<MIDI_AUTOMATION_KEYS.length;lane++){
    const laneKey=automationLaneKey(lane);
    if(!midiLaneVisible(lane))continue;
    const points=[...(S.midiCurves[String(laneKey)]||[])].sort((a,b)=>a.beat-b.beat);
    for(let index=0;index<points.length;index++){
      const point=points[index];
      const x=beatToX(point.beat);
      const y=midiYFromValue(point.value,lane);
      if(Math.abs(cx-x)<=hitRadius&&Math.abs(cy-y)<=hitRadius){
        return {key:laneKey,index};
      }
    }
  }
  return null;
}

function dedupeMidiCCCollisions(keepId){
  const keep=S.midi.find(ev=>ev.id===keepId);
  if(!keep)return;
  const keepBeat=trimBeatNumber(parseBeat(keep.beat));
  S.midi=S.midi.filter(ev=>{
    if(ev.id===keepId)return true;
    return Math.abs(trimBeatNumber(parseBeat(ev.beat))-keepBeat)>=1e-4;
  });
}

canvas.addEventListener('wheel',e=>{
  e.preventDefault();
  if(e.ctrlKey||e.metaKey){
    const oldZoom=S.zoom;
    S.zoom=clamp(S.zoom*(e.deltaY>0?0.88:1.14),18,320);
    S.scrollX+=S.playBeat*(S.zoom-oldZoom);
  } else {
    const maxScroll=Math.max(0,totalBeats()*S.zoom-CW+LABEL_W+80);
    S.scrollX=clamp(S.scrollX+(e.shiftKey?e.deltaY:e.deltaX)*0.8,0,maxScroll);
  }
  render();
},{passive:false});
