// Cube Hopper: original isometric pyramid hopper (inspired by Q*bert). Original hopper, balls and "Spring" chaser.
(()=>{const W=256,H=224,R=7,OX=128,OY=36,HW=14,HH=7,SIDE=14;
const scr=(r,c)=>[OX+(c*2-r)*HW,OY+r*(HH+SIDE)];
const HOP=[".9999...","999999..","90909999","99999999.","..9999999","..999.99",".99..99.","99...99."];
const SPRING=["..dd..","dd7d7d","dddddd",".d22d.","..dd..","..d...","...d..","..d..."];
const TOPS=[[1,12,12],[1,13,10],[5,14,11],[1,9,10]];
function lvl(g){const s=g.s;s.cubes=[];for(let r=0;r<R;r++)for(let c=0;c<=r;c++)s.cubes.push({r,c,st:0});s.need=s.lv==1?1:2;reset(g)}
function reset(g){const s=g.s;s.p={r:0,c:0,fr:null,t:0,dead:0};s.en=[];s.spawn=120;s.freeze=0}
function hop(o,r,c,dur){o.fr=[o.r,o.c];o.r=r;o.c=c;o.t=dur;o.dur=dur}
const on=(r,c)=>r>=0&&r<R&&c>=0&&c<=r;
function land(g){const s=g.s,p=s.p;const cu=s.cubes.find(q=>q.r==p.r&&q.c==p.c);
 if(s.lv>=3){cu.st=cu.st>=s.need?0:cu.st+1;g.add(15);g.tone(cu.st?520:260,.06)}else if(cu.st<s.need){cu.st++;g.add(25);g.tone(440+cu.st*120,.06)}
 if(s.cubes.every(q=>q.st==s.need)){s.clear=120;g.add(1000+s.lv*250);g.sfx("win")}}
BNG.register({id:"cube",name:"Cube Hopper",inspired:"Q*bert-style isometric pyramid hoppers",cats:["Arcade","Puzzle","Classic"],w:W,h:H,
 desc:"Hop diagonally around an isometric pyramid and change the color of every top face. Dodge the bouncing red balls and the purple Spring that chases you, and don't jump off the edge.",
 controls:["Up: hop up-right · Right: down-right","Down: down-left · Left: up-left","Green ball freezes enemies"],
 init(g){const s=g.s;s.lv=1;s.lives=3;lvl(g)},
 key(g,a){const s=g.s,p=s.p;if(p.t>0||p.dead||s.clear)return;const d={up:[-1,0],right:[1,1],down:[1,0],left:[-1,-1]}[a];if(!d)return;hop(p,p.r+d[0],p.c+d[1],16);g.sfx("jump")},
 update(g){const s=g.s,p=s.p;if(s.clear){if(--s.clear==0){s.lv++;lvl(g)}return}
  if(p.dead){if(--p.dead==0){s.lives--;if(s.lives<=0){g.over();return}reset(g)}return}
  if(p.t>0&&--p.t==0){if(!on(p.r,p.c)){p.fall=1;p.dead=70;g.tone(800,.8,"square",.05,80);return}land(g)}
  if(s.freeze>0)s.freeze--;
  if(--s.spawn<=0&&s.en.length<2+Math.floor(s.lv/2)){s.spawn=Math.max(80,220-s.lv*20);const k=Math.random();const t=!s.en.some(e=>e.k=="spring")&&k<.35?"spring":k>.9?"green":"red";s.en.push({k:t,r:-1,c:0,t:0,egg:t=="spring",wait:20});const e=s.en[s.en.length-1];hop(e,1,g.ri(2),30)}
  s.en=s.en.filter(e=>{if(s.freeze>0)return true;if(e.t>0){e.t--;if(e.t==0&&!on(e.r,e.c))return false;return true}
   if(--e.wait>0)return true;e.wait=e.k=="spring"&&!e.egg?14:22;
   if(e.k=="spring"&&!e.egg){let best=null,bd=1e9;[[-1,0],[1,1],[1,0],[-1,-1]].forEach(([dr,dc])=>{const r=e.r+dr,c=e.c+dc;if(!on(r,c))return;const [x1,y1]=scr(r,c),[x2,y2]=scr(p.r,p.c),d=Math.hypot(x1-x2,y1-y2);if(d<bd){bd=d;best=[r,c]}});if(best)hop(e,best[0],best[1],22);return true}
   if(e.r>=R-1){if(e.egg){e.egg=false;return true}hop(e,R,e.c+g.ri(2),30);return true}hop(e,e.r+1,e.c+g.ri(2),24);return true});
  if(!p.t&&!p.dead)for(const e of s.en){if(e.t>0&&e.t<e.dur*.7)continue;if(e.r==p.r&&e.c==p.c){if(e.k=="green"){s.freeze=180;g.add(100);g.sfx("power");s.en=s.en.filter(x=>x!==e);break}p.dead=80;g.sfx("die");break}}},
 draw(g){const s=g.s,p=s.p;g.cls(0);const tc=TOPS[(s.lv-1)%TOPS.length];
  s.cubes.forEach(q=>{const [x,y]=scr(q.r,q.c),col=q.st==0?tc[0]:q.st>=s.need?tc[2]:tc[1];
   for(let d=0;d<HW;d++){const yl=Math.round(y+d*HH/HW),yr=Math.round(y+HH-d*HH/HW);g.rect(x-HW+d,yl,1,SIDE+1,d==0?9:4);g.rect(x+d,yr,1,SIDE+1,d==HW-1?1:2)}
   for(let i=0;i<=HH;i++){const w=Math.round(HW*i/HH);g.rect(x-w,y-HH+i,w*2,1,col);g.rect(x-w,y+HH-i,w*2,1,col)}});
  const pos=o=>{if(o.t>0&&o.fr){const k=1-o.t/o.dur,[x1,y1]=scr(...o.fr),[x2,y2]=scr(o.r,o.c);return[x1+(x2-x1)*k,y1+(y2-y1)*k-Math.sin(k*Math.PI)*14]}return scr(o.r,o.c)};
  s.en.forEach(e=>{const [x,y]=pos(e);if(e.k=="spring"&&!e.egg)g.spr(SPRING,x-3,y-12);else g.circ(x,y-5,4,e.k=="green"?11:e.k=="spring"?13:8)});
  if(!(p.dead&&!p.fall&&(p.dead>>2)%2)){let [x,y]=pos(p);if(p.fall)y+=(70-p.dead)*3;g.spr(HOP,x-4,y-12)}
  g.text("SCORE "+g.score,3,3,7);g.text("LEVEL "+s.lv,W-3,3,10,1,"r");g.text("CHANGE TO",W-3,12,6,1,"r");g.rect(W-20,20,16,6,tc[2]);for(let i=0;i<s.lives;i++)g.spr(HOP,3+i*11,12);
  if(s.freeze)g.text("FROZEN!",W/2,H-14,11,1,"c");if(s.clear)g.text("PYRAMID DONE!",W/2,H-30,10,2,"c")}});
})();
