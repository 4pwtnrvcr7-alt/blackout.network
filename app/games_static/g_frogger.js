// Road Hopper: original road-and-river crossing game (inspired by Frogger).
(()=>{const T=16,W=256,H=240,COLS=16;
const FROG=[["..b..b..",".bbbbbb.","b.bbbb.b","..b33b..",".bbbbbb.","b.bbbb.b","b......b"]];
const CAR=["..8888....",".88cc88...","8888888888","8888888888",".00....00."];
// rows: 1 homes, 2-6 river, 7 bank, 8-12 road, 13 start
function lanes(lv){const k=1+(lv-1)*.18;return[
 {y:2,t:"log",v:.6*k,len:4,gap:3},{y:3,t:"turtle",v:-.8*k,len:3,gap:3},{y:4,t:"log",v:1.1*k,len:6,gap:4},{y:5,t:"log",v:.5*k,len:3,gap:3},{y:6,t:"turtle",v:-1*k,len:2,gap:3},
 {y:8,t:"truck",v:-.5*k,len:2,gap:5},{y:9,t:"car",v:1.3*k,len:1,gap:5},{y:10,t:"car",v:-.9*k,len:1,gap:3},{y:11,t:"car",v:.7*k,len:1,gap:4},{y:12,t:"car",v:-1.1*k,len:1,gap:4}]}
function build(g){const s=g.s;s.L=lanes(s.lv).map(l=>{const it=[];let x=g.rnd(40);while(x<W+64){it.push({x,len:l.len,ph:g.ri(300)});x+=(l.len+l.gap+g.ri(2))*T}return Object.assign(l,{items:it,span:x})})}
function frog(g){const s=g.s;s.fx=7;s.fy=13;s.ox=7*T;s.hop=0;s.max=13;s.time=1800}
BNG.register({id:"frogger",name:"Road Hopper",inspired:"Frogger-style crossing games",cats:["Arcade","Classic"],w:W,h:H,
 desc:"Hop an original pixel frog across five lanes of traffic and a river of drifting logs and turtles. Fill all five lily-pad homes to clear the level.",
 controls:["Arrows / WASD: hop one space","Ride logs and turtles; avoid water and cars"],
 init(g){const s=g.s;s.lv=1;s.lives=3;s.homes=[0,0,0,0,0];s.dead=0;build(g);frog(g)},
 key(g,a){const s=g.s;if(s.dead||s.hop)return;const d={left:[-1,0],right:[1,0],up:[0,-1],down:[0,1]}[a];if(!d)return;
  const nx=Math.round(s.ox/T)+d[0],ny=s.fy+d[1];if(nx<0||nx>=COLS||ny>13||ny<1)return;s.ox=nx*T;s.fy=ny;s.hop=6;s.face=a;g.sfx("jump");if(ny<s.max){s.max=ny;g.add(10)}},
 update(g){const s=g.s;s.L.forEach(l=>{l.items.forEach(it=>{it.x+=l.v;if(l.v>0&&it.x>W+8)it.x-=l.span;if(l.v<0&&it.x+it.len*T<-8)it.x+=l.span})});
  if(s.dead){if(--s.dead==0){if(s.lives<=0){g.over("SPLAT!");return}frog(g)}return}
  if(s.hop)s.hop--;if(--s.time<=0){die(g);return}
  const fy=s.fy,fx=s.ox+T/2,lane=s.L.find(l=>l.y==fy);
  if(!s.hop){if(fy==1){const slot=[1,4,7,10,13].findIndex(c=>Math.abs(fx-(c*T+T/2))<10);if(slot<0||s.homes[slot]){die(g);return}
    s.homes[slot]=1;g.add(50+Math.floor(s.time/30)*2);g.sfx("coin");if(s.homes.every(Boolean)){g.add(1000);s.lv++;s.homes=[0,0,0,0,0];build(g);g.sfx("win")}frog(g);return}
   if(lane&&(lane.t=="log"||lane.t=="turtle")){const on=lane.items.find(it=>fx>=it.x+2&&fx<=it.x+it.len*T-2&&!(lane.t=="turtle"&&sunk(g,it)));if(!on){die(g,true);return}s.ox+=lane.v;if(s.ox<-4||s.ox>W-T+4){die(g,true);return}}}
  if(lane&&(lane.t=="car"||lane.t=="truck")){const w=lane.t=="truck"?2*T:T;if(lane.items.some(it=>fx>it.x+2&&fx<it.x+w*it.len/(lane.t=="truck"?2:1)-2+(lane.t=="truck"?0:0))){die(g);return}}},
 draw(g){const s=g.s;g.cls(0);g.rect(0,T,W,T,3);[1,4,7,10,13].forEach((c,i)=>{g.rect(c*T-2,T,T+4,T,1);if(s.homes[i])g.spr(FROG[0],c*T+4,T+4,{map:{11:11,3:8}})});
  g.rect(0,2*T,W,5*T,1);for(let i=0;i<30;i++)g.rect((i*53+g.ticks/3)%W,2*T+(i*37)%(5*T),3,1,12);g.rect(0,7*T,W,T,13);g.rect(0,8*T,W,5*T,0);for(let y=9;y<13;y++)for(let x=0;x<W;x+=24)g.rect(x,y*T,10,1,6);g.rect(0,13*T,W,T,13);g.rect(0,14*T,W,H-14*T,1);
  s.L.forEach(l=>l.items.forEach(it=>{const Y=l.y*T;if(l.t=="log"){g.rect(it.x,Y+3,it.len*T,10,4);g.rect(it.x,Y+3,it.len*T,2,9);for(let k=6;k<it.len*T;k+=9)g.px(it.x+k,Y+8,0)}
   else if(l.t=="turtle"){if(sunk(g,it)&&(g.ticks>>3)%2)return;for(let k=0;k<it.len;k++){const X=it.x+k*T;g.circ(X+8,Y+8,5,sunk(g,it)?5:3);g.circ(X+8,Y+8,3,11);g.rect(X+(l.v<0?1:13),Y+7,2,2,3)}}
   else if(l.t=="truck"){g.rect(it.x,Y+3,2*T,10,7);g.rect(it.x+(l.v<0?0:24),Y+3,8,10,9);g.rect(it.x+2,Y+12,4,3,0);g.rect(it.x+24,Y+12,4,3,0)}
   else g.spr(CAR,it.x+2,Y+5,{flip:l.v<0,map:{8:[8,14,10,12][l.y%4]}})}));
  if(!s.dead||(s.dead>>2)%2){const X=s.ox+4,Y=s.fy*T+4-(s.hop?2:0);g.spr(FROG[0],X,Y,{map:s.dead?{11:8}:{}})}
  g.text("SCORE "+g.score,3,3,7);g.text("LEVEL "+s.lv,W/2,3,10,1,"c");for(let i=0;i<s.lives;i++)g.spr(FROG[0],W-12-i*10,0);
  g.text("TIME",3,H-11,6);g.rect(24,H-11,Math.max(0,s.time/1800*140),5,s.time<450?8:11)}});
function sunk(g,it){return it.len<=2&&((g.ticks+(it.ph||0))%300)>220}
function die(g,water){const s=g.s;s.lives--;s.dead=60;water?g.noise(.3,.1,0,400):g.sfx("hit")}
})();
