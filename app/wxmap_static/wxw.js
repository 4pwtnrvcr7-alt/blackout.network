/* Weather map worker (/weather, Nov 22 2026, pt1743u; worldwide satellite + model layers pt1744u). Runs off the main thread so panning never stutters:
   1) radar tiles: decodes NOAA MRMS (IEM) tiles, converts their colours back to reflectivity (dBZ) with the published colour table,
      softens the edges and repaints them in one palette (no yellow), then hands the map an ImageBitmap;
   2) worldwide satellite tiles: geostationary infrared (NASA GIBS colour table, EUMETSAT greyscale) becomes a soft cloud layer, one
      satellite per longitude sector with feathered seams; NASA IMERG rain rates are turned into the same reflectivity palette as the radar;
   3) model fields: temperature / rain / snow from the Open-Meteo grids, and worldwide GFS rain + cloud cover, rendered into Web-Mercator bitmaps. */
"use strict";
var LC = [[11.0,164,164,255],[11.5,161,161,252],[12.0,158,158,249],[12.5,154,154,246],[13.0,151,151,242],[13.5,148,148,239],[14.0,145,145,236],[14.5,142,142,233],[15.0,138,138,230],[15.5,135,135,227],[16.0,132,132,224],[16.5,129,129,220],[17.0,126,126,217],[17.5,122,122,214],[18.0,119,119,211],[18.5,116,116,208],[19.0,113,113,205],[19.5,110,110,201],[20.0,106,106,198],[20.5,103,103,195],[21.0,64,128,255],[21.5,62,125,249],[22.0,61,122,242],[22.5,59,118,236],[23.0,58,115,230],[23.5,56,112,223],[24.0,54,109,217],[24.5,53,106,211],[25.0,51,102,204],[25.5,50,99,198],[26.0,48,96,192],[26.5,46,93,185],[27.0,45,90,179],[27.5,43,86,172],[28.0,42,83,166],[28.5,40,80,160],[29.0,38,77,153],[29.5,37,74,147],[30.0,35,70,141],[30.5,34,67,134],[31.0,32,64,128],[31.5,0,249,0],[32.0,0,242,0],[32.5,0,236,0],[33.0,0,230,0],[33.5,0,223,0],[34.0,0,217,0],[34.5,0,211,0],[35.0,0,204,0],[35.5,0,198,0],[36.0,0,192,0],[36.5,0,185,0],[37.0,0,179,0],[37.5,0,172,0],[38.0,0,166,0],[38.5,0,160,0],[39.0,0,153,0],[39.5,0,147,0],[40.0,0,141,0],[40.5,0,134,0],[41.0,0,128,0],[41.5,255,249,0],[42.0,255,242,0],[42.5,255,236,0],[43.0,255,230,0],[43.5,255,223,0],[44.0,255,217,0],[44.5,255,211,0],[45.0,255,204,0],[45.5,255,198,0],[46.0,255,192,0],[46.5,255,185,0],[47.0,255,179,0],[47.5,255,172,0],[48.0,255,166,0],[48.5,255,160,0],[49.0,255,153,0],[49.5,255,147,0],[50.0,255,141,0],[50.5,255,134,0],[51.0,255,0,0],[51.5,250,0,0],[52.0,245,0,0],[52.5,241,0,0],[53.0,236,0,0],[53.5,231,0,0],[54.0,227,0,0],[54.5,222,0,0],[55.0,217,0,0],[55.5,212,0,0],[56.0,207,0,0],[56.5,203,0,0],[57.0,198,0,0],[57.5,193,0,0],[58.0,189,0,0],[58.5,184,0,0],[59.0,179,0,0],[59.5,174,0,0],[60.0,170,0,0],[60.5,165,0,0],[61.0,255,0,255],[61.5,249,0,249],[62.0,242,0,242],[62.5,236,0,236],[63.0,230,0,230],[63.5,223,0,223],[64.0,217,0,217],[64.5,211,0,211],[65.0,204,0,204],[65.5,198,0,198],[66.0,192,0,192],[66.5,185,0,185],[67.0,179,0,179],[67.5,172,0,172],[68.0,166,0,166],[68.5,160,0,160],[69.0,153,0,153],[69.5,147,0,147],[70.0,141,0,141],[70.5,134,0,134],[71.0,255,255,255],[71.5,249,249,249],[72.0,242,242,242],[72.5,236,236,236],[73.0,230,230,230],[73.5,223,223,223],[74.0,217,217,217],[74.5,211,211,211],[75.0,204,204,204],[75.5,198,198,198],[76.0,192,192,192],[76.5,185,185,185],[77.0,179,179,179],[77.5,172,172,172],[78.0,166,166,166],[78.5,160,160,160],[79.0,153,153,153],[79.5,147,147,147],[80.0,141,141,141],[80.5,134,134,134],[81.0,128,128,128],[81.5,128,128,128],[82.0,128,128,128],[82.5,128,128,128],[83.0,128,128,128],[83.5,128,128,128],[84.0,128,128,128],[84.5,128,128,128],[85.0,128,128,128],[85.5,128,128,128],[86.0,128,128,128],[86.5,128,128,128],[87.0,128,128,128],[87.5,128,128,128],[88.0,128,128,128],[88.5,128,128,128],[89.0,128,128,128],[89.5,128,128,128],[90.0,128,128,128],[90.5,128,128,128],[91.0,128,128,128],[91.5,128,128,128],[92.0,128,128,128],[92.5,128,128,128],[93.0,128,128,128],[93.5,128,128,128],[94.0,128,128,128],[94.5,128,128,128],[95.0,128,128,128]];
var IRT = [[-91.6,255,255,255],[-90.6,127,0,127],[-89.6,140,13,135],[-88.6,153,25,142],[-87.6,165,38,150],[-86.6,178,51,157],[-85.6,191,64,165],[-84.6,204,76,173],[-83.6,217,89,180],[-82.6,229,102,188],[-81.6,242,114,195],[-80.6,255,127,203],[-79.6,230,230,230],[-78.6,204,204,204],[-77.6,177,177,177],[-76.6,155,155,155],[-75.6,129,129,129],[-74.6,102,102,102],[-73.6,76,76,76],[-72.6,54,54,54],[-71.6,27,27,27],[-70.6,5,5,5],[-69.6,26,0,0],[-68.6,51,0,0],[-67.6,77,0,0],[-66.6,102,0,0],[-65.6,128,0,0],[-64.6,153,0,0],[-63.6,179,0,0],[-62.6,204,0,0],[-61.6,230,0,0],[-60.6,255,0,0],[-59.6,255,26,0],[-58.6,255,51,0],[-57.6,255,77,0],[-56.6,255,102,0],[-55.6,255,128,0],[-54.6,255,153,0],[-53.6,255,179,0],[-52.6,255,204,0],[-51.6,255,230,0],[-50.6,255,255,0],[-49.6,230,255,0],[-48.6,204,255,0],[-47.6,179,255,0],[-46.6,153,255,0],[-45.6,128,255,0],[-44.6,102,255,0],[-43.6,77,255,0],[-42.6,51,255,0],[-41.6,26,255,0],[-40.6,0,255,0],[-39.6,0,234,10],[-38.6,0,212,19],[-37.6,0,191,29],[-36.6,0,170,38],[-35.6,0,149,48],[-34.6,0,128,58],[-33.6,0,106,67],[-32.6,0,85,77],[-31.6,0,64,86],[-30.85,0,42,96],[-30.35,0,21,105],[-29.85,0,0,115],[-29.35,0,0,125],[-28.85,0,13,122],[-28.35,0,26,129],[-27.85,0,38,136],[-27.35,0,51,143],[-26.85,0,64,150],[-26.35,0,76,157],[-25.85,0,89,164],[-25.35,0,102,171],[-24.85,0,115,178],[-24.35,0,128,185],[-23.85,0,140,192],[-23.35,0,153,199],[-22.85,0,166,206],[-22.35,0,178,213],[-21.85,0,191,220],[-21.35,0,204,227],[-20.85,0,217,234],[-20.35,0,230,241],[-19.85,0,242,248],[-19.35,0,255,255],[-18.85,197,197,197],[-18.35,196,196,196],[-17.85,194,194,194],[-17.35,193,193,193],[-16.85,192,192,192],[-16.35,191,191,191],[-15.85,189,189,189],[-15.35,188,188,188],[-14.85,187,187,187],[-14.35,185,185,185],[-13.85,184,184,184],[-13.35,183,183,183],[-12.85,181,181,181],[-12.35,180,180,180],[-11.85,179,179,179],[-11.35,178,178,178],[-10.85,176,176,176],[-10.35,175,175,175],[-9.85,174,174,174],[-9.35,172,172,172],[-8.85,171,171,171],[-8.35,170,170,170],[-7.85,169,169,169],[-7.35,167,167,167],[-6.85,166,166,166],[-6.35,165,165,165],[-5.85,163,163,163],[-5.35,162,162,162],[-4.85,161,161,161],[-4.35,159,159,159],[-3.85,158,158,158],[-3.35,157,157,157],[-2.85,156,156,156],[-2.35,154,154,154],[-1.85,153,153,153],[-1.35,152,152,152],[-0.85,150,150,150],[-0.35,149,149,149],[0.15,148,148,148],[0.65,147,147,147],[1.15,145,145,145],[1.65,144,144,144],[2.15,143,143,143],[2.65,141,141,141],[3.15,140,140,140],[3.65,139,139,139],[4.15,138,138,138],[4.65,136,136,136],[5.15,135,135,135],[5.65,134,134,134],[6.15,132,132,132],[6.65,131,131,131],[7.15,130,130,130],[7.65,128,128,128],[8.15,127,127,127],[8.65,126,126,126],[9.15,125,125,125],[9.65,123,123,123],[10.15,122,122,122],[10.65,121,121,121],[11.15,119,119,119],[11.65,118,118,118],[12.15,117,117,117],[12.65,116,116,116],[13.15,114,114,114],[13.65,113,113,113],[14.15,112,112,112],[14.65,110,110,110],[15.15,109,109,109],[15.65,108,108,108],[16.15,106,106,106],[16.65,105,105,105],[17.15,104,104,104],[17.65,103,103,103],[18.15,101,101,101],[18.65,100,100,100],[19.15,99,99,99],[19.65,97,97,97],[20.15,96,96,96],[20.65,95,95,95],[21.15,94,94,94],[21.65,92,92,92],[22.15,91,91,91],[22.65,90,90,90],[23.15,88,88,88],[23.65,87,87,87],[24.15,86,86,86],[24.65,84,84,84],[25.15,83,83,83],[25.65,82,82,82],[26.15,81,81,81],[26.65,79,79,79],[27.15,78,78,78],[27.65,77,77,77],[28.15,75,75,75],[28.65,74,74,74],[29.15,73,73,73],[29.65,72,72,72],[30.15,70,70,70],[30.65,69,69,69],[31.15,68,68,68],[31.65,66,66,66],[32.15,65,65,65],[32.65,64,64,64],[33.15,62,62,62],[33.65,61,61,61],[34.15,60,60,60],[34.65,59,59,59],[35.15,57,57,57],[35.65,56,56,56],[36.15,55,55,55],[36.65,53,53,53],[37.15,52,52,52],[37.65,51,51,51],[38.15,50,50,50],[38.65,48,48,48],[39.15,47,47,47],[39.65,46,46,46],[40.15,44,44,44],[40.65,43,43,43],[41.15,42,42,42],[41.65,41,41,41],[42.15,39,39,39],[42.65,38,38,38],[43.15,37,37,37],[43.65,35,35,35],[44.15,34,34,34],[44.65,33,33,33],[45.15,31,31,31],[45.65,30,30,30],[46.15,29,29,29],[46.65,28,28,28],[47.15,26,26,26],[47.65,25,25,25],[48.15,24,24,24],[48.65,22,22,22],[49.15,21,21,21],[49.65,20,20,20],[50.15,19,19,19],[50.65,17,17,17],[51.15,16,16,16],[51.65,15,15,15],[52.15,13,13,13],[52.65,12,12,12],[53.15,11,11,11],[53.65,9,9,9],[54.15,8,8,8],[54.65,7,7,7],[55.15,6,6,6],[55.65,4,4,4],[56.15,3,3,3],[56.65,2,2,2],[57.15,1,1,1]];
var GPM = [[0.1029,0,118,78],[0.109,0,120,75],[0.1155,0,123,72],[0.1223,0,126,69],[0.1296,0,129,66],[0.1373,0,131,62],[0.1454,0,134,58],[0.154,0,137,54],[0.1631,0,140,50],[0.1728,0,142,46],[0.183,0,145,41],[0.1939,0,148,36],[0.2053,0,151,31],[0.2175,0,153,26],[0.2304,0,156,20],[0.244,0,159,15],[0.2585,0,162,9],[0.2738,0,165,3],[0.29,3,167,0],[0.3072,9,170,0],[0.3255,16,173,0],[0.3448,23,176,0],[0.3651,30,178,0],[0.3868,38,181,0],[0.4097,45,184,0],[0.434,53,187,0],[0.4598,61,189,0],[0.487,69,192,0],[0.5158,78,195,0],[0.5464,86,198,0],[0.5788,95,200,0],[0.6131,104,203,0],[0.6494,114,206,0],[0.6878,123,209,0],[0.7286,133,212,0],[0.7718,143,214,0],[0.8175,153,217,0],[0.866,163,220,0],[0.9173,174,223,0],[0.9716,184,225,0],[1.0292,195,228,0],[1.0902,207,231,0],[1.1548,218,234,0],[1.2232,230,236,0],[1.2957,239,237,0],[1.3724,242,230,0],[1.4537,245,224,0],[1.5399,247,217,0],[1.6312,250,210,0],[1.7278,253,202,0],[1.8302,255,194,1],[1.9386,255,185,4],[2.0535,255,176,6],[2.1752,255,168,9],[2.3041,255,160,12],[2.4406,255,152,15],[2.5852,255,144,17],[2.7384,255,136,20],[2.9007,255,129,23],[3.0726,255,122,26],[3.2547,255,115,28],[3.4475,255,108,31],[3.6517,255,101,34],[3.8681,255,95,37],[4.0974,255,89,39],[4.3401,255,83,42],[4.5972,255,77,45],[4.8697,255,71,48],[5.1582,255,66,51],[5.4638,255,52,44],[5.7876,255,38,38],[6.1306,255,32,32],[6.4938,255,26,26],[6.8786,255,19,19],[7.2862,255,13,13],[7.7179,255,7,7],[8.1753,255,1,1],[8.6597,250,0,0],[9.1728,243,0,0],[9.7163,237,0,0],[10.292,231,0,0],[10.9018,225,0,0],[11.5478,218,0,0],[12.2321,212,0,0],[12.9569,206,0,0],[13.7246,200,0,0],[14.5379,194,0,0],[15.3993,187,0,0],[16.3117,181,0,0],[17.2782,175,0,0],[18.3021,169,0,0],[19.3865,162,0,0],[20.5352,156,0,0],[21.752,150,0,0],[23.0409,144,0,0],[24.4062,138,0,0],[25.8523,131,0,0],[27.3842,125,0,0],[29.0068,119,0,0],[30.7256,113,0,0],[32.5462,106,0,0],[34.4747,100,0,0],[36.5174,94,0,0],[38.6812,88,0,0],[40.9732,82,0,0],[43.4011,75,0,0],[45.9727,69,0,0],[48.6967,63,0,0],[51.5822,57,0,0],[54.6579,51,0,0],[0.1029,177,250,238],[0.109,174,250,239],[0.1155,170,249,239],[0.1223,167,248,240],[0.1296,164,248,241],[0.1373,161,247,242],[0.1454,158,246,243],[0.154,155,245,244],[0.1631,152,244,244],[0.1728,149,241,243],[0.183,146,238,242],[0.1939,143,235,241],[0.2053,140,231,240],[0.2175,137,228,239],[0.2304,134,224,238],[0.244,132,221,237],[0.2585,129,217,236],[0.2738,126,213,234],[0.29,124,209,233],[0.3072,121,205,232],[0.3255,118,201,230],[0.3448,116,197,229],[0.3651,113,193,228],[0.3868,111,189,226],[0.4097,109,184,225],[0.434,106,180,223],[0.4598,104,176,221],[0.487,102,171,220],[0.5158,99,167,218],[0.5464,97,162,216],[0.5788,95,158,215],[0.6131,93,153,213],[0.6494,91,149,211],[0.6878,89,144,209],[0.7286,87,140,207],[0.7718,85,135,205],[0.8175,83,131,203],[0.866,81,126,201],[0.9173,79,122,199],[0.9716,77,117,197],[1.0292,79,115,196],[1.0902,77,112,197],[1.1548,76,109,198],[1.2232,75,106,199],[1.2957,74,102,201],[1.3724,73,99,202],[1.4537,72,95,203],[1.5399,70,92,204],[1.6312,69,88,205],[1.7278,68,84,206],[1.8302,67,80,208],[1.9386,66,76,209],[2.0535,64,72,210],[2.1752,63,68,211],[2.3041,62,64,212],[2.4406,63,61,213],[2.5852,65,60,215],[2.7384,67,59,216],[2.9007,69,57,217],[3.0726,72,56,218],[3.2547,74,55,219],[3.4475,77,54,220],[3.6517,80,53,222],[3.8681,83,52,223],[4.0974,86,50,224],[4.3401,89,49,225],[4.5972,92,48,226],[4.8697,95,47,228],[5.1582,99,46,229],[5.4638,102,45,230],[5.7876,106,43,231],[6.1306,106,37,232],[6.4938,106,31,232],[6.8786,107,25,233],[7.2862,109,20,233],[7.7179,111,18,229],[8.1753,112,16,225],[8.6597,114,15,221],[9.1728,116,13,217],[9.7163,117,12,213],[10.292,119,11,209],[10.9018,120,10,204],[11.5478,121,10,199],[12.2321,122,10,193],[12.9569,122,9,188],[13.7246,123,9,183],[14.5379,123,9,178],[15.3993,123,9,172],[16.3117,122,8,167],[17.2782,122,8,162],[18.3021,121,8,157],[19.3865,120,8,152],[20.5352,119,7,146],[21.752,118,7,141],[23.0409,116,7,136],[24.4062,114,6,131],[25.8523,112,6,125],[27.3842,110,6,120],[29.0068,108,6,115],[30.7256,105,5,110],[32.5462,102,5,105],[34.4747,99,5,99],[36.5174,94,4,93],[38.6812,89,4,86],[40.9732,84,4,79],[43.4011,79,4,72],[45.9727,73,3,66],[48.6967,68,3,60],[51.5822,63,3,54],[54.6579,58,3,48]];
/* ---- reflectivity palette (dBZ -> RGBA). Soft alpha at the light end so echoes read as clouds, not pixels. ---- */
var RP = [[6, 40, 90, 170, 0], [12, 50, 118, 205, .42], [18, 62, 156, 238, .66], [24, 56, 196, 226, .78], [30, 46, 212, 150, .86], [36, 36, 186, 96, .9],
          [41, 255, 154, 61, .93], [47, 255, 106, 42, .95], [52, 255, 59, 59, .96], [58, 214, 38, 120, .97], [63, 224, 64, 251, .98], [70, 246, 236, 255, 1]];
var DLUT = new Uint8ClampedArray(201 * 4);   /* dBZ 0..100 in 0.5 steps */
(function () {
  for (var i = 0; i <= 200; i++) {
    var v = i / 2, c;
    if (v <= RP[0][0]) c = [0, 0, 0, 0];
    else if (v >= RP[RP.length - 1][0]) c = RP[RP.length - 1].slice(1);
    else for (var k = 1; k < RP.length; k++) if (v <= RP[k][0]) { var a = RP[k - 1], b = RP[k], t = (v - a[0]) / (b[0] - a[0]); c = [a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t, a[4] + (b[4] - a[4]) * t]; break; }
    DLUT[i * 4] = c[0]; DLUT[i * 4 + 1] = c[1]; DLUT[i * 4 + 2] = c[2]; DLUT[i * 4 + 3] = Math.round(c[3] * 255);
  }
})();
var MRMS = new Map(); LC.forEach(function (e) { MRMS.set(e[1] << 16 | e[2] << 8 | e[3], e[0]); });
/* infrared: colour -> brightness temperature (deg C). GIBS tiles are resampled, so colours that are not in the table are matched to the
   nearest entry (grey ramp interpolated, coloured cold tops by nearest colour), with a cache. */
var IRM = new Map(), IRC = new Map(), IRG = [];
IRT.forEach(function (e) { IRM.set(e[1] << 16 | e[2] << 8 | e[3], e[0]); if (e[1] === e[2] && e[2] === e[3] && e[0] > -30) IRG.push(e); });
IRG.sort(function (a, b) { return b[1] - a[1]; });
function irT(r, g, b) {
  var key = r << 16 | g << 8 | b, v = IRM.get(key); if (v !== undefined) return v;
  v = IRC.get(key); if (v !== undefined) return v;
  if (Math.abs(r - g) < 6 && Math.abs(g - b) < 6 && r <= IRG[0][1]) {   /* grey: interpolate along the warm grey ramp */
    var gv = (r + g + b) / 3; v = IRG[IRG.length - 1][0];
    for (var i = 1; i < IRG.length; i++) if (gv >= IRG[i][1]) { var A = IRG[i - 1], B = IRG[i], t = (A[1] - gv) / Math.max(1, A[1] - B[1]); v = A[0] + (B[0] - A[0]) * t; break; }
  } else {
    var bd = 1e9; for (var k = 0; k < IRT.length; k++) { var e = IRT[k], d = (e[1] - r) * (e[1] - r) + (e[2] - g) * (e[2] - g) + (e[3] - b) * (e[3] - b); if (d < bd) { bd = d; v = e[0]; } }
  }
  if (IRC.size > 60000) IRC.clear(); IRC.set(key, v); return v;
}
/* cloud look from temperature: clear warm ground is transparent, colder tops get lighter grey and more opaque */
var CL = new Uint8ClampedArray(161 * 4);   /* -100..+60 deg C */
(function () {
  for (var i = 0; i <= 160; i++) {
    var T = i - 100, a = Math.min(1, Math.max(0, (-6 - T) / 52)); a = a * a * (3 - 2 * a);   /* pt1745u: thin or warm cloud (above about -6 C) stays clear, so the map shows through */
    var w = Math.min(1, Math.max(0, (-10 - T) / 50));
    CL[i * 4] = 128 + 52 * w; CL[i * 4 + 1] = 134 + 52 * w; CL[i * 4 + 2] = 146 + 50 * w; CL[i * 4 + 3] = Math.round(a * 255);   /* t1746u: soft grey, full shape here; the page sets the strength (cloud opacity slider) */
  }
})();
function clT(T, o, d, wt) { var i = Math.round(Math.min(160, Math.max(0, T + 100))) * 4; d[o] = CL[i]; d[o + 1] = CL[i + 1]; d[o + 2] = CL[i + 2]; d[o + 3] = CL[i + 3] * wt; }
/* IMERG: colour -> rain rate (mm/h) -> reflectivity with the Marshall-Palmer relation Z = 200 R^1.6 */
var GPMM = new Map(), GPMC = new Map();
GPM.forEach(function (e) { GPMM.set(e[1] << 16 | e[2] << 8 | e[3], e[0]); });
function gpmR(r, g, b) {
  var key = r << 16 | g << 8 | b, v = GPMM.get(key); if (v !== undefined) return v;
  v = GPMC.get(key); if (v !== undefined) return v;
  var bd = 1e9; v = 0; for (var k = 0; k < GPM.length; k++) { var e = GPM[k], d = (e[1] - r) * (e[1] - r) + (e[2] - g) * (e[2] - g) + (e[3] - b) * (e[3] - b); if (d < bd) { bd = d; v = e[0]; } }
  if (bd > 900) v = 0; GPMC.set(key, v); return v;
}
function rDbz(R) { return R > 0 ? 10 * Math.log(200 * Math.pow(R, 1.6)) / Math.LN10 : 0; }
/* one satellite per longitude sector; neighbouring sectors overlap by 2 x FE degrees and cross-fade */
var SEC = { gw: [-180, -106], ge: [-106, -37.5], ms: [-37.5, 30], io: [30, 90], hi: [90, 180] }, FE = 2.5;
function secW(k, lon) {
  var s = SEC[k]; if (!s) return 1;
  var a = s[0] === -180 ? -1e9 : s[0] - FE, b = s[1] === 180 ? 1e9 : s[1] + FE;
  if (lon < a || lon > b) return 0;
  return Math.min(1, (lon - a) / (2 * FE), (b - lon) / (2 * FE));
}
/* NOAA MRMS domain: worldwide rain (IMERG, GFS) is hidden inside it so the two never double up */
var DOM = { w: -130, e: -60, s: 20, n: 55 };
function tileLon(x, z) { return x / Math.pow(2, z) * 360 - 180; }
function tileLat(y, z) { var n = Math.PI - 2 * Math.PI * y / Math.pow(2, z); return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n))); }
var CV = null, CX = null;
function blank1() { var c = new OffscreenCanvas(1, 1); c.getContext("2d"); return c.transferToImageBitmap(); }
function canvas(w, h) {
  if (!CV) { CV = new OffscreenCanvas(w, h); CX = CV.getContext("2d", { willReadFrequently: true }); }
  if (CV.width !== w || CV.height !== h) { CV.width = w; CV.height = h; }
  return CX;
}
function domMask(z, x, y, W, H, feather) {
  /* 0..1 per pixel: how much of the worldwide layer to hide (1 = inside the NOAA radar domain). null when the tile is clear of it. */
  var lw = tileLon(x, z), le = tileLon(x + 1, z), ln = tileLat(y, z), ls = tileLat(y + 1, z), F = feather || 0;
  if (le < DOM.w - F || lw > DOM.e + F || ln < DOM.s - F || ls > DOM.n + F) return null;
  var m = new Float32Array(W * H), cols = new Float32Array(W);
  for (var px = 0; px < W; px++) { var lo = tileLon(x + (px + 0.5) / W, z); cols[px] = F ? Math.min(1, Math.max(0, Math.min(lo - DOM.w, DOM.e - lo) / F + 0.5)) : (lo >= DOM.w && lo <= DOM.e ? 1 : 0); }
  for (var py = 0; py < H; py++) { var la = tileLat(y + (py + 0.5) / H, z), r = F ? Math.min(1, Math.max(0, Math.min(la - DOM.s, DOM.n - la) / F + 0.5)) : (la >= DOM.s && la <= DOM.n ? 1 : 0);
    if (r) for (var q = 0; q < W; q++) m[py * W + q] = r * cols[q]; }
  return m;
}
/* WebKit (Safari, every iOS browser) uploads an ImageBitmap to WebGL without premultiplying it, so MapLibre's premultiplied blending turned
   every semi-transparent pixel into solid white (Nov 22 2026, pt1747u: the white blocks and stripe on iPhone). The page tests for that
   once and tells the workers; then the pixels are premultiplied here, which is what the GPU gets on every browser. */
var PMFIX = false;
function put(cx, im) {
  if (PMFIX) { var d = im.data; for (var i = 0; i < d.length; i += 4) { var a = d[i + 3]; if (a === 255) continue; if (a === 0) { d[i] = d[i + 1] = d[i + 2] = 0; continue; } d[i] = d[i] * a / 255; d[i + 1] = d[i + 1] * a / 255; d[i + 2] = d[i + 2] * a / 255; } }
  cx.putImageData(im, 0, 0);
}
function done(cx) { var b; if (CV.transferToImageBitmap) { b = CV.transferToImageBitmap(); CV = null; return b; } return createImageBitmap(CV); }
function radarTile(kind, buf, z, x, y, sec) {
  return createImageBitmap(new Blob([buf], { type: "image/png" })).then(function (bmp) {
    var W = bmp.width, H = bmp.height;
    if (kind === "h" && !PMFIX) return bmp;   /* HRRR forecast tiles keep their own rain / snow / mix colours */
    if (kind === "h") { var hc = canvas(W, H); hc.clearRect(0, 0, W, H); hc.drawImage(bmp, 0, 0); bmp.close(); put(hc, hc.getImageData(0, 0, W, H)); return done(hc); }
    if (kind === "i") {   /* fully inside the NOAA domain: the U.S. radar covers it */
      var lw = tileLon(x, z), le = tileLon(x + 1, z), ln = tileLat(y, z), ls = tileLat(y + 1, z);
      if (lw >= DOM.w && le <= DOM.e && ls >= DOM.s && ln <= DOM.n) { bmp.close(); return blank1(); }
    }
    var cx = canvas(W, H); cx.clearRect(0, 0, W, H); cx.drawImage(bmp, 0, 0); bmp.close();
    var im = cx.getImageData(0, 0, W, H), d = im.data, N = W * H, i, o;
    if (kind === "s" || kind === "e") {   /* infrared -> clouds */
      var cw = new Float32Array(W), anyc = false;
      for (var px = 0; px < W; px++) { cw[px] = secW(sec, tileLon(x + (px + 0.5) / W, z)); if (cw[px] > 0) anyc = true; }
      if (!anyc) return blank1();
      var rw = new Float32Array(H);   /* geostationary views are unusable near the poles: fade out from 62 to 74 degrees */
      for (var ry = 0; ry < H; ry++) { var rl = Math.abs(tileLat(y + (ry + 0.5) / H, z)); rw[ry] = Math.min(1, Math.max(0, (74 - rl) / 12)); }
      var TT = new Float32Array(N);
      for (i = 0; i < N; i++) {
        o = i * 4;
        TT[i] = d[o + 3] < 8 ? 99 : kind === "s" ? irT(d[o], d[o + 1], d[o + 2]) : 25 - 0.3 * d[o];   /* EUMETView ir108 greyscale: about +25 C (black) to -50 C (white) */
      }
      /* 3x3 median: removes the single-pixel speckle the resampled tiles carry, keeps cloud edges */
      var nb = new Float32Array(9);
      for (var yy0 = 0; yy0 < H; yy0++) for (var xx0 = 0; xx0 < W; xx0++) {
        i = yy0 * W + xx0; o = i * 4; var wt = cw[xx0] * rw[yy0];
        if (!wt || TT[i] === 99) { d[o + 3] = 0; continue; }
        var c = 0;
        for (var dy0 = -1; dy0 <= 1; dy0++) { var y3 = yy0 + dy0; if (y3 < 0) y3 = 0; else if (y3 >= H) y3 = H - 1;
          for (var dx0 = -1; dx0 <= 1; dx0++) { var x3 = xx0 + dx0; if (x3 < 0) x3 = 0; else if (x3 >= W) x3 = W - 1; var tv = TT[y3 * W + x3]; nb[c++] = tv === 99 ? TT[i] : tv; } }
        for (var a1 = 1; a1 < 9; a1++) { var key = nb[a1], b1 = a1 - 1; while (b1 >= 0 && nb[b1] > key) { nb[b1 + 1] = nb[b1]; b1--; } nb[b1 + 1] = key; }
        clT(nb[4], o, d, wt);
      }
      put(cx, im); return done(cx);
    }
    var mask = kind === "i" ? domMask(z, x, y, W, H, 0) : null, D = new Float32Array(N), any = false;
    for (i = 0; i < N; i++) {
      o = i * 4; var a = d[o + 3], v = 0;
      if (a > 0 && !(mask && mask[i] > 0.5)) {
        if (kind === "m") { var k = MRMS.get(d[o] << 16 | d[o + 1] << 8 | d[o + 2]); v = k === undefined ? 0 : k; }
        else v = rDbz(gpmR(d[o], d[o + 1], d[o + 2]));
        if (v > 0) any = true;
      }
      D[i] = v;
    }
    if (!any) return blank1();
    /* soften: 3x3 Gaussian on reflectivity (edges clamp), so scans read as smooth cloud shapes at every zoom */
    var S = new Float32Array(N);
    for (var yy = 0; yy < H; yy++) for (var xx = 0; xx < W; xx++) {
      var s = 0, wsum = 0;
      for (var dy = -1; dy <= 1; dy++) { var y2 = yy + dy; if (y2 < 0 || y2 >= H) continue;
        for (var dx = -1; dx <= 1; dx++) { var x2 = xx + dx; if (x2 < 0 || x2 >= W) continue; var w = (dx ? 1 : 2) * (dy ? 1 : 2); s += D[y2 * W + x2] * w; wsum += w; } }
      S[yy * W + xx] = s / wsum;
    }
    for (var j = 0; j < N; j++) {
      var q = j * 4, val = Math.max(S[j], D[j] * 0.85), li = Math.min(200, Math.round(val * 2)) * 4;
      d[q] = DLUT[li]; d[q + 1] = DLUT[li + 1]; d[q + 2] = DLUT[li + 2]; d[q + 3] = DLUT[li + 3];
    }
    put(cx, im);
    return done(cx);
  });
}

/* ---- worldwide GFS forecast: rain rate (1 degree, log-coded 1..255) and cloud cover (2 degrees, 0..255) ---- */
var GFS = null;   /* {run, n, p: {nx, ny, lat0, lon0, step, data: Uint8Array}, c: {...}, lo, hi} */
function gfsLoad(m) {
  function dec(buf, meta) {
    return createImageBitmap(new Blob([buf], { type: "image/png" })).then(function (bmp) {
      var c = new OffscreenCanvas(bmp.width, bmp.height), x = c.getContext("2d", { willReadFrequently: true });
      x.drawImage(bmp, 0, 0); var px = x.getImageData(0, 0, bmp.width, bmp.height).data, out = new Uint8Array(bmp.width * bmp.height);
      for (var i = 0; i < out.length; i++) out[i] = px[i * 4];
      bmp.close(); return { nx: meta.nx, ny: meta.ny, lat0: meta.lat0, lon0: meta.lon0, step: meta.step, data: out };
    });
  }
  return Promise.all([dec(m.p, m.meta.p), dec(m.c, m.meta.c)]).then(function (r) {
    /* rain: one soft 3x3 pass in log space ("no rain" counts as -24), stored offset by 24, so showers read as rounded cells, not grid squares */
    var p = r[0], nx = p.nx, ny = p.ny, nt = m.meta.times.length, src = p.data, out = new Uint8Array(src.length), F = new Float32Array(nx * ny);
    for (var k = 0; k < nt; k++) {
      var off = k * nx * ny;
      for (var i = 0; i < nx * ny; i++) { var v = src[off + i]; F[i] = v ? v : -24; }
      for (var j = 0; j < ny; j++) for (var x = 0; x < nx; x++) {
        var s = 0, w = 0;
        for (var dj = -1; dj <= 1; dj++) { var jj = j + dj; if (jj < 0 || jj >= ny) continue;
          for (var di = -1; di <= 1; di++) { var ii = (x + di + nx) % nx, kk = (di ? 1 : 2) * (dj ? 1 : 2); s += F[jj * nx + ii] * kk; w += kk; } }
        out[off + j * nx + x] = Math.max(0, Math.min(255, Math.round(s / w + 24)));
      }
    }
    p.data = out; p.off = 24;
    /* cloud cover: the same soft pass (hides the 2-degree steps) */
    var c = r[1], cnx = c.nx, cny = c.ny, cs = c.data, co = new Uint8Array(cs.length);
    for (k = 0; k < nt; k++) {
      var coff = k * cnx * cny;
      for (var j2 = 0; j2 < cny; j2++) for (var x2 = 0; x2 < cnx; x2++) {
        var s2 = 0, w2 = 0;
        for (var dj2 = -1; dj2 <= 1; dj2++) { var jj2 = j2 + dj2; if (jj2 < 0 || jj2 >= cny) continue;
          for (var di2 = -1; di2 <= 1; di2++) { var ii2 = (x2 + di2 + cnx) % cnx, k2 = (di2 ? 1 : 2) * (dj2 ? 1 : 2); s2 += cs[coff + jj2 * cnx + ii2] * k2; w2 += k2; } }
        co[coff + j2 * cnx + x2] = Math.round(s2 / w2);
      }
    }
    c.data = co;
    GFS = { run: m.meta.run, n: nt, p: p, c: r[1], lo: m.meta.rate.lo, hi: m.meta.rate.hi };
  });
}
function gAt2(g, k, i, j) { if (j < 0) j = 0; else if (j >= g.ny) j = g.ny - 1; i = ((i % g.nx) + g.nx) % g.nx; return g.data[(k * g.ny + j) * g.nx + i]; }
function gfsTile(m) {   /* one 256 px Web-Mercator tile of GFS rain (kind "p", masked inside the NOAA domain when "pm") or cloud cover ("c") */
  if (!GFS || GFS.run !== m.run) return null;
  var isP = m.kind.charAt(0) === "p", mask = m.kind === "pm", g = isP ? GFS.p : GFS.c, k = m.k, z = m.z, x = m.x, y = m.y, W = 256, H = 256;
  if (k < 0 || k >= GFS.n) return null;
  if (mask) { var lw = tileLon(x, z), le = tileLon(x + 1, z), ln = tileLat(y, z), ls = tileLat(y + 1, z); if (lw >= DOM.w + 2 && le <= DOM.e - 2 && ls >= DOM.s + 2 && ln <= DOM.n - 2) return blank1(); }
  var cx = canvas(W, H), im = cx.createImageData(W, H), D = im.data, L = Math.log(GFS.hi / GFS.lo), any = false, ZERO = -24, base = k * g.ny;
  var nx = g.nx, ny = g.ny, data = g.data;
  /* code -> float once per tile (only the rows this tile touches), then bicubic with precomputed column indices */
  var lons = new Float32Array(W), hx = new Float32Array(W), cI = new Int32Array(W * 4), cF = new Float32Array(W);
  for (var px = 0; px < W; px++) {
    lons[px] = tileLon(x + (px + 0.5) / W, z); hx[px] = mask ? Math.min(1, Math.max(0, Math.min(lons[px] - DOM.w, DOM.e - lons[px]) / 2 + 0.5)) : 0;
    var gx = (lons[px] - g.lon0) / g.step, x1 = Math.floor(gx); cF[px] = gx - x1;
    for (var q = 0; q < 4; q++) cI[px * 4 + q] = (((x1 - 1 + q) % nx) + nx) % nx;
  }
  var rowCache = {};
  function row(j) {
    if (j < 0) j = 0; else if (j >= ny) j = ny - 1;
    var r = rowCache[j]; if (r) return r;
    r = new Float32Array(nx); var off = (base + j) * nx;
    for (var i = 0; i < nx; i++) r[i] = isP ? data[off + i] - 24 : data[off + i];
    rowCache[j] = r; return r;
  }
  for (var py = 0; py < H; py++) {
    var lat = tileLat(y + (py + 0.5) / H, z), gy = (g.lat0 - lat) / g.step, y1 = Math.floor(gy), fy = gy - y1;
    var hy = mask ? Math.min(1, Math.max(0, Math.min(lat - DOM.s, DOM.n - lat) / 2 + 0.5)) : 0;
    var R0 = row(y1 - 1), R1 = row(y1), R2 = row(y1 + 1), R3 = row(y1 + 2);
    for (px = 0; px < W; px++) {
      var k4 = px * 4, i0 = cI[k4], i1 = cI[k4 + 1], i2 = cI[k4 + 2], i3 = cI[k4 + 3], fx = cF[px], o = (py * W + px) * 4;
      var v = cr(cr(R0[i0], R0[i1], R0[i2], R0[i3], fx), cr(R1[i0], R1[i1], R1[i2], R1[i3], fx), cr(R2[i0], R2[i1], R2[i2], R2[i3], fx), cr(R3[i0], R3[i1], R3[i2], R3[i3], fx), fy);
      if (isP) {
        if (v < 1) continue;
        var R = GFS.lo * Math.exp((v - 1) / 254 * L), li = Math.min(200, Math.max(0, Math.round(rDbz(R) * 2))) * 4, hide = hy * hx[px];
        var al = DLUT[li + 3] * (1 - hide); if (!al) continue;
        D[o] = DLUT[li]; D[o + 1] = DLUT[li + 1]; D[o + 2] = DLUT[li + 2]; D[o + 3] = al; any = true;
      } else {
        var c = Math.min(1, Math.max(0, (v / 255 - 0.55) / 0.45)); c = c * c * (3 - 2 * c);   /* model total cloud: a lighter veil than the satellite view */
        if (c <= 0.01) continue;
        var w = Math.min(1, Math.max(0, (v / 255 - 0.6) / 0.4));
        D[o] = 128 + 48 * w; D[o + 1] = 134 + 48 * w; D[o + 2] = 146 + 46 * w; D[o + 3] = Math.round(c * 0.62 * 255); any = true;
      }
    }
  }
  if (!any) return blank1();
  put(cx, im);
  var b = CV.transferToImageBitmap(); CV = null; return b;
}

/* ---- model grids ---- */
var GR = {};   /* key -> {nx, ny, lat0, lon0, step, wrap, nt, N, temp, precip, snow} (Float32, NaN = no data) */
function my(lat) { return Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)); }
function iy(y) { return (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI; }
function field(g, mode, k) {
  var N = g.N, out = new Float32Array(N), j, q, b = k * N;
  if (mode === "temp") for (j = 0; j < N; j++) out[j] = g.temp[b + j];
  else if (mode === "rain") for (j = 0; j < N; j++) { var p = g.precip[b + j]; out[j] = p !== p ? NaN : p / 254; }
  else for (j = 0; j < N; j++) { var s = 0, ok = false; for (q = Math.max(0, k - 7); q <= k; q++) { var v = g.snow[q * N + j]; if (v === v) { s += v; ok = true; } } out[j] = ok ? s / 25.4 : NaN; }
  return mode === "temp" ? out : blurF(g, out);
}
function blurF(g, F) {   /* NaN-aware 3x3 [1 2 1] pass: rain and snow cells read as soft weather shapes, not grid squares */
  var nx = g.nx, ny = g.ny, out = new Float32Array(F.length);
  for (var j = 0; j < ny; j++) for (var i = 0; i < nx; i++) {
    var c = F[j * nx + i]; if (c !== c) { out[j * nx + i] = NaN; continue; }
    var s = 0, w = 0;
    for (var dj = -1; dj <= 1; dj++) { var jj = j + dj; if (jj < 0 || jj >= ny) continue;
      for (var di = -1; di <= 1; di++) { var ii = i + di; if (g.wrap) ii = (ii + nx) % nx; else if (ii < 0 || ii >= nx) continue;
        var v = F[jj * nx + ii]; if (v !== v) continue; var k = (di ? 1 : 2) * (dj ? 1 : 2); s += v * k; w += k; } }
    out[j * nx + i] = s / w;
  }
  return out;
}
function cr(p0, p1, p2, p3, t) { return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0))); }
function at(g, F, i, j) { if (j < 0) j = 0; else if (j >= g.ny) j = g.ny - 1; if (g.wrap) i = ((i % g.nx) + g.nx) % g.nx; else if (i < 0) i = 0; else if (i >= g.nx) i = g.nx - 1; return F[j * g.nx + i]; }
function bilin(g, F, gx, gy) {
  var x0 = Math.floor(gx), y0 = Math.floor(gy), fx = gx - x0, fy = gy - y0, a = at(g, F, x0, y0), b = at(g, F, x0 + 1, y0), c = at(g, F, x0, y0 + 1), d = at(g, F, x0 + 1, y0 + 1);
  if (a === a && b === b && c === c && d === d) return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
  var s = 0, w = 0;
  if (a === a) { var wa = (1 - fx) * (1 - fy) + 1e-3; s += a * wa; w += wa; } if (b === b) { var wb = fx * (1 - fy) + 1e-3; s += b * wb; w += wb; }
  if (c === c) { var wc = (1 - fx) * fy + 1e-3; s += c * wc; w += wc; } if (d === d) { var wd = fx * fy + 1e-3; s += d * wd; w += wd; }
  return w ? s / w : NaN;
}
function smooth(g, F, gx, gy) {
  if (gy < 0 || gy > g.ny - 1 || (!g.wrap && (gx < 0 || gx > g.nx - 1))) return NaN;
  var x1 = Math.floor(gx), y1 = Math.floor(gy), fx = gx - x1, fy = gy - y1, rows = [0, 0, 0, 0];
  for (var j = -1; j <= 2; j++) {
    var r0 = at(g, F, x1 - 1, y1 + j), r1 = at(g, F, x1, y1 + j), r2 = at(g, F, x1 + 1, y1 + j), r3 = at(g, F, x1 + 2, y1 + j);
    if (r0 !== r0 || r1 !== r1 || r2 !== r2 || r3 !== r3) return bilin(g, F, gx, gy);
    rows[j + 1] = cr(r0, r1, r2, r3, fx);
  }
  return cr(rows[0], rows[1], rows[2], rows[3], fy);
}
function ramp(p, v) {
  if (v <= p[0][0]) return p[0].slice(1);
  for (var i = 1; i < p.length; i++) if (v <= p[i][0]) { var a = p[i - 1], b = p[i], t = (v - a[0]) / (b[0] - a[0]); return [a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t, a[4] + (b[4] - a[4]) * t]; }
  return p[p.length - 1].slice(1);
}
function fieldImage(m) {
  var g = GR[m.g]; if (!g) return null;
  var F = field(g, m.mode, m.k), P = m.pal, lo = P[0][0], hi = P[P.length - 1][0], NL = 512, lut = new Array(NL + 1);
  for (var u = 0; u <= NL; u++) lut[u] = ramp(P, lo + (hi - lo) * u / NL);
  var W = m.w, H = m.h, cx = canvas(W, H), im = cx.createImageData(W, H), D = im.data;
  var yT = my(m.n), yB = my(m.s), lonW = m.lw, lonE = m.le;
  for (var py = 0; py < H; py++) {
    var lat = iy(yT - (py + 0.5) / H * (yT - yB)), gy = (lat - g.lat0) / g.step;
    var ey = Math.min(gy, g.ny - 1 - gy);
    for (var px = 0; px < W; px++) {
      var lon = lonW + (px + 0.5) / W * (lonE - lonW), gx = (lon - g.lon0) / g.step, v = smooth(g, F, gx, gy), o = (py * W + px) * 4;
      if (v !== v) { D[o + 3] = 0; continue; }
      var soft = 1;
      if (m.mode !== "temp") { if (v < lo * 0.25) { D[o + 3] = 0; continue; } if (v < lo) { soft = (v - lo * 0.25) / (lo * 0.75); soft *= soft; } }
      var c = lut[Math.round(Math.min(1, Math.max(0, (v - lo) / (hi - lo))) * NL)];
      var e = g.wrap ? ey : Math.min(gx, g.nx - 1 - gx, ey), fade = Math.min(1, Math.max(0, e / (m.fade || 2.2))); fade = fade * fade * (3 - 2 * fade) * soft;
      D[o] = c[0]; D[o + 1] = c[1]; D[o + 2] = c[2]; D[o + 3] = Math.round(c[3] * 255 * fade);
    }
  }
  put(cx, im);
  var b = CV.transferToImageBitmap(); CV = null; return b;
}

self.onmessage = function (e) {
  var m = e.data;
  if (m.op === "tile") {
    radarTile(m.kind, m.buf, m.z, m.x, m.y, m.sec).then(function (bmp) { self.postMessage({ id: m.id, bmp: bmp }, [bmp]); }, function (err) { self.postMessage({ id: m.id, err: String(err && err.message || err) }); });
  } else if (m.op === "gfs") {
    gfsLoad(m).then(function () { self.postMessage({ id: m.id, ok: 1 }); }, function (err) { self.postMessage({ id: m.id, err: String(err && err.message || err) }); });
  } else if (m.op === "gfstile") {
    try { var g = gfsTile(m); self.postMessage({ id: m.id, bmp: g }, g ? [g] : []); } catch (err) { self.postMessage({ id: m.id, err: String(err && err.message || err) }); }
  } else if (m.op === "cfg") {
    PMFIX = !!m.pm; self.postMessage({ id: m.id, ok: 1 });
  } else if (m.op === "grid") {
    GR[m.key] = m.grid; self.postMessage({ id: m.id, ok: 1 });
  } else if (m.op === "field") {
    try { var b = fieldImage(m); self.postMessage({ id: m.id, bmp: b }, b ? [b] : []); } catch (err) { self.postMessage({ id: m.id, err: String(err && err.message || err) }); }
  }
};
