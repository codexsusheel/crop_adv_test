// Plain browser JavaScript. All model and market requests go to our own FastAPI server.
const $ = id => document.getElementById(id);
const fields = ['N','P','K','temperature','humidity','ph','rainfall'];
const labels = {N:'Nitrogen · CSV scale',P:'Phosphorus · CSV scale',K:'Potassium · CSV scale',temperature:'Temperature (°C)',humidity:'Humidity (%)',ph:'Soil pH',rainfall:'Rainfall · CSV scale'};
const sample = [90,42,43,20.9,82,6.5,203];
// Blank date selects the latest imported quotes for the chosen location/crop.
function node(tag, text, className) { const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(className) el.className=className; return el; }
function inputField(container, name, label, value='', options=null) {
  const wrap=node('label',label); const input=document.createElement(options?'select':'input');
  input.name=name; input.required=true;
  if(options) options.forEach(v=>{const op=node('option',typeof v==='object'?v.label:v);op.value=typeof v==='object'?v.value:v;input.append(op);});
  else {input.type='number';input.step='any';input.value=value;}
  wrap.append(input);container.append(wrap);return input;
}
fields.forEach(f=>inputField($('soil-fields'),f,labels[f]));
$('example').onclick=()=>fields.forEach((f,i)=>$('soil-form').elements[f].value=sample[i]);
function soil(){const form=$('soil-form');if(!form.reportValidity())throw Error('Complete the field measurements under Recommend first.');return Object.fromEntries(fields.map(f=>[f,Number(form.elements[f].value)]));}
async function api(path, body) {
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;
}
async function task(target, action) {
  const marketButton = target.id==='market-result' ? $('market-form').querySelector('button') : null;
  if(marketButton){marketButton.disabled=true;marketButton.textContent='Checking stored records…';}
  target.replaceChildren(node('p',marketButton?'Looking up market records…':'Working…'));
  try {await action();} catch(error){target.replaceChildren(node('p',error.message,'error'));}
  finally {if(marketButton){marketButton.disabled=false;marketButton.textContent='Find prices';}}
}
function table(headers, rows) {const wrap=node('div',undefined,'table-wrap');const t=node('table');const head=node('tr');headers.forEach(h=>head.append(node('th',h)));t.append(head);rows.forEach(row=>{const tr=node('tr');row.forEach(v=>tr.append(node('td',v)));t.append(tr);});wrap.append(t);return wrap;}
function pretty(value){return typeof value==='number'?Number(value.toFixed(4)).toLocaleString():value===null?'Not available':String(value);}
// Structured results use textContent so neither user input nor upstream text becomes HTML.
function renderObject(value, parent) {
  if(Array.isArray(value)) {value.forEach((v,i)=>{const d=node('div',undefined,'detail');d.append(node('strong',String(i+1)));renderObject(v,d);parent.append(d);});if(!value.length)parent.append(node('p','None'));return;}
  if(value && typeof value==='object') {Object.entries(value).forEach(([key,v])=>{const d=node('div',undefined,'detail');d.append(node('strong',key.replaceAll('_',' ')));if(v && typeof v==='object')renderObject(v,d);else d.append(node('div',pretty(v)));parent.append(d);});return;}
  parent.append(node('p',pretty(value)));
}
function percent(value) {return value>0 && value<.001?' <0.1%':`${(value*100).toFixed(1)}%`;}
function summaryCards(parent, items) {
  const grid=node('div',undefined,'summary-grid');
  items.forEach(([label,value])=>{const card=node('div',undefined,'summary-stat');card.append(node('span',label),node('strong',value));grid.append(card);});parent.append(grid);
}
function assessment(data, box) {
  box.replaceChildren(node('span',data.status.replaceAll('_',' '),'badge '+(data.status==='OK'?'':'warning')));
  box.append(node('h2',data.recommendation?data.recommendation.charAt(0).toUpperCase()+data.recommendation.slice(1):'No confident recommendation'));
  summaryCards(box,[['Calibrated confidence',percent(data.confidence)],['Stable trials',`${Math.round(data.stability.unchanged_fraction*data.stability.trials)} / ${data.stability.trials}`]]);
  if(data.reasons.length){const list=node('ul');data.reasons.forEach(r=>list.append(node('li',r)));box.append(list);}
  box.append(node('p',data.note,'muted'));
  if(data.forest_candidates){box.append(node('h3','Crop support inside the forest'),node('p',data.probability_note,'muted'));
    data.forest_candidates.forEach(c=>{const row=node('div',undefined,'candidate');row.append(node('strong',c.crop),node('span',percent(c.score)));box.append(row);const bar=node('div',undefined,'bar');const fill=node('span');fill.style.width=`${c.score*100}%`;bar.append(fill);box.append(bar);});
    const details=node('details');details.append(node('summary','View calibrated probabilities'),table(['Crop','Calibrated probability'],data.forest_candidates.map(c=>[c.crop,percent(c.calibrated_probability)])));box.append(details);
  }
  if(data.explanation.length){const details=node('details');details.append(node('summary','Why this crop?'),node('p','Change in this crop’s probability when an input is replaced by its training median. Positive values support the crop; this is not cause and effect.','muted'),table(['Feature','Effect (percentage points)'],data.explanation.map(e=>[labels[e.feature]||e.feature,`${e.probability_difference>0?'+':''}${(e.probability_difference*100).toFixed(1)}`])));box.append(details);}
}
function renderPrediction(data) {assessment(data,$('prediction'));}
$('soil-form').onsubmit=e=>{e.preventDefault();task($('prediction'),async()=>renderPrediction(await api('/predict',soil())));};
document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==button.dataset.tab);document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===button));});
$('crop-load').onclick=()=>task($('crop-ranges'),async()=>{const r=await api('/crops/'+$('crop-select').value);$('crop-ranges').replaceChildren(table(['Feature','Ideal (10–90%)','Acceptable (2.5–97.5%)'],Object.entries(r.ranges).map(([f,v])=>[f,v.ideal.map(pretty).join(' – '),v.acceptable.map(pretty).join(' – ')])),node('p',r.note,'muted'));});
$('land-check').onclick=()=>task($('land-result'),async()=>{const r=await api('/land-check',{crop:$('crop-select').value,inputs:soil()});const box=$('land-result');box.replaceChildren(node('h3',r.crop));summaryCards(box,[['Land fit',percent(r.fit_score)],['Verdict',r.verdict.replaceAll('_',' ')]]);box.append(table(['Measurement','Fit'],Object.entries(r.features).map(([f,s])=>[labels[f],s])),node('p',r.advice,'muted'));const details=node('details');details.append(node('summary','Model assessment'));const content=node('div');assessment(r.assessment,content);details.append(content);box.append(details);});
const tools={
  'what-if':{help:'Uses your field measurements. Change one input and compare the model responses.',fields:[['feature','Feature',fields],['operation','Operation',['set','add','percent']],['value','Change value']]},
  'what-if/sweep':{help:'Uses your field measurements. Check 2–30 evenly spaced values; tipping intervals are approximate.',fields:[['feature','Feature',fields],['start','Start value'],['end','End value'],['steps','Steps']]},
  profit:{help:'Use quintals per hectare for yields, INR per quintal for price, and INR per hectare for cost.',fields:[['area_ha','Area (ha)'],['price_per_quintal','Price (INR/quintal)'],['low_yield_q_ha','Low yield (q/ha)'],['typical_yield_q_ha','Typical yield (q/ha)'],['high_yield_q_ha','High yield (q/ha)'],['cost_per_ha','Total cost (INR/ha)'],['duration_days','Duration (days)']]},
  fertilizer:{help:'Uses N, P, K and pH from your field inputs. Choose a crop to screen nutrient levels and suggest fertilizer sources. Default: compare with that crop’s CSV samples. Select confirmed_available_kg_ha only for laboratory available elemental N/P/K results in kg/ha (not ppm, P2O5 or K2O).',fields:[['measurement_basis','Measurement basis',['csv_scale','confirmed_available_kg_ha']]]},
  rotation:{help:'Broad legume/non-legume alternation only. Confirm seasonal and local suitability separately.',fields:[]}
};
let crops=[], fertilizerProfiles=[];
function showTool(){const name=$('tool-select').value;const spec=tools[name];$('tool-help').textContent=spec.help;$('tool-fields').replaceChildren();if(name==='fertilizer')inputField($('tool-fields'),'crop','Crop','',crops);spec.fields.forEach(([key,label,options])=>inputField($('tool-fields'),key,label,'',options));if(name==='rotation')inputField($('tool-fields'),'previous_crop','Previous crop','',crops);
  if(name==='fertilizer'){
    const region=inputField($('tool-fields'),'state','State for regional reference','',[{value:'',label:'No regional reference'},'Tamil Nadu','Telangana',{value:'Other',label:'Other state'}]);region.required=false;
    const profile=inputField($('tool-fields'),'reference_profile','Published crop reference','',[{value:'',label:'Soil screening only'}]);profile.required=false;
    const condition=node('label','I confirm laboratory N/P/K units and the reference’s stated cultivation conditions.');const checkbox=node('input');checkbox.type='checkbox';checkbox.name='conditions_confirmed';condition.prepend(checkbox);$('tool-fields').append(condition);
    const conditions=node('p','Regional references currently cover specified Tamil Nadu rice/cotton conditions.');conditions.className='muted';$('tool-fields').append(conditions);
    const update=()=>{const crop=$('tool-form').elements.crop.value;const relevant=fertilizerProfiles.filter(p=>p.crop===crop&&p.state===region.value);profile.replaceChildren();[{id:'',label:'Soil screening only'},...relevant].forEach(p=>{const op=node('option',p.label);op.value=p.id;profile.append(op);});checkbox.checked=false;conditions.textContent=relevant.length?'Choose only a reference matching your region and cultivation conditions.':'No verified regional reference for this crop/state. Soil screening remains available.';};
    region.onchange=update;$('tool-form').elements.crop.onchange=update;profile.onchange=()=>{checkbox.checked=false;const p=fertilizerProfiles.find(p=>p.id===profile.value);conditions.textContent=p?p.conditions:'Soil screening only.';};update();
  }
  $('tool-result').replaceChildren();}
$('tool-select').onchange=showTool;
function renderTool(name, r, box) {
  box.replaceChildren();
  if(name==='fertilizer') {
    box.append(node('h3',`Nutrient review for ${r.crop}`),node('p',r.reference_label,'muted'));
    r.nutrients.forEach(n=>{const card=node('section',undefined,'nutrient-card');card.append(node('span',n.status.replaceAll('_',' '),'badge '+(n.priority==='review'?'warning':'')),node('h3',`${n.nutrient}: ${pretty(n.value)}`),node('p',`Reference: ${n.reference_range.map(pretty).join(' – ')}`,'muted'),node('p',n.action));box.append(card);});
    r.warnings.forEach(w=>box.append(node('p',w,'warning callout')));box.append(node('p',r.note,'muted'));
    if(r.source_url){const a=node('a','Soil-test rating source: TNAU');a.href=r.source_url;a.target='_blank';a.rel='noopener';box.append(a);}
    if(r.regional_reference){const ref=r.regional_reference;const card=node('section',undefined,'nutrient-card');card.append(node('h3','Regional crop reference'));if(ref.status==='reference_only'){card.append(node('p',ref.label),node('p',ref.conditions,'muted'),table(['Fertilizer nutrient','Published reference (kg/ha)'],Object.entries(ref.nutrients_kg_ha).map(([k,v])=>[k,v])),node('p',ref.schedule),node('p',ref.note,'muted'));const a=node('a','Read TNAU source ↗');a.href=ref.source_url;a.target='_blank';a.rel='noopener';card.append(a);}else card.append(node('p',ref.message));box.append(card);}return;
  }
  if(name==='profit') {box.append(node('h3','Profit scenarios'),table(['Yield scenario','Revenue (₹)','Net profit (₹)','Profit / 30 days (₹)'],Object.entries(r.scenarios).map(([label,v])=>[label,pretty(v.revenue_inr),pretty(v.profit_inr),pretty(v.profit_per_30_days_inr)])));summaryCards(box,[['Break-even yield (q/ha)',pretty(r.break_even_yield_q_ha)],['Break-even price (₹/q)',pretty(r.break_even_price_inr_q)]]);box.append(node('p',r.note,'muted'));return;}
  if(name==='rotation') {box.append(node('h3','Next-crop options'),node('p',r.candidates.length?r.candidates.join(' · '):'No rotation options for this crop.'),node('p',r.note,'muted'));return;}
  if(name==='what-if/sweep') {box.append(node('h3','How the recommendation changes'),table(['Input value','Recommendation','Confidence','Status'],r.points.map(p=>[pretty(p.value),p.recommendation||'Withheld',percent(p.confidence),p.status.replaceAll('_',' ')])),node('p',r.tipping_intervals.length?'Changes occur within: '+r.tipping_intervals.map(x=>x.map(pretty).join(' to ')).join('; '):'No recommendation change across the sampled values.'));return;}
  if(name==='what-if') {const grid=node('div',undefined,'report-comparison');[['Before',r.before],['After',r.after]].forEach(([label,v])=>{const card=node('section');card.append(node('h3',label));const content=node('div');assessment(v,content);card.append(content);grid.append(card);});box.append(grid);const changes=Object.entries(r.probability_changes).filter(([,v])=>Math.abs(v)>.0001).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1]));box.append(table(['Crop','Change (percentage points)'],changes.map(([c,v])=>[c,`${v>0?'+':''}${(v*100).toFixed(2)}`])),node('p',r.note,'muted'));}
}
$('tool-form').onsubmit=e=>{e.preventDefault();task($('tool-result'),async()=>{const name=$('tool-select').value;const body={};new FormData(e.target).forEach((v,k)=>body[k]=['feature','operation','previous_crop','crop','measurement_basis','state','reference_profile'].includes(k)?v:k==='conditions_confirmed'?true:Number(v));if(name==='fertilizer'){body.reference_profile=body.reference_profile||null;body.conditions_confirmed=!!e.target.elements.conditions_confirmed.checked;}if(name.startsWith('what-if')||name==='fertilizer')body.inputs=soil();const r=await api('/'+name,body);renderTool(name,r,$('tool-result'));});};
(async()=>{try{crops=(await api('/crops')).crops;crops.forEach(c=>{const op=node('option',c);op.value=c;$('crop-select').append(op);});fertilizerProfiles=(await api('/fertilizer/references')).profiles;showTool();const m=await api('/metrics');$('metrics-summary').append(table(['Test accuracy','Macro-F1','Train / test'],[[m.training.test_accuracy,m.training.test_macro_f1,`${m.training.n_train} / ${m.training.n_test}`]]));}catch(e){$('prediction').append(node('p','Application unavailable: '+e.message,'error'));}})();
