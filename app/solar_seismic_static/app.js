// ---- Solar & Seismic tab (served by solar_seismic.py; loaded by dashboard.html). Read-only research view: observed patterns, not causation. ----
(()=>{"use strict";
const M=document.getElementById("tab-solar");if(!M)return;
const e_=s=>esc(s),U=u=>esc(safeUrl(u));
const SS={d:null,open:new Set(),charts:{},map:null,lay:null,view:"week",hist:false,m45:false,afilt:"all",aall:false,qall:false,busy:false,built:false,shown:false,sel:null};
const KPC=k=>k==null?"#3a4250":k>=8.67?"#820014":k>=7.67?"#a8071a":k>=6.67?"#d4380d":k>=5.67?"#ff4d4f":k>=4.67?"#ff7a45":k>=3.67?"#faad14":"#52c41a";
const GLAB=["quiet","G1 minor","G2 moderate","G3 strong","G4 severe","G5 extreme"];
const gOf=k=>k==null||k<4.67?0:Math.min(5,Math.max(1,Math.floor(k+.34)-4));
const kpTxt=k=>{if(k==null)return"—";const w=Math.floor(k+.01),f=+(k-w).toFixed(2);return f>=.6?`${w+1}−`:f>=.3?`${w}+`:`${w}`};
const xcls=f=>{if(!f||f<=0)return"—";for(const[L,b]of[["X",1e-4],["M",1e-5],["C",1e-6],["B",1e-7],["A",1e-8]])if(f>=b)return L+(f/b).toFixed(1);return"A"+(f/1e-8).toFixed(1)};
const etS=t=>t?new Date(t).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric"}).replace(", "," ").replace(":00","").replace(" AM","a").replace(" PM","p"):"";
const etF=t=>t?new Date(t).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET":"—";
const ago=s=>s==null?"—":s<90?`${s}s ago`:s<5400?`${Math.round(s/60)} min ago`:`${Math.round(s/3600)} h ago`;
const lvl=n=>n==null||n===""?0:+n;
const pill=(sc,n)=>`<span class="pill s${Math.min(5,lvl(n))}">${sc}${n==null||n===""?"–":n}</span>`;

// ---------- accordion ----------
function acc(key,head,body,o={}){const op=SS.open.has(key)||(o.open&&!SS.open.has("x:"+key));if(o.open&&!SS.open.has("x:"+key))SS.open.add(key);
 return `<div class="ss-acc ${o.cls||""}${op?" open":""}" data-k="${e_(key)}"><button type="button" class="ss-ah" aria-expanded="${op}">${o.ic?`<span class=ic>${o.ic}</span>`:""}<span class=t>${head}</span><span class=ss-chev>▶</span></button><div class=ss-ab><div class=ss-ai><div class=ss-ac>${body}</div></div></div></div>`}
function keepRoom(){const r=M.getBoundingClientRect();const need=scrollY+innerHeight-(r.top+scrollY);if(need>M.offsetHeight)M.style.minHeight=need+"px"}
M.addEventListener("click",ev=>{const h=ev.target.closest(".ss-ah");if(!h||!M.contains(h))return;ev.preventDefault();const a=h.parentElement,k=a.dataset.k;
 const y0=h.getBoundingClientRect().top;keepRoom();const op=!a.classList.contains("open");a.classList.toggle("open",op);h.setAttribute("aria-expanded",op);
 if(op){SS.open.add(k);SS.open.delete("x:"+k)}else{SS.open.delete(k);SS.open.add("x:"+k)}
 const t0=performance.now();(function fix(){const d=h.getBoundingClientRect().top-y0;if(Math.abs(d)>.5)scrollBy(0,d);if(performance.now()-t0<380)requestAnimationFrame(fix)})();
 if(op){const c=a.querySelector("canvas[data-lazy]");if(c)lazyChart(c.dataset.lazy)}});

// ---------- illustrations ----------
const SV=(vb,b)=>`<svg viewBox="${vb}" role="img" aria-hidden="true" font-family="system-ui,sans-serif">${b}</svg>`;
const FIG={
chain:SV("0 0 430 120",`<defs><radialGradient id="ssSun" cx="40%" cy="40%"><stop offset="0" stop-color="#fff1b8"/><stop offset=".5" stop-color="#ffc53d"/><stop offset="1" stop-color="#d46b08"/></radialGradient><radialGradient id="ssEarth" cx="40%" cy="35%"><stop offset="0" stop-color="#91d5ff"/><stop offset="1" stop-color="#0050b3"/></radialGradient><marker id="ssAr" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8z" fill="#ffd666"/></marker></defs>
<circle cx="40" cy="58" r="30" fill="url(#ssSun)"/><circle cx="31" cy="50" r="4" fill="#874d00" opacity=".7"/><circle cx="47" cy="64" r="3" fill="#874d00" opacity=".7"/>
<path d="M66 40 Q74 26 84 36" stroke="#ff7a45" stroke-width="3" fill="none"/>
<g stroke="#ffd666" stroke-width="1.6" fill="none" marker-end="url(#ssAr)" opacity=".85"><path d="M78 50 L170 46"/><path d="M78 62 L170 62"/><path d="M78 74 L170 80"/></g>
<ellipse cx="128" cy="62" rx="18" ry="24" fill="#ffd666" opacity=".18" stroke="#ffd666" stroke-dasharray="3 3"/>
<path d="M226 22 Q186 60 226 100" stroke="#8b95a3" stroke-width="1.6" fill="none" stroke-dasharray="4 3"/>
<g stroke="#4aa3ff" stroke-width="1.3" fill="none" opacity=".9"><path d="M262 60 C240 20 300 10 330 40 C350 58 380 60 420 56"/><path d="M262 60 C240 100 300 110 330 80 C350 62 380 62 420 66"/><path d="M262 60 C252 34 292 30 304 46"/><path d="M262 60 C252 86 292 90 304 74"/></g>
<circle cx="262" cy="60" r="12" fill="url(#ssEarth)"/>
<path d="M256 76 l-6 14 h8 l-4 12" stroke="#ff4d4f" stroke-width="2" fill="none"/>
<g font-size="9.5" fill="#c9d0d9" text-anchor="middle"><text x="40" y="104">Sun</text><text x="124" y="104">solar wind · CME</text><text x="204" y="117" text-anchor="end">bow shock</text><text x="262" y="20">magnetosphere</text><text x="372" y="96">magnetotail</text><text x="290" y="117" fill="#ff7875">ground currents</text></g>`),
sun:SV("0 0 270 150",`<defs><radialGradient id="ssS2" cx="45%" cy="45%"><stop offset="0" stop-color="#fff1b8"/><stop offset=".6" stop-color="#ffc53d"/><stop offset="1" stop-color="#d46b08"/></radialGradient></defs>
<g stroke="#ffd666" fill="none" stroke-width="1.3" opacity=".75"><path d="M135 30 C40 -10 30 160 135 120"/><path d="M135 30 C230 -10 240 160 135 120"/><path d="M135 42 C80 20 80 130 135 108"/><path d="M135 42 C190 20 190 130 135 108"/></g>
<circle cx="135" cy="75" r="42" fill="url(#ssS2)"/><path d="M95 75 Q135 62 175 75" stroke="#874d00" stroke-width="1" fill="none" opacity=".6"/>
<circle cx="120" cy="68" r="5" fill="#5c3100"/><circle cx="128" cy="70" r="3" fill="#5c3100"/><path d="M118 64 C118 46 132 46 130 66" stroke="#ff7a45" stroke-width="2.2" fill="none"/>
<g font-size="10" fill="#c9d0d9"><text x="8" y="144">field lines wound up by rotation</text><text x="162" y="38" fill="#ffd666">sunspot pair</text></g>`),
xray:SV("0 0 270 150",`<g font-size="10" fill="#c9d0d9"><path d="M40 10 V120 H262" stroke="#5a6472" fill="none"/>
${[["X",22,"#ff4d4f"],["M",44,"#ff7a45"],["C",66,"#faad14"],["B",88,"#52c41a"],["A",110,"#2c3440"]].map(([l,y,c])=>`<rect x="41" y="${y-11}" width="221" height="22" fill="${c}" opacity=".12"/><text x="24" y="${y+3}" fill="${c}" font-weight="700">${l}</text>`).join("")}
<path d="M42 96 L80 94 L100 92 L112 70 L118 40 L126 64 L140 84 L170 90 L190 86 L200 60 L206 74 L230 88 L262 92" stroke="#ffd666" stroke-width="2" fill="none"/>
<text x="120" y="34" fill="#ff7a45">M-class flare</text><text x="48" y="140">each letter = 10× the one below (W/m²)</text></g>`),
mag:SV("0 0 270 150",`<defs><radialGradient id="ssE2" cx="40%" cy="35%"><stop offset="0" stop-color="#91d5ff"/><stop offset="1" stop-color="#0050b3"/></radialGradient></defs>
<path d="M66 20 Q20 75 66 130" stroke="#8b95a3" stroke-dasharray="4 3" fill="none"/>
<g stroke="#4aa3ff" fill="none" stroke-width="1.3"><path d="M110 75 C90 30 150 20 180 45 C200 60 230 60 266 58"/><path d="M110 75 C90 120 150 130 180 105 C200 90 230 90 266 92"/><path d="M110 75 C100 50 135 45 145 60"/><path d="M110 75 C100 100 135 105 145 90"/></g>
<g stroke="#ffd666" stroke-width="1.4"><path d="M8 50 H52"/><path d="M8 75 H52"/><path d="M8 100 H52"/></g>
<path d="M30 34 V58" stroke="#ff4d4f" stroke-width="2.4" marker-end="url(#ssAr)"/><text x="34" y="30" font-size="10" fill="#ff7875">Bz south</text>
<circle cx="83" cy="75" r="5" fill="#ff4d4f" opacity=".85"/><text x="70" y="64" font-size="9.5" fill="#ff7875">reconnection</text>
<circle cx="110" cy="75" r="11" fill="url(#ssE2)"/>
<g font-size="10" fill="#c9d0d9"><text x="56" y="145">bow shock</text><text x="186" y="40">magnetotail →</text></g>`),
kp:SV("0 0 270 150",`<g font-size="10" fill="#c9d0d9"><path d="M30 10 V120 H262" stroke="#5a6472" fill="none"/>
${[1,2,2.33,3,1.67,4,5.33,6.67,5,3.33,2,1.33].map((k,i)=>`<rect x="${36+i*19}" y="${120-k*11}" width="14" height="${k*11}" fill="${KPC(k)}" rx="1.5"/>`).join("")}
<path d="M30 ${120-4.67*11} H262" stroke="#ff7a45" stroke-dasharray="4 3"/><text x="200" y="${116-4.67*11}" fill="#ff7a45">G1 line (Kp 5)</text>
<text x="10" y="124">0</text><text x="10" y="58">5</text><text x="10" y="25">9</text><text x="60" y="140">3-hour Kp bars during a storm</text></g>`),
grid:SV("0 0 270 150",`<g fill="none" stroke-width="1.6"><path d="M10 40 Q70 10 130 40 T260 40" stroke="#4aa3ff" opacity=".7"/><path d="M10 52 Q70 22 130 52 T260 52" stroke="#4aa3ff" opacity=".4"/>
<path d="M40 70 L40 125 M30 80 H50 M32 90 H48 M220 70 L220 125 M210 80 H230 M212 90 H228" stroke="#c9d0d9"/><path d="M40 80 Q130 70 220 80" stroke="#c9d0d9"/>
<path d="M14 132 H256" stroke="#5a6472"/><path d="M40 125 V132 M220 125 V132" stroke="#c9d0d9"/><path d="M50 140 H210" stroke="#ff4d4f" stroke-dasharray="5 4"/><path d="M200 136 L210 140 L200 144" stroke="#ff4d4f"/></g>
<rect x="31" y="100" width="18" height="16" fill="#faad14" opacity=".35" stroke="#faad14"/><rect x="211" y="100" width="18" height="16" fill="#faad14" opacity=".35" stroke="#faad14"/>
<g font-size="10" fill="#c9d0d9"><text x="92" y="20">electrojet in the ionosphere</text><text x="80" y="128">earth: induced electric field</text><text x="104" y="96">transformer → GIC ↯</text></g>`),
quake:SV("0 0 270 150",`<g fill="none" stroke-width="1.6"><path d="M10 105 H260" stroke="#5a6472"/><path d="M130 105 L118 140" stroke="#ff4d4f"/>
<path d="M20 70 Q60 50 100 70 T180 70 T260 70" stroke="#ffd666" opacity=".6"/><text x="22" y="62" font-size="10" fill="#ffd666" stroke="none">geomagnetic activity</text>
<path d="M30 100 l8 -10 l8 14 l8 -18 l8 22 l8 -12 l8 6" stroke="#4aa3ff"/><path d="M160 100 l8 -6 l8 10 l8 -14 l8 16 l8 -8" stroke="#4aa3ff"/></g>
<text x="118" y="88" font-size="26" fill="#faad14" font-weight="800">?</text>
<g font-size="10" fill="#c9d0d9"><text x="30" y="126">quakes: driven by tectonic stress</text><text x="40" y="146">is there a measurable link? → test, don't assume</text></g>`)};

// ---------- science content ----------
const SCI=[
["sci_sun","☀","The Sun's magnetic field, sunspots and the solar wind","Why the Sun has weather at all",`<figure class=ss-fig>${FIG.sun}<figcaption>Rotation and convection twist the field; sunspots mark where it breaks through.</figcaption></figure>
<p>The Sun is a ball of electrically conducting plasma. It rotates faster at the equator (about 25 days) than near the poles (about 35 days), and the boiling convection beneath its surface stretches and twists the magnetic field. This <b>dynamo</b> concentrates the field into bundles; where a bundle punches through the visible surface it chokes off the flow of heat, leaving a cooler, darker <b>sunspot</b> (about 3,500–4,500 °C versus about 5,500 °C around it). Sunspot groups are the <b>active regions</b> where flares and eruptions start.</p>
<p>Sunspot numbers rise and fall over a roughly <b>11-year solar cycle</b>, and the Sun's overall magnetic polarity flips each cycle (a full magnetic cycle is about 22 years). Solar Cycle 25 began in December 2019 and peaked around late 2024. In 2026 the Sun is in the declining phase, which historically still produces large flares and eruptions, plus recurring fast wind streams from coronal holes.</p>
<p>The outer atmosphere (the <b>corona</b>) is over a million degrees, too hot for gravity to hold, so it streams away continuously as the <b>solar wind</b>: typically 300–500 km/s (slow wind) up to 700–800 km/s (fast wind from coronal holes), with a few protons per cubic centimeter at Earth. The wind drags the Sun's field with it as the <b>interplanetary magnetic field (IMF)</b>, a few nanotesla (nT) at Earth. Flares and eruption shock waves can also accelerate <b>solar energetic particles</b>, protons moving at a large fraction of light speed, that arrive within tens of minutes to hours.</p>
<p>The wind is measured about 1.5 million km sunward of Earth at the L1 point, which gives roughly <b>15–60 minutes</b> of warning, depending on the wind speed. The speed, density, Bt and Bz tiles below come from NOAA's real-time L1 feed.</p>`],
["sci_flare","💥","Solar flares (X-ray classes) and coronal mass ejections","Light-speed flashes vs. billion-ton clouds",`<figure class=ss-fig>${FIG.xray}<figcaption>GOES measures 0.1–0.8 nm X-ray flux; the class is read off a log scale.</figcaption></figure>
<p>A <b>solar flare</b> is a sudden release of magnetic energy in an active region, a flash across the spectrum. Flares are classed by their peak soft X-ray flux (0.1–0.8 nm) measured by NOAA's GOES satellites: <b>A, B, C, M, X</b>, each 10× stronger than the last (C = 10⁻⁶ W/m², M = 10⁻⁵, X = 10⁻⁴). The number is a multiplier: M2.5 is 2.5 × 10⁻⁵ W/m², and the X class is open-ended (X10, X20…). The light arrives in about <b>8 minutes</b>, so there is no warning. It ionizes the sunlit upper atmosphere and can black out shortwave (HF) radio on the dayside for minutes to hours; that is NOAA's <b>R scale</b>.</p>
<p>A <b>coronal mass ejection (CME)</b> is different: a cloud of magnetized plasma, typically around a billion tons or more, thrown off at 250 to more than 3,000 km/s. Earth-directed CMEs take roughly <b>15 hours (the fastest) to 4 days</b> to arrive. A fast CME drives a shock wave ahead of it that accelerates energetic particles. Big flares and CMEs often happen together, but either can occur alone, and a CME's punch depends mostly on its speed and the <b>direction of its magnetic field</b> when it reaches Earth (see Bz, next).</p>`],
["sci_mag","🧲","Earth's magnetosphere, bow shock, reconnection and Bz","How the shield works and how energy gets in",`<figure class=ss-fig>${FIG.mag}<figcaption>A southward IMF (negative Bz) reconnects with Earth's field on the dayside.</figcaption></figure>
<p>Earth's own field, generated by the churning liquid-iron outer core, carves out a protective bubble, the <b>magnetosphere</b>. The supersonic solar wind slows abruptly at the <b>bow shock</b> (about 13–15 Earth radii upstream), flows around the <b>magnetopause</b> (about 10 Earth radii on the dayside, closer during storms), and stretches the nightside into a long <b>magnetotail</b>.</p>
<p>The key to space weather is <b>magnetic reconnection</b>. Earth's field at the dayside nose points north. When the IMF's north–south component, <b>Bz</b>, points <b>south (negative)</b>, the two fields are antiparallel and can merge, peeling Earth's field lines open and loading energy into the tail. That energy is released in bursts (substorms) that drive currents and aurora. A northward Bz mostly keeps the door shut. Rule of thumb: <b>fast wind plus a strongly southward Bz (−10 nT or lower) held for hours</b> is the recipe for a storm. That is why the Bz tile turns red when it goes negative.</p>`],
["sci_storm","🌐","Geomagnetic storms: the Kp index, NOAA G / S / R scales and Dst","How storms are measured",`<figure class=ss-fig>${FIG.kp}<figcaption>Kp is reported every 3 hours on a 0–9 scale, in thirds (5−, 5, 5+).</figcaption></figure>
<p>A <b>geomagnetic storm</b> is a global disturbance of Earth's field driven by the solar wind. The <b>Kp index</b> summarizes how disturbed the field was over each 3-hour window, on a quasi-logarithmic 0–9 scale from a network of mid-latitude magnetometers. NOAA's real-time estimate is shown here, plus a 1-minute estimate for "right now".</p>
<table class=ss-tb><tr><th>NOAA scale</th><th>What it measures</th><th>Levels</th></tr>
<tr><td><b>G</b> geomagnetic storm</td><td>Kp</td><td>G1 Kp 5 · G2 Kp 6 · G3 Kp 7 · G4 Kp 8 · G5 Kp 9</td></tr>
<tr><td><b>S</b> solar radiation storm</td><td>≥10 MeV proton flux (pfu)</td><td>S1 10 · S2 100 · S3 1,000 · S4 10⁴ · S5 10⁵</td></tr>
<tr><td><b>R</b> radio blackout</td><td>peak X-ray flux</td><td>R1 M1 · R2 M5 · R3 X1 · R4 X10 · R5 X20</td></tr></table>
<p><b>Dst</b> (disturbance storm time) is an hourly index, in nT, of the ring current that swells around Earth during storms, measured at low-latitude observatories. Below −50 nT is a moderate storm, below −100 an intense one, and below −250 a "superstorm". The May 10–11, 2024 storm, the first G5 since 2003, reached roughly −400 nT. This tab uses Kp because NOAA publishes it in real time on a 3-hour grid that lines up with the earthquake bins.</p>`],
["sci_ground","⚡","How it reaches the ground: power grids, pipelines, radio, GPS, aurora, radiation","The practical effects",`<figure class=ss-fig>${FIG.grid}<figcaption>A changing field induces an electric field in the ground; long grounded conductors pick it up.</figcaption></figure>
<p><b>Power grids and pipelines.</b> During storms, intense ionospheric currents (electrojets) make the ground-level magnetic field change quickly. By Faraday's law that induces a <b>geoelectric field</b> in the Earth, from fractions of a volt to several volts per kilometer, strongest over resistive rock. Long conductors grounded at both ends pick it up as <b>geomagnetically induced currents (GIC)</b>, quasi-DC currents that flow through transformer neutrals. They can half-saturate transformer cores, causing heating, harmonics and extra reactive-power demand, and can trip protection. On March 13, 1989 the Hydro-Québec grid collapsed in about 90 seconds, leaving about 6 million people without power for about 9 hours. In pipelines, GIC upsets cathodic corrosion protection. Places at lower geomagnetic latitude have lower risk than high-latitude regions (Canada, Scandinavia, the northern US), but not zero. US utilities must assess it under the NERC TPL-007 standard.</p>
<p><b>Radio and GPS.</b> Flares black out dayside HF radio (R scale). Energetic protons cause polar-cap absorption that can last days and disrupt polar air routes. Storms make the ionosphere lumpy and fast-changing, degrading GPS/GNSS. During the May 2024 storm, precision GPS steering for farm equipment in the US Midwest was disrupted at planting time.</p>
<p><b>Aurora.</b> Particles raining down field lines make oxygen glow green (557.7 nm) and red (630 nm) and nitrogen glow blue-purple. Big storms push the auroral oval toward the equator. In May and October 2024 aurora was photographed as far south as the US Gulf Coast and northern Mexico.</p>
<p><b>Radiation for aviation and satellites.</b> Solar radiation storms (S scale) raise the dose on polar and high-altitude flights and for astronauts. Satellites suffer electronics upsets and surface or internal charging. Storms also heat and puff up the upper atmosphere, raising drag: in February 2022 SpaceX lost about 38 of 49 newly launched Starlink satellites after a modest geomagnetic storm.</p>`],
["sci_quake","🔍","Is there a solar / geomagnetic link to earthquakes? What has been proposed, and the evidence","An honest look at a contested idea",`<figure class=ss-fig>${FIG.quake}<figcaption>A hypothesis worth testing, not a finding.</figcaption></figure>
<p><b>What drives earthquakes.</b> Earthquakes release elastic strain that plate motion builds up over decades to millennia. Whether a stressed fault fails on a given day is extremely hard to predict. <b>The USGS position is that no one, by any method, has predicted a major earthquake</b>; solar or geomagnetic indicators are not an accepted forecasting tool.</p>
<p><b>What has been proposed.</b></p><ul>
<li>Electrical or electromagnetic triggering: storm-induced telluric currents in fault zones affecting fluids or friction (electrokinetic and piezoelectric ideas).</li>
<li>Magnetostriction or tiny stress changes from rapid field changes.</li>
<li>Solar-cycle modulation of global seismicity.</li>
<li>Specific statistical claims. For example, a 2020 <i>Scientific Reports</i> paper (Marchitelli et al.) reported that global M5.6+ quakes tracked solar-wind proton density over about 20 years. Results like this are debated and not broadly replicated.</li></ul>
<p><b>Why most seismologists are skeptical.</b></p><ul>
<li>The stresses a geomagnetic storm could plausibly add to a fault are tiny. Even the solid-Earth tides, which add far larger stress changes twice a day, show only a weak, hard-won statistical triggering effect.</li>
<li>A USGS study (Love &amp; Thomas, 2013, <i>Geophysical Research Letters</i>), titled "Insignificant solar-terrestrial triggering of earthquakes", found no statistically significant link between global earthquakes and solar-wind or geomagnetic activity.</li></ul>
<p><b>Common traps.</b></p><ul>
<li>Aftershocks cluster, so quakes are not independent events.</li>
<li>Storms are rare, so storm samples are small.</li>
<li>Catalog completeness varies by region.</li>
<li>Testing many windows and lags guarantees a few "hits" by chance.</li></ul>
<p><b>The honest stance:</b> unproven and mostly unsupported, but cheap to keep testing. The Correlation lab below logs every 3-hour window going forward, so the evidence base grows instead of resting on anecdotes.</p>`]];

// ---------- skeleton ----------
function skeleton(){
 $("ss_app").innerHTML=`<div class=ss-status id=ss_status></div>
 <div class=ss-lead><div><p><b>Space weather and earthquakes, side by side.</b> The Sun constantly sends out a magnetized wind and, now and then, flares and billion-ton eruptions. Earth's magnetic field deflects most of it, but some of that energy reaches the ground as electric currents, radio blackouts and aurora. This tab explains the physics, shows NOAA's and the USGS's live readings, and runs an open-ended experiment: does the bot's own data show any pattern between geomagnetic activity and earthquake timing?</p>
 <p class=meta>Click any heading to expand it in place; click again to collapse it.</p></div><div>${FIG.chain}</div></div>
 <h3 class=ss-h>① The science, from the Sun to the ground</h3><div id=ss_sci>${SCI.map(([k,ic,t,s,b])=>acc(k,`<b>${t}</b><small>${s}</small>`,b,{ic,cls:k=="sci_quake"?"mu":"sol"})).join("")}</div>`;
 const live=document.createElement("section");live.className="pn";live.id="ss_live";
 live.innerHTML=`<h2>② Live conditions <span class=meta>— NOAA Space Weather Prediction Center, USGS and tsunami.gov</span></h2><div class=ss-tiles id=ss_tiles></div>
 <div class=ss-cols><div><h3 class=ss-h>Space weather alerts, watches &amp; warnings <span class=meta id=ss_acount></span></h3><div class=ss-chips id=ss_achips></div><div id=ss_alerts></div></div>
 <div><h3 class=ss-h>Notable earthquakes &amp; tsunami flags, past 7 days <span class=meta id=ss_qcount></span></h3><div class=ss-hint style="margin-bottom:4px">M5+, USGS "significant", tsunami-flagged, or picked up by the bot's scanner. Every M2.5+ quake is on the map and in the charts.</div><div id=ss_quakes></div></div></div>
 <div id=ss_extra style="margin-top:8px"></div>`;
 const lab=document.createElement("section");lab.className="pn";lab.id="ss_lab";
 lab.innerHTML=`<h2>③ Correlation lab <span class=meta>— science is discovery: this bot is capturing the evidence</span></h2>
 <div class=ss-banner><svg viewBox="0 0 54 54" aria-hidden="true"><circle cx="23" cy="23" r="15" fill="none" stroke="#ffd666" stroke-width="3"/><path d="M34 34 L48 48" stroke="#ffd666" stroke-width="4" stroke-linecap="round"/><path d="M14 26 l4 -6 l4 8 l4 -10 l4 8" stroke="#4aa3ff" stroke-width="2" fill="none"/></svg>
 <div><b>Observed patterns, not proven causes.</b> Every 3 hours lines up a Kp reading (NOAA's 3-hour grid), the peak GOES X-ray flux and a USGS earthquake count, and logs it to its own database, so the evidence grows week by week. A correlation here is a lead to examine, not a finding. Read the caveats before drawing conclusions. <span id=ss_logline></span></div></div>
 <div class=ss-ctl><span>Statistics over</span><span class=ss-seg id=ss_view><button data-v=week class=on>Past 7 days</button><button data-v=all>Everything logged</button></span><span class=ss-hint>Click any bar to drill into that 3-hour window.</span></div>
 <div class=ss-legend id=ss_leg1></div><div class=ss-chart><canvas id=ss_c1></canvas></div>
 <div class=ss-legend id=ss_leg2 style="margin-top:6px"></div><div class="ss-chart b"><canvas id=ss_c2></canvas></div>
 <div id=ss_binbox></div>
 <div class=ss-stats id=ss_stats></div><div id=ss_rates></div><div class=ss-caveat id=ss_cav></div>
 <div id=ss_labacc></div>
 <h3 class=ss-h style="margin-top:12px">Where the quakes were <span class=meta id=ss_mapmeta></span></h3>
 <div id=ss_stormmsg></div>
 <div class=ss-maphd><label class=sw><input type=checkbox id=ss_m45> M4.5+ only</label><label class=sw><input type=checkbox id=ss_hist> include older quakes from the log</label>
  <span><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ff4d4f;margin-right:4px"></i>during a storm window (Kp ≥ 5)</span><span><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--bn-link,#4aa3ff);margin-right:4px"></i>other quakes</span><span><i style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #5cdbd3;margin-right:4px"></i>tsunami flag</span><span class=ss-hint>Circle size = magnitude. Click the map to enable scroll-zoom.</span></div>
 <div id=ss_map></div>`;
 M.append(live,lab);
 // How-this-works notes (same component as the other tabs)
 if(typeof HW_ICONS=="object"&&typeof hwI=="function"){const Y="#faad14";
  HW_ICONS.solar=hwI(`<circle cx="44" cy="55" r="20" stroke="${Y}"/><path d="M44 25 v-8 M44 93 v-8 M14 55 h-8 M82 55 h-8 M23 34 l-6 -6 M65 76 l6 6 M23 76 l-6 6 M65 34 l6 -6" stroke="${Y}"/><path d="M90 55 h30" stroke-dasharray="4 4"/><circle cx="150" cy="55" r="12"/><path d="M138 55 C120 20 175 15 192 40 M138 55 C120 90 175 95 192 70"/><path d="M146 72 l-5 12 h7 l-4 11" stroke="${R}"/>`);
  HW_ICONS.solar_live=hwI(`<rect x="14" y="16" width="52" height="36" rx="4" stroke="${Y}"/><rect x="74" y="16" width="52" height="36" rx="4" stroke="${Y}"/><rect x="134" y="16" width="52" height="36" rx="4"/><path d="M22 40 l8 -8 l8 4 l8 -12 l10 6" stroke="${Y}"/><path d="M142 42 l6 -10 l6 14 l6 -18 l6 12 l8 -4"/><path d="M14 66 h172 M14 80 h150 M14 94 h120"/><circle cx="178" cy="80" r="4" fill="${R}" stroke="${R}"/>`);
  HW_ICONS.solar_lab=hwI(`<path d="M16 98 h170 M16 98 V12"/>${[22,30,18,44,26,20,34,16].map((h,i)=>`<rect x="${24+i*20}" y="${54-h}" width="12" height="${h}" stroke="${Y}"/>`).join("")}${[10,18,8,22,14,30,12,16].map((h,i)=>`<rect x="${24+i*20}" y="${96-h}" width="12" height="${h}"/>`).join("")}<circle cx="140" cy="40" r="16" stroke="${R}"/><path d="M152 52 l14 14" stroke="${R}"/>`);}
 if(typeof hwAttach=="function"){
  hwAttach(M.querySelector("#ss_top h2"),"solar",()=>"The science section is written from NOAA SWPC, NASA and USGS reference material. The live tiles and charts come straight from free public NOAA, USGS and tsunami.gov data feeds, fetched by this computer at most once every 5 minutes and cached, and cross-checked against what the bot's scanner already logged in its own database. Nothing here changes threat scores or ranks.");
  hwAttach(live.querySelector("h2"),"solar_live",()=>"Tiles show the latest NOAA readings: the 3-hour planetary Kp index (plus NOAA's 1-minute estimate), the R/S/G scales and 3-day forecast, the GOES X-ray flux and flare list, and the solar wind and magnetic field at L1. Earthquakes come from the USGS M2.5+ and 'significant' feeds for the past week; tsunami bulletins from NOAA's two tsunami warning centers. Each item links to its raw source. A ✓ bot badge means the scanner also captured it.");
  hwAttach(lab.querySelector("h2"),"solar_lab",()=>"The week is cut into 3-hour windows on NOAA's Kp grid. Each window gets its Kp, peak X-ray flux, flare count and the number of M2.5+ and M4.5+ quakes from USGS, and every refresh (plus a background pass every 30 minutes) saves the windows to solar_seismic.db so the record keeps growing past USGS's 7-day feed. Pearson (linear) and Spearman (rank) correlations and storm vs. quiet quake rates are computed from those windows. A 'storm window' is Kp ≥ 5− (4.67), NOAA's G1 threshold. These are observed patterns, not significance tests.");}
 // controls
 $("ss_view").onclick=e=>{const b=e.target.closest("button");if(!b)return;SS.view=b.dataset.v;$("ss_view").querySelectorAll("button").forEach(x=>x.classList.toggle("on",x==b));renderStats()};
 $("ss_m45").onchange=e=>{SS.m45=e.target.checked;renderMap()};$("ss_hist").onchange=e=>{SS.hist=e.target.checked;renderMap()};
 $("ss_achips").onclick=e=>{const b=e.target.closest("button");if(!b)return;SS.afilt=b.dataset.f;renderAlerts()};
 M.addEventListener("click",e=>{const b=e.target.closest("[data-ssmore]");if(!b)return;e.preventDefault();keepRoom();SS[b.dataset.ssmore]=!SS[b.dataset.ssmore];b.dataset.ssmore=="aall"?renderAlerts():renderQuakes()});
 SS.built=true}

// ---------- data ----------
async function load(force){if(SS.busy)return;SS.busy=true;const st=$("ss_status");if(st&&SS.d)st.insertAdjacentHTML("beforeend",`<span id=ss_ld>· refreshing…</span>`);
 try{const r=await fetch("api/solar_seismic"+(force?"?force=1":""),{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;SS.d=j;render()}
 catch(err){if(st)st.innerHTML=`<span class=bad>Solar &amp; Seismic data unavailable: ${e_(err)}</span>`}finally{SS.busy=false;const l=$("ss_ld");if(l)l.remove()}}
function render(){if(!SS.built)skeleton();const D=SS.d;
 const ok=D.sources.filter(s=>s.ok).length,n=D.sources.length,stale=D.sources.filter(s=>!s.ok&&s.has_data).length;
 $("ss_status").innerHTML=`<span><span class="ss-dot ${ok==n?"":ok>=n-2?"warn":"bad"}"></span>${ok}/${n} live sources OK${stale?` · ${stale} showing cached data`:""}</span><span>Updated ${e_(D.generated_et)}</span><span>Upstream data refreshes at most every 5 min · next in ${Math.ceil(D.next_fetch_s/60)} min</span><span>Evidence log: <b>${D.log.bins}</b> windows since ${e_(etF(D.log.since))}</span>`;
 renderTiles();renderAlerts();renderQuakes();renderExtra();renderLab();if(SS.shown)drawLab()}
const spark=(vals,col,o={})=>{const v=vals.filter(x=>x!=null);if(v.length<2)return"";const mn=o.min??Math.min(...v),mx=o.max??Math.max(...v),W=200,H=30,sp=mx-mn||1;
 const pts=vals.map((x,i)=>x==null?null:[(i/(vals.length-1))*W,H-2-((x-mn)/sp)*(H-4)]);let d="",pen=false;pts.forEach(p=>{if(!p){pen=false;return}d+=(pen?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1);pen=true});
 const z=o.zero!=null&&mn<o.zero&&mx>o.zero?`<path d="M0 ${(H-2-((o.zero-mn)/sp)*(H-4)).toFixed(1)} H${W}" stroke="#5a6472" stroke-dasharray="3 3"/>`:"";
 return `<svg class=spark viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${z}<path d="${d}" fill="none" stroke="${col}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`};
const SRC=k=>(SS.d.sources.find(s=>s.key==k)||{}).url;
const raw=(k,l="raw ↗")=>`<a href="${U(SRC(k))}" target=_blank rel="noopener noreferrer">${l}</a>`;
function renderTiles(){const D=SS.d,N=D.now,k=N.kp,sc=N.scales,w=N.wind,q=N.quake;
 const kb=D.bins.slice(-8).map(b=>`<rect x="${D.bins.slice(-8).indexOf(b)*25}" y="${30-(b.kp||0)/9*28}" width="20" height="${(b.kp||0)/9*28}" fill="${KPC(b.kp)}" rx="1.5"/>`).join("");
 const T=[];
 T.push(`<div class=ss-tile><div class=lab><span>Planetary Kp</span>${raw("kp")}</div><div class=val style="color:${KPC(k.value)}">${kpTxt(k.value)}<small>${GLAB[gOf(k.value)]}</small></div>
  <div class=sub>3-hour index to ${e_(k.t_et||"—")} · 1-min estimate now <b>${k.est!=null?k.est.toFixed(2):"—"}</b></div><svg class=spark viewBox="0 0 200 30" preserveAspectRatio="none">${kb}</svg>
  <div class=sub2>24 h max ${kpTxt(k.max24)} · 7-day max ${kpTxt(k.max7)}</div>
  ${acc("t_kp","What this means",`Kp 0–3 is quiet, 4 is active, and 5 or more (G1+) is a geomagnetic storm. Storm conditions mean grid operators watch for induced currents, HF radio and GPS degrade at high latitudes, and aurora moves toward the equator. Low-latitude places (around 30° N/S) usually need Kp 8–9 to see aurora. Bars: the last 24 hours, 3 hours each.`)}</div>`);
 const sn=sc.now,sm=sc.max24;
 T.push(`<div class=ss-tile><div class=lab><span>NOAA scales now</span>${raw("scales")}</div><div class=val>${pill("R",sn.R)}${pill("S",sn.S)}${pill("G",sn.G)}</div>
  <div class=sub>Past 24 h max: ${pill("R",sm.R)}${pill("S",sm.S)}${pill("G",sm.G)}</div>
  <div class=sub2>${sc.forecast.map(f=>`${e_(f.date?f.date.slice(5):"")}: G${f.G??"–"} · R1–2 ${f.R_minor??"–"}% · S1 ${f.S_prob??"–"}%`).join("<br>")}</div>
  ${acc("t_sc","What this means",`<b>R</b> = radio blackouts from flare X-rays, <b>S</b> = solar radiation (energetic protons) storms, <b>G</b> = geomagnetic storms. Each runs 1 (minor) to 5 (extreme), and 0 means none. The three lines are NOAA's forecast for the next three days: the expected G level and the chance of R1–R2 blackouts and S1+ radiation storms.`)}</div>`);
 const fl=N.flare;
 T.push(`<div class=ss-tile><div class=lab><span>GOES X-ray / flares</span>${raw("xray")}</div><div class=val style="color:var(--sol2)">${e_(N.xray.class||"—")}<small>now</small></div>
  <div class=sub>Latest flare: <b>${e_(fl.latest?fl.latest.class:"none")}</b>${fl.latest?` at ${e_(fl.latest.t_et)}`:""}</div>${spark(D.bins.map(b=>b.xray_max?Math.log10(b.xray_max):null),"#ffd666")}
  <div class=sub2>7 days: biggest ${e_(fl.biggest?fl.biggest.class:"—")}${fl.biggest?` (${e_(fl.biggest.t_et)})`:""} · ${fl.count.X} X · ${fl.count.M} M · ${fl.count.C} C · ${fl.count.B} B</div>
  ${acc("t_xr","What this means",`The current 0.1–0.8 nm X-ray flux, expressed as a flare class. M1 or above triggers an R1 radio blackout on the sunlit side of Earth; X-class flares cause wide HF outages. The line shows the peak flux in each 3-hour window over the past week (log scale). Flare list: ${raw("flares","GOES flare list ↗")}.`)}</div>`);
 const ws=D.wind24.map(r=>r.proton_speed),bz=D.mag24.map(r=>r.bz_gsm);
 T.push(`<div class=ss-tile><div class=lab><span>Solar wind at L1</span>${raw("wind_now")}</div><div class=val>${w.speed!=null?Math.round(w.speed):"—"}<small>km/s</small></div>
  <div class=sub>Density ${w.density!=null?w.density.toFixed(1):"—"} p/cm³ · ${w.speed>=600?"fast stream":w.speed>=450?"elevated":"slow/ambient"}</div>${spark(ws,"#ffd666")}<div class=sub2>24 h: ${ws.filter(x=>x).length?Math.round(Math.min(...ws.filter(x=>x)))+"–"+Math.round(Math.max(...ws.filter(x=>x)))+" km/s":"—"} · ${e_(w.t_et||"")} · ${raw("wind1m","1-min ↗")}</div>
  ${acc("t_sw","What this means",`Typical wind is 300–450 km/s. Sustained 600+ km/s (a coronal-hole stream or a CME passing) carries much more energy into the magnetosphere, especially when Bz is southward. At this speed the wind takes about ${w.speed?Math.round(1.5e6/w.speed/60):"—"} minutes to travel from L1 to Earth.`)}</div>`);
 T.push(`<div class="ss-tile ${w.bz!=null&&w.bz<=-10?"hi":""}"><div class=lab><span>Magnetic field Bt / Bz</span>${raw("mag_now")}</div><div class=val style="color:${w.bz==null?"inherit":w.bz<=-10?"var(--hi)":w.bz<0?"var(--md)":"var(--lo)"}">${w.bz!=null?(w.bz>0?"+":"")+w.bz:"—"}<small>nT Bz · Bt ${w.bt??"—"}</small></div>
  <div class=sub>${w.bz==null?"no data":w.bz<=-10?"strongly south: the door is open":w.bz<0?"southward: some coupling":"northward: mostly shielded"}</div>${spark(bz,"#ff7a45",{zero:0})}<div class=sub2>24 h Bz range ${bz.filter(x=>x!=null).length?Math.min(...bz.filter(x=>x!=null)).toFixed(1)+" to "+Math.max(...bz.filter(x=>x!=null)).toFixed(1):"—"} nT · ${raw("mag1m","1-min ↗")}</div>
  ${acc("t_bz","What this means",`Bt is the total strength of the interplanetary magnetic field and Bz its north–south part (GSM coordinates). Negative (southward) Bz lets the field reconnect with Earth's and pour energy in; −10 nT or lower held for hours with fast wind is the classic storm setup. The dashed line on the chart is zero.`)}</div>`);
 const L=q.latest,B=q.biggest;
 T.push(`<div class="ss-tile qk"><div class=lab><span>Latest notable quake</span>${raw("eq")}</div><div class=val style="color:var(--qk)">${L?"M"+L.mag:"—"}<small>${L?e_(L.t_et):""}</small></div>
  <div class=sub>${L?`<a href="${U(L.url)}" target=_blank rel="noopener noreferrer">${e_(L.place)}</a>`:"none"}</div>
  <div class=sub2>7 days: <b>${q.count}</b> M2.5+ · <b>${q.m45}</b> M4.5+ · biggest ${B?`<a href="${U(B.url)}" target=_blank rel="noopener noreferrer">M${B.mag} ${e_(B.place)}</a>`:"—"}</div>
  ${acc("t_q","What this means",`The USGS lists every quake of M2.5 or more worldwide, with best coverage in the US; outside the US the global list is only complete from about M4.5. "Notable" means the latest M4.5+ or USGS-significant event. Magnitude is logarithmic: each whole step is about 32× more energy.`)}</div>`);
 const ts=N.tsunami||[];
 T.push(`<div class="ss-tile ${ts.some(x=>/warning|advisory/i.test(x.category||""))?"hi":"qk"}"><div class=lab><span>Tsunami bulletins</span><a href="https://www.tsunami.gov/" target=_blank rel="noopener noreferrer">tsunami.gov ↗</a></div><div class=val style="color:#5cdbd3">${q.tsunami_flagged}<small>USGS tsunami flags (7 d)</small></div>
  ${ts.map(x=>x.error?`<div class=sub2>${x.center=="tsu_ntwc"?"NTWC":"PTWC"}: feed unreadable</div>`:`<div class=sub><b>${x.center=="tsu_ntwc"?"NTWC Alaska":"PTWC Hawaii"}</b>: ${e_(x.category||"")} · ${e_(x.region||x.title||"")}${x.mag?` · M${x.mag}`:""}</div><div class=sub2>${e_(x.t_et||"")} · <a href="${U(x.bulletin||x.feed)}" target=_blank rel="noopener noreferrer">bulletin ↗</a> · ${raw(x.center,"feed ↗")}</div>`).join("")}
  ${acc("t_ts","What this means",`USGS sets its "tsunami" flag on large quakes in oceanic regions. It means "check tsunami.gov", not that a tsunami happened. The official word comes from NOAA's two warning centers; their latest bulletin is shown, and an "Information" statement means no threat. For US Atlantic and Gulf coasts the National Tsunami Warning Center is the authority; elsewhere, follow your national warning centre.`)}</div>`);
 $("ss_tiles").innerHTML=T.join("")}
const KIND=[["all","All"],["Alert","Alerts"],["Warning","Warnings"],["Watch","Watches"],["Summary","Summaries"]];
function renderAlerts(){const A=SS.d.alerts,wk=Date.now()-7*864e5;const A7=A.filter(a=>a.t&&new Date(a.t)>=wk);
 const f=SS.afilt,L=A7.filter(a=>f=="all"||a.kind.includes(f));
 $("ss_acount").textContent=`· ${A7.length} in 7 days · ${SS.d.log.alerts} logged`;
 $("ss_achips").innerHTML=KIND.map(([k,l])=>`<button class="${k==f?"on":""}" data-f="${k}">${l} <span class=meta>${k=="all"?A7.length:A7.filter(a=>a.kind.includes(k)).length}</span></button>`).join("");
 const show=SS.aall?L:L.slice(0,10);
 $("ss_alerts").innerHTML=show.map(a=>acc("a_"+a.id,`${a.scale?pill(a.scale[0],a.scale[1]):`<span class=pill>${e_(a.kind)}</span>`} <b>${e_(a.head)}</b><small>${e_(a.t_et)} · ${e_(a.product_id)}${a.bot?' · <span class="pill bot">✓ bot captured</span>':""}</small>`,
  `<pre class=ss-msg>${e_(a.message)}</pre><div class=ss-links><a href="${U(SRC("alerts"))}" target=_blank rel="noopener noreferrer">raw alerts.json ↗</a><a href="https://www.swpc.noaa.gov/products/alerts-watches-and-warnings" target=_blank rel="noopener noreferrer">SWPC alerts page ↗</a>${a.bot?"<span>also logged by the bot's scanner (The Wire / Watchlist)</span>":""}</div>`,
  {cls:a.level>=3?"hi":"sol"})).join("")||"<div class=meta>No alerts in this category in the past 7 days.</div>";
 if(L.length>10)$("ss_alerts").insertAdjacentHTML("beforeend",`<button class=ss-more data-ssmore=aall>${SS.aall?"Show fewer":`Show all ${L.length}`}</button>`)}
function qHead(q){return `<span class="pill qk">M${q.mag}</span> <b>${e_(q.place)}</b>${q.tsunami?' <span class="pill ts">🌊 tsunami flag</span>':""}${q.alert?` <span class="pill ${e_(q.alert)}">PAGER ${e_(q.alert)}</span>`:""}${q.storm?' <span class="pill s3">storm window</span>':""}${q.bot?` <span class="pill bot">✓ bot rank ${q.bot.rank??"–"}</span>`:""}<small>${e_(q.t_et)} · depth ${q.depth!=null?Math.round(q.depth):"–"} km · Kp at the time ${kpTxt(q.kp)}</small>`}
function qBody(q){return `<table class=ss-tb><tr><td>Time</td><td>${e_(q.t_et)} · ${e_(q.t)}</td></tr><tr><td>Magnitude</td><td>${q.mag} ${e_(q.magType||"")} · ${e_(q.status||"")}</td></tr><tr><td>Location</td><td>${q.lat!=null?q.lat.toFixed(2)+", "+q.lon.toFixed(2):"–"} · depth ${q.depth!=null?q.depth.toFixed(1):"–"} km</td></tr>
 <tr><td>Felt reports</td><td>${q.felt??0}</td></tr><tr><td>Geomagnetic context</td><td>Kp ${kpTxt(q.kp)} in that 3-hour window: ${q.storm?"<b style='color:var(--hi)'>storm window (G1+)</b>":q.kp>=3.67?"active, below storm level":"quiet"}</td></tr>
 ${q.tsunami?`<tr><td>Tsunami</td><td>USGS flag set. Check <a href="https://www.tsunami.gov/" target=_blank rel="noopener noreferrer">tsunami.gov</a> for official bulletins.</td></tr>`:""}${q.bot?`<tr><td>Bot</td><td>Captured by the scanner: rank ${q.bot.rank??"–"}/10, score ${q.bot.score??"–"}</td></tr>`:""}</table>
 <div class=ss-links><a href="${U(q.url)}" target=_blank rel="noopener noreferrer">USGS event page ↗</a><a href="${U(q.detail)}" target=_blank rel="noopener noreferrer">raw GeoJSON ↗</a></div>`}
function renderQuakes(){const Q=SS.d.quakes_notable;$("ss_qcount").textContent=`· ${Q.length} shown of ${SS.d.now.quake.count} M2.5+`;
 const show=SS.qall?Q:Q.slice(0,10);
 $("ss_quakes").innerHTML=show.map(q=>acc("q_"+q.id,qHead(q),qBody(q),{cls:q.storm||q.mag>=6.5?"hi":"qk"})).join("")||"<div class=meta>No notable quakes this week.</div>";
 if(Q.length>10)$("ss_quakes").insertAdjacentHTML("beforeend",`<button class=ss-more data-ssmore=qall>${SS.qall?"Show fewer":`Show all ${Q.length}`}</button>`)}
function renderExtra(){const D=SS.d,c=D.scanner.counts||{};
 const rows=D.sources.map(s=>`<tr><td><a href="${U(s.url)}" target=_blank rel="noopener noreferrer">${e_(s.name)}</a>${s.error?`<div class=meta>${e_(s.error)}</div>`:""}</td><td class="${s.ok?"ok":s.has_data?"dis":"bad"}">${s.ok?"✓ live":s.has_data?"cached":"✗ down"}</td><td>${ago(s.age_s)}</td><td class=n>${s.ms??"–"} ms</td><td class=n>${s.ok24}/${s.fetches24}</td></tr>`).join("");
 const sh=(D.scanner.health||[]).map(h=>`<tr><td>${e_(h.name)}</td><td class="${h.ok?"ok":"bad"}">${h.ok?"✓":"✗"}</td><td>${e_(h.checked_et||"")}</td><td class=n>${h.items??"–"}</td></tr>`).join("");
 $("ss_extra").innerHTML=acc("x_wind","<b>Solar wind &amp; magnetic field, last 24 hours</b><small>1-minute real-time data from L1, averaged to 10 minutes</small>",`<div class=ss-legend><span><i style="background:#ffd666"></i>speed (km/s, left)</span><span><i style="background:#ff7a45"></i>Bz (nT, right)</span><span><i style="background:var(--bn-muted,#8b95a3)"></i>Bt (nT, right)</span></div><div class="ss-chart c"><canvas data-lazy=wind id=ss_cw></canvas></div>`,{cls:"sol",ic:"🌬"})
 +acc("x_src",`<b>Data sources &amp; live status</b><small>${D.sources.filter(s=>s.ok).length}/${D.sources.length} live · plus what the bot's scanner already captured</small>`,`<table class=ss-tb><tr><th>Source (raw link)</th><th>Status</th><th>Fetched</th><th class=n>Time</th><th class=n>OK fetches 24 h</th></tr>${rows}</table>
  <p><b>Bot's scanner (blackout.db, read-only):</b> ${c.swpc??"–"} NOAA SWPC items since ${e_(etF(c.swpc_since))} · ${c.usgs??"–"} USGS quakes since ${e_(etF(c.usgs_since))}. The scanner pulls the USGS significant/M4.5+ daily feeds and SWPC alerts every scan; this tab adds the full week, Kp, X-ray and solar-wind series.</p>
  ${sh?`<table class=ss-tb><tr><th>Scanner source</th><th>OK</th><th>Last checked</th><th class=n>Items</th></tr>${sh}</table>`:""}`,{cls:"mu",ic:"🛰"})}

// ---------- lab ----------
function renderLab(){const D=SS.d,L=D.log;
 $("ss_logline").innerHTML=`<br><b>${L.bins}</b> windows logged since ${e_(etF(L.since))} (covering back to ${e_(etF(L.first_bin))}) · ${L.quakes} quakes · ${L.storm_bins} storm windows · ${L.storm_quakes} quakes during storms · <a href="api/solar_seismic/bins.csv">windows CSV</a> · <a href="api/solar_seismic/quakes.csv">quakes CSV</a>`;
 $("ss_leg1").innerHTML=`<span><i style="background:#52c41a"></i>Kp &lt; 4 quiet</span><span><i style="background:#faad14"></i>Kp 4 active</span><span><i style="background:#ff7a45"></i>G1</span><span><i style="background:#ff4d4f"></i>G2</span><span><i style="background:#d4380d"></i>G3+</span><span><i style="background:#3a4250"></i>estimate (window still open)</span><span><i style="background:#ffd666;height:3px"></i>peak X-ray flux (right, log scale)</span><span><i style="background:rgba(255,77,79,.18)"></i>storm window</span>`;
 $("ss_leg2").innerHTML=`<span><i style="background:rgba(74,163,255,.6)"></i>M2.5+ quakes per 3 h (left)</span><span><i style="background:var(--bn-text,#e6e9ee);height:3px"></i>M4.5+ per 3 h (right)</span>`;
 renderStats();
 const sq=D.map.filter(q=>q.storm),sb=D.bins.filter(b=>b.storm&&!b.partial).length;
 $("ss_stormmsg").innerHTML=sb?`<div class=ss-yesstorm><b>${sb}</b> storm window${sb>1?"s":""} (Kp ≥ 5) this week, with <b>${sq.length}</b> M2.5+ quake${sq.length==1?"":"s"} inside ${sb>1?"them":"it"}. They're highlighted in red with a pulsing ring.</div>`
  :`<div class=ss-nostorm><b>No geomagnetic storm windows (Kp ≥ 5) in the past 7 days</b>${D.now.kp.max7!=null?`: the week's highest Kp was ${kpTxt(D.now.kp.max7)}`:""}. So no quakes fell inside a storm window, and all ${D.map.length} M2.5+ quakes are shown in blue. When a storm hits, quakes during it turn red here automatically${D.now.scales.forecast.some(f=>+f.G>0)?`. NOAA currently forecasts up to G${Math.max(...D.now.scales.forecast.map(f=>+f.G||0))} in the next 3 days`:""}.</div>`;
 $("ss_mapmeta").textContent=`· ${D.map.length} M2.5+ quakes this week${D.map_hist.length?` · ${D.map_hist.length} older in the log`:""}`}
const rFmt=r=>r==null?"n/a":(r>0?"+":"")+r.toFixed(2);
function rCard(t,r,rs,n,nz,note){const pos=r==null?50:50+r*50,w=nz?nz*50:0;
 const words=r==null?"Not enough variation to compute yet.":Math.abs(r)<nz?`Within the range random noise produces with ${n} windows (±${nz.toFixed(2)}): no pattern.`:`Outside the ±${nz.toFixed(2)} noise band: a ${r>0?"positive":"negative"} ${Math.abs(r)<.4?"weak":"moderate"} association worth watching. Windows aren't independent, so this is still not significance.`;
 return `<div class=ss-stat><div class=k>${t}</div><div class=v>${rFmt(r)}<small>Pearson r (linear)</small></div><div class=k>Spearman ρ (rank-based): <b style="color:var(--tx)">${rFmt(rs)}</b></div><div class=ss-rbar title="−1 … 0 … +1; the grey band is the ±noise range for this many windows"><div class=nz style="left:${50-w}%;width:${2*w}%"></div><div class=mid></div>${r!=null?`<div class=pt style="left:${pos}%"></div>`:""}</div><div class=why>${words}${note?` ${note}`:""}</div></div>`}
function renderStats(){const S=SS.d.stats[SS.view];if(!S)return;const nz=S.noise_r||0;
 $("ss_stats").innerHTML=`<div class=ss-stat><div class=k>Sample (${e_(S.label)})</div><div class=v>${S.n}<small>3-hour windows</small></div><div class=why>${e_(etF(S.from))} → ${e_(etF(S.to))}. ${S.storm.bins} storm windows, ${S.active.bins} active, ${S.quiet.bins} quiet. Only closed windows with a final Kp count.</div></div>`
  +rCard("Kp vs. M2.5+ quake count",S.pearson_kp_q25,S.spearman_kp_q25,S.n,nz)+rCard("Kp vs. M4.5+ quake count",S.pearson_kp_q45,S.spearman_kp_q45,S.n,nz)+rCard("Peak X-ray flux (log) vs. M2.5+ count",S.pearson_xray_q25,S.spearman_xray_q25,S.n,nz,"Flares mainly affect the dayside ionosphere, so a link here would be even more surprising.");
 const row=(l,g)=>`<tr><td>${l}</td><td class=n>${g.bins}</td><td class=n>${g.hours}</td><td class=n>${g.q25}</td><td class=n><b>${g.rate25??"—"}</b></td><td class=n>${g.q45}</td><td class=n><b>${g.rate45??"—"}</b></td></tr>`;
 $("ss_rates").innerHTML=`<table class=ss-tb><tr><th>Geomagnetic state of the window</th><th class=n>Windows</th><th class=n>Hours</th><th class=n>M2.5+ quakes</th><th class=n>per 3 h</th><th class=n>M4.5+ quakes</th><th class=n>per 3 h</th></tr>
  ${row("Quiet (Kp &lt; 4)",S.quiet)}${row("Active (Kp 4)",S.active)}${row("<b style='color:var(--hi)'>Storm (Kp ≥ 5, G1+)</b>",S.storm)}${row("All non-storm",S.nonstorm)}</table>
  <div class=ss-hint>${S.ratio25!=null?`Storm-window quake rate is <b>${S.ratio25}×</b> the non-storm rate for M2.5+ and <b>${S.ratio45??"—"}×</b> for M4.5+ (1.0× = no difference).`:`No storm windows in this sample yet, so a storm vs. non-storm rate can't be compared. The comparison fills in automatically as storms are logged.`}</div>`;
 $("ss_cav").innerHTML=`<b>Read this before drawing conclusions.</b> ${S.n} windows is a small sample, and these numbers are descriptive, not a significance test. Earthquakes cluster (aftershocks), so windows aren't independent. Big quakes are rare, and storms rarer. USGS's worldwide list is only complete from about M4.5; smaller quakes are mostly US-based. Checking several measures and time lags will turn up some "hits" by chance alone. A real effect would have to show up consistently, in the M4.5+ counts, over many storms and months of logging. That is exactly the record this lab is building.`;
 $("ss_labacc").innerHTML=acc("l_lag",`<b>Time-lag check</b><small>Does Kp line up with quakes 0–24 hours later? (${e_(S.label)})</small>`,`<div class="ss-chart c"><canvas data-lazy=lag id=ss_cl></canvas></div><div class=ss-hint>Each bar is the Pearson r between Kp in a window and the M2.5+ count 0, 3, 6 … 24 hours later. Dashed lines mark the ±${nz.toFixed(2)} noise band. With 9 lags tested, about 1 in 20 bars poking past the band is expected by chance, so a single tall bar means little.</div>`,{cls:"sol",ic:"⏱"})
  +acc("l_log",`<b>Evidence log</b><small>The latest 3-hour windows saved to solar_seismic.db · ${SS.d.log.bins} total</small>`,logTable(),{cls:"mu",ic:"🗂"});
 if(SS.charts.lag)drawLag()}
function logTable(){const B=SS.d.bins.slice(-16).reverse();return `<table class=ss-tb><tr><th>Window (ET)</th><th class=n>Kp</th><th class=n>Peak X-ray</th><th class=n>Flares C/M/X</th><th class=n>M2.5+</th><th class=n>M4.5+</th><th class=n>Max M</th><th>State</th></tr>
 ${B.map(b=>`<tr><td>${e_(b.label)}</td><td class=n style="color:${KPC(b.kp)}">${kpTxt(b.kp)}${b.kp_est?"*":""}</td><td class=n>${xcls(b.xray_max)}</td><td class=n>${b.flares_c}/${b.flares_m}/${b.flares_x}</td><td class=n>${b.q25}</td><td class=n>${b.q45}</td><td class=n>${b.max_mag??"–"}</td><td>${b.partial?"<span class=meta>open</span>":b.storm?"<b style='color:var(--hi)'>storm</b>":b.kp>=3.67?"active":"quiet"}</td></tr>`).join("")}</table>
 <div class=ss-hint>* = estimated from 1-minute Kp while the window is still open; the final value replaces it. Download everything: <a href="api/solar_seismic/bins.csv">windows CSV</a> · <a href="api/solar_seismic/quakes.csv">quakes CSV</a>.</div>`}
const fixW={id:"ssfix",afterFit:s=>{s.width=58}};
const bandPlugin={id:"ssband",beforeDatasetsDraw(c){const B=SS.d&&SS.d.bins;if(!B)return;const x=c.scales.x,a=c.chartArea,g=c.ctx;g.save();
 B.forEach((b,i)=>{if(!(b.storm||(SS.sel===i)))return;const w=(x.getPixelForValue(1)-x.getPixelForValue(0))||8;const px=x.getPixelForValue(i)-w/2;g.fillStyle=SS.sel===i?"rgba(255,214,102,.16)":"rgba(255,77,79,.18)";g.fillRect(px,a.top,w,a.bottom-a.top)});g.restore()}};
function drawLab(){if(!SS.d||typeof Chart=="undefined")return;const B=SS.d.bins,lab=B.map(b=>etS(b.bin_start));
 const tick={color:"#8b95a3",maxRotation:0,autoSkip:true,maxTicksLimit:14,font:{size:10.5}},grid={color:"#1f252d"};
 const tip={mode:"index",intersect:false,callbacks:{title:it=>B[it[0].dataIndex].label+" (3 h)",afterBody:it=>{const b=B[it[0].dataIndex];return[`Flares C/M/X: ${b.flares_c}/${b.flares_m}/${b.flares_x}`,`Max quake: ${b.max_mag??"–"}`,b.partial?"window still open":""]}}};
 const onClick=(ev,el)=>{if(el&&el.length)selBin(el[0].index)};
 const ds1=[{type:"bar",label:"Kp",data:B.map(b=>b.kp),backgroundColor:B.map(b=>b.kp_est?"#3a4250":KPC(b.kp)),yAxisID:"y",order:2,barPercentage:.92,categoryPercentage:.95},
  {type:"line",label:"Peak X-ray (W/m²)",data:B.map(b=>b.xray_max),borderColor:"#ffd666",backgroundColor:"#ffd666",borderWidth:1.6,pointRadius:0,pointHoverRadius:3,yAxisID:"x2",order:1,tension:.25,spanGaps:true}];
 const o1={responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},onClick,plugins:{legend:{display:false},tooltip:{...tip,callbacks:{...tip.callbacks,label:c=>c.dataset.label=="Kp"?`Kp ${kpTxt(c.raw)}${B[c.dataIndex].kp_est?" (estimate)":""}`:`X-ray ${xcls(c.raw)}`}}},
  scales:{x:{ticks:tick,grid},y:{min:0,max:9,ticks:{color:"#8b95a3",stepSize:1},grid,title:{display:true,text:"Kp",color:"#8b95a3"},afterFit:fixW.afterFit},
  x2:{type:"logarithmic",position:"right",min:1e-8,max:1e-3,grid:{display:false},ticks:{color:"#ffd666",callback:v=>({1e-8:"A",1e-7:"B",1e-6:"C",1e-5:"M",1e-4:"X"})[v]||""},afterBuildTicks:a=>{a.ticks=[1e-8,1e-7,1e-6,1e-5,1e-4,1e-3].map(v=>({value:v}))},afterFit:fixW.afterFit}}};
 const ds2=[{type:"bar",label:"M2.5+",data:B.map(b=>b.q25),backgroundColor:B.map(b=>b.storm?"rgba(255,77,79,.75)":"rgba(74,163,255,.6)"),yAxisID:"y",order:2,barPercentage:.92,categoryPercentage:.95},
  {type:"line",label:"M4.5+",data:B.map(b=>b.q45),borderColor:"#e6e9ee",backgroundColor:"#e6e9ee",borderWidth:1.4,pointRadius:1.5,yAxisID:"y2",order:1,tension:.2}];
 const mx=Math.max(4,...B.map(b=>b.q25));
 const o2={responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},onClick,plugins:{legend:{display:false},tooltip:{...tip,callbacks:{...tip.callbacks,label:c=>`${c.dataset.label}: ${c.raw} quake${c.raw==1?"":"s"}`}}},
  scales:{x:{ticks:tick,grid},y:{min:0,suggestedMax:mx,ticks:{color:"#8b95a3",precision:0},grid,title:{display:true,text:"quakes / 3 h",color:"#8b95a3"},afterFit:fixW.afterFit},y2:{position:"right",min:0,suggestedMax:Math.max(3,...B.map(b=>b.q45)),grid:{display:false},ticks:{color:"#e6e9ee",precision:0},afterFit:fixW.afterFit}}};
 const mk=(id,key,ds,o)=>{const c=SS.charts[key];if(c){c.data.labels=lab;c.data.datasets=ds;c.options=o;c.update();return}SS.charts[key]=new Chart($(id),{data:{labels:lab,datasets:ds},options:o,plugins:[bandPlugin]})};
 mk("ss_c1","c1",ds1,o1);mk("ss_c2","c2",ds2,o2);
 // mirror hover between the two charts (shared time axis)
 const sync=(a,b)=>{$(a).onmousemove=ev=>{const s=SS.charts[a=="ss_c1"?"c1":"c2"],t=SS.charts[a=="ss_c1"?"c2":"c1"];const el=s.getElementsAtEventForMode(ev,"index",{intersect:false},false);if(!el.length)return;const i=el[0].index;
  t.setActiveElements(t.data.datasets.map((d,k)=>({datasetIndex:k,index:i})));t.tooltip.setActiveElements(t.data.datasets.map((d,k)=>({datasetIndex:k,index:i})),{x:0,y:0});t.update("none")};
  $(a).onmouseleave=()=>{const t=SS.charts[a=="ss_c1"?"c2":"c1"];t.setActiveElements([]);t.tooltip.setActiveElements([],{x:0,y:0});t.update("none")}};
 sync("ss_c1");sync("ss_c2");
 if(SS.charts.wind)drawWind();if(SS.charts.lag)drawLag();renderMap()}
function lazyChart(k){if(k=="wind")drawWind();if(k=="lag")drawLag()}
function drawWind(){const W=SS.d.wind24,G=SS.d.mag24,el=$("ss_cw");if(!el)return;const lab=W.map(r=>r.t);const gm={};G.forEach(r=>gm[r.t]=r);
 const ds=[{type:"line",label:"Speed",data:W.map(r=>r.proton_speed),borderColor:"#ffd666",borderWidth:1.5,pointRadius:0,yAxisID:"y",spanGaps:true},
  {type:"line",label:"Bz",data:lab.map(t=>(gm[t]||{}).bz_gsm??null),borderColor:"#ff7a45",borderWidth:1.3,pointRadius:0,yAxisID:"y2",spanGaps:true},
  {type:"line",label:"Bt",data:lab.map(t=>(gm[t]||{}).bt??null),borderColor:"#8b95a3",borderWidth:1.1,pointRadius:0,yAxisID:"y2",spanGaps:true,borderDash:[4,3]}];
 const o={responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},plugins:{legend:{display:false},tooltip:{callbacks:{title:it=>etF(lab[it[0].dataIndex])}}},
  scales:{x:{ticks:{color:"#8b95a3",maxTicksLimit:9,maxRotation:0,callback:(v,i)=>etS(lab[i])},grid:{color:"#1f252d"}},y:{ticks:{color:"#ffd666"},grid:{color:"#1f252d"},afterFit:fixW.afterFit},y2:{position:"right",ticks:{color:"#ff7a45"},grid:{display:false},afterFit:fixW.afterFit}}};
 const c=SS.charts.wind;if(c&&c.canvas==el){c.data.labels=lab;c.data.datasets=ds;c.update();return}if(c)c.destroy();SS.charts.wind=new Chart(el,{data:{labels:lab,datasets:ds},options:o})}
function drawLag(){const S=SS.d.stats[SS.view],el=$("ss_cl");if(!el||!S)return;const nz=S.noise_r||0;const lab=S.lags.map(l=>`+${l.lag_h} h`);
 const ds=[{type:"bar",label:"r",data:S.lags.map(l=>l.r),backgroundColor:S.lags.map(l=>l.r!=null&&Math.abs(l.r)>=nz?"#faad14":"#4aa3ff")},
  {type:"line",label:"+noise",data:S.lags.map(()=>nz),borderColor:"#5a6472",borderDash:[4,4],pointRadius:0,borderWidth:1},{type:"line",label:"−noise",data:S.lags.map(()=>-nz),borderColor:"#5a6472",borderDash:[4,4],pointRadius:0,borderWidth:1}];
 const o={responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false},tooltip:{filter:i=>i.datasetIndex==0,callbacks:{label:c=>`r = ${rFmt(c.raw)}`}}},scales:{x:{ticks:{color:"#8b95a3"},grid:{color:"#1f252d"}},y:{min:-1,max:1,ticks:{color:"#8b95a3",stepSize:.5},grid:{color:"#1f252d"},afterFit:fixW.afterFit}}};
 const c=SS.charts.lag;if(c&&c.canvas==el){c.data.labels=lab;c.data.datasets=ds;c.update();return}if(c)c.destroy();SS.charts.lag=new Chart(el,{data:{labels:lab,datasets:ds},options:o})}
function selBin(i){const b=SS.d.bins[i];if(!b)return;keepRoom();SS.sel=SS.sel===i?null:i;Object.values({a:SS.charts.c1,b:SS.charts.c2}).forEach(c=>c&&c.update("none"));
 if(SS.sel==null){$("ss_binbox").innerHTML="";return}
 const t0=new Date(b.bin_start),t1=new Date(+t0+3*36e5);const Q=SS.d.map.filter(q=>{const t=new Date(q.t);return t>=t0&&t<t1}).sort((a,b)=>b.mag-a.mag);const F=SS.d.flares.filter(f=>{const t=new Date(f.t);return t>=t0&&t<t1});
 $("ss_binbox").innerHTML=`<div class=ss-bin><b>${e_(b.label)} → ${e_(etF(t1).replace(/^\w+ \d+, /,""))}</b> · Kp <b style="color:${KPC(b.kp)}">${kpTxt(b.kp)}</b>${b.kp_est?" (estimate)":""} · ${b.storm?"<b style='color:var(--hi)'>storm window</b>":b.kp>=3.67?"active":"quiet"} · peak X-ray ${xcls(b.xray_max)} · ${b.q25} M2.5+ / ${b.q45} M4.5+ quakes <button class=ss-more id=ss_binx style="float:right;margin:0">✕ close</button>
 ${F.length?`<div class=ss-hint style="margin-top:4px">Flares: ${F.map(f=>`${e_(f.class)} at ${e_(f.t_et)}`).join(" · ")}</div>`:""}
 <div style="margin-top:6px">${Q.slice(0,12).map(q=>acc("bq_"+q.id,qHead(q),qBody(q),{cls:"qk"})).join("")||"<span class=meta>No M2.5+ quakes in this window.</span>"}${Q.length>12?`<div class=ss-hint>+${Q.length-12} smaller quakes (all are on the map)</div>`:""}</div></div>`;
 $("ss_binx").onclick=()=>selBin(i)}
function renderMap(){if(!SS.shown||typeof L=="undefined"||!SS.d)return;
 if(!SS.map){SS.map=L.map("ss_map",{worldCopyJump:true,scrollWheelZoom:false,minZoom:1}).setView([20,10],2);
  (window.bnBaseLayer?bnBaseLayer(SS.map,{maxZoom:12}):null)/* t252: shared keyless basemap (OpenFreeMap → VersaTiles → NASA GIBS); no OSM tile servers */;
  SS.lay=L.layerGroup().addTo(SS.map);SS.map.on("click",()=>SS.map.scrollWheelZoom.enable());SS.map.on("mouseout",()=>SS.map.scrollWheelZoom.disable())}
 SS.lay.clearLayers();let Q=SS.d.map.slice();if(SS.hist)Q=SS.d.map_hist.map(q=>({...q,t_et:etF(q.t),old:1})).concat(Q);if(SS.m45)Q=Q.filter(q=>q.mag>=4.5);
 Q.sort((a,b)=>(a.storm-b.storm)||(a.mag-b.mag));
 Q.forEach(q=>{if(q.lat==null)return;const r=3+Math.max(0,q.mag-2.5)*2.6;const col=q.storm?"#ff4d4f":q.old?"#8b95a3":"#4aa3ff";
  const m=L.circleMarker([q.lat,q.lon],{radius:r,color:q.tsunami?"#5cdbd3":col,weight:q.tsunami?2.5:q.storm?2:1,fillColor:col,fillOpacity:q.storm?.75:.45,className:q.storm?"ss-storm":""});
  m.bindPopup(`<b>M${q.mag} ${e_(q.place)}</b><br>${e_(q.t_et||etF(q.t))}<br>Depth ${q.depth!=null?Math.round(q.depth):"–"} km · Kp ${kpTxt(q.kp)}${q.storm?" · <b style='color:#c00'>storm window</b>":""}${q.tsunami?"<br>🌊 USGS tsunami flag":""}<br><a href="${U(q.url)}" target=_blank rel="noopener noreferrer">USGS event page ↗</a>`);m.addTo(SS.lay)});
 setTimeout(()=>SS.map.invalidateSize(),60)}

// ---------- tab wiring, refresh, CSV ----------
function onShow(){SS.shown=true;M.style.minHeight="";if(!SS.d)load().then(()=>drawLab());else{drawLab()}}
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(!b||!b.dataset.tab)return;if(b.dataset.tab=="solar_seismic")setTimeout(onShow,30);else{SS.shown=false}});
const rb=$("ss_ref");if(rb)rb.onclick=async e=>{e.stopPropagation();rb.disabled=true;rb.textContent="refreshing…";try{if($("refresh")&&$("refresh").onclick)await $("refresh").onclick()}catch(_){}
 await load(true);if(SS.shown)drawLab();rb.textContent="⟳ Refresh";rb.disabled=false};
setInterval(()=>{if(SS.shown&&!document.hidden)load().then(()=>{if(SS.shown)drawLab()})},300000);
load();
})();
