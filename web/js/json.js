// ═══════════════════════════════════════════════
// JSON PREVIEW
// ═══════════════════════════════════════════════
function buildJSON(){
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
  return{song:{name:S.songName,meta:{key:`${S.keyRoot} ${S.keyMode}`,time_signature:S.timeSig,bpm:S.bpm,tempo_curve:[{time:0.0,bpm:S.bpm}]},tracks}};
}

function hlJSON(s){
  return s
    .replace(/("(?:[^"\\]|\\.)*")\s*:/g,'<span class="jk">$1</span>:')
    .replace(/:\s*("(?:[^"\\]|\\.)*")/g,': <span class="js">$1</span>')
    .replace(/:\s*(-?\d+\.?\d*)/g,': <span class="jn">$1</span>')
    .replace(/:\s*(true|false|null)/g,': <span class="jb">$1</span>');
}

function syncJSON(){
  const raw=JSON.stringify(buildJSON());
  localStorage.setItem('guitarbot_autosave',raw);
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

function buildUploadJSON(){
  const full=buildJSON();
  const cycle=getCycleRange();
  if(!cycle)return full;

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

  return {
    song:{
      ...full.song,
      tracks,
    },
  };
}

// ═══════════════════════════════════════════════
// EXPORT / IMPORT
// ═══════════════════════════════════════════════
document.getElementById('btn-export').addEventListener('click',()=>{
  const blob=new Blob([JSON.stringify(buildJSON(),null,2)],{type:'application/json'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=(S.songName.replace(/[^a-z0-9_\-]/gi,'_').toLowerCase()||'song')+'.json';
  a.click(); URL.revokeObjectURL(a.href);
});

document.getElementById('btn-upload').addEventListener('click',async()=>{
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
  }catch(err){
    alert(
      'Upload failed. Start the local uploader first:\n\n'
      +'python send_song_arrangement.py --serve\n\n'
      +'Then try Upload to Bot again.\n\n'
      +`Details: ${err.message}`
    );
    btn.textContent=original;
    btn.disabled=false;
  }
});

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
  const f=e.target.files[0]; if(!f)return;
  const r=new FileReader();
  r.onload=ev=>{try{loadJSON(JSON.parse(ev.target.result))}catch(err){alert('Invalid JSON: '+err.message)}};
  r.readAsText(f); e.target.value='';
});

function loadJSON(data){
  const song=data.song; if(!song)return alert('Missing "song" key');
  S.songName=song.name||'Imported';
  document.getElementById('song-name').value=S.songName;
  if(song.meta){
    const m=song.meta;
    if(m.bpm){S.bpm=m.bpm;document.getElementById('bpm').value=m.bpm}
    if(m.key){const p=m.key.split(' ');S.keyRoot=p[0]||'E';S.keyMode=p[1]||'minor';
      document.getElementById('key-root').value=S.keyRoot;
      document.getElementById('key-mode').value=S.keyMode}
    if(m.time_signature){S.timeSig=m.time_signature;document.getElementById('time-sig').value=S.timeSig}
  }
  S.pluck=[]; S.chord=[]; S.midi=[]; S.midiCurves=createEmptyMidiCurves(); S.midiCurveMuted=createEmptyMidiCurveMuteState(); S.midiLaneMenuLane=null; S.focusedCCLane=null; S.nextId=1;
  S.selPluck=null; S.selPluckIds.clear(); S.selChord=null; S.selMidi=null; closeInsp();
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
        S.pluck.push({id:S.nextId++,note:ev.note||52,
          duration_b:durationBeats,
          speed:normalizeImportedSpeed(ev.speed),slide:ev.slide??0,
          beat:hasBeat?ev.beat:beatLabel(b),
          string_index:ev.string_index??null});
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
  S.measures=Math.max(8,Math.ceil(maxB/m)+2);
  document.getElementById('measures').value=S.measures;
  syncCycleControls();
  render(); syncJSON();
}

function getSelectedPluckEvents(){
  const ids=S.selPluckIds.size?[...S.selPluckIds]:(S.selPluck!==null?[S.selPluck]:[]);
  if(!ids.length)return [];
  const idSet=new Set(ids);
  return S.pluck.filter(ev=>idSet.has(ev.id));
}

function copySelectedPluckEvents(){
  const selected=getSelectedPluckEvents();
  if(!selected.length)return false;
  const events=selected
    .map(ev=>({
      beat:parseBeat(ev.beat),
      note:ev.note,
      duration_b:ev.duration_b,
      speed:ev.speed,
      slide:ev.slide,
      string_index:ev.string_index,
    }))
    .sort((a,b)=>a.beat-b.beat||a.note-b.note);

  const originBeat=Math.min(...events.map(e=>e.beat));
  const originNote=Math.min(...events.map(e=>e.note));
  S.clipboardPluck={originBeat,originNote,events};
  return true;
}

function pastePluckEvents(){
  const clip=S.clipboardPluck;
  if(!clip||!clip.events||!clip.events.length)return false;
  const targetBeat=S.pasteAnchor?S.pasteAnchor.beat:(clip.originBeat+1);
  const created=[];

  for(const src of clip.events){
    const b=targetBeat+(src.beat-clip.originBeat);
    if(b<0||b>=totalBeats())continue;
    const n=clamp(src.note,MIDI_MIN,MIDI_MAX);
    const ev={
      id:S.nextId++,
      note:n,
      duration_b:src.duration_b,
      speed:src.speed,
      slide:src.slide,
      beat:beatLabel(normalizeBeat(b)),
      string_index:src.string_index,
    };
    S.pluck.push(ev);
    created.push(ev.id);
  }

  if(!created.length)return false;
  S.selPluckIds=new Set(created);
  S.selPluck=created.length===1?created[0]:null;
  S.selChord=null;
  S.selMidi=null;
  if(created.length===1){
    const ev=S.pluck.find(e=>e.id===created[0]);
    if(ev)openInsp(ev);
  } else {
    closeInsp();
  }
  syncJSON();
  render();
  return true;
}
