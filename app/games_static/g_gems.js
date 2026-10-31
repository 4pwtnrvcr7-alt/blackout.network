// Gem Miner: original falling-boulder cave digger (inspired by Boulder Dash). Procedurally generated caves.
(()=>{const T=16,VW=16,VH=12,OY=16,MW=40,MH=22;
// cells: 0 empty,1 dirt,2 wall,3 steel,4 boulder,5 gem,6 exit,7 player,8 firefly
const MINER=["..4444..",".444444.","..ffff..","..0ff0..","..ffff..",".c9999c.","c.9999.c","..1..1..","..1..1..",".11..11."];
function cave(g){const s=g.s,m=[];for(let y=0;y<MH;y++){m.push([]);for(let x=0;x<MW;x++){let c=1;if(x==0||y==0||x==MW-1||y==MH-1)c=3;else{const r=Math.random();c=r<.13?4:r<.18+.005*s.lv?5:r<.22?0:1}m[y].push(c)}}
 for(let i=0;i<3+s.lv;i++){const y=2+g.ri(MH-4),x=2+g.ri(MW-14),l=4+g.ri(8);for(let k=0;k<l;k++)m[y][x+k]=2}
 s.fl=[];for(let i=0;i<Math.min(5,1+s.lv);i++){const x=8+g.ri(MW-12),y=3+g.ri(MH-6);for(let dy=-1;dy<=1;dy++)for(let dx=-2;dx<=2;dx++)m[y+dy][x+dx]=0;m[y][x]=8;s.fl.push({x,y,d:0})}
 for(let y=1;y<=3;y++)for(let x=1;x<=3;x++)m[y][x]=1;m[2][2]=7;s.p={x:2,y:2};for(let x=1;x<=3;x++)if(m[0][x]!=3)m[0][x]=3;
 const ex={x:MW-3-g.ri(6),y:MH-3-g.ri(5)};m[ex.y][ex.x]=2;s.exit=ex;
 s.m=m;s.fall=m.map(r=>r.map(()=>false));let gems=0;m.forEach(r=>r.forEach(c=>{if(c==5)gems++}));s.need=Math.max(8,Math.floor(gems*.55));s.got=0;s.open=false;s.time=150;s.tick=0;s.dead=0;s.done=0;s.boom=[]}
const DIRS=[[0,-1],[1,0],[0,1],[-1,0]];
function explode(g,cx,cy){const s=g.s;for(let y=cy-1;y<=cy+1;y++)for(let x=cx-1;x<=cx+1;x++){if(s.m[y]&&s.m[y][x]!=null&&s.m[y][x]!=3&&!(x==s.exit.x&&y==s.exit.y)){if(s.m[y][x]==7)s.dead=90;s.m[y][x]=5;s.boom.push({x,y,t:12})}}g.sfx("boom")}
function step(g){const s=g.s,m=s.m;
 const d=g.held("left")?[-1,0]:g.held("right")?[1,0]:g.held("up")?[0,-1]:g.held("down")?[0,1]:null;
 if(d&&!s.dead){const nx=s.p.x+d[0],ny=s.p.y+d[1],c=m[ny][nx];
  if(c==0||c==1||c==5||(c==6)){if(c==5){s.got++;g.add(s.open?20:10);g.sfx("coin");if(s.got>=s.need&&!s.open){s.open=true;m[s.exit.y][s.exit.x]=6;g.sfx("power")}}
   if(c==6){s.done=1;g.add(s.time*5);g.sfx("win");m[s.p.y][s.p.x]=0;m[ny][nx]=7;s.p={x:nx,y:ny};return}if(c==1)g.tone(120,.03,"triangle",.05);m[s.p.y][s.p.x]=0;m[ny][nx]=7;s.p={x:nx,y:ny}}
  else if(c==4&&d[1]==0&&m[ny][nx+d[0]]==0&&!s.fall[ny][nx]&&Math.random()<.6){m[ny][nx+d[0]]=4;m[ny][nx]=7;m[s.p.y][s.p.x]=0;s.p={x:nx,y:ny};g.tone(80,.06,"square",.05)}}
 const nf=m.map(r=>r.map(()=>false));
 for(let y=MH-2;y>=1;y--)for(let x=1;x<MW-1;x++){const c=m[y][x];if(c!=4&&c!=5)continue;const b=m[y+1][x];
  if(b==0){m[y+1][x]=c;m[y][x]=0;nf[y+1][x]=true;continue}
  if(s.fall[y][x]){if(b==7){explode(g,x,y+1);continue}if(b==8){explode(g,x,y+1);g.add(250);continue}g.tone(c==4?70:900,.05,c==4?"triangle":"square",.06)}
  if(b==4||b==5||b==2){if(m[y][x-1]==0&&m[y+1][x-1]==0){m[y][x-1]=c;m[y][x]=0;nf[y][x-1]=true}else if(m[y][x+1]==0&&m[y+1][x+1]==0){m[y][x+1]=c;m[y][x]=0;nf[y][x+1]=true}}}
 s.fall=nf;
 // fireflies: keep a wall on the left (turn left when possible)
 const fl=[];for(let y=1;y<MH-1;y++)for(let x=1;x<MW-1;x++)if(m[y][x]==8)fl.push([x,y]);
 const moved=new Set();fl.forEach(([x,y])=>{if(m[y][x]!=8||moved.has(x+","+y))return;
  if(DIRS.some(([dx,dy])=>m[y+dy][x+dx]==7)){explode(g,x,y);return}
  const f=s.fl.find(q=>q.x==x&&q.y==y)||{x,y,d:0};let moved1=false;for(const t of [3,0,1,2]){const nd=(f.d+t)%4,[dx,dy]=DIRS[nd];if(m[y+dy][x+dx]==0){m[y][x]=0;m[y+dy][x+dx]=8;f.x=x+dx;f.y=y+dy;f.d=nd;moved.add(f.x+","+f.y);moved1=true;break}}
  if(!s.fl.includes(f))s.fl.push(f)});
 s.fl=s.fl.filter(f=>m[f.y][f.x]==8)}
BNG.register({id:"gems",name:"Gem Miner",inspired:"Boulder Dash-style cave diggers",cats:["Puzzle","Action","Classic"],w:VW*T,h:VH*T+OY,
 desc:"Tunnel through a new cave every level to collect enough gems to open the exit. Boulders and gems fall and roll when you dig under them, and fireflies explode on contact.",
 controls:["Arrows / WASD: dig and move","Push single boulders sideways","Collect the gem quota, then reach the exit"],
 init(g){const s=g.s;s.lv=1;s.lives=3;cave(g)},
 update(g){const s=g.s;s.boom=s.boom.filter(b=>--b.t>0);
  if(s.dead){if(--s.dead==0){s.lives--;if(s.lives<=0){g.over("CAVE-IN!");return}cave(g)}return}
  if(s.done){if(++s.done>60){s.lv++;cave(g)}return}
  if(g.ticks%60==0&&--s.time<=0){s.dead=60;g.sfx("die");return}
  if(++s.tick>=7){s.tick=0;step(g)}
  if(s.dead==90)g.sfx("die")},
 draw(g){const s=g.s;g.cls(0);const cx=g.clamp(s.p.x-VW/2+1,0,MW-VW),cy=g.clamp(s.p.y-VH/2+1,0,MH-VH);
  for(let y=0;y<VH;y++)for(let x=0;x<VW;x++){const c=s.m[cy+y][cx+x],X=x*T,Y=OY+y*T;
   if(c==1){g.rect(X,Y,T,T,4);g.px(X+3,Y+4,9);g.px(X+11,Y+9,2);g.px(X+7,Y+13,9);g.px(X+13,Y+2,2)}
   else if(c==2){g.rect(X,Y,T,T,5);g.rect(X,Y+7,T,1,0);g.rect(X+7,Y,1,7,0);g.rect(X+3,Y+8,1,8,0);g.rect(X+12,Y+8,1,8,0)}
   else if(c==3){g.rect(X,Y,T,T,13);g.box(X,Y,T,T,6);g.px(X+3,Y+3,7);g.px(X+12,Y+12,1)}
   else if(c==4){g.circ(X+8,Y+8,7,6);g.circ(X+6,Y+6,3,7);g.circ(X+10,Y+11,2,5)}
   else if(c==5){const f=(g.ticks>>3)%4;for(let i=0;i<7;i++){const w=i<4?i*2+1:13-i*2;g.rect(X+8-w,Y+2+i*1.7,w*2,2,[12,12,7,12][(i+f)%4])}}
   else if(c==6){g.rect(X,Y,T,T,(g.ticks>>3)%2?11:3);g.box(X+2,Y+2,T-4,T-4,7)}
   else if(c==7){g.spr(MINER,X+4,Y+3)}
   else if(c==8){const k=(g.ticks>>2)%4;g.box(X+2+k,Y+2+k,T-4-k*2,T-4-k*2,[9,10,8,14][k]);g.box(X+5,Y+5,6,6,10)}}
  if(!s.open)g.rect((s.exit.x-cx)*T,OY+(s.exit.y-cy)*T,0,0,0);
  s.boom.forEach(b=>{if(b.x>=cx&&b.x<cx+VW&&b.y>=cy&&b.y<cy+VH)g.rect((b.x-cx)*T+b.t/2,OY+(b.y-cy)*T+b.t/2,T-b.t,T-b.t,[7,10,9,8][b.t%4])});
  g.rect(0,0,g.W,OY,0);g.text("GEMS "+s.got+"/"+s.need,3,5,s.open?11:12);g.text("TIME "+s.time,96,5,s.time<30?8:7);g.text("CAVE "+s.lv,150,5,10);g.text(g.score,g.W-3,5,7,1,"r");for(let i=0;i<s.lives;i++)g.rect(196+i*6,5,4,5,9);
  if(s.done)g.text("CAVE CLEARED!",g.W/2,90,11,2,"c")}});
})();
