// ═══════════════════════════════════════════════
// CANVAS
// ═══════════════════════════════════════════════
const canvas=document.getElementById('roll');
const ctx=canvas.getContext('2d');
let CW=0;

function resize(){
  CW=document.getElementById('roll-wrap').clientWidth;
  const h=canvasH();
  const dpr=window.devicePixelRatio||1;
  canvas.width=CW*dpr;
  canvas.height=h*dpr;
  canvas.style.width=CW+'px';
  canvas.style.height=h+'px';
  ctx.scale(dpr,dpr);
  render();
}

// ═══════════════════════════════════════════════
// RENDER
// ═══════════════════════════════════════════════
function render(){
  if(!ctx)return;
  ctx.clearRect(0,0,CW,canvasH());
  drawBG(); drawGrid(); drawLabels();
  drawCycleBar(); drawChordLane();
  const inAutomation = S.activeTab === 'automation';
  if(inAutomation){
    // Ghost notes as background reference, then full-opacity automation lanes
    ctx.save(); ctx.globalAlpha = 0.15; drawNotes(); ctx.restore();
    drawMidiLane(); drawTempoPointOverlay();
  } else {
    drawSlideLinks();
    if(S.spectrogramVisible) drawSpectrogram();
    drawNotes();
  }
  if(S.noteAnalysis && Object.keys(S.noteAnalysis).length) drawNoteAnalysisOverlay();
  drawPlayhead(); drawSelectionBox();
}

function drawSectionGuides(){
  if(!Array.isArray(S.sections)||!S.sections.length)return;

  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W,0,CW-LABEL_W,canvasH());
  ctx.clip();
  ctx.setLineDash([4,4]);
  ctx.lineWidth=1;
  ctx.font='600 10px "JetBrains Mono"';
  ctx.textAlign='left';
  ctx.textBaseline='top';

  const sections=[...S.sections]
    .filter(section=>Number.isFinite(section?.startBeat)&&Number.isFinite(section?.endBeat)&&section.endBeat>section.startBeat)
    .sort((a,b)=>a.startBeat-b.startBeat||a.endBeat-b.endBeat||a.id-b.id);

  for(const section of sections){
    const x1=beatToX(section.startBeat);
    const x2=beatToX(section.endBeat);
    if(x2<LABEL_W-2||x1>CW+2)continue;

    ctx.strokeStyle='rgba(34,211,238,0.62)';
    ctx.beginPath();
    ctx.moveTo(x1,0);
    ctx.lineTo(x1,canvasH());
    ctx.stroke();

    ctx.strokeStyle='rgba(245,158,11,0.55)';
    ctx.beginPath();
    ctx.moveTo(x2,0);
    ctx.lineTo(x2,canvasH());
    ctx.stroke();

    ctx.strokeStyle='rgba(94,234,212,0.45)';
    ctx.strokeRect(x1,2,Math.max(0,x2-x1),CHORD_H-4);

    const label=String(section.name||'').trim();
    if(label){
      ctx.fillStyle='rgba(94,234,212,0.88)';
      ctx.fillText(label,Math.max(LABEL_W+2,x1+3),4);
    }
  }

  ctx.setLineDash([]);
  ctx.restore();
}

function drawTempoPointOverlay(){
  const lane=tempoLane();
  if(!midiLaneVisible(lane))return;
  const selected=S.selMidiCurvePoints[TEMPO_AUTOMATION_KEY];
  if(!selected||selected.size!==1)return;

  const points=S.midiCurves[TEMPO_AUTOMATION_KEY]||[];
  let target=null;
  for(const point of points){
    if(selected.has(midiCurvePointKey(point.beat))){
      target=point;
      break;
    }
  }
  if(!target)return;

  const x=beatToX(target.beat);
  const y=midiYFromValue(target.value,lane);
  const valueText=`${clamp(Math.round(target.value),TEMPO_MIN,TEMPO_MAX)} BPM`;

  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, 0, CW - LABEL_W, canvasH());
  ctx.clip();
  ctx.font='600 10px "JetBrains Mono"';
  const textW=ctx.measureText(valueText).width;
  const padX=6;
  const bubbleW=textW+padX*2;
  const bubbleH=18;
  let bx=x+8;
  let by=y-24;

  if(bx+bubbleW>CW-4)bx=x-bubbleW-8;
  if(by<CHORD_H+2)by=y+8;

  ctx.fillStyle='rgba(10,10,16,0.92)';
  ctx.strokeStyle='#f59e0b';
  ctx.lineWidth=1;
  ctx.beginPath();
  ctx.roundRect(bx,by,bubbleW,bubbleH,5);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle='#fbbf24';
  ctx.textAlign='left';
  ctx.textBaseline='middle';
  ctx.fillText(valueText,bx+padX,by+bubbleH/2+0.5);
  ctx.restore();
}

function eventStringIndex(ev){
  if(ev&&ev.string_index!==null&&ev.string_index!==undefined){
    const explicit=parseInt(ev.string_index,10);
    if(Number.isFinite(explicit)&&explicit>=0&&explicit<STRINGS.length)return explicit;
  }
  if(ev.note===0) return 0;
  if(ev.note===2) return 1;
  if(ev.note===4) return 2;
  const inferred=STRINGS.findIndex(s=>ev.note>=s.min&&ev.note<=s.max);
  return inferred>=0?inferred:0;
}

function normalizeMidiCurvePoints(points,key='1'){
  const curveKey=String(key);
  const sorted=[...points].sort((a,b)=>a.beat-b.beat);
  const deduped=[];
  for(const point of sorted){
    const beat=trimBeatNumber(Math.max(0,parseFloat(point.beat)||0));
    const fallback=isTempoLaneKey(curveKey)?S.bpm:0;
    const value=clampAutomationValue(curveKey,parseFloat(point.value)||fallback);
    if(deduped.length&&Math.abs(deduped[deduped.length-1].beat-beat)<1e-4){
      deduped[deduped.length-1]={beat,value};
    }else{
      deduped.push({beat,value});
    }
  }
  return deduped;
}

function upsertMidiCurvePoint(curveKey,beat,value){
  const key=String(curveKey);
  const targetBeat=trimBeatNumber(Math.max(0,beat));
  const targetValue=clampAutomationValue(key,value);
  const points=S.midiCurves[key]||[];

  const filtered=points.filter(point=>{
    const pointBeat=trimBeatNumber(Math.max(0,parseFloat(point.beat)||0));
    if(!S.snapEnabled)return Math.abs(pointBeat-targetBeat)>1e-4;
    return Math.abs(snap(pointBeat)-targetBeat)>1e-4;
  });
  filtered.push({beat:targetBeat,value:targetValue});
  S.midiCurves[key]=normalizeMidiCurvePoints(filtered,key);
}

function clearMidiCurveRange(curveKey,startBeat,endBeat){
  const key=String(curveKey);
  const lo=Math.min(startBeat,endBeat);
  const hi=Math.max(startBeat,endBeat);
  const eps=1e-4;
  const points=S.midiCurves[key]||[];
  S.midiCurves[key]=points.filter(point=>{
    const pointBeat=trimBeatNumber(Math.max(0,parseFloat(point.beat)||0));
    return !(pointBeat>lo+eps&&pointBeat<hi-eps);
  });
}

function midiAutomationEvents(){
  const events=[];
  const interpDefault=1;
  for(const cc of MIDI_AUTOMATION_CCS){
    if(S.midiCurveMuted[String(cc)])continue;
    const points=normalizeMidiCurvePoints(S.midiCurves[String(cc)]||[],String(cc));
    points.forEach((point,index)=>{
      events.push({
        address:'/cc',
        args:[cc,point.value],
        interp:index<points.length-1?interpDefault:0,
        beat:beatLabel(point.beat),
      });
    });
  }
  return events;
}

function drawSlideLinks(){
  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, 0, CW - LABEL_W, canvasH());
  ctx.clip();

  const byString=STRINGS.map(()=>[]);
  for(const ev of S.pluck){
    byString[eventStringIndex(ev)].push(ev);
  }

  for(const events of byString){
    events.sort((a,b)=>parseBeat(a.beat)-parseBeat(b.beat)||a.id-b.id);
    for(let index=1;index<events.length;index++){
      const to=events[index];
      if(!to.slide)continue;
      const from=events[index-1];

      const fromBeat=parseBeat(from.beat);
      const toBeat=parseBeat(to.beat);
      const fromX=beatToX(fromBeat)+Math.max(8,from.duration_b*S.zoom);
      const toX=beatToX(toBeat);
      const fromY=noteToY(from.note)+(activeNoteH()/2);
      const toY=noteToY(to.note)+(activeNoteH()/2);

      if(toX<LABEL_W||fromX>CW)continue;

      const toStringIdx=eventStringIndex(to);
      const color=STRINGS[toStringIdx]?.color||strOf(to.note).color;
      ctx.strokeStyle=color;
      ctx.lineWidth=1.3;
      ctx.globalAlpha=0.85;
      ctx.beginPath();
      ctx.moveTo(fromX,fromY);
      ctx.lineTo(toX,toY);
      ctx.stroke();

      const angle=Math.atan2(toY-fromY,toX-fromX);
      const head=5;
      ctx.beginPath();
      ctx.moveTo(toX,toY);
      ctx.lineTo(toX-head*Math.cos(angle-Math.PI/6),toY-head*Math.sin(angle-Math.PI/6));
      ctx.lineTo(toX-head*Math.cos(angle+Math.PI/6),toY-head*Math.sin(angle+Math.PI/6));
      ctx.closePath();
      ctx.fillStyle=color;
      ctx.fill();
      ctx.globalAlpha=1;
    }
  }
  ctx.restore();
}

function drawCycleBar(){
  const range=getCycleRange();
  if(!range)return;
  const x1=Math.max(LABEL_W,beatToX(range.startBeat));
  const x2=Math.min(CW,beatToX(range.endBeat));
  if(x2<=x1)return;

  ctx.fillStyle='rgba(168,85,247,0.14)';
  ctx.fillRect(x1,0,x2-x1,canvasH());
  ctx.fillStyle='rgba(168,85,247,0.2)';
  ctx.fillRect(x1,0,x2-x1,CHORD_H);
  ctx.strokeStyle='#a855f7';
  ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(x1,0); ctx.lineTo(x1,canvasH()); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x2,0); ctx.lineTo(x2,canvasH()); ctx.stroke();
}

function drawBG(){
  // Chord lane
  ctx.fillStyle='#10101a'; ctx.fillRect(0,0,CW,CHORD_H);
  // Roll rows
  for(let n=MIDI_MIN;n<=MIDI_MAX;n++){
    const y=noteToY(n), s=strOf(n), isSharp=[1,3,6,8,10].includes(n%12);
    ctx.fillStyle=isSharp?'#08080e':s.dim; ctx.fillRect(LABEL_W,y,CW-LABEL_W,activeNoteH());
    ctx.fillStyle='#14141e'; ctx.fillRect(LABEL_W,y+activeNoteH()-1,CW-LABEL_W,1);
  }
  // Sliderless lanes (6 strings) — hidden in automation mode
  if(S.activeTab!=='automation'){
    const slTop = CHORD_H + rollH();
    for(let i=0; i<STRINGS.length; i++){
      const y=slTop + i*SLIDERLESS_H;
      ctx.fillStyle=i%2===0?'#101018':'#0c0c14';
      ctx.fillRect(LABEL_W,y,CW-LABEL_W,SLIDERLESS_H);
      ctx.fillStyle='#14141e'; ctx.fillRect(LABEL_W,y+SLIDERLESS_H-1,CW-LABEL_W,1);
    }
  }
  // MIDI lane
  const my=midiTopY();
  if (S.activeTab === 'automation') {
    for(let lane=0;lane<MIDI_LANE_COUNT;lane++){
      if(!midiLaneVisible(lane))continue;
      const top=midiLaneTop(lane);
      const height=midiLaneHeight(lane);
      const laneKey=automationLaneKey(lane);
      const isTempo=lane!==MIDI_GENERAL_LANE_INDEX&&isTempoLaneKey(laneKey);
      ctx.fillStyle=isTempo?'#10141b':(lane%2===0?'#0a0a12':'#0d0d16');
      ctx.fillRect(LABEL_W,top,CW-LABEL_W,height);
    }
  }
  // Label column
  ctx.fillStyle='#0e0e16';
  ctx.fillRect(0,0,LABEL_W,canvasH());
  ctx.fillStyle='#161622'; ctx.fillRect(0,0,LABEL_W,CHORD_H);
  if (S.activeTab === 'automation') {
    ctx.fillRect(0,my,LABEL_W,MIDI_H);
  }
  // Lane labels
  ctx.fillStyle='#383860'; ctx.font='500 9px "JetBrains Mono"'; ctx.textAlign='center';
  ctx.fillText('CHD',LABEL_W/2,CHORD_H/2+3);
  if (S.activeTab === 'automation') {
    for(let lane=0;lane<MIDI_LANE_COUNT;lane++){
      if(!midiLaneVisible(lane))continue;
      const top=midiLaneTop(lane);
      const h=midiLaneHeight(lane);
      const laneKey=automationLaneKey(lane);
      const label=lane===MIDI_GENERAL_LANE_INDEX
        ?'FX'
        :(isTempoLaneKey(laneKey)
          ?`TMP${S.midiCurveMuted[String(laneKey)]?' (M)':''}`
          :`CC${laneKey}${S.midiCurveMuted[String(laneKey)]?' (M)':''}`);
      ctx.fillText(label,LABEL_W/2,top+h/2+3);
    }
  }
}

function drawGrid(){
  const tb=totalBeats(), m=bpm();
  const gs=gridStep(), eps=gs*0.05;
  const measureLabelXs=[];
  for(let b=0; b<=tb+eps; b+=gs){
    const br=parseFloat(b.toFixed(9));
    const x=beatToX(br);
    if(x<LABEL_W-1||x>CW+1)continue;
    const remM=br%m, isMeasure=remM<eps||(m-remM)<eps;
    const remB=br%1,  isBeat=remB<eps||(1-remB)<eps;
    ctx.strokeStyle=isMeasure?'#323250':isBeat?'#1e1e34':'#141428';
    ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,canvasH()); ctx.stroke();
    if(isMeasure){
      measureLabelXs.push({x,bar:Math.round(br/m)+1});
    }
  }

  ctx.fillStyle='#8f8fd8';
  ctx.font='700 10px "JetBrains Mono"';
  ctx.textAlign='left';
  ctx.shadowColor='rgba(0,0,0,0.55)';
  ctx.shadowBlur=2;
  for(const label of measureLabelXs){
    ctx.fillText(label.bar,label.x+3,CHORD_H-4);
  }
  ctx.shadowBlur=0;

  // Zone separators
  ctx.strokeStyle='#232340'; ctx.lineWidth=1;
  const slTop = CHORD_H + rollH();
  const zoneLines = [[0,CHORD_H],[0,slTop]];
  if(S.activeTab!=='automation'){
    for(let i=1; i<=6; i++) zoneLines.push([0, slTop+SLIDERLESS_H*i]);
  }
  zoneLines.forEach(([,y])=>{
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(CW,y); ctx.stroke();
  });
  if (S.activeTab === 'automation') {
    for(let lane=0;lane<MIDI_LANE_COUNT;lane++){
      if(!midiLaneVisible(lane))continue;
      const y=midiLaneTop(lane);
      ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(CW,y); ctx.stroke();
    }
    ctx.beginPath(); ctx.moveTo(0,midiTopY()+MIDI_H); ctx.lineTo(CW,midiTopY()+MIDI_H); ctx.stroke();
  }
  ctx.beginPath(); ctx.moveTo(LABEL_W,0); ctx.lineTo(LABEL_W,canvasH()); ctx.stroke();

  // Bottom time ruler (seconds), companion to top bar numbering
  const rulerH=14;
  const rulerY=canvasH()-rulerH;
  ctx.fillStyle='rgba(10,10,18,0.92)';
  ctx.fillRect(LABEL_W,rulerY,CW-LABEL_W,rulerH);
  ctx.strokeStyle='#232340';
  ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(LABEL_W,rulerY); ctx.lineTo(CW,rulerY); ctx.stroke();

  const totalSeconds=beatsToSeconds(tb);
  const secStep=secondsTickStep();
  const visibleStartSec=beatsToSeconds(Math.max(0,xToBeat(LABEL_W)));
  const tickStart=Math.floor(visibleStartSec/secStep)*secStep;
  const startSec=Math.max(0,tickStart-secStep);
  const endSec=totalSeconds+secStep;
  ctx.font='500 9px "JetBrains Mono"';
  ctx.textAlign='left';
  for(let sec=startSec;sec<=endSec+1e-6;sec+=secStep){
    const beat=sec/Math.max(1e-6,secondsPerBeat());
    const x=beatToX(beat);
    if(x<LABEL_W-2||x>CW+2)continue;
    ctx.strokeStyle='#2a2a44';
    ctx.beginPath(); ctx.moveTo(x,rulerY); ctx.lineTo(x,canvasH()); ctx.stroke();
    ctx.fillStyle='#565680';
    ctx.fillText(formatTimelineSeconds(sec),x+2,canvasH()-4);
  }
}

function drawLabels(){
  ctx.textAlign='right';
  for(let n=MIDI_MIN;n<=MIDI_MAX;n++){
    const y=noteToY(n), isC=(n%12)===0, isSharp=[1,3,6,8,10].includes(n%12);
    ctx.fillStyle=isC?'#5858a0':isSharp?'#1e1e38':'#303058';
    ctx.font=(isC?'600':'400')+' 9px "JetBrains Mono"';
    ctx.fillText(noteName(n),LABEL_W-4,y+activeNoteH()/2+3);
  }
  // Sliderless lane labels — hidden in automation mode
  if(S.activeTab!=='automation'){
    const slTop = CHORD_H + rollH();
    for(let i=0; i<STRINGS.length; i++){
      // Lane 0 = highest string (E4), lane 5 = lowest (E2)
      const s = STRINGS[STRINGS.length - 1 - i];
      const y = slTop + i*SLIDERLESS_H;
      ctx.fillStyle = s.color;
      ctx.font = '600 9px "JetBrains Mono"';
      ctx.fillText(s.name, LABEL_W-4, y+SLIDERLESS_H/2+3);
    }
  }
  // String lanes + controls in left column
  STRINGS.forEach((s,index)=>{
    const rects=stringTrackControlRects(index);
    if(!rects)return;
    const isSoloed=S.stringSoloIndex===index;
    const hasAnySolo=Number.isInteger(S.stringSoloIndex);
    const isMuted=!!S.stringMuted[index];
    const inactive=(hasAnySolo&&!isSoloed)||isMuted;

    ctx.fillStyle=inactive?'#1a1a28':s.dim;
    ctx.fillRect(1,rects.bounds.top+1,LABEL_W-2,rects.bounds.height-2);
    ctx.fillStyle=inactive?'#303050':s.color+'aa';
    ctx.fillRect(2,rects.bounds.top+1,3,rects.bounds.height-2);

    ctx.font='600 8px "JetBrains Mono"';
    ctx.textAlign='left';
    ctx.fillStyle=inactive?'#4a4a72':'#a5a5d0';
    ctx.fillText(s.name,rects.label.x,rects.label.y+rects.label.h-1);

    const drawBtn=(r,label,on,color)=>{
      ctx.fillStyle=on?color+'cc':'#181827';
      ctx.strokeStyle=on?color:'#2e2e48';
      ctx.lineWidth=1;
      ctx.beginPath();
      ctx.roundRect(r.x, r.y, r.w, r.h, 4);
      ctx.fill();
      ctx.stroke();
      ctx.font='600 10px "JetBrains Mono"';
      ctx.fillStyle=on?'#0c0c12':'#6d6d98';
      ctx.textAlign='center';
      ctx.textBaseline='middle';
      ctx.fillText(label,r.x+r.w/2,r.y+r.h/2 + 0.5);
    };

    drawBtn(rects.solo,'S',isSoloed,'#22d3ee');
    drawBtn(rects.mute,'M',isMuted,'#f43f5e');
  });
}

function drawChordLane(){
  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, 0, CW - LABEL_W, canvasH());
  ctx.clip();

  state.chord.forEach(ev=>{
    const x=beatToX(parseBeat(ev.beat));
    if(x<LABEL_W-60||x>CW+20)return;
    const sel=ev.id===S.selChord;
    const col=sel?'#fbbf24':'#8a760e';
    // Stem
    ctx.fillStyle=col; ctx.fillRect(x-1,4,2,CHORD_H-8);
    // Flag box
    const fw=Math.max(36,ev.chord.length*8+10);
    ctx.fillStyle=sel?'#fbbf2418':'#8a760e18';
    ctx.fillRect(x,4,fw,CHORD_H-10);
    ctx.strokeStyle=col; ctx.lineWidth=1;
    ctx.strokeRect(x,4,fw,CHORD_H-10);
    ctx.fillStyle=col; ctx.font='600 10px "JetBrains Mono"';
    ctx.textAlign='left'; ctx.fillText(ev.chord,x+5,CHORD_H-9);
  });
  ctx.restore();
}

function drawMidiLane(){
  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, 0, CW - LABEL_W, canvasH());
  ctx.clip();

  if(midiLaneVisible(MIDI_GENERAL_LANE_INDEX)){
  const cy=midiLaneTop(MIDI_GENERAL_LANE_INDEX)+midiLaneHeight(MIDI_GENERAL_LANE_INDEX)/2;
  S.midi.forEach(ev=>{
    const x=beatToX(parseBeat(ev.beat));
    if(x<LABEL_W-20||x>CW+20)return;
    const sel=ev.id===S.selMidi;
    const col=sel?'#22d3ee':'#0e7a8c';
    const sz=sel?8:6;
    ctx.beginPath();
    ctx.moveTo(x,cy-sz); ctx.lineTo(x+sz,cy);
    ctx.lineTo(x,cy+sz); ctx.lineTo(x-sz,cy);
    ctx.closePath();
    ctx.fillStyle=col+(sel?'':'88'); ctx.fill();
    ctx.strokeStyle=col; ctx.lineWidth=1; ctx.stroke();
    ctx.fillStyle=col; ctx.font='500 9px "JetBrains Mono"';
    ctx.textAlign='left'; ctx.fillText(ev.address,x+sz+3,cy+3);
  });
  }

  for(let lane=0;lane<MIDI_AUTOMATION_KEYS.length;lane++){
    if(!midiLaneVisible(lane))continue;
    const laneKey=automationLaneKey(lane);
    const points=[...(S.midiCurves[String(laneKey)]||[])].sort((a,b)=>a.beat-b.beat);
    if(!points.length)continue;
    const muted=!!S.midiCurveMuted[String(laneKey)];

    const color=isTempoLaneKey(laneKey)?'#f59e0b':(String(laneKey)==='7'?'#22d3ee':'#a855f7');
    ctx.strokeStyle=color;
    ctx.lineWidth=1.8;
    ctx.globalAlpha=muted?0.28:0.9;
    ctx.beginPath();
    points.forEach((point,index)=>{
      const x=beatToX(point.beat);
      const y=midiYFromValue(point.value,lane);
      if(index===0)ctx.moveTo(x,y); else ctx.lineTo(x,y);
    });
    ctx.stroke();
    ctx.globalAlpha=1;

    for(const point of points){
      const x=beatToX(point.beat);
      const y=midiYFromValue(point.value,lane);
      if(x<LABEL_W-4||x>CW+4)continue;
      const selected=isMidiCurvePointSelected(laneKey,point);
      if(selected){
        ctx.beginPath();
        ctx.arc(x,y,5.2,0,Math.PI*2);
        ctx.strokeStyle=color;
        ctx.lineWidth=1.8;
        ctx.globalAlpha=muted?0.45:1;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(x,y,selected?3.6:2.7,0,Math.PI*2);
      ctx.fillStyle=color;
      ctx.globalAlpha=muted?0.35:1;
      ctx.fill();
      ctx.strokeStyle='#0b0b0f';
      ctx.lineWidth=1;
      ctx.stroke();
      ctx.globalAlpha=1;
    }
  }
  ctx.restore();
}

function drawNotes(){
  S.pluck.forEach(ev=>{
    const b=parseBeat(ev.beat), x=beatToX(b);
    const y=noteToY(ev.note);
    const w=Math.max(8,ev.duration_b*S.zoom);
    if(x+w<LABEL_W||x>CW)return;
    const sel=ev.id===S.selPluck||S.selPluckIds.has(ev.id);
    const stringIdx=eventStringIndex(ev);
    const s=STRINGS[stringIdx]||strOf(ev.note);
    const isTrem=hasTremolo(ev);
    const cx2=Math.max(LABEL_W,x), cw2=Math.min(CW,x+w)-cx2;
    if(cw2<=0)return;

    ctx.save();
    ctx.beginPath(); ctx.rect(cx2,y+1,cw2,activeNoteH()-2); ctx.clip();

    // Body
    ctx.fillStyle=s.color+(sel?'ee':'bb');
    ctx.fillRect(x,y+1,w,activeNoteH()-2);

    // Slide stripes
    if(ev.slide){
      ctx.strokeStyle='rgba(255,255,255,0.22)'; ctx.lineWidth=1;
      for(let sx=x-activeNoteH();sx<x+w+activeNoteH();sx+=5){
        ctx.beginPath(); ctx.moveTo(sx,y+1); ctx.lineTo(sx+activeNoteH()-2,y+activeNoteH()-1); ctx.stroke();
      }

      const markerX=Math.max(LABEL_W+3, x+4);
      const markerY=y+(activeNoteH()/2);
      ctx.beginPath();
      ctx.moveTo(markerX+6,markerY-4);
      ctx.lineTo(markerX,markerY);
      ctx.lineTo(markerX+6,markerY+4);
      ctx.strokeStyle='rgba(255,255,255,0.8)';
      ctx.lineWidth=1.4;
      ctx.stroke();
    }
    // Tremolo wave
    if(isTrem){
      ctx.strokeStyle='rgba(0,0,0,0.45)'; ctx.lineWidth=1.5;
      const my2=y+activeNoteH()/2;
      ctx.beginPath();
      for(let tx=x;tx<x+w;tx+=2){
        const wy=my2+Math.sin((tx-x)*1.2)*2.2;
        tx===x?ctx.moveTo(tx,wy):ctx.lineTo(tx,wy);
      }
      ctx.stroke();
    }
    ctx.restore();

    // Border
    ctx.strokeStyle=sel?'#fff':s.color;
    ctx.lineWidth=sel?1.5:0.8;
    if(sel){ctx.shadowBlur=10;ctx.shadowColor=s.color}
    ctx.strokeRect(cx2,y+1,cw2,activeNoteH()-2);
    ctx.shadowBlur=0;

    // Resize handle
    const hx=Math.min(CW-4,x+w-4);
    if(hx>=LABEL_W){
      ctx.fillStyle='rgba(255,255,255,0.45)';
      ctx.fillRect(hx,y+2,3,activeNoteH()-4);
    }

    const layout=(typeof noteWarningBadgeLayout==='function')?noteWarningBadgeLayout(ev):null;
    if(layout){
      const pulse=(typeof noteWarningPulseActive==='function')?noteWarningPulseActive():false;
      const badgeR=layout.r;
      const badgeCx=layout.cx;
      const badgeCy=layout.cy;

      ctx.save();
      if(pulse){
        ctx.shadowColor='rgba(251,191,36,0.95)';
        ctx.shadowBlur=16;
      }
      ctx.fillStyle='rgba(245,158,11,0.96)';
      ctx.beginPath();
      ctx.arc(badgeCx,badgeCy,badgeR,0,Math.PI*2);
      ctx.fill();
      ctx.strokeStyle='#fff3c4';
      ctx.lineWidth=1.4;
      ctx.stroke();

      ctx.shadowBlur=0;
      ctx.fillStyle='#19130a';
      ctx.font='700 9px "JetBrains Mono"';
      ctx.textAlign='center';
      ctx.textBaseline='middle';
      ctx.fillText(String(Math.min(99,layout.warningCount)),badgeCx,badgeCy+0.5);

      ctx.strokeStyle='rgba(245,158,11,0.85)';
      ctx.lineWidth=1;
      ctx.beginPath();
      ctx.moveTo(badgeCx+badgeR*0.45,badgeCy+badgeR*0.45);
      ctx.lineTo(cx2,y+1);
      ctx.stroke();
      ctx.restore();
    }
  });
}

function drawSelectionBox(){
  if(!drag||drag.type!=='select-box')return;
  const x=Math.min(drag.sx,drag.cx), y=Math.min(drag.sy,drag.cy);
  const w=Math.abs(drag.cx-drag.sx), h=Math.abs(drag.cy-drag.sy);
  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, 0, CW - LABEL_W, canvasH());
  ctx.clip();
  ctx.setLineDash([4,3]);
  ctx.fillStyle='rgba(34,211,238,0.14)';
  ctx.strokeStyle='#22d3ee';
  ctx.lineWidth=1;
  ctx.fillRect(x,y,w,h);
  ctx.strokeRect(x,y,w,h);
  ctx.restore();
}

function drawPlayhead(){
  if(!S.playing&&S.playBeat===0)return;
  const x=beatToX(S.playBeat);
  if(x<LABEL_W-5||x>CW+5)return;
  
  ctx.save();
  ctx.beginPath();
  ctx.rect(LABEL_W, 0, CW - LABEL_W, canvasH());
  ctx.clip();

  ctx.strokeStyle='#f43f5e'; ctx.lineWidth=1.5;
  ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,canvasH()); ctx.stroke();
  ctx.fillStyle='#f43f5e';
  ctx.beginPath(); ctx.moveTo(x-5,0); ctx.lineTo(x+5,0); ctx.lineTo(x,8); ctx.closePath(); ctx.fill();
  ctx.restore();
}
