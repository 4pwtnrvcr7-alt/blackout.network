// Moon Lander: original lunar-landing game (inspired by Lunar Lander).
(()=>{const W=256,H=224;
function terrain(g){const s=g.s,pts=[];let y=170;for(let x=0;x<=W;x+=8){y=g.clamp(y+g.rnd(30)-15,110,205);pts.push([x,y])}
 s.pads=[];const used=new Set();[5,3,2].forEach((mult,k)=>{let i;do{i=2+g.ri(pts.length-6)}while([...used].some(u=>Math.abs(u-i)<5));used.add(i);const w=mult==5?1:mult==3?2:3;const yy=pts[i][1];for(let j=0;j<=w;j++)pts[i+j][1]=yy;s.pads.push({x0:pts[i][0],x1:pts[i+w][0],y:yy,mult})});s.ter=pts}
function round(g){const s=g.s;terrain(g);s.l={x:30+g.rnd(60),y:24,vx:.6,vy:0,a:0};s.landed=0;s.crash=0}
const groundY=(s,x)=>{x=Math.max(0,Math.min(W-.01,x));const i=Math.min(s.ter.length-2,Math.floor(x/8)),a=s.ter[i],b=s.ter[i+1];return a[1]+(b[1]-a[1])*((x-a[0])/8)};
BNG.register({id:"lander",name:"Moon Lander",inspired:"Lunar Lander-style thrust-and-gravity games",cats:["Arcade","Classic"],w:W,h:H,
 desc:"Touch down gently on a flat landing pad using as little fuel as you can. Smaller pads multiply your points. Land upright and slowly, or you'll crash.",
 controls:["Left/Right: rotate","Up / Space: main thruster","Land slowly (green speed) and upright"],
 init(g){const s=g.s;s.fuel=1000;s.lives=3;s.rounds=0;round(g)},
 update(g){const s=g.s,l=s.l;if(s.landed||s.crash){if(--s.wait<=0){if(s.crash){s.lives--;if(s.lives<=0||s.fuel<=0){g.over(s.fuel<=0?"OUT OF FUEL":"LANDER LOST");return}}round(g)}return}
  if(g.held("left"))l.a-=.04;if(g.held("right"))l.a+=.04;l.a=g.clamp(l.a,-1.6,1.6);s.thr=(g.held("up")||g.held("fire"))&&s.fuel>0;
  if(s.thr){l.vx+=Math.sin(l.a)*.045;l.vy-=Math.cos(l.a)*.045;s.fuel=Math.max(0,s.fuel-1);if(g.ticks%5==0)g.noise(.08,.04,0,300)}
  l.vy+=.016;l.x+=l.vx;l.y+=l.vy;if(l.x<0)l.x+=W;if(l.x>W)l.x-=W;if(l.y<4){l.y=4;l.vy=Math.max(0,l.vy)}
  const gy=Math.min(groundY(s,l.x-4),groundY(s,l.x+4));if(l.y+5>=gy){const pad=s.pads.find(p=>l.x-4>=p.x0&&l.x+4<=p.x1);
   if(pad&&Math.abs(l.vy)<.6&&Math.abs(l.vx)<.4&&Math.abs(l.a)<.2){s.landed=1;s.wait=120;l.y=pad.y-5;const pts=50*pad.mult+Math.floor(s.fuel/20);g.add(pts);s.msg="LANDED! +"+pts;s.rounds++;s.fuel=Math.min(1000,s.fuel+120);g.sfx("win")}
   else{s.crash=1;s.wait=120;s.msg=pad?"TOO FAST - CRASHED":"CRASHED";s.fuel=Math.max(0,s.fuel-150);g.sfx("boom");s.debris=Array.from({length:14},()=>({x:l.x,y:l.y,vx:g.rnd(3)-1.5,vy:-g.rnd(2.5)}))}}},
 draw(g){const s=g.s,l=s.l;g.cls(0);for(let i=0;i<50;i++)g.px((i*89)%W,(i*47)%120,i%5?5:7);g.circ(220,30,10,6);g.circ(224,27,9,0);
  for(let i=0;i<s.ter.length-1;i++){const [x1,y1]=s.ter[i],[x2,y2]=s.ter[i+1];for(let x=x1;x<x2;x++){const y=y1+(y2-y1)*(x-x1)/8;g.rect(x,y,1,H-y,5);g.px(x,y,6)}}
  s.pads.forEach(p=>{g.rect(p.x0,p.y,p.x1-p.x0,2,10);g.text("X"+p.mult,(p.x0+p.x1)/2,p.y+5,10,1,"c")});
  if(s.crash){(s.debris||[]).forEach(d=>{d.x+=d.vx;d.y+=d.vy;d.vy+=.05;if(d.y<groundY(s,d.x))g.rect(d.x,d.y,2,2,g.pick([9,8,6]))})}
  else{const c=Math.cos(l.a),sn=Math.sin(l.a),P=(x,y)=>[l.x+x*c-y*sn,l.y+x*sn+y*c];
   const body=[[-3,-5],[3,-5],[4,-1],[-4,-1]];for(let i=0;i<4;i++)g.line(...P(...body[i]),...P(...body[(i+1)%4]),7);g.line(...P(-4,-1),...P(-5,5),6);g.line(...P(4,-1),...P(5,5),6);g.line(...P(-6,5),...P(-4,5),6);g.line(...P(4,5),...P(6,5),6);
   g.px(...P(0,-3),12);if(s.thr&&g.ticks%3)g.line(...P(0,0),...P(0,4+g.ri(4)),9)}
  const sp=c=>c?11:8;g.text("SCORE "+g.score,3,3,7);g.text("FUEL",3,11,6);g.rect(22,11,s.fuel/1000*60,5,s.fuel<200?8:10);g.text("LANDERS "+s.lives,W-3,3,7,1,"r");
  g.text("H-SPD "+Math.abs(l.vx*10).toFixed(0),W-3,11,sp(Math.abs(l.vx)<.4),1,"r");g.text("V-SPD "+(l.vy*10).toFixed(0),W-3,19,sp(Math.abs(l.vy)<.6),1,"r");if(s.msg&&(s.landed||s.crash))g.text(s.msg,W/2,80,s.landed?11:8,2,"c")}});
})();
