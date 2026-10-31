// 2048 and 4096: original sliding-tile merge puzzles (inspired by 2048 by Gabriele Cirulli and its forerunners).
(()=>{
function make(o){const N=o.n,CS=o.cs,GAP=4,BX=(256-(N*CS+(N+1)*GAP))/2,BY=30;
 function empty(s){const e=[];for(let y=0;y<N;y++)for(let x=0;x<N;x++)if(!s.b[y][x])e.push([x,y]);return e}
 function addTile(g){const e=empty(g.s);if(!e.length)return;const [x,y]=g.pick(e);g.s.b[y][x]={v:Math.random()<.9?2:4,born:g.ticks}}
 function canMove(s){for(let y=0;y<N;y++)for(let x=0;x<N;x++){const t=s.b[y][x];if(!t)return true;if(x<N-1&&s.b[y][x+1]&&s.b[y][x+1].v==t.v)return true;if(y<N-1&&s.b[y+1][x]&&s.b[y+1][x].v==t.v)return true}return false}
 function slide(g,dx,dy){const s=g.s;let moved=false,gain=0;const order=[...Array(N).keys()];const xs=dx>0?order.slice().reverse():order,ys=dy>0?order.slice().reverse():order;
  for(let y=0;y<N;y++)for(let x=0;x<N;x++)if(s.b[y][x]){s.b[y][x].m=false;s.b[y][x].fx=x;s.b[y][x].fy=y}
  for(const y of ys)for(const x of xs){const t=s.b[y][x];if(!t)continue;let cx=x,cy=y;
   while(true){const nx=cx+dx,ny=cy+dy;if(nx<0||ny<0||nx>=N||ny>=N)break;const o=s.b[ny][nx];if(!o){s.b[ny][nx]=t;s.b[cy][cx]=null;cx=nx;cy=ny;moved=true;continue}
    if(o.v==t.v&&!o.m&&!t.m){o.v*=2;o.m=true;o.pop=g.ticks;o.fx=t.fx;o.fy=t.fy;s.b[cy][cx]=null;gain+=o.v;moved=true;if(o.v>s.top)s.top=o.v}break}}
  if(!moved){g.sfx("bump");return}s.anim=g.ticks;g.add(gain);gain?g.tone(300+Math.log2(gain)*60,.07,"square",.05):g.sfx("move");addTile(g);
  if(s.top>=o.target&&!s.won){s.won=true;g.add(o.target);g.win(o.target+"! YOU WIN");return}if(!canMove(s))g.over("NO MOVES LEFT")}
 BNG.register({id:o.id,name:o.name,inspired:o.insp,cats:["Puzzle"],w:256,h:224,desc:o.desc,
  controls:["Arrows / WASD: slide all tiles","Equal tiles merge","Reach "+o.target+" to win"],
  init(g){const s=g.s;s.b=Array.from({length:N},()=>new Array(N).fill(null));s.top=2;s.won=false;s.anim=-99;addTile(g);addTile(g)},
  key(g,a){const d={left:[-1,0],right:[1,0],up:[0,-1],down:[0,1]}[a];if(d)slide(g,d[0],d[1])},
  update(){},
  draw(g){const s=g.s;g.cls(o.bg);g.text(o.name,8,8,o.title,2);g.text("SCORE "+g.score,248,6,7,1,"r");const b=g.best();g.text("BEST "+(b==null?"-":b),248,14,6,1,"r");g.text("GOAL "+o.target,128,20,6,1,"c");
   const bw=N*CS+(N+1)*GAP;g.rect(BX,BY,bw,bw,o.board);g.box(BX-1,BY-1,bw+2,bw+2,o.edge);
   for(let y=0;y<N;y++)for(let x=0;x<N;x++)g.rect(BX+GAP+x*(CS+GAP),BY+GAP+y*(CS+GAP),CS,CS,o.cell);
   const k=Math.min(1,(g.ticks-s.anim)/6);
   for(let y=0;y<N;y++)for(let x=0;x<N;x++){const t=s.b[y][x];if(!t)continue;const fx=t.fx??x,fy=t.fy??y,ix=fx+(x-fx)*k,iy=fy+(y-fy)*k;
    let px=BX+GAP+ix*(CS+GAP),py=BY+GAP+iy*(CS+GAP),sz=CS;const born=g.ticks-(t.born??-99);if(born<6){const sh=Math.round((6-born)*CS/14);px+=sh;py+=sh;sz-=sh*2}
    const pop=t.pop!=null&&g.ticks-t.pop<6?2:0;const ci=Math.log2(t.v)-1,col=o.cols[Math.min(ci,o.cols.length-1)];
    g.rect(px-pop,py-pop,sz+pop*2,sz+pop*2,col);g.rect(px-pop,py-pop,sz+pop*2,2,7);g.rect(px-pop,py+sz+pop-2,sz+pop*2,2,0);
    const str=String(t.v),sc=str.length<=2&&CS>=36?3:str.length<=3&&CS>=30?2:1;g.text(str,px+sz/2+1,py+sz/2-Math.floor(5*sc/2)+1,0,sc,"c");g.text(str,px+sz/2,py+sz/2-Math.floor(5*sc/2),o.ink(t.v),sc,"c")}}})}
make({id:"t2048",name:"2048",n:4,cs:42,target:2048,insp:"the 2048 sliding-tile puzzle",bg:1,board:5,cell:13,edge:6,title:10,
 desc:"Slide the 4x4 board in any direction. Matching numbers merge and double. Build a 2048 tile before the board fills up.",
 cols:[15,9,4,8,2,14,10,11,3,12,1,13],ink:v=>v<=4?0:7});
make({id:"t4096",name:"4096",n:5,cs:34,target:4096,insp:"the 2048 sliding-tile puzzle, on a bigger 5x5 board",bg:0,board:1,cell:5,edge:12,title:12,
 desc:"The same merge idea on a roomier 5x5 board with a cool neon palette. Keep merging until a 4096 tile appears.",
 cols:[6,12,1,13,3,11,10,9,14,2,8,7],ink:v=>[6,12,11,10,9,7].includes([6,12,1,13,3,11,10,9,14,2,8,7][Math.min(Math.log2(v)-1,11)])?0:7});
})();
