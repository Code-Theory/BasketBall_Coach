const $ = id => document.getElementById(id);
let currentJob = null, previewImage = null, hoop = null, origin = null, draft = null, pollTimer = null, hoopTimer = null, hoopTouched = false;
let demoVideoUrl = null;
const canvas = $('preview'), ctx = canvas.getContext('2d');
const show = (id, yes) => $(id).classList.toggle('hidden', !yes);
function journey(step){document.querySelectorAll('.journey [data-step]').forEach(el=>el.classList.toggle('active',el.dataset.step===step));}
function imageSource(filename){return filename && filename.startsWith('data:') ? filename : '/media/'+currentJob+'/'+filename;}
// A server started before an update may still serve a cached older template.
// Add the review controls if that page is paired with this newer script.
function ensureReviewControls() {
  const actions = document.querySelector('.review-actions');
  if (!actions) return;
  for (const [id, label] of [['replay-shot', 'Replay selected shot'], ['jump-rim', 'Jump to rim'], ['confirm-shot', 'Confirm outcome']]) {
    if (!$(id)) {
      const button = document.createElement('button');
      button.id = id; button.type = 'button'; button.className = 'button button-quiet'; button.textContent = label;
      actions.prepend(button);
    }
  }
  if (!$('outcome-detail')) {
    const detail = document.createElement('p');
    detail.id = 'outcome-detail'; detail.className = 'outcome-detail'; detail.setAttribute('role', 'status');
    actions.insertAdjacentElement('afterend', detail);
  }
}
ensureReviewControls();
function error(message) { $('error').textContent = message; show('error', true); $('error').scrollIntoView({behavior:'smooth', block:'nearest'}); }
function clearError() { show('error', false); }

async function selectFile(file) {
  if (!file) return;
  clearError();
  if (file.size > 200 * 1024 * 1024) return error('Please choose a video under 200 MB.');
  $('dropzone').classList.add('busy');
  const data = new FormData(); data.append('video', file);
  try {
    const response = await fetch('/api/upload', {method:'POST', body:data});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Upload failed.');
    currentJob = result.id; hoop = null; draft = null; hoopTouched = false; clearTimeout(hoopTimer);
    $('video-name').textContent = result.filename;
    $('selection-status').textContent = 'Finding the hoop...'; $('analyze').disabled = true;
    previewImage = new Image();
    previewImage.onload = () => { canvas.width = previewImage.naturalWidth; canvas.height = previewImage.naturalHeight; draw(); };
    previewImage.src = result.preview;
    show('workspace', false); show('results', false); show('prepare', true); journey('rim'); findHoop(currentJob);
    $('prepare').scrollIntoView({behavior:'smooth', block:'start'});
  } catch (e) { error(e.message || 'Could not upload this video.'); }
  finally { $('dropzone').classList.remove('busy'); $('video-file').value = ''; }
}

async function findHoop(job) {
  try {
    const response = await fetch('/api/jobs/' + job);
    if (!response.ok) throw new Error('Could not check the hoop');
    const data = await response.json();
    if (job !== currentJob || hoopTouched) return;
    if (data.hoop_search === 'searching') { hoopTimer = setTimeout(() => findHoop(job), 1200); return; }
    hoop = data.suggested_hoop;
    $('selection-status').textContent = hoop ? 'Hoop found. Check the box and adjust it if needed.' : 'Hoop not found. Draw a box around the rim, or continue without it.';
    $('analyze').disabled = false;
    draw();
  } catch (_) {
    if (job === currentJob && !hoopTouched) { $('selection-status').textContent = 'Draw a box around the rim, or continue without it.'; $('analyze').disabled = false; }
  }
}
$('video-file').addEventListener('change', e => selectFile(e.target.files[0]));
$('dropzone').addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); $('video-file').click();}});
for (const event of ['dragenter','dragover']) $('dropzone').addEventListener(event, e => {e.preventDefault(); $('dropzone').classList.add('drag');});
for (const event of ['dragleave','drop']) $('dropzone').addEventListener(event, e => {e.preventDefault(); $('dropzone').classList.remove('drag');});
$('dropzone').addEventListener('drop', e => selectFile(e.dataTransfer.files[0]));
function pos(e) { const r=canvas.getBoundingClientRect(); return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]; }
function draw() {
  if (!previewImage) return;
  ctx.drawImage(previewImage,0,0,canvas.width,canvas.height);
  const box = draft || hoop;
  if (box) {const [x1,y1,x2,y2] = box; ctx.lineWidth=Math.max(2,canvas.width/350);ctx.strokeStyle='#bfe0b5';ctx.fillStyle='rgba(185,224,181,.15)';ctx.fillRect(x1*canvas.width,y1*canvas.height,(x2-x1)*canvas.width,(y2-y1)*canvas.height);ctx.strokeRect(x1*canvas.width,y1*canvas.height,(x2-x1)*canvas.width,(y2-y1)*canvas.height);}
}
canvas.addEventListener('pointerdown', e => {origin=pos(e);canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove', e => {if(!origin)return; const p=pos(e);draft=[Math.min(origin[0],p[0]),Math.min(origin[1],p[1]),Math.max(origin[0],p[0]),Math.max(origin[1],p[1])];draw();});
canvas.addEventListener('pointerup', e => {if(!origin)return;origin=null;if(draft && draft[2]-draft[0]>=.01 && draft[3]-draft[1]>=.005){hoop=draft;hoopTouched=true;clearTimeout(hoopTimer);$('analyze').disabled=false;$('selection-status').textContent='Hoop selected. Adjust the box by drawing again.';}draft=null;draw();});
$('clear-hoop').addEventListener('click',()=>{hoop=null;draft=null;hoopTouched=true;clearTimeout(hoopTimer);$('analyze').disabled=false;$('selection-status').textContent='No hoop selected. Draw a box to estimate makes and misses.';draw();});
function reset(){setSavedSession(null);clearTimeout(pollTimer);clearTimeout(hoopTimer);currentJob=null;hoop=null;previewImage=null;if(demoVideoUrl){URL.revokeObjectURL(demoVideoUrl);demoVideoUrl=null;}show('prepare',false);show('results',false);show('loading',false);show('workspace',true);journey('upload');clearError();window.scrollTo({top:0,behavior:'smooth'});}
$('change-video').addEventListener('click',reset);$('start-over').addEventListener('click',reset);
$('analyze').addEventListener('click', async()=>{
  if(!currentJob)return; clearError(); $('analyze').disabled=true;
  try {const r=await fetch('/api/analyze/'+currentJob,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hoop})});const data=await r.json();if(!r.ok){if(r.status===409 && data.active_job){currentJob=data.active_job;}else throw new Error(data.error||'Could not start analysis.');}setSavedSession(currentJob);show('prepare',false);show('loading',true);journey('analyze');$('loading').scrollIntoView({behavior:'smooth',block:'center'});poll();}
  catch(e){error(e.message);} finally{$('analyze').disabled=false;}
});
async function poll(){
  try {const r=await fetch('/api/jobs/'+currentJob);const data=await r.json();if(!r.ok)throw new Error('Could not read analysis status.');
    $('progress-bar').style.width=(data.progress||0)+'%';$('progress-number').textContent=(data.progress||0)+'%';$('progress-message').textContent=data.message||'Analyzing your clip…';
    if(data.state==='done'){setSavedSession(currentJob);show('loading',false);renderResults(data.result);show('results',true);$('results').scrollIntoView({behavior:'smooth',block:'start'});return;}
    if(data.state==='error')throw new Error(data.error||'Analysis failed.');
    pollTimer=setTimeout(poll,1000);
  }catch(e){show('loading',false);show('prepare',true);error(e.message+' Please choose another video and try again.');}
}
let reviewResult = null, selectedShot = null, saveQueue = Promise.resolve(), saveRevision = 0;
const sessionKey = 'courtvision.lastReview';
function setSavedSession(job) { try { if (job) localStorage.setItem(sessionKey, job); else localStorage.removeItem(sessionKey); } catch (_) {} }
function queueReviewSave() {
  if (!currentJob || !reviewResult) return;
  if(currentJob==='demo'){$('save-status').textContent='Demo changes are temporary';return;}
  const job = currentJob, revision = ++saveRevision;
  const shots = reviewResult.shots.map(shot => ({id: Number.isInteger(shot.id) ? shot.id : null, seconds: shot.seconds, outcome: shot.outcome, reviewed: !!shot.reviewed}));
  $('save-status').textContent = 'Saving...';
  saveQueue = saveQueue.catch(() => {}).then(async () => {
    const response = await fetch('/api/jobs/' + job + '/review', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({shots})});
    if (!response.ok) throw new Error('Save failed');
    if (currentJob === job && revision === saveRevision) $('save-status').textContent = 'Review saved';
  }).catch(() => {
    if (currentJob === job && revision === saveRevision) $('save-status').textContent = 'Could not save changes';
  });
}
async function restoreReview() {
  let job; try { job = localStorage.getItem(sessionKey); } catch (_) { return; }
  if (!job || !/^[0-9a-f]{32}$/.test(job)) return;
  try {
    const response = await fetch('/api/jobs/' + job);
    if (!response.ok) { setSavedSession(null); return; }
    const item = await response.json();
    if (currentJob) return;
    if (item.state === 'running') {
      currentJob = job; show('workspace', false); show('loading', true); journey('analyze'); poll(); return;
    }
    if (item.state !== 'done' || !item.result) { setSavedSession(null); return; }
    currentJob = job; renderResults(item.result); show('workspace', false); show('results', true);
  } catch (_) { /* The last review remains available when the server returns. */ }
}
function renderResults(r){
  reviewResult = r;
  selectedShot = r.shots.length ? r.shots[0] : null;
  $('review-video').src = currentJob==='demo' ? demoVideoUrl : '/api/jobs/' + currentJob + '/video';
  $('session-label').textContent=currentJob==='demo' ? 'Illustrative demo · simulated footage and example measurements.' : 'Every rep is a chance to see something new.';
  $('save-status').textContent=currentJob==='demo' ? 'Demo changes are temporary' : 'Review saved';
  journey('review');
  $('video-duration').textContent=r.video_duration+' sec'; $('ball-frames').textContent=r.ball_frames+' / '+r.processed_frames+' frames';
  const trace=$('trajectory'); trace.replaceChildren();
  if(r.trajectory){const img=document.createElement('img');img.src='/media/'+currentJob+'/'+r.trajectory;img.alt='Detected basketball trajectory';trace.append(img);}else trace.textContent='No ball path available';
  drawReview();
}
function drawReview(){
  ensureReviewControls();
  const shots=reviewResult.shots;
  $('attempts').textContent=shots.length;
  const made=shots.filter(s=>s.outcome==='made').length;
  const missed=shots.filter(s=>s.outcome==='missed').length;
  const uncertain=shots.filter(s=>s.outcome==='uncertain').length;
  const lowEvidence=shots.filter(s=>!s.reviewed && s.outcome!=='uncertain' && s.tracking && (s.tracking.evidence==='low' || ['fit','extrapolated'].includes(s.tracking.method))).length;
  $('made').textContent=(shots.length && !made && !missed) ? '--' : made;
  $('missed').textContent=(shots.length && !made && !missed) ? '--' : missed;
  $('uncertain').textContent=uncertain+lowEvidence;
  const reviewed=shots.filter(s=>s.reviewed && s.outcome!=='uncertain');
  const reviewedPct=reviewed.length ? Math.round(100*reviewed.filter(s=>s.outcome==='made').length/reviewed.length)+'% reviewed shooting' : 'No reviewed shooting percentage yet';
  $('review-summary').textContent=uncertain+' uncertain, '+lowEvidence+' low-evidence. '+reviewedPct+'.';
  const list=$('shot-list'); list.replaceChildren();
  if(!shots.length) list.textContent='No shots detected. Review the video and add attempts manually.';
  shots.forEach((shot,index)=>{
    const item=document.createElement('div'); item.className='shot-item'+(shot===selectedShot?' selected':'');item.dataset.outcome=shot.outcome;
    const choose=document.createElement('button'); choose.type='button'; choose.textContent='Shot '+(index+1)+'  /  '+shot.seconds.toFixed(2)+'s'; choose.setAttribute('aria-pressed', String(shot===selectedShot));
    choose.addEventListener('click',()=>{selectedShot=shot;$('review-video').currentTime=Math.max(0,shot.seconds-1);drawReview();});
    const select=document.createElement('select'); select.setAttribute('aria-label','Outcome for shot '+(index+1));
    for(const [value,label] of [['uncertain','Uncertain'],['made','Made'],['missed','Missed']]){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}
    select.value=shot.outcome;select.addEventListener('change',()=>{shot.outcome=select.value;shot.reviewed=true;drawReview();queueReviewSave();});
    const remove=document.createElement('button'); remove.type='button';remove.textContent='Remove';remove.setAttribute('aria-label','Remove shot '+(index+1));
    remove.addEventListener('click',()=>{shots.splice(shots.indexOf(shot),1);if(selectedShot===shot)selectedShot=shots[0]||null;drawReview();queueReviewSave();});
    item.append(choose,select,remove);
    const evidence=document.createElement('small'); evidence.className='shot-evidence';
    evidence.textContent=shot.reviewed ? 'Manually reviewed' : shot.outcome==='uncertain' ? 'Needs review' : shot.tracking && (shot.tracking.evidence==='low' || ['fit','extrapolated'].includes(shot.tracking.method)) ? 'Low-evidence estimate · review' : 'Automatic estimate · review';
    item.append(evidence);list.append(item);
  });
  const stages=selectedShot ? selectedShot.stages : {};
  const detail=$('outcome-detail');
  $('replay-shot').disabled=!selectedShot;
  $('jump-rim').disabled=!(selectedShot && selectedShot.tracking && Number.isFinite(selectedShot.tracking.crossing_seconds));
  $('confirm-shot').disabled=!(selectedShot && selectedShot.outcome !== 'uncertain');
  if(!selectedShot) detail.textContent='Select a shot to see its outcome and review the video.';
  else if(selectedShot.reviewed) detail.textContent='Manually reviewed outcome. Watch the video again to check your selection.';
  else if(selectedShot.outcome==='uncertain') detail.textContent=reviewResult.hoop_selected ? 'Outcome uncertain: the tracker did not find enough matching evidence near the rim. Replay the shot and select an outcome.' : 'Outcome uncertain: no rim was selected. Review the video and select an outcome.';
  else if(selectedShot.tracking && (selectedShot.tracking.evidence==='low' || ['fit','extrapolated'].includes(selectedShot.tracking.method))) detail.textContent='Low-evidence estimate: the tracker fitted the ball path near the rim, so this is not a confirmed score. Replay the rim and check the outcome.';
  else detail.textContent='Automatically estimated outcome. A 2D camera view can be ambiguous; replay the rim and confirm it.';
  const container=$('stages');container.replaceChildren();
  const measured=['load','release','follow'].filter(k=>stages[k] && (stages[k].elbow!==null || stages[k].knee!==null)).length;
  $('measurement-status').textContent=measured ? measured+' of 3 moments measured. Select a frame to jump to it. Angles are 2D estimates.' : 'Form could not be measured for this shot. Try a steady view with the whole player visible.';
  for(const [key,title,sub] of [['load','Load','The gather'],['release','Release','Estimated release'],['follow','Follow-through','After the release']]){
    const d=stages[key],card=document.createElement('article');card.className='stage';
    const visual=document.createElement('div');visual.className='stage-img';
    if(d && d.image){const img=document.createElement('img');img.src=imageSource(d.image);img.alt=title+' with pose overlay';visual.append(img);}else visual.textContent='Not detected';
    const body=document.createElement('div');body.className='stage-body';const label=document.createElement('span');label.textContent=sub.toUpperCase();const heading=document.createElement('b');heading.textContent=title;const details=document.createElement('small');
    details.textContent=d?('Elbow '+(d.elbow===null?'--':d.elbow+' deg')+' - Knee '+(d.knee===null?'--':d.knee+' deg')+'\n'+d.seconds+' sec - '+d.side+' side'):'No measurement available.';details.style.whiteSpace='pre-line';body.append(label,heading,details);
    if(d){const jump=document.createElement('button');jump.type='button';jump.className='stage-jump';jump.textContent='View moment ↗';jump.addEventListener('click',()=>{$('review-video').currentTime=d.seconds;$('review-video').pause();$('review-video').scrollIntoView({behavior:'smooth',block:'center'});});body.append(jump);}
    card.append(visual,body);if(d && d.original_image){const pair=document.createElement('div');pair.className='stage-original';const original=document.createElement('img');original.src=imageSource(d.original_image);original.alt=title+' original video frame';const caption=document.createElement('span');caption.textContent='ORIGINAL';pair.append(original,caption);visual.append(pair);const overlayLabel=document.createElement('span');overlayLabel.className='overlay-label';overlayLabel.textContent='POSE';visual.append(overlayLabel);}container.append(card);
  }
  const notesList=$('film-notes');notesList.replaceChildren();
  const notes=selectedShot ? [...selectedShot.notes] : ['No reliable form measurement is available. Review the video and add missed attempts.'];
  if(selectedShot && selectedShot.outcome==='missed'){
    if(stages.load && stages.load.knee !== null && stages.load.knee >= 160) notes.push('Possible area to review: the knee appeared nearly straight at load (160 degrees or more in this 2D view).');
    if(selectedShot.apparent_angle !== null && selectedShot.apparent_angle !== undefined && selectedShot.apparent_angle < 30) notes.push('Possible area to review: the visible launch path appeared relatively flat (under 30 degrees in the image).');
  }
  for(const note of notes){const li=document.createElement('li');li.textContent=note;notesList.append(li);}
  const warnings=[];
  if(!reviewResult.hoop_selected)warnings.push('No rim was selected; automatic outcomes are uncertain.');
  if(uncertain)warnings.push('Some shot outcomes are uncertain. A dash means no outcome could be classified; review the video and select an outcome.');
  if(!shots.length)warnings.push('No releases were detected. This does not mean no shots were taken.');
  if(reviewResult.ball_frames<3)warnings.push('Few ball detections were found. Try a closer, well-lit video.');
  $('result-note').textContent=warnings.join(' ');
}
$('add-shot').addEventListener('click',()=>{
  if(!reviewResult)return;
  const time=Number($('review-video').currentTime)||0;
  const shot={seconds:Math.round(time*100)/100,outcome:'uncertain',stages:{},notes:['This attempt was added manually; automatic form measurements are unavailable.']};
  shot.reviewed=true;
  reviewResult.shots.push(shot);reviewResult.shots.sort((a,b)=>a.seconds-b.seconds);selectedShot=shot;drawReview();queueReviewSave();
});

$('replay-shot').addEventListener('click',()=>{if(selectedShot){const video=$('review-video');video.currentTime=Math.max(0,selectedShot.seconds-1);video.play().catch(()=>{});}});
$('jump-rim').addEventListener('click',()=>{if(selectedShot && selectedShot.tracking){const video=$('review-video');video.currentTime=Math.max(0,selectedShot.tracking.crossing_seconds-0.8);video.play().catch(()=>{});}});
$('confirm-shot').addEventListener('click',()=>{if(selectedShot && selectedShot.outcome!=='uncertain'){selectedShot.reviewed=true;drawReview();queueReviewSave();}});
$('playback-speed').addEventListener('change', e=>{$('review-video').playbackRate=Number(e.target.value);});

function demoFrame(overlay){
  const lines=overlay?'<path d="M100 67 L100 110 L82 142 M100 110 L120 142 M100 75 L122 64 L140 44 M100 75 L82 90" fill="none" stroke="#bfe3b1" stroke-width="4"/><circle cx="140" cy="44" r="5" fill="#f1a573"/>':'';
  return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="160" viewBox="0 0 240 160"><rect width="240" height="160" fill="#1b3025"/><path d="M0 142H240 M0 154H240" stroke="#59745c"/><circle cx="100" cy="53" r="12" fill="#d7a67e"/><path d="M100 67 L100 110 L82 142 M100 110 L120 142 M100 75 L122 64 L140 44 M100 75 L82 90" fill="none" stroke="#c1cab8" stroke-width="8"/><circle cx="147" cy="40" r="8" fill="#e99565"/><path d="M190 28h32v27h-32 M186 56h36" stroke="#c4d2c0" stroke-width="3" fill="none"/>'+lines+'</svg>');
}
async function makeDemoVideo(){
  if(!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) throw new Error('This browser cannot create the illustrative demo video.');
  const c=document.createElement('canvas');c.width=640;c.height=360;const x=c.getContext('2d');
  const stream=c.captureStream(20), chunks=[], rec=new MediaRecorder(stream);
  const finished=new Promise((resolve,reject)=>{rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};rec.onerror=()=>reject(new Error('Could not prepare the demo video.'));rec.onstop=()=>resolve(new Blob(chunks,{type:rec.mimeType||'video/webm'}));});
  rec.start();let n=0;
  await new Promise(resolve=>{const timer=setInterval(()=>{x.fillStyle='#14251c';x.fillRect(0,0,640,360);x.strokeStyle='#526e56';x.lineWidth=3;x.beginPath();x.moveTo(0,300);x.lineTo(640,300);x.stroke();x.strokeStyle='#d1dfc7';x.strokeRect(482,50,105,76);x.beginPath();x.moveTo(475,130);x.lineTo(555,130);x.stroke();x.fillStyle='#e9a274';x.beginPath();const t=Math.min(1,n/55);x.arc(185+330*t,212-240*t+145*t*t,12,0,Math.PI*2);x.fill();x.fillStyle='#a5c49b';x.font='20px Segoe UI';x.fillText('ILLUSTRATIVE DEMO',25,35);if(++n>=65){clearInterval(timer);resolve();}},50);});
  rec.stop();const blob=await finished;stream.getTracks().forEach(track=>track.stop());return URL.createObjectURL(blob);
}
$('open-demo').addEventListener('click',async()=>{
  clearError();$('open-demo').disabled=true;$('open-demo').textContent='Preparing demo…';
  try{demoVideoUrl=await makeDemoVideo();currentJob='demo';const pose=demoFrame(true),original=demoFrame(false);const stages={};
    for(const [key,seconds,elbow,knee] of [['load',.3,78,118],['release',1.2,145,151],['follow',1.7,168,164]])stages[key]={seconds,elbow,knee,side:'right',image:pose,original_image:original};
    const result={video_duration:3.2,ball_frames:48,processed_frames:60,hoop_selected:true,trajectory:null,shots:[{id:0,seconds:1.2,outcome:'uncertain',reviewed:false,stages,apparent_angle:null,notes:['Illustrative example only: the positions and measurements are simulated.','Review cue: compare the load and release to see how the knee extends.']}]};
    renderResults(result);show('workspace',false);show('prepare',false);show('results',true);$('results').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){error(e.message);}finally{$('open-demo').disabled=false;$('open-demo').textContent='Explore an illustrative demo ↗';}
});

function escapeReport(value){return String(value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
async function embedImage(source){try{if(source.startsWith('data:'))return source;const response=await fetch(source);if(!response.ok)return '';const blob=await response.blob();return await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>resolve('');reader.readAsDataURL(blob);});}catch(_){return '';}}
$('download-report').addEventListener('click',async()=>{
  if(!reviewResult)return;const button=$('download-report');button.disabled=true;button.textContent='Preparing report…';
  try{const shots=reviewResult.shots;const reviewed=shots.filter(s=>s.reviewed && s.outcome!=='uncertain');const made=reviewed.filter(s=>s.outcome==='made').length;
    let stagesHtml='';if(selectedShot){for(const [key,title] of [['load','Load'],['release','Release'],['follow','Follow-through']]){const stage=selectedShot.stages[key];if(!stage)continue;const img=stage.image?await embedImage(imageSource(stage.image)):'';stagesHtml+='<article>'+(img?'<img src="'+img+'" alt="'+title+' pose">':'')+'<h3>'+title+'</h3><p>'+escapeReport(stage.seconds)+' sec · Elbow '+escapeReport(stage.elbow ?? '—')+'° · Knee '+escapeReport(stage.knee ?? '—')+'°</p></article>';}}
    const rows=shots.map((s,i)=>'<tr><td>'+(i+1)+'</td><td>'+escapeReport(s.seconds.toFixed(2))+' s</td><td>'+escapeReport(s.outcome)+'</td><td>'+escapeReport(s.reviewed?'Reviewed':'AI estimate')+'</td></tr>').join('');
    const notes=selectedShot?(selectedShot.notes||[]).map(n=>'<li>'+escapeReport(n)+'</li>').join(''):'';
    const html='<!doctype html><html><head><meta charset="utf-8"><title>CourtVision report</title><style>body{font:15px/1.6 Arial;color:#1e2d24;max-width:900px;margin:40px auto;padding:0 25px}h1,h2{font-family:Georgia}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #ddd;padding:10px;text-align:left}section{display:flex;gap:12px}article{flex:1}img{max-width:100%}small{color:#54675a}@media print{body{margin:0}}</style></head><body><small>COURTVISION · '+(currentJob==='demo'?'ILLUSTRATIVE DEMO':'SESSION REPORT')+'</small><h1>Your film room</h1><p>'+shots.length+' attempts · '+reviewed.length+' reviewed · '+(reviewed.length?Math.round(made/reviewed.length*100)+'% reviewed shooting':'No reviewed shooting percentage')+'</p><h2>Shot review</h2><table><thead><tr><th>Shot</th><th>Time</th><th>Outcome</th><th>Source</th></tr></thead><tbody>'+rows+'</tbody></table><h2>Selected shot · form study</h2><section>'+stagesHtml+'</section><ul>'+notes+'</ul><small>Automatic outcomes and 2D measurements are estimates. Review the video before drawing conclusions.</small></body></html>';
    const url=URL.createObjectURL(new Blob([html],{type:'text/html'}));const a=document.createElement('a');a.href=url;a.download='courtvision-report.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(_){error('Could not prepare the report. Please try again.');}finally{button.disabled=false;button.textContent='Download report';}
});

restoreReview();
