/* Network status board (/network, Nov 23 2026, pt1758u). The main view: "Is it down?" search with a plain-English verdict,
   live tiles by group with a 24 h strip, chain reactions, one-tap "Down for me" reports, a US report map that appears only
   during an incident, and the incident timeline. Data: /api/netmap/data (shared with net.js) + /api/netmap/board. */
(function () {
  "use strict";
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function url(u) { return /^https?:\/\//i.test(u || "") || /^\/[a-z]/.test(u || "") ? esc(u) : ""; }
  var root = $("nb"); if (!root) return;
  var D = null, B = null, OPEN = null, MAPD = null;
  var GB = [{ id: "internet", name: "Internet and ISPs", g: ["isp", "sat"] }, { id: "mobile", name: "Mobile", g: ["mobile"] }, { id: "cloud", name: "Cloud", g: ["cloud"] },
            { id: "money", name: "Payments and banking", g: ["pay", "rails"] }, { id: "apps", name: "Apps and messaging", g: ["apps"] }, { id: "gov", name: "Government and public", g: ["gov"] }];
  var ALIAS = { gmail: "workspace", google: "workspace", meet: "workspace", "google meet": "workspace", "google drive": "workspace", drive: "workspace", outlook: "m365", teams: "m365", office: "m365",
    "office 365": "m365", microsoft: "m365", hotmail: "m365", chatgpt: "openai", "chat gpt": "openai", sora: "openai", comcast: "xfinity", centurylink: "lumen", "spectrum internet": "spectrum",
    "time warner": "spectrum", charter: "spectrum", "at&t": "att", att: "att", verizon: "verizonwireless", fios: "verizonfios", tmobile: "tmobile", "t mobile": "tmobile", "amazon web services": "aws",
    amazon: "aws", "google cloud": "gcp", "microsoft azure": "azure", fednow: "fedres", fedwire: "fedres", ach: "increase", "social security": "ssa", irs: "logingov", "cash app": "cashapp",
    venmo: "~Venmo", snapchat: "~Snapchat", snap: "~Snapchat", spotify: "~Spotify", x: "~X", twitter: "~X", slack: "~Slack", roblox: "~Roblox", fortnite: "~Fortnite", alexa: "~Alexa", signal: "~Signal",
    robinhood: "~Robinhood", canva: "~Canva", uber: "~Uber", claude: "~Claude", xbox: "~Xbox", minecraft: "~Minecraft", "prime video": "~Prime Video", etsy: "~Etsy", duolingo: "~Duolingo" };
  var LV = function (l) { return l >= 3 ? "out" : l === 2 ? "deg" : l === 1 ? "minor" : l === 0 ? "ok" : "na"; };
  var WORD = function (l) { return l >= 3 ? "Major outage" : l === 2 ? "Disruption" : l === 1 ? "Minor issue" : l === 0 ? "Normal" : "No live feed"; };
  function short(n) { return String(n || "").replace(/\s*\((.*)\)\s*$/, ""); }
  function sub(n) { var m = /\((.*)\)\s*$/.exec(n || ""); return m ? m[1] : ""; }
  var TZ = (function () { try { return new Intl.DateTimeFormat("en-US", { timeZoneName: "short" }).formatToParts(new Date()).filter(function (p) { return p.type === "timeZoneName"; })[0].value; } catch (e) { return ""; } })();
  function tm(ts) { var d = new Date(ts); return isFinite(d) ? d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : ""; }
  function dayLbl(ts) {
    var d = new Date(ts), t = new Date(); if (!isFinite(d)) return "";
    var k = Math.round((new Date(t.toDateString()) - new Date(d.toDateString())) / 864e5);
    return k === 0 ? "Today" : k === 1 ? "Yesterday" : d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  }
  function when(ts) { var d = new Date(ts); if (!isFinite(d)) return ""; var dl = dayLbl(ts); return (dl === "Today" ? "" : dl + ", ") + tm(ts) + (TZ ? " " + TZ : ""); }
  function dur(m) { m = Math.max(1, Math.round(m)); return m < 60 ? m + " min" : m < 1440 ? Math.floor(m / 60) + " h" + (m % 60 ? " " + (m % 60) + " min" : "") : Math.round(m / 1440) + " d"; }
  function ago(ts) { var m = (Date.now() - Date.parse(ts)) / 60000; return !isFinite(m) ? "" : m < 1 ? "just now" : m < 60 ? Math.round(m) + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " d ago"; }
  function nets() { return D && D.nets ? D.nets : []; }
  function byId(id) { var a = nets(); for (var i = 0; i < a.length; i++) if (a[i].id === id) return a[i]; return null; }
  function rep(id) { return (B && B.reports && B.reports[id]) || { h1: 0, h24: 0, hrs: null, states: {}, surge: false, base: 0 }; }
  function deps() { return (B && B.deps) || []; }
  function hot(n) { return n.level >= 2 || rep(n.id).surge; }
  function score(n) { var r = rep(n.id); return (n.level >= 0 ? n.level : 0) * 10 + (r.surge ? 15 : 0) + Math.min(9, r.h1); }
  function upsOf(id) { return deps().filter(function (d) { return d.down.indexOf(id) >= 0; }); }
  function chainHits(id) { return upsOf(id).filter(function (d) { var u = byId(d.up); return u && u.level >= 2; }); }

  /* ---------- 24 h strip: one bar per hour (status level), cyan line = our user reports ---------- */
  function strip(n) {
    var h = n.h24, r = rep(n.id).hrs, W = 120, H = 26, bw = W / 24, s = '<svg class="nb-sp" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true">';
    if (!h) return s + '<line x1="0" y1="' + (H - 2) + '" x2="' + W + '" y2="' + (H - 2) + '" class="nb-sp-na"/></svg>';
    for (var i = 0; i < 24; i++) {
      var l = h[i], bh = l >= 3 ? H : l === 2 ? H * 0.78 : l === 1 ? H * 0.5 : l === 0 ? H * 0.28 : H * 0.1;
      s += '<rect x="' + (i * bw + 0.6).toFixed(1) + '" y="' + (H - bh).toFixed(1) + '" width="' + (bw - 1.2).toFixed(1) + '" height="' + bh.toFixed(1) + '" rx="1" class="b-' + LV(l) + '"/>';
    }
    if (r) { var mx = Math.max.apply(null, r); if (mx > 0) { var p = r.map(function (v, i) { return (i * bw + bw / 2).toFixed(1) + "," + (H - 2 - (H - 6) * v / mx).toFixed(1); }); s += '<polyline points="' + p.join(" ") + '" class="nb-sp-r"/>'; } }
    return s + '</svg>';
  }

  /* ---------- verdict: plain English, from the status page, IODA and our own reports ---------- */
  function verdict(n) {
    var r = rep(n.id), nm = short(n.name), lv = n.level, ch = chainHits(n.id), inc = (n.incidents || [])[0], rec = (n.recent || [])[0];
    var head, cls = LV(lv), conf, why = [];
    if (n.link_only) { head = "Check " + nm + "'s own status page."; cls = "na"; }
    else if (lv >= 3) head = "Yes. " + nm + " is down.";
    else if (lv === 2) head = "Partly. " + nm + " has a disruption.";
    else if (lv === 1) head = "Mostly up. " + nm + " reports a minor issue.";
    else if (lv === 0 && r.surge) { head = "Maybe. " + nm + " says it is up, but " + r.h1 + " people reported it down in the last hour."; cls = "rep"; }
    else if (lv === 0 && ch.length) { head = "Probably up, but at risk."; cls = "minor"; }
    else if (lv === 0) head = "No. " + nm + " looks up.";
    else { head = "Unknown. " + nm + "'s live status is unavailable right now."; }
    var isAsn = n.kind === "asn", off = isAsn ? null : lv, ioda = isAsn ? lv : null;
    if (lv >= 2 && !isAsn) conf = "High"; else if (lv >= 2 && isAsn) conf = r.h1 >= 3 ? "High" : "Medium";
    else if (r.surge || ch.length) conf = "Medium"; else if (lv === 0 && r.h1 === 0) conf = "High"; else if (lv >= 0) conf = "Medium"; else conf = "Low";
    var since = "";
    var old = function (ts) { return Date.now() - Date.parse(ts) > 3 * 864e5; };
    if (lv === 1 && inc && inc.since && old(inc.since)) since = "Long-running notice, posted " + new Date(inc.since).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    else if (lv >= 1 && (inc && inc.since)) since = "Since " + when(inc.since) + " (" + ago(inc.since) + ")";
    else if (lv >= 1 && rec && !rec.e) since = "Since " + when(rec.s) + " (" + ago(rec.s) + ")";
    else if (rec && rec.e) since = "Last problem: " + when(rec.s) + ", recovered after " + dur((Date.parse(rec.e) - Date.parse(rec.s)) / 60000);
    else if (!n.link_only && lv >= 0) since = "No problems logged in the last 7 days";
    var where = []; if (isAsn && n.incidents && n.incidents.length) n.incidents.forEach(function (i) { where.push(String(i.t || "").split(":")[0]); });
    var sts = Object.keys(r.states || {}).sort(function (a, b) { return r.states[b] - r.states[a]; });
    if (sts.length) where.push("reports from " + sts.slice(0, 4).join(", "));
    var sig = '<ul class="nb-sig">' +
      '<li><span>Status page</span><b class="c-' + (off == null ? "na" : LV(off)) + '">' + (off == null ? (isAsn ? "None published" : "–") : WORD(off)) + '</b></li>' +
      '<li><span>IODA internet signal</span><b class="c-' + (ioda == null ? "na" : ioda >= 2 ? "deg" : "ok") + '">' + (ioda == null ? "Not measured" : ioda >= 2 ? "Drop detected" : "Normal") + '</b></li>' +
      '<li><span>Reports here, last hour</span><b class="c-' + (r.surge ? "rep" : "na") + '">' + r.h1 + (r.surge ? " · spiking" : "") + '</b></li></ul>';
    var chain = ch.map(function (d) { var u = byId(d.up); return '<p class="nb-vchain"><i></i>Likely affected: ' + esc(short(u.name)) + ' has a ' + esc(WORD(u.level).toLowerCase()) + ' and ' + esc(nm) + ' relies on it. ' + esc(d.why) + '.</p>'; }).join("");
    if (n.incidents && n.incidents.length) why = n.incidents.slice(0, 2).map(function (i) { return '<li>' + esc(i.t) + '</li>'; });
    return '<div class="nb-vh c-' + cls + '"><i></i><div><p class="nb-vt">' + esc(head) + '</p>' + (since ? '<p class="nb-vs">' + esc(since) + (where.length ? " · " + esc(where.join(" · ")) : "") + '</p>' : "") + '</div></div>' +
      (why.length ? '<ul class="nb-vi">' + why.join("") + '</ul>' : "") + chain + sig +
      '<p class="nb-conf">Confidence: <b>' + conf + '</b>' + (n.basis ? " · " + esc(n.basis) : "") + '</p>' + actions(n);
  }
  function actions(n) {
    var a = '<div class="nb-act">';
    if (!n.link_only) a += '<button type="button" class="nb-down" data-down="' + esc(n.id) + '">' + (mine(n.id) ? "Reported. Thanks" : "Down for me") + '</button>';
    a += (url(n.status_url) ? '<a class="nb-lnk" href="' + url(n.status_url) + '" target="_blank" rel="noopener">Official status</a>' : "") +
      (url(n.support) ? '<a class="nb-lnk" href="' + url(n.support) + '" target="_blank" rel="noopener">Contact</a>' : "") +
      (url(n.ioda) ? '<a class="nb-lnk" href="' + url(n.ioda) + '" target="_blank" rel="noopener">IODA</a>' : "") +
      (url(n.page) ? '<a class="nb-lnk" href="' + url(n.page) + '">Details</a>' : "") + '</div><div class="nb-zip" data-zipfor="' + esc(n.id) + '" hidden></div>';
    return a;
  }
  function untracked(app) {
    var ups = deps().filter(function (d) { return d.also.indexOf(app) >= 0; });
    var bad = ups.filter(function (d) { var u = byId(d.up); return u && u.level >= 2; });
    var lst = ups.map(function (d) { var u = byId(d.up); return u ? short(u.name) + " (" + WORD(u.level).toLowerCase() + ")" : d.up; }).join(" and ");
    var head = bad.length ? "Likely affected. " + app + " relies on " + bad.map(function (d) { return short(byId(d.up).name); }).join(" and ") + ", which has a problem now." : "Probably up. We do not track " + app + " directly.";
    return '<div class="nb-vh c-' + (bad.length ? "deg" : "minor") + '"><i></i><div><p class="nb-vt">' + esc(head) + '</p><p class="nb-vs">' + esc(app) + ' went down with ' + esc(lst) + ' in past outages. Their status now: ' +
      esc(ups.map(function (d) { var u = byId(d.up); return u ? short(u.name) + " " + WORD(u.level).toLowerCase() : ""; }).join(", ")) + '.</p></div></div>' +
      '<p class="nb-conf">Confidence: <b>' + (bad.length ? "Medium" : "Low") + '</b> · based on documented past outages, marked as likely</p>' +
      ups.map(function (d) { return '<p class="nb-vs"><a class="nb-lnk" href="' + url(d.src) + '" target="_blank" rel="noopener">Source: ' + esc(d.why) + '</a></p>'; }).join("");
  }

  /* ---------- search ---------- */
  function index() {
    var out = nets().map(function (n) { return { id: n.id, label: short(n.name), hint: sub(n.name), keys: (n.name + " " + n.id).toLowerCase() }; });
    deps().forEach(function (d) { d.also.forEach(function (a) { if (!out.some(function (o) { return o.app === a; })) out.push({ app: a, label: a, hint: "tracked through " + d.up.toUpperCase(), keys: a.toLowerCase() }); }); });
    return out;
  }
  function find(q) {
    q = q.trim().toLowerCase().replace(/\s+/g, " "); if (!q) return [];
    var ix = index(), hit = [], al = ALIAS[q];
    if (al) { var a = al.charAt(0) === "~" ? ix.filter(function (o) { return o.app === al.slice(1); }) : ix.filter(function (o) { return o.id === al; }); hit = hit.concat(a); }
    ix.forEach(function (o) { if (hit.indexOf(o) < 0 && (o.label.toLowerCase().indexOf(q) === 0 || o.keys.indexOf(q) >= 0)) hit.push(o); });
    Object.keys(ALIAS).forEach(function (k) { if (k.indexOf(q) === 0 && q.length >= 2) { var v = ALIAS[k]; ix.forEach(function (o) { if ((v.charAt(0) === "~" ? o.app === v.slice(1) : o.id === v) && hit.indexOf(o) < 0) hit.push(o); }); } });
    return hit.slice(0, 6);
  }
  var qi = $("nb_q"), sug = $("nb_sug"), vbox = $("nb_v");
  function showVerdict(o) {
    if (!o) return; sug.hidden = true;
    var n = o.id ? byId(o.id) : null;
    vbox.innerHTML = '<p class="nb-vk">' + esc(o.label) + (o.hint ? ' <span>' + esc(o.hint) + '</span>' : "") + '</p>' + (n ? verdict(n) : untracked(o.app));
    vbox.hidden = false; vbox.dataset.id = o.id || ""; vbox.dataset.app = o.app || "";
  }
  function suggest() {
    var h = find(qi.value);
    if (!h.length) { sug.hidden = !qi.value.trim(); sug.innerHTML = qi.value.trim() ? '<li class="nb-none">Not tracked yet. Try a provider, carrier, bank or app name.</li>' : ""; return; }
    sug.innerHTML = h.map(function (o, i) { var n = o.id ? byId(o.id) : null; return '<li><button type="button" data-i="' + i + '"><i class="d-' + (n ? LV(n.level) : "na") + '"></i>' + esc(o.label) + '<span>' + esc(o.hint || (n ? WORD(n.level) : "")) + '</span></button></li>'; }).join("");
    sug.hidden = false; sug._h = h;
  }
  qi.addEventListener("input", suggest);
  qi.addEventListener("focus", function () { if (qi.value) suggest(); });
  sug.addEventListener("click", function (e) { var b = e.target.closest("button[data-i]"); if (b) { var o = sug._h[+b.dataset.i]; qi.value = o.label; showVerdict(o); } });
  $("nb_qf").addEventListener("submit", function (e) { e.preventDefault(); var h = find(qi.value); if (h.length) { qi.value = h[0].label; showVerdict(h[0]); qi.blur(); } else suggest(); });
  document.addEventListener("click", function (e) { if (!e.target.closest(".nb-hero")) sug.hidden = true; });

  /* ---------- tiles ---------- */
  function tile(n) {
    var r = rep(n.id), cls = "nb-t s-" + LV(n.level) + (r.surge && n.level < 2 ? " s-rep" : "") + (OPEN === n.id ? " on" : ""), ch = chainHits(n.id);
    return '<button type="button" class="' + cls + '" data-t="' + esc(n.id) + '" aria-expanded="' + (OPEN === n.id) + '">' +
      '<span class="nb-tn">' + esc(short(n.name)) + '</span>' + (sub(n.name) ? '<span class="nb-ts">' + esc(sub(n.name)) + '</span>' : "") +
      '<span class="nb-tw"><i></i>' + esc(n.link_only ? "Link to status" : r.surge && n.level < 2 ? "People report problems" : WORD(n.level)) + (ch.length && n.level < 2 ? '<em>Likely affected</em>' : "") + '</span>' + strip(n) +
      '<span class="nb-tf"><span>24 h</span>' + (r.h1 ? '<span class="nb-tr">' + r.h1 + ' report' + (r.h1 > 1 ? "s" : "") + ' / h</span>' : (n.uptime != null ? '<span>' + n.uptime.toFixed(2) + '% · 30 d</span>' : "")) + '</span></button>';
  }
  function detail(n) {
    var tl = ((B && B.timeline) || []).filter(function (t) { return t.svc === n.id; }).slice(0, 4);
    var ups = upsOf(n.id), downs = deps().filter(function (d) { return d.up === n.id; });
    return '<div class="nb-d" id="nb_d" role="region" aria-label="' + esc(short(n.name)) + ' details"><button type="button" class="nb-dx" aria-label="Close details">×</button>' +
      '<p class="nb-vk">' + esc(short(n.name)) + (sub(n.name) ? ' <span>' + esc(sub(n.name)) + '</span>' : "") + '</p>' + verdict(n) +
      (tl.length ? '<p class="nb-k2">Recent log</p><ul class="nb-dl">' + tl.map(tlRow).join("") + '</ul>' : "") +
      (downs.length ? '<p class="nb-k2">If ' + esc(short(n.name)) + ' fails, these often fail too</p>' + downs.map(chainBody).join("") : "") +
      (ups.length ? '<p class="nb-k2">Depends on</p><p class="nb-vs">' + ups.map(function (d) { var u = byId(d.up); return u ? esc(short(u.name)) + " (" + esc(WORD(u.level).toLowerCase()) + ")" : ""; }).join(", ") + '. Documented in past outages.</p>' : "") + '</div>';
  }
  function groups() {
    var all = nets(), h = "";
    var gs = GB.map(function (g) { var ns = all.filter(function (n) { return g.g.indexOf(n.group) >= 0; }); ns.sort(function (a, b) { return (score(b) - score(a)) || a.name.localeCompare(b.name); });
      return { g: g, ns: ns, worst: ns.reduce(function (m, n) { return Math.max(m, score(n)); }, 0) }; }).filter(function (x) { return x.ns.length; });
    gs.sort(function (a, b) { return (b.worst >= 20 ? b.worst : 0) - (a.worst >= 20 ? a.worst : 0); });   /* groups with a real problem move up; otherwise the fixed order */
    gs.forEach(function (x) {
      var bad = x.ns.filter(function (n) { return n.level >= 2; }).length, ok = x.ns.filter(function (n) { return n.level === 0 || n.level === 1; }).length, mi = x.ns.filter(function (n) { return n.level === 1; }).length;
      h += '<section class="nb-g" aria-label="' + esc(x.g.name) + '"><div class="nb-gh"><h2>' + esc(x.g.name) + '</h2><span class="' + (bad ? "c-deg" : "") + '">' + (bad ? bad + " with problems" : (mi ? (ok - mi) + " normal · " + mi + " minor" : ok + " of " + x.ns.length + " normal")) + '</span></div><div class="nb-grid">';
      x.ns.forEach(function (n) { h += tile(n); if (OPEN === n.id && !(hot(n) && !n.link_only)) h += detail(n); });   /* a problem tile opens up in Problems now */
      h += '</div></section>';
    });
    $("nb_groups").innerHTML = h;
  }

  /* ---------- problems now + chain reactions + report map ---------- */
  function chainBody(d) {
    var u = byId(d.up); if (!u) return "";
    var ds = d.down.map(byId).filter(Boolean);
    return '<div class="nb-ch' + (u.level >= 2 ? " on" : "") + '"><p class="nb-chh"><i class="d-' + LV(u.level) + '"></i><b>' + esc(short(u.name)) + (d.region ? " " + esc(d.region) : "") + '</b><span>' + esc(WORD(u.level)) + '</span></p>' +
      '<p class="nb-chl">' + (u.level >= 2 ? "Also likely affected" : "Would likely take down") + '</p><ul class="nb-chd">' +
      ds.map(function (n) { return '<li><button type="button" data-t="' + esc(n.id) + '"><i class="d-' + LV(n.level) + '"></i>' + esc(short(n.name)) + '<span>' + esc(n.level >= 2 ? WORD(n.level) : "likely") + '</span></button></li>'; }).join("") +
      d.also.slice(0, 6).map(function (a) { return '<li class="nb-chu"><span>' + esc(a) + '</span><em>likely</em></li>'; }).join("") + (d.also.length > 6 ? '<li class="nb-chu"><span>+' + (d.also.length - 6) + ' more</span></li>' : "") + '</ul>' +
      '<p class="nb-chs"><a href="' + url(d.src) + '" target="_blank" rel="noopener">' + esc(d.why) + '</a></p></div>';
  }
  function now() {
    var all = nets().filter(function (n) { return !n.link_only; }), bad = all.filter(hot).sort(function (a, b) { return score(b) - score(a); });
    var tracked = all.filter(function (n) { return n.level >= 0; }), ok = tracked.filter(function (n) { return n.level <= 1; }).length, minor = tracked.filter(function (n) { return n.level === 1; }).length;
    var pulse = $("nb_pulse"), sec = $("nb_now");
    var worst = bad.length ? Math.max.apply(null, bad.map(function (n) { return n.level; })) : 0;
    pulse.className = "nb-pulse c-" + (bad.length ? (worst >= 3 ? "out" : worst === 2 ? "deg" : "rep") : "ok");
    pulse.innerHTML = '<i></i><div><p class="nb-pt">' + (bad.length ? bad.length + (bad.length > 1 ? " services have problems right now" : " service has a problem right now") : "No major U.S. outages right now") + '</p>' +
      '<p class="nb-ps">' + (ok - minor) + " normal" + (minor ? " · " + minor + " minor issue" + (minor > 1 ? "s" : "") : "") + " · " + all.length + " tracked" + (D && D.generated ? " · checked " + ago(D.generated) : "") + '</p></div>';
    var chains = deps().filter(function (d) { var u = byId(d.up); return u && u.level >= 2; });
    if (!bad.length) { sec.hidden = true; sec.innerHTML = ""; }
    else {
      var h = '<div class="nb-gh"><h2>Problems now</h2><span>Worst first</span></div><div class="nb-grid">';
      bad.forEach(function (n) { h += tile(n); if (OPEN === n.id) h += detail(n); });
      h += '</div>';
      if (chains.length) h += '<div class="nb-gh"><h2>Chain reactions</h2><span>Documented dependencies</span></div><div class="nb-chg">' + chains.map(chainBody).join("") + '</div>';
      var st = {}; bad.forEach(function (n) { var s = rep(n.id).states || {}; for (var k in s) st[k] = (st[k] || 0) + s[k]; });
      if (Object.keys(st).length) h += '<div class="nb-gh"><h2>Where people report it</h2><span>Last 3 hours, by ZIP</span></div><div class="nb-map" id="nb_map" data-st=\'' + esc(JSON.stringify(st)) + '\'></div>';
      sec.innerHTML = h; sec.hidden = false; if (Object.keys(st).length) usMap(st);
    }
    var cw = $("nb_chains"); if (cw) cw.innerHTML = deps().filter(function (d) { return chains.indexOf(d) < 0; }).map(chainBody).join("");
  }
  function usMap(st) {
    var el = $("nb_map"); if (!el) return;
    var draw = function () {
      var W = 600, H = 340, x = function (lo) { return (lo + 125) / 59 * W; }, y = function (la) { return (50 - la) / 26 * H; }, pth = "";
      (MAPD.features || []).forEach(function (f) { var g = f.geometry || {}, ls = g.type === "LineString" ? [g.coordinates] : g.type === "MultiLineString" ? g.coordinates : g.type === "Polygon" ? g.coordinates : g.type === "MultiPolygon" ? [].concat.apply([], g.coordinates) : [];
        ls.forEach(function (r) { if (!r || !r.length || !r.every(function (c) { return c[0] > -126 && c[0] < -65 && c[1] > 23 && c[1] < 50.5; })) return; pth += "M" + r.map(function (c) { return x(c[0]).toFixed(1) + " " + y(c[1]).toFixed(1); }).join("L"); }); });   /* continental U.S. only */
      var mx = 1, pt = (B && B.st_pt) || {}, dots = ""; for (var k in st) mx = Math.max(mx, st[k]);
      for (var s in st) { var p = pt[s]; if (!p || p[0] < -126) continue; var rr = 5 + 16 * Math.sqrt(st[s] / mx);
        dots += '<circle cx="' + x(p[0]).toFixed(1) + '" cy="' + y(p[1]).toFixed(1) + '" r="' + rr.toFixed(1) + '" class="nb-md"/><text x="' + x(p[0]).toFixed(1) + '" y="' + (y(p[1]) + 4).toFixed(1) + '">' + esc(s) + '</text>'; }
      el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Map of the continental U.S. with user reports by state"><path d="' + pth + '" class="nb-ms"/>' + dots + '</svg>';
    };
    if (MAPD) draw(); else fetch("/api/signal/us_states.geojson").then(function (r) { return r.json(); }).then(function (j) { MAPD = j; draw(); }, function () { el.hidden = true; });
  }

  /* ---------- timeline ---------- */
  function tlRow(t) {
    var s = when(t.start), e = t.end ? tm(t.end) + (TZ ? " " + TZ : "") : null;
    return '<li class="c-' + (t.end ? "done" : LV(t.level)) + '"><i></i><div><p class="nb-tlh"><b>' + esc(short(t.name)) + '</b> ' + esc(t.title) + '</p><p class="nb-tlm">' +
      (t.end ? "Started " + esc(s) + " · recovered " + esc(e) + " · " + dur(t.mins) : "Started " + esc(s) + " · still going, " + dur(t.mins) + " so far") + ' · ' + esc(t.src) + '</p></div></li>';
  }
  var TLN = 10;
  function timeline() {
    var tl = (B && B.timeline) || [], el = $("nb_tl"); if (!el) return;
    if (!tl.length) { el.innerHTML = '<p class="nb-empty">Nothing logged in the last 3 days.</p>'; return; }
    var h = "", last = "";
    tl.slice(0, TLN).forEach(function (t) { var d = dayLbl(t.start); if (d !== last) { h += (last ? "</ul>" : "") + '<p class="nb-day">' + esc(d) + '</p><ul class="nb-tll">'; last = d; } h += tlRow(t); });
    h += "</ul>" + (tl.length > TLN ? '<button type="button" class="nb-more" id="nb_tlm">Show more</button>' : "");
    el.innerHTML = h; var m = $("nb_tlm"); if (m) m.onclick = function () { TLN += 15; timeline(); };
  }

  /* ---------- Down for me ---------- */
  function mine(id) { try { var m = JSON.parse(localStorage.getItem("bn_nb_rep") || "{}"); return m[id] && Date.now() - m[id] < 9e5; } catch (e) { return false; } }
  function setMine(id) { try { var m = JSON.parse(localStorage.getItem("bn_nb_rep") || "{}"); m[id] = Date.now(); localStorage.setItem("bn_nb_rep", JSON.stringify(m)); } catch (e) {} }
  function post(body) { return fetch("/api/vote/netdown", { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(body) }).then(function (r) { return r.json().then(function (j) { j._ok = r.ok; j._st = r.status; return j; }); }); }
  root.addEventListener("click", function (e) {
    var dn = e.target.closest("[data-down]");
    if (dn) {
      var id = dn.dataset.down; if (mine(id) || dn.disabled) return; dn.disabled = true; dn.textContent = "Sending…";
      post({ svc: id }).then(function (j) {
        var z = dn.closest(".nb-v,.nb-d").querySelector('[data-zipfor="' + id + '"]');
        if (!j._ok && j._st === 429) { setMine(id); dn.textContent = "Already counted. Thanks"; dn.classList.add("done"); return; }
        if (!j._ok) { dn.textContent = j.error || "Could not send"; dn.disabled = false; return; }
        setMine(id); dn.textContent = "Reported. Thanks"; dn.classList.add("done");
        if (z) { z.hidden = false; z.innerHTML = '<form class="nb-zf"><label for="nbz_' + esc(id) + '">Add your ZIP to put it on the outage map (optional, nothing else is stored)</label><div><input id="nbz_' + esc(id) + '" inputmode="numeric" pattern="[0-9]{5}" maxlength="5" placeholder="ZIP" autocomplete="postal-code"><button type="submit">Add</button></div></form>';
          z.querySelector("form").onsubmit = function (ev) { ev.preventDefault(); var v = z.querySelector("input").value.trim(); if (!/^\d{5}$/.test(v)) { z.querySelector("label").textContent = "Enter 5 digits"; return; }
            post({ tok: j.tok, zip: v }).then(function (k) { z.innerHTML = '<p class="nb-vs">' + (k._ok ? "Added to the map (" + esc(k.st) + ")." : esc(k.error || "Could not add the ZIP")) + '</p>'; setTimeout(loadBoard, 1500); }, function () {}); }; }
        setTimeout(function () { HOLD = false; loadBoard(); }, 45000);
      }, function () { dn.textContent = "Could not send. Try again"; dn.disabled = false; });
      return;
    }
    var x = e.target.closest(".nb-dx"); if (x) { OPEN = null; render(); return; }
    var t = e.target.closest("[data-t]");
    if (t) { var nid = t.dataset.t; OPEN = OPEN === nid ? null : nid; render(); var d = $("nb_d"); if (d && OPEN) { var r = d.getBoundingClientRect(); if (r.top < 110 || r.bottom > innerHeight) root.scrollTo({ top: root.scrollTop + r.top - 120, behavior: "smooth" }); } }
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && OPEN) { OPEN = null; render(); } });

  /* ---------- data ---------- */
  var HOLD = false;
  function render() {
    if (!D) return;
    if (document.querySelector(".nb-zf")) { HOLD = true; return; }   /* never wipe a ZIP box someone is typing in */ now(); groups(); timeline();
    if (vbox.dataset.id || vbox.dataset.app) { var o = vbox.dataset.id ? { id: vbox.dataset.id, label: short((byId(vbox.dataset.id) || {}).name), hint: sub((byId(vbox.dataset.id) || {}).name) } : { app: vbox.dataset.app, label: vbox.dataset.app };
      var keepZip = vbox.querySelector(".nb-zip:not([hidden])"); if (!keepZip) showVerdict(o); }
  }
  function loadBoard() {
    return fetch("/api/netmap/board", { credentials: "same-origin" }).then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (j) { B = j; render(); }, function () {});
  }
  var pB = loadBoard().then(function () { if (window.__nxStep) window.__nxStep("rep", 1); });
  (window.__nxData || fetch("/api/netmap/data").then(function (r) { return r.json(); })).then(function (j) {
    D = j; render();
    var q = new URLSearchParams(location.search).get("q"); if (q) { qi.value = q; var h = find(q); if (h.length) showVerdict(h[0]); }
  }, function () { $("nb_pulse").innerHTML = '<i></i><div><p class="nb-pt">Network data is unavailable right now</p><p class="nb-ps">Try again in a minute.</p></div>'; });
  document.addEventListener("nx:data", function (e) { D = e.detail; render(); });
  setInterval(function () { if (!document.hidden && document.body.classList.contains("nx-board")) loadBoard(); }, 60000);
})();
