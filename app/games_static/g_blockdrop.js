// Block Drop: original falling-block puzzle (inspired by Tetris-style games).
(()=>{const BW=10,BH=20,C=10,OX=78,OY=12;
const P={I:[[0,0,0,0],[1,1,1,1],[0,0,0,0],[0,0,0,0]],O:[[1,1],[1,1]],T:[[0,1,0],[1,1,1],[0,0,0]],S:[[0,1,1],[1,1,0],[0,0,0]],Z:[[1,1,0],[0,1,1],[0,0,0]],J:[[1,0,0],[1,1,1],[0,0,0]],L:[[0,0,1],[1,1,1],[0,0,0]]};
const COL={I:12,O:10,T:14,S:11,Z:8,J:13,L:9},NAMES=Object.keys(P);
const rot=m=>m[0].map((_,i)=>m.map(r=>r[i]).reverse());
function bag(s){if(!s.bag.length){s.bag=NAMES.slice();for(let i=s.bag.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[s.bag[i],s.bag[j]]=[s.bag[j],s.bag[i]]}}return s.bag.pop()}
function fits(s,m,x,y){for(let r=0;r<m.length;r++)for(let c=0;c<m[r].length;c++)if(m[r][c]){const X=x+c,Y=y+r;if(X<0||X>=BW||Y>=BH)return false;if(Y>=0&&s.b[Y][X])return false}return true}
function spawn(g){const s=g.s;s.cur={n:s.next,m:P[s.next].map(r=>r.slice())};s.next=bag(s);s.x=Math.floor((BW-s.cur.m[0].length)/2);s.y=-1;s.fall=0;if(!fits(s,s.cur.m,s.x,s.y))g.over("BLOCKS TOPPED OUT")}
function lock(g){const s=g.s,m=s.cur.m;for(let r=0;r<m.length;r++)for(let c=0;c<m[r].length;c++)if(m[r][c]){if(s.y+r<0){g.over("BLOCKS TOPPED OUT");return}s.b[s.y+r][s.x+c]=s.cur.n}
 let n=0;for(let y=BH-1;y>=0;y--)if(s.b[y].every(v=>v)){s.b.splice(y,1);s.b.unshift(new Array(BW).fill(0));n++;y++}
 if(n){g.add([0,100,300,500,800][n]*s.level);s.lines+=n;s.flash=10;g.sfx("line");s.level=1+Math.floor(s.lines/10)}else g.sfx("drop");spawn(g)}
BNG.register({id:"blockdrop",name:"Block Drop",inspired:"Tetris-style falling-block puzzles",cats:["Puzzle","Classic"],w:256,h:224,
 desc:"Rotate and slide falling seven-block shapes to complete full rows. Clearing several rows at once scores more, and every 10 rows the drop speeds up.",
 controls:["Left/Right: move","Up / X: rotate","Z: rotate back","Down: soft drop","Space: hard drop"],
 init(g){const s=g.s;s.b=Array.from({length:BH},()=>new Array(BW).fill(0));s.bag=[];s.next=bag(s);s.level=1;s.lines=0;s.flash=0;spawn(g)},
 key(g,a,code){const s=g.s;if(!s.cur)return;
  if(a=="left"||a=="right"){const d=a=="left"?-1:1;if(fits(s,s.cur.m,s.x+d,s.y)){s.x+=d;g.sfx("move")}}
  else if(a=="down"){if(fits(s,s.cur.m,s.x,s.y+1)){s.y++;g.add(1);s.fall=0}else lock(g)}
  else if(a=="up"||code=="KeyX"||code=="KeyZ"){let m=rot(s.cur.m);if(code=="KeyZ")m=rot(rot(m));for(const k of [0,-1,1,-2,2])if(fits(s,m,s.x+k,s.y)){s.cur.m=m;s.x+=k;g.sfx("click");break}}
  else if(a=="fire"){let d=0;while(fits(s,s.cur.m,s.x,s.y+1)){s.y++;d++}g.add(d*2);lock(g)}},
 update(g){const s=g.s;if(s.flash)s.flash--;if(++s.fall>=Math.max(3,48-(s.level-1)*5)){s.fall=0;if(fits(s,s.cur.m,s.x,s.y+1))s.y++;else lock(g)}},
 draw(g){const s=g.s;g.cls(1);for(let i=0;i<14;i++)for(let j=0;j<16;j++)if((i+j)%3==0)g.px(i*19+7,j*15+4,13);
  const cell=(x,y,c)=>{g.rect(x,y,C,C,c);g.rect(x,y,C,1,7);g.rect(x,y,1,C,7);g.rect(x+1,y+C-1,C-1,1,0);g.rect(x+C-1,y+1,1,C-1,0);g.rect(x+3,y+3,3,3,7)};
  g.rect(OX-3,OY-3,BW*C+6,BH*C+6,6);g.rect(OX-2,OY-2,BW*C+4,BH*C+4,5);g.rect(OX,OY,BW*C,BH*C,s.flash?2:0);
  for(let y=0;y<BH;y++)for(let x=0;x<BW;x++)if(s.b[y][x])cell(OX+x*C,OY+y*C,COL[s.b[y][x]]);
  if(s.cur){let gy=s.y;while(fits(s,s.cur.m,s.x,gy+1))gy++;s.cur.m.forEach((r,ri)=>r.forEach((v,ci)=>{if(v&&gy+ri>=0)g.box(OX+(s.x+ci)*C,OY+(gy+ri)*C,C,C,5)}));
   s.cur.m.forEach((r,ri)=>r.forEach((v,ci)=>{if(v&&s.y+ri>=0)cell(OX+(s.x+ci)*C,OY+(s.y+ri)*C,COL[s.cur.n])}))}
  g.text("BLOCK",8,14,10,2);g.text("DROP",8,28,10,2);g.text("SCORE",8,60,6);g.text(g.score,8,68,7);g.text("LINES",8,84,6);g.text(s.lines,8,92,7);g.text("LEVEL",8,108,6);g.text(s.level,8,116,7);
  g.text("NEXT",190,14,6);g.rect(188,22,48,40,0);const nm=P[s.next];nm.forEach((r,ri)=>r.forEach((v,ci)=>{if(v)cell(192+ci*C,28+ri*C,COL[s.next])}))}});
})();
