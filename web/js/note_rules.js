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
  if(note===0) return 0;
  if(note===2) return 1;
  if(note===4) return 2;
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
  const byString=[[],[],[]];

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

function bindNoteWarningUI(){
  if(S.noteWarningUIBound)return;
  const badge=document.getElementById('note-warn');
  if(!badge)return;
  badge.addEventListener('click',onNoteWarningsBadgeClick);
  S.noteWarningUIBound=true;
}

function renderNoteWarnings(){
  bindNoteWarningUI();
  const badge=document.getElementById('note-warn');
  if(!badge)return;
  const warnings=evaluatePluckNoteWarnings();
  S.noteWarnings=warnings;
  S.noteWarningsByNoteId=buildWarningIndex(warnings);
  const count=warnings.length;

  if(!count){
    badge.classList.remove('warn');
    badge.classList.add('ok');
    badge.textContent='✓ NOTES OK';
    badge.title='No note timing warnings';
    hideNoteWarningPopover();
    return;
  }

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
