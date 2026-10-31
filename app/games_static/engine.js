// Blackout Network: Games tab engine. Original code; HTML5 Canvas + WebAudio only, no external assets, no emulators.
// Each game registers {id,name,inspired,cats,desc,controls,w,h,init,update,draw,key,keyup,click,modes,best}.
(()=>{"use strict";
const PAL=["#000000","#1d2b53","#7e2553","#008751","#ab5236","#5f574f","#c2c3c7","#fff1e8","#ff004d","#ffa300","#ffec27","#00e436","#29adff","#83769c","#ff77a8","#ffccaa"];
const F={"0":"111101101101111","1":"010110010010111","2":"111001111100111","3":"111001111001111","4":"101101111001001","5":"111100111001111","6":"111100111101111","7":"111001001010010","8":"111101111101111","9":"111101111001111",
A:"010101111101101",B:"110101110101110",C:"011100100100011",D:"110101101101110",E:"111100110100111",F:"111100110100100",G:"011100101101011",H:"101101111101101",I:"111010010010111",J:"001001001101010",K:"101101110101101",L:"100100100100111",M:"101111111101101",N:"110101101101101",O:"010101101101010",P:"110101110100100",Q:"010101101110011",R:"110101110101101",S:"011100010001110",T:"111010010010010",U:"101101101101111",V:"101101101101010",W:"101101111111101",X:"101101010101101",Y:"101101010010010",Z:"111001010100111",
" ":"000000000000000",".":"000000000000010",",":"000000000010100",":":"000010000010000","!":"010010010000010","?":"111001010000010","-":"000000111000000","+":"000010111010000","/":"001001010100100","(":"010100100100010",")":"010001001001010","'":"010010000000000","*":"101010101000000","=":"000111000111000","<":"001010100010001",">":"100010001010100","#":"101111101111101","%":"101001010100101","^":"010101000000000","_":"000000000000111","&":"010101010101011","$":"011110010011110","@":"010101111100011","x":"000101010101000"};
const KEYMAP={ArrowLeft:"left",KeyA:"left",ArrowRight:"right",KeyD:"right",ArrowUp:"up",KeyW:"up",ArrowDown:"down",KeyS:"down",Space:"fire",Enter:"enter",NumpadEnter:"enter",Backspace:"back",Delete:"back"};
const NOSCROLL=new Set(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown","Space","PageUp","PageDown","Home","End","Backspace"]);
const LS={get(k){try{return localStorage.getItem(k)}catch(_){return null}},set(k,v){try{localStorage.setItem(k,v)}catch(_){}}};
// ---------- sound: oscillator beeps + filtered noise, generated live ----------
let AC=null,muted=LS.get("bn_games_mute")=="1";
function ac(){if(!AC){try{AC=new(window.AudioContext||window.webkitAudioContext)()}catch(_){AC=null}}if(AC&&AC.state=="suspended")AC.resume().catch(()=>{});return AC}
function tone(f,d=.1,w="square",v=.06,f2=0,delay=0){if(muted)return;const a=ac();if(!a)return;try{const t=a.currentTime+delay,o=a.createOscillator(),g=a.createGain();o.type=w;o.frequency.setValueAtTime(f,t);if(f2)o.frequency.exponentialRampToValueAtTime(Math.max(20,f2),t+d);g.gain.setValueAtTime(v,t);g.gain.exponentialRampToValueAtTime(.0001,t+d);o.connect(g);g.connect(a.destination);o.start(t);o.stop(t+d+.03)}catch(_){}}
function noise(d=.25,v=.12,delay=0,fq=900){if(muted)return;const a=ac();if(!a)return;try{const n=Math.floor(a.sampleRate*d),b=a.createBuffer(1,n,a.sampleRate),c=b.getChannelData(0);for(let i=0;i<n;i++)c[i]=Math.random()*2-1;
 const s=a.createBufferSource(),fl=a.createBiquadFilter(),g=a.createGain(),t=a.currentTime+delay;s.buffer=b;fl.type="lowpass";fl.frequency.value=fq;g.gain.setValueAtTime(v,t);g.gain.exponentialRampToValueAtTime(.0001,t+d);s.connect(fl);fl.connect(g);g.connect(a.destination);s.start(t)}catch(_){}}
const arp=(ns,d=.07,w="square",v=.05)=>ns.forEach((f,i)=>tone(f,d*1.4,w,v,0,i*d));
const SFX={move:()=>tone(220,.035,"square",.035),click:()=>tone(660,.03,"square",.04),eat:()=>{tone(988,.05,"square",.05);tone(1319,.09,"square",.05,0,.05)},coin:()=>{tone(988,.05,"square",.05);tone(1319,.14,"square",.05,0,.05)},
 jump:()=>tone(280,.16,"square",.05,720),shoot:()=>tone(1100,.09,"square",.04,220),boom:()=>noise(.35,.14,0,700),pop:()=>noise(.12,.1,0,2400),hit:()=>tone(160,.12,"sawtooth",.06,60),
 power:()=>arp([392,523,659,784,1047],.05),die:()=>{tone(660,.55,"square",.06,55)},win:()=>arp([523,659,784,1047,784,1047],.09),line:()=>arp([523,784,1047],.05),bad:()=>tone(110,.22,"square",.05),
 drop:()=>tone(140,.06,"triangle",.1),start:()=>arp([262,330,392,523],.06),bump:()=>tone(120,.06,"square",.06),step:()=>tone(90,.03,"triangle",.08),place:()=>tone(440,.05,"triangle",.08)};
// ---------- drawing helpers bound to a game context ----------
function makeG(def,cv,silent){const ctx=cv.getContext("2d");cv.width=def.w;cv.height=def.h;ctx.imageSmoothingEnabled=false;
 const C=c=>typeof c=="number"?PAL[c]:c;
 const g={def,cv,ctx,W:def.w,H:def.h,s:{},score:0,state:"start",t:0,ticks:0,mode:+(LS.get("bn_games_mode_"+def.id)||0)%((def.modes||[0]).length),keys:{},silent,pal:PAL,
  c:C,rnd:n=>Math.random()*n,ri:n=>Math.floor(Math.random()*n),pick:a=>a[Math.floor(Math.random()*a.length)],clamp:(v,a,b)=>v<a?a:v>b?b:v,
  rect(x,y,w,h,c){ctx.fillStyle=C(c);ctx.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h))},
  box(x,y,w,h,c){g.rect(x,y,w,1,c);g.rect(x,y+h-1,w,1,c);g.rect(x,y,1,h,c);g.rect(x+w-1,y,1,h,c)},
  cls(c=0){ctx.fillStyle=C(c);ctx.fillRect(0,0,g.W,g.H)},
  px(x,y,c){ctx.fillStyle=C(c);ctx.fillRect(Math.round(x),Math.round(y),1,1)},
  line(x0,y0,x1,y1,c){ctx.fillStyle=C(c);x0=Math.round(x0);y0=Math.round(y0);x1=Math.round(x1);y1=Math.round(y1);let dx=Math.abs(x1-x0),dy=-Math.abs(y1-y0),sx=x0<x1?1:-1,sy=y0<y1?1:-1,e=dx+dy,n=0;
   while(n++<2000){ctx.fillRect(x0,y0,1,1);if(x0==x1&&y0==y1)break;const e2=2*e;if(e2>=dy){e+=dy;x0+=sx}if(e2<=dx){e+=dx;y0+=sy}}},
  circ(cx,cy,r,c,fill=true){ctx.fillStyle=C(c);cx=Math.round(cx);cy=Math.round(cy);r=Math.round(r);if(fill){for(let y=-r;y<=r;y++){const w=Math.floor(Math.sqrt(r*r-y*y+r*.8));ctx.fillRect(cx-w,cy+y,2*w+1,1)}}
   else{let x=r,y=0,e=1-r;while(x>=y){[[x,y],[y,x],[-y,x],[-x,y],[-x,-y],[-y,-x],[y,-x],[x,-y]].forEach(([a,b])=>ctx.fillRect(cx+a,cy+b,1,1));y++;if(e<0)e+=2*y+1;else{x--;e+=2*(y-x)+1}}}},
  tw:(s,sc=1)=>String(s).length*4*sc-sc,
  text(str,x,y,c=7,sc=1,al="l"){str=String(str).toUpperCase();let w=str.length*4*sc-sc;if(al=="c")x-=Math.floor(w/2);else if(al=="r")x-=w;ctx.fillStyle=C(c);
   for(const ch of str){const gl=F[ch]||F[ch.toLowerCase()];if(gl)for(let i=0;i<15;i++)if(gl[i]=="1")ctx.fillRect(Math.round(x+(i%3)*sc),Math.round(y+Math.floor(i/3)*sc),sc,sc);x+=4*sc}},
  // sprite: array of strings, hex digit = palette index, "." = transparent
  spr(rows,x,y,o={}){const s=o.s||1,sy=o.sy||s,fl=o.flip,m=o.map;x=Math.round(x);y=Math.round(y);for(let r=0;r<rows.length;r++){const row=rows[r],L=row.length;for(let i=0;i<L;i++){const ch=row[i];if(ch=="."||ch==" ")continue;let ci=parseInt(ch,16);if(m&&m[ci]!=null)ci=m[ci];ctx.fillStyle=PAL[ci];const y0=Math.round(y+r*sy);ctx.fillRect(x+(fl?L-1-i:i)*s,y0,s,Math.round(y+(r+1)*sy)-y0)}}},
  sfx(n){if(!g.silent&&SFX[n])SFX[n]()},tone(...a){if(!g.silent)tone(...a)},noise(...a){if(!g.silent)noise(...a)},
  held(a){for(const k in g.keys)if(g.keys[k]&&(KEYMAP[k]==a||k==a))return true;return false},
  add(n){g.score=Math.max(0,g.score+n)},
  over(msg){if(g.state!="play")return;g.state="over";g.msg=msg||"GAME OVER";g.won=false;g.newBest=saveBest(g,false);g.overAt=performance.now();g.sfx("die")},
  win(msg){if(g.state!="play")return;g.state="over";g.msg=msg||"YOU WIN!";g.won=true;g.newBest=saveBest(g,true);g.overAt=performance.now();g.sfx("win")},
  best(){return getBest(g)}};
 return g}
const bkey=g=>"bn_games_hi_"+g.def.id+(g.def.modes?"_"+g.mode:"");
function getBest(g){const v=LS.get(bkey(g));return v==null||v===""?null:+v}
function saveBest(g,won){const lower=g.def.best=="time";if(lower&&!won)return false;const v=g.score,b=getBest(g);if(!lower&&v<=0)return false;
 if(b==null||(lower?v<b:v>b)){LS.set(bkey(g),String(v));return true}return false}
const fmtT=s=>s==null?"—":Math.floor(s/60)+":"+String(Math.floor(s%60)).padStart(2,"0");
// ---------- registry + player ----------
const GAMES=[];const P={g:null,raf:0,acc:0,last:0,root:null,el:{},onBack:null};
function register(def){if(!GAMES.find(x=>x.id==def.id))GAMES.push(def)}
function wrap(g,str,max){const out=[];String(str).split(/\s+/).forEach(w=>{const l=out.length?out[out.length-1]:null;if(l!=null&&(l+" "+w).length*4<=max)out[out.length-1]=l+" "+w;else out.push(w)});return out}
function overlay(g){const {W,H}=g,ctx=g.ctx,cx=W>>1;const dim=a=>{ctx.fillStyle=`rgba(0,0,0,${a})`;ctx.fillRect(0,0,W,H)};const sc=W>=200?2:1;
 if(g.state=="start"){dim(.72);let y=Math.max(8,(H>>1)-62);g.text(g.def.name,cx,y,10,sc,"c");y+=7*sc+4;
  wrap(g,"INSPIRED BY "+g.def.inspired,W-16).forEach(l=>{g.text(l,cx,y,6,1,"c");y+=7});y+=4;
  if(g.def.modes){g.text("< "+g.def.modes[g.mode]+" >",cx,y,11,1,"c");y+=7;g.text("LEFT/RIGHT OR 1-"+g.def.modes.length+": DIFFICULTY",cx,y,13,1,"c");y+=11}
  (g.def.controls||[]).slice(0,7).forEach(c=>{wrap(g,c,W-16).forEach(l=>{g.text(l,cx,y,7,1,"c");y+=7})});y+=6;
  const b=getBest(g);g.text("BEST: "+(b==null?"-":(g.def.best=="time"?fmtT(b):b)),cx,y,12,1,"c");y+=10;
  if((performance.now()/500|0)%2)g.text("PRESS ENTER, SPACE OR CLICK",cx,y,10,1,"c");return}
 if(g.state=="pause"){dim(.65);g.text("PAUSED",cx,(H>>1)-12,10,sc,"c");g.text("P OR ESC TO RESUME",cx,(H>>1)+6,7,1,"c");g.text("M: SOUND "+(muted?"OFF":"ON"),cx,(H>>1)+16,6,1,"c");return}
 if(g.state=="over"){dim(.6);let y=(H>>1)-30;wrap(g,g.msg,W/sc-8).forEach(l=>{g.text(l,cx,y,g.won?11:8,sc,"c");y+=7*sc+2});y+=4;
  const tm=g.def.best=="time";g.text((tm?"TIME ":"SCORE ")+(tm?fmtT(g.score):g.score),cx,y,7,1,"c");y+=9;const b=getBest(g);g.text("BEST "+(b==null?"-":(tm?fmtT(b):b)),cx,y,12,1,"c");y+=9;
  if(g.newBest){g.text("NEW BEST!",cx,y,10,1,"c")}y+=12;if(performance.now()-g.overAt>500&&(performance.now()/500|0)%2)g.text("ENTER, SPACE OR R: PLAY AGAIN",cx,y,10,1,"c")}}
function start(g){g.score=0;g.t=0;g.ticks=0;g.s={};g.keys={};g.newBest=false;g.state="play";g.def.init(g);g.sfx("start");hud(true)}
function setMuted(m){muted=m;LS.set("bn_games_mute",m?"1":"0");if(P.el.mute)P.el.mute.textContent=muted?"🔇 Sound off":"🔊 Sound on";if(P.el.mute)P.el.mute.setAttribute("aria-pressed",String(muted))}
function keyName(e){const c=e.code;let a=KEYMAP[c];if(/^(Digit|Numpad)[0-9]$/.test(c))a=c.slice(-1);return a}
function kd(e){const g=P.g;if(!g)return;if(!P.el.stage||P.el.stage.offsetParent===null)return;const tg=e.target;if(tg&&(tg.tagName=="INPUT"||tg.tagName=="TEXTAREA"||tg.tagName=="SELECT"||tg.isContentEditable))return;if(e.ctrlKey||e.metaKey||e.altKey)return;
 const code=e.code,act=keyName(e);if(NOSCROLL.has(code))e.preventDefault();
 g.keys[code]=true;
 if(code=="KeyM"){setMuted(!muted);return}
 if(code=="KeyP"||code=="Escape"){e.preventDefault();if(g.state=="play"){g.state="pause";SFX.click()}else if(g.state=="pause"){g.state="play";SFX.click()}hud(true);return}
 if(g.state=="start"){const n=(g.def.modes||[]).length;
  if(n&&(act=="left"||act=="right")){g.mode=(g.mode+(act=="left"?n-1:1))%n;LS.set("bn_games_mode_"+g.def.id,g.mode);g.s={};g.def.init(g);SFX.move();hud(true);return}
  if(n&&act&&/^[1-9]$/.test(act)&&+act<=n){g.mode=+act-1;LS.set("bn_games_mode_"+g.def.id,g.mode);g.s={};g.def.init(g);SFX.move();hud(true);return}
  if(!e.repeat&&(act=="enter"||act=="fire")){ac();start(g)}return}
 if(g.state=="over"){if(!e.repeat&&(code=="KeyR"||act=="enter"||act=="fire")&&performance.now()-g.overAt>500)start(g);return}
 if(g.state!="play")return;if(g.def.key)g.def.key(g,act,code,e)}
function ku(e){const g=P.g;if(!g)return;delete g.keys[e.code];if(g.state=="play"&&g.def.keyup)g.def.keyup(g,keyName(e),e.code)}
function blur(){if(P.g){P.g.keys={};if(P.g.state=="play"){P.g.state="pause";hud(true)}}}
function vis(){if(document.hidden)blur()}
function pos(e){const r=P.g.cv.getBoundingClientRect();return[Math.floor((e.clientX-r.left)/r.width*P.g.W),Math.floor((e.clientY-r.top)/r.height*P.g.H)]}
function md(e){const g=P.g;if(!g)return;e.preventDefault();P.el.stage.focus({preventScroll:true});ac();
 if(g.state=="start"){start(g);return}if(g.state=="over"){if(performance.now()-g.overAt>500)start(g);return}if(g.state=="pause"){g.state="play";hud(true);return}
 if(g.def.click){const [x,y]=pos(e);g.def.click(g,x,y,e.button)}}
function mm(e){const g=P.g;if(g&&g.state=="play"&&g.def.mouse){const [x,y]=pos(e);g.def.mouse(g,x,y)}}
function frame(ts){const g=P.g;if(!g)return;P.raf=requestAnimationFrame(frame);let dt=ts-(P.last||ts);P.last=ts;if(dt>250)dt=250;P.acc+=dt;let n=0;
 while(P.acc>=1000/60&&n<6){P.acc-=1000/60;n++;if(g.state=="play"){g.ticks++;g.t=g.ticks/60;if(g.def.best=="time")g.score=Math.floor(g.t);try{g.def.update&&g.def.update(g)}catch(err){console.error(err)}}}
 if(n==6)P.acc=0;render(g);hud()}
function render(g){g.ctx.setTransform(1,0,0,1,0,0);g.def.draw(g);if(g.state!="play")overlay(g)}
let lastH="";function hud(force){const g=P.g;if(!g||!P.el.score)return;const tm=g.def.best=="time",b=getBest(g);
 const h=(tm?"Time ":"Score ")+(tm?fmtT(g.score):g.score)+"|"+(b==null?"—":(tm?fmtT(b):b))+"|"+g.state;if(h==lastH&&!force)return;lastH=h;
 P.el.score.textContent=(tm?"Time ":"Score ")+(tm?fmtT(g.score):g.score);P.el.best.textContent=(tm?"Best time ":"Best ")+(b==null?"—":(tm?fmtT(b):b))+(g.def.modes?" ("+g.def.modes[g.mode].toLowerCase()+")":"");
 P.el.pause.textContent=g.state=="pause"?"▶ Resume":"⏸ Pause";P.el.pause.disabled=!(g.state=="play"||g.state=="pause")}
function fit(){const g=P.g;if(!g||!P.el.stage)return;const aw=Math.max(200,P.el.stage.clientWidth-8),ah=Math.max(240,window.innerHeight-250);let s=Math.min(aw/g.W,ah/g.H);s=s>=2?Math.floor(s):Math.max(1,Math.floor(s*2)/2);
 g.cv.style.width=g.W*s+"px";g.cv.style.height=g.H*s+"px"}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function open(id,root,onBack){close();const def=GAMES.find(x=>x.id==id);if(!def)return null;P.root=root;P.onBack=onBack;
 root.innerHTML=`<div class="gm-player" data-game="${esc(def.id)}"><div class="gm-pbar"><button type="button" class="gm-back">← All games</button><b class="gm-ptitle">${esc(def.name)}</b><span class="gm-pinsp">inspired by ${esc(def.inspired)}</span><span class="gm-sp"></span><span class="gm-score"></span><span class="gm-best"></span><button type="button" class="gm-mute"></button><button type="button" class="gm-pause"></button><button type="button" class="gm-restart">↻ Restart</button></div>
 <div class="gm-stage" tabindex="0" aria-label="${esc(def.name)} game. Keyboard controls are listed below."><canvas class="gm-cv" width="${def.w}" height="${def.h}"></canvas></div>
 <div class="gm-ctl"><b>Controls:</b> ${(def.controls||[]).map(esc).join(" · ")} · P / Esc: pause · M: sound on/off</div><div class="gm-desc meta">${esc(def.desc)}</div></div>`;
 const q=s=>root.querySelector(s);P.el={stage:q(".gm-stage"),score:q(".gm-score"),best:q(".gm-best"),mute:q(".gm-mute"),pause:q(".gm-pause"),restart:q(".gm-restart")};
 const g=makeG(def,q(".gm-cv"),false);P.g=g;g.def.init(g);setMuted(muted);lastH="";
 q(".gm-back").onclick=()=>{close();onBack&&onBack()};P.el.mute.onclick=()=>{setMuted(!muted);P.el.stage.focus({preventScroll:true})};
 P.el.pause.onclick=()=>{if(g.state=="play")g.state="pause";else if(g.state=="pause")g.state="play";hud(true);P.el.stage.focus({preventScroll:true})};
 P.el.restart.onclick=()=>{ac();start(g);P.el.stage.focus({preventScroll:true})};
 window.addEventListener("keydown",kd,true);window.addEventListener("keyup",ku,true);window.addEventListener("blur",blur);document.addEventListener("visibilitychange",vis);window.addEventListener("resize",fit);
 g.cv.addEventListener("mousedown",md);g.cv.addEventListener("mousemove",mm);g.cv.addEventListener("contextmenu",e=>e.preventDefault());
 fit();P.last=0;P.acc=0;P.raf=requestAnimationFrame(frame);P.el.stage.focus({preventScroll:true});hud(true);return g}
function close(){if(P.raf)cancelAnimationFrame(P.raf);P.raf=0;window.removeEventListener("keydown",kd,true);window.removeEventListener("keyup",ku,true);window.removeEventListener("blur",blur);document.removeEventListener("visibilitychange",vis);window.removeEventListener("resize",fit);
 if(P.g&&P.g.cv){P.g.cv.removeEventListener("mousedown",md);P.g.cv.removeEventListener("mousemove",mm)}P.g=null;P.el={};if(P.root)P.root.innerHTML="";P.root=null}
function pause(){if(P.g&&P.g.state=="play"){P.g.state="pause";P.g.keys={};hud(true)}}
function thumb(def){const cv=document.createElement("canvas");const g=makeG(def,cv,true);try{def.init(g);g.state="play";if(def.thumbTicks)for(let i=0;i<def.thumbTicks;i++){g.ticks++;def.update(g)}def.draw(g)}catch(err){console.error("thumb "+def.id,err);g.cls(1);g.text(def.name,def.w/2,def.h/2,7,1,"c")}return cv}
window.BNG={register,games:GAMES,open,close,pause,thumb,get cur(){return P.g},fmtT,PAL,sfx:SFX,get muted(){return muted}};
})();
