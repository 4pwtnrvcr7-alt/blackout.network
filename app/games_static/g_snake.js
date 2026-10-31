// Snake: original implementation.
(()=>{const CW=32,CH=26,T=8,OY=16;
const APPLE=["..33....","...3....",".8888...","888878..","8888888.","8888888.",".88888..","..888..."];
function food(g){const s=g.s;for(let i=0;i<999;i++){const f={x:g.ri(CW),y:g.ri(CH)};if(!s.body.some(b=>b.x==f.x&&b.y==f.y)){s.food=f;return}}}
BNG.register({id:"snake",name:"Snake",inspired:"the classic Snake / Nibbles arcade and phone games",cats:["Arcade","Classic"],w:256,h:224,
 desc:"Steer a growing pixel snake to the fruit without biting the walls or your own tail. Each fruit is worth more as the snake speeds up.",
 controls:["Arrows / WASD: steer","Eat fruit, avoid walls and your tail"],
 init(g){const s=g.s;s.body=[{x:8,y:13},{x:7,y:13},{x:6,y:13}];s.dir={x:1,y:0};s.q=[];s.step=0;s.speed=9;s.eaten=0;food(g)},
 key(g,a){const D={left:{x:-1,y:0},right:{x:1,y:0},up:{x:0,y:-1},down:{x:0,y:1}}[a];if(!D)return;const s=g.s,last=s.q.length?s.q[s.q.length-1]:s.dir;
  if((D.x==-last.x&&D.y==-last.y)||(D.x==last.x&&D.y==last.y)||s.q.length>2)return;s.q.push(D)},
 update(g){const s=g.s;if(++s.step<s.speed)return;s.step=0;if(s.q.length)s.dir=s.q.shift();
  const h={x:s.body[0].x+s.dir.x,y:s.body[0].y+s.dir.y};const grow=h.x==s.food.x&&h.y==s.food.y;
  if(h.x<0||h.y<0||h.x>=CW||h.y>=CH||s.body.slice(0,grow?s.body.length:s.body.length-1).some(b=>b.x==h.x&&b.y==h.y)){g.over("YOU CRASHED!");return}
  s.body.unshift(h);if(grow){s.eaten++;g.add(10+(9-s.speed)*5);g.sfx("eat");s.speed=Math.max(3,9-Math.floor(s.eaten/5));food(g)}else{s.body.pop();g.sfx("step")}},
 draw(g){const s=g.s;g.cls(1);g.rect(0,0,256,OY,0);g.text("SNAKE",4,5,11);g.text("SCORE "+g.score,252,5,7,1,"r");g.text("LEN "+s.body.length,128,5,6,1,"c");
  for(let y=0;y<CH;y++)for(let x=0;x<CW;x++)if((x+y)%2)g.rect(x*T,OY+y*T,T,T,"#22305c");
  g.spr(APPLE,s.food.x*T,OY+s.food.y*T);
  s.body.forEach((b,i)=>{g.rect(b.x*T,OY+b.y*T,T,T,i?(i%2?3:11):11);if(i)g.rect(b.x*T+2,OY+b.y*T+2,4,4,i%2?11:3)});
  const h=s.body[0],d=s.dir;g.rect(h.x*T+(d.x>0?5:d.x<0?1:1),OY+h.y*T+(d.y>0?5:d.y<0?1:1),2,2,0);g.rect(h.x*T+(d.x>0?5:d.x<0?1:5),OY+h.y*T+(d.y>0?5:d.y<0?1:5),2,2,0)}});
})();
