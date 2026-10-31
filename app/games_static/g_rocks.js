// Rock Blaster: original vector-style space rock shooter (inspired by Asteroids).
(()=>{const W=256,H=224,R=[0,5,10,17];
const wrap=o=>{o.x=(o.x+W)%W;o.y=(o.y+H)%H};
function rock(g,x,y,sz){const n=9+g.ri(3),pts=[];for(let i=0;i<n;i++)pts.push(.7+Math.random()*.4);const a=Math.random()*6.28,sp=(.3+Math.random()*.6)*(1.6-sz*.3)*(1+g.s.wave*.06);return{x,y,sz,pts,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,rot:Math.random()*6.28,vr:(Math.random()-.5)*.04}}
function wave(g){const s=g.s;s.rocks=[];for(let i=0;i<3+s.wave;i++){let x,y;do{x=g.rnd(W);y=g.rnd(H)}while(Math.hypot(x-s.sh.x,y-s.sh.y)<70);s.rocks.push(rock(g,x,y,3))}}
function ship(g){const s=g.s;s.sh={x:W/2,y:H/2,a:-Math.PI/2,vx:0,vy:0,inv:150,dead:0}}
BNG.register({id:"rocks",name:"Rock Blaster",inspired:"Asteroids and other vector space shooters",cats:["Arcade","Action","Classic"],w:W,h:H,
 desc:"Pilot a tiny ship through a drifting rock field. Big rocks split into smaller, faster ones. The screen wraps around, and hyperspace is a gamble.",
 controls:["Left/Right: rotate","Up: thrust","Space: fire","Down: hyperspace jump"],
 init(g){const s=g.s;s.lives=3;s.wave=1;s.b=[];s.parts=[];ship(g);wave(g);s.next=10000},
 key(g,a){const s=g.s,h=s.sh;if(h.dead)return;if(a=="fire"&&s.b.length<5){s.b.push({x:h.x+Math.cos(h.a)*6,y:h.y+Math.sin(h.a)*6,vx:Math.cos(h.a)*4.5+h.vx,vy:Math.sin(h.a)*4.5+h.vy,t:50});g.sfx("shoot")}
  if(a=="down"){h.x=g.rnd(W);h.y=g.rnd(H);h.vx=h.vy=0;g.tone(200,.3,"sine",.06,1200);if(Math.random()<.08){boom(g,h.x,h.y,7);die(g)}}},
 update(g){const s=g.s,h=s.sh;
  if(h.dead){if(--h.dead==0){if(s.lives<=0){g.over();return}ship(g)}}else{
   if(g.held("left"))h.a-=.08;if(g.held("right"))h.a+=.08;s.thr=g.held("up");if(s.thr){h.vx+=Math.cos(h.a)*.09;h.vy+=Math.sin(h.a)*.09;if(g.ticks%6==0)g.noise(.06,.03,0,400)}
   h.vx*=.99;h.vy*=.99;const sp=Math.hypot(h.vx,h.vy);if(sp>4){h.vx*=4/sp;h.vy*=4/sp}h.x+=h.vx;h.y+=h.vy;wrap(h);if(h.inv)h.inv--}
  s.b=s.b.filter(b=>{b.x+=b.vx;b.y+=b.vy;wrap(b);return--b.t>0});
  s.parts=s.parts.filter(p=>{p.x+=p.vx;p.y+=p.vy;return--p.t>0});
  const nr=[];s.rocks.forEach(r=>{r.x+=r.vx;r.y+=r.vy;r.rot+=r.vr;wrap(r);let hit=false;
   for(let i=0;i<s.b.length;i++){const b=s.b[i];if(Math.hypot(b.x-r.x,b.y-r.y)<R[r.sz]){s.b.splice(i,1);hit=true;break}}
   if(!hit&&!h.dead&&!h.inv&&Math.hypot(h.x-r.x,h.y-r.y)<R[r.sz]+3){hit=true;boom(g,h.x,h.y,12);die(g)}
   if(hit){g.add([0,100,50,20][r.sz]);boom(g,r.x,r.y,r.sz*3);g.noise(.15+r.sz*.08,.1,0,500+r.sz*150);if(r.sz>1){nr.push(rock(g,r.x,r.y,r.sz-1),rock(g,r.x,r.y,r.sz-1))}}else nr.push(r)});
  s.rocks=nr;if(g.score>=s.next){s.next+=10000;s.lives++;g.sfx("power")}
  if(!s.rocks.length){s.wave++;wave(g);g.sfx("start")}},
 draw(g){const s=g.s,h=s.sh;g.cls(0);for(let i=0;i<40;i++)g.px((i*97)%W,(i*61+i*i)%H,i%7?5:6);
  s.rocks.forEach(r=>{const n=r.pts.length;let px,py,fx,fy;for(let i=0;i<=n;i++){const a=r.rot+i/n*6.283,rr=R[r.sz]*r.pts[i%n],x=r.x+Math.cos(a)*rr,y=r.y+Math.sin(a)*rr;if(i)g.line(px,py,x,y,6);else{fx=x;fy=y}px=x;py=y}});
  s.b.forEach(b=>g.rect(b.x-1,b.y-1,2,2,10));s.parts.forEach(p=>g.px(p.x,p.y,p.c));
  if(!h.dead&&!(h.inv&&(h.inv>>2)%2)){const P=(a,d)=>[h.x+Math.cos(h.a+a)*d,h.y+Math.sin(h.a+a)*d];const n=P(0,7),l=P(2.5,6),r=P(-2.5,6),bk=P(Math.PI,3);
   g.line(...n,...l,7);g.line(...n,...r,7);g.line(...l,...bk,7);g.line(...r,...bk,7);if(s.thr&&g.ticks%4<2){const f=P(Math.PI,7);g.line(...bk,...f,9)}}
  g.text(g.score,4,4,7,2);g.text("WAVE "+s.wave,W-4,4,6,1,"r");for(let i=0;i<s.lives;i++){const x=8+i*9,y=20;g.line(x,y-4,x-3,y+3,7);g.line(x,y-4,x+3,y+3,7);g.line(x-2,y+1,x+2,y+1,7)}}});
function boom(g,x,y,n){for(let i=0;i<n+4;i++){const a=Math.random()*6.28,v=Math.random()*1.6;g.s.parts.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v,t:20+g.ri(20),c:g.pick([7,9,10,6])})}}
function die(g){const s=g.s;s.sh.dead=90;s.lives--;g.sfx("boom")}
})();
