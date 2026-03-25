// ═══════════════════════════════════════════════
// JSON PREVIEW
// ═══════════════════════════════════════════════
function buildJSON(){
  const tempoPoints=normalizeMidiCurvePoints(S.midiCurves[TEMPO_AUTOMATION_KEY]||[],TEMPO_AUTOMATION_KEY);
  const tempoCurve=[];
  if(!tempoPoints.length||Math.abs((tempoPoints[0]?.beat||0))>1e-4){
    tempoCurve.push({time:0.0,bpm:S.bpm});
  }
  tempoPoints.forEach(point=>{
    tempoCurve.push({
      time:beatsToSeconds(point.beat),
      bpm:clamp(Math.round(point.value),TEMPO_MIN,TEMPO_MAX),
    });
  });

  const tracks=[];
  if(S.chord.length){
    tracks.push({name:"chords_main",type:"chord",
      events:[...S.chord].sort((a,b)=>parseBeat(a.beat)-parseBeat(b.beat))
        .map(e=>({chord:e.chord,beat:e.beat}))});
  }
  if(S.pluck.length){
    tracks.push({name:"pluck_main",type:"pluck",
      events:[...S.pluck].sort((a,b)=>parseBeat(a.beat)-parseBeat(b.beat))
        .map(e=>{
          const o={note:e.note,duration_b:e.duration_b,speed:e.speed,slide:e.slide,beat:e.beat};
          if(e.string_index!==null)o.string_index=e.string_index;
          return o;
        })});
  }
  const combinedMidi=[
    ...S.midi.map(e=>({address:e.address,args:e.args,interp:e.interp,beat:e.beat})),
    ...midiAutomationEvents(),
  ].sort((a,b)=>parseBeat(a.beat)-parseBeat(b.beat));
  if(combinedMidi.length){
    tracks.push({name:"midi_fx",type:"midi",
      events:combinedMidi});
  }
  const automationLaneRanges=Object.fromEntries(
    MIDI_AUTOMATION_KEYS.map(key=>{
      const k=String(key);
      const range=getAutomationLaneRange(k);
      return [k,{min:range.min,max:range.max}];
    })
  );
  return{song:{name:S.songName,meta:{key:`${S.keyRoot} ${S.keyMode}`,time_signature:S.timeSig,bpm:S.bpm,tempo_curve:tempoCurve,automation_lane_ranges:automationLaneRanges},tracks}};
}

function hlJSON(s){
  return s
    .replace(/("(?:[^"\\]|\\.)*")\s*:/g,'<span class="jk">$1</span>:')
    .replace(/:\s*("(?:[^"\\]|\\.)*")/g,': <span class="js">$1</span>')
    .replace(/:\s*(-?\d+\.?\d*)/g,': <span class="jn">$1</span>')
    .replace(/:\s*(true|false|null)/g,': <span class="jb">$1</span>');
}

const HISTORY_LIMIT=200;

function pushHistorySnapshot(raw){
  if(S.historySuspend)return;
  if(!S.historyUndo.length||S.historyUndo[S.historyUndo.length-1]!==raw){
    S.historyUndo.push(raw);
    if(S.historyUndo.length>HISTORY_LIMIT)S.historyUndo.shift();
  }
  S.historyRedo=[];
}

function restoreHistorySnapshot(raw){
  if(!raw)return false;
  try{
    S.historySuspend=true;
    loadJSON(JSON.parse(raw));
    return true;
  }catch(_e){
    return false;
  }finally{
    S.historySuspend=false;
  }
}

function canUndo(){
  return S.historyUndo.length>1;
}

function canRedo(){
  return S.historyRedo.length>0;
}

function undoHistory(){
  if(!canUndo())return false;
  const current=S.historyUndo.pop();
  S.historyRedo.push(current);
  const previous=S.historyUndo[S.historyUndo.length-1];
  return restoreHistorySnapshot(previous);
}

function redoHistory(){
  if(!canRedo())return false;
  const next=S.historyRedo.pop();
  if(!next)return false;
  S.historyUndo.push(next);
  return restoreHistorySnapshot(next);
}

function syncJSON(){
  const raw=JSON.stringify(buildJSON());
  localStorage.setItem('guitarbot_autosave',raw);
  pushHistorySnapshot(raw);
  if(typeof renderNoteWarnings==='function')renderNoteWarnings();
  const jp=document.getElementById('jp');
  if(!jp||!jp.classList.contains('open'))return;
  document.getElementById('jp-content').innerHTML=hlJSON(JSON.stringify(buildJSON(),null,2));
}

function toggleJP(){
  const jp=document.getElementById('jp'), ch=document.getElementById('jp-chev');
  jp.classList.toggle('open');
  ch.style.transform=jp.classList.contains('open')?'rotate(180deg)':'';
  syncJSON();
}

async function copyPreviewJSON(event){
  if(event)event.stopPropagation();
  const raw=JSON.stringify(buildJSON(),null,2);
  try{
    await navigator.clipboard.writeText(raw);
  }catch(_e){
    const ta=document.createElement('textarea');
    ta.value=raw;
    ta.style.position='fixed';
    ta.style.opacity='0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
}

function buildUploadJSON(){
  const full=buildJSON();
  const soloRange=Number.isInteger(S.stringSoloIndex)?STRINGS[S.stringSoloIndex]:null;
  const mutedRanges=STRINGS.filter((_,index)=>!!S.stringMuted[index]);
  const allowPluckNote=(noteRaw)=>{
    const note=parseInt(noteRaw,10);
    if(!Number.isFinite(note))return false;
    if(soloRange)return note>=soloRange.min&&note<=soloRange.max;
    return !mutedRanges.some(range=>note>=range.min&&note<=range.max);
  };

  if(!getCycleRange()){
    if(!soloRange&&!mutedRanges.length)return full;
    return {
      song:{
        ...full.song,
        tracks:(full.song.tracks||[]).map(track=>{
          if(track.type!=='pluck')return track;
          return {
            ...track,
            events:(track.events||[]).filter(ev=>allowPluckNote(ev.note)),
          };
        }),
      },
    };
  }

  const cycle=getCycleRange();

  const {startBeat,endBeat}=cycle;
  const spb=secondsPerBeat();
  const toTimestamp=beat=>1+Math.max(0,(beat-startBeat))*spb;
  const eventBeat=ev=>{
    if(ev&&ev.beat!==undefined&&ev.beat!==null&&String(ev.beat).trim()!=='')return parseBeat(ev.beat);
    if(ev&&ev.timestamp!==undefined&&ev.timestamp!==null)return secondsToBeat(ev.timestamp);
    return 0;
  };

  const tracks=(full.song.tracks||[]).map(track=>{
    const events=(track.events||[])
      .filter(ev=>{
        if(track.type==='pluck'&&(soloRange||mutedRanges.length)){
          if(!allowPluckNote(ev.note))return false;
        }
        const beat=eventBeat(ev);
        return beat>=startBeat&&beat<endBeat;
      })
      .map(ev=>{
        const beat=eventBeat(ev);
        if(track.type==='pluck'){
          const durationBeats=(ev.duration_b!==undefined&&ev.duration_b!==null)
            ? (parseFloat(ev.duration_b)||0.5)
            : ((ev.duration_s!==undefined&&ev.duration_s!==null)
                ? secondsToDurationBeats(ev.duration_s)
                : (parseFloat(ev.duration)||0.5));
          const out={
            note:ev.note,
            duration_s:durationBeats*spb,
            speed:ev.speed,
            slide:ev.slide,
            timestamp:toTimestamp(beat),
          };
          if(ev.string_index!==undefined&&ev.string_index!==null)out.string_index=ev.string_index;
          return out;
        }
        if(track.type==='chord'){
          return {chord:ev.chord,timestamp:toTimestamp(beat)};
        }
        if(track.type==='midi'){
          return {address:ev.address,args:ev.args,interp:ev.interp,timestamp:toTimestamp(beat)};
        }
        return ev;
      });
    return {...track,events};
  });

  const tempoCurve=(full.song.meta?.tempo_curve||[])
    .filter(point=>Number.isFinite(parseFloat(point?.time))&&Number.isFinite(parseFloat(point?.bpm)))
    .map(point=>({
      beat:secondsToBeat(parseFloat(point.time)),
      bpm:clamp(Math.round(parseFloat(point.bpm)),TEMPO_MIN,TEMPO_MAX),
    }))
    .filter(point=>point.beat>=startBeat&&point.beat<endBeat)
    .map(point=>({
      time:Math.max(0,(point.beat-startBeat))*spb,
      bpm:point.bpm,
    }))
    .sort((a,b)=>a.time-b.time);
  if(!tempoCurve.length||tempoCurve[0].time>1e-6){
    tempoCurve.unshift({time:0.0,bpm:clamp(Math.round(S.bpm),TEMPO_MIN,TEMPO_MAX)});
  }

  return {
    song:{
      ...full.song,
      meta:{
        ...full.song.meta,
        tempo_curve:tempoCurve,
      },
      tracks,
    },
  };
}

// ═══════════════════════════════════════════════
// EXPORT / IMPORT
// ═══════════════════════════════════════════════
function baseNameNoExt(fileName){
  return (String(fileName||'Imported')
    .replace(/\.[^/.]+$/,'')
    .trim())||'Imported';
}

function splitTimeSig(sigRaw){
  const parts=String(sigRaw||'4/4').split('/');
  const numerator=Math.max(1,parseInt(parts[0],10)||4);
  const denominator=Math.max(1,parseInt(parts[1],10)||4);
  return {numerator,denominator};
}

function uiBeatToQuarterBeats(beat,denominator){
  return (parseFloat(beat)||0)*(4/Math.max(1,denominator));
}

function quarterBeatsToUiBeat(quarterBeats,denominator){
  return (parseFloat(quarterBeats)||0)*(Math.max(1,denominator)/4);
}

function uiBeatToTicks(beat,denominator,ppq){
  const quarterBeats=uiBeatToQuarterBeats(beat,denominator);
  return Math.max(0,Math.round(quarterBeats*Math.max(1,ppq||480)));
}

function ticksToUiBeat(ticks,denominator,ppq){
  const quarterBeats=(parseFloat(ticks)||0)/Math.max(1,ppq||480);
  return trimBeatNumber(Math.max(0,quarterBeatsToUiBeat(quarterBeats,denominator)));
}

function midiTempoCurveForExport(denominator,ppq){
  const points=normalizeMidiCurvePoints(S.midiCurves[TEMPO_AUTOMATION_KEY]||[],TEMPO_AUTOMATION_KEY);
  if(!points.length){
    return [{ticks:0,bpm:clamp(Math.round(S.bpm),TEMPO_MIN,TEMPO_MAX)}];
  }
  return points.map(point=>({
    ticks:uiBeatToTicks(point.beat,denominator,ppq),
    bpm:clamp(Math.round(point.value),TEMPO_MIN,TEMPO_MAX),
  }));
}

function maybePushMidiFxEvent(events,beat,address,args,interp=0){
  if(!Number.isFinite(beat))return;
  events.push({address,args,interp,beat:beatLabel(beat)});
}

let importToastTimer=null;
function showImportToast(message,durationMs=3200){
  const toast=document.getElementById('import-toast');
  if(!toast)return;
  toast.textContent=message;
  toast.classList.add('on');
  if(importToastTimer)clearTimeout(importToastTimer);
  importToastTimer=setTimeout(()=>{
    toast.classList.remove('on');
    importToastTimer=null;
  },Math.max(1200,parseInt(durationMs,10)||3200));
}

function buildDownOctaveCandidates(noteRaw){
  const source=parseInt(noteRaw,10);
  const note=Number.isFinite(source)?source:52;
  const candidates=[];
  for(let oct=0;oct<=8;oct++){
    const shifted=note-(12*oct);
    if(shifted<MIDI_MIN)break;
    if(shifted>MIDI_MAX)continue;
    candidates.push({note:shifted,octavesDown:oct});
  }

  if(!candidates.length){
    let shifted=note;
    let octavesDown=0;
    while(shifted>MIDI_MAX&&octavesDown<8){
      shifted-=12;
      octavesDown++;
    }
    if(shifted>=MIDI_MIN&&shifted<=MIDI_MAX){
      candidates.push({note:shifted,octavesDown});
    }
  }

  if(!candidates.length){
    candidates.push({
      note:clamp(note,MIDI_MIN,MIDI_MAX),
      octavesDown:Math.max(0,Math.ceil((note-MIDI_MAX)/12)),
    });
  }

  const seen=new Set();
  return candidates.filter(candidate=>{
    if(seen.has(candidate.note))return false;
    seen.add(candidate.note);
    return true;
  });
}

function optimizeImportedMidiNotePitches(rawNotes){
  if(!Array.isArray(rawNotes)||!rawNotes.length)return [];

  const ordered=rawNotes
    .map((note,index)=>({note,index}))
    .sort((a,b)=>{
      const aStart=parseFloat(a.note.startTick)||0;
      const bStart=parseFloat(b.note.startTick)||0;
      if(aStart!==bStart)return aStart-bStart;
      const aEnd=parseFloat(a.note.endTick)||aStart;
      const bEnd=parseFloat(b.note.endTick)||bStart;
      if(aEnd!==bEnd)return aEnd-bEnd;
      return (parseInt(a.note.midi,10)||0)-(parseInt(b.note.midi,10)||0);
    });

  const BEAM_WIDTH=8;
  const WEIGHT_OVERLAP=80;
  const WEIGHT_EXACT_STACK=120;
  const WEIGHT_OCTAVE_SHIFT=3;
  const WEIGHT_REGISTER=0.05;
  const registerCenter=(MIDI_MIN+MIDI_MAX)/2;

  let beam=[{cost:0,active:[],path:null}];

  for(let step=0;step<ordered.length;step++){
    const entry=ordered[step];
    const src=entry.note;
    const startTick=Math.max(0,parseFloat(src.startTick)||0);
    const endTick=Math.max(startTick+1,parseFloat(src.endTick)||startTick+1);
    const candidates=buildDownOctaveCandidates(src.midi);
    const nextBeam=[];

    for(const state of beam){
      const stillActive=state.active.filter(active=>active.endTick>startTick);
      for(const candidate of candidates){
        let overlapCount=0;
        let exactStackCount=0;
        for(const active of stillActive){
          if(active.note!==candidate.note)continue;
          const overlaps=active.startTick<endTick&&active.endTick>startTick;
          if(!overlaps)continue;
          overlapCount++;
          if(Math.abs(active.startTick-startTick)<1e-6)exactStackCount++;
        }

        const octavePenalty=WEIGHT_OCTAVE_SHIFT*candidate.octavesDown;
        const overlapPenalty=(WEIGHT_OVERLAP*overlapCount)+(WEIGHT_EXACT_STACK*exactStackCount);
        const registerPenalty=WEIGHT_REGISTER*Math.abs(candidate.note-registerCenter);
        const score=state.cost+octavePenalty+overlapPenalty+registerPenalty;

        nextBeam.push({
          cost:score,
          active:[...stillActive,{note:candidate.note,startTick,endTick}],
          path:{note:candidate.note,prev:state.path},
        });
      }
    }

    nextBeam.sort((a,b)=>a.cost-b.cost);
    beam=nextBeam.slice(0,BEAM_WIDTH);
  }

  const best=beam[0]||{path:null};
  const chosenOrdered=[];
  let pathNode=best.path;
  while(pathNode){
    chosenOrdered.push(pathNode.note);
    pathNode=pathNode.prev;
  }
  chosenOrdered.reverse();

  const mapped=new Array(rawNotes.length).fill(52);
  for(let i=0;i<ordered.length;i++){
    mapped[ordered[i].index]=chosenOrdered[i]??52;
  }
  return mapped;
}

function importMidiFromArrayBuffer(buffer,fileName='Imported.mid'){
  if(typeof Midi==='undefined'){
    alert('MIDI library not loaded. Reload this page and try again.');
    return;
  }
  const midi=new Midi(buffer);
  const ts=midi.header?.timeSignatures?.[0]?.timeSignature;
  const importedNumerator=Math.max(1,parseInt(ts?.[0],10)||4);
  const importedDenominator=Math.max(1,parseInt(ts?.[1],10)||4);
  const importedTimeSig=`${importedNumerator}/${importedDenominator}`;

  const tempos=[...(midi.header?.tempos||[])]
    .filter(t=>Number.isFinite(parseFloat(t?.bpm)))
    .sort((a,b)=>(parseFloat(a?.ticks)||0)-(parseFloat(b?.ticks)||0));
  const bpm=clamp(
    Math.round(parseFloat(tempos[0]?.bpm)||120),
    TEMPO_MIN,
    TEMPO_MAX
  );

  const tempo_curve=tempos.map(entry=>{
    const ticks=parseFloat(entry?.ticks)||0;
    const seconds=Number.isFinite(parseFloat(entry?.time))
      ? parseFloat(entry.time)
      : ticks/Math.max(1,midi.header?.ppq||480)*(60/Math.max(1,bpm));
    return {
      time:Math.max(0,seconds),
      bpm:clamp(Math.round(parseFloat(entry?.bpm)||bpm),TEMPO_MIN,TEMPO_MAX),
    };
  });

  const rawImportedNotes=[];
  const midiEvents=[];

  for(const track of midi.tracks||[]){
    for(const note of track.notes||[]){
      const startTick=Math.max(0,parseFloat(note.ticks)||0);
      const durationTicks=Math.max(1,parseInt(note.durationTicks,10)||1);
      rawImportedNotes.push({
        midi:parseInt(note.midi,10)||52,
        startTick,
        endTick:startTick+durationTicks,
        durationTicks,
        velocity:Math.max(0,Math.min(1,parseFloat(note.velocity)||0.8)),
      });
    }

    const ccMap=track.controlChanges||{};
    for(const key of Object.keys(ccMap)){
      const events=ccMap[key]||[];
      for(const ccEvent of events){
        const cc=parseInt(ccEvent.number,10);
        if(!Number.isFinite(cc))continue;
        const beat=ticksToUiBeat(ccEvent.ticks,importedDenominator,midi.header?.ppq||480);
        const value=clamp(Math.round((parseFloat(ccEvent.value)||0)*127),0,127);
        maybePushMidiFxEvent(midiEvents,beat,'/cc',[cc,value],1);
      }
    }

    for(const pitchEvent of track.pitchBends||[]){
      const beat=ticksToUiBeat(pitchEvent.ticks,importedDenominator,midi.header?.ppq||480);
      maybePushMidiFxEvent(midiEvents,beat,'/pitch',[parseFloat(pitchEvent.value)||0],0);
    }

    for(const programEvent of track.programChanges||[]){
      const beat=ticksToUiBeat(programEvent.ticks,importedDenominator,midi.header?.ppq||480);
      const program=parseInt(programEvent.number,10);
      if(!Number.isFinite(program))continue;
      maybePushMidiFxEvent(midiEvents,beat,'/program',[program],0);
    }
  }

  const optimizedNotes=optimizeImportedMidiNotePitches(rawImportedNotes);
  const pluckEvents=[];
  let shiftedCount=0;
  rawImportedNotes.forEach((note,index)=>{
    const beat=ticksToUiBeat(note.startTick,importedDenominator,midi.header?.ppq||480);
    const durationBeats=Math.max(
      minDurationBeats(),
      ticksToUiBeat(note.durationTicks,importedDenominator,midi.header?.ppq||480)
    );
    const speed=clampSpeed(Math.round(note.velocity*(SPEED_MAX-SPEED_MIN)+SPEED_MIN));
    const optimizedPitch=clamp(parseInt(optimizedNotes[index],10)||52,MIDI_MIN,MIDI_MAX);
    if(optimizedPitch!==parseInt(note.midi,10))shiftedCount++;
    pluckEvents.push({
      note:optimizedPitch,
      duration_b:trimBeatNumber(durationBeats),
      speed,
      slide:0,
      beat:beatLabel(beat),
    });
  });

  const tracks=[];
  if(pluckEvents.length){
    tracks.push({name:'pluck_main',type:'pluck',events:pluckEvents});
  }
  if(midiEvents.length){
    tracks.push({name:'midi_fx',type:'midi',events:midiEvents});
  }

  loadJSON({song:{
    name:baseNameNoExt(fileName),
    meta:{
      key:'E minor',
      time_signature:importedTimeSig,
      bpm,
      tempo_curve
    },
    tracks
  }});
  
  if(shiftedCount>0){
    const plural=shiftedCount===1?'':'s';
    showImportToast(`Adjusted ${shiftedCount} note${plural} by octave to reduce overlap/range issues.`);
  }

  if(typeof renderNoteWarnings==='function')renderNoteWarnings();
}

function exportMidiFile(){
  if(typeof Midi==='undefined'){
    alert('MIDI library not loaded. Reload this page and try again.');
    return;
  }
  const midi=new Midi();
  const ts=splitTimeSig(S.timeSig);
  const denominator=ts.denominator;
  const ppq=480;
  midi.header.setTempo(S.bpm);

  const pluckTrack=midi.addTrack();
  pluckTrack.name='pluck_main';
  S.pluck.forEach(ev=>{
    const ticks=uiBeatToTicks(parseBeat(ev.beat),denominator,ppq);
    const durationBeats=(ev.duration_b!==undefined&&ev.duration_b!==null)
      ? (parseFloat(ev.duration_b)||0.5)
      : (parseFloat(ev.duration)||0.5);
    const durationTicks=Math.max(1,uiBeatToTicks(durationBeats,denominator,ppq));
    const velocity=clamp(ev.speed/127,0,1);
    pluckTrack.addNote({
      midi:clamp(parseInt(ev.note,10)||52,0,127),
      ticks,
      durationTicks,
      velocity,
    });
  });

  const midiTrack=midi.addTrack();
  midiTrack.name='midi_fx';
  const fxEvents=[
    ...S.midi.map(e=>({address:e.address,args:e.args,interp:e.interp,beat:e.beat})),
    ...midiAutomationEvents(),
  ].sort((a,b)=>parseBeat(a.beat)-parseBeat(b.beat));

  fxEvents.forEach(ev=>{
    const ticks=uiBeatToTicks(parseBeat(ev.beat),denominator,ppq);
    if(ev.address==='/cc'&&Array.isArray(ev.args)&&ev.args.length>=2){
      const number=parseInt(ev.args[0],10);
      const value=clamp(parseFloat(ev.args[1])||0,0,127)/127;
      if(Number.isFinite(number))midiTrack.addCC({number,ticks,value});
      return;
    }
    if(ev.address==='/note'&&Array.isArray(ev.args)&&ev.args.length>=1){
      const midiNote=clamp(parseInt(ev.args[0],10)||60,0,127);
      const velocity=clamp(parseFloat(ev.args[1])||96,0,127)/127;
      midiTrack.addNote({midi:midiNote,ticks,durationTicks:Math.max(1,uiBeatToTicks(gridStep(),denominator,ppq)),velocity});
      return;
    }
    if(ev.address==='/pitch'&&Array.isArray(ev.args)&&ev.args.length>=1){
      let value=parseFloat(ev.args[0]);
      if(!Number.isFinite(value))value=0;
      if(Math.abs(value)>1)value=clamp((value-8192)/8192,-1,1);
      midiTrack.addPitchBend({ticks,value:clamp(value,-1,1)});
      return;
    }
    if(ev.address==='/program'&&Array.isArray(ev.args)&&ev.args.length>=1){
      const program=parseInt(ev.args[0],10);
      if(Number.isFinite(program))midiTrack.instrument.number=clamp(program,0,127);
    }
  });

  const tempoCurve=midiTempoCurveForExport(denominator,ppq);
  tempoCurve.forEach(pt=>{
    // @ts-ignore
    midi.header.tempos.push({ticks:pt.ticks,bpm:pt.bpm});
  });

  return midi.toArray();
}

function saveBlobWithAnchor(blob,fileName){
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=fileName;
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportJsonFile(){
  const base=(S.songName.replace(/[^a-z0-9_\-]/gi,'_').toLowerCase()||'song');
  const blob=new Blob([JSON.stringify(buildJSON(),null,2)],{type:'application/json'});
  saveBlobWithAnchor(blob,`${base}.json`);
}

function exportMidiViaAnchor(){
  const base=(S.songName.replace(/[^a-z0-9_\-]/gi,'_').toLowerCase()||'song');
  const bytes=exportMidiFile();
  const blob=new Blob([bytes],{type:'audio/midi'});
  saveBlobWithAnchor(blob,`${base}.mid`);
}

function openExportPop(){
  const pop=document.getElementById('export-pop');
  const btn=document.getElementById('btn-export');
  if(!pop||!btn)return;
  const rect=btn.getBoundingClientRect();
  pop.style.left=`${Math.max(8,rect.left)}px`;
  pop.style.top=`${Math.max(8,rect.bottom+6)}px`;
  pop.classList.add('on');

  const bounds=pop.getBoundingClientRect();
  let left=rect.left;
  let top=rect.bottom+6;
  if(left+bounds.width>window.innerWidth-8)left=window.innerWidth-bounds.width-8;
  if(left<8)left=8;
  if(top+bounds.height>window.innerHeight-8)top=rect.top-bounds.height-6;
  if(top<8)top=8;
  pop.style.left=`${Math.round(left)}px`;
  pop.style.top=`${Math.round(top)}px`;
}

function closeExportPop(){
  document.getElementById('export-pop')?.classList.remove('on');
}

async function exportUsingNativePicker(){
  if(typeof window.showSaveFilePicker!=='function')return false;
  const base=(S.songName.replace(/[^a-z0-9_\-]/gi,'_').toLowerCase()||'song');
  let handle;
  try{
    handle=await window.showSaveFilePicker({
      suggestedName:`${base}.json`,
      types:[
        {
          description:'JSON Arrangement',
          accept:{'application/json':['.json']},
        },
        {
          description:'MIDI File',
          accept:{'audio/midi':['.mid','.midi']},
        },
      ],
    });
  }catch(err){
    if(err&&err.name==='AbortError')return true;
    return false;
  }

  const name=String(handle?.name||'').toLowerCase();
  const asMidi=name.endsWith('.mid')||name.endsWith('.midi');
  const blob=asMidi
    ? new Blob([exportMidiFile()],{type:'audio/midi'})
    : new Blob([JSON.stringify(buildJSON(),null,2)],{type:'application/json'});
  const writable=await handle.createWritable();
  await writable.write(blob);
  await writable.close();
  return true;
}

document.getElementById('btn-export').addEventListener('click',async()=>{
  closeExportPop();
  const usedNative=await exportUsingNativePicker();
  if(usedNative)return;
  openExportPop();
});

document.getElementById('btn-export-json').addEventListener('click',()=>{
  closeExportPop();
  exportJsonFile();
});

document.getElementById('btn-export-midi').addEventListener('click',()=>{
  closeExportPop();
  exportMidiViaAnchor();
});

document.addEventListener('pointerdown',e=>{
  const pop=document.getElementById('export-pop');
  const btn=document.getElementById('btn-export');
  if(!pop||!btn)return;
  if(!pop.contains(e.target)&&!btn.contains(e.target))closeExportPop();
});

async function uploadToBot(){
  const btn=document.getElementById('btn-upload');
  const original=btn.textContent;
  btn.disabled=true;
  btn.textContent='… Uploading';
  try{
    const res=await fetch('http://127.0.0.1:8765/upload',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(buildUploadJSON())
    });
    const data=await res.json().catch(()=>({ok:false,error:'Invalid server response'}));
    if(!res.ok||!data.ok)throw new Error(data.error||`HTTP ${res.status}`);
    btn.textContent='✓ Uploaded';
    setTimeout(()=>{btn.textContent=original;btn.disabled=false},900);
    return true;
  }catch(err){
    alert(
      'Upload failed. Start the local uploader first:\n\n'
      +'python send_song_arrangement.py --serve\n\n'
      +'Then try Upload to Bot again.\n\n'
      +`Details: ${err.message}`
    );
    btn.textContent=original;
    btn.disabled=false;
    return false;
  }
}

document.getElementById('btn-upload').addEventListener('click',()=>uploadToBot());

document.getElementById('btn-reset-bot').addEventListener('click',async()=>{
  const btn=document.getElementById('btn-reset-bot');
  const original=btn.textContent;
  btn.disabled=true;
  btn.textContent='… Resetting';
  try{
    const res=await fetch('http://127.0.0.1:8765/reset',{method:'POST'});
    const data=await res.json().catch(()=>({ok:false,error:'Invalid server response'}));
    if(!res.ok||!data.ok)throw new Error(data.error||`HTTP ${res.status}`);
    btn.textContent='✓ Reset';
    setTimeout(()=>{btn.textContent=original;btn.disabled=false},900);
  }catch(err){
    alert(
      'Reset failed. Start the local uploader first:\n\n'
      +'python send_song_arrangement.py --serve\n\n'
      +'Then try Reset Bot again.\n\n'
      +`Details: ${err.message}`
    );
    btn.textContent=original;
    btn.disabled=false;
  }
});

document.getElementById('btn-import').addEventListener('click',()=>document.getElementById('hidden-file').click());
document.getElementById('hidden-file').addEventListener('change',e=>{
  const f=e.target.files[0];
  if(!f)return;
  const ext=f.name.toLowerCase().split('.').pop();
  const isMidi=ext==='mid'||ext==='midi'||f.type==='audio/midi'||f.type==='audio/x-midi';
  const r=new FileReader();
  if(isMidi){
    r.onload=ev=>{
      try{importMidiFromArrayBuffer(ev.target.result,f.name);}catch(err){alert('Invalid MIDI: '+err.message);}
    };
    r.readAsArrayBuffer(f);
  }else{
    r.onload=ev=>{try{loadJSON(JSON.parse(ev.target.result))}catch(err){alert('Invalid JSON: '+err.message)}};
    r.readAsText(f);
  }
  e.target.value='';
});

function loadJSON(data){
  const song=data.song; if(!song)return alert('Missing "song" key');
  S.songName=song.name||'Imported';
  document.getElementById('song-name').value=S.songName;
  S.automationLaneRanges=createDefaultAutomationLaneRanges();
  if(song.meta){
    const m=song.meta;
    if(m.bpm){S.bpm=m.bpm;document.getElementById('bpm').value=m.bpm}
    if(m.key){const p=m.key.split(' ');S.keyRoot=p[0]||'E';S.keyMode=p[1]||'minor';
      document.getElementById('key-root').value=S.keyRoot;
      document.getElementById('key-mode').value=S.keyMode}
    if(m.time_signature){S.timeSig=m.time_signature;document.getElementById('time-sig').value=S.timeSig}
    if(m.automation_lane_ranges&&typeof m.automation_lane_ranges==='object'){
      for(const key of MIDI_AUTOMATION_KEYS){
        const k=String(key);
        const raw=m.automation_lane_ranges[k];
        if(!raw||typeof raw!=='object')continue;
        const min=parseFloat(raw.min);
        const max=parseFloat(raw.max);
        if(!Number.isFinite(min)||!Number.isFinite(max))continue;
        const hard=isTempoLaneKey(k)
          ?{min:TEMPO_MIN,max:TEMPO_MAX}
          :{min:0,max:127};
        let nMin=clamp(Math.round(min),hard.min,hard.max);
        let nMax=clamp(Math.round(max),hard.min,hard.max);
        if(nMax<=nMin)nMax=Math.min(hard.max,nMin+1);
        if(nMax<=nMin){nMin=hard.min;nMax=Math.min(hard.max,hard.min+1);}
        S.automationLaneRanges[k]={min:nMin,max:nMax};
      }
    }
  }
  S.pluck=[]; S.chord=[]; S.midi=[]; S.midiCurves=createEmptyMidiCurves(); S.midiCurveMuted=createEmptyMidiCurveMuteState(); S.midiLaneMenuLane=null; S.focusedCCLane=null; S.nextId=1;
  S.selPluck=null; S.selPluckIds.clear(); S.selChord=null; S.selMidi=null; clearMidiCurveSelection(); S.clipboardPluck=null; S.clipboardMidiCurves=null; closeInsp();
  let maxB=0;
  (song.tracks||[]).forEach(tr=>{
    (tr.events||[]).forEach(ev=>{
      const hasBeat=ev.beat!==undefined&&ev.beat!==null&&String(ev.beat).trim()!=='';
      const hasTimestamp=Number.isFinite(parseFloat(ev.timestamp));
      const b=hasBeat?parseBeat(ev.beat):(hasTimestamp?secondsToBeat(ev.timestamp):0);
      maxB=Math.max(maxB,b);
      if(tr.type==='pluck'){
        const durationBeats=(ev.duration_b!==undefined&&ev.duration_b!==null)
          ? (parseFloat(ev.duration_b)||0.5)
          : ((ev.duration_s!==undefined&&ev.duration_s!==null)
              ? secondsToDurationBeats(ev.duration_s)
              : (parseFloat(ev.duration)||0.5));
        S.pluck.push(ensureSlideShape({id:S.nextId++,note:ev.note||52,
          duration_b:durationBeats,
          speed:normalizeImportedSpeed(ev.speed),slide:ev.slide??0,
          slideIn:ev.slideIn??ev.slide_in??0,
          slideOut:ev.slideOut??ev.slide_out??0,
          beat:hasBeat?ev.beat:beatLabel(b),
          string_index:ev.string_index??null}));
      } else if(tr.type==='chord'){
        S.chord.push({id:S.nextId++,chord:ev.chord||'Em',beat:hasBeat?ev.beat:beatLabel(b)});
      } else if(tr.type==='midi'){
        const address=ev.address||'/cc';
        const args=Array.isArray(ev.args)?ev.args:[];
        const cc=args.length?parseInt(args[0],10):NaN;
        const value=args.length>1?parseFloat(args[1]):0;
        if(address==='/cc'&&MIDI_AUTOMATION_CCS.includes(cc)){
          upsertMidiCurvePoint(cc,b,clamp(Math.round(Number.isFinite(value)?value:0),0,127));
        } else {
          S.midi.push({id:S.nextId++,address,args,interp:ev.interp??0,beat:hasBeat?ev.beat:beatLabel(b)});
        }
      }
    });
  });
  // Keep one /cc event per controller per beat in general MIDI lane.
  const seenCCBeats=new Set();
  S.midi=S.midi.filter(ev=>{
    const cc=midiCCFromEvent(ev);
    if(cc===null)return true;
    const key=`${cc}@${trimBeatNumber(parseBeat(ev.beat)).toFixed(4)}`;
    if(seenCCBeats.has(key))return false;
    seenCCBeats.add(key);
    return true;
  });
  const m=bpm();
  if(Array.isArray(song.meta?.tempo_curve)){
    const points=[];
    for(const entry of song.meta.tempo_curve){
      const time=parseFloat(entry?.time);
      const bpmVal=parseFloat(entry?.bpm);
      if(!Number.isFinite(time)||!Number.isFinite(bpmVal))continue;
      points.push({beat:secondsToBeat(time),value:clamp(Math.round(bpmVal),TEMPO_MIN,TEMPO_MAX)});
    }
    S.midiCurves[TEMPO_AUTOMATION_KEY]=normalizeMidiCurvePoints(points,TEMPO_AUTOMATION_KEY);
  }

  for(const key of MIDI_AUTOMATION_KEYS){
    const k=String(key);
    S.midiCurves[k]=normalizeMidiCurvePoints(S.midiCurves[k]||[],k);
  }

  S.measures=Math.max(8,Math.ceil(maxB/m)+2);
  document.getElementById('measures').value=S.measures;
  syncCycleControls();
  render(); syncJSON();
}
