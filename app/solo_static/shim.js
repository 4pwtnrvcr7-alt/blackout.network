// Dashboard helpers the reworked tab add-ons expect (solo.py). Defined only when missing.
(function(w){
  if(typeof w.$!=="function") w.$=function(id){return document.getElementById(id)};
  if(typeof w.esc!=="function") w.esc=function(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})};
  if(typeof w.safeUrl!=="function") w.safeUrl=function(u){return/^https?:\/\//i.test(u||"")?u:"#"};
  if(typeof w.lv!=="function") w.lv=function(s){return s>=60?"h":s>=35?"m":"l"};
  // Politics (and any other tab) "Data range:" line: earliest–latest alert time in America/New_York (dashboard.html's helpers).
  if(typeof w.fmtET!=="function") w.fmtET=function(d,withDate){
    var o={timeZone:"America/New_York",hour:"numeric",minute:"2-digit",timeZoneName:"short"};
    if(withDate){o.month="short";o.day="numeric";o.year="numeric"}
    var p=new Intl.DateTimeFormat("en-US",o).formatToParts(d),g=function(t){for(var i=0;i<p.length;i++)if(p[i].type===t)return p[i].value;return""};
    return (withDate?(g("month")+" "+g("day")+", "+g("year")+" "):"")+g("hour")+":"+g("minute")+" "+g("dayPeriod")+" "+g("timeZoneName");
  };
  if(typeof w.dataRange!=="function") w.dataRange=function(items){
    var lo=Infinity,hi=-Infinity;
    (items||[]).forEach(function(x){["event_time","first_seen","updated"].forEach(function(k){var v=x[k]?Date.parse(x[k]):NaN;if(!isNaN(v)&&v<=Date.now()+6e5){if(v<lo)lo=v;if(v>hi)hi=v}})});
    if(!isFinite(lo)) return "Data range: no items loaded";
    var a=new Date(lo),b=new Date(hi),dk=function(d){return d.toLocaleDateString("en-US",{timeZone:"America/New_York"})};
    return "Data range: "+w.fmtET(a,true)+" – "+(dk(a)===dk(b)?w.fmtET(b,false):w.fmtET(b,true));
  };
})(window);
