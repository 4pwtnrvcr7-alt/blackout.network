// Bug Blaster: original garden bug shooter (inspired by Centipede).
(()=>{const T=8,CW=30,CH=28,OY=8,ZONE=22;
const GUN=["..7..","..7..",".777.","77777","7.7.7"];
const SPIDER=["1..11..1",".1.11.1.","..1111..","11.88.11","..1111..",".1....1.","1......1"];
function bugs(g){const s=g.s;const n=8+Math.min(6,s.wave);s.seg=[];for(let i=0;i<n;i++)s.seg.push({x:14-i,y:0,dx:1,dy:1,head:i==0,pz:false});s.step=0}
BNG.register({id:"centipede",name:"Bug Blaster",inspired:"Centipede-style garden shooters",cats:["Arcade","Action","Classic"],w:CW*T,h:CH*T+OY,
 desc:"A long segmented bug winds down through a mushroom patch. Shoot a segment and it turns into a mushroom while the bug splits in two. Keep away from the bouncing spider.",
 controls:["Arrows / WASD: move inside the bottom zone","Space: fire (hold for auto-fire)"],
 init(g){const s=g.s;s.m={};for(let i=0;i<34;i++){const x=g.ri(CW),y=1+g.ri(ZONE-3);s.m[x+","+y]=4}s.px=CW*T/2;s.py=(CH-2)*T;s.lives=3;s.wave=1;s.shot=null;s.dead=0;s.spider=null;s.spT=300;bugs(g)},
 update(g){const s=g.s;if(s.dead){if(--s.dead==0){if(s.lives<=0){g.over("BUGGED OUT!");return}bugs(g);s.spider=null;Object.keys(s.m).forEach(k=>{if(s.m[k]<4)s.m[k]=4})}return}
  const sp=1.6;if(g.held("left"))s.px-=sp;if(g.held("right"))s.px+=sp;if(g.held("up"))s.py-=sp;if(g.held("down"))s.py+=sp;
  const ox=s.px,oy=s.py;s.px=g.clamp(s.px,0,CW*T-5);s.py=g.clamp(s.py,ZONE*T,CH*T-5);
  const blocked=()=>{const x0=Math.floor(s.px/T),x1=Math.floor((s.px+4)/T),y0=Math.floor(s.py/T),y1=Math.floor((s.py+4)/T);for(const x of [x0,x1])for(const y of [y0,y1])if(s.m[x+","+y])return true;return false};
  if(blocked()){s.px=ox;s.py=oy;if(blocked()){s.px=g.clamp(ox,0,CW*T-5);}}
  if(g.held("fire")&&!s.shot){s.shot={x:s.px+2,y:s.py};g.sfx("shoot")}
  if(s.shot){s.shot.y-=7;const sx=Math.floor(s.shot.x/T),sy=Math.floor(s.shot.y/T);if(s.shot.y<0)s.shot=null;else{
    const k=sx+","+sy;const hi=s.seg.findIndex(q=>q.x==sx&&q.y==sy);
    if(hi>=0){const q=s.seg[hi];g.add(q.head?100:10);g.sfx("pop");s.m[q.x+","+q.y]=4;if(s.seg[hi+1])s.seg[hi+1].head=true;s.seg.splice(hi,1);s.shot=null}
    else if(s.m[k]){if(--s.m[k]<=0){delete s.m[k];g.add(1)}g.tone(220,.03);s.shot=null}
    else if(s.spider&&Math.abs(s.shot.x-s.spider.x-4)<5&&Math.abs(s.shot.y-s.spider.y-3)<5){const d=Math.abs(s.py-s.spider.y),v=d<16?900:d<40?600:300;g.add(v);s.fx={x:s.spider.x,y:s.spider.y,v,t:50};s.spider=null;s.shot=null;g.sfx("boom")}}}
  const delay=Math.max(3,8-Math.floor(s.wave/2));if(++s.step>=delay){s.step=0;
   s.seg.forEach(q=>{const nx=q.x+q.dx;if(q.pz||nx<0||nx>=CW||s.m[nx+","+q.y]){q.dx=-q.dx;q.y+=q.dy;if(q.y>=CH-1){q.y=CH-1;q.dy=-1}else if(q.dy<0&&q.y<ZONE){q.dy=1;q.y=ZONE+1}q.pz=false}else q.x=nx});
   if(s.seg.length)g.tone(s.seg.length%2?140:120,.04,"triangle",.07)}
  for(const q of s.seg){if(Math.abs(q.x*T+4-(s.px+2))<6&&Math.abs(q.y*T+4-(s.py+2))<6){hit(g);return}}
  if(!s.spider&&--s.spT<=0){const l=Math.random()<.5;s.spider={x:l?-8:CW*T,y:ZONE*T+g.rnd(30),vx:l?1:-1,vy:1.2};s.spT=400+g.ri(300)}
  if(s.spider){const p=s.spider;p.x+=p.vx*(.8+s.wave*.05);p.y+=p.vy;if(p.y<ZONE*T-8||p.y>CH*T-8)p.vy=-p.vy;if(g.ticks%40==0)p.vy=(Math.random()<.5?-1:1)*(.6+Math.random());
   delete s.m[Math.floor((p.x+4)/T)+","+Math.floor((p.y+3)/T)];if(p.x<-12||p.x>CW*T+12)s.spider=null;else if(Math.abs(p.x+4-(s.px+2))<6&&Math.abs(p.y+3-(s.py+2))<6){hit(g);return}}
  if(!s.seg.length){s.wave++;g.add(500);g.sfx("power");bugs(g)}if(s.fx&&--s.fx.t<=0)s.fx=null},
 draw(g){const s=g.s;g.cls(0);g.rect(0,0,g.W,OY,1);g.text("SCORE "+g.score,2,2,7);g.text("WAVE "+s.wave,g.W/2,2,10,1,"c");for(let i=0;i<s.lives;i++)g.spr(GUN,g.W-8-i*8,2,{map:{7:12}});
  const Y=y=>OY+y;g.rect(0,Y(ZONE*T),g.W,1,1);
  for(const k in s.m){const [x,y]=k.split(",").map(Number),hp=s.m[k],X=x*T,YY=Y(y*T);g.rect(X+1,YY+1,6,Math.max(1,hp+(hp>2?0:0)),hp>2?14:2);g.rect(X+1,YY,6,1,hp>2?8:2);g.rect(X+3,YY+5,2,3,15)}
  s.seg.forEach(q=>{const X=q.x*T,YY=Y(q.y*T);g.circ(X+4,YY+4,3,q.head?8:11);g.rect(X+2,YY+3,1,1,0);g.rect(X+5,YY+3,1,1,0);if(q.head){g.px(X+1,YY,10);g.px(X+6,YY,10)}else g.px(X+(g.ticks>>3)%2?1:6,YY+7,3)});
  if(s.spider)g.spr(SPIDER,s.spider.x,Y(s.spider.y),{map:{1:13,8:8}});
  if(!s.dead||(s.dead>>2)%2)g.spr(GUN,s.px,Y(s.py),{map:{7:s.dead?8:12}});if(s.shot)g.rect(s.shot.x,Y(s.shot.y),1,5,10);
  if(s.fx)g.text(s.fx.v,s.fx.x+4,Y(s.fx.y),10,1,"c")}});
function hit(g){const s=g.s;s.lives--;s.dead=80;s.shot=null;g.sfx("boom")}
})();
