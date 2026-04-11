// ═══════════════════════════════════════════════
// SECTION ARRANGER
// ═══════════════════════════════════════════════
let sectionDragPayload=null;

function ensureSectionStateShape(){
  if(!Array.isArray(S.sections))S.sections=[];
  if(!Array.isArray(S.sectionTimeline))S.sectionTimeline=[];
  if(!Number.isInteger(S.sectionNextId)||S.sectionNextId<1)S.sectionNextId=1;
  if(!Number.isInteger(S.sectionNextTimelineId)||S.sectionNextTimelineId<1)S.sectionNextTimelineId=1;
  if(!Number.isInteger(S.sectionSelectedTimelineItemId))S.sectionSelectedTimelineItemId=null;
  if(!Array.isArray(S.sectionSelectedTimelineItemIds))S.sectionSelectedTimelineItemIds=[];
}

function getSelectedSectionTimelineItemIds(){
  ensureSectionStateShape();
  const selectedRaw=S.sectionSelectedTimelineItemIds.length
    ?S.sectionSelectedTimelineItemIds
    :(Number.isInteger(S.sectionSelectedTimelineItemId)?[S.sectionSelectedTimelineItemId]:[]);
  const selectedSet=new Set(selectedRaw.filter(Number.isInteger));
  return S.sectionTimeline.filter(item=>selectedSet.has(item.id)).map(item=>item.id);
}

function setSelectedSectionTimelineItemIds(idsRaw,anchorId=null){
  ensureSectionStateShape();
  const idSet=new Set((Array.isArray(idsRaw)?idsRaw:[]).filter(Number.isInteger));
  const ordered=S.sectionTimeline.filter(item=>idSet.has(item.id)).map(item=>item.id);
  S.sectionSelectedTimelineItemIds=ordered;
  if(ordered.length===0){
    S.sectionSelectedTimelineItemId=null;
    return;
  }
  const fallback=ordered[ordered.length-1];
  S.sectionSelectedTimelineItemId=ordered.includes(anchorId)?anchorId:fallback;
}

function applyTimelineCardSelection(itemId,event){
  const current=getSelectedSectionTimelineItemIds();
  const currentSet=new Set(current);
  const anchorId=Number.isInteger(S.sectionSelectedTimelineItemId)?S.sectionSelectedTimelineItemId:itemId;

  if(event.shiftKey){
    const itemIds=S.sectionTimeline.map(item=>item.id);
    const anchorIdx=itemIds.indexOf(anchorId);
    const targetIdx=itemIds.indexOf(itemId);
    if(anchorIdx<0||targetIdx<0){
      setSelectedSectionTimelineItemIds([itemId],itemId);
      return;
    }
    const lo=Math.min(anchorIdx,targetIdx);
    const hi=Math.max(anchorIdx,targetIdx);
    setSelectedSectionTimelineItemIds(itemIds.slice(lo,hi+1),itemId);
    return;
  }

  if(event.ctrlKey||event.metaKey){
    if(currentSet.has(itemId))currentSet.delete(itemId);
    else currentSet.add(itemId);
    const next=[...currentSet];
    setSelectedSectionTimelineItemIds(next,next.length?itemId:null);
    return;
  }

  setSelectedSectionTimelineItemIds([itemId],itemId);
}

function sectionNameFromIndex(index){
  const letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const safeIndex=Math.max(0,parseInt(index,10)||0);
  const letter=letters[safeIndex%letters.length];
  const suffix=Math.floor(safeIndex/letters.length);
  return suffix>0?`${letter}${suffix}`:letter;
}

function nextDefaultSectionName(){
  ensureSectionStateShape();
  const names=new Set(S.sections.map(section=>String(section.name||'').trim().toUpperCase()));
  let index=S.sections.length;
  for(let attempt=0;attempt<300;attempt++){
    const candidate=sectionNameFromIndex(index+attempt);
    if(!names.has(candidate.toUpperCase()))return candidate;
  }
  return `S${S.sections.length+1}`;
}

function sanitizeSectionName(name,fallback){
  const clean=String(name||'').replace(/\s+/g,' ').trim();
  if(clean)return clean.slice(0,24);
  return fallback;
}

function findSectionById(sectionId){
  return S.sections.find(section=>section.id===sectionId)||null;
}

function parseSectionBeat(raw){
  if(typeof raw==='number')return trimBeatNumber(Math.max(0,raw));
  if(raw===null||raw===undefined)return 0;
  return trimBeatNumber(Math.max(0,parseBeat(raw)));
}

function describeSectionRange(section){
  const span=Math.max(0,trimBeatNumber(section.endBeat-section.startBeat));
  const barSpan=trimBeatNumber(span/Math.max(1,bpm()));
  return `${beatLabel(section.startBeat)} -> ${beatLabel(section.endBeat)} (${barSpan} bars)`;
}

function sectionTimelineTotalBeats(){
  ensureSectionStateShape();
  let total=0;
  for(const item of S.sectionTimeline){
    const section=findSectionById(item.sectionId);
    if(!section)continue;
    const loops=Math.max(1,parseInt(item.loops,10)||1);
    const span=Math.max(0,trimBeatNumber(section.endBeat-section.startBeat));
    total+=span*loops;
  }
  return trimBeatNumber(total);
}

function sectionTimelineTotalBars(){
  return trimBeatNumber(sectionTimelineTotalBeats()/Math.max(1,bpm()));
}

function refreshSectionMeta(){
  const meta=document.getElementById('section-meta');
  if(!meta)return;
  const bars=sectionTimelineTotalBars();
  meta.textContent=`${bars} bars`;
}

function syncSectionControls(){
  ensureSectionStateShape();
  const addBtn=document.getElementById('btn-add-section');
  const hasCycle=!!getCycleRange();
  if(addBtn){
    addBtn.style.display=hasCycle?'inline-flex':'none';
    addBtn.disabled=!hasCycle;
  }
}

function createSectionFromCycle(){
  ensureSectionStateShape();
  const cycle=getCycleRange();
  if(!cycle)return false;

  const section={
    id:S.sectionNextId++,
    name:nextDefaultSectionName(),
    startBeat:trimBeatNumber(cycle.startBeat),
    endBeat:trimBeatNumber(cycle.endBeat),
  };
  S.sections.push(section);
  renderSectionView();
  syncSectionControls();
  syncJSON();
  return true;
}

function insertSectionTimelineItem(index,sectionId,loops=1){
  ensureSectionStateShape();
  const section=findSectionById(sectionId);
  if(!section)return false;

  const insertAt=clamp(parseInt(index,10)||0,0,S.sectionTimeline.length);
  const item={
    id:S.sectionNextTimelineId++,
    sectionId:section.id,
    loops:Math.max(1,parseInt(loops,10)||1),
  };
  S.sectionTimeline.splice(insertAt,0,item);
  setSelectedSectionTimelineItemIds([item.id],item.id);
  return true;
}

function moveSectionTimelineItem(itemId,targetIndex){
  const fromIndex=S.sectionTimeline.findIndex(item=>item.id===itemId);
  if(fromIndex<0)return false;

  const boundedTarget=clamp(parseInt(targetIndex,10)||0,0,S.sectionTimeline.length);
  const [item]=S.sectionTimeline.splice(fromIndex,1);
  let insertAt=boundedTarget;
  if(fromIndex<boundedTarget)insertAt=Math.max(0,boundedTarget-1);
  S.sectionTimeline.splice(insertAt,0,item);
  setSelectedSectionTimelineItemIds([item.id],item.id);
  return true;
}

function moveSectionTimelineItems(itemIdsRaw,targetIndex){
  const itemIds=(Array.isArray(itemIdsRaw)?itemIdsRaw:[]).filter(Number.isInteger);
  if(!itemIds.length)return false;

  const selectedSet=new Set(itemIds);
  const selectedItems=S.sectionTimeline.filter(item=>selectedSet.has(item.id));
  if(!selectedItems.length)return false;

  const boundedTarget=clamp(parseInt(targetIndex,10)||0,0,S.sectionTimeline.length);
  const selectedBeforeTarget=S.sectionTimeline
    .slice(0,boundedTarget)
    .filter(item=>selectedSet.has(item.id)).length;
  const insertAt=Math.max(0,boundedTarget-selectedBeforeTarget);

  const remaining=S.sectionTimeline.filter(item=>!selectedSet.has(item.id));
  remaining.splice(insertAt,0,...selectedItems);
  S.sectionTimeline=remaining;
  setSelectedSectionTimelineItemIds(selectedItems.map(item=>item.id),selectedItems[selectedItems.length-1]?.id||null);
  return true;
}

function clearHotDropSlots(){
  document.querySelectorAll('.timeline-drop-slot.hot').forEach(slot=>slot.classList.remove('hot'));
}

function applySectionDrop(insertIndex){
  if(!sectionDragPayload)return;
  let changed=false;
  if(sectionDragPayload.source==='library'){
    changed=insertSectionTimelineItem(insertIndex,sectionDragPayload.sectionId,1);
  }else if(sectionDragPayload.source==='timeline'){
    const ids=(Array.isArray(sectionDragPayload.itemIds)&&sectionDragPayload.itemIds.length)
      ?sectionDragPayload.itemIds
      :[sectionDragPayload.itemId];
    changed=moveSectionTimelineItems(ids,insertIndex);
  }
  sectionDragPayload=null;
  clearHotDropSlots();
  if(!changed)return;
  renderSectionView();
  syncJSON();
}

function renderSectionLibrary(){
  const library=document.getElementById('section-library');
  if(!library)return;
  library.innerHTML='';

  if(!S.sections.length){
    const empty=document.createElement('div');
    empty.className='section-empty';
    empty.style.minHeight='64px';
    empty.textContent='Create a cycle range in the chord lane, then press SECTION.';
    library.appendChild(empty);
    return;
  }

  for(const section of S.sections){
    const card=document.createElement('div');
    card.className='section-card';
    card.draggable=true;
    card.dataset.sectionId=String(section.id);

    const top=document.createElement('div');
    top.className='section-card-top';
    const range=document.createElement('div');
    range.className='section-card-range';
    range.textContent=describeSectionRange(section);
    top.appendChild(range);

    const nameInput=document.createElement('input');
    nameInput.className='section-name';
    nameInput.type='text';
    nameInput.maxLength=24;
    nameInput.value=section.name;
    nameInput.addEventListener('change',()=>{
      section.name=sanitizeSectionName(nameInput.value,section.name);
      nameInput.value=section.name;
      renderSectionView();
      syncJSON();
    });

    card.appendChild(top);
    card.appendChild(nameInput);

    card.addEventListener('dragstart',event=>{
      sectionDragPayload={source:'library',sectionId:section.id};
      event.dataTransfer.effectAllowed='copyMove';
      event.dataTransfer.setData('text/plain',`section:${section.id}`);
    });
    card.addEventListener('dragend',()=>{
      sectionDragPayload=null;
      clearHotDropSlots();
    });

    library.appendChild(card);
  }
}

function timelineItemDropSlot(index){
  const slot=document.createElement('div');
  slot.className='timeline-drop-slot';
  slot.dataset.insertIndex=String(index);

  slot.addEventListener('dragover',event=>{
    if(!sectionDragPayload)return;
    event.preventDefault();
    clearHotDropSlots();
    slot.classList.add('hot');
  });

  slot.addEventListener('dragleave',()=>slot.classList.remove('hot'));

  slot.addEventListener('drop',event=>{
    event.preventDefault();
    applySectionDrop(index);
  });

  return slot;
}

function removeSectionTimelineItem(itemId){
  const index=S.sectionTimeline.findIndex(item=>item.id===itemId);
  if(index<0)return false;
  S.sectionTimeline.splice(index,1);
  const remaining=getSelectedSectionTimelineItemIds().filter(id=>id!==itemId);
  if(remaining.length){
    setSelectedSectionTimelineItemIds(remaining,S.sectionSelectedTimelineItemId===itemId?remaining[remaining.length-1]:S.sectionSelectedTimelineItemId);
  }else{
    const next=S.sectionTimeline[index]||S.sectionTimeline[index-1]||null;
    setSelectedSectionTimelineItemIds(next?[next.id]:[],next?next.id:null);
  }
  return true;
}

function removeSectionTimelineItems(itemIdsRaw){
  const ids=(Array.isArray(itemIdsRaw)?itemIdsRaw:[]).filter(Number.isInteger);
  if(!ids.length)return false;
  const idSet=new Set(ids);
  const before=S.sectionTimeline.length;
  S.sectionTimeline=S.sectionTimeline.filter(item=>!idSet.has(item.id));
  if(S.sectionTimeline.length===before)return false;
  setSelectedSectionTimelineItemIds([],null);
  return true;
}

function renderSectionTimeline(){
  const timeline=document.getElementById('section-timeline');
  if(!timeline)return;
  timeline.ondragover=null;
  timeline.ondrop=null;
  timeline.innerHTML='';

  if(!S.sectionTimeline.length){
    const empty=document.createElement('div');
    empty.className='section-empty';
    empty.textContent='Drag sections here to build a composition timeline.';
    timeline.appendChild(empty);

    timeline.ondragover=event=>{
      if(!sectionDragPayload)return;
      event.preventDefault();
    };

    timeline.ondrop=event=>{
      event.preventDefault();
      applySectionDrop(0);
    };
    return;
  }

  for(let index=0;index<=S.sectionTimeline.length;index++){
    const slot=timelineItemDropSlot(index);
    if(index===S.sectionTimeline.length){
      slot.style.flex='1';
      slot.style.minWidth='14px';
    }
    timeline.appendChild(slot);
    if(index>=S.sectionTimeline.length)continue;

    const item=S.sectionTimeline[index];
    const section=findSectionById(item.sectionId);
    if(!section)continue;

    const loops=Math.max(1,parseInt(item.loops,10)||1);
    const spanBeat=Math.max(0,trimBeatNumber(section.endBeat-section.startBeat));
    const spanBars=trimBeatNumber((spanBeat*loops)/Math.max(1,bpm()));

    const card=document.createElement('div');
    const selectedSet=new Set(getSelectedSectionTimelineItemIds());
    card.className=`timeline-item${selectedSet.has(item.id)?' selected':''}`;
    card.draggable=true;
    card.dataset.timelineItemId=String(item.id);

    const head=document.createElement('div');
    head.className='timeline-item-head';
    const name=document.createElement('div');
    name.className='timeline-item-name';
    name.textContent=section.name;
    const remove=document.createElement('button');
    remove.className='timeline-remove';
    remove.type='button';
    remove.textContent='X';
    remove.addEventListener('click',event=>{
      event.stopPropagation();
      if(removeSectionTimelineItem(item.id)){
        renderSectionView();
        syncJSON();
      }
    });
    head.appendChild(name);
    head.appendChild(remove);

    const loopsRow=document.createElement('div');
    loopsRow.className='timeline-loops';
    const loopsLabel=document.createElement('label');
    loopsLabel.textContent='Loops';
    const loopsInput=document.createElement('input');
    loopsInput.type='number';
    loopsInput.min='1';
    loopsInput.max='64';
    loopsInput.step='1';
    loopsInput.value=String(loops);
    loopsInput.addEventListener('change',()=>{
      item.loops=clamp(parseInt(loopsInput.value,10)||1,1,64);
      loopsInput.value=String(item.loops);
      renderSectionView();
      syncJSON();
    });
    loopsRow.appendChild(loopsLabel);
    loopsRow.appendChild(loopsInput);

    const range=document.createElement('div');
    range.className='timeline-item-range';
    range.textContent=`${describeSectionRange(section)} x ${loops} = ${spanBars} bars`;

    card.appendChild(head);
    card.appendChild(loopsRow);
    card.appendChild(range);

    card.addEventListener('click',event=>{
      applyTimelineCardSelection(item.id,event);
      renderSectionView();
    });

    card.addEventListener('dragstart',event=>{
      const currentSelected=new Set(getSelectedSectionTimelineItemIds());
      if(!currentSelected.has(item.id)){
        setSelectedSectionTimelineItemIds([item.id],item.id);
      }
      const selectedIds=getSelectedSectionTimelineItemIds();
      sectionDragPayload={source:'timeline',itemId:item.id,itemIds:selectedIds};
      event.dataTransfer.effectAllowed='move';
      event.dataTransfer.setData('text/plain',`timeline:${item.id}`);
    });

    card.addEventListener('dragend',()=>{
      sectionDragPayload=null;
      clearHotDropSlots();
    });

    timeline.appendChild(card);
  }
}

function renderSectionView(){
  ensureSectionStateShape();
  renderSectionLibrary();
  renderSectionTimeline();
  refreshSectionMeta();
}

function copySelectedSectionTimelineItem(){
  if(S.activeTab!=='sections')return false;
  ensureSectionStateShape();
  const selectedIds=getSelectedSectionTimelineItemIds();
  if(!selectedIds.length)return false;
  const items=S.sectionTimeline
    .filter(item=>selectedIds.includes(item.id))
    .map(item=>({sectionId:item.sectionId,loops:Math.max(1,parseInt(item.loops,10)||1)}));
  if(!items.length)return false;
  S.sectionClipboard={items};
  return true;
}

function pasteSelectedSectionTimelineItem(){
  if(S.activeTab!=='sections')return false;
  ensureSectionStateShape();
  const clipboardItems=Array.isArray(S.sectionClipboard?.items)?S.sectionClipboard.items:[];
  if(!clipboardItems.length)return false;

  const selectedIds=getSelectedSectionTimelineItemIds();
  let insertIndex=S.sectionTimeline.length;
  if(selectedIds.length){
    const selectedSet=new Set(selectedIds);
    for(let i=S.sectionTimeline.length-1;i>=0;i--){
      if(!selectedSet.has(S.sectionTimeline[i].id))continue;
      insertIndex=i+1;
      break;
    }
  }

  const created=[];
  for(const entry of clipboardItems){
    const ok=insertSectionTimelineItem(insertIndex,entry.sectionId,entry.loops);
    if(!ok)continue;
    created.push(S.sectionSelectedTimelineItemId);
    insertIndex+=1;
  }
  if(!created.length)return false;
  setSelectedSectionTimelineItemIds(created,created[created.length-1]);
  renderSectionView();
  syncJSON();
  return true;
}

function deleteSelectedSectionTimelineItem(){
  if(S.activeTab!=='sections')return false;
  const selectedIds=getSelectedSectionTimelineItemIds();
  if(!selectedIds.length)return false;
  const removed=removeSectionTimelineItems(selectedIds);
  if(!removed)return false;
  renderSectionView();
  syncJSON();
  return true;
}

function onTabChanged(tab){
  const seq=document.getElementById('seq');
  const insp=document.getElementById('insp');
  const sectionView=document.getElementById('section-view');
  const uploadBtn=document.getElementById('btn-upload');
  const isSections=tab==='sections';

  if(seq)seq.style.display=isSections?'none':'flex';
  if(sectionView)sectionView.style.display=isSections?'flex':'none';
  if(insp)insp.style.display=isSections?'none':'';
  if(isSections&&typeof closeInsp==='function')closeInsp();

  if(uploadBtn){
    uploadBtn.textContent=isSections?'⇪ Upload Sections':'⇪ Upload to Bot';
  }

  if(isSections)renderSectionView();
  syncSectionControls();
  if(typeof resize==='function')requestAnimationFrame(()=>resize());
}

const addSectionButton=document.getElementById('btn-add-section');
if(addSectionButton){
  addSectionButton.addEventListener('click',()=>createSectionFromCycle());
}

// ── SECTION EXPORT MODAL ──

function openSectionExportModal(){
  document.getElementById('section-export-modal')?.classList.add('on');
}

function closeSectionExportModal(){
  document.getElementById('section-export-modal')?.classList.remove('on');
}

document.getElementById('btn-export-sections')?.addEventListener('click',openSectionExportModal);
document.getElementById('btn-close-section-export')?.addEventListener('click',closeSectionExportModal);

document.getElementById('section-export-modal')?.addEventListener('click',e=>{
  if(e.target===e.currentTarget)closeSectionExportModal();
});

document.getElementById('btn-sec-export-json')?.addEventListener('click',()=>{
  closeSectionExportModal();
  // Export the sections-expanded (flat) JSON
  const expanded=buildSectionExpandedJSON();
  const data=expanded||buildJSON();
  const base=(S.songName.replace(/[^a-z0-9_\-]/gi,'_').toLowerCase()||'song');
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  saveBlobWithAnchor(blob,`${base}_expanded.json`);
});

document.getElementById('btn-sec-export-midi')?.addEventListener('click',()=>{
  closeSectionExportModal();
  exportUsingNativePicker('midi').then(usedNative=>{
    if(!usedNative)exportMidiViaAnchor();
  });
});

document.getElementById('btn-sec-export-seq')?.addEventListener('click',()=>{
  closeSectionExportModal();
  const expanded=buildSectionExpandedJSON();
  if(!expanded){
    alert('No section timeline to export.');
    return;
  }
  // Strip the original sections/timeline so the expanded flat events load
  // cleanly without section guides appearing at old boundaries.
  const flat={
    song:{
      ...expanded.song,
      arrangement:{sections:[],timeline:[]},
    },
  };
  loadJSON(flat);
  if(typeof setActiveTab==='function')setActiveTab('create');
});

window.syncSectionControls=syncSectionControls;
window.renderSectionView=renderSectionView;
window.onTabChanged=onTabChanged;
window.copySelectedSectionTimelineItem=copySelectedSectionTimelineItem;
window.pasteSelectedSectionTimelineItem=pasteSelectedSectionTimelineItem;
window.deleteSelectedSectionTimelineItem=deleteSelectedSectionTimelineItem;
window.sectionTimelineTotalBeats=sectionTimelineTotalBeats;

syncSectionControls();
renderSectionView();
