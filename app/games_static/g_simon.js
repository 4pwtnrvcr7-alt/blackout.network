// Tone Recall: original memory-sequence game (inspired by the Simon electronic toy).
(()=>{const W=224,H=224,PADS=[{k:"up",c:3,l:11,f:330,x:72,y:24},{k:"right",c:2,l:8,f:440,x:136,y:88},{k:"down",c:1,l:12,f:262,x:72,y:152},{k:"left",c:4,l:10,f:392,x:8,y:88}];
function next(g){const s=g.s;s.seq.push(g.ri(4));s.mode="show";s.i=0;s.timer=40;s.inp=0}
function lit(g,p){g.s.lit=p;g.s.litT=Math.max(10,20-g.s.seq.length);g.tone(PADS[p].f,.25,"square",.06)}
BNG.register({id:"simon",name:"Tone Recall",inspired:"the Simon electronic memory toy",cats:["Puzzle","Classic"],w:W,h:H,
 desc:"Watch the pads light up and play the same tune back. Each round adds one note, and the playback speeds up as the sequence grows.",
 controls:["Arrows / WASD: press the matching pad","Click a pad with the mouse"],
 init(g){const s=g.s;s.seq=[];s.lit=-1;s.litT=0;next(g)},
 press(g,p){const s=g.s;if(s.mode!="input")return;lit(g,p);if(p!==s.seq[s.inp]){s.mode="dead";g.tone(110,.5,"sawtooth",.07);setTimeout(()=>g.over("WRONG PAD! "+(s.seq.length-1)+" ROUNDS"),10);return}
  s.inp++;if(s.inp>=s.seq.length){g.add(s.seq.length*10);s.mode="wait";s.timer=50}},
 key(g,a){const p=PADS.findIndex(q=>q.k==a);if(p>=0)this.press(g,p)},
 click(g,x,y){const p=PADS.findIndex(q=>x>=q.x&&x<q.x+80&&y>=q.y&&y<q.y+48);if(p>=0)this.press(g,p)},
 update(g){const s=g.s;if(s.litT>0&&--s.litT==0)s.lit=-1;
  if(s.mode=="show"){if(--s.timer<=0){if(s.i<s.seq.length){lit(g,s.seq[s.i]);s.i++;s.timer=Math.max(16,34-s.seq.length)}else{s.mode="input";s.inp=0}}}
  else if(s.mode=="wait"){if(--s.timer<=0)next(g)}},
 draw(g){const s=g.s;g.cls(0);g.circ(112,112,104,5);g.circ(112,112,100,0);
  PADS.forEach((p,i)=>{const on=s.lit==i;g.rect(p.x,p.y,80,48,on?p.l:p.c);g.box(p.x,p.y,80,48,on?7:6);g.text(["^",">","V","<"][i],p.x+40,p.y+20,on?0:6,2,"c")});
  g.circ(112,112,22,1);g.text(s.seq.length,112,105,10,2,"c");g.text("ROUND",112,120,6,1,"c");
  g.text(s.mode=="show"?"WATCH...":s.mode=="input"?"YOUR TURN":"",112,212,s.mode=="input"?11:9,1,"c");g.text("SCORE "+g.score,4,4,7)}});
})();
