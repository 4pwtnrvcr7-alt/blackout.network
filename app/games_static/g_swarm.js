// Star Swarm: original formation-and-dive space shooter (inspired by Galaga / Galaxian).
(()=>{const W=224,H=256,PY=232;
const SH=["...7...","...7...","..777..",".7c7c7.","7777777","77.7.77"];
const EN=[["1..1..1","11.1.11",".11111.","1.888.1",".11111.",".1...1."],["..111..",".1.8.1.","1111111","1.1.1.1","1.....1","..1.1.."],[".1...1.","..111..",".18181.","1111111","1.111.1","1.....1"]];
const EC=[[10,8],[14,8],[12,7]];
function wave(g){const s=g.s;s.en=[];const rows=[[2,6],[1,8],[1,8],[0,10]];let k=0;rows.forEach(([t,n],r)=>{for(let c=0;c<n;c++){const sx=W/2-(n-1)*10+c*20,sy=30+r*16;const side=(r+c)%2;
 s.en.push({t,sx,sy,x:side?-10:W+10,y:H*.55,st:"enter",d:k*5,p:0,fx:side?-10:W+10,fy:H*.55,hp:t==0?2:1,c:EC[t]});k++}});s.sway=0;s.diveT=180}
BNG.register({id:"swarm",name:"Star Swarm",inspired:"Galaga and Galaxian-style formation shooters",cats:["Arcade","Action","Classic"],w:W,h:H,
 desc:"Waves of original pixel ships swoop in, line up in formation and peel off in diving attacks. Shoot them while they're diving for double points.",
 controls:["Left/Right: move","Space: fire (two shots at a time)"],
 init(g){const s=g.s;s.px=W/2;s.lives=3;s.wave=1;s.shots=[];s.eb=[];s.parts=[];s.dead=0;s.stars=Array.from({length:50},()=>({x:g.rnd(W),y:g.rnd(H),v:.3+Math.random()*1.2,c:g.pick([5,6,12,13])}));wave(g)},
 key(g,a){const s=g.s;if(a=="fire"&&!s.dead&&s.shots.length<2){s.shots.push({x:s.px,y:PY-4});g.sfx("shoot")}},
 update(g){const s=g.s;s.stars.forEach(t=>{t.y+=t.v;if(t.y>H)t.y=0});s.parts=s.parts.filter(p=>{p.x+=p.vx;p.y+=p.vy;return--p.t>0});
  if(s.dead){if(--s.dead==0){if(s.lives<=0){g.over();return}s.px=W/2;s.eb=[]}}
  else{if(g.held("left"))s.px-=2;if(g.held("right"))s.px+=2;s.px=g.clamp(s.px,6,W-6)}
  s.sway+=.02;const off=Math.sin(s.sway)*10;
  s.shots=s.shots.filter(b=>{b.y-=5;if(b.y<0)return false;for(const e of s.en){if(e.st=="gone")continue;if(Math.abs(b.x-e.x)<5&&Math.abs(b.y-e.y)<5){if(--e.hp>0){g.tone(500,.05);e.c=[9,8];return false}
   e.st="gone";g.add([150,80,50][e.t]*(e.st=="dive"||e.dv?2:1));boom(g,e.x,e.y,e.c[0]);g.sfx("pop");return false}}return true});
  if(--s.diveT<=0&&!s.dead){s.diveT=Math.max(40,140-s.wave*12);const f=s.en.filter(e=>e.st=="form");if(f.length){const n=Math.min(f.length,1+(s.wave>2)+(Math.random()<.3));for(let i=0;i<n;i++){const e=g.pick(f);if(e.st=="form"){e.st="dive";e.dv=true;e.p=0;e.ox=e.x;e.dir=e.x<W/2?1:-1;g.tone(900,.25,"square",.03,300)}}}}
  for(const e of s.en){if(e.st=="enter"){if(e.d>0){e.d--;continue}e.p+=.012;const t=Math.min(1,e.p),tx=e.sx+off,ty=e.sy,cx=W/2+(e.fx<0?-60:60),cy=40;
    e.x=(1-t)**2*e.fx+2*(1-t)*t*cx+t*t*tx;e.y=(1-t)**2*e.fy+2*(1-t)*t*cy+t*t*ty;if(t>=1)e.st="form"}
   else if(e.st=="form"){e.x=e.sx+off;e.y=e.sy}
   else if(e.st=="dive"){e.p++;e.y+=1.6+s.wave*.12;e.x+=Math.sin(e.p/18)*2.2*e.dir+(s.px-e.x)*.012;if(e.p%50==25&&s.eb.length<6)s.eb.push({x:e.x,y:e.y+4,vx:(s.px-e.x)/90});
    if(e.y>H+8){e.y=-8;e.st="ret"}}
   else if(e.st=="ret"){const tx=e.sx+off,ty=e.sy;e.x+=(tx-e.x)*.06;e.y+=Math.min(2,ty-e.y);if(Math.abs(ty-e.y)<1){e.st="form";e.dv=false}}
   if(!s.dead&&e.st!="gone"&&Math.abs(e.x-s.px)<6&&Math.abs(e.y-PY)<6){e.st="gone";boom(g,e.x,e.y,8);die(g)}}
  s.eb=s.eb.filter(b=>{b.y+=2.4;b.x+=b.vx;if(!s.dead&&Math.abs(b.x-s.px)<4&&Math.abs(b.y-PY)<4){die(g);return false}return b.y<H});
  if(s.en.every(e=>e.st=="gone")){s.wave++;g.add(1000);g.sfx("win");wave(g)}},
 draw(g){const s=g.s;g.cls(0);s.stars.forEach(t=>g.px(t.x,t.y,t.c));
  s.en.forEach(e=>{if(e.st!="gone")g.spr(EN[e.t],e.x-3,e.y-3,{map:{1:e.c[0],8:e.c[1]}})});
  s.parts.forEach(p=>g.px(p.x,p.y,p.c));s.shots.forEach(b=>g.rect(b.x,b.y,1,4,10));s.eb.forEach(b=>{g.rect(b.x,b.y,2,3,8)});
  if(!s.dead)g.spr(SH,s.px-3,PY-3,{map:{12:12}});
  g.text("SCORE "+g.score,3,3,7);g.text("WAVE "+s.wave,W-3,3,10,1,"r");for(let i=0;i<s.lives;i++)g.spr(SH,4+i*9,H-8,{map:{7:6}})}});
function boom(g,x,y,c){for(let i=0;i<10;i++){const a=Math.random()*6.28,v=Math.random()*1.5;g.s.parts.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v,t:15+g.ri(15),c:g.pick([c,7,9])})}}
function die(g){const s=g.s;if(s.dead)return;s.lives--;s.dead=90;boom(g,s.px,PY,12);g.sfx("boom")}
})();
