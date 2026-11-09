const $ = id => document.getElementById(id);
let currentJob = null, previewImage = null, hoop = null, origin = null, draft = null, pollTimer = null, hoopTimer = null, hoopTouched = false;
const canvas = $('preview'), ctx = canvas.getContext('2d');
const show = (id, yes) => $(id).classList.toggle('hidden', !yes);
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
    show('workspace', false); show('results', false); show('prepare', true); findHoop(currentJob);
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
function reset(){setSavedSession(null);clearTimeout(pollTimer);clearTimeout(hoopTimer);currentJob=null;hoop=null;previewImage=null;show('prepare',false);show('results',false);show('loading',false);show('workspace',true);clearError();window.scrollTo({top:0,behavior:'smooth'});}
$('change-video').addEventListener('click',reset);$('start-over').addEventListener('click',reset);
$('analyze').addEventListener('click', async()=>{
  if(!currentJob)return; clearError(); $('analyze').disabled=true;
  try {const r=await fetch('/api/analyze/'+currentJob,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hoop})});const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not start analysis.');show('prepare',false);show('loading',true);$('loading').scrollIntoView({behavior:'smooth',block:'center'});poll();}
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
  const job = currentJob, revision = ++saveRevision;
  const shots = reviewResult.shots.map(shot => ({id: Number.isInteger(shot.id) ? shot.id : null, seconds: shot.seconds, outcome: shot.outcome}));
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
    if (currentJob || item.state !== 'done' || !item.result) return;
    currentJob = job; renderResults(item.result); show('workspace', false); show('results', true);
  } catch (_) { /* The last review remains available when the server returns. */ }
}
function renderResults(r){
  reviewResult = r;
  selectedShot = r.shots.length ? r.shots[0] : null;
  $('review-video').src = '/api/jobs/' + currentJob + '/video';
  $('video-duration').textContent=r.video_duration+' sec'; $('ball-frames').textContent=r.ball_frames+' / '+r.processed_frames+' frames';
  const trace=$('trajectory'); trace.replaceChildren();
  if(r.trajectory){const img=document.createElement('img');img.src='/media/'+currentJob+'/'+r.trajectory;img.alt='Detected basketball trajectory';trace.append(img);}else trace.textContent='No ball path available';
  drawReview();
}
function drawReview(){
  const shots=reviewResult.shots;
  $('attempts').textContent=shots.length;
  const made=shots.filter(s=>s.outcome==='made').length;
  const missed=shots.filter(s=>s.outcome==='missed').length;
  const uncertain=shots.filter(s=>s.outcome==='uncertain').length;
  $('made').textContent=(shots.length && !made && !missed) ? '--' : made;
  $('missed').textContent=(shots.length && !made && !missed) ? '--' : missed;
  $('uncertain').textContent=uncertain;
  $('review-summary').textContent=uncertain+' uncertain outcome'+(uncertain===1?'':'s')+'. Counts include your edits.';
  const list=$('shot-list'); list.replaceChildren();
  if(!shots.length) list.textContent='No shots detected. Review the video and add attempts manually.';
  shots.forEach((shot,index)=>{
    const item=document.createElement('div'); item.className='shot-item'+(shot===selectedShot?' selected':'');
    const choose=document.createElement('button'); choose.type='button'; choose.textContent='Shot '+(index+1)+'  /  '+shot.seconds.toFixed(2)+'s'; choose.setAttribute('aria-pressed', String(shot===selectedShot));
    choose.addEventListener('click',()=>{selectedShot=shot;$('review-video').currentTime=shot.seconds;drawReview();});
    const select=document.createElement('select'); select.setAttribute('aria-label','Outcome for shot '+(index+1));
    for(const [value,label] of [['uncertain','Uncertain'],['made','Made'],['missed','Missed']]){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}
    select.value=shot.outcome;select.addEventListener('change',()=>{shot.outcome=select.value;drawReview();queueReviewSave();});
    const remove=document.createElement('button'); remove.type='button';remove.textContent='Remove';remove.setAttribute('aria-label','Remove shot '+(index+1));
    remove.addEventListener('click',()=>{shots.splice(shots.indexOf(shot),1);if(selectedShot===shot)selectedShot=shots[0]||null;drawReview();queueReviewSave();});
    item.append(choose,select,remove);list.append(item);
  });
  const stages=selectedShot ? selectedShot.stages : {};
  const container=$('stages');container.replaceChildren();
  for(const [key,title,sub] of [['load','Load','The gather'],['release','Release','Estimated release'],['follow','Follow-through','After the release']]){
    const d=stages[key],card=document.createElement('article');card.className='stage';
    const visual=document.createElement('div');visual.className='stage-img';
    if(d && d.image){const img=document.createElement('img');img.src='/media/'+currentJob+'/'+d.image;img.alt=title+' position';visual.append(img);}else visual.textContent='Not detected';
    const body=document.createElement('div');body.className='stage-body';const label=document.createElement('span');label.textContent=sub.toUpperCase();const heading=document.createElement('b');heading.textContent=title;const details=document.createElement('small');
    details.textContent=d?('Elbow '+(d.elbow===null?'--':d.elbow+' deg')+' - Knee '+(d.knee===null?'--':d.knee+' deg')+'\n'+d.seconds+' sec - '+d.side+' side'):'No measurement available.';details.style.whiteSpace='pre-line';body.append(label,heading,details);card.append(visual,body);container.append(card);
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
  reviewResult.shots.push(shot);reviewResult.shots.sort((a,b)=>a.seconds-b.seconds);selectedShot=shot;drawReview();queueReviewSave();
});

restoreReview();
