// 81: original Sudoku-style 9x9 number puzzle with generated, unique-solution puzzles in three difficulties.
(()=>{const W=256,H=224,CS=22,BX=6,BY=14;
function solve(b,count){// returns number of solutions up to `count`; fills b with first solution when count==1
 let best=-1,bc=10,cand=null;for(let i=0;i<81;i++)if(!b[i]){const c=cands(b,i);if(c.length<bc){bc=c.length;best=i;cand=c;if(bc==0)return 0}}
 if(best<0)return 1;let n=0;for(const v of cand){b[best]=v;n+=solve(b,count-n);if(n>=count){if(count==1)return n;b[best]=0;return n}}b[best]=0;return n}
function cands(b,i){const r=Math.floor(i/9),c=i%9,used=new Set();for(let k=0;k<9;k++){used.add(b[r*9+k]);used.add(b[k*9+c])}const br=r-r%3,bc=c-c%3;for(let y=0;y<3;y++)for(let x=0;x<3;x++)used.add(b[(br+y)*9+bc+x]);
 const out=[];for(let v=1;v<=9;v++)if(!used.has(v))out.push(v);for(let k=out.length-1;k>0;k--){const j=Math.floor(Math.random()*(k+1));[out[k],out[j]]=[out[j],out[k]]}return out}
function generate(clues){const sol=new Array(81).fill(0);solve(sol,1);const p=sol.slice();const order=[...Array(81).keys()].sort(()=>Math.random()-.5);let filled=81;
 for(const i of order){if(filled<=clues)break;const v=p[i];p[i]=0;const t=p.slice();if(solve(t,2)!=1)p[i]=v;else filled--}return{p,sol}}
const CLUES=[40,32,26];
function conflicts(b){const bad=new Set();const grp=[];for(let k=0;k<9;k++){grp.push([...Array(9).keys()].map(j=>k*9+j));grp.push([...Array(9).keys()].map(j=>j*9+k));grp.push([...Array(9).keys()].map(j=>(Math.floor(k/3)*3+Math.floor(j/3))*9+(k%3)*3+j%3))}
 grp.forEach(gp=>{const seen={};gp.forEach(i=>{const v=b[i];if(!v)return;(seen[v]=seen[v]||[]).push(i)});Object.values(seen).forEach(a=>{if(a.length>1)a.forEach(i=>bad.add(i))})});return bad}
function put(g,v){const s=g.s,i=s.cy*9+s.cx;if(s.giv[i])return g.sfx("bad");if(s.notes&&v){s.nt[i]^=1<<v;g.sfx("click");return}s.b[i]=v;s.nt[i]=0;s.bad=conflicts(s.b);
 if(v){if(v!=s.sol[i])s.wrong++;g.sfx(s.bad.has(i)?"bad":"place")}else g.sfx("move");if(s.b.every((x,k)=>x==s.sol[k])){g.win("SOLVED IN "+BNG.fmtT(g.score))}}
BNG.register({id:"n81",name:"81",inspired:"Sudoku-style number placement puzzles",cats:["Puzzle"],w:W,h:H,best:"time",modes:["EASY","MEDIUM","HARD"],
 desc:"Fill the 81-cell grid so every row, column and 3x3 box holds 1 to 9 exactly once. Each puzzle is freshly generated with one solution. Clashes show in red, and best times are kept per difficulty.",
 controls:["Arrows / WASD: move","1-9: place a number","Backspace / Delete / 0: clear","N: pencil-notes mode","H: hint (+30 s)"],
 init(g){const s=g.s;const {p,sol}=generate(CLUES[g.mode]);s.b=p.slice();s.giv=p.map(v=>!!v);s.sol=sol;s.nt=new Array(81).fill(0);s.cx=4;s.cy=4;s.bad=new Set();s.wrong=0;s.notes=false;s.hints=0},
 key(g,a,code){const s=g.s;if(a=="left")s.cx=(s.cx+8)%9;else if(a=="right")s.cx=(s.cx+1)%9;else if(a=="up")s.cy=(s.cy+8)%9;else if(a=="down")s.cy=(s.cy+1)%9;
  else if(a&&/^[1-9]$/.test(a))put(g,+a);else if(a=="back"||a=="0")put(g,0);else if(code=="KeyN"){s.notes=!s.notes;g.sfx("click")}
  else if(code=="KeyH"){const i=s.cy*9+s.cx;if(!s.giv[i]&&s.b[i]!=s.sol[i]){s.hints++;g.ticks+=1800;g.t=g.ticks/60;g.score=Math.floor(g.t);s.giv[i]=true;s.b[i]=s.sol[i];s.nt[i]=0;s.bad=conflicts(s.b);g.sfx("power");if(s.b.every((x,k)=>x==s.sol[k]))g.win("SOLVED IN "+BNG.fmtT(g.score))}}
  if(["left","right","up","down"].includes(a))g.sfx("move")},
 click(g,x,y){const s=g.s,c=Math.floor((x-BX)/CS),r=Math.floor((y-BY)/CS);if(c>=0&&c<9&&r>=0&&r<9){s.cx=c;s.cy=r;g.sfx("move")}
  const px=212;if(x>=px&&x<px+40)for(let v=1;v<=9;v++){const yy=40+(v-1)*14;if(y>=yy&&y<yy+12)put(g,v)}},
 update(){},
 draw(g){const s=g.s;g.cls(1);const sel=s.b[s.cy*9+s.cx];
  for(let r=0;r<9;r++)for(let c=0;c<9;c++){const i=r*9+c,X=BX+c*CS,Y=BY+r*CS;let bg=7;if(r==s.cy||c==s.cx||(Math.floor(r/3)==Math.floor(s.cy/3)&&Math.floor(c/3)==Math.floor(s.cx/3)))bg=15;if(sel&&s.b[i]==sel)bg=10;if(r==s.cy&&c==s.cx)bg=12;
   g.rect(X,Y,CS,CS,bg);const v=s.b[i];if(v)g.text(v,X+CS/2+1,Y+6,s.bad.has(i)?8:s.giv[i]?0:1,2,"c");
   else if(s.nt[i])for(let n=1;n<=9;n++)if(s.nt[i]&1<<n)g.text(n,X+3+((n-1)%3)*6,Y+2+Math.floor((n-1)/3)*7,13)}
  for(let k=0;k<=9;k++){const w=k%3==0?2:1,col=k%3==0?0:6;g.rect(BX+k*CS-(k%3==0?1:0),BY,w,9*CS,col);g.rect(BX,BY+k*CS-(k%3==0?1:0),9*CS,w,col)}
  g.text("81",W-4,3,10,2,"r");g.text(g.def.modes[g.mode],6,4,13);g.text("TIME "+BNG.fmtT(g.score),106,4,7,1,"c");
  for(let v=1;v<=9;v++){const n=s.b.filter(x=>x==v).length,yy=40+(v-1)*14;g.rect(212,yy,40,12,n>=9?5:13);g.text(v+(n>=9?" OK":" "+(9-n)),232,yy+3,n>=9?6:7,1,"c")}
  g.text(s.notes?"NOTES ON":"NOTES OFF",232,172,s.notes?11:6,1,"c");g.text("HINTS "+s.hints,232,182,6,1,"c");g.text("CLASH "+s.bad.size,232,192,s.bad.size?8:6,1,"c")}});
window.BNG_81={generate,solve,conflicts};
})();
