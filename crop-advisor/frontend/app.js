// Plain browser JavaScript. All model and market requests go to our own FastAPI server.
const $ = id => document.getElementById(id);
const fields = ['N','P','K','temperature','humidity','ph','rainfall'];
const labels = {N:'Nitrogen · CSV scale',P:'Phosphorus · CSV scale',K:'Potassium · CSV scale',temperature:'Temperature (°C)',humidity:'Humidity (%)',ph:'Soil pH',rainfall:'Rainfall · CSV scale'};
const sample = [90,42,43,20.9,82,6.5,203];
// Use the user's local calendar date, avoiding UTC shifting it to the prior day.
const today = new Date();
$('market-form').elements.date.value = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
function node(tag, text, className) { const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(className) el.className=className; return el; }
function inputField(container, name, label, value='', options=null) {
  const wrap=node('label',label); const input=document.createElement(options?'select':'input');
  input.name=name; input.required=true;
  if(options) options.forEach(v=>{const op=node('option',v);op.value=v;input.append(op);});
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
  if(marketButton){marketButton.disabled=true;marketButton.textContent='Checking government records…';}
  target.replaceChildren(node('p',marketButton?'Contacting data.gov.in… This may take up to about a minute.':'Working…'));
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
$('market-form').onsubmit=e=>{e.preventDefault();task($('market-result'),async()=>{const params=new URLSearchParams();new FormData(e.target).forEach((v,k)=>{if(v.trim())params.set(k,v.trim());});const r=await api('/market/'+$('market-crop').value+'?'+params);const box=$('market-result');box.replaceChildren(node('p',r.status.toUpperCase()+' · '+(r.message||'')),node('p',r.unit,'muted'));if(r.records.length)box.append(table(['Market','Variety','Reported date','Min','Modal','Max'],r.records.map(x=>[x.market,x.variety,x.arrival_date,x.min_price,x.modal_price,x.max_price])));});};
const tools={
  'what-if':{help:'Uses your field measurements. Change one input and compare the model responses.',fields:[['feature','Feature',fields],['operation','Operation',['set','add','percent']],['value','Change value']]},
  'what-if/sweep':{help:'Uses your field measurements. Check 2–30 evenly spaced values; tipping intervals are approximate.',fields:[['feature','Feature',fields],['start','Start value'],['end','End value'],['steps','Steps']]},
  profit:{help:'Use quintals per hectare for yields, INR per quintal for price, and INR per hectare for cost.',fields:[['area_ha','Area (ha)'],['price_per_quintal','Price (INR/quintal)'],['low_yield_q_ha','Low yield (q/ha)'],['typical_yield_q_ha','Typical yield (q/ha)'],['high_yield_q_ha','High yield (q/ha)'],['cost_per_ha','Total cost (INR/ha)'],['duration_days','Duration (days)']]},
  fertilizer:{help:'Uses N, P, K and pH from your field inputs. Choose a crop to screen nutrient levels and suggest fertilizer sources. Default: compare with that crop’s CSV samples. Select confirmed_available_kg_ha only for laboratory available elemental N/P/K results in kg/ha (not ppm, P2O5 or K2O).',fields:[['measurement_basis','Measurement basis',['csv_scale','confirmed_available_kg_ha']]]},
  rotation:{help:'Broad legume/non-legume alternation only. Confirm seasonal and local suitability separately.',fields:[]}
};
let crops=[];
function showTool(){const name=$('tool-select').value;const spec=tools[name];$('tool-help').textContent=spec.help;$('tool-fields').replaceChildren();if(name==='fertilizer')inputField($('tool-fields'),'crop','Crop','',crops);spec.fields.forEach(([key,label,options])=>inputField($('tool-fields'),key,label,'',options));if(name==='rotation')inputField($('tool-fields'),'previous_crop','Previous crop','',crops);$('tool-result').replaceChildren();}
$('tool-select').onchange=showTool;
function renderTool(name, r, box) {
  box.replaceChildren();
  if(name==='fertilizer') {
    box.append(node('h3',`Nutrient review for ${r.crop}`),node('p',r.reference_label,'muted'));
    r.nutrients.forEach(n=>{const card=node('section',undefined,'nutrient-card');card.append(node('span',n.status.replaceAll('_',' '),'badge '+(n.priority==='review'?'warning':'')),node('h3',`${n.nutrient}: ${pretty(n.value)}`),node('p',`Reference: ${n.reference_range.map(pretty).join(' – ')}`,'muted'),node('p',n.action));box.append(card);});
    r.warnings.forEach(w=>box.append(node('p',w,'warning callout')));box.append(node('p',r.note,'muted'));
    if(r.source_url){const a=node('a','Soil-test rating source: TNAU');a.href=r.source_url;a.target='_blank';a.rel='noopener';box.append(a);}return;
  }
  if(name==='profit') {box.append(node('h3','Profit scenarios'),table(['Yield scenario','Revenue (₹)','Net profit (₹)','Profit / 30 days (₹)'],Object.entries(r.scenarios).map(([label,v])=>[label,pretty(v.revenue_inr),pretty(v.profit_inr),pretty(v.profit_per_30_days_inr)])));summaryCards(box,[['Break-even yield (q/ha)',pretty(r.break_even_yield_q_ha)],['Break-even price (₹/q)',pretty(r.break_even_price_inr_q)]]);box.append(node('p',r.note,'muted'));return;}
  if(name==='rotation') {box.append(node('h3','Next-crop options'),node('p',r.candidates.length?r.candidates.join(' · '):'No rotation options for this crop.'),node('p',r.note,'muted'));return;}
  if(name==='what-if/sweep') {box.append(node('h3','How the recommendation changes'),table(['Input value','Recommendation','Confidence','Status'],r.points.map(p=>[pretty(p.value),p.recommendation||'Withheld',percent(p.confidence),p.status.replaceAll('_',' ')])),node('p',r.tipping_intervals.length?'Changes occur within: '+r.tipping_intervals.map(x=>x.map(pretty).join(' to ')).join('; '):'No recommendation change across the sampled values.'));return;}
  if(name==='what-if') {const grid=node('div',undefined,'report-comparison');[['Before',r.before],['After',r.after]].forEach(([label,v])=>{const card=node('section');card.append(node('h3',label));const content=node('div');assessment(v,content);card.append(content);grid.append(card);});box.append(grid);const changes=Object.entries(r.probability_changes).filter(([,v])=>Math.abs(v)>.0001).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1]));box.append(table(['Crop','Change (percentage points)'],changes.map(([c,v])=>[c,`${v>0?'+':''}${(v*100).toFixed(2)}`])),node('p',r.note,'muted'));}
}
$('tool-form').onsubmit=e=>{e.preventDefault();task($('tool-result'),async()=>{const name=$('tool-select').value;const body={};new FormData(e.target).forEach((v,k)=>body[k]=['feature','operation','previous_crop','crop','measurement_basis'].includes(k)?v:Number(v));if(name.startsWith('what-if')||name==='fertilizer')body.inputs=soil();const r=await api('/'+name,body);renderTool(name,r,$('tool-result'));});};
(async()=>{try{crops=(await api('/crops')).crops;['crop-select','market-crop'].forEach(id=>crops.forEach(c=>{const op=node('option',c);op.value=c;$(id).append(op);}));showTool();const m=await api('/metrics');$('metrics-summary').append(table(['Test accuracy','Macro-F1','Train / test'],[[m.training.test_accuracy,m.training.test_macro_f1,`${m.training.n_train} / ${m.training.n_test}`]]));}catch(e){$('prediction').append(node('p','Application unavailable: '+e.message,'error'));}})();
