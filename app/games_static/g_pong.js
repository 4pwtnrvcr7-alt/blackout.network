// Paddle Duel: original two-paddle tennis vs a CPU (inspired by Pong).
(()=>{const W=256,H=192,PH=28,WIN=7;
function serve(g,dir){const s=g.s;s.bx=W/2;s.by=H/2;const an=(Math.random()-.5)*.9;s.sp=2.2;s.vx=Math.cos(an)*s.sp*dir;s.vy=Math.sin(an)*s.sp;s.wait=50}
BNG.register({id:"pong",name:"Paddle Duel",inspired:"Pong and early arcade tennis games",cats:["Arcade","Classic"],w:W,h:H,
 desc:"Two paddles, one square ball. Beat the CPU to 7 points. Hitting the ball near the edge of your paddle angles it, and long rallies speed it up.",
 controls:["Up/Down or W/S: move paddle","First to 7 wins"],
 init(g){const s=g.s;s.py=H/2-PH/2;s.cy=H/2-PH/2;s.ps=0;s.cs=0;s.rally=0;serve(g,1)},
 update(g){const s=g.s;if(g.held("up"))s.py-=3.2;if(g.held("down"))s.py+=3.2;s.py=g.clamp(s.py,10,H-PH-2);
  const tgt=(s.vx>0?s.by:H/2)-PH/2+Math.sin(g.ticks/40)*8;const cs=1.9+Math.min(1.2,s.ps*.12);s.cy+=g.clamp(tgt-s.cy,-cs,cs);s.cy=g.clamp(s.cy,10,H-PH-2);
  if(s.wait>0){s.wait--;return}
  for(let k=0;k<2;k++){s.bx+=s.vx/2;s.by+=s.vy/2;if(s.by<11){s.by=11;s.vy=-s.vy;g.tone(300,.04)}if(s.by>H-3){s.by=H-3;s.vy=-s.vy;g.tone(300,.04)}
   const hit=(px,py,dir)=>{const o=(s.by-(py+PH/2))/(PH/2);s.sp=Math.min(5,s.sp+.15);const an=o*1.0;s.vx=Math.cos(an)*s.sp*dir;s.vy=Math.sin(an)*s.sp};
   if(s.vx<0&&s.bx<=14&&s.bx>=8&&s.by>=s.py-2&&s.by<=s.py+PH+2){hit(12,s.py,1);s.bx=15;s.rally++;g.add(10);g.tone(520,.05)}
   if(s.vx>0&&s.bx>=W-14&&s.bx<=W-8&&s.by>=s.cy-2&&s.by<=s.cy+PH+2){hit(W-12,s.cy,-1);s.bx=W-15;g.tone(440,.05)}}
  if(s.bx<-6){s.cs++;g.sfx("bad");if(s.cs>=WIN){g.over("CPU WINS "+s.cs+"-"+s.ps);return}serve(g,1)}
  if(s.bx>W+6){s.ps++;g.add(100);g.sfx("coin");if(s.ps>=WIN){g.add(500);g.win("YOU WIN "+s.ps+"-"+s.cs);return}serve(g,-1)}},
 draw(g){const s=g.s;g.cls(0);g.rect(0,8,W,2,6);for(let y=12;y<H;y+=8)g.rect(W/2-1,y,2,4,5);
  g.text(s.ps,W/2-24,16,7,3,"c");g.text(s.cs,W/2+24,16,7,3,"c");g.text("YOU",30,1,12);g.text("CPU",W-30,1,8,1,"r");g.text("SCORE "+g.score,W/2,1,6,1,"c");
  g.rect(8,s.py,4,PH,12);g.rect(W-12,s.cy,4,PH,8);if(s.wait<=0||(s.wait>>3)%2)g.rect(s.bx-2,s.by-2,4,4,7)}});
})();
