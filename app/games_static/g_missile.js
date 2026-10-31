// City Defense: original missile-defense game (inspired by Missile Command).
(()=>{const W=256,H=224,GY=208,BASES=[24,128,232],CITIES=[56,80,104,152,176,200];
function wave(g){const s=g.s;s.ammo=[10,10,10];s.todo=8+s.wave*2;s.spawnT=60;s.em=[];s.pm=[];s.ex=[];s.inter=0}
function targets(s){const t=[];s.cities.forEach((c,i)=>{if(c)t.push(CITIES[i])});BASES.forEach((x,i)=>{if(s.ammo[i]>0||Math.random()<.3)t.push(x)});return t}
function spawn(g,x,y){const s=g.s,ts=targets(s);if(!ts.length)return;const tx=g.pick(ts)+g.rnd(6)-3,v=.25+s.wave*.05;const d=Math.hypot(tx-x,GY-y);s.em.push({sx:x,sy:y,x,y,tx,ty:GY,vx:(tx-x)/d*v,vy:(GY-y)/d*v,split:s.wave>=3&&Math.random()<.25&&y<20})}
function fire(g,bi){const s=g.s;if(bi==null){let best=null,bd=1e9;BASES.forEach((x,i)=>{if(s.ammo[i]>0&&Math.abs(x-s.cx)<bd){bd=Math.abs(x-s.cx);best=i}});bi=best}
 if(bi==null||s.ammo[bi]<=0){g.sfx("bad");return}s.ammo[bi]--;const sx=BASES[bi],sy=GY-8,d=Math.hypot(s.cx-sx,s.cy-sy)||1,v=bi==1?5:4;s.pm.push({sx,sy,x:sx,y:sy,tx:s.cx,ty:s.cy,vx:(s.cx-sx)/d*v,vy:(s.cy-sy)/d*v});g.sfx("shoot")}
BNG.register({id:"missile",name:"City Defense",inspired:"Missile Command-style defense games",cats:["Arcade","Action","Classic"],w:W,h:H,
 desc:"Incoming warheads are falling on six original pixel cities. Aim the crosshair and launch counter-missiles from three bases. Their blasts chain through the sky.",
 controls:["Arrows / WASD or mouse: aim","Space / click: fire from nearest base","Z / X / C: fire from left / middle / right base"],
 init(g){const s=g.s;s.cities=[1,1,1,1,1,1];s.wave=1;s.cx=W/2;s.cy=100;s.next=10000;wave(g)},
 mouse(g,x,y){g.s.cx=g.clamp(x,0,W-1);g.s.cy=g.clamp(y,10,GY-16)},
 click(g,x,y){this.mouse(g,x,y);fire(g)},
 key(g,a,code){if(a=="fire")fire(g);else if(code=="KeyZ")fire(g,0);else if(code=="KeyX")fire(g,1);else if(code=="KeyC")fire(g,2)},
 update(g){const s=g.s;if(g.held("left"))s.cx-=3;if(g.held("right"))s.cx+=3;if(g.held("up"))s.cy-=3;if(g.held("down"))s.cy+=3;s.cx=g.clamp(s.cx,0,W-1);s.cy=g.clamp(s.cy,10,GY-16);
  if(s.inter){if(--s.inter==0){s.wave++;wave(g)}return}
  if(s.todo>0&&--s.spawnT<=0){s.spawnT=Math.max(20,90-s.wave*6)+g.ri(40);const n=Math.min(s.todo,1+g.ri(Math.min(4,1+s.wave/2)));for(let i=0;i<n;i++){spawn(g,g.rnd(W),0);s.todo--}}
  s.pm=s.pm.filter(m=>{m.x+=m.vx;m.y+=m.vy;if((m.tx-m.x)*m.vx+(m.ty-m.y)*m.vy<=0){s.ex.push({x:m.tx,y:m.ty,r:0,t:0,mine:1});g.sfx("pop");return false}return true});
  s.ex=s.ex.filter(e=>{e.t++;e.r=e.t<20?e.t*.75:Math.max(0,15-(e.t-20)*.5);return e.t<50});
  s.em=s.em.filter(m=>{m.x+=m.vx;m.y+=m.vy;
   if(s.ex.some(e=>Math.hypot(e.x-m.x,e.y-m.y)<e.r+1)){g.add(25*Math.min(6,s.wave));s.ex.push({x:m.x,y:m.y,r:0,t:0});g.noise(.2,.06,0,1200);return false}
   if(m.split&&m.y>60+g.rnd(30)){m.split=false;for(let i=0;i<2;i++)spawn(g,m.x,m.y)}
   if(m.y>=GY){s.ex.push({x:m.x,y:GY,r:0,t:0});g.sfx("boom");CITIES.forEach((x,i)=>{if(Math.abs(x-m.x)<10)s.cities[i]=0});BASES.forEach((x,i)=>{if(Math.abs(x-m.x)<10)s.ammo[i]=0});return false}return true});
  if(!s.cities.some(Boolean)&&!s.ex.length){g.over("THE CITIES HAVE FALLEN");return}
  if(s.todo<=0&&!s.em.length&&!s.ex.length&&!s.pm.length){const bonus=s.ammo.reduce((a,b)=>a+b,0)*5+s.cities.filter(Boolean).length*100;g.add(bonus);s.lastBonus=bonus;s.inter=120;g.sfx("win");
   if(g.score>=s.next){s.next+=10000;const d=s.cities.indexOf(0);if(d>=0)s.cities[d]=1}}},
 draw(g){const s=g.s;g.cls(0);for(let i=0;i<30;i++)g.px((i*73)%W,(i*41)%150,i%3?1:13);
  g.rect(0,GY,W,H-GY,9);for(let x=0;x<W;x+=6)g.px(x+(x%12?2:0),GY+4,4);
  BASES.forEach((x,i)=>{g.rect(x-12,GY-6,24,6,9);g.rect(x-6,GY-10,12,4,9);for(let k=0;k<s.ammo[i];k++)g.rect(x-10+(k%5)*4,GY-4+Math.floor(k/5)*2,2,1,12)});
  CITIES.forEach((x,i)=>{if(s.cities[i]){g.rect(x-8,GY-6,4,6,12);g.rect(x-4,GY-10,4,10,13);g.rect(x,GY-8,4,8,12);g.rect(x+4,GY-5,4,5,13);for(let k=0;k<4;k++)g.px(x-3+k*2%6,GY-8+k,10)}else{g.rect(x-7,GY-2,14,2,5)}});
  s.em.forEach(m=>{g.line(m.sx,m.sy,m.x,m.y,8);g.px(m.x,m.y,7)});s.pm.forEach(m=>{g.line(m.sx,m.sy,m.x,m.y,12);g.px(m.x,m.y,7);g.px(m.tx-1,m.ty-1,7);g.px(m.tx+1,m.ty+1,7);g.px(m.tx+1,m.ty-1,7);g.px(m.tx-1,m.ty+1,7)});
  s.ex.forEach(e=>g.circ(e.x,e.y,e.r,[7,10,9,8,14][(g.ticks>>1)%5]));
  const c=10;g.rect(s.cx-4,s.cy,3,1,c);g.rect(s.cx+2,s.cy,3,1,c);g.rect(s.cx,s.cy-4,1,3,c);g.rect(s.cx,s.cy+2,1,3,c);
  g.text("SCORE "+g.score,3,3,7);g.text("WAVE "+s.wave,W-3,3,10,1,"r");if(s.inter)g.text("WAVE CLEAR  BONUS "+(s.lastBonus||0),W/2,90,11,1,"c")}});
})();
