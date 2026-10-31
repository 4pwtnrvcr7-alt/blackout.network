// Pixel Checkers: original checkers (English draughts rules) vs an alpha-beta AI. Forced captures, multi-jumps, kings.
(()=>{const SQ=28,BX=8,BY=8,W=320,H=240;
function initial(){const b=new Array(64).fill(null);for(let r=0;r<8;r++)for(let c=0;c<8;c++)if((r+c)%2==1){if(r<3)b[r*8+c]="b";else if(r>4)b[r*8+c]="r"}return b}
const own=(p,s)=>p&&p.toLowerCase()==s,isK=p=>p&&p==p.toUpperCase();
function moves(b,s){const caps=[],simple=[];const dirs=p=>isK(p)?[[-1,-1],[-1,1],[1,-1],[1,1]]:s=="r"?[[-1,-1],[-1,1]]:[[1,-1],[1,1]];
 for(let f=0;f<64;f++){const p=b[f];if(!own(p,s))continue;
  const dfs=(bb,sq,path,caps1,pc)=>{let ext=false;const r=sq>>3,c=sq&7;for(const [dr,dc] of dirs(pc)){const mr=r+dr,mc=c+dc,tr=r+2*dr,tc=c+2*dc;if(tr<0||tr>7||tc<0||tc>7)continue;const mid=mr*8+mc,to=tr*8+tc;
    if(bb[mid]&&!own(bb[mid],s)&&!bb[to]){ext=true;const nb=bb.slice();nb[to]=pc;nb[sq]=null;nb[mid]=null;const crown=!isK(pc)&&(s=="r"?tr==0:tr==7);
     if(crown)caps.push({path:path.concat(to),caps:caps1.concat(mid)});else dfs(nb,to,path.concat(to),caps1.concat(mid),pc)}}
   if(!ext&&caps1.length)caps.push({path,caps:caps1})};
  dfs(b,f,[f],[],p);
  if(!caps.length)for(const [dr,dc] of dirs(p)){const r=(f>>3)+dr,c=(f&7)+dc;if(r>=0&&r<8&&c>=0&&c<8&&!b[r*8+c])simple.push({path:[f,r*8+c],caps:[]})}}
 return caps.length?caps:simple}
function apply(b,m){const nb=b.slice(),f=m.path[0],t=m.path[m.path.length-1];let p=nb[f];nb[f]=null;m.caps.forEach(c=>nb[c]=null);if(p=="r"&&t>>3==0)p="R";if(p=="b"&&t>>3==7)p="B";nb[t]=p;return nb}
function ev(b){let v=0;b.forEach((p,i)=>{if(!p)return;const r=i>>3,val=isK(p)?165:100+(p=="b"?r:7-r)*4+((i&7)>1&&(i&7)<6?3:0);v+=p.toLowerCase()=="b"?val:-val});return v}
function ab(b,s,d,a,bt){const ms=moves(b,s);if(!ms.length)return -100000-d;if(d==0)return(s=="b"?1:-1)*ev(b);const o=s=="b"?"r":"b";
 for(const m of ms){const v=-ab(apply(b,m),o,d-1,-bt,-a);if(v>a)a=v;if(a>=bt)break}return a}
function best(b,d,noise){const ms=moves(b,"b");let bm=ms[0],bv=-1e9;ms.forEach(m=>{const v=-ab(apply(b,m),"r",d-1,-1e9,1e9)+Math.random()*noise;if(v>bv){bv=v;bm=m}});return bm}
function after(g){const s=g.s;s.ms=moves(s.b,s.turn);if(!s.ms.length){if(s.turn=="b"){g.add(1000*(g.mode+1));g.win("YOU WIN!")}else g.over("CPU WINS");return}if(s.quiet>=80){g.add(200);g.over("DRAW - 40 MOVES EACH, NO CAPTURES")}}
function exec(g,m){const s=g.s;const side=s.turn;s.b=apply(s.b,m);s.last=m;s.quiet=m.caps.length?0:s.quiet+1;if(m.caps.length){g.sfx("pop");if(side=="r")g.add(m.caps.length*100)}else g.sfx("place");
 s.turn=side=="r"?"b":"r";s.sel=-1;s.part=[];after(g);if(g.state=="play"&&s.turn=="b")s.ai=26}
BNG.register({id:"checkers",name:"Pixel Checkers",inspired:"classic checkers / English draughts (public-domain rules)",cats:["Board/Card","Classic"],w:W,h:H,modes:["EASY","NORMAL","HARD"],
 desc:"Checkers against a computer opponent with three strengths. Captures are forced, multi-jumps chain, and men crowned on the far row become kings. You play red and move first.",
 controls:["Arrows: move cursor","Space / Enter: pick a piece, then each landing square","Backspace: cancel","Mouse: click piece, then squares"],
 init(g){const s=g.s;s.b=initial();s.turn="r";s.cur=40+1;s.sel=-1;s.part=[];s.last=null;s.ai=0;s.quiet=0;s.ms=moves(s.b,"r")},
 act(g,sq){const s=g.s;if(s.turn!="r"||s.ai)return;
  if(s.sel<0||(own(s.b[sq],"r")&&!s.part.length)){if(s.ms.some(m=>m.path[0]==sq)){s.sel=sq;s.part=[sq];g.sfx("click")}else if(own(s.b[sq],"r")){g.sfx("bad");s.msg=s.ms[0].caps.length?"A CAPTURE IS REQUIRED":"THAT PIECE CAN'T MOVE"}return}
  const pre=s.part.concat(sq),cand=s.ms.filter(m=>pre.every((x,i)=>m.path[i]==x));if(!cand.length){g.sfx("bad");return}
  const done=cand.find(m=>m.path.length==pre.length);if(done){exec(g,done);return}s.part=pre;g.sfx("click")},
 key(g,a){const s=g.s;const r=s.cur>>3,c=s.cur&7;if(a=="left"&&c>0)s.cur--;else if(a=="right"&&c<7)s.cur++;else if(a=="up"&&r>0)s.cur-=8;else if(a=="down"&&r<7)s.cur+=8;else if(a=="fire"||a=="enter")this.act(g,s.cur);else if(a=="back"){s.sel=-1;s.part=[]}if(["left","right","up","down"].includes(a)){g.sfx("move");s.msg=""}},
 click(g,x,y){const c=Math.floor((x-BX)/SQ),r=Math.floor((y-BY)/SQ);if(c>=0&&c<8&&r>=0&&r<8){g.s.cur=r*8+c;this.act(g,g.s.cur)}},
 update(g){const s=g.s;if(s.ai>0&&--s.ai==0&&s.turn=="b"){const m=best(s.b,[2,4,6][g.mode],[40,6,0][g.mode]);if(m)exec(g,m)}},
 draw(g){const s=g.s;g.cls(1);const cand=s.part.length?s.ms.filter(m=>s.part.every((x,i)=>m.path[i]==x)).map(m=>m.path[s.part.length]).filter(v=>v!=null):[];
  for(let r=0;r<8;r++)for(let c=0;c<8;c++){const i=r*8+c,X=BX+c*SQ,Y=BY+r*SQ;g.rect(X,Y,SQ,SQ,(r+c)%2?3:15);if(s.last&&s.last.path.includes(i))g.rect(X,Y,SQ,SQ,11);
   const p=s.b[i];if(p){const red=p.toLowerCase()=="r";g.circ(X+14,Y+15,11,red?2:0);g.circ(X+14,Y+13,11,red?8:5);g.circ(X+14,Y+13,7,red?14:13,false);if(isK(p)){g.spr(["1.1.1","11111","11111"],X+9,Y+10,{s:2,map:{1:10}})}}
   if(cand.includes(i))g.circ(X+14,Y+14,4,10);if(!s.part.length&&s.turn=="r"&&!s.ai&&s.ms.some(m=>m.path[0]==i)&&s.ms[0].caps.length&&(g.ticks>>4)%2)g.box(X+1,Y+1,SQ-2,SQ-2,10)}
  s.part.forEach(q=>g.box(BX+(q&7)*SQ,BY+(q>>3)*SQ,SQ,SQ,12));
  const cx=BX+(s.cur&7)*SQ,cy=BY+(s.cur>>3)*SQ;if((g.ticks>>4)%4)for(const [a,b] of [[0,0],[SQ-4,0],[0,SQ-4],[SQ-4,SQ-4]])g.rect(cx+a,cy+b,4,4,10);
  const PX=240,cnt=t=>s.b.filter(p=>p&&p.toLowerCase()==t).length;g.text("PIXEL",PX,8,10,2);g.text("CHECKERS",PX,20,10,1);g.text(g.def.modes[g.mode],PX,30,13);
  g.text(s.turn=="r"?"YOUR MOVE":"CPU THINKING",PX,44,s.turn=="r"?11:9);g.text("SCORE "+g.score,PX,56,7);g.text("RED  "+cnt("r"),PX,72,8);g.text("BLACK "+cnt("b"),PX,82,6);
  if(s.ms.length&&s.ms[0].caps.length&&s.turn=="r")g.text("JUMP REQUIRED",PX,100,10);if(s.msg)g.text(s.msg.slice(0,18),PX,112,8);g.text("NO-CAPTURE",PX,130,6);g.text(s.quiet+"/80",PX,138,6)}});
window.BNG_CHECKERS={moves,apply,initial,best};
})();
