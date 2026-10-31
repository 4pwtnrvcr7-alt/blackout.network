// Pixel Solitaire: original Klondike solitaire (public-domain card game), draw-one, with keyboard and mouse play.
(()=>{const W=256,H=240,CW=30,CH=40,TOP=14,TAB=62;
const SUIT=[["..1..",".111.","11111","..1..",".111."],[".1.1.","11111","11111",".111.","..1.."],["..1..",".111.","11111",".111.","..1.."],[".111.",".111.","11111","..1..",".111."]];
const RK=["","A","2","3","4","5","6","7","8","9","10","J","Q","K"];const red=c=>c.s==1||c.s==2;const colX=i=>5+i*36;
function deal(g){const s=g.s,d=[];for(let su=0;su<4;su++)for(let r=1;r<=13;r++)d.push({s:su,r,up:false});for(let i=d.length-1;i>0;i--){const j=g.ri(i+1);[d[i],d[j]]=[d[j],d[i]]}
 s.p=[[],[],[],[],[],[],[]].concat([[],[],[],[],[],[]]);for(let c=0;c<7;c++)for(let k=0;k<=c;k++){const cd=d.pop();cd.up=k==c;s.p[6+c].push(cd)}s.p[0]=d}
const pileAt=(row,col)=>row==0?(col==0?0:col==1?1:col>=3?col-1:1):6+col;
function offs(pile){let down=0;pile.forEach(c=>{if(!c.up)down++});const up=pile.length-down;const fy=Math.min(10,up>1?Math.floor((H-4-TAB-CH-down*4)/(up-1)):10);return pile.map((c,i)=>{let y=TAB;for(let k=0;k<i;k++)y+=pile[k].up?fy:4;return y})}
function canF(s,c,fi){const f=s.p[2+fi];return f.length?f[f.length-1].s==c.s&&f[f.length-1].r==c.r-1:c.r==1}
function canT(s,c,ti){const t=s.p[6+ti];if(!t.length)return c.r==13;const top=t[t.length-1];return top.up&&red(top)!=red(c)&&top.r==c.r+1}
function flipTops(g){const s=g.s;for(let i=6;i<13;i++){const t=s.p[i];if(t.length&&!t[t.length-1].up){t[t.length-1].up=true;g.add(5)}}}
function checkWin(g){const s=g.s;if([2,3,4,5].every(i=>s.p[i].length==13)){g.add(Math.max(0,1500-Math.floor(g.t)*2));g.win("ALL CARDS HOME!")}}
function move(g,from,idx,to){const s=g.s,cards=s.p[from].slice(idx);if(!cards.length)return false;
 if(to>=2&&to<=5){if(cards.length!=1||!canF(s,cards[0],to-2))return false}else if(to>=6){if(!canT(s,cards[0],to-6))return false}else return false;
 s.p[from].splice(idx);s.p[to].push(...cards);if(to<=5)g.add(10);else if(from==1)g.add(5);else if(from>=2&&from<=5)g.add(-15);g.sfx(to<=5?"coin":"place");flipTops(g);s.moves++;checkWin(g);return true}
function draw1(g){const s=g.s;if(s.p[0].length){const c=s.p[0].pop();c.up=true;s.p[1].push(c);g.sfx("click")}else if(s.p[1].length){s.p[0]=s.p[1].reverse().map(c=>(c.up=false,c));s.p[1]=[];g.sfx("drop");s.passes++}else g.sfx("bad");s.moves++}
function auto(g,pile){const s=g.s,P=s.p[pile];if(!P.length||pile==0||(pile>=2&&pile<=5))return false;const c=P[P.length-1];if(!c.up)return false;for(let f=0;f<4;f++)if(canF(s,c,f))return move(g,pile,P.length-1,2+f);return false}
function act(g,row,col,depth){const s=g.s,pile=pileAt(row,col);
 if(s.hold){const h=s.hold;s.hold=null;if(h.pile==pile){g.sfx("move");return}if(!move(g,h.pile,h.idx,pile))g.sfx("bad");return}
 if(pile==0){draw1(g);return}const P=s.p[pile];if(!P.length){g.sfx("bad");return}
 if(pile>=6){let d=depth==null?P.length-1:Math.min(depth,P.length-1);if(!P[d].up){if(d==P.length-1){P[d].up=true;g.add(5);g.sfx("click")}else g.sfx("bad");return}s.hold={pile,idx:d};g.sfx("click");return}
 s.hold={pile,idx:P.length-1};g.sfx("click")}
function drawCard(g,c,x,y,hl){if(!c.up){g.rect(x,y,CW,CH,1);g.box(x,y,CW,CH,6);for(let k=3;k<CW-3;k+=4)for(let j=3;j<CH-3;j+=4)g.px(x+k+(j%8?2:0),y+j,12);g.box(x+2,y+2,CW-4,CH-4,12);return}
 g.rect(x,y,CW,CH,7);g.box(x,y,CW,CH,hl?10:5);const col=red(c)?8:0;g.text(RK[c.r],x+2,y+2,col);g.spr(SUIT[c.s],x+CW-7,y+2,{map:{1:col}});
 if(c.r>10){g.rect(x+7,y+11,16,22,red(c)?14:12);g.box(x+7,y+11,16,22,col);g.text(RK[c.r],x+15,y+15,col,2,"c");g.spr(SUIT[c.s],x+13,y+27,{map:{1:col}})}else g.spr(SUIT[c.s],x+10,y+17,{s:2,map:{1:col}});
 g.text(RK[c.r],x+CW-2,y+CH-7,col,1,"r")}
function slot(g,x,y,label){g.box(x,y,CW,CH,3);g.box(x+1,y+1,CW-2,CH-2,3);if(label)g.text(label,x+CW/2,y+CH/2-2,3,1,"c")}
BNG.register({id:"solitaire",name:"Pixel Solitaire",inspired:"Klondike solitaire (public-domain card game)",cats:["Board/Card","Classic"],w:W,h:H,
 desc:"Classic draw-one Klondike with hand-drawn pixel cards. Build the four foundations from ace to king, and stack the tableau down in alternating colors. Only kings go in empty columns.",
 controls:["Arrows: move cursor (Up/Down picks depth in a column)","Space / Enter: draw, pick up or drop cards","F: send cursor card to a foundation","Backspace: cancel","N: give up this deal","Mouse: click to pick up and drop"],
 init(g){const s=g.s;deal(g);s.row=1;s.col=0;s.depth=null;s.hold=null;s.moves=0;s.passes=0},
 key(g,a,code){const s=g.s;const P=s.p[pileAt(s.row,s.col)];
  if(a=="left"||a=="right"){const d=a=="left"?-1:1;s.col=(s.col+d+7)%7;if(s.row==0&&s.col==2)s.col=(s.col+d+7)%7;s.depth=null;g.sfx("move")}
  else if(a=="up"){if(s.row==1){const T=s.p[6+s.col];const cur=s.depth==null?T.length-1:s.depth;if(cur>0&&T[cur-1]&&T[cur-1].up)s.depth=cur-1;else{s.row=0;if(s.col==2)s.col=1;s.depth=null}}g.sfx("move")}
  else if(a=="down"){if(s.row==0){s.row=1;s.depth=null}else{const T=s.p[6+s.col];if(s.depth!=null&&s.depth<T.length-1)s.depth++;}g.sfx("move")}
  else if(a=="fire"||a=="enter"){act(g,s.row,s.col,s.row==1?s.depth:null);s.depth=null}
  else if(code=="KeyF"){s.hold=null;if(!auto(g,pileAt(s.row,s.col)))g.sfx("bad")}
  else if(a=="back"){s.hold=null;g.sfx("move")}else if(code=="KeyN"){g.over("GAVE UP - NEW DEAL?")}},
 click(g,x,y,btn){const s=g.s,col=Math.floor((x-5)/36);if(col<0||col>6||x>colX(col)+CW)return;
  if(y>=TOP&&y<TOP+CH){if(col==2)return;s.row=0;s.col=col;if(btn==2){auto(g,pileAt(0,col));return}act(g,0,col,null);return}
  if(y>=TAB){const T=s.p[6+col],ys=offs(T);let d=null;for(let i=T.length-1;i>=0;i--)if(y>=ys[i]&&y<ys[i]+CH){d=i;break}s.row=1;s.col=col;if(btn==2){auto(g,6+col);return}act(g,1,col,d==null?T.length-1:d)}},
 update(){},
 draw(g){const s=g.s;g.cls(3);for(let i=0;i<40;i++)g.px((i*67)%W,(i*29)%H,11);
  g.text("SCORE "+g.score,4,4,7);g.text("MOVES "+s.moves,W/2,4,15,1,"c");g.text(BNG.fmtT(Math.floor(g.t)),W-4,4,15,1,"r");
  const st=s.p[0],wa=s.p[1];if(st.length){drawCard(g,st[st.length-1],colX(0),TOP);if(st.length>1)g.box(colX(0)+1,TOP+1,CW,CH,0)}else slot(g,colX(0),TOP,"O");
  if(wa.length&&!(s.hold&&s.hold.pile==1))drawCard(g,wa[wa.length-1],colX(1),TOP);else if(wa.length>1)drawCard(g,wa[wa.length-2],colX(1),TOP);else slot(g,colX(1),TOP,"");
  for(let f=0;f<4;f++){const F=s.p[2+f],x=colX(3+f);if(F.length)drawCard(g,F[F.length-(s.hold&&s.hold.pile==2+f&&F.length>1?2:1)],x,TOP);else{slot(g,x,TOP,"");g.spr(SUIT[f],x+12,TOP+17,{map:{1:3}})}if(s.hold&&s.hold.pile==2+f&&F.length==1)slot(g,x,TOP,"")}
  for(let c=0;c<7;c++){const T=s.p[6+c],ys=offs(T),x=colX(c);if(!T.length)slot(g,x,TAB,"K");T.forEach((cd,i)=>{const held=s.hold&&s.hold.pile==6+c&&i>=s.hold.idx;drawCard(g,cd,x,ys[i]-(held?3:0),held)})}
  let cx=colX(s.col),cy=TOP;if(s.row==1){const T=s.p[6+s.col],ys=offs(T);const d=s.depth==null?T.length-1:s.depth;cy=T.length?ys[d]:TAB}
  if((g.ticks>>3)%3){g.box(cx-2,cy-2,CW+4,CH+4,10);g.box(cx-1,cy-1,CW+2,CH+2,9)}
  if(s.hold){const P=s.p[s.hold.pile],c=P[s.hold.idx];if(c){g.rect(cx+CW-8,cy-8,14,10,0);g.text(RK[c.r],cx+CW-6,cy-6,10)}if(s.hold.pile<=5)drawCard(g,P[P.length-1],cx+6,cy+8,true)}}});
})();
