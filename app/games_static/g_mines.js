// Mine Sweep: original mine-finding logic puzzle (inspired by Minesweeper).
(()=>{const W=256,H=224,CFG=[{w:9,h:9,m:10,cs:18},{w:16,h:16,m:40,cs:12},{w:30,h:16,m:99,cs:8}];
const NUMC=[0,12,11,8,1,4,13,0,5];
function cfg(g){return CFG[g.mode]}
function geo(g){const c=cfg(g);return{ox:Math.floor((W-c.w*c.cs)/2),oy:20+Math.floor((H-20-c.h*c.cs)/2)}}
function place(g,sx,sy){const s=g.s,c=cfg(g);let n=0;while(n<c.m){const x=g.ri(c.w),y=g.ri(c.h);if(s.mine[y][x]||(Math.abs(x-sx)<=1&&Math.abs(y-sy)<=1))continue;s.mine[y][x]=1;n++}
 for(let y=0;y<c.h;y++)for(let x=0;x<c.w;x++){let k=0;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)if(s.mine[y+dy]&&s.mine[y+dy][x+dx])k++;s.num[y][x]=k}s.placed=true}
function reveal(g,x,y){const s=g.s,c=cfg(g);if(!s.placed)place(g,x,y);if(s.flag[y][x]||s.open[y][x])return;
 if(s.mine[y][x]){s.open[y][x]=1;s.boom={x,y};for(let yy=0;yy<c.h;yy++)for(let xx=0;xx<c.w;xx++)if(s.mine[yy][xx])s.open[yy][xx]=1;g.sfx("boom");g.over("BOOM! YOU HIT A MINE");return}
 const st=[[x,y]];let n=0;while(st.length){const [a,b]=st.pop();if(a<0||b<0||a>=c.w||b>=c.h||s.open[b][a]||s.flag[b][a])continue;s.open[b][a]=1;n++;s.left--;if(s.num[b][a]==0)for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)if(dx||dy)st.push([a+dx,b+dy])}
 g.tone(n>1?700:500,.04,"square",.04);if(s.left==0){for(let yy=0;yy<c.h;yy++)for(let xx=0;xx<c.w;xx++)if(s.mine[yy][xx])s.flag[yy][xx]=1;g.win("CLEARED IN "+BNG.fmtT(g.score))}}
function chord(g,x,y){const s=g.s,c=cfg(g);if(!s.open[y][x]||!s.num[y][x])return false;let f=0;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)if(s.flag[y+dy]&&s.flag[y+dy][x+dx])f++;if(f!=s.num[y][x])return false;
 for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const a=x+dx,b=y+dy;if(a>=0&&b>=0&&a<c.w&&b<c.h&&!s.open[b][a]&&g.state=="play")reveal(g,a,b)}return true}
function flag(g,x,y){const s=g.s;if(s.open[y][x])return;s.flag[y][x]^=1;g.tone(s.flag[y][x]?880:330,.05)}
BNG.register({id:"mines",name:"Mine Sweep",inspired:"Minesweeper-style logic puzzles",cats:["Puzzle","Classic"],w:W,h:H,best:"time",modes:["EASY 9X9","MEDIUM 16X16","HARD 30X16"],
 desc:"Uncover every safe square without hitting a mine. Each number shows how many mines touch that square. Your first reveal is always safe. Best times are kept for each size.",
 controls:["Arrows / WASD: move cursor","Space / Enter: reveal (on a number: open its neighbors)","F: flag a square","Mouse: left reveal, right flag"],
 init(g){const s=g.s,c=cfg(g);const mk=()=>Array.from({length:c.h},()=>new Array(c.w).fill(0));s.mine=mk();s.num=mk();s.open=mk();s.flag=mk();s.placed=false;s.left=c.w*c.h-c.m;s.cx=Math.floor(c.w/2);s.cy=Math.floor(c.h/2)},
 key(g,a,code){const s=g.s,c=cfg(g);if(a=="left")s.cx=(s.cx+c.w-1)%c.w;else if(a=="right")s.cx=(s.cx+1)%c.w;else if(a=="up")s.cy=(s.cy+c.h-1)%c.h;else if(a=="down")s.cy=(s.cy+1)%c.h;
  else if(code=="KeyF")flag(g,s.cx,s.cy);else if(a=="fire"||a=="enter"){if(!chord(g,s.cx,s.cy))reveal(g,s.cx,s.cy)}if(["left","right","up","down"].includes(a))g.sfx("move")},
 click(g,x,y,btn){const s=g.s,c=cfg(g),{ox,oy}=geo(g);const cx=Math.floor((x-ox)/c.cs),cy=Math.floor((y-oy)/c.cs);if(cx<0||cy<0||cx>=c.w||cy>=c.h)return;s.cx=cx;s.cy=cy;if(btn==2)flag(g,cx,cy);else if(!chord(g,cx,cy))reveal(g,cx,cy)},
 update(){},
 draw(g){const s=g.s,c=cfg(g),{ox,oy}=geo(g),cs=c.cs;g.cls(1);let fl=0;s.flag.forEach(r=>r.forEach(v=>fl+=v));
  g.text("MINES "+(c.m-fl),4,6,8);g.text("TIME "+BNG.fmtT(g.score),W/2,6,10,1,"c");g.text(g.def.modes[g.mode],W-4,6,6,1,"r");
  for(let y=0;y<c.h;y++)for(let x=0;x<c.w;x++){const X=ox+x*cs,Y=oy+y*cs;
   if(s.open[y][x]){g.rect(X,Y,cs,cs,s.boom&&s.boom.x==x&&s.boom.y==y?8:6);g.rect(X,Y,cs,1,5);g.rect(X,Y,1,cs,5);
    if(s.mine[y][x]){g.circ(X+cs/2,Y+cs/2,Math.max(1,cs/2-3),0);g.px(X+cs/2-1,Y+cs/2-1,7)}else if(s.num[y][x]){const sc=cs>=16?2:1;g.text(s.num[y][x],X+cs/2+(sc==2?0:1),Y+cs/2-Math.floor(5*sc/2),NUMC[s.num[y][x]],sc,"c")}}
   else{g.rect(X,Y,cs,cs,13);g.rect(X,Y,cs,1,7);g.rect(X,Y,1,cs,7);g.rect(X,Y+cs-1,cs,1,5);g.rect(X+cs-1,Y,1,cs,5);
    if(s.flag[y][x]){const k=Math.max(1,Math.floor(cs/8));g.rect(X+cs/2,Y+2*k,k,cs-4*k,0);g.rect(X+cs/2-3*k,Y+2*k,3*k,2*k,8);g.rect(X+cs/2-2*k,Y+cs-3*k,4*k,k,0);if(g.state=="over"&&!g.won&&!s.mine[y][x]){g.line(X+1,Y+1,X+cs-2,Y+cs-2,8)}}}}
  g.box(ox+s.cx*cs,oy+s.cy*cs,cs,cs,(g.ticks>>3)%2?10:9)}});
})();
