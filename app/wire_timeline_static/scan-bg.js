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
  var dpr=1,w=0,h=0,cx=0,cy=0,R=0,raf=0,running=false,t0=0,last=0;
  var mer=[],par=[],nodes=[],links=[],packets=[],stars=[],pings=[],glyphs=[],hud=[];
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

  function buildMesh(){
    mer=[];par=[];
    var i,j,nM=mobile?16:24,nP=mobile?10:14,step=mobile?10:8;
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
    var n=mobile?36:56,i,k,a,b,dot,tries;
    // irregular but stable coverage (not a real map)
    for(i=0;i<n;i++){
      var lat=(Math.asin(2*rnd()-1)*180)/Math.PI*0.82;
      var lon=(rnd()*360)-180;
      nodes.push({p:sph(lat,lon),s:0.55+rnd()*0.9,id:hex((seed^0x4B0)<<1&0xffff),hot:0});
    }
    // a few equatorial dense hubs
    for(i=0;i<8;i++){
      nodes.push({p:sph((rnd()-0.5)*18,i*45+(rnd()-0.5)*16),s:1.05+rnd()*0.4,id:hex(0xA000+i),hot:0});
    }
    var maxL=mobile?28:44;
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
    var n=mobile?10:16,i;
    for(i=0;i<n;i++){
      var L=links[(rnd()*links.length)|0];
      if(!L)break;
      packets.push({L:L,t:rnd(),v:0.08+rnd()*0.16,rev:rnd()<0.5,trail:[]});
    }
  }
  function buildStars(){
    stars=[];
    var n=mobile?90:160,i;
    for(i=0;i<n;i++){
      stars.push({x:rnd()*w,y:rnd()*h,a:0.08+rnd()*0.32,s:rnd()<0.08?1.4:0.7+rnd()*0.6,ph:rnd()*Math.PI*2});
    }
  }
  function buildGlyphs(){
    glyphs=[];
    var cols=2,c,r,rows=mobile?9:12;
    for(c=0;c<cols;c++){
      var side=c===0?0:(c===cols-1?1:(rnd()<0.5?0:1));
      var rowsA=[];
      for(r=0;r<rows;r++){
        rowsA.push({k:["RX","TX","AZ","EL","PRF","LO","HI","SYNC","BEAM","PKT","ID"][(rnd()*11)|0],v:hex((rnd()*0xffff)|0)});
      }
      glyphs.push({side:side,xOff:14+c*92,yOff:70+c*28,rows:rowsA,sp:12+rnd()*18,ph:rnd()*200});
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
    cx=w*0.52;cy=h*0.42;R=Math.min(w,h)*0.40;
    if(w<500){cx=w*0.5;cy=h*0.38;R=Math.min(w,h)*0.36}
    seed=0xA5F11C;
    buildMesh();buildNodes();buildPackets();buildStars();buildGlyphs();buildHud();
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
    pings.push({
      p:node.p,t:now,life:1.8+Math.random()*0.8,
      red:!!forceRed,r0:4+node.s*2
    });
    node.hot=1;
  }

  function draw(now){
    var t=(now-t0)/1000;
    var ay=t*0.075, ax=TILT;
    var scan=t*0.55; // radians, longitude of the beam
    var i,j,p,q,a,b,u,z,g,pk,L,tt,col,al;

    ctx.fillStyle="#03050a";
    ctx.fillRect(0,0,w,h);

    // stars
    for(i=0;i<stars.length;i++){
      g=stars[i];
      al=g.a*(RM?1:(0.65+0.35*Math.sin(t*1.2+g.ph)));
      ctx.fillStyle="rgba(210,226,240,"+al.toFixed(3)+")";
      ctx.fillRect(g.x,g.y,g.s,g.s);
    }

    // faint far grid (back hemisphere)
    ctx.strokeStyle="rgba(140,180,210,0.05)";
    ctx.lineWidth=0.6;
    for(i=0;i<mer.length;i++)strokePath(mer[i],ay,ax,0.6,true);
    for(i=0;i<par.length;i++)strokePath(par[i],ay,ax,0.6,true);

    // scan beam slice on the sphere (longitudinal lune)
    var beamW=0.16;
    ctx.save();
    ctx.beginPath();
    var first=true;
    // front arc of the scan plane
    for(i=-90;i<=90;i+=4){
      var slon=(scan*180/Math.PI)%360;
      p=prj(rot(sph(i,slon),ay,ax));
      if(p[2]<0)continue;
      if(first){ctx.moveTo(p[0],p[1]);first=false}else ctx.lineTo(p[0],p[1]);
    }
    ctx.strokeStyle="rgba(170,226,255,0.70)";
    ctx.lineWidth=1.25;
    ctx.stroke();
    // soft wash around the beam
    ctx.beginPath();
    first=true;
    for(i=-88;i<=88;i+=6){
      p=prj(rot(sph(i,(scan*180/Math.PI)),ay,ax));
      if(p[2]<0.05)continue;
      if(first){ctx.moveTo(p[0],p[1]);first=false}else ctx.lineTo(p[0],p[1]);
    }
    ctx.strokeStyle="rgba(120,200,255,0.16)";
    ctx.lineWidth=22;
    ctx.stroke();
    ctx.restore();

    // front grid, brighter near the beam
    for(i=0;i<mer.length;i++){
      var lon=-180+i*(360/mer.length);
      var dlon=Math.abs(((lon*Math.PI/180-scan+Math.PI)%(Math.PI*2)+Math.PI*2)%(Math.PI*2)-Math.PI);
      al=0.14+Math.max(0,1-dlon/0.7)*0.42;
      ctx.strokeStyle="rgba(186,214,235,"+al.toFixed(3)+")";
      strokePath(mer[i],ay,ax,dlon<0.2?1.05:0.7,false);
    }
    ctx.strokeStyle="rgba(186,214,235,0.20)";
    for(i=0;i<par.length;i++)strokePath(par[i],ay,ax,0.7,false);

    // equatorial orbital ring
    ctx.beginPath();
    var rin=1.13,started=false;
    for(i=0;i<=360;i+=4){
      var e=sph(0,i);
      p=prj(rot([e[0]*rin,e[1]*rin,e[2]*rin],ay,ax));
      if(p[2]<0){started=false;continue}
      if(!started){ctx.moveTo(p[0],p[1]);started=true}else ctx.lineTo(p[0],p[1]);
    }
    ctx.strokeStyle="rgba(150,210,240,0.22)";
    ctx.lineWidth=0.8;
    ctx.stroke();

    // limb / atmosphere
    ctx.beginPath();
    ctx.arc(cx,cy,R,0,Math.PI*2);
    ctx.strokeStyle="rgba(170,214,240,0.28)";
    ctx.lineWidth=1.1;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx,cy,R+3.5,0,Math.PI*2);
    ctx.strokeStyle="rgba(90,170,220,0.08)";
    ctx.lineWidth=6;
    ctx.stroke();

    // reticule ticks
    ctx.strokeStyle="rgba(200,220,235,0.18)";
    ctx.lineWidth=1;
    for(i=0;i<hud.length;i++){
      var ang=-Math.PI/2+i*(Math.PI*2/hud.length);
      var inner=R+8,outer=R+8+hud[i]*4;
      ctx.beginPath();
      ctx.moveTo(cx+Math.cos(ang)*inner,cy+Math.sin(ang)*inner);
      ctx.lineTo(cx+Math.cos(ang)*outer,cy+Math.sin(ang)*outer);
      ctx.stroke();
    }

    // links
    for(i=0;i<links.length;i++){
      L=links[i];
      a=prj(rot(L.a.p,ay,ax));b=prj(rot(L.b.p,ay,ax));
      if(a[2]<0&&b[2]<0)continue;
      z=Math.min(a[2],b[2]);
      al=0.05+0.16*limbAlpha(z);
      ctx.beginPath();
      var steps=8,prev=null;
      for(j=0;j<=steps;j++){
        q=prj(rot(slerp(L.a.p,L.b.p,j/steps),ay,ax));
        if(q[2]<0){prev=null;continue}
        if(!prev)ctx.moveTo(q[0],q[1]);else ctx.lineTo(q[0],q[1]);
        prev=q;
      }
      ctx.strokeStyle="rgba(150,210,240,"+al.toFixed(3)+")";
      ctx.lineWidth=0.7;
      ctx.stroke();
    }

    // packets
    for(i=0;i<packets.length;i++){
      pk=packets[i];
      if(!RM){
        pk.t+=((now-last)/1000)*pk.v;
        if(pk.t>1){pk.t-=1;pk.L=links[(Math.random()*links.length)|0]||pk.L;pk.rev=Math.random()<0.5}
      }
      tt=pk.rev?1-pk.t:pk.t;
      u=slerp(pk.L.a.p,pk.L.b.p,tt);
      p=prj(rot(u,ay,ax));
      if(p[2]<0)continue;
      ctx.fillStyle="rgba(210,240,255,"+(0.45+0.5*limbAlpha(p[2])).toFixed(3)+")";
      ctx.beginPath();ctx.arc(p[0],p[1],2.0,0,Math.PI*2);ctx.fill();
      // short trail
      ctx.beginPath();
      var tr=false;
      for(j=1;j<=4;j++){
        var tt2=tt-(pk.rev?-1:1)*j*0.03;
        if(tt2<0||tt2>1)break;
        q=prj(rot(slerp(pk.L.a.p,pk.L.b.p,tt2),ay,ax));
        if(q[2]<0)break;
        if(!tr){ctx.moveTo(p[0],p[1]);tr=true}ctx.lineTo(q[0],q[1]);
      }
      if(tr){ctx.strokeStyle="rgba(140,210,255,0.35)";ctx.lineWidth=1;ctx.stroke()}
    }

    // scan-beam hits + rare flashes
    if(!RM){
      for(i=0;i<nodes.length;i++){
        var nd=nodes[i];
        // node longitude after ignoring tilt, approximate in original lon from p
        var nlon=Math.atan2(nd.p[0],nd.p[2]);
        var dd=Math.abs(((nlon-scan+Math.PI)%(Math.PI*2)+Math.PI*2)%(Math.PI*2)-Math.PI);
        if(dd<0.035&&Math.random()<0.04){
          var front=rot(nd.p,ay,ax)[2]>0.15;
          if(front)maybePing(nd,now,Math.random()<0.18);
        }
        if(nd.hot>0)nd.hot*=0.94;
      }
      // occasional unprompted rare signal
      if(Math.random()<0.006){
        var cand=[];
        for(i=0;i<nodes.length;i++)if(rot(nodes[i].p,ay,ax)[2]>0.35)cand.push(nodes[i]);
        if(cand.length)maybePing(cand[(Math.random()*cand.length)|0],now,Math.random()<0.28);
      }
    }

    // nodes
    for(i=0;i<nodes.length;i++){
      p=prj(rot(nodes[i].p,ay,ax));
      if(p[2]<0)continue;
      al=0.25+0.7*limbAlpha(p[2]);
      var rad=1.15+nodes[i].s*0.85;
      if(nodes[i].hot>0.05){
        ctx.fillStyle="rgba(230,246,255,"+Math.min(1,al+nodes[i].hot).toFixed(3)+")";
        rad+=nodes[i].hot*2;
      }else{
        ctx.fillStyle="rgba(188,224,245,"+al.toFixed(3)+")";
      }
      ctx.beginPath();ctx.arc(p[0],p[1],rad,0,Math.PI*2);ctx.fill();
    }

    // ping rings
    for(i=pings.length-1;i>=0;i--){
      var pg=pings[i];
      var age=(now-pg.t)/1000;
      if(age>pg.life){pings.splice(i,1);continue}
      p=prj(rot(pg.p,ay,ax));
      if(p[2]<0)continue;
      var k=age/pg.life;
      var rr=pg.r0+k*46;
      al=(1-k)*(0.25+0.55*limbAlpha(p[2]));
      ctx.beginPath();ctx.arc(p[0],p[1],rr,0,Math.PI*2);
      ctx.strokeStyle=(pg.red?"rgba(229,72,77,":"rgba(170,220,255,")+al.toFixed(3)+")";
      ctx.lineWidth=1.3-k*0.6;
      ctx.stroke();
      if(k<0.25){
        ctx.beginPath();ctx.arc(p[0],p[1],2.4,0,Math.PI*2);
        ctx.fillStyle=pg.red?"rgba(229,72,77,0.9)":"rgba(230,246,255,0.9)";
        ctx.fill();
      }
    }

    // telemetry glyphs — edges only, very faint
    ctx.font="10px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace";
    ctx.textBaseline="top";
    for(i=0;i<glyphs.length;i++){
      g=glyphs[i];
      var x=g.side?w-g.xOff-86:g.xOff;
      var scroll=(t*g.sp+g.ph)%(g.rows.length*16);
      for(j=0;j<g.rows.length;j++){
        var y=g.yOff+((j*16-scroll+g.rows.length*16)%(g.rows.length*16));
        if(y<40||y>h-80)continue;
        ctx.fillStyle="rgba(170,200,220,0.13)";
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
    else if(!RM){t0=0;start()}
  });
  W.addEventListener("resize",function(){
    resize();
    if(RM){t0=0;draw(0)}
  });

  resize();
  if(RM){
    t0=0;
    var n,count=0;
    // hold a composed mid-scan still with a few rings already open
    for(n=0;n<nodes.length&&count<3;n++){
      if(rot(nodes[n].p,0.6,TILT)[2]>0.4){maybePing(nodes[n],7600,count===1);count++}
    }
    last=8000;
    draw(8000);
  }else start();
})();
