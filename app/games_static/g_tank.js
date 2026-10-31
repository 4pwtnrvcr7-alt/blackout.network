// Tank Sector: original first-person wireframe tank battle (inspired by Battlezone).
(()=>{const W=256,H=200,HZ=110,F=160,CAMY=12,NEAR=4,SPAN=1600;
const CUBE={v:[[-1,0,-1],[1,0,-1],[1,0,1],[-1,0,1],[-1,2,-1],[1,2,-1],[1,2,1],[-1,2,1]],e:[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]]};
const PYR={v:[[-1,0,-1],[1,0,-1],[1,0,1],[-1,0,1],[0,2.4,0]],e:[[0,1],[1,2],[2,3],[3,0],[0,4],[1,4],[2,4],[3,4]]};
const TANK={v:[[-10,0,-14],[10,0,-14],[10,0,14],[-10,0,14],[-12,5,-17],[12,5,-17],[12,5,17],[-12,5,17],[-6,5,-6],[6,5,-6],[6,5,8],[-6,5,8],[0,10,2],[0,8,-1],[0,8,-26]],
 e:[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7],[8,9],[9,10],[10,11],[11,8],[8,12],[9,12],[10,12],[11,12],[13,14]]};
function proj(s,x,y,z){const dx=x-s.px,dz=z-s.pz,c=Math.cos(s.a),sn=Math.sin(s.a);return[dx*c-dz*sn,y-CAMY,dx*sn+dz*c]}
function seg(g,a,b,col){let [x1,y1,z1]=a,[x2,y2,z2]=b;if(z1<NEAR&&z2<NEAR)return;if(z1<NEAR){const t=(NEAR-z1)/(z2-z1);x1+=(x2-x1)*t;y1+=(y2-y1)*t;z1=NEAR}if(z2<NEAR){const t=(NEAR-z2)/(z1-z2);x2+=(x1-x2)*t;y2+=(y1-y2)*t;z2=NEAR}
 const X1=W/2+x1/z1*F,Y1=HZ-y1/z1*F,X2=W/2+x2/z2*F,Y2=HZ-y2/z2*F;if(Math.max(X1,X2)<-50||Math.min(X1,X2)>W+50)return;g.line(g.clamp(X1,-300,600),g.clamp(Y1,-300,600),g.clamp(X2,-300,600),g.clamp(Y2,-300,600),col)}
function model(g,m,x,z,sc,ang,col,ysc){const s=g.s,c=Math.cos(ang),sn=Math.sin(ang);const P=m.v.map(([vx,vy,vz])=>proj(s,x+(vx*c-vz*sn)*sc,vy*(ysc||sc),z+(vx*sn+vz*c)*sc));m.e.forEach(([i,j])=>seg(g,P[i],P[j],col))}
const rel=(s,o)=>{let dx=o.x-s.px,dz=o.z-s.pz;dx=((dx%SPAN)+SPAN*1.5)%SPAN-SPAN/2;dz=((dz%SPAN)+SPAN*1.5)%SPAN-SPAN/2;return[s.px+dx,s.pz+dz]};
function enemy(g){const s=g.s,a=Math.random()*6.28,d=450+g.rnd(300);s.en={x:s.px+Math.sin(a)*d,z:s.pz+Math.cos(a)*d,a:0,cool:120,hp:1,turn:0};s.ebul=null}
BNG.register({id:"tank",name:"Tank Sector",inspired:"Battlezone-style wireframe tank battles",cats:["Action","Arcade","Classic"],w:W,h:H,
 desc:"Drive a tank across a green wireframe battlefield of cubes and pyramids. Track the enemy on radar, line up your shot, and dodge its shells. Obstacles stop shells too.",
 controls:["Up/Down: drive forward/back","Left/Right: turn","Space: fire one shell"],
 init(g){const s=g.s;s.px=0;s.pz=0;s.a=0;s.lives=3;s.obs=[];for(let i=0;i<26;i++){let x,z;do{x=g.rnd(SPAN)-SPAN/2;z=g.rnd(SPAN)-SPAN/2}while(Math.hypot(x,z)<80);s.obs.push({x,z,t:g.ri(2),r:g.ri(6)*.3})}s.bul=null;s.parts=[];s.hit=0;s.kills=0;enemy(g)},
 key(g,a){const s=g.s;if(a=="fire"&&!s.bul&&!s.hit){s.bul={x:s.px+Math.sin(s.a)*10,z:s.pz+Math.cos(s.a)*10,vx:Math.sin(s.a)*6,vz:Math.cos(s.a)*6,t:110};g.sfx("shoot");g.noise(.2,.08,0,600)}},
 update(g){const s=g.s;if(s.hit){if(--s.hit==0){s.lives--;if(s.lives<=0){g.over("TANK DESTROYED");return}enemy(g)}return}
  if(g.held("left"))s.a-=.025;if(g.held("right"))s.a+=.025;let mv=(g.held("up")?1.2:0)-(g.held("down")?.8:0);
  if(mv){const nx=s.px+Math.sin(s.a)*mv,nz=s.pz+Math.cos(s.a)*mv;const blocked=s.obs.some(o=>{const [ox,oz]=rel(s,o);return Math.hypot(ox-nx,oz-nz)<26});if(!blocked){s.px=nx;s.pz=nz}else if(g.ticks%10==0)g.sfx("bump");if(g.ticks%8==0)g.tone(55,.08,"sawtooth",.03)}
  const e=s.en,dx=s.px-e.x,dz=s.pz-e.z,dist=Math.hypot(dx,dz),want=Math.atan2(dx,dz);let da=Math.atan2(Math.sin(want-e.a),Math.cos(want-e.a));
  e.a+=g.clamp(da,-.012-s.kills*.001,.012+s.kills*.001);if(dist>120){const nx=e.x+Math.sin(e.a)*(.5+s.kills*.05),nz=e.z+Math.cos(e.a)*(.5+s.kills*.05);if(!s.obs.some(o=>{const [ox,oz]=rel(s,o);return Math.hypot(ox-nx,oz-nz)<30}))e.x=nx,e.z=nz;else e.a+=.05}
  if(--e.cool<=0&&Math.abs(da)<.08&&!s.ebul&&dist<700){e.cool=Math.max(70,190-s.kills*12);s.ebul={x:e.x,z:e.z,vx:Math.sin(e.a)*3.4,vz:Math.cos(e.a)*3.4,t:240};g.tone(150,.25,"square",.05,60)}
  const stop=b=>s.obs.some(o=>{const [ox,oz]=rel(s,o);return Math.hypot(ox-b.x,oz-b.z)<18});
  if(s.bul){const b=s.bul;b.x+=b.vx;b.z+=b.vz;if(--b.t<=0||stop(b))s.bul=null;else if(Math.hypot(b.x-e.x,b.z-e.z)<22){s.bul=null;s.kills++;g.add(1000);g.sfx("boom");for(let i=0;i<14;i++)s.parts.push({x:e.x,z:e.z,y:4,vx:g.rnd(4)-2,vz:g.rnd(4)-2,vy:2+g.rnd(3),t:60});enemy(g)}}
  if(s.ebul){const b=s.ebul;b.x+=b.vx;b.z+=b.vz;if(--b.t<=0||stop(b))s.ebul=null;else if(Math.hypot(b.x-s.px,b.z-s.pz)<14){s.ebul=null;s.hit=120;g.sfx("boom");g.sfx("die")}}
  s.parts=s.parts.filter(p=>{p.x+=p.vx;p.z+=p.vz;p.y+=p.vy;p.vy-=.15;if(p.y<0){p.y=0;p.vy*=-.4}return--p.t>0})},
 draw(g){const s=g.s;g.cls(0);
  for(let i=0;i<24;i++){const ang=i/24*6.283,rel=Math.atan2(Math.sin(ang-s.a),Math.cos(ang-s.a));if(Math.abs(rel)>1)continue;const x=W/2+Math.tan(rel)*F,hh=[10,22,14,30,8,18][i%6];
   const x2=W/2+Math.tan(Math.min(1.2,rel+.13))*F;g.line(x,HZ,(x+x2)/2,HZ-hh,3);g.line((x+x2)/2,HZ-hh,x2,HZ,3)}
  g.rect(0,HZ,W,1,11);
  s.obs.forEach(o=>{const [x,z]=rel(s,o);model(g,o.t?PYR:CUBE,x,z,12,o.r,11)});
  const e=s.en;model(g,TANK,e.x,e.z,1,e.a,8,1);
  s.parts.forEach(p=>{const q=proj(s,p.x,p.y,p.z);if(q[2]>NEAR){const X=W/2+q[0]/q[2]*F,Y=HZ-q[1]/q[2]*F;g.rect(X,Y,2,2,9)}});
  [s.bul,s.ebul].forEach((b,i)=>{if(!b)return;const q=proj(s,b.x,6,b.z);if(q[2]>NEAR){const X=W/2+q[0]/q[2]*F,Y=HZ-q[1]/q[2]*F,r=Math.max(1,30/q[2]);g.circ(X,Y,r,i?8:10)}});
  g.rect(W/2-8,HZ-30,6,1,11);g.rect(W/2+3,HZ-30,6,1,11);g.rect(W/2,HZ-38,1,5,11);g.rect(W/2,HZ-27,1,5,11);
  const RX=W/2,RY=20,RR=16;g.circ(RX,RY,RR,1);g.circ(RX,RY,RR,3,false);g.line(RX,RY,RX-RR*.5,RY-RR*.85,3);g.line(RX,RY,RX+RR*.5,RY-RR*.85,3);
  const dx=e.x-s.px,dz=e.z-s.pz,c=Math.cos(s.a),sn=Math.sin(s.a),rx=dx*c-dz*sn,rz=dx*sn+dz*c,d=Math.hypot(rx,rz),k=Math.min(RR-2,d/50);if(d>0&&(g.ticks>>3)%3)g.rect(RX+rx/d*k-1,RY-rz/d*k-1,2,2,8);
  g.text("SCORE "+g.score,3,3,11);g.text("TANKS "+s.lives,W-3,3,11,1,"r");
  const da=Math.atan2(Math.sin(Math.atan2(dx,dz)-s.a),Math.cos(Math.atan2(dx,dz)-s.a));if(Math.abs(da)>.6)g.text(da>0?"ENEMY TO RIGHT >":"< ENEMY TO LEFT",W/2,HZ+70,8,1,"c");else if(d<260)g.text("ENEMY IN RANGE",W/2,HZ+70,10,1,"c");
  g.rect(0,H-24,W,24,0);g.line(0,H-24,60,HZ+20,3);g.line(W,H-24,W-60,HZ+20,3);
  if(s.hit){for(let i=0;i<9;i++){const a=i*.7+1;g.line(W/2,HZ,W/2+Math.cos(a)*200,HZ+Math.sin(a)*200,7)}g.text("HIT!",W/2,40,8,3,"c")}}});
})();
