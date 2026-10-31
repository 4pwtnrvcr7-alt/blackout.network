// Barrel Climb: original ladders-and-barrels climber (inspired by Donkey Kong). Original "Brute" and hero art.
(()=>{const W=256,H=232;
const G=[{x0:0,x1:256,yl:222,yr:214},{x0:0,x1:232,yl:182,yr:188},{x0:24,x1:256,yl:152,yr:146},{x0:0,x1:232,yl:114,yr:120},{x0:24,x1:256,yl:86,yr:80},{x0:0,x1:232,yl:48,yr:54},{x0:96,x1:150,yl:24,yr:24}];
const LAD=[[200,0,1],[60,1,2],[130,1,2],[180,2,3],[90,2,3],[40,3,4],[150,3,4],[210,4,5],[120,4,5],[120,5,6]].map(([x,lo,hi])=>({x,lo,hi}));
const gy=(i,x)=>{const g=G[i];return g.yl+(g.yr-g.yl)*(x-g.x0)/(g.x1-g.x0)};const down=i=>G[i].yr>G[i].yl?1:-1;
const HERO=["..8888..",".888888.","..ffff..","..f0f0..","..ffff..",".cccccc.","c.cccc.c","f.cccc.f","..c..c..","..c..c..",".44..44."];
const BRUTE=["....4444444.....","...444444444....","..44ffffffff44..","..4f0ff00ff0f4..","..4ffff88ffff4..","..44f888888f44..",".44444ffff44444.","4444444444444444","44.4444444444.44","44.4444444444.44","ff.4444444444.ff","...444....444...","..4444....4444.."];
const PAL_BOT=["..6..6..",".666666.",".6c66c6.",".666666.","..6666..",".6.66.6."];
function lv(g){const s=g.s;s.p={x:16,y:gy(0,16),gi:0,st:"walk",vy:0,vx:0,face:1};s.b=[];s.bt=60;s.bonus=5000;s.ham=[{x:200,gi:2},{x:70,gi:4}];s.hamT=0;s.dead=0;s.done=0}
BNG.register({id:"barrels",name:"Barrel Climb",inspired:"Donkey Kong-style ladder-and-barrel climbers",cats:["Arcade","Action","Classic"],w:W,h:H,
 desc:"An original big Brute is rolling barrels down sloped girders. Climb the ladders, jump the barrels, grab a hammer to smash them, and free the caged robot pal at the top.",
 controls:["Left/Right: walk","Up/Down: climb ladders","Space: jump (over barrels for points)","Hammer: smash barrels for 8 s"],
 init(g){const s=g.s;s.lives=3;s.level=1;lv(g)},
 key(g,a){const p=g.s.p;if(a=="fire"&&p.st=="walk"&&!g.s.hamT&&!g.s.dead&&!g.s.done){p.st="jump";p.vy=-2.7;p.vx=g.held("left")?-1.1:g.held("right")?1.1:0;g.sfx("jump");p.scored=false}},
 update(g){const s=g.s,p=s.p;if(s.dead){if(--s.dead==0){s.lives--;if(s.lives<=0){g.over("SQUASHED!");return}lv(g)}return}
  if(s.done){if(--s.done==0){s.level++;lv(g)}return}
  if(g.ticks%120==0){s.bonus-=100;if(s.bonus<=0){die(g);return}}
  if(s.hamT>0)s.hamT--;
  if(p.st=="walk"){let mv=0;if(g.held("left"))mv=-1;else if(g.held("right"))mv=1;if(mv){p.face=mv;p.x=g.clamp(p.x+mv*1.1,G[p.gi].x0+4,G[p.gi].x1-4);if(g.ticks%10==0)g.sfx("step")}p.y=gy(p.gi,p.x);
   if(!s.hamT){const up=LAD.find(l=>l.lo==p.gi&&Math.abs(l.x-p.x)<4),dn=LAD.find(l=>l.hi==p.gi&&Math.abs(l.x-p.x)<4);
    if(g.held("up")&&up){p.st="climb";p.lad=up;p.x=up.x}else if(g.held("down")&&dn){p.st="climb";p.lad=dn;p.x=dn.x;p.y+=1}}}
  else if(p.st=="climb"){const l=p.lad;if(g.held("up")){p.y-=.8;if(g.ticks%12==0)g.sfx("step")}if(g.held("down")){p.y+=.8;if(g.ticks%12==0)g.sfx("step")}
   if(p.y<=gy(l.hi,l.x)){p.y=gy(l.hi,l.x);p.gi=l.hi;p.st="walk";if(p.gi==6){s.done=150;g.add(s.bonus);g.sfx("win");return}}
   if(p.y>=gy(l.lo,l.x)){p.y=gy(l.lo,l.x);p.gi=l.lo;p.st="walk"}}
  else if(p.st=="jump"){p.x=g.clamp(p.x+p.vx,G[p.gi].x0+4,G[p.gi].x1-4);p.vy+=.15;p.y+=p.vy;if(p.vy>0&&p.y>=gy(p.gi,p.x)){p.y=gy(p.gi,p.x);p.st="walk"}}
  s.ham=s.ham.filter(h=>{if(p.gi==h.gi&&Math.abs(p.x-h.x)<6&&p.st!="climb"){s.hamT=480;g.sfx("power");return false}return true});
  if(--s.bt<=0){s.bt=Math.max(55,170-s.level*18-g.ri(60));s.b.push({x:44,y:gy(5,44),gi:5,dir:1,st:"roll",vy:0,last:null,rot:0});s.throwT=20}
  const bs=1+s.level*.15;if(s.throwT)s.throwT--;
  s.b=s.b.filter(b=>{b.rot+=b.dir*.2;if(b.st=="roll"){b.x+=b.dir*bs;b.y=gy(b.gi,b.x);
    const l=LAD.find(q=>q.hi==b.gi&&Math.abs(q.x-b.x)<bs/2+.1);if(l&&l!==b.last){b.last=l;if(Math.random()<.25+s.level*.03){b.st="lad";b.l=l;b.x=l.x}}
    if(b.x>G[b.gi].x1||b.x<G[b.gi].x0){if(b.gi==0)return false;b.st="fall";b.vy=0}}
   else if(b.st=="lad"){b.y+=1.1;if(b.y>=gy(b.l.lo,b.x)){b.gi=b.l.lo;b.dir=down(b.gi);b.st="roll";b.y=gy(b.gi,b.x)}}
   else if(b.st=="fall"){b.vy+=.2;b.y+=b.vy;b.x+=b.dir*.4;const t=b.gi-1;if(b.y>=gy(t,b.x)){b.gi=t;b.dir=down(t);b.st="roll";b.y=gy(t,b.x);g.tone(90,.06,"triangle",.08)}}
   if(Math.abs(b.x-(p.x+p.face*(s.hamT?9:0)))<(s.hamT?11:7)&&Math.abs((b.y-5)-(p.y-6))<(s.hamT?12:9)){if(s.hamT){g.add(300);g.sfx("boom");s.fx={x:b.x,y:b.y,t:30,v:300};return false}die(g);return true}
   if(p.st=="jump"&&!b.scored&&b.gi==p.gi&&Math.abs(b.x-p.x)<6&&p.y<b.y-9){b.scored=true;g.add(100);g.sfx("coin");s.fx={x:b.x,y:b.y-14,t:30,v:100}}
   return b.y<H+10});
  if(s.fx&&--s.fx.t<=0)s.fx=null},
 draw(g){const s=g.s,p=s.p;g.cls(0);
  LAD.forEach(l=>{const y0=gy(l.hi,l.x),y1=gy(l.lo,l.x);g.rect(l.x-5,y0,1,y1-y0,12);g.rect(l.x+4,y0,1,y1-y0,12);for(let y=y0+3;y<y1;y+=5)g.rect(l.x-5,y,10,1,12)});
  G.forEach((q,i)=>{for(let x=q.x0;x<q.x1;x+=8){const y=Math.round(gy(i,x+4));g.rect(x,y,8,6,8);g.rect(x,y,8,1,14);g.rect(x,y+5,8,1,2);g.line(x,y+5,x+4,y+1,2);g.line(x+4,y+1,x+8,y+5,2)}});
  g.spr(BRUTE,6,gy(5,14)-13,{flip:s.throwT>0});if(s.throwT>0)g.circ(28,gy(5,28)-16,5,4);
  g.box(124,6,20,18,6);g.spr(PAL_BOT,130,15);for(let x=126;x<144;x+=4)g.rect(x,6,1,18,6);if((g.ticks>>5)%2)g.text("HELP!",112,0,7,1,"c");
  s.ham.forEach(h=>{const y=gy(h.gi,h.x);g.rect(h.x-1,y-10,2,8,4);g.rect(h.x-4,y-12,8,4,6)});
  s.b.forEach(b=>{const y=b.y-5;g.circ(b.x,y,5,4);g.circ(b.x,y,3,9);const a=b.rot;g.line(b.x-Math.cos(a)*4,y-Math.sin(a)*4,b.x+Math.cos(a)*4,y+Math.sin(a)*4,4)});
  if(!s.dead||(s.dead>>3)%2){g.spr(HERO,p.x-4,p.y-11,{flip:p.face<0,map:s.dead?{12:8}:{}});if(s.hamT&&(s.hamT>90||(s.hamT>>2)%2)){const up=(g.ticks>>3)%2,hx=p.x+p.face*(up?3:8),hy=p.y-(up?18:10);g.rect(hx-1,hy,2,7,4);g.rect(hx-4,hy-3,8,4,6)}}
  if(s.fx)g.text(s.fx.v,s.fx.x,s.fx.y-10,10,1,"c");
  g.text("SCORE "+g.score,3,3,7);g.text("BONUS "+s.bonus,W-3,3,s.bonus<1500?8:10,1,"r");g.text("L"+s.level,W-3,11,6,1,"r");for(let i=0;i<s.lives;i++)g.rect(4+i*6,11,4,4,8);
  if(s.done)g.text("RESCUED!",W/2,100,11,2,"c")}});
function die(g){const s=g.s;if(s.dead)return;s.dead=90;g.sfx("die")}
})();
