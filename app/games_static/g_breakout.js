// Brick Breaker: original paddle-and-ball game (inspired by Breakout).
(()=>{const W=256,H=224,PW=34;
const LV=[r=>true,(r,c)=>(r+c)%2==0||r<2,(r,c)=>Math.abs(c-5.5)<r+1,(r,c)=>c%3!=1||r%2==0];
function bricks(g){const s=g.s,f=LV[(s.level-1)%LV.length];s.br=[];for(let r=0;r<6;r++)for(let c=0;c<12;c++)if(f(r,c))s.br.push({x:8+c*20,y:28+r*10,c:[8,9,10,11,12,14][r],hp:r==0&&s.level>2?2:1,pts:(6-r)*10})}
function serve(g){const s=g.s;s.stuck=true;s.bx=s.px+PW/2;s.by=196;s.vx=0;s.vy=0}
BNG.register({id:"breakout",name:"Brick Breaker",inspired:"Breakout-style paddle and brick games",cats:["Arcade","Classic"],w:W,h:H,
 desc:"Bounce the ball off your paddle to smash every brick. Where the ball hits the paddle sets its angle. Clear a wall to move on to a new layout.",
 controls:["Left/Right: move paddle","Space: launch ball","Mouse also moves the paddle"],
 init(g){const s=g.s;s.px=W/2-PW/2;s.lives=3;s.level=1;bricks(g);serve(g);s.spd=2.4},
 mouse(g,x){g.s.px=g.clamp(x-PW/2,4,W-4-PW)},
 click(g){if(g.s.stuck)this.key(g,"fire")},
 key(g,a){const s=g.s;if(a=="fire"&&s.stuck){s.stuck=false;const an=-Math.PI/2+(Math.random()-.5)*.8;s.vx=Math.cos(an)*s.spd;s.vy=Math.sin(an)*s.spd;g.sfx("jump")}},
 update(g){const s=g.s;if(g.held("left"))s.px-=4;if(g.held("right"))s.px+=4;s.px=g.clamp(s.px,4,W-4-PW);
  if(s.stuck){s.bx=s.px+PW/2;s.by=196;return}
  for(let k=0;k<2;k++){s.bx+=s.vx/2;s.by+=s.vy/2;
   if(s.bx<6){s.bx=6;s.vx=Math.abs(s.vx);g.sfx("bump")}if(s.bx>W-6){s.bx=W-6;s.vx=-Math.abs(s.vx);g.sfx("bump")}if(s.by<18){s.by=18;s.vy=Math.abs(s.vy);g.sfx("bump")}
   if(s.vy>0&&s.by>=198&&s.by<=204&&s.bx>=s.px-2&&s.bx<=s.px+PW+2){const o=(s.bx-(s.px+PW/2))/(PW/2),an=-Math.PI/2+o*1.05;s.vx=Math.cos(an)*s.spd;s.vy=Math.sin(an)*s.spd;s.by=197;g.sfx("click")}
   for(let i=0;i<s.br.length;i++){const b=s.br[i];if(s.bx+2>b.x&&s.bx-2<b.x+18&&s.by+2>b.y&&s.by-2<b.y+8){
     const ox=Math.min(s.bx+2-b.x,b.x+18-(s.bx-2)),oy=Math.min(s.by+2-b.y,b.y+8-(s.by-2));if(ox<oy)s.vx=-s.vx;else s.vy=-s.vy;
     if(--b.hp<=0){s.br.splice(i,1);g.add(b.pts);g.tone(400+b.pts*8,.06,"square",.05)}else g.sfx("bump");s.spd=Math.min(4.2,s.spd+.02);const m=Math.hypot(s.vx,s.vy);s.vx*=s.spd/m;s.vy*=s.spd/m;break}}}
  if(s.by>H+4){s.lives--;g.sfx("hit");if(s.lives<=0){g.over();return}serve(g)}
  if(!s.br.length){s.level++;g.add(500);g.sfx("power");s.spd=2.4+s.level*.15;bricks(g);serve(g)}},
 draw(g){const s=g.s;g.cls(1);g.rect(0,0,W,14,0);g.text("SCORE "+g.score,4,4,7);g.text("LEVEL "+s.level,128,4,10,1,"c");for(let i=0;i<s.lives;i++)g.circ(W-10-i*9,6,2,8);
  g.rect(0,14,4,H,6);g.rect(W-4,14,4,H,6);g.rect(0,14,W,2,6);
  s.br.forEach(b=>{g.rect(b.x,b.y,18,8,b.c);g.rect(b.x,b.y,18,1,7);g.rect(b.x,b.y+7,18,1,0);if(b.hp>1)g.rect(b.x+7,b.y+3,4,2,7)});
  g.rect(s.px,200,PW,5,12);g.rect(s.px+2,200,PW-4,1,7);g.rect(s.px,204,PW,1,1);g.rect(s.px-2,201,2,3,8);g.rect(s.px+PW,201,2,3,8);
  g.rect(s.bx-2,s.by-2,4,4,7);if(s.stuck)g.text("SPACE TO LAUNCH",W/2,170,6,1,"c")}});
})();
