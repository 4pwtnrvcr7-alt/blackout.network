// Alien Wave: original marching-alien shooter (inspired by Space Invaders). Original alien designs.
(()=>{const W=224,H=240,PY=214;
const AL=[[["..1..1..","...11...","..1111..",".11.11.1","11111111","1.1..1.1","1......1",".1....1."],["..1..1..","...11...","..1111..","1.11.11.","11111111","1.1..1.1",".1....1.","1......1"]],
 [["...11...",".111111.","11.11.11","11111111","..1..1..",".1.11.1.","1.1..1.1","........"],["...11...",".111111.","11.11.11","11111111",".1.11.1.","1......1",".1....1.","........"]],
 [["..1111..",".111111.","1.1111.1","11111111","11.11.11",".1....1.","1.1..1.1","........"],["..1111..",".111111.","1.1111.1","11111111","11.11.11","..1..1..",".1.11.1.","........"]]];
const PLAYER=["....77....","...7777...",".77777777.","7777777777","77.7777.77"];
const UFO=["...8888...",".88888888.","8.88.88.88","8888888888",".8..88..8."];
function wave(g){const s=g.s;s.al=[];for(let r=0;r<5;r++)for(let c=0;c<11;c++)s.al.push({r,c,x:16+c*16,y:28+Math.min(4,s.wave-1)*6+r*14,t:r==0?2:r<3?1:0,alive:true});
 s.dx=2;s.stepT=0;s.frame=0;s.bul=[];s.ufo=null;s.ufoT=600+g.ri(600);
 s.sh=[0,1,2,3].map(i=>{const m=[];for(let y=0;y<12;y++){m.push([]);for(let x=0;x<20;x++)m[y].push(!(y<3&&(x<3-y||x>16+y))&&!(y>7&&x>5&&x<14))}return{x:22+i*48,y:178,m}})}
BNG.register({id:"invaders",name:"Alien Wave",inspired:"Space Invaders-style marching alien shooters",cats:["Arcade","Action","Classic"],w:W,h:H,
 desc:"Rows of original pixel aliens march side to side and drop lower every pass. Hide behind crumbling shields and pick them off before they land. Watch for the bonus saucer.",
 controls:["Left/Right: move","Space: fire"],
 init(g){const s=g.s;s.px=W/2;s.lives=3;s.wave=1;s.shot=null;s.dead=0;wave(g)},
 key(g,a){const s=g.s;if(a=="fire"&&!s.shot&&!s.dead){s.shot={x:s.px,y:PY-2};g.sfx("shoot")}},
 update(g){const s=g.s;if(s.dead){if(--s.dead==0){if(s.lives<=0){g.over("THE ALIENS LANDED");return}s.px=W/2}return}
  if(g.held("left"))s.px-=1.6;if(g.held("right"))s.px+=1.6;s.px=g.clamp(s.px,8,W-8);
  const live=s.al.filter(a=>a.alive);if(!live.length){s.wave++;g.add(1000);g.sfx("win");wave(g);return}
  const delay=Math.max(2,Math.floor(live.length/1.2)-s.wave);if(++s.stepT>=delay){s.stepT=0;s.frame^=1;g.tone([98,92,87,82][g.ticks%4],.06,"square",.05);
   const minX=Math.min(...live.map(a=>a.x)),maxX=Math.max(...live.map(a=>a.x));if((s.dx>0&&maxX+8+s.dx>W-4)||(s.dx<0&&minX+s.dx<4)){s.dx=-s.dx;live.forEach(a=>a.y+=6)}else live.forEach(a=>a.x+=s.dx)}
  if(live.some(a=>a.y+8>=PY-4)){s.lives=0;s.dead=60;g.sfx("die");return}
  if(g.ri(100)<3+s.wave&&s.bul.length<3+s.wave){const cols={};live.forEach(a=>{if(!cols[a.c]||cols[a.c].y<a.y)cols[a.c]=a});const sh=g.pick(Object.values(cols));s.bul.push({x:sh.x+4,y:sh.y+8,z:g.ri(2)})}
  if(s.shot){s.shot.y-=5;const sh=s.shot;if(sh.y<10)s.shot=null;else{
    for(const a of live)if(sh.x>=a.x&&sh.x<a.x+8&&sh.y>=a.y&&sh.y<a.y+8){a.alive=false;s.shot=null;g.add([10,20,30][a.t]);g.sfx("pop");s.fx={x:a.x,y:a.y,t:10};break}
    if(s.shot&&s.ufo&&Math.abs(sh.x-s.ufo.x-5)<6&&sh.y<26&&sh.y>14){const v=g.pick([50,100,150,300]);g.add(v);s.fx={x:s.ufo.x,y:16,t:40,v};s.ufo=null;s.shot=null;g.sfx("boom")}
    if(s.shot&&hitShield(s,sh.x,sh.y))s.shot=null}}
  s.bul=s.bul.filter(b=>{b.y+=2+s.wave*.15;if(b.y>H)return false;if(hitShield(s,b.x,b.y))return false;
   if(b.y>=PY&&b.y<=PY+5&&Math.abs(b.x-s.px)<5){s.lives--;s.dead=70;g.sfx("boom");s.bul=[];return false}return true});
  if(s.ufo){s.ufo.x+=s.ufo.v;if(g.ticks%8==0)g.tone(600+Math.sin(g.ticks/4)*100,.08,"sine",.03);if(s.ufo.x<-12||s.ufo.x>W+12)s.ufo=null}else if(--s.ufoT<=0){s.ufoT=900+g.ri(600);const r=Math.random()<.5;s.ufo={x:r?-10:W+2,v:r?.8:-.8}}
  if(s.fx&&--s.fx.t<=0)s.fx=null},
 draw(g){const s=g.s;g.cls(0);g.text("SCORE "+g.score,4,3,7);g.text("WAVE "+s.wave,W-4,3,6,1,"r");
  s.al.forEach(a=>{if(a.alive)g.spr(AL[a.t][s.frame],a.x,a.y,{map:{1:[11,12,14][a.t]}})});
  if(s.ufo)g.spr(UFO,s.ufo.x,16);
  s.sh.forEach(sh=>sh.m.forEach((row,y)=>row.forEach((v,x)=>{if(v)g.px(sh.x+x,sh.y+y,11)})));
  if(!s.dead||(s.dead>>2)%2)g.spr(PLAYER,s.px-5,PY,{map:{7:s.dead?8:12}});
  if(s.shot)g.rect(s.shot.x,s.shot.y,1,4,7);s.bul.forEach(b=>{g.rect(b.x,b.y,1,4,b.z?10:8);g.px(b.x+((g.ticks>>2)%2?1:-1),b.y+1,b.z?10:8)});
  if(s.fx){if(s.fx.v)g.text(s.fx.v,s.fx.x+5,16,8,1,"c");else g.spr(["1..1.1.1",".1.1.1..","..1..1.1","11....11","1.1..1..",".1.1..1.","1..1.1.."],s.fx.x,s.fx.y,{map:{1:9}})}
  g.rect(0,H-12,W,1,11);for(let i=0;i<s.lives;i++)g.spr(PLAYER,6+i*14,H-9,{map:{7:12}})}});
function hitShield(s,x,y){x=Math.round(x);y=Math.round(y);for(const sh of s.sh){const lx=x-sh.x,ly=y-sh.y;if(lx>=0&&lx<20&&ly>=0&&ly<12&&sh.m[ly][lx]){for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++)if(Math.random()<.75&&sh.m[ly+dy]&&sh.m[ly+dy][lx+dx]!=null)sh.m[ly+dy][lx+dx]=false;return true}}return false}
})();
