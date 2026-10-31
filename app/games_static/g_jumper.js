// Pixel Jumper: original side-scrolling platformer (inspired by Super Mario Bros.-style games). Original hero, enemies, tiles and levels.
(()=>{const T=16,W=256,H=224,ROWS=14;
const HERO=["...cccc.....","..cccccccc..","..ff0ff0....","..ffffffff..","...ffff.....","..999c999...",".9999c99999.",".ff99999.ff.","..999999....","..9999999...","..44..444...",".444...444..","............","............"];
const HERO2=["...cccc.....","..cccccccc..","..ff0ff0....","..ffffffff..","...ffff.....","..999c999...",".9999c9999..","..ff9999ff..","..999999....","...99999....","...444......","..4444......","............","............"];
const BLOB=["....dddd......","..dddddddd....",".dd77dd77dd...",".dd70dd70dd...","dddddddddddd..","dddd2222dddd..","dddddddddddd..",".dddddddddd...","..dd....dd....","..22....22...."];
const FRUIT=["....33......","...3........","..aaaaaa....",".aa7aaaaa...","aaaaaaaaaa..","aaaaa9aaaa..","aaaa999aaa..",".aaaa9aaa...","..aaaaaa....","...aaaa....."];
const SOLID=new Set(["#","B","?","M","U","=","P","q"]);
// level builder: ground, pits, blocks, coins, enemies, pipes, stairs, flag
const LV=[
 {len:150,pits:[[38,40],[78,80],[110,112]],blk:[[16,8,"?"],[20,8,"B?B?B"],[22,4,"M"],[46,8,"BBB"],[47,4,"B?B"],[62,8,"?M?"],[86,8,"BB"],[86,4,"?"],[96,8,"B??B"]],coins:[[20,6,5],[46,6,3],[70,9,4],[100,7,3]],pipes:[[30,2],[56,3],[72,2]],en:[24,34,48,52,66,84,90,98,104,120],stairs:[[126,4,1],[134,4,-1]],sky:12},
 {len:170,pits:[[30,33],[60,62],[96,99],[128,130]],blk:[[14,8,"?B?"],[24,8,"BMB"],[40,8,"BBBBB"],[42,4,"?"],[68,8,"?=?"],[80,6,"BBBB"],[82,2,"?"],[104,8,"B?B"],[118,8,"=?="],[140,8,"?"]],coins:[[30,7,4],[60,6,3],[96,7,4],[128,6,3],[44,2,3]],pipes:[[20,2],[50,3],[90,4],[114,2]],en:[18,26,36,44,46,54,66,74,84,88,102,108,122,136,142],stairs:[[148,5,1]],sky:1},
 {len:190,pits:[[24,27],[44,47],[70,73],[100,103],[126,130],[150,152]],blk:[[12,8,"?M?"],[30,7,"==="],[36,8,"B?B"],[52,8,"BB?BB"],[54,4,"M"],[78,7,"=="],[84,8,"?B?"],[106,8,"B?B?B"],[116,4,"="],[134,7,"==="],[135,3,"?"],[156,8,"BMB"]],coins:[[24,6,4],[44,6,4],[70,6,4],[100,6,4],[126,6,4],[150,6,3]],pipes:[[18,3],[64,4],[94,3],[120,2],[146,3]],en:[16,20,32,38,50,54,58,66,80,88,92,108,112,118,124,138,142,160,166],stairs:[[168,6,1]],sky:2}];
function build(n){const d=LV[n],L=d.len,m=[];for(let y=0;y<ROWS;y++)m.push(new Array(L).fill(" "));const set=(x,y,c)=>{if(x>=0&&x<L&&y>=0&&y<ROWS)m[y][x]=c};
 for(let x=0;x<L;x++)if(!d.pits.some(([a,b])=>x>=a&&x<=b)){set(x,12,"#");set(x,13,"#")}
 d.blk.forEach(([x,y,str])=>[...str].forEach((c,i)=>set(x+i,y,c)));d.coins.forEach(([x,y,n])=>{for(let i=0;i<n;i++)if(m[y][x+i]==" ")set(x+i,y,"o")});
 d.pipes.forEach(([x,h])=>{for(let y=12-h;y<12;y++){set(x,y,y==12-h?"q":"P");set(x+1,y,y==12-h?"q":"P")}});
 d.stairs.forEach(([x,h,dir])=>{for(let i=0;i<h;i++)for(let y=0;y<=i;y++)set(dir>0?x+i:x+h-1-i,11-y,"=")});
 const fx=L-10;for(let y=2;y<12;y++)set(fx,y,"|");set(fx,12,"#");set(fx,11,"=");
 return{m,L,fx,en:d.en.map(x=>({x:x*T,y:10*T,vx:-.5,vy:0,alive:true,squash:0,act:false})),sky:d.sky}}
function start(g,keep){const s=g.s;const b=build(s.lv);s.m=b.m;s.L=b.L;s.fx=b.fx;s.en=b.en;s.sky=b.sky;s.items=[];s.parts=[];s.p={x:2*T,y:10*T,vx:0,vy:0,on:false,face:1,big:keep&&s.big?1:0,inv:0};s.big=s.p.big;s.cam=0;s.time=300*60;s.dead=0;s.clear=0}
const tile=(s,x,y)=>y<0||y>=ROWS||x<0||x>=s.L?(x<0?"=":" "):s.m[y][x];
const solidAt=(s,px,py)=>SOLID.has(tile(s,Math.floor(px/T),Math.floor(py/T)));
function collide(s,o,w,h,onHead){o.x+=o.vx;if(o.vx>0&&(solidAt(s,o.x+w,o.y+1)||solidAt(s,o.x+w,o.y+h-1)||(h>T&&solidAt(s,o.x+w,o.y+h/2)))){o.x=Math.floor((o.x+w)/T)*T-w-.01;o.vx=o.hitw?-Math.abs(o.vx):0;o.wall=1}
 else if(o.vx<0&&(solidAt(s,o.x,o.y+1)||solidAt(s,o.x,o.y+h-1)||(h>T&&solidAt(s,o.x,o.y+h/2)))){o.x=Math.floor(o.x/T+1)*T+.01;o.vx=o.hitw?Math.abs(o.vx):0;o.wall=-1}
 o.y+=o.vy;o.on=false;if(o.vy>=0&&(solidAt(s,o.x+1,o.y+h)||solidAt(s,o.x+w-1,o.y+h))){o.y=Math.floor((o.y+h)/T)*T-h;o.vy=0;o.on=true}
 else if(o.vy<0&&(solidAt(s,o.x+2,o.y)||solidAt(s,o.x+w-2,o.y))){const tx=Math.floor((o.x+w/2)/T),ty=Math.floor(o.y/T);o.y=(ty+1)*T;o.vy=0;if(onHead)onHead(tx,ty)}}
BNG.register({id:"jumper",name:"Pixel Jumper",inspired:"Super Mario Bros.-style side-scrolling platformers",cats:["Action","Arcade","Classic"],w:W,h:H,
 desc:"Run and jump through three original side-scrolling levels as a little teal-capped explorer. Stomp purple blobs, bonk ? blocks for coins, grab a star-fruit to grow, and reach the flag.",
 controls:["Left/Right: run","Up / Space / Z: jump (hold for higher)","Shift or X: sprint","Stomp blobs; avoid their sides; reach the flag"],
 init(g){const s=g.s;s.lv=0;s.lives=3;s.coins=0;s.big=0;start(g)},
 key(g,a,code){const s=g.s,p=s.p;if((a=="up"||a=="fire"||code=="KeyZ")&&p.on&&!s.dead&&!s.clear){p.vy=-6.2;p.on=false;p.jh=12;g.sfx("jump")}},
 update(g){const s=g.s,p=s.p;s.parts=s.parts.filter(q=>{q.x+=q.vx;q.y+=q.vy;q.vy+=.3;return--q.t>0});
  if(s.dead){if(--s.dead==0){s.lives--;if(s.lives<=0){g.over();return}s.big=0;start(g)}else if(s.dead<70){p.y+=p.vy;p.vy+=.3}return}
  if(s.clear){s.clear--;if(p.y<12*T-(p.big?28:14)-.5)p.y=Math.min(12*T-(p.big?28:14),p.y+2);else if(p.x<(s.fx+4)*T)p.x+=1;if(s.clear==0){s.lv++;if(s.lv>=LV.length){g.add(5000);g.win("ALL 3 LEVELS CLEARED!");return}start(g,true)}return}
  if(--s.time<=0){die(g);return}
  const run=g.held("ShiftLeft")||g.held("ShiftRight")||g.held("KeyX"),mx=run?3:2,ac=p.on?.25:.15;
  if(g.held("left")){p.vx=Math.max(-mx,p.vx-ac);p.face=-1}else if(g.held("right")){p.vx=Math.min(mx,p.vx+ac);p.face=1}else{p.vx*=p.on?.8:.95;if(Math.abs(p.vx)<.1)p.vx=0}
  const jumpHeld=g.held("up")||g.held("fire")||g.held("KeyZ");if(p.vy<0&&jumpHeld&&p.jh>0){p.vy-=.18;p.jh--}if(!jumpHeld)p.jh=0;
  p.vy=Math.min(7,p.vy+.4);const ph=p.big?28:14,pw=11;
  collide(s,p,pw,ph,(tx,ty)=>{const c=s.m[ty][tx];if(c=="?"||c=="M"){s.m[ty][tx]="U";if(c=="?"){g.add(100);s.coins++;g.sfx("coin");s.parts.push({x:tx*T+4,y:ty*T-8,vx:0,vy:-4,t:22,coin:1})}else{s.items.push({x:tx*T+2,y:ty*T-12,vx:1,vy:-2,rise:12});g.sfx("power")}}
   else if(c=="B"){if(p.big){s.m[ty][tx]=" ";g.add(50);g.sfx("boom");for(let i=0;i<4;i++)s.parts.push({x:tx*T+8,y:ty*T+8,vx:(i%2?1:-1)*(1+Math.random()),vy:-3-Math.random()*2,t:40})}else g.sfx("bump")}else g.sfx("bump");
   s.en.forEach(e=>{if(e.alive&&Math.abs(e.x+7-(tx*T+8))<14&&Math.abs(e.y+10-ty*T)<6){e.alive=false;e.flip=1;e.vy=-3;g.add(200)}})});
  if(p.x<s.cam)p.x=s.cam,p.vx=Math.max(0,p.vx);
  // coins
  for(const [dx,dy] of [[2,2],[pw-2,2],[2,ph-2],[pw-2,ph-2]]){const tx=Math.floor((p.x+dx)/T),ty=Math.floor((p.y+dy)/T);if(tile(s,tx,ty)=="o"){s.m[ty][tx]=" ";g.add(100);s.coins++;g.sfx("coin")}}
  if(s.coins>=50){s.coins-=50;s.lives++;g.sfx("power")}
  if(p.y>H+16){die(g);return}if(p.inv)p.inv--;
  if(Math.floor((p.x+pw)/T)>=s.fx){s.clear=120;g.add(Math.floor(s.time/60)*10+(p.y<6*T?2000:p.y<9*T?800:200));g.sfx("win");p.vx=0;return}
  s.items=s.items.filter(it=>{if(it.rise>0){it.rise--;it.y-=1;return true}it.vy=Math.min(6,it.vy+.35);it.hitw=1;collide(s,it,12,10);if(it.y>H)return false;
   if(Math.abs(it.x+6-(p.x+pw/2))<12&&Math.abs(it.y+5-(p.y+ph/2))<ph/2+5){if(!p.big){p.big=1;s.big=1;p.y-=14}g.add(1000);g.sfx("power");return false}return true});
  s.en.forEach(e=>{if(!e.act&&e.x<s.cam+W+16)e.act=true;if(!e.act)return;if(e.flip){e.y+=e.vy;e.vy+=.3;return}if(!e.alive){e.squash--;return}
   e.vy=Math.min(6,e.vy+.4);e.hitw=1;collide(s,e,14,10);if(e.y>H){e.alive=false;e.squash=0;return}
   const ox=Math.abs(e.x+7-(p.x+pw/2))<12,oy=p.y+ph>e.y&&p.y<e.y+10;if(ox&&oy){if(p.vy>0&&p.y+ph-e.y<10){e.alive=false;e.squash=30;p.vy=jumpHeld?-6:-4;g.add(100);g.sfx("pop")}
    else if(!p.inv){if(p.big){p.big=0;s.big=0;p.y+=14;p.inv=100;g.sfx("hit")}else{die(g);return}}}});
  s.cam=Math.max(s.cam,g.clamp(p.x-W*.4,0,s.L*T-W))},
 draw(g){const s=g.s,p=s.p,cam=Math.floor(s.cam);g.cls(s.sky);
  for(let i=0;i<8;i++){const x=((i*170-cam*.3)%(W+80)+W+80)%(W+80)-40,y=20+(i*37)%50;g.circ(x,y,7,7);g.circ(x+9,y-3,9,7);g.circ(x+19,y,7,7)}
  for(let i=0;i<6;i++){const x=((i*230-cam*.5)%(W+120)+W+120)%(W+120)-60;g.circ(x,12*T+8,28,s.sky==12?3:5);g.circ(x,12*T+8,22,s.sky==12?11:13)}
  const x0=Math.floor(cam/T);for(let y=0;y<ROWS;y++)for(let x=x0;x<=x0+W/T+1;x++){const c=tile(s,x,y),X=x*T-cam,Y=y*T;if(c==" ")continue;
   if(c=="#"){g.rect(X,Y,T,T,4);g.rect(X,Y,T,2,y==12?11:4);if(y==12)g.rect(X,Y+2,T,1,3);g.rect(X+3,Y+6,2,2,2);g.rect(X+10,Y+11,2,2,2)}
   else if(c=="B"){g.rect(X,Y,T,T,9);g.rect(X,Y+7,T,1,4);g.rect(X,Y+15,T,1,4);g.rect(X+7,Y,1,7,4);g.rect(X+3,Y+8,1,7,4);g.rect(X+11,Y+8,1,7,4)}
   else if(c=="?"||c=="M"){g.rect(X,Y,T,T,(g.ticks>>4)%3?10:9);g.box(X,Y,T,T,4);g.text("?",X+8,Y+4,4,2,"c")}
   else if(c=="U"){g.rect(X,Y,T,T,5);g.box(X,Y,T,T,0)}
   else if(c=="="){g.rect(X,Y,T,T,6);g.rect(X,Y,T,1,7);g.rect(X,Y+15,T,1,5);g.rect(X+15,Y,1,T,5)}
   else if(c=="P"||c=="q"){const left=tile(s,x-1,y)!=c;g.rect(X,Y,T,T,3);g.rect(X+(left?3:0),Y,3,T,11);if(c=="q"){g.rect(X-(left?1:0),Y,T+1,6,11);g.rect(X,Y+5,T,1,1)}}
   else if(c=="o"){const w=[6,4,2,4][(g.ticks>>3)%4];g.rect(X+8-w/2,Y+2,w,12,10);g.rect(X+8-w/2,Y+2,1,12,7)}
   else if(c=="|"){g.rect(X+7,Y,2,T,6);if(y==2){g.circ(X+8,Y,3,11);g.spr(["8888888.","88888888","8888888.","7777...."],X-6,Y+3,{map:{}})}}}
  s.items.forEach(it=>g.spr(FRUIT,it.x-cam,it.y));
  s.en.forEach(e=>{if(!e.act)return;if(e.flip){g.spr(BLOB.slice().reverse(),e.x-cam,e.y);return}if(!e.alive){if(e.squash>0)g.spr(BLOB.slice(6),e.x-cam,e.y+6);return}g.spr(BLOB,e.x-cam,e.y,{flip:(g.ticks>>3)%2})});
  s.parts.forEach(q=>q.coin?g.rect(q.x-cam,q.y,6,10,10):g.rect(q.x-cam,q.y,4,4,9));
  if(!(p.inv&&(p.inv>>2)%2)){const fr=p.on&&Math.abs(p.vx)>.3&&(g.ticks>>2)%2?HERO2:HERO;const spr=p.on?fr:HERO2;g.spr(spr.slice(0,12),p.x-cam-1,p.y,{flip:p.face<0,sy:p.big?2.33:1.17})}
  g.rect(0,0,W,11,0);g.text("SCORE "+g.score,3,3,7);g.text("COINS "+s.coins,88,3,10);g.text("WORLD "+(s.lv+1)+"/3",150,3,11);g.text("TIME "+Math.ceil(s.time/60),W-3,3,s.time<3000?8:7,1,"r");
  for(let i=0;i<s.lives;i++)g.rect(4+i*6,14,4,4,12);if(s.clear>60)g.text("LEVEL CLEAR!",W/2,60,10,2,"c")}});
function die(g){const s=g.s;if(s.dead)return;s.dead=100;s.p.vy=-5;g.sfx("die")}
})();
