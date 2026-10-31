// Tunnel Digger: original dig-and-pump underground game (inspired by Dig Dug).
(()=>{const T=16,CW=14,CH=13,OY=16;
const DIG=["..cccc..",".cccccc.",".c7777c.","cc7070cc",".cccccc.","..9999..",".999999.","..4..4.."];
const PUF=["..8888..",".888888.","88777788","88707088","88888888","88888888",".88..88.","88....88"];
const GHOST=["........","........","..7..7..","..0..0..","........","........","........","........"];
function lvl(g){const s=g.s;s.dirt=[];for(let y=0;y<CH;y++){s.dirt.push([]);for(let x=0;x<CW;x++)s.dirt[y].push(y>0)}
 const dig=(x,y)=>{if(y>=0&&y<CH&&x>=0&&x<CW)s.dirt[y][x]=false};for(let y=1;y<=6;y++)dig(7,y);for(let x=5;x<=9;x++)dig(x,6);
 s.p={x:7,y:0,fx:7,fy:0,mv:0,face:[0,1]};s.en=[];const n=Math.min(8,3+s.lv);
 for(let i=0;i<n;i++){let x,y;do{x=1+g.ri(CW-2);y=3+g.ri(CH-4)}while(Math.abs(x-7)<3&&y<8);for(let k=-1;k<=1;k++)dig(x+k,y);s.en.push({x,y,fx:x,fy:y,mv:0,inf:0,ghost:0,gt:300+g.ri(600),pts:y<5?200:y<8?300:400,dead:0})}
 s.rocks=[];for(let i=0;i<3;i++){let x,y;do{x=1+g.ri(CW-2);y=2+g.ri(CH-5)}while(!s.dirt[y][x]||!s.dirt[y+1][x]||s.rocks.some(r=>r.x==x&&r.y==y)||x==7);s.rocks.push({x,y,st:"rest",t:0,fy:y,kills:0})}s.pump=null;s.dead=0}
const blocked=(s,x,y,ghost)=>x<0||y<0||x>=CW||y>=CH||s.rocks.some(r=>r.x==x&&Math.round(r.fy)==y)||(!ghost&&s.dirt[y][x]);
BNG.register({id:"digger",name:"Tunnel Digger",inspired:"Dig Dug-style tunneling games",cats:["Arcade","Action","Classic"],w:CW*T,h:CH*T+OY,
 desc:"Dig tunnels through layered dirt and pump up the goggled Puffers until they pop. Dig under a rock to drop it on them for big points. Puffers can drift through the dirt as ghosts.",
 controls:["Arrows / WASD: dig and move","Space: fire the pump (tap repeatedly to pop)"],
 init(g){const s=g.s;s.lv=1;s.lives=3;lvl(g)},
 key(g,a){const s=g.s,p=s.p;if(a=="fire"&&!s.dead){const [dx,dy]=p.face;let len=0,hit=null;for(let k=1;k<=3;k++){const x=p.x+dx*k,y=p.y+dy*k;if(x<0||y<0||x>=CW||y>=CH||s.dirt[y][x])break;len=k;const e=s.en.find(e=>!e.dead&&Math.round(e.fx)==x&&Math.round(e.fy)==y);if(e){hit=e;break}}
  s.pump={len,t:10};if(hit){hit.inf++;hit.deflate=90;g.tone(300+hit.inf*120,.08,"square",.05);if(hit.inf>=4){hit.dead=30;g.add(hit.pts);g.sfx("pop")}}else g.tone(200,.05)}},
 update(g){const s=g.s,p=s.p;if(s.dead){if(--s.dead==0){s.lives--;if(s.lives<=0){g.over("GOT YOU!");return}s.p={x:7,y:0,fx:7,fy:0,mv:0,face:[0,1]};s.en.forEach(e=>{e.inf=0;e.ghost=0})}return}
  if(s.clear){if(--s.clear==0){s.lv++;lvl(g)}return}
  if(s.pump&&--s.pump.t<=0)s.pump=null;
  if(p.mv>0){p.mv--;p.fx+=(p.x-p.fx)/(p.mv+1);p.fy+=(p.y-p.fy)/(p.mv+1)}else{p.fx=p.x;p.fy=p.y;
   const d=g.held("left")?[-1,0]:g.held("right")?[1,0]:g.held("up")?[0,-1]:g.held("down")?[0,1]:null;
   if(d&&!s.pump){p.face=d;const nx=p.x+d[0],ny=p.y+d[1];if(nx>=0&&ny>=0&&nx<CW&&ny<CH&&!s.rocks.some(r=>r.x==nx&&Math.round(r.fy)==ny)){const dug=s.dirt[ny][nx];s.dirt[ny][nx]=false;p.x=nx;p.y=ny;p.mv=dug?10:7;if(dug){g.add(1);if(g.ticks%2==0)g.tone(90+ny*6,.04,"triangle",.06)}}}}
  s.rocks.forEach(r=>{if(r.st=="rest"){if(r.y+1<CH&&!s.dirt[r.y+1][r.x]&&!(p.x==r.x&&p.y==r.y+1&&p.mv==0&&false)){r.st="wobble";r.t=50}}
   else if(r.st=="wobble"){if(--r.t<=0){r.st="fall";g.tone(400,.5,"square",.04,80)}}
   else if(r.st=="fall"){r.fy+=.18;const ty=Math.floor(r.fy)+1;
    s.en.forEach(e=>{if(!e.dead&&Math.round(e.fx)==r.x&&Math.abs(e.fy-r.fy)<.9){e.dead=40;e.crushed=1;r.kills++}});
    if(Math.round(p.fx)==r.x&&Math.abs(p.fy-r.fy)<.8){s.dead=90;g.sfx("die")}
    if(ty>=CH||s.dirt[ty][r.x]){r.st="gone";r.t=40;r.y=ty-1;r.fy=r.y;g.sfx("boom");if(r.kills)g.add([0,1000,2500,4000,6000,8000][Math.min(5,r.kills)])}}
   else if(r.st=="gone")r.t--});
  s.rocks=s.rocks.filter(r=>r.st!="gone"||r.t>0);
  s.en.forEach(e=>{if(e.dead){if(--e.dead<=0)e.gone=true;return}if(e.inf>0){if(--e.deflate<=0){e.inf--;e.deflate=60}return}
   if(e.mv>0){e.mv--;e.fx+=(e.x-e.fx)/(e.mv+1);e.fy+=(e.y-e.fy)/(e.mv+1);return}e.fx=e.x;e.fy=e.y;
   if(e.ghost>0){e.ghost--;if(e.ghost==0&&s.dirt[e.y][e.x])e.ghost=1}else if(--e.gt<=0){e.gt=400+g.ri(500)-s.lv*30;e.ghost=120+g.ri(120)}
   const opts=[[1,0],[-1,0],[0,1],[0,-1]].filter(([dx,dy])=>!blocked(s,e.x+dx,e.y+dy,e.ghost>0)&&e.y+dy>=0);if(!opts.length)return;
   let best=opts[0],bd=1e9;opts.forEach(o=>{const d=Math.abs(e.x+o[0]-p.x)+Math.abs(e.y+o[1]-p.y)+(o[0]==-(e.ld||[0,0])[0]&&o[1]==-(e.ld||[0,0])[1]?2:0)+Math.random()*1.5;if(d<bd){bd=d;best=o}});
   e.ld=best;e.x+=best[0];e.y+=best[1];e.mv=e.ghost?22:Math.max(9,16-s.lv)});
  s.en=s.en.filter(e=>!e.gone);
  for(const e of s.en)if(!e.dead&&!e.inf&&Math.abs(e.fx-p.fx)<.7&&Math.abs(e.fy-p.fy)<.7){s.dead=90;g.sfx("die");break}
  if(!s.en.length&&!s.clear){s.clear=90;g.add(1000);g.sfx("win")}},
 draw(g){const s=g.s,p=s.p;g.cls(12);g.rect(0,0,g.W,OY,0);const lay=[9,4,2,1];
  for(let y=1;y<CH;y++)for(let x=0;x<CW;x++){const X=x*T,Y=OY+y*T;const c=lay[Math.min(3,Math.floor((y-1)/3))];if(s.dirt[y][x]){g.rect(X,Y,T,T,c);if((x*7+y*3)%4==0)g.px(X+5,Y+7,0);if((x+y)%3==0)g.px(X+11,Y+3,15)}else g.rect(X,Y,T,T,0)}
  g.rect(0,OY,g.W,T,12);g.circ(g.W-20,OY+6,5,10);
  s.rocks.forEach(r=>{if(r.st=="gone"&&(r.t>>2)%2)return;const X=r.x*T+(r.st=="wobble"?((g.ticks>>2)%2?1:-1):0),Y=OY+r.fy*T;g.circ(X+8,Y+8,7,6);g.circ(X+6,Y+6,3,7);g.px(X+10,Y+11,5)});
  if(s.pump&&s.pump.len){const [dx,dy]=p.face;for(let k=1;k<=s.pump.len;k++)g.rect(p.fx*T+8+dx*(k*T-8)-(dy?1:0)-(dx?4:0),OY+p.fy*T+8+dy*(k*T-8)-(dx?1:0)-(dy?4:0),dx?T:2,dy?T:2,7)}
  s.en.forEach(e=>{const X=e.fx*T,Y=OY+e.fy*T;if(e.dead){if(!e.crushed)g.circ(X+8,Y+8,8+(30-e.dead)/4,(e.dead>>1)%2?7:8);else g.rect(X+2,Y+12,12,3,8);return}
   if(e.ghost)g.spr(GHOST,X+4,Y+4);else if(e.inf){g.circ(X+8,Y+8,5+e.inf*2,8);g.rect(X+5,Y+6,2,2,7);g.rect(X+10,Y+6,2,2,7)}else g.spr(PUF,X+4,Y+4,{flip:(g.ticks>>3)%2,s:1})});
  if(!(s.dead&&(s.dead>>2)%2))g.spr(DIG,p.fx*T+4,OY+p.fy*T+4,{flip:p.face[0]<0});
  g.text("SCORE "+g.score,3,5,7);g.text("ROUND "+s.lv,g.W/2,5,10,1,"c");for(let i=0;i<s.lives;i++)g.rect(g.W-8-i*7,5,5,5,12);if(s.clear)g.text("ROUND CLEAR!",g.W/2,OY+40,10,2,"c")}});
})();
