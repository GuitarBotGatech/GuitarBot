const NOTE_RULES=[
  {
    id:'too-short',
    title:'Note too short',
    severity:'warn',
    thresholdS:0.08,
    message:ctx=>`Very short note (${ctx.durationS.toFixed(3)}s) may under-articulate`,
  },
  {
    id:'too-close',
    title:'Onsets too close',
    severity:'warn',
    thresholdS:0.12,
    message:ctx=>`Onsets ${ctx.gapS.toFixed(3)}s apart on same string may be unstable`,
  },
  {
    id:'overlap',
    title:'Notes overlap',
    severity:'warn',
    message:ctx=>`Same-string overlap ${ctx.overlapS.toFixed(3)}s (cannot fret two spots at once)`,
  },
  {
    id:'open-string-risk',
    title:'Open-string risk',
    severity:'warn',
    message:ctx=>`Prep starts ${ctx.earlyMs.toFixed(0)}ms before prior tremolo ends (possible open-string pluck)`,
  },
];

const NOTE_WARNING_PULSE_MS=1800;

function ensureNoteWarningPopover(){
  let pop=document.getElementById('note-warn-popover');
  if(pop)return pop;
  pop=document.createElement('div');
  pop.id='note-warn-popover';
  pop.className='note-warn-popover';
  document.body.appendChild(pop);
  return pop;
}

function hideNoteWarningPopover(){
  const pop=document.getElementById('note-warn-popover');
  if(!pop)return;
  pop.classList.remove('on');
}

function showNoteWarningPopoverAt(clientX,clientY,text){
  if(!text){
    hideNoteWarningPopover();
    return;
  }

  const pop=ensureNoteWarningPopover();
  pop.textContent=text;

  const top=Math.max(8,Math.min(window.innerHeight-180,clientY+10));
  const left=Math.max(8,Math.min(window.innerWidth-360,clientX+12));
  pop.style.top=`${top}px`;
  pop.style.left=`${left}px`;
  pop.classList.add('on');
}

function noteWarningLinesForNote(noteId){
  const warnings=noteWarningsByNoteId()[String(noteId)]||[];
  if(!warnings.length)return [];
  const lines=warnings.slice(0,8).map((warning,index)=>{
    const beatText=`@${warning.beat}`;
    const strText=`S${warning.stringIndex+1}`;
    return `${index+1}. ${beatText} ${strText} — ${warning.message}`;
  });
  if(warnings.length>lines.length)lines.push(`…and ${warnings.length-lines.length} more`);
  return lines;
}

function noteWarningBadgeLayout(ev){
  const warningCount=noteWarningCountForNote(ev?.id);
  if(!warningCount)return null;

  const x=beatToX(parseBeat(ev.beat));
  const y=noteToY(ev.note);
  const w=Math.max(8,(parseFloat(ev.duration_b)||0)*S.zoom);
  if(x+w<LABEL_W||x>CW)return null;

  const cx2=Math.max(LABEL_W,x);
  const cw2=Math.min(CW,x+w)-cx2;
  if(cw2<=0)return null;

  const r=8;
  const cx=Math.max(LABEL_W+r+1,cx2-r-4);
  const cy=Math.max(CHORD_H+r+1,y-r-6);
  return {cx,cy,r,warningCount};
}

function findWarningBadgeHit(cx,cy){
  for(let i=S.pluck.length-1;i>=0;i--){
    const ev=S.pluck[i];
    const layout=noteWarningBadgeLayout(ev);
    if(!layout)continue;
    const dx=cx-layout.cx;
    const dy=cy-layout.cy;
    if((dx*dx)+(dy*dy)<=layout.r*layout.r){
      return {ev,layout};
    }
  }
  return null;
}

function updateNoteWarningHover(cx,cy,clientX,clientY){
  const hit=findWarningBadgeHit(cx,cy);
  if(!hit){
    hideNoteWarningPopover();
    return false;
  }

  const lines=noteWarningLinesForNote(hit.ev.id);
  if(lines.length)showNoteWarningPopoverAt(clientX,clientY,lines.join('\n'));
  return true;
}

function noteRuleStringIndex(ev){
  if(ev&&ev.string_index!==null&&ev.string_index!==undefined){
    const explicit=parseInt(ev.string_index,10);
    if(Number.isFinite(explicit)&&explicit>=0&&explicit<STRINGS.length)return explicit;
  }
  const note=parseInt(ev?.note,10);
  if(note>=0&&note<STRINGS.length) return note;
  const inferred=STRINGS.findIndex(s=>note>=s.min&&note<=s.max);
  return inferred>=0?inferred:0;
}

function noteRulePrepTimeSeconds(prevEvent,nextEvent){
  const base=0.45;
  if(!nextEvent)return base;

  const prevNote=prevEvent?parseInt(prevEvent.note,10):null;
  const nextNote=parseInt(nextEvent.note,10);
  const durationS=Math.max(0,(parseFloat(nextEvent.duration_b)||0)*secondsPerBeat());
  const slideOn=parseInt(nextEvent.slide||0,10)===1;
  const sameNote=prevNote!==null&&prevNote===nextNote;
  const isTremolo=durationS>=0.5;

  let motionTime=0;
  if(sameNote&&!slideOn){
    motionTime=0.2;
  }else{
    motionTime=0.7;
    if(prevNote!==null){
      const semitoneDelta=Math.abs(nextNote-prevNote);
      motionTime+=Math.min(0.2,semitoneDelta*0.015);
    }
  }
  if(isTremolo)motionTime+=0.005;
  return Math.max(base,motionTime);
}

function evaluatePluckNoteWarnings(){
  const warnings=[];
  const byString=STRINGS.map(()=>[]);

  for(const ev of S.pluck){
    const stringIndex=noteRuleStringIndex(ev);
    const startBeat=parseBeat(ev.beat);
    const durationB=Math.max(0,parseFloat(ev.duration_b)||0);
    const durationS=durationB*secondsPerBeat();
    byString[stringIndex].push({ev,stringIndex,startBeat,durationB,durationS,endBeat:startBeat+durationB});

    const shortRule=NOTE_RULES.find(rule=>rule.id==='too-short');
    if(shortRule&&durationS<shortRule.thresholdS){
      warnings.push({
        ruleId:shortRule.id,
        severity:shortRule.severity,
        noteId:ev.id,
        stringIndex,
        beat:trimBeatNumber(startBeat),
        message:shortRule.message({durationS}),
      });
    }
  }

  const closeRule=NOTE_RULES.find(rule=>rule.id==='too-close');
  const overlapRule=NOTE_RULES.find(rule=>rule.id==='overlap');
  const openRule=NOTE_RULES.find(rule=>rule.id==='open-string-risk');

  for(const events of byString){
    events.sort((a,b)=>a.startBeat-b.startBeat||a.ev.id-b.ev.id);
    for(let i=0;i<events.length;i++){
      const cur=events[i];
      const prev=events[i-1]||null;
      const gapS=prev?(cur.startBeat-prev.startBeat)*secondsPerBeat():Infinity;
      const priorOverlaps=[];
      for(let j=0;j<i;j++){
        const candidate=events[j];
        if(candidate.endBeat-cur.startBeat>1e-6)priorOverlaps.push(candidate);
      }

      if(closeRule&&prev&&gapS<closeRule.thresholdS){
        warnings.push({
          ruleId:closeRule.id,
          severity:closeRule.severity,
          noteId:cur.ev.id,
          stringIndex:cur.stringIndex,
          beat:trimBeatNumber(cur.startBeat),
          message:closeRule.message({gapS}),
        });
      }

      if(overlapRule&&priorOverlaps.length){
        const maxOverlapS=Math.max(...priorOverlaps.map(candidate=>Math.max(0,(candidate.endBeat-cur.startBeat)*secondsPerBeat())));
        warnings.push({
          ruleId:overlapRule.id,
          severity:overlapRule.severity,
          noteId:cur.ev.id,
          stringIndex:cur.stringIndex,
          beat:trimBeatNumber(cur.startBeat),
          message:overlapRule.message({overlapS:maxOverlapS}),
        });
      }

      if(openRule&&prev){
        const prevIsTremolo=prev.durationS>=0.5;
        const curSlide=parseInt(cur.ev.slide||0,10)===1;
        if(prevIsTremolo&&!curSlide){
          const prepS=noteRulePrepTimeSeconds(prev.ev,cur.ev);
          const prepStartBeat=cur.startBeat-(prepS/secondsPerBeat());
          if(prepStartBeat<prev.endBeat){
            warnings.push({
              ruleId:openRule.id,
              severity:openRule.severity,
              noteId:cur.ev.id,
              stringIndex:cur.stringIndex,
              beat:trimBeatNumber(cur.startBeat),
              message:openRule.message({earlyMs:(prev.endBeat-prepStartBeat)*secondsPerBeat()*1000}),
            });
          }
        }
      }
    }
  }

  return warnings;
}

function buildWarningIndex(warnings){
  const byNote={};
  for(const warning of warnings){
    const key=String(warning.noteId);
    if(!byNote[key])byNote[key]=[];
    byNote[key].push(warning);
  }
  return byNote;
}

function noteWarningsByNoteId(){
  return S.noteWarningsByNoteId||{};
}

function noteWarningCountForNote(noteId){
  const warnings=noteWarningsByNoteId()[String(noteId)]||[];
  return warnings.length;
}

function noteWarningPulseActive(){
  return (S.noteWarningPulseUntil||0)>Date.now();
}

function centerTimelineOnBeat(targetBeat){
  const visibleW=Math.max(1,CW-LABEL_W);
  const maxScroll=Math.max(0,totalBeats()*S.zoom-visibleW);
  const desired=(targetBeat*S.zoom)-(visibleW/2);
  S.scrollX=clamp(desired,0,maxScroll);
}

function jumpToFirstWarningNote(){
  const warnings=S.noteWarnings||[];
  if(!warnings.length)return;
  const first=warnings[0];
  const ev=S.pluck.find(note=>note.id===first.noteId);
  if(!ev)return;

  const beat=parseBeat(ev.beat);
  const x=beatToX(beat);
  if(x<LABEL_W+8||x>CW-8){
    centerTimelineOnBeat(beat);
  }

  S.noteWarningPulseUntil=Date.now()+NOTE_WARNING_PULSE_MS;
  render();
}

function onNoteWarningsBadgeClick(event){
  event.preventDefault();
  event.stopPropagation();
  const badge=document.getElementById('note-warn');
  if(!badge)return;
  if(!(S.noteWarnings||[]).length)return;

  badge.classList.remove('pulse');
  void badge.offsetWidth;
  badge.classList.add('pulse');
  setTimeout(()=>badge.classList.remove('pulse'),700);

  jumpToFirstWarningNote();
}

function warningWeight(ruleId){
  if(ruleId==='overlap')return 11;
  if(ruleId==='too-close')return 8;
  if(ruleId==='open-string-risk')return 6;
  if(ruleId==='too-short')return 2;
  return 4;
}

function warningScore(warnings){
  let total=0;
  for(const warning of warnings||[])total+=warningWeight(warning.ruleId);
  return total;
}

function warningScoreForNote(noteId,warnings){
  let total=0;
  for(const warning of warnings||[]){
    if(warning.noteId===noteId)total+=warningWeight(warning.ruleId);
  }
  return total;
}

function candidateOnsetSteps(){
  const step=S.snapEnabled?Math.max(0.02,gridStep()/2):0.05;
  return [-2*step,-step,0,step,2*step];
}

function candidateOffsetSteps(){
  const step=S.snapEnabled?Math.max(0.02,gridStep()/2):0.05;
  return [-2*step,-step,0,step,2*step];
}

function candidateOctaveShifts(){
  return [0,-12,12,-24,24];
}

function noteFixState(ev){
  return {
    note:parseInt(ev.note,10)||52,
    startBeat:parseBeat(ev.beat),
    duration:Math.max(minDurationBeats(),parseFloat(ev.duration_b)||minDurationBeats()),
  };
}

function applyNoteFixState(ev,state){
  const start=Math.max(0,parseFloat(state.startBeat)||0);
  const duration=Math.max(minDurationBeats(),parseFloat(state.duration)||minDurationBeats());
  ev.note=clamp(parseInt(state.note,10)||52,MIDI_MIN,MIDI_MAX);
  ev.beat=beatLabel(start);
  ev.duration_b=trimBeatNumber(duration);
}

function movementPenalty(base,candidate){
  const semitones=Math.abs((parseInt(candidate.note,10)||0)-(parseInt(base.note,10)||0));
  const octaveMoves=semitones/12;
  const onsetDelta=Math.abs((parseFloat(candidate.startBeat)||0)-(parseFloat(base.startBeat)||0));
  const endBase=(parseFloat(base.startBeat)||0)+(parseFloat(base.duration)||0);
  const endCand=(parseFloat(candidate.startBeat)||0)+(parseFloat(candidate.duration)||0);
  const offsetDelta=Math.abs(endCand-endBase);
  return (octaveMoves*0.9)+(onsetDelta*2.0)+(offsetDelta*1.6);
}

function ruleThresholdSeconds(ruleId,fallback=0){
  const rule=NOTE_RULES.find(item=>item.id===ruleId);
  const raw=rule?.thresholdS;
  return Number.isFinite(parseFloat(raw))?parseFloat(raw):fallback;
}

function clampToPlayableOctave(noteRaw){
  let note=parseInt(noteRaw,10);
  if(!Number.isFinite(note))note=52;
  while(note>MIDI_MAX)note-=12;
  while(note<MIDI_MIN)note+=12;
  return clamp(note,MIDI_MIN,MIDI_MAX);
}

function optimizeNoteWarningsLayout(){
  if(!S.pluck.length)return {improved:false,before:0,after:0,moved:0};
  const originalById=new Map(S.pluck.map(ev=>[ev.id,noteFixState(ev)]));
  const initialWarnings=evaluatePluckNoteWarnings();
  const initialCount=initialWarnings.length;

  const spb=secondsPerBeat();
  const closeGapBeats=ruleThresholdSeconds('too-close',0.12)/Math.max(1e-6,spb);
  const minDurBeats=Math.max(minDurationBeats(),ruleThresholdSeconds('too-short',0.08)/Math.max(1e-6,spb));

  const byString=STRINGS.map(()=>[]);
  for(const ev of S.pluck){
    const stringIndex=noteRuleStringIndex(ev);
    byString[stringIndex].push(ev);
  }

  for(const events of byString){
    events.sort((a,b)=>parseBeat(a.beat)-parseBeat(b.beat)||a.id-b.id);
    let prevPlaced=null;

    for(const ev of events){
      const base=noteFixState(ev);
      const baseEnd=base.startBeat+base.duration;

      let requiredStart=0;
      if(prevPlaced){
        requiredStart=Math.max(requiredStart,prevPlaced.startBeat+closeGapBeats);
        requiredStart=Math.max(requiredStart,prevPlaced.endBeat+1e-4);
        const prevEvent=prevPlaced.ev;
        const prevDurationS=(prevPlaced.endBeat-prevPlaced.startBeat)*spb;
        const prevIsTremolo=prevDurationS>=0.5;
        const curSlide=parseInt(ev.slide||0,10)===1;
        if(prevIsTremolo&&!curSlide){
          const prepS=noteRulePrepTimeSeconds(prevEvent,ev);
          requiredStart=Math.max(requiredStart,prevPlaced.endBeat+(prepS/spb));
        }
      }

      let best={
        note:clampToPlayableOctave(base.note),
        startBeat:Math.max(0,base.startBeat),
        duration:Math.max(minDurBeats,base.duration),
      };
      let bestCost=Number.POSITIVE_INFINITY;

      for(const oct of candidateOctaveShifts()){
        const shifted=base.note+oct;
        if(shifted<MIDI_MIN||shifted>MIDI_MAX)continue;
        for(const onsetStep of candidateOnsetSteps()){
          let start=Math.max(0,base.startBeat+onsetStep);
          start=Math.max(start,requiredStart);
          start=trimBeatNumber(start);

          for(const offsetStep of candidateOffsetSteps()){
            const targetEnd=Math.max(start+minDurBeats,baseEnd+offsetStep);
            const duration=Math.max(minDurBeats,trimBeatNumber(targetEnd-start));
            const candidate={note:shifted,startBeat:start,duration};
            const cost=movementPenalty(base,candidate);
            if(cost<bestCost-1e-6){
              best=candidate;
              bestCost=cost;
            }
          }
        }
      }

      applyNoteFixState(ev,best);
      prevPlaced={
        ev,
        startBeat:parseBeat(ev.beat),
        endBeat:parseBeat(ev.beat)+Math.max(minDurBeats,parseFloat(ev.duration_b)||minDurBeats),
      };
    }
  }

  const currentWarnings=evaluatePluckNoteWarnings();
  if(currentWarnings.length>initialCount){
    for(const ev of S.pluck){
      const original=originalById.get(ev.id);
      if(!original)continue;
      applyNoteFixState(ev,original);
    }
  }

  const finalWarnings=evaluatePluckNoteWarnings();
  S.noteWarnings=finalWarnings;
  S.noteWarningsByNoteId=buildWarningIndex(finalWarnings);
  const afterWarnings=finalWarnings.length;

  let moved=0;
  for(const ev of S.pluck){
    const original=originalById.get(ev.id);
    if(!original)continue;
    const now=noteFixState(ev);
    const changedPitch=original.note!==now.note;
    const changedOnset=Math.abs(original.startBeat-now.startBeat)>1e-4;
    const changedDur=Math.abs(original.duration-now.duration)>1e-4;
    if(changedPitch||changedOnset||changedDur)moved++;
  }

  return {
    improved:afterWarnings<initialCount,
    before:initialCount,
    after:afterWarnings,
    moved,
  };
}

function renderNoteWarningsAndGetCount(){
  const warnings=evaluatePluckNoteWarnings();
  S.noteWarnings=warnings;
  S.noteWarningsByNoteId=buildWarningIndex(warnings);
  const badge=document.getElementById('note-warn');
  const count=warnings.length;

  if(badge){
    if(!count){
      badge.classList.remove('warn');
      badge.classList.add('ok');
      badge.textContent='✓ NOTES OK';
      badge.title='No note timing warnings';
      hideNoteWarningPopover();
    }else{
      badge.classList.remove('ok');
      badge.classList.add('warn');
      badge.textContent=`⚠ ${count} WARNINGS`;

      const lines=warnings.slice(0,8).map((warning,index)=>{
        const beatText=`@${warning.beat}`;
        const strText=`S${warning.stringIndex+1}`;
        return `${index+1}. ${beatText} ${strText} — ${warning.message}`;
      });
      if(warnings.length>lines.length)lines.push(`…and ${warnings.length-lines.length} more`);
      badge.title=lines.join('\n');
    }
  }

  return count;
}

function planStringsGreedy(){
  // Greedy string assignment: for each unassigned note (sorted by time),
  // pick the string whose current fret position requires the least travel.
  // Skips notes that already have an explicit string_index set.
  const lastFret=new Array(STRINGS.length).fill(0);
  const sorted=[...S.pluck].sort((a,b)=>parseBeat(a.beat)-parseBeat(b.beat));
  const changes=[];
  for(const ev of sorted){
    if(ev.note>=0&&ev.note<=5) continue; // chord-pluck shorthand, skip
    if(ev.string_index!=null) {
      // Respect pin; update lastFret so subsequent notes plan around it
      const s=parseInt(ev.string_index,10);
      if(s>=0&&s<STRINGS.length) lastFret[s]=ev.note-STRINGS[s].min;
      continue;
    }
    let bestStr=-1, bestCost=Infinity;
    STRINGS.forEach((s,i)=>{
      if(ev.note<s.min||ev.note>s.max) return;
      const fret=ev.note-s.min;
      const cost=Math.abs(fret-lastFret[i]);
      if(cost<bestCost){bestCost=cost;bestStr=i;}
    });
    if(bestStr>=0){
      changes.push({id:ev.id,string_index:bestStr});
      lastFret[bestStr]=ev.note-STRINGS[bestStr].min;
    }
  }
  if(!changes.length) return;
  pushHistorySnapshot(JSON.stringify(buildJSON()));
  changes.forEach(({id,string_index})=>{
    const ev=S.pluck.find(e=>e.id===id);
    if(ev) ev.string_index=string_index;
  });
  render();
}

function bindNoteWarningUI(){
  if(S.noteWarningUIBound)return;
  const badge=document.getElementById('note-warn');
  const planBtn=document.getElementById('btn-plan-strings');
  if(!badge)return;
  badge.addEventListener('click',onNoteWarningsBadgeClick);
  if(planBtn) planBtn.addEventListener('click',planStringsGreedy);
  S.noteWarningUIBound=true;
}

function renderNoteWarnings(){
  bindNoteWarningUI();
  renderNoteWarningsAndGetCount();
}
