// Market browsing is independent of model labels. All options come from MongoDB.
const marketForm=$('market-form');
const marketFields=['state','district','commodity','date','market','variety'];
const optionKeys=['states','districts','commodities','dates','markets','varieties'];
let optionRevision=0, searchRevision=0;
const currency=new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2});
const money=value=>currency.format(value);
const indiaTime=value=>new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST';
function marketParams(){const params=new URLSearchParams();new FormData(marketForm).forEach((v,k)=>{if(v.trim())params.set(k,v.trim());});return params;}
function setOptions(name, values, previous=''){
  const select=marketForm.elements[name];
  const prompt={state:'Choose a state',district:'Choose a district',commodity:'Choose a commodity',date:'Latest imported date',market:'All markets',variety:'All varieties'}[name];
  const blank=node('option',prompt);blank.value='';select.replaceChildren(blank);
  values.forEach(value=>{const op=node('option',value||'Unspecified');op.value=value;select.append(op);});
  select.value=values.includes(previous)?previous:'';select.disabled=values.length===0;
}
marketFields.forEach(name=>setOptions(name,[]));
function canSearch(){return ['state','district','commodity'].every(name=>!!marketForm.elements[name].value);}

async function loadMarketOptions(changed=-1){
  const revision=++optionRevision;++searchRevision;
  const values=Object.fromEntries(marketFields.map(name=>[name,marketForm.elements[name].value]));
  if(changed>=0) marketFields.slice(changed+1).forEach(name=>{values[name]='';setOptions(name,[]);});
  marketForm.querySelector('button').disabled=true;
  $('market-result').replaceChildren();$('market-options-status').textContent='Loading available selections…';
  const params=new URLSearchParams();Object.entries(values).forEach(([k,v])=>{if(v)params.set(k,v);});
  // Variety is the final selector, not an input to the options endpoint.
  params.delete('variety');
  try{
    const data=await api('/market/options?'+params);
    if(revision!==optionRevision)return; // Ignore responses for superseded selections.
    marketFields.forEach((name,index)=>setOptions(name,data[optionKeys[index]],values[name]));
    $('market-options-status').textContent=canSearch()?`${data.dates.length} imported reporting date(s) available. Blank date uses the latest.`:'Choose a state, then district and commodity.';
    marketForm.querySelector('button').disabled=!canSearch();
  }catch(error){if(revision===optionRevision)$('market-options-status').textContent=error.message;}
}
marketFields.forEach((name,index)=>marketForm.elements[name].onchange=()=>{
  if(name==='variety'){++searchRevision;$('market-result').replaceChildren();return;}
  loadMarketOptions(index);
});

function renderMarketReport(result){
  const box=$('market-result');box.replaceChildren(node('h3',`${result.commodity} · ${result.district}`));
  box.append(node('p',result.message,'muted'));
  if(!result.records.length)return;
  const summary=result.summary;
  summaryCards(box,[['Reporting date',result.reporting_date],['Markets shown',String(summary.market_count)],
                    ['Lowest minimum / quintal',money(summary.lowest_min)],['Median modal / quintal',money(summary.median_modal)],
                    ['Highest maximum / quintal',money(summary.highest_max)]]);
  box.append(node('p','Modal means the reported prevailing price; the median above summarizes displayed quotes across potentially different varieties/grades. It is not a forecast or a guaranteed sale price.','muted'));
  if(result.truncated)box.append(node('p',`Showing ${result.returned} of ${result.total_matching} matching quotes. Narrow the market or variety filter.`,'warning callout'));
  box.append(table(['Market','Variety','Grade','Reported','Minimum (₹/q)','Modal (₹/q)','Maximum (₹/q)'],result.records.map(r=>[r.market,r.variety||'—',r.grade||'—',r.arrival_date,money(r.min_price),money(r.modal_price),money(r.max_price)])));
  const chart=node('details');chart.append(node('summary','Compare reported modal prices'));
  const compared=result.records.slice(0,20);const maximum=Math.max(...compared.map(r=>r.modal_price));
  compared.forEach(r=>{const row=node('div',undefined,'price-comparison');row.append(node('span',`${r.market} · ${r.variety||'unspecified'} · ${r.grade||'unspecified'}`),node('strong',money(r.modal_price)));const bar=node('div',undefined,'bar');const fill=node('span');fill.style.width=`${r.modal_price/maximum*100}%`;bar.append(fill);row.append(bar);chart.append(row);});
  chart.append(node('p','Comparison shows up to 20 displayed quotes; filter to the same variety and grade before comparing markets.','muted'));box.append(chart);
  (result.sources||[]).forEach(source=>{const link=node('a','Government source ↗');link.href=source.source_url;link.target='_blank';link.rel='noopener';box.append(link);});
}
marketForm.onsubmit=async event=>{
  event.preventDefault();const revision=++searchRevision;const button=marketForm.querySelector('button');button.disabled=true;button.textContent='Checking stored records…';
  $('market-result').replaceChildren(node('p','Reading MongoDB…'));
  try{const result=await api('/market/prices?'+marketParams());if(revision===searchRevision)renderMarketReport(result);}
  catch(error){if(revision===searchRevision)$('market-result').replaceChildren(node('p',error.message,'error'));}
  finally{button.textContent='Find prices';button.disabled=!canSearch();}
};

async function refreshMarketCoverage(){
  const button=$('market-refresh');button.disabled=true;
  try{
    const [status,history]=await Promise.all([api('/market/status'),api('/market/imports')]);
    const box=$('market-status');box.replaceChildren();
    const label=status.freshness==='today'?'Dated today (stored export)':status.freshness==='older'?`${status.report_age_days} day(s) old`:status.freshness==='empty'?'No records imported':'Check future-dated records';
    summaryCards(box,[['Stored records',Number(status.records).toLocaleString('en-IN')],['Latest reporting date',status.latest_reporting_date||'None'],['Freshness',label],['Commodities / states',`${status.commodities} / ${status.states}`]]);
    if(status.last_record_imported_at)box.append(node('p',`Last record import: ${indiaTime(status.last_record_imported_at)}. Data does not refresh automatically.`,'muted'));
    const imports=$('market-imports');imports.replaceChildren(node('h3','Recent import runs'));
    if(history.imports.length)imports.append(table(['Finished / started','Source','Status','Accepted / rejected rows','Coverage'],history.imports.map(r=>[indiaTime(r.finished_at||r.started_at),r.filename||r.method,r.status.replaceAll('_',' '),`${r.accepted} / ${r.invalid}`,`${(r.coverage?.states||[]).length} states · ${r.coverage?.commodity_count||0} commodities · ${r.coverage?.date_from||'—'} to ${r.coverage?.date_to||'—'}`])));
    else imports.append(node('p','No tracked import runs yet. Previous records remain available; future imports will appear here.'));
    await loadMarketOptions();
  }catch(error){$('market-status').replaceChildren(node('p',error.message,'error'));}
  finally{button.disabled=false;}
}
$('market-refresh').onclick=refreshMarketCoverage;
refreshMarketCoverage();
