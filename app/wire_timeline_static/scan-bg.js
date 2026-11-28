/* Wire scan background. Original canvas animation for /wire.
   Dark SpaceX-style network globe: streams, a scan beam, telemetry glyphs,
   and rare-signal flashes. No libraries, no stock footage. */
(function(){
  "use strict";
  var cv=document.querySelector(".tl-scanbg");
  if(!cv||!cv.getContext)return;
  var ctx=cv.getContext("2d",{alpha:false});
  if(!ctx)return;
  var W=window, RM=W.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  var dpr=1,w=0,h=0,cx=0,cy=0,R=0,raf=0,running=false,t0=0,last=0,debut=true;
  var mer=[],par=[],nodes=[],links=[],packets=[],streams=[],stars=[],pings=[],glyphs=[],hud=[];
  var TILT=0.42, seed=0xA5F11C, mobile=false;

  function rnd(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}
  function sph(lat,lon){
    var ph=lat*Math.PI/180,th=lon*Math.PI/180,cl=Math.cos(ph);
    return[cl*Math.sin(th),Math.sin(ph),cl*Math.cos(th)];
  }
  function rot(p,ay,ax){
    var c=Math.cos(ay),s=Math.sin(ay),x=p[0]*c+p[2]*s,z=-p[0]*s+p[2]*c;
    c=Math.cos(ax);s=Math.sin(ax);
    return[x,p[1]*c-z*s,p[1]*s+z*c];
  }
  function prj(p){return[cx+p[0]*R,cy-p[1]*R,p[2]]}
  function slerp(a,b,t){
    var d=a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
    d=d<-1?-1:d>1?1:d;
    var th=Math.acos(d);
    if(th<1e-4)return[a[0],a[1],a[2]];
    var s=Math.sin(th),w1=Math.sin((1-t)*th)/s,w2=Math.sin(t*th)/s;
    return[a[0]*w1+b[0]*w2,a[1]*w1+b[1]*w2,a[2]*w1+b[2]*w2];
  }
  function hex(n){return("000"+n.toString(16).toUpperCase()).slice(-4)}
  function merPt(mi,t){
    var pts=mer[mi];
    if(!pts||pts.length<2)return pts[0];
    var u=t*(pts.length-1),i=Math.min(pts.length-2,u|0),f=u-i;
    var a=pts[i],b=pts[i+1];
    return[a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,a[2]+(b[2]-a[2])*f];
  }

  function buildMesh(){
    mer=[];par=[];
    var i,j,nM=mobile?16:24,step=mobile?10:8;
    for(i=0;i<nM;i++){
      var lon=-180+i*(360/nM),pts=[];
      for(j=-90;j<=90;j+=step)pts.push(sph(j,lon));
      mer.push(pts);
    }
    for(j=-75;j<=75;j+=15){
      pts=[];
      for(i=-180;i<=180;i+=step)pts.push(sph(j,i));
      par.push(pts);
    }
  }
  function buildNodes(){
    nodes=[];links=[];
    var n=mobile?40:60,i,k,a,b,dot,tries;
    for(i=0;i<n;i++){
      var lat=(Math.asin(2*rnd()-1)*180)/Math.PI*0.82;
      var lon=(rnd()*360)-180;
      nodes.push({p:sph(lat,lon),s:0.55+rnd()*0.9,id:hex((seed^0x4B0)<<1&0xffff),hot:0});
    }
    for(i=0;i<8;i++){
      nodes.push({p:sph((rnd()-0.5)*18,i*45+(rnd()-0.5)*16),s:1.05+rnd()*0.4,id:hex(0xA000+i),hot:0});
    }
    var maxL=mobile?36:52;
    for(k=0;k<maxL;k++){
      tries=0;
      do{
        a=nodes[(rnd()*nodes.length)|0];
        b=nodes[(rnd()*nodes.length)|0];
        dot=a.p[0]*b.p[0]+a.p[1]*b.p[1]+a.p[2]*b.p[2];
        tries++;
      }while((a===b||dot<0.12||dot>0.92)&&tries<12);
      if(a!==b&&dot>=0.12&&dot<=0.92)links.push({a:a,b:b,dot:dot});
    }
  }
  function buildPackets(){
    packets=[];
    var n=mobile?24:36,i;
    for(i=0;i<n;i++){
      var L=links[(rnd()*links.length)|0];
      if(!L)break;
      packets.push({L:L,t:rnd(),v:0.10+rnd()*0.20,rev:rnd()<0.5});
    }
  }
  function buildStreams(){
    streams=[];
    var n=mobile?16:22,i;
    for(i=0;i<n;i++){
      streams.push({mer:(rnd()*mer.length)|0,t:rnd(),v:0.10+rnd()*0.20,rev:rnd()<0.5});
    }
  }
  function buildStars(){
    stars=[];
    var n=mobile?110:180,i;
    for(i=0;i<n;i++){
      stars.push({x:rnd()*w,y:rnd()*h,a:0.14+rnd()*0.40,s:rnd()<0.08?1.5:0.7+rnd()*0.7,ph:rnd()*Math.PI*2});
    }
  }
  function buildGlyphs(){
    glyphs=[];
    var cols=2,c,r,rows=mobile?10:12;
    for(c=0;c<cols;c++){
      var side=c===0?0:1;
      var rowsA=[];
      for(r=0;r<rows;r++){
        rowsA.push({k:["RX","TX","AZ","EL","PRF","LO","HI","SYNC","BEAM","PKT","ID"][(rnd()*11)|0],v:hex((rnd()*0xffff)|0)});
      }
      glyphs.push({side:side,xOff:14+c*8,yOff:64+c*18,rows:rowsA,sp:14+rnd()*16,ph:rnd()*200});
    }
  }
  function buildHud(){
    hud=[];
    var i;
    for(i=0;i<72;i++)hud.push((i%6===0)?2:1);
  }

  function resize(){
    var r=cv.getBoundingClientRect();
    w=Math.max(1,r.width||W.innerWidth||320);
    h=Math.max(1,r.height||W.innerHeight||480);
    dpr=Math.min(2,W.devicePixelRatio||1);
    mobile=w<=700;
    var bw=Math.round(w*dpr),bh=Math.round(h*dpr);
    if(cv.width!==bw||cv.height!==bh){cv.width=bw;cv.height=bh}
    ctx.setTransform(dpr,0,0,dpr,0,0);
    cx=w*0.52;cy=h*0.42;R=Math.min(w,h)*0.42;
    if(w<500){cx=w*0.5;cy=h*0.36;R=Math.min(w,h)*0.42}
    seed=0xA5F11C;
    buildMesh();buildNodes();buildPackets();buildStreams();buildStars();buildGlyphs();buildHud();
  }

  function strokePath(pts,ay,ax,width,back){
    var i,p,vis,lastIn=false;
    ctx.lineWidth=width;
    ctx.beginPath();
    for(i=0;i<pts.length;i++){
      p=prj(rot(pts[i],ay,ax));
      vis=back?(p[2]<=0.02):(p[2]>-0.02);
      if(vis){
        if(!lastIn)ctx.moveTo(p[0],p[1]);
        else ctx.lineTo(p[0],p[1]);
        lastIn=true;
      }else lastIn=false;
    }
    ctx.stroke();
  }

  function limbAlpha(z){
    var a=(z+0.08)/1.08;
    if(a<0)return 0;
    if(a>1)return 1;
    return a*a;
  }

  function maybePing(node,now,forceRed){
    if(pings.length>=3)return;
    var rare=!!forceRed;
    pings.push({
      p:node.p,t:now,life:2.2+Math.random()*0.5,
      red:rare,r0:6+node.s*2,
      label:rare?"SIGNAL ACQUIRED \u00B7 RARE":"SIGNAL ACQUIRED"
    });
    node.hot=1;
    node.armed=false;
  }

  function beamPath(slon,step,zMin){
    var i,p,first=true;
    ctx.beginPath();
    for(i=-90;i<=90;i+=step){
      p=prj(rot(sph(i,slon),ayFor,axFor));
      if(p[2]<zMin)continue;
      if(first){ctx.moveTo(p[0],p[1]);first=false}else ctx.lineTo(p[0],p[1]);
    }
  }
  var ayFor=0,axFor=0;

  function draw(now){
    var t=(now-t0)/1000;
    var ay=t*0.075, ax=TILT;
    ayFor=ay;axFor=ax;
    var scan=t*0.62;
    var slon=((scan*180/Math.PI)%360+360)%360;
    var i,j,p,q,a,b,u,z,g,pk,L,tt,al,st,dt;

    ctx.fillStyle="#03050a";
    ctx.fillRect(0,0,w,h);

    for(i=0;i<stars.length;i++){
      g=stars[i];
      al=g.a*(RM?1:(0.7+0.3*Math.sin(t*1.2+g.ph)));
      ctx.fillStyle="rgba(210,226,240,"+al.toFixed(3)+")";
      ctx.fillRect(g.x,g.y,g.s,g.s);
    }

    ctx.strokeStyle="rgba(140,180,210,0.12)";
    for(i=0;i<mer.length;i++)strokePath(mer[i],ay,ax,0.7,true);
    for(i=0;i<par.length;i++)strokePath(par[i],ay,ax,0.7,true);

    // scan beam: layered cyan glow + bright core
    ctx.save();
    ctx.lineJoin="round";ctx.lineCap="round";
    beamPath(slon,6,-0.02);
    ctx.strokeStyle="rgba(70,190,255,0.12)";ctx.lineWidth=48;ctx.stroke();
    beamPath(slon,5,-0.02);
    ctx.strokeStyle="rgba(110,214,255,0.22)";ctx.lineWidth=26;ctx.stroke();
    beamPath(slon,4,-0.05);
    ctx.strokeStyle="rgba(160,230,255,0.55)";ctx.lineWidth=9;ctx.stroke();
    beamPath(slon,3,-0.08);
    ctx.strokeStyle="rgba(220,245,255,0.96)";ctx.lineWidth=2.1;ctx.stroke();
    ctx.restore();

    // front grid ~2x brighter, lifted near the beam
    for(i=0;i<mer.length;i++){
      var lon=-180+i*(360/mer.length);
      var dlon=Math.abs(((lon*Math.PI/180-scan+Math.PI)%(Math.PI*2)+Math.PI*2)%(Math.PI*2)-Math.PI);
      al=0.28+Math.max(0,1-dlon/0.7)*0.55;
      ctx.strokeStyle="rgba(198,226,245,"+al.toFixed(3)+")";
      strokePath(mer[i],ay,ax,dlon<0.2?1.35:0.9,false);
    }
    ctx.strokeStyle="rgba(198,226,245,0.42)";
    for(i=0;i<par.length;i++)strokePath(par[i],ay,ax,0.9,false);

    ctx.beginPath();
    var rin=1.13,started=false;
    for(i=0;i<=360;i+=4){
      var e=sph(0,i);
      p=prj(rot([e[0]*rin,e[1]*rin,e[2]*rin],ay,ax));
      if(p[2]<0){started=false;continue}
      if(!started){ctx.moveTo(p[0],p[1]);started=true}else ctx.lineTo(p[0],p[1]);
    }
    ctx.strokeStyle="rgba(160,220,250,0.48)";
    ctx.lineWidth=1.0;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(cx,cy,R,0,Math.PI*2);
    ctx.strokeStyle="rgba(190,228,250,0.58)";
    ctx.lineWidth=1.35;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx,cy,R+4.5,0,Math.PI*2);
    ctx.strokeStyle="rgba(90,190,230,0.18)";
    ctx.lineWidth=10;
    ctx.stroke();

    ctx.strokeStyle="rgba(210,230,245,0.34)";
    ctx.lineWidth=1;
    for(i=0;i<hud.length;i++){
      var ang=-Math.PI/2+i*(Math.PI*2/hud.length);
      var inner=R+8,outer=R+8+hud[i]*4;
      ctx.beginPath();
      ctx.moveTo(cx+Math.cos(ang)*inner,cy+Math.sin(ang)*inner);
      ctx.lineTo(cx+Math.cos(ang)*outer,cy+Math.sin(ang)*outer);
      ctx.stroke();
    }

    for(i=0;i<links.length;i++){
      L=links[i];
      a=prj(rot(L.a.p,ay,ax));b=prj(rot(L.b.p,ay,ax));
      if(a[2]<0&&b[2]<0)continue;
      z=Math.min(a[2],b[2]);
      al=0.12+0.32*limbAlpha(z);
      ctx.beginPath();
      var steps=8,prev=null;
      for(j=0;j<=steps;j++){
        q=prj(rot(slerp(L.a.p,L.b.p,j/steps),ay,ax));
        if(q[2]<0){prev=null;continue}
        if(!prev)ctx.moveTo(q[0],q[1]);else ctx.lineTo(q[0],q[1]);
        prev=q;
      }
      ctx.strokeStyle="rgba(160,220,250,"+al.toFixed(3)+")";
      ctx.lineWidth=0.85;
      ctx.stroke();
    }

    dt=(last&&!RM)?Math.min(0.05,(now-last)/1000):0;

    // meridian data streams
    for(i=0;i<streams.length;i++){
      st=streams[i];
      if(dt){st.t+=dt*st.v;if(st.t>1){st.t-=1;st.mer=(Math.random()*mer.length)|0;st.rev=Math.random()<0.5}}
      tt=st.rev?1-st.t:st.t;
      p=prj(rot(merPt(st.mer,tt),ay,ax));
      if(p[2]<0)continue;
      ctx.fillStyle="rgba(200,240,255,"+(0.55+0.4*limbAlpha(p[2])).toFixed(3)+")";
      ctx.beginPath();ctx.arc(p[0],p[1],1.7,0,Math.PI*2);ctx.fill();
      ctx.beginPath();
      var tr=false;
      for(j=1;j<=7;j++){
        var tt2=tt-(st.rev?-1:1)*j*0.02;
        if(tt2<0||tt2>1)break;
        q=prj(rot(merPt(st.mer,tt2),ay,ax));
        if(q[2]<0)break;
        if(!tr){ctx.moveTo(p[0],p[1]);tr=true}ctx.lineTo(q[0],q[1]);
      }
      if(tr){ctx.strokeStyle="rgba(130,215,255,0.45)";ctx.lineWidth=1.2;ctx.stroke()}
    }

    // packets on network links
    for(i=0;i<packets.length;i++){
      pk=packets[i];
      if(dt){
        pk.t+=dt*pk.v;
        if(pk.t>1){pk.t-=1;pk.L=links[(Math.random()*links.length)|0]||pk.L;pk.rev=Math.random()<0.5}
      }
      tt=pk.rev?1-pk.t:pk.t;
      u=slerp(pk.L.a.p,pk.L.b.p,tt);
      p=prj(rot(u,ay,ax));
      if(p[2]<0)continue;
      ctx.fillStyle="rgba(220,245,255,"+(0.65+0.35*limbAlpha(p[2])).toFixed(3)+")";
      ctx.beginPath();ctx.arc(p[0],p[1],2.15,0,Math.PI*2);ctx.fill();
      ctx.beginPath();
      tr=false;
      for(j=1;j<=8;j++){
        var tt3=tt-(pk.rev?-1:1)*j*0.025;
        if(tt3<0||tt3>1)break;
        q=prj(rot(slerp(pk.L.a.p,pk.L.b.p,tt3),ay,ax));
        if(q[2]<0)break;
        if(!tr){ctx.moveTo(p[0],p[1]);tr=true}ctx.lineTo(q[0],q[1]);
      }
      if(tr){ctx.strokeStyle="rgba(150,225,255,0.5)";ctx.lineWidth=1.35;ctx.stroke()}
    }

    if(!RM){
      if(debut&&t>0.7){
        var seeded=[];
        for(i=0;i<nodes.length;i++)if(rot(nodes[i].p,ay,ax)[2]>0.45)seeded.push(nodes[i]);
        if(seeded.length)maybePing(seeded[(Math.random()*seeded.length)|0],now,true);
        debut=false;
      }
      for(i=0;i<nodes.length;i++){
        var nd=nodes[i];
        var nlon=Math.atan2(nd.p[0],nd.p[2]);
        var dd=Math.abs(((nlon-scan+Math.PI)%(Math.PI*2)+Math.PI*2)%(Math.PI*2)-Math.PI);
        if(dd>0.10)nd.armed=true;
        if(dd<0.04&&nd.armed!==false){
          nd.armed=false;
          if(rot(nd.p,ay,ax)[2]>0.18&&Math.random()<0.40)maybePing(nd,now,Math.random()<0.40);
        }
        if(nd.hot>0)nd.hot*=0.93;
      }
      if(Math.random()<0.004){
        var cand=[];
        for(i=0;i<nodes.length;i++)if(rot(nodes[i].p,ay,ax)[2]>0.35)cand.push(nodes[i]);
        if(cand.length)maybePing(cand[(Math.random()*cand.length)|0],now,Math.random()<0.5);
      }
    }

    for(i=0;i<nodes.length;i++){
      p=prj(rot(nodes[i].p,ay,ax));
      if(p[2]<0)continue;
      al=0.45+0.55*limbAlpha(p[2]);
      var rad=1.3+nodes[i].s*0.95;
      if(nodes[i].hot>0.05){
        ctx.fillStyle="rgba(235,248,255,"+Math.min(1,al+nodes[i].hot).toFixed(3)+")";
        rad+=nodes[i].hot*2.4;
      }else{
        ctx.fillStyle="rgba(210,236,250,"+al.toFixed(3)+")";
      }
      ctx.beginPath();ctx.arc(p[0],p[1],rad,0,Math.PI*2);ctx.fill();
    }

    ctx.textAlign="left";
    ctx.textBaseline="bottom";
    ctx.font="9px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace";
    for(i=pings.length-1;i>=0;i--){
      var pg=pings[i];
      var age=(now-pg.t)/1000;
      if(age>pg.life){pings.splice(i,1);continue}
      p=prj(rot(pg.p,ay,ax));
      if(p[2]<0)continue;
      var k=age/pg.life;
      var rr=pg.r0+k*58;
      al=(1-k)*(0.45+0.55*limbAlpha(p[2]));
      // second, fainter ring
      ctx.beginPath();ctx.arc(p[0],p[1],rr*0.62,0,Math.PI*2);
      ctx.strokeStyle=(pg.red?"rgba(229,72,77,":"rgba(180,230,255,")+(al*0.7).toFixed(3)+")";
      ctx.lineWidth=1.1;
      ctx.stroke();
      ctx.beginPath();ctx.arc(p[0],p[1],rr,0,Math.PI*2);
      ctx.strokeStyle=(pg.red?"rgba(229,72,77,":"rgba(180,230,255,")+al.toFixed(3)+")";
      ctx.lineWidth=1.8-k*0.7;
      ctx.stroke();
      if(k<0.35){
        ctx.beginPath();ctx.arc(p[0],p[1],3.1,0,Math.PI*2);
        ctx.fillStyle=pg.red?"rgba(229,72,77,0.95)":"rgba(235,248,255,0.95)";
        ctx.fill();
      }
      if(pg.label&&k<0.72){
        var la=(1-k/0.72)*0.95;
        var lx=p[0]+10, ly=p[1]-10;
        if(lx+154>w){lx=p[0]-10;ctx.textAlign="right"}
        else ctx.textAlign="left";
        ctx.fillStyle=pg.red?"rgba(255,214,214,"+la.toFixed(3)+")":"rgba(210,238,255,"+la.toFixed(3)+")";
        ctx.fillText(pg.label,lx,ly);
        ctx.textAlign="left";
      }
    }

    // telemetry: legible but faint, edges only, kept off the headline block
    ctx.font="10px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace";
    ctx.textBaseline="top";
    ctx.textAlign="left";
    for(i=0;i<glyphs.length;i++){
      g=glyphs[i];
      var x=g.side?w-g.xOff-96:g.xOff;
      var scroll=(t*g.sp+g.ph)%(g.rows.length*16);
      for(j=0;j<g.rows.length;j++){
        var y=g.yOff+((j*16-scroll+g.rows.length*16)%(g.rows.length*16));
        if(y<48||y>h*0.58)continue;
        ctx.fillStyle="rgba(190,220,235,0.36)";
        ctx.fillText(g.rows[j].k+" "+g.rows[j].v,x,y);
      }
    }

    last=now;
  }

  function loop(ts){
    if(document.hidden){running=false;raf=0;return}
    if(!t0)t0=ts;
    draw(ts);
    if(!RM){running=true;raf=requestAnimationFrame(loop)}
  }

  function start(){
    if(running||RM)return;
    running=true;
    raf=requestAnimationFrame(loop);
  }
  function stop(){
    running=false;
    if(raf){cancelAnimationFrame(raf);raf=0}
  }

  document.addEventListener("visibilitychange",function(){
    if(document.hidden)stop();
    else if(!RM){t0=0;debut=true;start()}
  });
  W.addEventListener("resize",function(){
    resize();
    if(RM){t0=0;draw(0)}
  });

  resize();
  if(RM){
    t0=0;debut=false;
    var n,count=0;
    for(n=0;n<nodes.length&&count<3;n++){
      if(rot(nodes[n].p,0.6,TILT)[2]>0.4){maybePing(nodes[n],7600,count===0);count++}
    }
    last=8000;
    draw(8000);
  }else start();
})();
