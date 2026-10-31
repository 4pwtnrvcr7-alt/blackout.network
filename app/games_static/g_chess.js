// Pixel Chess: original chess vs a small alpha-beta AI. Full legal moves, check/mate/stalemate, castling, en passant, promotion.
(()=>{const SQ=28,BX=8,BY=8,W=320,H=240;
const SIL={p:["............","............",".....11.....","....1111....","....1111....",".....11.....","....1111....",".....11.....",".....11.....","....1111....","...111111...","..11111111..","............"],
r:["............","..11.11.11..","..11111111..","...111111...","....1111....","....1111....","....1111....","....1111....","...111111...","..11111111..","..11111111..","............","............"],
n:["............",".....1.1....","....11111...","...1111111..","..111.11111.","..11..11111.","......1111..",".....11111..","....111111..","...1111111..","..11111111..","..11111111..","............"],
b:["............",".....11.....","....1111....","...111.11...","...11.111...","...111111...","....1111....",".....11.....","....1111....","...111111...","..11111111..","..11111111..","............"],
q:["............",".1...11...1.",".1..1111..1.",".11.1111.11.","..11111111..","..11111111..","...111111...","....1111....","....1111....","...111111...","..11111111..","..11111111..","............"],
k:["............",".....11.....","....1111....",".....11.....","..11.11.11..",".1111111111.",".1111111111.","..11111111..","...111111...","....1111....","...111111...","..11111111..","............"]};
const SPR={};for(const k in SIL){const m=SIL[k];SPR[k]=m.map((row,y)=>[...row].map((ch,x)=>{if(ch=="1")return"1";for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){const r=m[y+dy];if(r&&r[x+dx]=="1")return"2"}return"."}).join(""))}
const VAL={p:100,n:320,b:330,r:500,q:900,k:0};
const isW=p=>p&&p===p.toUpperCase(),side=p=>p?(isW(p)?"w":"b"):null,low=p=>p&&p.toLowerCase();
const N=[[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]],K8=[[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]],DI=[[-1,-1],[-1,1],[1,-1],[1,1]],OR=[[-1,0],[1,0],[0,-1],[0,1]];
function initial(){const b=new Array(64).fill(null),back="rnbqkbnr";for(let c=0;c<8;c++){b[c]=back[c];b[8+c]="p";b[48+c]="P";b[56+c]=back[c].toUpperCase()}return{b,turn:"w",cs:{K:1,Q:1,k:1,q:1},ep:-1,half:0}}
function attacked(b,sq,by){const r=sq>>3,c=sq&7,at=(rr,cc)=>rr>=0&&rr<8&&cc>=0&&cc<8?b[rr*8+cc]:undefined;
 const pr=by=="w"?r+1:r-1,pp=by=="w"?"P":"p";if(at(pr,c-1)===pp||at(pr,c+1)===pp)return true;
 const own=x=>by=="w"?x.toUpperCase():x;for(const [dr,dc] of N)if(at(r+dr,c+dc)===own("n"))return true;for(const [dr,dc] of K8)if(at(r+dr,c+dc)===own("k"))return true;
 for(const [dirs,set] of [[DI,["b","q"]],[OR,["r","q"]]])for(const [dr,dc] of dirs){let rr=r+dr,cc=c+dc;while(rr>=0&&rr<8&&cc>=0&&cc<8){const p=b[rr*8+cc];if(p){if(side(p)==by&&set.includes(low(p)))return true;break}rr+=dr;cc+=dc}}return false}
const kingSq=(b,s)=>b.indexOf(s=="w"?"K":"k");const inCheck=(st,s)=>attacked(st.b,kingSq(st.b,s),s=="w"?"b":"w");
function pseudo(st){const b=st.b,s=st.turn,o=s=="w"?"b":"w",mv=[];
 for(let f=0;f<64;f++){const p=b[f];if(!p||side(p)!=s)continue;const r=f>>3,c=f&7,t=low(p);const add=(tt,extra)=>mv.push(Object.assign({f,t:tt},extra||{}));
  if(t=="p"){const d=s=="w"?-1:1,last=s=="w"?0:7,start=s=="w"?6:1,r1=r+d;const pushP=(tt,ex)=>{if((tt>>3)==last)["q","r","b","n"].forEach(pr=>add(tt,Object.assign({pr},ex)));else add(tt,ex)};
   if(r1>=0&&r1<8&&!b[r1*8+c]){pushP(r1*8+c);if(r==start&&!b[(r+2*d)*8+c])add((r+2*d)*8+c,{dbl:1})}
   for(const dc of [-1,1]){const cc=c+dc;if(cc<0||cc>7||r1<0||r1>7)continue;const tt=r1*8+cc;if(b[tt]&&side(b[tt])==o)pushP(tt);else if(tt===st.ep)add(tt,{ep:1})}}
  else if(t=="n"||t=="k"){for(const [dr,dc] of t=="n"?N:K8){const rr=r+dr,cc=c+dc;if(rr<0||rr>7||cc<0||cc>7)continue;const q=b[rr*8+cc];if(!q||side(q)==o)add(rr*8+cc)}
   if(t=="k"){const home=s=="w"?60:4;if(f==home&&!attacked(b,f,o)){const K=s=="w"?"K":"k",Q=s=="w"?"Q":"q";
     if(st.cs[K]&&!b[f+1]&&!b[f+2]&&low(b[f+3])=="r"&&!attacked(b,f+1,o)&&!attacked(b,f+2,o))add(f+2,{cs:"K"});
     if(st.cs[Q]&&!b[f-1]&&!b[f-2]&&!b[f-3]&&low(b[f-4])=="r"&&!attacked(b,f-1,o)&&!attacked(b,f-2,o))add(f-2,{cs:"Q"})}}}
  else{const dirs=t=="b"?DI:t=="r"?OR:DI.concat(OR);for(const [dr,dc] of dirs){let rr=r+dr,cc=c+dc;while(rr>=0&&rr<8&&cc>=0&&cc<8){const q=b[rr*8+cc];if(!q)add(rr*8+cc);else{if(side(q)==o)add(rr*8+cc);break}rr+=dr;cc+=dc}}}}
 return mv}
function make(st,m){const b=st.b.slice(),p=b[m.f],s=st.turn,cs=Object.assign({},st.cs);let cap=b[m.t];b[m.t]=m.pr?(s=="w"?m.pr.toUpperCase():m.pr):p;b[m.f]=null;
 if(m.ep){const cq=m.t+(s=="w"?8:-8);cap=b[cq];b[cq]=null}if(m.cs){if(m.cs=="K"){b[m.f+1]=b[m.f+3];b[m.f+3]=null}else{b[m.f-1]=b[m.f-4];b[m.f-4]=null}}
 if(low(p)=="k"){if(s=="w"){cs.K=0;cs.Q=0}else{cs.k=0;cs.q=0}}[[63,"K"],[56,"Q"],[7,"k"],[0,"q"]].forEach(([sq,k])=>{if(m.f==sq||m.t==sq)cs[k]=0});
 return{b,turn:s=="w"?"b":"w",cs,ep:m.dbl?(m.f+m.t)/2:-1,half:low(p)=="p"||cap?0:st.half+1,cap}}
function legal(st){return pseudo(st).filter(m=>!inCheck(make(st,m),st.turn))}
const PST_C=[0,1,2,3,3,2,1,0];
function evalW(st){let v=0;const b=st.b;for(let i=0;i<64;i++){const p=b[i];if(!p)continue;const t=low(p),r=i>>3,c=i&7,w=isW(p);let x=VAL[t];
  if(t=="n"||t=="b")x+=(PST_C[r]+PST_C[c])*5;else if(t=="p")x+=(w?6-r:r-1)*8+(c>1&&c<6?PST_C[r]*3:0);else if(t=="q")x+=(PST_C[r]+PST_C[c]);else if(t=="k")x+=(w?(r==7?10:-10):(r==0?10:-10))+((c==6||c==2)?10:0);v+=w?x:-x}return v}
function order(st,ms){return ms.map(m=>({m,k:(st.b[m.t]?VAL[low(st.b[m.t])]*10-VAL[low(st.b[m.f])]:0)+(m.pr=="q"?800:0)})).sort((a,b)=>b.k-a.k).map(x=>x.m)}
function search(st,d,a,bt,ply){const ms=legal(st);if(!ms.length)return inCheck(st,st.turn)?-100000+ply:0;if(d==0)return(st.turn=="w"?1:-1)*evalW(st);
 for(const m of order(st,ms)){const v=-search(make(st,m),d-1,-bt,-a,ply+1);if(v>a)a=v;if(a>=bt)break}return a}
function best(st,depth,noise){const ms=order(st,legal(st));let bm=ms[0],bv=-1e9;for(const m of ms){const v=-search(make(st,m),depth-1,-1e9,-bv,1)+(noise?Math.random()*noise:0);if(v>bv){bv=v;bm=m}}return bm}
const sqName=i=>"abcdefgh"[i&7]+(8-(i>>3));
function status(g){const s=g.s,st=s.st,ms=legal(st);s.legal=ms;s.check=inCheck(st,st.turn);
 const pcs=st.b.filter(Boolean).map(low).filter(x=>x!="k");const insuff=!pcs.length||(pcs.length==1&&(pcs[0]=="n"||pcs[0]=="b"));
 if(!ms.length){if(s.check){if(st.turn=="b"){g.add(1000*(g.mode+1));g.win("CHECKMATE - YOU WIN!")}else g.over("CHECKMATE - CPU WINS")}else{g.add(200);g.over("STALEMATE - DRAW")}return}
 if(insuff){g.add(200);g.over("DRAW - NOT ENOUGH MATERIAL");return}if(st.half>=100){g.add(200);g.over("DRAW - 50-MOVE RULE");return}if(s.check)g.sfx("bad")}
function doMove(g,m){const s=g.s,mover=s.st.turn;const n=make(s.st,m);if(n.cap){if(mover=="w"){g.add(VAL[low(n.cap)]/10);s.capW.push(n.cap)}else s.capB.push(n.cap);g.sfx("pop")}else g.sfx("place");
 s.hist.push((mover=="w"?Math.floor(s.hist.length/2)+1+". ":"")+(m.cs?(m.cs=="K"?"O-O":"O-O-O"):(low(s.st.b[m.f])=="p"?"":s.st.b[m.f].toUpperCase())+sqName(m.f)+(n.cap?"x":"-")+sqName(m.t)+(m.pr?"="+m.pr.toUpperCase():"")));
 s.st=n;s.last=m;s.sel=-1;s.promo=null;status(g);if(g.state=="play"&&s.st.turn=="b")s.ai=24}
BNG.register({id:"chess",name:"Pixel Chess",inspired:"classic chess (public-domain rules)",cats:["Board/Card","Classic"],w:W,h:H,modes:["EASY","NORMAL","HARD"],
 desc:"Full-rules chess against a small computer opponent with three strengths. It covers castling, en passant, promotion and check, plus checkmate, stalemate and draws. You play white.",
 controls:["Arrows: move cursor","Space / Enter: pick up / place piece","Backspace: cancel selection","Promotion: Q R B N keys or arrows + Space","Mouse: click a piece, then its square"],
 init(g){const s=g.s;s.st=initial();s.cur=52;s.sel=-1;s.last=null;s.capW=[];s.capB=[];s.hist=[];s.ai=0;s.promo=null;s.pi=0;s.legal=legal(s.st);s.check=false},
 act(g,sq){const s=g.s;if(s.st.turn!="w"||s.ai)return;const p=s.st.b[sq];
  if(s.sel>=0){const ms=s.legal.filter(m=>m.f==s.sel&&m.t==sq);if(ms.length){if(ms.length>1){s.promo=ms;s.pi=0;g.sfx("click")}else doMove(g,ms[0]);return}}
  if(p&&isW(p)&&s.legal.some(m=>m.f==sq)){s.sel=sq;g.sfx("click")}else{if(s.sel>=0)g.sfx("bad");s.sel=-1}},
 key(g,a,code){const s=g.s;if(s.promo){const k={KeyQ:"q",KeyR:"r",KeyB:"b",KeyN:"n"}[code];if(k){doMove(g,s.promo.find(m=>m.pr==k));return}if(a=="left")s.pi=(s.pi+3)%4;if(a=="right")s.pi=(s.pi+1)%4;if(a=="fire"||a=="enter")doMove(g,s.promo[s.pi]);if(a=="back")s.promo=null;return}
  const r=s.cur>>3,c=s.cur&7;if(a=="left"&&c>0)s.cur--;else if(a=="right"&&c<7)s.cur++;else if(a=="up"&&r>0)s.cur-=8;else if(a=="down"&&r<7)s.cur+=8;else if(a=="fire"||a=="enter")this.act(g,s.cur);else if(a=="back")s.sel=-1;if(["left","right","up","down"].includes(a))g.sfx("move")},
 click(g,x,y){const s=g.s;if(s.promo){const i=Math.floor((x-BX-28)/42);if(y>=BY+96&&y<BY+136&&i>=0&&i<4)doMove(g,s.promo[i]);return}const c=Math.floor((x-BX)/SQ),r=Math.floor((y-BY)/SQ);if(c>=0&&c<8&&r>=0&&r<8){s.cur=r*8+c;this.act(g,s.cur)}},
 update(g){const s=g.s;if(s.ai>0&&--s.ai==0&&s.st.turn=="b"){const m=[()=>best(s.st,1,60),()=>best(s.st,2,8),()=>best(s.st,3,0)][g.mode]();if(m)doMove(g,m)}},
 draw(g){const s=g.s,st=s.st;g.cls(1);
  for(let r=0;r<8;r++)for(let c=0;c<8;c++){const i=r*8+c,X=BX+c*SQ,Y=BY+r*SQ;g.rect(X,Y,SQ,SQ,(r+c)%2?4:15);
   if(s.last&&(i==s.last.f||i==s.last.t))g.rect(X,Y,SQ,SQ,(r+c)%2?9:10);
   if(s.check&&st.b[i]==(st.turn=="w"?"K":"k"))g.rect(X,Y,SQ,SQ,8);
   const p=st.b[i];if(p)g.spr(SPR[low(p)],X+2,Y+1,{s:2,map:isW(p)?{1:7,2:0}:{1:0,2:6}});
   if(s.sel>=0&&s.legal.some(m=>m.f==s.sel&&m.t==i)){if(p)g.box(X+1,Y+1,SQ-2,SQ-2,11);else g.circ(X+SQ/2,Y+SQ/2,3,11)}}
  if(s.sel>=0)g.box(BX+(s.sel&7)*SQ,BY+(s.sel>>3)*SQ,SQ,SQ,12),g.box(BX+(s.sel&7)*SQ+1,BY+(s.sel>>3)*SQ+1,SQ-2,SQ-2,12);
  const cx=BX+(s.cur&7)*SQ,cy=BY+(s.cur>>3)*SQ;if((g.ticks>>4)%4)for(const [a,b] of [[0,0],[SQ-4,0],[0,SQ-4],[SQ-4,SQ-4]]){g.rect(cx+a,cy+b,4,4,10)}
  for(let i=0;i<8;i++){g.text("ABCDEFGH"[i],BX+i*SQ+SQ/2,BY+8*SQ+2,6,1,"c")}
  const PX=240;g.text("PIXEL",PX,8,10,2);g.text("CHESS",PX,20,10,2);g.text(g.def.modes[g.mode],PX,34,13);
  g.text(st.turn=="w"?(s.check?"CHECK! YOUR MOVE":"YOUR MOVE"):"CPU THINKING",PX,46,st.turn=="w"?(s.check?8:11):9);
  g.text("SCORE "+g.score,PX,56,7);g.text("TAKEN",PX,68,6);s.capW.forEach((p,i)=>g.spr(SPR[low(p)],PX+(i%6)*12,76+Math.floor(i/6)*13,{map:{1:0,2:6}}));
  g.text("LOST",PX,110,6);s.capB.forEach((p,i)=>g.spr(SPR[low(p)],PX+(i%6)*12,118+Math.floor(i/6)*13,{map:{1:7,2:0}}));
  s.hist.slice(-8).forEach((h,i)=>g.text(h,PX,156+i*8,6));
  if(s.promo){g.rect(BX+20,BY+86,176,58,0);g.box(BX+20,BY+86,176,58,10);g.text("PROMOTE TO:",BX+108,BY+90,10,1,"c");
   s.promo.forEach((m,i)=>{const X=BX+28+i*42,Y=BY+100;g.rect(X,Y,34,34,i==s.pi?12:5);g.spr(SPR[m.pr],X+5,Y+4,{s:2,map:{1:7,2:0}});g.text(m.pr,X+17,Y+36,7,1,"c")})}}});
window.BNG_CHESS={initial,legal,make,inCheck,best};
})();
