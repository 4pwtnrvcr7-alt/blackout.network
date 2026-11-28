/* Wire loading screen. Original canvas animation, shown once per page load, then an instant cut to the plain black timeline.
   US-centred globe built from a 1-degree land grid (Natural Earth 110m, public domain; tools/gen_wire_land.py), with a signal
   arc for every located Wire item returned by /api/wire_tl/pulse (the same public rows the timeline shows). Nothing is invented:
   no located signals means no arcs. No libraries, no network assets; cool greys and white only. Reduced motion gets one still frame, then the cut. */
(function(){
  "use strict";
  var W=window,D=document,H=D.documentElement,root=D.getElementById("tl_ld"),cv=D.getElementById("tl_ldc");
  function drop(){H.classList.remove("tl-ld");if(root&&root.parentNode)root.parentNode.removeChild(root)}
  if(!root||!cv||!cv.getContext||!H.classList.contains("tl-ld")){drop();return}
  var ctx=cv.getContext("2d",{alpha:false});
  if(!ctx){drop();return}
  var RM=W.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DUR=2.4,EXIT=0.22,MAXHOLD=4.4,HUBLAT=39,HUBLON=-98,D2R=Math.PI/180;
  var LAND=/*LAND*/{"step":1.0,"rows":[[-55.5,[[-68.5,1]]],[-54.5,[[-71.5,6]]],[-53.5,[[-73.5,6]]],[-52.5,[[-73.5,4]]],[-51.5,[[-74.5,6],[-59.5,2]]],[-50.5,[[-74.5,6]]],[-49.5,[[-75.5,8],[69.5,1]]],[-48.5,[[-75.5,9]]],[-47.5,[[-74.5,9]]],[-46.5,[[-74.5,8],[168.5,2]]],[-45.5,[[-74.5,8],[167.5,4]]],[-44.5,[[-73.5,9],[168.5,3]]],[-43.5,[[-72.5,8],[146.5,1],[170.5,3]]],[-42.5,[[-73.5,11],[145.5,3],[171.5,3]]],[-41.5,[[-73.5,9],[145.5,3],[172.5,2],[175.5,1]]],[-40.5,[[-73.5,12],[175.5,2]]],[-39.5,[[-72.5,11],[174.5,3]]],[-38.5,[[-72.5,14],[143.5,1],[145.5,2],[175.5,3]]],[-37.5,[[-73.5,17],[140.5,10],[175.5,1]]],[-36.5,[[-72.5,16],[140.5,10],[174.5,1]]],[-35.5,[[-72.5,16],[138.5,12],[173.5,1]]],[-34.5,[[-71.5,14],[-56.5,3],[19.5,2],[116.5,3],[135.5,1],[137.5,14]]],[-33.5,[[-71.5,19],[18.5,9],[115.5,9],[135.5,2],[138.5,13]]],[-32.5,[[-70.5,19],[18.5,11],[116.5,10],[134.5,18]]],[-31.5,[[-71.5,21],[18.5,12],[116.5,37]]],[-30.5,[[-71.5,22],[17.5,14],[115.5,38]]],[-29.5,[[-70.5,21],[17.5,14],[115.5,38]]],[-28.5,[[-70.5,22],[16.5,16],[115.5,39]]],[-27.5,[[-70.5,22],[15.5,18],[114.5,39]]],[-26.5,[[-70.5,22],[15.5,18],[113.5,40]]],[-25.5,[[-70.5,23],[15.5,18],[45.5,1],[114.5,39]]],[-24.5,[[-70.5,24],[15.5,20],[44.5,3],[113.5,39]]],[-23.5,[[-69.5,25],[14.5,21],[44.5,4],[114.5,37]]],[-22.5,[[-69.5,28],[14.5,22],[43.5,5],[114.5,36]]],[-21.5,[[-69.5,29],[14.5,21],[43.5,5],[115.5,34],[165.5,1]]],[-20.5,[[-69.5,30],[13.5,22],[44.5,5],[118.5,31],[164.5,1]]],[-19.5,[[-69.5,30],[13.5,22],[44.5,5],[121.5,26]]],[-18.5,[[-69.5,30],[12.5,24],[44.5,5],[122.5,24]]],[-17.5,[[-70.5,32],[12.5,26],[44.5,5],[122.5,18],[141.5,5],[178.5,1]]],[-16.5,[[-72.5,34],[12.5,28],[44.5,6],[124.5,14],[141.5,5],[167.5,1],[179.5,1]]],[-15.5,[[-74.5,36],[12.5,28],[47.5,3],[124.5,12],[142.5,3]]],[-14.5,[[-75.5,37],[12.5,29],[48.5,2],[126.5,2],[129.5,7],[142.5,3]]],[-13.5,[[-75.5,37],[13.5,28],[49.5,1],[130.5,6],[142.5,2]]],[-12.5,[[-76.5,39],[13.5,28],[49.5,1],[131.5,6],[142.5,1]]],[-11.5,[[-76.5,40],[14.5,26],[132.5,1],[142.5,1]]],[-10.5,[[-77.5,42],[13.5,27],[150.5,1]]],[-9.5,[[-78.5,43],[13.5,27],[119.5,1],[124.5,1],[147.5,2],[160.5,2]]],[-8.5,[[-78.5,44],[13.5,26],[114.5,1],[117.5,2],[120.5,1],[122.5,1],[126.5,1],[140.5,3],[146.5,2]]],[-7.5,[[-79.5,45],[13.5,26],[107.5,6],[138.5,9],[158.5,1]]],[-6.5,[[-80.5,46],[12.5,27],[106.5,3],[134.5,1],[138.5,10],[155.5,1]]],[-5.5,[[-80.5,46],[12.5,27],[104.5,2],[122.5,1],[134.5,1],[138.5,8],[148.5,1],[150.5,2]]],[-4.5,[[-80.5,43],[11.5,28],[103.5,3],[122.5,1],[136.5,9]]],[-3.5,[[-79.5,41],[11.5,29],[102.5,4],[114.5,2],[119.5,1],[121.5,1],[126.5,1],[130.5,1],[133.5,10]]],[-2.5,[[-80.5,36],[-43.5,1],[10.5,31],[101.5,5],[110.5,7],[119.5,3],[133.5,1],[136.5,4]]],[-1.5,[[-80.5,36],[9.5,33],[101.5,3],[110.5,7],[119.5,3],[131.5,3]]],[-0.5,[[-79.5,31],[9.5,33],[100.5,4],[109.5,9],[132.5,1]]],[0.5,[[-79.5,30],[9.5,34],[99.5,4],[109.5,9],[120.5,4],[128.5,1]]],[1.5,[[-78.5,29],[9.5,36],[99.5,3],[103.5,1],[109.5,9],[128.5,1]]],[2.5,[[-78.5,28],[10.5,36],[98.5,2],[102.5,2],[111.5,7]]],[3.5,[[-76.5,26],[10.5,37],[97.5,2],[101.5,2],[113.5,4]]],[4.5,[[-76.5,25],[-7.5,1],[6.5,42],[96.5,2],[101.5,2],[114.5,5]]],[5.5,[[-77.5,25],[-9.5,10],[5.5,44],[100.5,3],[116.5,3]]],[6.5,[[-76.5,19],[-10.5,60],[80.5,2],[100.5,2],[116.5,2],[124.5,1]]],[7.5,[[-80.5,1],[-77.5,19],[-12.5,63],[80.5,2],[99.5,1],[122.5,1],[124.5,3]]],[8.5,[[-83.5,4],[-77.5,18],[-12.5,63],[77.5,1],[80.5,1],[98.5,2],[123.5,1],[125.5,1]]],[9.5,[[-83.5,2],[-79.5,1],[-75.5,4],[-70.5,10],[-13.5,65],[76.5,3],[80.5,1],[98.5,1],[105.5,1],[118.5,1],[125.5,1]]],[10.5,[[-85.5,3],[-75.5,4],[-70.5,5],[-63.5,1],[-61.5,1],[-14.5,59],[45.5,6],[76.5,4],[98.5,1],[104.5,3],[119.5,1]]],[11.5,[[-85.5,2],[-72.5,1],[-15.5,59],[49.5,2],[76.5,4],[99.5,1],[103.5,6],[122.5,1],[125.5,1]]],[12.5,[[-86.5,4],[-16.5,60],[75.5,5],[98.5,2],[102.5,7],[124.5,1]]],[13.5,[[-89.5,6],[-16.5,59],[43.5,4],[75.5,5],[98.5,11],[122.5,2]]],[14.5,[[-91.5,9],[-16.5,58],[43.5,6],[74.5,6],[98.5,11],[120.5,2]]],[15.5,[[-92.5,9],[-16.5,57],[43.5,9],[74.5,6],[98.5,11],[120.5,2]]],[16.5,[[-98.5,11],[-16.5,56],[43.5,10],[73.5,9],[94.5,14],[120.5,2]]],[17.5,[[-100.5,13],[-15.5,55],[42.5,13],[73.5,10],[94.5,13],[120.5,2]]],[18.5,[[-103.5,9],[-92.5,5],[-73.5,6],[-66.5,1],[-15.5,54],[41.5,16],[73.5,11],[94.5,12],[109.5,1]]],[19.5,[[-155.5,1],[-104.5,9],[-90.5,4],[-72.5,3],[-15.5,53],[41.5,17],[73.5,12],[94.5,12],[109.5,2]]],[20.5,[[-105.5,9],[-89.5,3],[-76.5,2],[-15.5,53],[40.5,19],[73.5,14],[93.5,14]]],[21.5,[[-104.5,8],[-78.5,2],[-16.5,54],[39.5,20],[70.5,17],[92.5,16],[109.5,2]]],[22.5,[[-105.5,8],[-83.5,1],[-81.5,3],[-15.5,52],[39.5,21],[70.5,21],[92.5,23],[120.5,1]]],[23.5,[[-106.5,9],[-15.5,52],[39.5,20],[68.5,49],[120.5,1]]],[24.5,[[-111.5,1],[-107.5,10],[-14.5,50],[37.5,14],[54.5,3],[67.5,52],[121.5,1]]],[25.5,[[-111.5,1],[-108.5,12],[-80.5,1],[-14.5,50],[37.5,13],[51.5,1],[59.5,60]]],[26.5,[[-112.5,1],[-108.5,12],[-81.5,2],[-78.5,1],[-13.5,48],[36.5,14],[57.5,63]]],[27.5,[[-114.5,3],[-110.5,14],[-82.5,3],[-12.5,46],[36.5,13],[53.5,68]]],[28.5,[[-113.5,1],[-111.5,16],[-82.5,2],[-10.5,45],[35.5,13],[51.5,71]]],[29.5,[[-114.5,1],[-111.5,17],[-90.5,2],[-82.5,2],[-9.5,42],[33.5,15],[50.5,72]]],[30.5,[[-115.5,1],[-112.5,32],[-9.5,29],[20.5,101]]],[31.5,[[-116.5,2],[-113.5,33],[-9.5,26],[20.5,7],[30.5,1],[35.5,87],[130.5,1]]],[32.5,[[-116.5,37],[-8.5,24],[21.5,2],[35.5,86],[130.5,2]]],[33.5,[[-117.5,39],[-7.5,19],[35.5,86],[130.5,4]]],[34.5,[[-119.5,43],[-6.5,17],[36.5,84],[126.5,1],[131.5,3],[135.5,2]]],[35.5,[[-120.5,45],[-5.5,1],[-1.5,13],[36.5,84],[127.5,2],[133.5,8]]],[36.5,[[-121.5,46],[-5.5,1],[1.5,10],[22.5,1],[29.5,2],[32.5,2],[36.5,85],[126.5,3],[136.5,5]]],[37.5,[[-122.5,47],[-8.5,8],[13.5,2],[21.5,2],[27.5,23],[54.5,65],[120.5,2],[126.5,3],[138.5,3]]],[38.5,[[-122.5,48],[-8.5,9],[21.5,3],[27.5,22],[54.5,64],[125.5,3],[140.5,1]]],[39.5,[[-123.5,50],[-8.5,9],[8.5,2],[16.5,1],[20.5,3],[26.5,23],[53.5,66],[122.5,1],[125.5,3],[140.5,2]]],[40.5,[[-123.5,50],[-8.5,10],[8.5,2],[15.5,3],[19.5,5],[26.5,1],[29.5,21],[53.5,68],[122.5,7],[140.5,2]]],[41.5,[[-123.5,53],[-8.5,11],[12.5,4],[19.5,9],[32.5,5],[41.5,8],[54.5,76]]],[42.5,[[-123.5,53],[-8.5,12],[11.5,3],[18.5,10],[42.5,6],[53.5,78],[140.5,4]]],[43.5,[[-123.5,54],[-7.5,3],[-1.5,9],[10.5,4],[16.5,12],[40.5,8],[51.5,84],[141.5,4]]],[44.5,[[-123.5,56],[-65.5,2],[-0.5,13],[15.5,14],[38.5,9],[50.5,86],[142.5,1]]],[45.5,[[-123.5,63],[-0.5,14],[14.5,16],[33.5,2],[37.5,11],[53.5,84]]],[46.5,[[-123.5,59],[-63.5,1],[-60.5,1],[-1.5,33],[32.5,3],[38.5,12],[53.5,85],[142.5,2]]],[47.5,[[-123.5,1],[-121.5,57],[-55.5,1],[-53.5,1],[-2.5,142],[142.5,1]]],[48.5,[[-122.5,54],[-67.5,3],[-58.5,6],[-4.5,145],[142.5,1]]],[49.5,[[-126.5,2],[-123.5,57],[-63.5,2],[-57.5,2],[-54.5,1],[-1.5,142],[142.5,2]]],[50.5,[[-127.5,1],[-125.5,66],[-57.5,2],[-4.5,2],[1.5,140],[142.5,2]]],[51.5,[[-127.5,48],[-78.5,22],[-55.5,1],[-3.5,5],[4.5,137],[142.5,1],[157.5,1]]],[52.5,[[-127.5,46],[-78.5,23],[-8.5,2],[-3.5,6],[4.5,137],[142.5,1],[156.5,2]]],[53.5,[[-132.5,1],[-128.5,47],[-78.5,23],[-8.5,3],[-2.5,3],[7.5,134],[142.5,1],[156.5,4]]],[54.5,[[-164.5,1],[-130.5,49],[-79.5,23],[-8.5,3],[-3.5,3],[9.5,1],[16.5,3],[20.5,117],[156.5,5]]],[55.5,[[-162.5,2],[-131.5,46],[-77.5,18],[-5.5,4],[8.5,2],[11.5,3],[21.5,115],[155.5,7]]],[56.5,[[-159.5,2],[-131.5,44],[-76.5,15],[-5.5,3],[8.5,3],[12.5,4],[21.5,117],[156.5,7]]],[57.5,[[-157.5,2],[-154.5,3],[-133.5,41],[-76.5,15],[-5.5,4],[10.5,1],[12.5,5],[22.5,1],[24.5,116],[157.5,6]]],[58.5,[[-156.5,3],[-137.5,45],[-77.5,10],[-66.5,4],[-4.5,2],[6.5,3],[11.5,6],[24.5,117],[159.5,3]]],[59.5,[[-161.5,8],[-151.5,2],[-139.5,45],[-77.5,9],[-65.5,2],[5.5,13],[25.5,2],[28.5,121],[151.5,4],[160.5,3]]],[60.5,[[-164.5,17],[-145.5,52],[-77.5,8],[-45.5,3],[5.5,13],[22.5,133],[162.5,9]]],[61.5,[[-165.5,72],[-77.5,6],[-48.5,6],[5.5,12],[21.5,136],[159.5,3],[164.5,9]]],[62.5,[[-164.5,73],[-83.5,2],[-77.5,1],[-69.5,3],[-49.5,7],[6.5,12],[21.5,156],[178.5,1]]],[63.5,[[-171.5,2],[-160.5,70],[-85.5,2],[-81.5,1],[-71.5,7],[-50.5,10],[9.5,11],[22.5,157]]],[64.5,[[-173.5,1],[-164.5,1],[-160.5,73],[-85.5,4],[-77.5,3],[-73.5,8],[-51.5,11],[-21.5,7],[11.5,10],[24.5,11],[37.5,141]]],[65.5,[[-178.5,7],[-167.5,81],[-85.5,1],[-73.5,6],[-64.5,2],[-52.5,13],[-22.5,9],[12.5,10],[25.5,10],[40.5,140]]],[66.5,[[-179.5,5],[-173.5,3],[-164.5,1],[-161.5,79],[-73.5,12],[-52.5,18],[13.5,20],[35.5,6],[44.5,28],[73.5,107]]],[67.5,[[-179.5,4],[-163.5,76],[-86.5,6],[-76.5,2],[-72.5,9],[-53.5,21],[14.5,27],[44.5,2],[48.5,25],[75.5,105]]],[68.5,[[-179.5,1],[-166.5,53],[-107.5,3],[-97.5,1],[-93.5,6],[-85.5,5],[-74.5,7],[-51.5,24],[16.5,22],[52.5,2],[57.5,10],[69.5,5],[75.5,105]]],[69.5,[[-162.5,24],[-134.5,15],[-116.5,14],[-99.5,4],[-94.5,4],[-85.5,4],[-76.5,10],[-53.5,2],[-50.5,27],[18.5,15],[60.5,4],[67.5,6],[74.5,94],[170.5,8]]],[70.5,[[-160.5,10],[-113.5,11],[-95.5,4],[-88.5,20],[-54.5,29],[-23.5,1],[24.5,7],[67.5,6],[74.5,86]]],[71.5,[[-179.5,1],[-123.5,4],[-118.5,14],[-99.5,3],[-95.5,3],[-89.5,16],[-72.5,1],[-54.5,33],[52.5,4],[68.5,4],[73.5,2],[76.5,53],[132.5,1],[135.5,2],[138.5,13]]],[72.5,[[-124.5,6],[-117.5,9],[-107.5,3],[-101.5,5],[-95.5,2],[-89.5,9],[-77.5,1],[-54.5,33],[52.5,4],[69.5,4],[81.5,48],[139.5,6]]],[73.5,[[-123.5,8],[-106.5,2],[-100.5,4],[-95.5,5],[-88.5,3],[-83.5,2],[-80.5,3],[-55.5,35],[54.5,3],[81.5,32],[114.5,5],[123.5,4],[140.5,3]]],[74.5,[[-113.5,2],[-89.5,6],[-82.5,1],[-56.5,37],[56.5,3],[86.5,24]]],[75.5,[[-116.5,7],[-108.5,3],[-100.5,3],[-95.5,2],[-92.5,6],[-85.5,5],[-58.5,39],[57.5,6],[90.5,24],[137.5,8]]],[76.5,[[-121.5,4],[-109.5,2],[-100.5,3],[-95.5,5],[-88.5,10],[-69.5,49],[65.5,4],[101.5,11]]],[77.5,[[-118.5,3],[-111.5,1],[-94.5,1],[-87.5,10],[-68.5,50],[14.5,4],[22.5,1],[103.5,2]]],[78.5,[[-112.5,3],[-104.5,5],[-98.5,3],[-92.5,4],[-87.5,13],[-72.5,53],[12.5,7],[100.5,5]]],[79.5,[[-94.5,21],[-65.5,47],[11.5,8],[21.5,4],[93.5,7]]],[80.5,[[-95.5,7],[-82.5,13],[-66.5,51],[19.5,2],[22.5,3],[47.5,4],[92.5,6]]],[81.5,[[-90.5,25],[-61.5,39],[-20.5,9]]],[82.5,[[-85.5,2],[-82.5,21],[-46.5,25]]],[83.5,[[-38.5,12]]]]}/*END*/;
  var w=0,h=0,dpr=1,cx=0,cy=0,R=0,sprite=null,spriteHalf=0,mobile=false;
  var land=null,hd=null,nland=0,sig=[],total=null,gotData=false,dataAt=0,ready=!!W.BN_TL_READY,readyAt=0;
  var lastNow=0,slow=0,seen=0,raf=0,t0=null,hudOn=false,hudT=0,exitAt=-1,finished=false,labelFont="",lbl={};
  var HUB=vec(HUBLAT,HUBLON);
  var elN=D.getElementById("tl_ldn"),elL=D.getElementById("tl_ldl"),elP=D.getElementById("tl_ldp"),elWM=D.getElementById("tl_ldw"),elCT=D.getElementById("tl_ldct"),elR=null;

  function vec(lat,lon){var p=lat*D2R,l=lon*D2R,c=Math.cos(p);return[c*Math.sin(l),Math.sin(p),c*Math.cos(l)]}
  function clamp(v,a,b){return v<a?a:v>b?b:v}
  function eo3(u){u=clamp(u,0,1);return 1-Math.pow(1-u,3)}
  function eo4(u){u=clamp(u,0,1);return 1-Math.pow(1-u,4)}
  function eio(u){u=clamp(u,0,1);return u<.5?4*u*u*u:1-Math.pow(-2*u+2,3)/2}
  function slerp(a,b,t){
    var d=clamp(a[0]*b[0]+a[1]*b[1]+a[2]*b[2],-1,1),th=Math.acos(d);
    if(th<1e-4)return[a[0],a[1],a[2]];
    var s=Math.sin(th),w1=Math.sin((1-t)*th)/s,w2=Math.sin(t*th)/s;
    return[a[0]*w1+b[0]*w2,a[1]*w1+b[1]*w2,a[2]*w1+b[2]*w2];
  }
  function slerpC(a,b,th,sn,t){if(th<1e-4)return a;var w1=Math.sin((1-t)*th)/sn,w2=Math.sin(t*th)/sn;return[a[0]*w1+b[0]*w2,a[1]*w1+b[1]*w2,a[2]*w1+b[2]*w2]}
  function ang(a,b){return Math.acos(clamp(a[0]*b[0]+a[1]*b[1]+a[2]*b[2],-1,1))}

  /* land grid -> unit vectors */
  (function(){
    var rows=LAND.rows,n=0,i,j,k,out;
    /* keep the dot spacing even on the sphere: far from the equator only every k-th meridian cell is kept */
    function stepAt(lat){return Math.max(1,Math.round(1/Math.max(.2,Math.cos(lat*D2R))))}
    for(i=0;i<rows.length;i++){var sp=stepAt(rows[i][0]);for(j=0;j<rows[i][1].length;j++){var r0=rows[i][1][j];for(k=0;k<r0[1];k++)if(Math.round(r0[0]+k+179.5)%sp===0)n++}}
    out=new Float32Array(n*3);n=0;
    for(i=0;i<rows.length;i++){
      var la=rows[i][0]*D2R,cl=Math.cos(la),sl=Math.sin(la),sp2=stepAt(rows[i][0]);
      for(j=0;j<rows[i][1].length;j++){
        var r=rows[i][1][j];
        for(k=0;k<r[1];k++){if(Math.round(r[0]+k+179.5)%sp2!==0)continue;var lo=(r[0]+k)*D2R;out[n*3]=cl*Math.sin(lo);out[n*3+1]=sl;out[n*3+2]=cl*Math.cos(lo);n++}
      }
    }
    land=out;nland=n;
    hd=new Float32Array(n);for(i=0;i<n;i++)hd[i]=Math.acos(clamp(out[i*3]*HUB[0]+out[i*3+1]*HUB[1]+out[i*3+2]*HUB[2],-1,1));
  })();

  /* view: lonV/latV in degrees; project a unit vector to [x,y,z] in css px (z>0 faces the viewer) */
  var vc=1,vs=0,tc=1,ts=0,SC=1;
  function setView(lonV,latV,sc){var a=lonV*D2R,b=latV*D2R;vc=Math.cos(a);vs=Math.sin(a);tc=Math.cos(b);ts=Math.sin(b);SC=sc}
  function prj(v,k){
    var x1=v[0]*vc-v[2]*vs,z1=v[0]*vs+v[2]*vc,y2=v[1]*tc-z1*ts,z2=v[1]*ts+z1*tc;
    k=k||1;
    return[cx+R*SC*k*x1,cy-R*SC*k*y2,z2];
  }

  var dprCap=0;
  function build(){
    var dm=Math.min(W.devicePixelRatio||1,2);if(dprCap)dm=Math.min(dm,dprCap);dpr=dm;
    cv.width=Math.round(w*dpr);cv.height=Math.round(h*dpr);cv.style.width=w+"px";cv.style.height=h+"px";
    mobile=w<=600;
    if(mobile){R=w*0.74;cx=w/2;cy=h*0.43}else{R=Math.max(h*0.58,Math.min(w*0.3,h*0.7));cx=w/2;cy=h*0.5}
    labelFont="600 "+(mobile?9.5:10.5)+"px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace";
    /* the glow sprite: dark sphere, fresnel rim, soft atmosphere. Drawn once, scaled per frame. */
    var rp=R*dpr,half=Math.ceil(rp*1.62);spriteHalf=half;
    var s=D.createElement("canvas");s.width=s.height=half*2;
    var g=s.getContext("2d"),gr;
    gr=g.createRadialGradient(half,half,rp*.96,half,half,rp*1.6);
    gr.addColorStop(0,"rgba(150,182,236,.34)");gr.addColorStop(.14,"rgba(112,150,214,.12)");gr.addColorStop(.45,"rgba(80,110,170,.035)");gr.addColorStop(1,"rgba(0,0,0,0)");
    g.fillStyle=gr;g.fillRect(0,0,half*2,half*2);
    g.save();g.beginPath();g.arc(half,half,rp,0,Math.PI*2);g.clip();
    gr=g.createRadialGradient(half-rp*.34,half-rp*.4,rp*.05,half-rp*.1,half-rp*.12,rp*1.25);
    gr.addColorStop(0,"#1a2230");gr.addColorStop(.55,"#080b11");gr.addColorStop(1,"#010203");
    g.fillStyle=gr;g.fillRect(0,0,half*2,half*2);
    gr=g.createRadialGradient(half,half,rp*.80,half,half,rp);
    gr.addColorStop(0,"rgba(130,170,235,0)");gr.addColorStop(.78,"rgba(130,170,235,.10)");gr.addColorStop(1,"rgba(190,215,255,.42)");
    g.fillStyle=gr;g.fillRect(0,0,half*2,half*2);
    g.restore();
    g.beginPath();g.arc(half,half,rp-.5*dpr,0,Math.PI*2);g.lineWidth=1.1*dpr;g.strokeStyle="rgba(205,222,255,.55)";g.stroke();
    sprite=s;
  }
  function size(){w=root.clientWidth||W.innerWidth;h=root.clientHeight||W.innerHeight;build();if(RM||finished)frame(performance.now())}

  /* data */
  function catLabel(k){
    var c=(W.BN_TL&&W.BN_TL.cats)||[],i;for(i=0;i<c.length;i++)if(c[i].k===k)return c[i].label;
    return String(k||"").replace(/_/g," ");
  }
  function takeData(j,now){
    if(!j||gotData)return;gotData=true;dataAt=now;
    var a=(j.signals||[]).filter(function(s){return typeof s.lat==="number"&&typeof s.lon==="number"}).slice(0,mobile?14:24);
    sig=a.map(function(s){return{v:vec(s.lat,s.lon),k:s.k,r:s.r,p:s.p||"",hot:(s.r||0)>=7,ts:0,ds:0.62,th:0,sn:1}});
    sig.forEach(function(q){q.th=ang(q.v,HUB);q.sn=Math.sin(q.th)||1});
    total=(typeof j.total==="number"&&j.total>0)?j.total:null;
    if(elR&&sig.length)elR.textContent=sig.length+" signals plotted";
  }
  function schedule(tNow){
    var n=sig.length,base=Math.max(.66,tNow+.04),step=n>1?clamp((1.5-base)/(n-1),.028,.085):0,i;
    if(RM){base=0;step=0}
    for(i=0;i<n;i++)sig[i].ts=base+i*step;
  }

  /* one frame at time t (seconds) */
  var COL="186,200,220";
  var AL=[.10,.2,.32,.46,.62,.8];
  var Lx=-.42,Ly=.52,Lz=.74;
  function frame(now){
    var t=RM?1.9:(now-t0)/1000;
    if(gotData&&!sig.scheduled){sig.scheduled=1;schedule(t)}
    var xp=exitAt>=0?clamp((t-exitAt)/EXIT,0,1):0;
    var u=clamp(t/2.15,0,1),e=eo3(u);
    var lonV=HUBLON+78*(1-e)-Math.max(0,t-2.15)*5,latV=12+(HUBLAT-12)*eo3(clamp(t/1.9,0,1));
    var dolly=.9+.1*eo3(clamp(t/2.2,0,1));
    var zoom=dolly*(1+.2*xp*xp);
    setView(lonV,latV,zoom);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.globalAlpha=1;ctx.fillStyle="#000";ctx.fillRect(0,0,w,h);

    var fadeIn=eo3(clamp((t-.04)/.5,0,1));
    /* sphere + atmosphere */
    if(sprite){
      var sh=spriteHalf/dpr*zoom;
      ctx.globalAlpha=fadeIn;ctx.drawImage(sprite,cx-sh,cy-sh,sh*2,sh*2);ctx.globalAlpha=1;
    }
    var Rz=R*zoom;
    /* graticule */
    var ga=.085*eo3(clamp((t-.15)/.7,0,1))*(1-xp);
    if(ga>.002){
      ctx.beginPath();
      var la,lo,pp,vis,i2;
      for(la=-60;la<=60;la+=30){vis=false;for(lo=-180;lo<=180;lo+=6){pp=prj(vec(la,lo));if(pp[2]>0){if(vis)ctx.lineTo(pp[0],pp[1]);else{ctx.moveTo(pp[0],pp[1]);vis=true}}else vis=false}}
      for(lo=-180;lo<180;lo+=30){vis=false;for(la=-84;la<=84;la+=6){pp=prj(vec(la,lo));if(pp[2]>0){if(vis)ctx.lineTo(pp[0],pp[1]);else{ctx.moveTo(pp[0],pp[1]);vis=true}}else vis=false}}
      ctx.lineWidth=1;ctx.strokeStyle="rgba(170,195,235,"+ga.toFixed(3)+")";ctx.stroke();
    }
    /* land dots, revealed outward from the US hub */
    var front=Math.sin(clamp((t-.12)/1.8,0,1)*Math.PI/2)*Math.PI*1.04,band=.15;
    var paths=[],nb=AL.length,b;for(b=0;b<nb+1;b++)paths.push(new Path2D());
    var ds=Math.max(1.1,Rz*.0054),i,x,y,z,x1,z1,y2,z2,q,lit,fd;
    for(i=0;i<nland;i++){
      fd=front-hd[i];if(fd<=0)continue;
      x=land[i*3];y=land[i*3+1];z=land[i*3+2];
      z1=x*vs+z*vc;z2=y*ts+z1*tc;
      if(z2<=.02)continue;
      y2=y*tc-z1*ts;x1=x*vc-z*vs;
      var sx=cx+Rz*x1,sy=cy-Rz*y2;
      var zf=.5+.5*z2;
      if(fd<band){var sz=ds*zf*(1+.35*z2);paths[nb].rect(sx-sz/2,sy-sz/2,sz,sz);continue}
      lit=.3+.7*Math.max(0,x1*Lx+y2*Ly+z2*Lz);
      q=lit*(.3+.7*Math.sqrt(z2))*(fd>=.35?1:fd/.35);
      b=(q*nb)|0;if(b>=nb)b=nb-1;
      var s2=ds*zf;paths[b].rect(sx-s2/2,sy-s2/2,s2,s2);
    }
    var ka=1-xp,ka2=clamp(1-xp*1.6,0,1);
    for(b=0;b<nb;b++){ctx.fillStyle="rgba("+COL+","+(AL[b]*ka).toFixed(3)+")";ctx.fill(paths[b])}
    ctx.fillStyle="rgba(255,255,255,"+(.95*ka).toFixed(3)+")";ctx.fill(paths[nb]);

    /* signal arcs + pulses */
    var n=sig.length,k,s,labels=[];
    var hp=prj(HUB);
    for(k=0;k<n;k++){
      s=sig[k];var lt=t-s.ts;if(lt<0)continue;
      var uh=eio(lt/s.ds),col=s.hot?"229,72,77":"236,242,252";
      var alt=.07+.2*Math.min(1,s.th/1.3);
      var N=uh<1?20:16,j2,prev=null,pt,vv,aa;
      var post=lt>s.ds?clamp(1-(lt-s.ds)/1.4,0,1):1;
      var base=uh>=1?.14+.2*post:1;
      for(j2=0;j2<=N;j2++){
        var uu=uh*j2/N;vv=slerpC(s.v,HUB,s.th,s.sn,uu);var al=1+alt*Math.sin(Math.PI*uu);
        pt=prj(vv,al);
        if(prev&&prev[2]>-.02&&pt[2]>-.02){
          var fr=j2/N;
          aa=uh<1?(.05+.95*Math.pow(fr,1.8)):base*(.35+.65*fr);
          ctx.strokeStyle="rgba("+col+","+(aa*ka).toFixed(3)+")";ctx.lineWidth=(uh<1?(.6+1.2*fr):1)*1;
          ctx.beginPath();ctx.moveTo(prev[0],prev[1]);ctx.lineTo(pt[0],pt[1]);ctx.stroke();
        }
        prev=pt;
      }
      if(uh<1&&prev&&prev[2]>-.02){
        ctx.fillStyle="rgba("+col+","+(.22*ka).toFixed(3)+")";ctx.beginPath();ctx.arc(prev[0],prev[1],5,0,7);ctx.fill();
        ctx.fillStyle="rgba(255,255,255,"+ka.toFixed(3)+")";ctx.beginPath();ctx.arc(prev[0],prev[1],2.1,0,7);ctx.fill();
      }
      /* origin: a ring and a standing dot on the surface */
      var op=prj(s.v);
      if(op[2]>.02){
        var rk=clamp(lt/.9,0,1),rr=3+20*eo3(rk);
        ctx.strokeStyle="rgba("+col+","+((1-rk)*.8*ka).toFixed(3)+")";ctx.lineWidth=1.1;
        ctx.beginPath();ctx.ellipse(op[0],op[1],rr*Math.max(op[2],.25),rr,Math.atan2(op[1]-cy,op[0]-cx),0,Math.PI*2);ctx.stroke();
        ctx.fillStyle="rgba("+col+","+(.95*ka).toFixed(3)+")";ctx.beginPath();ctx.arc(op[0],op[1],s.hot?2.6:2,0,7);ctx.fill();
        if(k<(mobile?3:5)&&lt<1.25&&op[2]>.3&&s.p)labels.push({x:op[0],y:op[1],s:s,a:Math.min(clamp(lt/.25,0,1),clamp((1.25-lt)/.35,0,1))*ka});
      }
      /* hub ring on arrival */
      var at=t-(s.ts+s.ds);
      if(at>=0&&at<.9){
        var hk=at/.9,hr=4+34*eo3(hk);
        ctx.strokeStyle="rgba("+col+","+((1-hk)*.5*ka).toFixed(3)+")";ctx.lineWidth=1;ctx.beginPath();ctx.arc(hp[0],hp[1],hr,0,Math.PI*2);ctx.stroke();
      }
    }
    /* hub */
    var ha=eo3(clamp((t-.5)/.4,0,1))*ka;
    if(ha>.01){
      ctx.fillStyle="rgba(255,255,255,"+(.16*ha).toFixed(3)+")";ctx.beginPath();ctx.arc(hp[0],hp[1],9,0,7);ctx.fill();
      ctx.fillStyle="rgba(255,255,255,"+ha.toFixed(3)+")";ctx.beginPath();ctx.arc(hp[0],hp[1],2.6,0,7);ctx.fill();
    }
    /* labels */
    if(labels.length){
      ctx.font=labelFont;ctx.textBaseline="middle";var placed=[];
      for(k=0;k<labels.length;k++){
        var L=labels[k],txt=(catLabel(L.s.k)+" \u00b7 "+L.s.p).toUpperCase(),tw=ctx.measureText(txt).width;
        var right=L.x<cx,dx=right?-1:1,lx=L.x+dx*16,ly=L.y-16;
        var bx=right?lx-tw-6:lx-2,by=ly-9,bw=tw+8,bh=18;
        if(bx<10||bx+bw>w-10||by<64||by+bh>h-90)continue;
        var hit=false,m;for(m=0;m<placed.length;m++){var o=placed[m];if(bx<o[0]+o[2]&&bx+bw>o[0]&&by<o[1]+o[3]&&by+bh>o[1])hit=true}
        if(hit)continue;placed.push([bx,by,bw,bh]);
        var c=L.s.hot?"255,150,152":"232,238,248";
        ctx.strokeStyle="rgba("+c+","+(.55*L.a).toFixed(3)+")";ctx.lineWidth=1;
        ctx.beginPath();ctx.moveTo(L.x+dx*3,L.y-3);ctx.lineTo(lx,ly);ctx.lineTo(lx+dx*(right?-4:4),ly);ctx.stroke();
        ctx.fillStyle="rgba("+c+","+(.95*L.a).toFixed(3)+")";ctx.textAlign=right?"right":"left";ctx.fillText(txt,lx+dx*8,ly);
      }
    }
    /* the opening: one shock ring from the hub as the screen cuts */
    if(xp>0){
      var sr=eo3(xp)*Math.max(w,h)*.85;
      ctx.strokeStyle="rgba(235,242,255,"+((1-xp)*.7).toFixed(3)+")";ctx.lineWidth=1.4;ctx.beginPath();ctx.arc(hp[0],hp[1],sr,0,Math.PI*2);ctx.stroke();
      ctx.fillStyle="rgba(0,0,0,"+(xp*xp).toFixed(3)+")";ctx.fillRect(0,0,w,h);
    }
    /* HUD */
    if(!hudOn&&(gotData||t>1.0||RM)){
      hudOn=true;
      if(elN){if(total){if(elL)elL.textContent="Signals on the Wire";elN.textContent=RM?total.toLocaleString("en-US"):"0"}else{if(elL)elL.textContent="The Wire \u00b7 Live";elN.textContent="Every signal";elN.className="ld-n wd"}}
      hudT=t;
    }
    if(hudOn&&elN&&total){var cu=RM?1:eo4(clamp((t-.3)/1.55,0,1));elN.textContent=Math.round(total*cu).toLocaleString("en-US")}
    var ho=hudOn?(RM?1:eo3((t-hudT)/.5))*ka2:0;if(elCT)elCT.style.opacity=ho.toFixed(3);if(elR)elR.style.opacity=ho.toFixed(3);
    if(elWM)elWM.style.opacity=((RM?1:eo3((t-.12)/.5))*ka2).toFixed(3);
    if(elP)elP.style.transform="scaleX("+clamp(t/DUR,0,1).toFixed(4)+")";
    return t;
  }

  function finish(){
    if(finished)return;finished=true;if(raf)cancelAnimationFrame(raf);raf=0;
    drop();try{D.dispatchEvent(new Event("bn-tl-loader-done"))}catch(e){}
  }
  function loop(now){
    if(finished)return;
    if(t0===null)t0=now;
    var t=frame(now);
    /* jank guard: if the first frames run slow (no GPU, busy phone) step the pixel density down once or twice instead of dropping frames */
    if(!W.BN_LD_MANUAL){
      if(lastNow&&t>.25&&t<1.4){slow+=(now-lastNow>24)?1:0;seen++;if(seen>=14){if(slow>=7&&dpr>1.01){dprCap=Math.max(1,dpr*.7);build()}slow=0;seen=0}}
      lastNow=now;
    }
    if(exitAt<0&&t>=DUR-EXIT&&(ready||t>=MAXHOLD-EXIT)){exitAt=Math.max(t,DUR-EXIT);try{D.dispatchEvent(new Event("bn-tl-loader-exit"))}catch(e){}}
    if(exitAt>=0&&t>=exitAt+EXIT){finish();return}
    if(!W.BN_LD_MANUAL)raf=requestAnimationFrame(loop);
  }

  D.addEventListener("bn-tl-ready",function(){ready=true;readyAt=performance.now()});
  W.addEventListener("resize",function(){if(!finished)size()});
  elR=D.createElement("span");elR.className="ld-rt";root.appendChild(elR);
  size();
  var fetchP=W.BN_PULSE||fetch("/api/wire_tl/pulse",{credentials:"same-origin"}).then(function(r){return r.ok?r.json():null}).catch(function(){return null});
  fetchP.then(function(j){takeData(j,(t0===null?0:(performance.now()-t0)/1000));
    if(RM){frame(0);}
  });
  if(!W.BN_LD_MANUAL)setTimeout(function(){finish()},9000); /* never trap the page */
  if(RM){
    frame(0);
    var rmEnd=function(){finish()};
    var started=performance.now();
    (function wait(){
      if(finished)return;
      var el=performance.now()-started;
      if((ready&&el>650)||el>2600){finish();return}
      setTimeout(wait,60);
    })();
    fetchP.then(function(){frame(0)});
  }else if(W.BN_LD_MANUAL){
    W.BN_LD_FRAME=function(ms){loop(ms);return finished};  /* test hook: step the clock by hand (used to record the preview videos) */
  }else{
    raf=requestAnimationFrame(loop);
  }
})();
