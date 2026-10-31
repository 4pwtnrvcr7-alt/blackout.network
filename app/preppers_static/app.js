// ---- 🎒 Preppers tab (served by preppers.py). Static reference + client-side planner; nothing is sent anywhere. ----
(()=>{"use strict";
const E=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const U=u=>/^https?:\/\//i.test(u||"")?E(u):"#";const $=(s,r)=>(r||document).querySelector(s),$$=(s,r)=>[...(r||document).querySelectorAll(s)];
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="preppers"]');if(!tb){tb=document.createElement("button");tb.dataset.tab="preppers";tb.textContent="🎒 Preppers";tb.title="Prepper supplier directory, supply planner and scenario kits"}
const place=()=>{const m=nav.querySelector('button[data-tab="med"]');if(m)m.after(tb);else nav.appendChild(tb);const a=document.getElementById("tab_howscore");if(a)tb.after(a)};place();setTimeout(place,600);
try{if(typeof TABHASH=="object"){TABHASH.preppers="preppers";HASHTAB.preppers="preppers"}}catch(_){}
let M=document.getElementById("tab-preppers");
if(!M){M=document.createElement("main");M.id="tab-preppers";M.dataset.addon="preppers";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn"><h2><span>🎒</span> Preppers <span class="meta">— rated suppliers, free official guidance, a supply planner and kits for every scenario</span></h2><div id="pp_app"><div class="meta">Loading…</div></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
if(location.hash=="#preppers")setTimeout(()=>tb.click(),400);
const app=$("#pp_app",M);let D=null,loaded=false;
const F={q:"",cat:"",tier:"",reg:"",min:0,sort:"rating"};const LS="bn_preppers_v1";
const save=o=>{try{const s=JSON.parse(localStorage.getItem(LS)||"{}");localStorage.setItem(LS,JSON.stringify(Object.assign(s,o)))}catch(_){}};
const load=()=>{try{return JSON.parse(localStorage.getItem(LS)||"{}")}catch(_){return{}}};
const BC={blue:"#58a6ff",green:"#3fb950",amber:"#faad14",red:"#f85149"};
const catOf=id=>(D.cats.find(c=>c.id==id)||{label:id,icon:"•"});
const REG=[["Global","🌐 Global"],["US","🇺🇸 US"],["CA","🇨🇦 Canada"],["UK","🇬🇧 UK"],["EU","🇪🇺 EU"],["AU","🇦🇺 Australia"],["NZ","🇳🇿 NZ"]];
const regs=e=>{const r=e.region,s=new Set();if(/global|worldwide|intl|swiss|swedish|finnish|\bany/i.test(r))s.add("Global");
 [["US",/\bUS\b/],["CA",/\bCA\b|canada/i],["UK",/\bUK\b/],["EU",/\bEU\b|\bIE\b/],["AU",/\bAU\b/],["NZ",/\bNZ\b/]].forEach(([k,x])=>x.test(r)&&s.add(k));return s};
// ---------- static content ----------
const OFFICIAL={hurricane:"https://www.ready.gov/hurricanes",winter:"https://www.ready.gov/winter-weather",quake:"https://www.ready.gov/earthquakes",fire:"https://www.ready.gov/wildfires",
 pandemic:"https://www.ready.gov/pandemic",grid:"https://www.ready.gov/power-outages",evac:"https://www.ready.gov/evacuation",sip:"https://www.ready.gov/shelter"};
const SCEN=[
 ["hurricane","🌀 Hurricane / tropical storm",["Water: 1 gal per person per day for at least 3–7 days|water","Fill bathtub / bladder before landfall for flushing|water","Non-perishable food that needs no cooking|food","Battery or hand-crank NOAA weather radio|comms","Power bank or power station, charged before landfall|power","Plywood or storm shutters; know your evacuation zone|security","Waterproof bag with IDs, insurance, prescriptions|docs","Generator outside only, 20 ft from windows + CO alarm|power","Flood insurance has a 30-day wait — buy early|docs"],OFFICIAL.hurricane],
 ["winter","❄ Winter storm / extreme cold",["Indoor-safe heater + CO alarm, extra fuel|heat","Sleeping bags or wool blankets rated for the cold|camping","Extra 25% calories; hot drinks; stove you can use safely|food","Insulate pipes; know how to shut off water|tools","Car kit: blanket, shovel, sand, jumper cables|camping","Headlamps and spare batteries (cold drains batteries)|tools","Medications and medical-device power for days without utilities|special"],OFFICIAL.winter],
 ["quake","🌋 Earthquake",["Shoes, gloves and a flashlight by every bed|tools","Gas shut-off wrench next to the meter|tools","Strap water heater and tall furniture|security","Water for 3–14 days; roads may close|water","Whistle and dust mask in every kit|bags","Out-of-area contact everyone texts (texts get through more often than calls)|comms","Trauma kit: tourniquet, pressure bandages|medical"],OFFICIAL.quake],
 ["fire","🔥 Wildfire",["Go-bag by the door; leave early|bags","N95 masks (smoke) for each person|medical","Air purifier / HEPA filter for one clean room|special","Copies of documents and photos in the cloud|docs","Two exit routes on paper maps|nav","Hoses, defensible-space tools|tools","Pet carriers and pet food|special"],OFFICIAL.fire],
 ["pandemic","🦠 Pandemic / quarantine",["2–4 weeks of food and household supplies|food","Rolling 30-day supply of prescriptions if your plan allows|special","Thermometer, fever reducers, oral rehydration salts|medical","Masks, gloves, disinfectant (follow label directions)|sanitation","Cleaning and hygiene supplies; trash bags|sanitation","Plan for school/work closures and remote care|training"],OFFICIAL.pandemic],
 ["grid","⚡ Grid-down / long power outage",["Power station or generator sized to your daily Wh|power","Solar panels for outages longer than 3 days|power","Cooler and ice plan; fridge food is safe ~4 h closed|food","Lanterns and headlamps, not candles|tools","Cash in small bills (card readers go down)|docs","Water filter if municipal pumps fail|water","AM/FM/NOAA radio for news; scanner for local updates|comms","Bucket toilet + bags if water pressure fails|sanitation"],OFFICIAL.grid],
 ["evac","🚗 Evacuation / bug-out",["One go-bag per person (24–72 h)|bags","Paper maps with 2–3 routes; full tank from half|nav","Phone chargers + power bank|power","Documents, cash, spare keys, glasses|docs","3 days of food and water per person|food","First-aid kit + medications|medical","Pet carrier, leash, records|special","Meeting place and out-of-area contact|training"],OFFICIAL.evac],
 ["sip","🏠 Shelter in place",["Pick an interior room; plastic sheeting + duct tape|security","2 weeks of water and food|water","Battery radio for official instructions|comms","Lighting and spare batteries|tools","Sanitation: bucket toilet, bags, bleach|sanitation","Medications and first aid|medical","Entertainment for kids; comfort items|special"],OFFICIAL.sip]];
const BUDGET=[["$100","Starter (per household)",["2 gal-per-person water containers + bleach|water","3 days of canned or no-cook food|food","Basic first-aid kit|medical","Headlamp per person + batteries|tools","Hand-crank or battery NOAA radio|comms","Copies of IDs in a zip bag|docs"]],
 ["$500","Two-week household",["Water filter + 14 days of stored water|water","14 days of food incl. some freeze-dried|food","Trauma add-on: tourniquet, pressure bandage|medical","Power bank per person + small solar panel|power","FRS/GMRS radios|comms","Bucket toilet + bags, hygiene supplies|sanitation","Indoor-safe heater or camp stove + CO alarm|heat","Go-bag per adult|bags"]],
 ["$2,000","Month-plus resilience",["Power station (1–2 kWh) + 200 W solar|power","30–90 days of food incl. bulk staples|food","Gravity filter + rain/storage containers|water","Wilderness first aid course + full med kit|medical","GMRS license + radios, or satellite messenger|comms","Sleep system per person for no-heat nights|camping","Seeds and basic garden tools|seeds","Fire/water-resistant document safe; cash reserve|docs","Door reinforcement + Grade 1 deadbolts|security"]]];
const TIPS=["Rotate food first-in, first-out: write the purchase date on every can and store new items at the back.","Stored tap water: replace every 6 months (Ready.gov). Commercially bottled water: follow the use-by date.",
 "Gasoline goes stale in about 3–6 months without stabilizer; stabilized fuel lasts longer. Rotate it into your car.","Check flashlight and smoke/CO alarm batteries twice a year, when clocks change.",
 "Charge power stations every 3 months; lithium packs keep best at 50–80%.","Review your kit each season: kids' clothes sizes, medications, documents, phone numbers.",
 "Many medicines lose strength after expiry, and some need cool storage — ask your pharmacist (FDA guidance).","Practice: run a weekend 'lights-off' drill to find the gaps before a real outage."];
const RELATED=[["weather","🌦 Weather"],["med","⛑ Medical"],["bush","🏕 Bushcraft"],["radio","📻 Radio"],["res","📍 Local Resources"],["maps","🗺 Maps"]];
// ---------- render shell ----------
function shell(){const s=load();Object.assign(F,s.F||{});
 app.innerHTML=`<div class=pp-disc>ℹ Informational only, not an endorsement. No affiliate links — blackout.network earns nothing from these. Prices and stock change; check each site. <b>Check local laws</b>, especially for firearms, ammunition, fuel storage and radio transmitting.</div>
 <div class=pp-jump>${[["pp_start","⭐ Start here"],["pp_dir","📇 Directory"],["pp_plan","🧮 Supply planner"],["pp_scen","🗂 Kits by scenario"],["pp_budget","💵 Budget kits"],["pp_range","🏹 Range finder"],["pp_land","🔎 Know the landscape"],["pp_tips","🔁 Rotation tips"],["pp_rubric","📐 How we rate"]].map(([i,l])=>`<a href="#" data-j="${i}">${l}</a>`).join("")}</div>
 <div class=pp-top id=pp_start>
  <div class="pp-card pp-72"><h3>⭐ Start here — 72-hour basics <span class=meta>(Ready.gov kit list)</span></h3><ol>
   <li><b>Water</b> — 1 gallon per person per day, 3 days <a href="#" data-cat=water>suppliers →</a></li><li><b>Food</b> — 3 days of no-cook food + manual can opener <a href="#" data-cat=food>→</a></li>
   <li><b>Light & power</b> — flashlight/headlamp, batteries, phone power bank <a href="#" data-cat=power>→</a></li><li><b>Radio</b> — battery or hand-crank NOAA weather radio <a href="#" data-cat=comms>→</a></li>
   <li><b>First aid</b> — kit + 7 days of prescriptions, glasses <a href="#" data-cat=medical>→</a></li><li><b>Sanitation</b> — wipes, garbage bags, plastic ties <a href="#" data-cat=sanitation>→</a></li>
   <li><b>Tools</b> — whistle, dust mask, wrench to turn off utilities <a href="#" data-cat=tools>→</a></li><li><b>Documents & cash</b> — copies in a waterproof bag <a href="#" data-cat=docs>→</a></li>
   <li><b>Plan</b> — meeting place + out-of-area contact <a href="https://www.ready.gov/plan" target=_blank rel=noopener>Ready.gov plan ↗</a></li></ol>
   <div class=meta>Official kit lists: <a href="https://www.ready.gov/kit" target=_blank rel=noopener>US</a> · <a href="https://prepare.campaign.gov.uk" target=_blank rel=noopener>UK</a> · <a href="https://www.getprepared.gc.ca" target=_blank rel=noopener>Canada</a> · <a href="https://www.redcross.org.au/prepare" target=_blank rel=noopener>Australia</a> · <a href="https://getready.govt.nz" target=_blank rel=noopener>NZ</a> · <a href="https://72tuntia.fi/en" target=_blank rel=noopener>Finland</a> · <a href="https://www.bbk.bund.de/DE/Home/home_node.html" target=_blank rel=noopener>Germany</a></div></div>
  <div class="pp-card"><h3>📊 At a glance</h3><div id=pp_stats></div><h3 style="margin-top:12px">🔗 Related blackout.network tabs</h3><div class=pp-rel>${RELATED.map(([t,l])=>`<button type=button data-go="${t}">${l}</button>`).join("")}</div></div></div>
 <div class=pp-sec id=pp_dir><h3>📇 Directory <span class=meta id=pp_count></span></h3>
  <div class=pp-filt><input id=pp_q type=search placeholder="Search name, tag or note (e.g. GMRS, freeze-dried, Canada)" value="${E(F.q)}">
   <select id=pp_tier aria-label="Price tier"><option value="">Any price</option>${["Free","$","$$","$$$"].map(t=>`<option ${F.tier==t?"selected":""}>${t}</option>`).join("")}</select>
   <select id=pp_reg aria-label="Region"><option value="">Any region</option>${REG.map(([k,l])=>`<option value="${k}" ${F.reg==k?"selected":""}>${l}</option>`).join("")}</select>
   <label class=pp-min>Rating ≥ <input id=pp_min type=range min=0 max=10 value="${F.min}"><b id=pp_minv>${F.min}</b></label>
   <select id=pp_sort aria-label="Sort"><option value=rating>Sort: rating</option><option value=name ${F.sort=="name"?"selected":""}>Sort: name</option></select>
   <button type=button id=pp_reset>Reset</button></div>
  <div class=pp-chips id=pp_chips></div><div class=pp-grid id=pp_grid></div></div>
 <div class=pp-sec id=pp_plan><h3>🧮 Supply planner <span class=meta>— saved in this browser only</span></h3><div class=pp-plan>
  <div class=pp-in>
   <label>Adults <input type=number id=pl_ad min=0 max=50 value=2></label><label>Kids <input type=number id=pl_kid min=0 max=50 value=0></label>
   <label>Infants (diapers) <input type=number id=pl_inf min=0 max=20 value=0></label><label>Pets <input type=number id=pl_pet min=0 max=30 value=0></label>
   <div class=pp-days>Days ${[3,14,30,90,365].map(d=>`<button type=button data-d=${d}>${d}</button>`).join("")}<input type=number id=pl_days min=1 max=730 value=14 aria-label="Custom days"></div>
   <label>Climate <select id=pl_clim><option value=temp>Temperate</option><option value=hot>Hot</option><option value=cold>Cold</option></select></label>
   <fieldset><legend>Power needs</legend><label class=sw><input type=checkbox id=pl_ph checked> Phones</label><label class=sw><input type=checkbox id=pl_lt checked> Lights + radio</label>
    <label class=sw><input type=checkbox id=pl_fr> Fridge</label><label class=sw><input type=checkbox id=pl_fan> Fans / heated blanket</label><label>CPAP / medical devices <input type=number id=pl_cpap min=0 max=10 value=0></label></fieldset>
   <label class=sw><input type=checkbox id=pl_gun> Include firearms planning range</label>
   <div class=pp-btns><button type=button class=pri id=pl_print>🖨 Print checklist</button><button type=button id=pl_clear>Clear ticks</button></div></div>
  <div class=pp-out id=pl_out></div></div></div>
 <div class=pp-sec id=pp_scen><h3>🗂 Kits by scenario</h3><div class=pp-scen>${SCEN.map(([k,t,items,u])=>`<details class=pp-card ${k=="grid"?"open":""}><summary><b>${t}</b></summary><ul>${items.map(x=>{const [a,c]=x.split("|");return `<li>${E(a)} <a href="#" data-cat="${c}" title="Find suppliers">→</a></li>`}).join("")}</ul><a href="${U(u)}" target=_blank rel=noopener>Official guidance (Ready.gov) ↗</a></details>`).join("")}</div></div>
 <div class=pp-sec id=pp_budget><h3>💵 Budget starter kits <span class=meta>— rough targets, pick from the directory</span></h3><div class=pp-bud>${BUDGET.map(([p,t,items])=>`<div class=pp-card><div class=pp-price>${p}</div><b>${t}</b><ul>${items.map(x=>{const [a,c]=x.split("|");return `<li>${catOf(c).icon} ${E(a)} <a href="#" data-cat="${c}">→</a></li>`}).join("")}</ul></div>`).join("")}</div></div>
 <div class=pp-sec id=pp_range><h3>🏹 Range finder <span class=meta>— uses the site's location picker; starts global</span></h3><div id=pp_geo></div><div id=pp_rlinks></div>
  <div class=pp-note>🦺 Safety first: the four rules (treat every gun as loaded, never point at anything you aren't willing to destroy, finger off the trigger until ready, know your target and what's beyond). Take a class before buying, store firearms locked and unloaded, and <b>check local laws</b> on purchase, carry, transport and storage.</div></div>
 <div class=pp-sec id=pp_land><h3>🔎 Know the landscape: militia & extremist group research</h3>
  <div class=pp-warn>For awareness and research only — <b>not an endorsement</b>. blackout.network does not list or link armed militias or hate groups as joinable resources. These are reputable research and government sources that track who such groups are. To report a threat: <a href="https://tips.fbi.gov" target=_blank rel=noopener>tips.fbi.gov</a> or 911.</div><div class=pp-land id=pp_landl></div></div>
 <div class=pp-sec id=pp_tips><h3>🔁 Rotation & expiry reminders</h3><ul class=pp-tips>${TIPS.map(t=>`<li>${E(t)}</li>`).join("")}</ul></div>
 <div class=pp-sec id=pp_rubric><h3>📐 How we rate (0–10)</h3><div class=pp-rub id=pp_rub></div></div>`;
 wire();}
// ---------- directory ----------
function stats(){const n=D.entries.length,free=D.entries.filter(e=>e.tier=="Free").length,b={};D.entries.forEach(e=>b[e.band]=(b[e.band]||0)+1);
 $("#pp_stats",M).innerHTML=`<div class=pp-st><span><b>${n}</b> sources</span><span><b>${D.cats.length}</b> categories</span><span><b>${free}</b> free / official</span></div><div class=pp-bands>${["blue","green","amber","red"].map(k=>`<span style="--c:${BC[k]}"><i></i>${{blue:"9–10",green:"7–8",amber:"4–6",red:"0–3"}[k]}: ${b[k]||0}</span>`).join("")}</div>`}
function chips(){$("#pp_chips",M).innerHTML=`<button type=button data-c="" class="${F.cat?"":"on"}">All <span>${D.entries.length}</span></button>`+D.cats.map(c=>`<button type=button data-c="${c.id}" class="${F.cat==c.id?"on":""}">${c.icon} ${E(c.label)} <span>${c.n}</span></button>`).join("")}
function card(e){const c=catOf(e.cat),col=BC[e.band];const p=e.parts;
 const tip=D.rubric.map(r=>`${r.label}: ${p[r.k]}/2`).join("\n");
 return `<article class=pp-e style="--c:${col}"><img src="${E(e.badge)}" alt="" width=56 height=56 loading=lazy><div class=pp-eb>
  <div class=pp-eh><a href="${U(e.url)}" target=_blank rel="noopener nofollow">${E(e.name)} ↗</a><span class=pp-r title="${E(tip)}">${e.rating}<small>/10</small></span></div>
  <div class=pp-em>${c.icon} ${E(c.label)} · ${E(e.tier)} · ${E(e.region.replace(/^Free · /,""))}</div><div class=pp-en>${E(e.note)}</div>
  <div class=pp-ew title="${E(tip)}">★ ${E(e.why)}</div><div class=pp-tags>${e.tags.map(t=>`<span data-t="${E(t)}">${E(t)}</span>`).join("")}</div></div></article>`}
function render(){const q=F.q.trim().toLowerCase();let L=D.entries.filter(e=>(!F.cat||e.cat==F.cat)&&(!F.tier||e.tier==F.tier)&&e.rating>=F.min&&(!F.reg||(()=>{const s=regs(e);return s.has(F.reg)||s.has("Global")})())
  &&(!q||(e.name+" "+e.note+" "+e.tags.join(" ")+" "+e.region+" "+catOf(e.cat).label).toLowerCase().includes(q)));
 L.sort(F.sort=="name"?(a,b)=>a.name.localeCompare(b.name):(a,b)=>b.rating-a.rating||a.name.localeCompare(b.name));
 $("#pp_count",M).textContent=`— ${L.length} of ${D.entries.length} shown`;
 $("#pp_grid",M).innerHTML=L.length?L.map(card).join(""):`<div class=meta>No matches. Try fewer filters.</div>`;chips();save({F})}
function setCat(c){F.cat=c;render();$("#pp_dir",M).scrollIntoView({behavior:"smooth",block:"start"})}
// ---------- planner ----------
const n=id=>Math.max(0,+($("#"+id,M).value)||0);const fmt=x=>x>=100?Math.round(x).toLocaleString():(Math.round(x*10)/10).toLocaleString();
function plan(){const ad=n("pl_ad"),kid=n("pl_kid"),inf=n("pl_inf"),pet=n("pl_pet"),days=Math.max(1,n("pl_days")),cl=$("#pl_clim",M).value,ppl=ad+kid+inf,cpap=n("pl_cpap");
 const wmul=cl=="hot"?2:1,kmul=cl=="cold"?1.25:1;
 const water=ppl*days*wmul+pet*days*0.25,kcal=(ad*2000+kid*1500)*kmul*days,cans=Math.ceil(kcal/400),fd=Math.ceil(kcal/250);
 const wh=($("#pl_ph",M).checked?ppl*15:0)+($("#pl_lt",M).checked?25:0)+($("#pl_fr",M).checked?1500:0)+($("#pl_fan",M).checked?(cl=="cold"?600:300):0)+cpap*60;
 const bat=Math.ceil(wh*Math.min(days,3)/100)*100,solar=Math.ceil(wh/4/50)*50,weeks=Math.ceil(days/7);
 const L=[
 ["water","💧 Water",`${fmt(water)} gal total (${wmul==2?"2":"1"} gal/person/day${pet?" + ~¼ gal/pet/day":""})`,`≈ ${Math.ceil(water/7)} × 7-gal jugs, plus a filter and bleach/tablets as backup. Ready.gov: at least 1 gal/person/day; hot weather can double needs.`,"https://www.ready.gov/water"],
 ["food","🥫 Food",`${fmt(kcal)} kcal total (${kmul>1?"+25% for cold, ":""}~2,000/adult · ~1,500/child per day)`,`Mix of ≈ ${cans.toLocaleString()} cans (~400 kcal per 15 oz can) or ≈ ${fd.toLocaleString()} freeze-dried servings (~250 kcal each — check labels). Manual can opener. ${days>=30?"Add bulk rice, beans, oats for long durations.":""}`,"https://www.ready.gov/food"],
 ...(pet?[["special","🐾 Pet food & supplies",`≈ ${fmt(pet*days*0.5)} lb food (~½ lb/pet/day, varies by size)`,"Carrier, leash, meds, vaccination records, litter/bags.","https://www.ready.gov/pets"]]:[]),
 ...(inf?[["special","🍼 Infant supplies",`≈ ${Math.ceil(inf*days*8)} diapers · formula for ${days} days`,"Wipes, bottles, ready-to-feed formula needs no water.","https://www.ready.gov/kids"]]:[]),
 ["medical","⛑ First aid",`1 household kit + 1 trauma/IFAK per adult (${ad}) + 1 per vehicle`,`Tourniquet and pressure bandages in each trauma kit; take a Stop the Bleed class. Thermometer, OTC pain/fever, antidiarrheal, antihistamine, oral rehydration salts${ppl?` for ${ppl}`:""}.`,"https://www.stopthebleed.org"],
 ["special","💊 Prescriptions",`${Math.min(days,30)}+ days of each prescription on hand`,`Ask your doctor/pharmacist about an emergency supply; keep a med list and copies of prescriptions. ${cpap?`${cpap} medical device(s) need power — see below.`:""}`,"https://www.fda.gov/drugs/emergency-preparedness-drugs/safe-drug-use-after-natural-disaster"],
 ["power","🔋 Power",`~${fmt(wh)} Wh/day`,`Battery/power station ≈ ${bat.toLocaleString()} Wh covers 3 days; for longer, ≈ ${solar} W solar (≈4 sun-hours/day) or a generator. ${$("#pl_fr",M).checked?"A fridge dominates the load — consider a cooler + ice plan.":""} Power bank per person.`,"https://www.cpsc.gov/Safety-Education/Safety-Education-Centers/Portable-Generators"],
 ["tools","🔦 Lighting & batteries",`${ppl} headlamps · ${Math.max(1,Math.ceil(ppl/2))} lanterns · ≈ ${Math.ceil(ppl*4*weeks)} AA/AAA`,"Skip candles (fire risk). Lithium AAs store ~20 years.",""],
 ["heat","🔥 Cooking & fuel",`≈ ${Math.ceil(days*Math.max(1,ppl/4))} × 1-lb propane cylinders for a camp stove (~1/day per 4 people)`,`${cl=="cold"?`Indoor-safe heater: ≈ ${Math.ceil(days*1.5)} lb more propane (8 h/day on low). `:""}Generator: ≈ ${fmt(days*8*0.15)} gal gas at 8 h/day for a 2–3 kW inverter model (check yours). CO alarm on every level.`,"https://www.cdc.gov/carbon-monoxide/about/index.html"],
 ...(cl=="cold"?[["camping","🛏 Warmth",`${ppl} cold-rated sleeping bags or 2 wool blankets each`,"Hats, layers; pick one small room to keep warm.","https://www.ready.gov/winter-weather"]]:[]),
 ...(cl=="hot"?[["power","🌡 Cooling",`${ppl} battery fans · electrolytes for ${days} days`,"Know the signs of heat illness; plan a cooling-center trip.","https://www.weather.gov/safety/heat"]]:[]),
 ["sanitation","🧼 Hygiene & sanitation",`≈ ${Math.ceil(ppl*weeks)} rolls toilet paper · ${Math.ceil(ppl*days)} heavy-duty bags · 1 gal unscented bleach`,"Bucket toilet + kitty litter if water fails; soap, wipes, menstrual supplies, toothbrushes.","https://www.cdc.gov/clean-hands/about/index.html"],
 ["comms","📡 Comms",`1 NOAA/AM-FM radio · ${Math.max(ad,1)} FRS/GMRS radios`,`Paper contact list + out-of-area contact. ${days>=30?"Consider a ham license or satellite messenger for long events.":""}`,"https://www.weather.gov/nwr"],
 ["docs","📁 Documents & cash","IDs, insurance, deeds, medical info — copies in a waterproof bag + encrypted cloud","Cash in small bills; card readers fail in outages.","https://www.ready.gov/financial-preparedness"],
 ["nav","🧭 Navigation","Paper road map of your region + compass","Mark 2–3 evacuation routes and meeting points.",""],
 ...($("#pl_gun",M).checked?[["ammo","🎯 Firearms (optional, personal choice)",`Planning range: a few hundred rounds per firearm you own and train with`,"General guidance varies widely; most experts stress training and safe locked storage over quantity. Follow local laws on purchase, storage and transport.","https://projectchildsafe.org"]]:[])];
 const tk=load().ticks||{};
 $("#pl_out",M).innerHTML=`<div class=pp-oh><b>${ppl} people${pet?` + ${pet} pet${pet>1?"s":""}`:""} · ${days} days · ${{temp:"temperate",hot:"hot",cold:"cold"}[cl]}</b> <span class=meta>Estimates from Ready.gov/CDC baselines — adjust for your needs.</span></div>`+
  L.map(([c,t,q,d,u],i)=>{const key=t.replace(/[^a-z]/gi,"");return `<label class="pp-li ${tk[key]?"done":""}"><input type=checkbox data-k="${key}" ${tk[key]?"checked":""}><div><b>${t}</b> — ${E(q)}<div class=meta>${E(d)}</div>
  <div class=pp-lk><a href="#" data-cat="${c}">Find suppliers →</a>${u?` · <a href="${U(u)}" target=_blank rel=noopener>source ↗</a>`:""}</div></div></label>`}).join("");
 save({P:{ad,kid,inf,pet,days,cl,cpap,ph:$("#pl_ph",M).checked,lt:$("#pl_lt",M).checked,fr:$("#pl_fr",M).checked,fan:$("#pl_fan",M).checked,gun:$("#pl_gun",M).checked}});
 $$(".pp-days button",M).forEach(b=>b.classList.toggle("on",+b.dataset.d==days))}
function restorePlan(){const P=load().P;if(!P)return;const s=(id,v)=>{const el=$("#"+id,M);if(el&&v!=null)el.type=="checkbox"?el.checked=!!v:el.value=v};
 s("pl_ad",P.ad);s("pl_kid",P.kid);s("pl_inf",P.inf);s("pl_pet",P.pet);s("pl_days",P.days);s("pl_clim",P.cl);s("pl_cpap",P.cpap);s("pl_ph",P.ph);s("pl_lt",P.lt);s("pl_fr",P.fr);s("pl_fan",P.fan);s("pl_gun",P.gun)}
function printList(){const w=window.open("","_blank");if(!w)return alert("Allow pop-ups to print");
 const rows=$$(".pp-li",M).map(l=>`<li>☐ ${l.querySelector("b").textContent} — ${E(l.querySelector("div").childNodes[2].textContent.replace(/^\s*—\s*/,""))}<br><small>${E(l.querySelector(".meta").textContent)}</small></li>`).join("");
 w.document.write(`<!doctype html><title>blackout.network supply checklist</title><style>body{font:14px system-ui;margin:24px;color:#111}li{margin:0 0 10px;list-style:none}small{color:#555}</style><h2>blackout.network — supply checklist</h2><p>${E($(".pp-oh b",M).textContent)}</p><ul>${rows}</ul><p><small>Informational estimates from Ready.gov/CDC baselines. Not professional advice. Check local laws.</small></p>`);w.document.close();w.focus();w.print()}
// ---------- range finder ----------
function ranges(){const l=window.BNGeo&&BNGeo.get();const lab=l?l.label:"";const q=encodeURIComponent("shooting range"+(lab?" "+lab:""));
 const ll=l&&l.lat!=null?`#map=10/${l.lat}/${l.lon}`:"";const cc=l&&l.cc||"";
 const L=[["NSSF WhereToShoot — public & private ranges (US/Canada)","https://www.wheretoshoot.org/"],["OpenStreetMap: ranges"+(lab?" near "+lab:""),`https://www.openstreetmap.org/search?query=${q}${ll}`],
  ["Google Maps: ranges"+(lab?" near "+lab:""),`https://www.google.com/maps/search/${q}`],["Hunter education by state/province (IHEA-USA)","https://www.ihea-usa.org/hunter-education"],
  ["NRA course finder","https://firearmtraining.nra.org"],["USCCA class finder","https://www.usconcealedcarry.com/training"],["Women's shooting chapters (A Girl & A Gun)","https://agirlandagun.org"],["Women's chapters (Armed Women of America)","https://armedwomen.org"],
  ["LGBTQ-friendly instructors (Operation Blazing Sword)","https://www.blazingsword.org"],["Civilian Marksmanship Program clubs","https://thecmp.org"]];
 if(cc=="GB"||cc=="UK")L.unshift(["British Shooting club finder (UK)","https://www.britishshooting.org.uk"],["NRA UK / Bisley","https://nra.org.uk"]);
 if(cc=="CA")L.unshift(["RCMP: Canadian Firearms Safety Course & PAL","https://rcmp.ca/en/firearms"]);
 if(cc=="AU")L.unshift(["SSAA ranges and clubs (Australia)","https://ssaa.org.au"]);
 if(l&&l.st)L.splice(1,0,[`${l.stname||l.st}: state wildlife agency public ranges (search)`,`https://www.google.com/search?q=${encodeURIComponent((l.stname||l.st)+" fish and wildlife public shooting range")}`]);
 $("#pp_rlinks",M).innerHTML=`<div class=meta>${lab?`Showing links for <b>${E(lab)}</b>.`:"Global view — pick a country/state or use your location for local searches."}</div><ul class=pp-rl>${L.map(([t,u])=>`<li><a href="${U(u)}" target=_blank rel=noopener>${E(t)} ↗</a></li>`).join("")}</ul>`}
// ---------- wiring ----------
function wire(){stats();render();
 $("#pp_landl",M).innerHTML=D.research.map(r=>`<div class=pp-lr><a href="${U(r.url)}" target=_blank rel=noopener>${E(r.name)} ↗</a><div>${E(r.desc)}</div><div class=meta>Source type: ${E(r.cred)}</div></div>`).join("");
 $("#pp_rub",M).innerHTML=`<p>Each source gets 0–2 points on five criteria; the rating is the sum. Hover a rating to see its breakdown.</p><ul>${D.rubric.map(r=>`<li><b>${E(r.label)}</b></li>`).join("")}</ul>
  <div class=pp-bands>${[["blue","9–10 excellent"],["green","7–8 solid"],["amber","4–6 mixed / niche"],["red","0–3 caution"]].map(([k,l])=>`<span style="--c:${BC[k]}"><i></i>${l}</span>`).join("")}</div>
  <p class=meta>Ratings are blackout.network's editorial judgment from public information and the companies' own pages, not lab tests. Official/free guidance usually scores 10. Emblems are original graphics made for this site — not the companies' logos. ${D.linkcheck.checked?`Links checked ${E(D.linkcheck.checked)}.`:""}</p>`;
 $("#pp_q",M).oninput=e=>{F.q=e.target.value;render()};$("#pp_tier",M).onchange=e=>{F.tier=e.target.value;render()};$("#pp_reg",M).onchange=e=>{F.reg=e.target.value;render()};
 $("#pp_min",M).oninput=e=>{F.min=+e.target.value;$("#pp_minv",M).textContent=F.min;render()};$("#pp_sort",M).onchange=e=>{F.sort=e.target.value;render()};
 $("#pp_reset",M).onclick=()=>{Object.assign(F,{q:"",cat:"",tier:"",reg:"",min:0,sort:"rating"});$("#pp_q",M).value="";$("#pp_tier",M).value="";$("#pp_reg",M).value="";$("#pp_min",M).value=0;$("#pp_minv",M).textContent=0;$("#pp_sort",M).value="rating";render()};
 M.addEventListener("click",e=>{const c=e.target.closest("[data-c]");if(c&&c.closest("#pp_chips")){F.cat=c.dataset.c;render();return}
  const a=e.target.closest("a[data-cat]");if(a){e.preventDefault();setCat(a.dataset.cat);return}
  const t=e.target.closest(".pp-tags span");if(t){F.q=t.dataset.t;$("#pp_q",M).value=F.q;render();return}
  const j=e.target.closest("a[data-j]");if(j){e.preventDefault();$("#"+j.dataset.j,M).scrollIntoView({behavior:"smooth",block:"start"});return}
  const g=e.target.closest("button[data-go]");if(g){const b=nav.querySelector(`button[data-tab="${g.dataset.go}"]`);if(b){b.click();scrollTo(0,0)}return}
  const d=e.target.closest(".pp-days button");if(d){$("#pl_days",M).value=d.dataset.d;plan()}});
 $(".pp-in",M).addEventListener("input",plan);$(".pp-in",M).addEventListener("change",plan);
 $("#pl_out",M).addEventListener("change",e=>{const k=e.target.dataset&&e.target.dataset.k;if(!k)return;const tk=load().ticks||{};tk[k]=e.target.checked;save({ticks:tk});e.target.closest(".pp-li").classList.toggle("done",e.target.checked)});
 $("#pl_print",M).onclick=printList;$("#pl_clear",M).onclick=()=>{save({ticks:{}});plan()};
 restorePlan();plan();
 const gi=()=>{if(!window.BNGeo)return setTimeout(gi,300);BNGeo.picker($("#pp_geo",M));BNGeo.on(ranges);ranges()};gi()}
async function init(){if(loaded)return;loaded=true;try{D=await (await fetch("api/preppers",{cache:"no-store"})).json();shell()}catch(e){loaded=false;app.innerHTML=`<div class=meta>Couldn't load: ${E(e)}</div>`}}
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="preppers")init()});
window.BNPreppers={init,setCat};
})();
