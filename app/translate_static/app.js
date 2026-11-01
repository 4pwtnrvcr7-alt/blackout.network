/* blackout.network site-wide translation (t397). The old offline Argos engine only runs on the scanner node, so on the public
   site (Render) picking a language translated nothing. Now: Google's free Website Translator is loaded on demand, only after a
   visitor picks a language (English visitors load nothing extra). The choice is saved in localStorage "bn_lang" plus the
   "googtrans" cookie, so every page opens already translated; dynamic content is translated as it appears. Google's banner,
   tooltips and highlight are hidden in app.css. Picking English clears the cookie and reloads the untouched English page.
   Picker: English first, then every language alphabetically by English name; it lives in the Settings popover and the footer. */
(()=>{
if(window.BNTR)return;
const L=[["af","Afrikaans","Afrikaans"],["sq","Shqip","Albanian"],["am","አማርኛ","Amharic"],["ar","العربية","Arabic"],["hy","Հայերեն","Armenian"],
["az","Azərbaycanca","Azerbaijani"],["eu","Euskara","Basque"],["be","Беларуская","Belarusian"],["bn","বাংলা","Bengali"],["bs","Bosanski","Bosnian"],
["bg","Български","Bulgarian"],["my","မြန်မာ","Burmese"],["ca","Català","Catalan"],["ceb","Cebuano","Cebuano"],["zh-CN","中文（简体）","Chinese (Simplified)"],
["zh-TW","中文（繁體）","Chinese (Traditional)"],["hr","Hrvatski","Croatian"],["cs","Čeština","Czech"],["da","Dansk","Danish"],["nl","Nederlands","Dutch"],
["eo","Esperanto","Esperanto"],["et","Eesti","Estonian"],["tl","Filipino","Filipino (Tagalog)"],["fi","Suomi","Finnish"],["fr","Français","French"],
["gl","Galego","Galician"],["ka","ქართული","Georgian"],["de","Deutsch","German"],["el","Ελληνικά","Greek"],["gu","ગુજરાતી","Gujarati"],
["ht","Kreyòl ayisyen","Haitian Creole"],["ha","Hausa","Hausa"],["iw","עברית","Hebrew"],["hi","हिन्दी","Hindi"],["hmn","Hmoob","Hmong"],
["hu","Magyar","Hungarian"],["is","Íslenska","Icelandic"],["ig","Igbo","Igbo"],["id","Bahasa Indonesia","Indonesian"],["ga","Gaeilge","Irish"],
["it","Italiano","Italian"],["ja","日本語","Japanese"],["jw","Basa Jawa","Javanese"],["kn","ಕನ್ನಡ","Kannada"],["kk","Қазақ","Kazakh"],
["km","ខ្មែរ","Khmer"],["rw","Kinyarwanda","Kinyarwanda"],["ko","한국어","Korean"],["ku","Kurdî","Kurdish"],["ky","Кыргызча","Kyrgyz"],
["lo","ລາວ","Lao"],["la","Latina","Latin"],["lv","Latviešu","Latvian"],["lt","Lietuvių","Lithuanian"],["mk","Македонски","Macedonian"],
["mg","Malagasy","Malagasy"],["ms","Bahasa Melayu","Malay"],["ml","മലയാളം","Malayalam"],["mt","Malti","Maltese"],["mi","Māori","Maori"],
["mr","मराठी","Marathi"],["mn","Монгол","Mongolian"],["ne","नेपाली","Nepali"],["no","Norsk","Norwegian"],["ps","پښتو","Pashto"],
["fa","فارسی","Persian"],["pl","Polski","Polish"],["pt","Português","Portuguese"],["pa","ਪੰਜਾਬੀ","Punjabi"],["ro","Română","Romanian"],
["ru","Русский","Russian"],["sm","Gagana Samoa","Samoan"],["sr","Српски","Serbian"],["sn","chiShona","Shona"],["sd","سنڌي","Sindhi"],
["si","සිංහල","Sinhala"],["sk","Slovenčina","Slovak"],["sl","Slovenščina","Slovenian"],["so","Soomaali","Somali"],["es","Español","Spanish"],
["su","Basa Sunda","Sundanese"],["sw","Kiswahili","Swahili"],["sv","Svenska","Swedish"],["tg","Тоҷикӣ","Tajik"],["ta","தமிழ்","Tamil"],
["te","తెలుగు","Telugu"],["th","ไทย","Thai"],["tr","Türkçe","Turkish"],["uk","Українська","Ukrainian"],["ur","اردو","Urdu"],
["uz","Oʻzbek","Uzbek"],["vi","Tiếng Việt","Vietnamese"],["cy","Cymraeg","Welsh"],["xh","isiXhosa","Xhosa"],["yi","ייִדיש","Yiddish"],
["yo","Yorùbá","Yoruba"],["zu","isiZulu","Zulu"]].sort((a,b)=>a[2].localeCompare(b[2]));
L.unshift(["en","English","English"]);
const CODES=new Set(L.map(x=>x[0]));
const OLD={zh:"zh-CN",zt:"zh-TW",pb:"pt",nb:"no",he:"iw"};        // codes saved by the old picker
const RTL=new Set(["ar","fa","iw","ur","ps","sd","yi"]);
const HTMLLANG={iw:"he",jw:"jv"};
const NOTE="Machine-translated by Google. The original English is authoritative.";
const getC=k=>(document.cookie.match("(?:^|; )"+k+"=([^;]*)")||[])[1];
const norm=l=>{l=OLD[l]||l||"en";return CODES.has(l)?l:"en"};
let lang="en";try{lang=localStorage.getItem("bn_lang")||getC("bn_lang")||"en"}catch(e){lang=getC("bn_lang")||"en"}lang=norm(lang);
function domains(){const h=location.hostname,p=h.split("."),out=["",h];if(p.length>=2&&!/^\d+$/.test(p[p.length-1]))out.push("."+p.slice(-2).join("."));return out}
function setCookies(l){const age=l=="en"?"max-age=0":"max-age=31536000";
 domains().forEach(d=>{document.cookie="googtrans="+(l=="en"?"":"/en/"+l)+";path=/;"+age+(d?";domain="+d:"")+";SameSite=Lax"});
 document.cookie="bn_lang="+l+";path=/;max-age=31536000;SameSite=Lax"}
function persist(l){try{localStorage.setItem("bn_lang",l)}catch(e){}setCookies(l)}
// keep the cookie in step with the saved choice (e.g. a visitor who picked a language before this version)
if(lang!="en"&&getC("googtrans")!=="/en/"+lang)setCookies(lang);
if(lang=="en"&&getC("googtrans"))setCookies("en");
let loading=false;
function protect(root){(root||document).querySelectorAll(".bn-word,.bn-logo,#bntr_bar,.bntr-foot,code,pre,kbd,.maplibregl-ctrl-attrib,.leaflet-control-attribution,.maplibregl-canvas-container,.leaflet-tile-pane").forEach(e=>{if(!e.classList.contains("notranslate"))e.classList.add("notranslate")})}
function load(){protect();if(window.google&&google.translate&&google.translate.TranslateElement){drive(0);return}if(loading)return;loading=true;
 let el=document.getElementById("bn_gt_el");if(!el){el=document.createElement("div");el.id="bn_gt_el";el.className="notranslate";el.setAttribute("aria-hidden","true");document.body.appendChild(el)}
 window.bnGtInit=()=>{try{new google.translate.TranslateElement({pageLanguage:"en",autoDisplay:false},"bn_gt_el")}catch(e){}drive(0)};
 const s=document.createElement("script");s.src="https://translate.google.com/translate_a/element.js?cb=bnGtInit";s.async=true;
 s.onerror=()=>{loading=false;status("⚠ translation service unreachable")};document.head.appendChild(s)}
function drive(n){if(lang=="en")return;const c=document.querySelector("select.goog-te-combo");
 if(!c||![].some.call(c.options,o=>o.value==lang)){if(n<60)setTimeout(()=>drive(n+1),250);return}
 if(c.value!==lang){c.value=lang;c.dispatchEvent(new Event("change"))}status("")}
function setLang(l){l=norm(l);if(l===lang)return;const was=lang;lang=l;persist(l);refresh();
 if(l=="en"){if(was!="en")location.reload();return}load()}
function opts(){return L.map(x=>`<option value="${x[0]}"${x[0]==lang?" selected":""}>${x[1]}${x[0]!="en"&&x[1]!=x[2]?" · "+x[2]:""}</option>`).join("")}
function picker(id){const s=document.createElement("select");s.id=id;s.className="bntr-sel notranslate";s.setAttribute("translate","no");
 s.setAttribute("aria-label","Language / Idioma / Langue / اللغة / 语言");s.innerHTML=opts();s.onchange=()=>setLang(s.value);return s}
function status(t){const s=document.getElementById("bntr_status");if(s)s.textContent=t||""}
function ui(){if(document.getElementById("bntr_bar"))return;
 const bar=document.createElement("span");bar.id="bntr_bar";bar.className="notranslate";bar.setAttribute("translate","no");
 bar.innerHTML='<span class="bntr-globe" aria-hidden="true">🌐</span><span class="bntr-lbl">Language</span>';bar.appendChild(picker("bntr_lang"));
 const st=document.createElement("span");st.id="bntr_status";st.className="bntr-st";bar.appendChild(st);
 const note=document.createElement("span");note.id="bntr_note";note.textContent=NOTE;bar.appendChild(note);
 const host=document.querySelector("#bn_settings .ctl")||document.querySelector("header .ctl");
 if(host)host.appendChild(bar);else{bar.classList.add("bntr-float");document.body.appendChild(bar)}
 const f=document.getElementById("site_foot")||document.querySelector("body>footer")||document.querySelector("footer");
 if(f&&!f.querySelector(".bntr-foot")){const w=document.createElement("span");w.className="bntr-foot notranslate";w.setAttribute("translate","no");w.append(" · 🌐 ",picker("bntr_lang_f"));f.appendChild(w)}
 refresh()}
function refresh(){document.querySelectorAll(".bntr-sel").forEach(s=>{if(s.value!==lang)s.value=lang});
 const R=document.documentElement;R.dir=RTL.has(lang)?"rtl":"ltr";R.lang=lang=="en"?"en":(HTMLLANG[lang]||lang);R.classList.toggle("bn-tr",lang!="en");
 const n=document.getElementById("bntr_note");if(n)n.hidden=lang=="en"}
function init(){ui();if(lang!="en"){status("translating…");load();
  let t=0;new MutationObserver(()=>{clearTimeout(t);t=setTimeout(protect,400)}).observe(document.body,{childList:true,subtree:true})}}
window.BNTR={setLang,get lang(){return lang},engine:"google",busy:0,get showOriginal(){return false},orig:el=>el?el.textContent:"",rescan:()=>{},langs:L};
if(document.readyState=="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
