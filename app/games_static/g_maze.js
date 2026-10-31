// Maze Muncher: original maze-chase game (inspired by Pac-Man). Original maze layout, sprites and ghost AI.
(()=>{const T=8,OY=12,MW=21,MH=21;
const MAP=["#####################","#.........#.........#","#o##.####.#.####.##o#","#...................#","#.##.#.#######.#.##.#","#....#....#....#....#","####.####.#.####.####","####.#.........#.####","####.#.###-###.#.####","    ...#GGGGG#...    ","####.#.#######.#.####","####.#.........#.####","####.#.#######.#.####","#.........#.........#","#.##.####.#.####.##.#","#o.#.............#.o#","##.#.#.#######.#.#.##","#....#....#....#....#","#.#######.#.#######.#","#...................#","#####################"];
const D=[{x:0,y:-1},{x:-1,y:0},{x:0,y:1},{x:1,y:0}],OPP=[2,3,0,1];
const GCOL=[8,14,12,9],CORNER=[[19,-2],[1,-2],[19,22],[1,22]];
const SPOOK=["...7....","..1111..",".111111.","11777711","11700711","11777711","11111111"];
const wall=(x,y)=>{if(y<0||y>=MH)return true;x=(x+MW)%MW;const c=MAP[y][x];return c=="#"||c=="G"||c=="-"};
const posOf=e=>({x:e.tx+D[e.d<0?0:e.d].x*e.p,y:e.ty+D[e.d<0?0:e.d].y*e.p});
function reset(g){const s=g.s;s.pl={tx:10,ty:15,p:0,d:-1,want:1};s.gh=[0,1,2,3].map(i=>({i,tx:10,ty:7,p:0,d:1,home:i>0,rel:i*150,fr:0,eat:false}));s.fright=0;s.combo=0;s.mt=0;s.mi=0;s.ready=100}
function level(g){const s=g.s;s.dots=MAP.map(r=>r.split("").map(c=>c=="."?1:c=="o"?2:0));s.left=s.dots.flat().filter(Boolean).length;s.bonus=null;s.bonusDone=false;reset(g)}
const MODES=[420,1200,420,1200,300,1e9];
function target(g,gh){const s=g.s,p=s.pl,pd=D[p.d<0?p.want:p.d];if(s.mi%2==0&&MODES[s.mi]<1e9)return CORNER[gh.i];
 if(gh.i==0)return[p.tx,p.ty];if(gh.i==1)return[p.tx+pd.x*4,p.ty+pd.y*4];
 if(gh.i==2){const r=s.gh[0];return[2*(p.tx+pd.x*2)-r.tx,2*(p.ty+pd.y*2)-r.ty]}
 return Math.hypot(gh.tx-p.tx,gh.ty-p.ty)>6?[p.tx,p.ty]:CORNER[3]}
function ghostDecide(g,gh){const opts=[0,1,2,3].filter(d=>d!=OPP[gh.d]&&!wall(gh.tx+D[d].x,gh.ty+D[d].y));if(!opts.length){gh.d=OPP[gh.d];return}
 if(gh.fr>0){gh.d=g.pick(opts);return}const [x,y]=target(g,gh);let best=opts[0],bd=1e9;opts.forEach(d=>{const dd=(gh.tx+D[d].x-x)**2+(gh.ty+D[d].y-y)**2;if(dd<bd){bd=dd;best=d}});gh.d=best}
function adv(e,sp,decide){e.p+=sp;while(e.p>=1){e.tx=(e.tx+D[e.d].x+MW)%MW;e.ty+=D[e.d].y;e.p-=1;decide(e);if(e.d<0){e.p=0;return}}}
BNG.register({id:"maze",name:"Maze Muncher",inspired:"Pac-Man-style maze chase games",cats:["Arcade","Classic"],w:MW*T,h:MH*T+OY+12,
 desc:"Clear every dot from an original maze while four one-eyed spooks hunt you, each with its own chase plan. Power pellets turn the tables for a few seconds.",
 controls:["Arrows / WASD: steer (you can pre-turn)","Power pellets let you eat spooks"],
 init(g){const s=g.s;s.lives=3;s.lv=1;level(g)},
 key(g,a){const i={up:0,left:1,down:2,right:3}[a];if(i==null)return;const p=g.s.pl;p.want=i;if(p.d>=0&&i==OPP[p.d]&&p.p>0){p.tx=(p.tx+D[p.d].x+MW)%MW;p.ty+=D[p.d].y;p.p=1-p.p;p.d=i}},
 update(g){const s=g.s;if(s.ready>0){s.ready--;return}
  if(s.dying>0){if(--s.dying==0){s.lives--;if(s.lives<=0){g.over("CAUGHT!");return}reset(g)}return}
  if(s.clear>0){if(--s.clear==0){s.lv++;level(g)}return}
  const p=s.pl,psp=Math.min(.16,.1+s.lv*.006);
  if(p.p==0&&!wall(p.tx+D[p.want].x,p.ty+D[p.want].y))p.d=p.want;
  if(p.d>=0){if(p.p==0&&wall(p.tx+D[p.d].x,p.ty+D[p.d].y))p.d=-1;else adv(p,psp,e=>{if(!wall(e.tx+D[e.want].x,e.ty+D[e.want].y))e.d=e.want;else if(wall(e.tx+D[e.d].x,e.ty+D[e.d].y))e.d=-1})}
  const v=s.dots[p.ty]&&s.dots[p.ty][p.tx];if(v&&p.p<.5){s.dots[p.ty][p.tx]=0;s.left--;if(v==1){g.add(10);g.tone(s.left%2?660:520,.03,"square",.03)}else{g.add(50);s.fright=Math.max(120,480-s.lv*40);s.combo=0;s.gh.forEach(h=>{if(!h.home){h.fr=1;h.d=OPP[h.d]}});g.sfx("power")}
   if(!s.bonusDone&&s.left<140){s.bonusDone=true;s.bonus={x:10,y:11,t:540}}if(s.left<=0){s.clear=90;g.add(500);g.sfx("win");return}}
  if(s.bonus){if(--s.bonus.t<=0)s.bonus=null;else if(p.tx==s.bonus.x&&p.ty==s.bonus.y){g.add(200*s.lv);g.sfx("coin");s.pop={t:60,v:200*s.lv,x:10,y:11};s.bonus=null}}
  if(s.fright>0&&--s.fright==0)s.gh.forEach(h=>h.fr=0);
  if(s.fright<=0){if(++s.mt>=MODES[s.mi]){s.mt=0;s.mi=Math.min(MODES.length-1,s.mi+1);s.gh.forEach(h=>{if(!h.home)h.d=OPP[h.d]})}}
  s.gh.forEach(h=>{if(h.home){if(--h.rel<=0){h.home=false;h.tx=10;h.ty=7;h.p=0;h.d=g.pick([1,3]);h.fr=0}return}
   const sp=(h.fr?.06:Math.min(.15,.09+s.lv*.006))*(h.ty==9&&(h.tx<4||h.tx>16)?.6:1);adv(h,sp,e=>ghostDecide(g,e));
   const a=posOf(h),b=posOf(p);if(Math.abs(a.x-b.x)+Math.abs(a.y-b.y)<.8){if(h.fr){s.combo++;const pts=200*2**(s.combo-1);g.add(pts);s.pop={t:50,v:pts,x:a.x,y:a.y};g.tone(880,.15,"square",.06,1760);h.home=true;h.rel=120;h.fr=0}else{s.dying=90;g.sfx("die")}}});
  if(s.pop&&--s.pop.t<=0)s.pop=null},
 draw(g){const s=g.s;g.cls(0);
  for(let y=0;y<MH;y++)for(let x=0;x<MW;x++){const c=MAP[y][x],X=x*T,Y=OY+y*T;
   if(c=="#"||c=="G"&&false){g.rect(X,Y,T,T,1);if(!wall(x,y-1)||y==0&&0)g.rect(X,Y,T,1,12);if(!wall(x,y+1))g.rect(X,Y+T-1,T,1,12);if(x>0&&!wall(x-1,y))g.rect(X,Y,1,T,12);if(x<MW-1&&!wall(x+1,y))g.rect(X+T-1,Y,1,T,12)}
   else if(c=="-")g.rect(X,Y+3,T,2,14);
   const d=s.dots[y][x];if(d==1)g.rect(X+3,Y+3,2,2,15);else if(d==2&&(g.ticks>>3)%2==0)g.circ(X+4,Y+4,2,15)}
  if(s.bonus){const X=s.bonus.x*T,Y=OY+s.bonus.y*T;g.spr(["...b....","..bbb...",".bb7bb..","bbbbbbb.",".bbbbb..","..bbb...","...b...."],X,Y,{map:{11:11}})}
  const sh=s.clear>0&&(s.clear>>3)%2;
  if(sh)for(let y=0;y<MH;y++)for(let x=0;x<MW;x++)if(MAP[y][x]=="#")g.rect(x*T+2,OY+y*T+2,4,4,7);
  s.gh.forEach(h=>{if(s.dying>0&&s.dying<60)return;let px,py;if(h.home){px=(8+h.i%5)*T-(h.i>2?8:0);py=OY+9*T+Math.round(Math.sin((g.ticks+h.i*20)/8))}else{const q=posOf(h);px=q.x*T;py=OY+q.y*T}
   const fr=h.fr&&!h.home,blink=fr&&s.fright<120&&(s.fright>>3)%2;g.spr(SPOOK,px,py,{map:fr?{1:blink?7:1,7:blink?8:15,0:8}:{1:GCOL[h.i]}});
   const ft=(g.ticks>>3)%2?"1.1.1.1.":".1.1.1.1";g.spr([ft],px,py+7,{map:{1:fr?(blink?7:1):GCOL[h.i]}})});
  const q=posOf(s.pl),cx=q.x*T+3.5,cy=OY+q.y*T+3.5,dir=s.pl.d<0?s.pl.want:s.pl.d,ang=[-Math.PI/2,Math.PI,Math.PI/2,0][dir];
  let mouth=s.pl.d<0?.25:Math.abs(Math.sin(g.ticks/4))*.9;if(s.dying>0)mouth=Math.min(Math.PI,(90-s.dying)/40*Math.PI);
  for(let dy=-4;dy<=4;dy++)for(let dx=-4;dx<=4;dx++){const xx=dx+.5,yy=dy+.5;if(xx*xx+yy*yy>13)continue;let a=Math.atan2(yy,xx)-ang;a=Math.atan2(Math.sin(a),Math.cos(a));if(Math.abs(a)<mouth)continue;g.px(Math.floor(cx)+dx,Math.floor(cy)+dy,10)}
  if(s.pop)g.text(s.pop.v,s.pop.x*T+4,OY+s.pop.y*T-2,12,1,"c");
  g.text("SCORE "+g.score,2,3,7);const b=g.best();g.text("HI "+(b==null?0:Math.max(b,g.score)),g.W-2,3,6,1,"r");
  for(let i=0;i<s.lives;i++)g.circ(6+i*10,g.H-6,3,10);g.text("LEVEL "+s.lv,g.W-2,g.H-8,9,1,"r");
  if(s.ready>0)g.text("READY!",g.W/2,OY+11*T+1,10,1,"c")}});
})();
