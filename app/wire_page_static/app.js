/* The Wire listing page. All digest work stays in the browser.
   APIs: GET /api/state (required), GET /api/social (optional), GET /api/state_items (once, on first expand). */
(function () {
  "use strict";
  var ET = "America/New_York";
  var OFFICIAL_RE = /\b(WHO|NWS|NOAA|USGS|EMSC|GDACS|GEOFON|INGV|JMA|CERT-EU|NCSC|CISA|CDC|FEMA)\b/i;
  var HYPE = /^(?:#?(?:BREAKING(?: NEWS)?|JUST IN|URGENT|ALERT|FLASH|DEVELOPING)\b\s*[:!\-–—|]*\s*)+/i;
  var LEAD = /^[^\w("'“‘\[]+/;
  var state = null;
  var social = null;
  var itemsById = null;
  var itemsPending = null;
  var mode = "confirmed";
  var openId = null;
  var more = { elev: false, low: false };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function parseT(t) {
    if (!t) return null;
    var d = Date.parse(String(t).replace("Z", "+00:00"));
    return isNaN(d) ? null : d;
  }
  function fmtET(ms, withZone) {
    if (!ms) return "";
    var d = new Date(ms);
    var now = new Date();
    var same = d.toLocaleDateString("en-US", { timeZone: ET }) === now.toLocaleDateString("en-US", { timeZone: ET });
    var yest = new Date(now.getTime() - 864e5).toLocaleDateString("en-US", { timeZone: ET }) === d.toLocaleDateString("en-US", { timeZone: ET });
    var t = d.toLocaleTimeString("en-US", { timeZone: ET, hour: "numeric", minute: "2-digit" });
    var z = withZone ? " ET" : "";
    if (same) return t + z;
    if (yest) return "Yesterday, " + t + z;
    return d.toLocaleDateString("en-US", { timeZone: ET, month: "short", day: "numeric" }) + ", " + t + z;
  }
  function cleanTitle(t) {
    t = String(t || "").replace(/\s+/g, " ").trim();
    t = t.replace(/^[\s⚡🚨🔴⚠️•●|]+/, "");
    t = t.replace(LEAD, "");
    t = t.replace(HYPE, "").replace(LEAD, "").trim();
    t = t.replace(/(\s+@[A-Za-z0-9_.]{2,30})+\.?$/, "").trim();
    t = t.replace(/\s+\S+\.(wordpress\.com|blogspot\.com)\S*$/, "").trim();
    // Nov 17 3 AM: clean short display titles (display only; scanner data and scoring untouched)
    var g = t.match(/^(Green|Orange|Red) (?:notification|alert) for (.+?)(?:\.\s|\.$|$)/i);
    if (g) { var gev = g[2].replace(/^(an?|the) /i, ""); return gev.charAt(0).toUpperCase() + gev.slice(1) + " (" + g[1].toLowerCase() + " alert)"; }
    var g2 = t.match(/^(Green|Orange|Red) (earthquake|flood|drought|tropical cyclone|volcano|wildfire|forest fire)\b.{0,80}?\bin ([A-Z][A-Za-z .-]{1,40}?)(?= \d| \(|,|\.|$)/);
    if (g2) return g2[2].charAt(0).toUpperCase() + g2[2].slice(1) + " in " + g2[3].trim() + " (" + g2[1].toLowerCase() + " alert)";
    var bar = t.match(/^[A-Za-z /&-]{3,40} \| (.{12,})$/);
    if (bar) t = bar[1];
    t = t.replace(/^\d{1,2}\/10\s+/, "");
    var ro = t.match(/^(.{30,160}?[a-z0-9)]) (?:At least|According to|Officials|Authorities|It is|This is)\b/);
    if (ro) t = ro[1];
    if (t.length > 120) t = t.slice(0, 117).replace(/\s+\S*$/, "") + "\u2026";
    var m = t.match(/^(.+? (?:Warning|Watch|Advisory)) issued (.+?) until (.+?) by NWS (.+)$/);
    if (m) {
      var office = m[4].replace(/\s+[A-Z]{2}$/, "").trim();
      return m[1] + ", NWS " + office + ", until " + m[3];
    }
    return t || String(arguments[0] || "");
  }
  function familiesN(c) {
    return parseInt(c.eff_families || c.n_families || 0, 10) || 0;
  }
  function isOfficial(c) {
    var fams = c.families || [];
    var i;
    for (i = 0; i < fams.length; i++) {
      if (OFFICIAL_RE.test(String(fams[i]))) return true;
    }
    var links = c.links || [];
    for (i = 0; i < links.length; i++) {
      if (OFFICIAL_RE.test(String(links[i].source || ""))) return true;
    }
    return OFFICIAL_RE.test(String(c.title || ""));
  }
  function confirmed(c) {
    if (c.watchlist) return false;
    return familiesN(c) >= 2 || isOfficial(c);
  }
  function band(rank) {
    var r = parseInt(rank || 0, 10) || 0;
    if (r >= 7) return "high";
    if (r >= 4) return "elev";
    return "low";
  }
  function hostLabel(src) {
    return String(src || "").replace(/^Google News:\s*/, "").replace(/^NWS \(api\.weather\.gov\)$/, "NWS");
  }

  function analysis(c) {
    var title = c.title || "";
    var raw = c.raw_title || title;
    var n = c.families_n;
    var official = c.official;
    if (/Ocean Shores/i.test(title)) {
      return {
        means: "Local Seattle-area newsrooms report that Ocean Shores, Washington, declared a state of emergency because of weather. Later coverage also mentions a boil-water advisory.",
        action: "If you are in or heading to the Washington coast, follow city and county guidance, boil tap water until any advisory is lifted, and check NWS Seattle before you travel."
      };
    }
    if (/Ebola/i.test(title) && /(Congo|Kenya|Ervebo)/i.test(title + " " + raw)) {
      return {
        means: "Multiple independent outlets report on the Ebola outbreak in the Democratic Republic of the Congo and on Kenya’s response. The rank and source count on this row are the live Wire figures.",
        action: "These items do not, by themselves, change U.S. public guidance. Travelers and health workers should follow current CDC and WHO advisories."
      };
    }
    if (/\bMERS\b/i.test(title) && official) {
      return {
        means: "This is an official WHO Disease Outbreak News item on Middle East respiratory syndrome (MERS). Social posts attached to it typically reprint that notice.",
        action: "The WHO notice is the primary source for case details."
      };
    }
    if (/Timothy Snyder/i.test(title) || /Coup Attempt/i.test(title)) {
      return {
        means: "This headline is commentary, not a confirmed event. The cluster may also include unrelated posts that only share a word with the original piece, so the source list can look noisier than the rank suggests.",
        action: "Treat this as opinion, not a new incident on the ground."
      };
    }
    if (/marathon/i.test(title) && /iheart|same syndicate/i.test((c.flags || []).join(" "))) {
      return {
        means: "This headline is circulating on one radio syndicate. Several items on The Wire can be the same story, not independent confirmations.",
        action: "Wait for an official health-department source or a second independent newsroom before treating this as confirmed."
      };
    }
    if (official && /Flood Warning/i.test(raw) && /Melbourne/i.test(raw)) {
      return {
        means: "The National Weather Service office in Melbourne, Florida, has an active Flood Warning. This is an official NWS alert, not a news rewrite.",
        action: "If you are in the warned area, follow NWS Melbourne and local emergency management. Do not drive through flood water."
      };
    }
    if (official && /Blizzard Warning/i.test(raw)) {
      return {
        means: "This is an official National Weather Service Blizzard Warning. Official alerts on The Wire are single-source by design when they come from NWS.",
        action: "Avoid travel in the warned area until the warning expires, and check the issuing NWS office for the exact zone and end time."
      };
    }
    if (official && /(Storm Warning|Coastal Flood|High Wind|Severe Thunderstorm|Special Marine)/i.test(raw)) {
      return {
        means: "This is an official National Weather Service warning. The title includes the issuing office and the time the warning is in effect.",
        action: "Follow the issuing NWS office and local officials if you are in the warned area."
      };
    }
    if (official && /\bM\s?\d|earthquake/i.test(title)) {
      return {
        means: "This earthquake was reported by official seismic agencies (for example USGS, EMSC, GEOFON or INGV). Magnitude and place come from those agencies.",
        action: "If you felt shaking, use official tsunami and civil-protection guidance for that coast. Most mid-ocean or moderate quakes need no action."
      };
    }
    if (official) {
      return { means: "This item is on The Wire from an official source.", action: "" };
    }
    if (n >= 2) {
      return { means: "Confirmed by " + n + " independent source families.", action: "" };
    }
    return { means: "Single-source and unconfirmed. The score is capped until a second independent source agrees.", action: "" };
  }

  function relatedVideos(c) {
    var list = (social && social.youtube) || [];
    if (!list.length) return [];
    var title = (c.title || "").toLowerCase();
    var words = title.match(/[a-z]{4,}/g) || [];
    var stop = { says: 1, with: 1, from: 1, that: 1, this: 1, they: 1, have: 1, will: 1, into: 1, over: 1, under: 1, about: 1, after: 1, tops: 1, cases: 1, news: 1, network: 1 };
    words = words.filter(function (w) { return !stop[w]; });
    var out = [];
    var i, v, vw, inter, score;
    for (i = 0; i < list.length; i++) {
      v = list[i];
      vw = String(v.title || "").toLowerCase();
      inter = words.filter(function (w) { return vw.indexOf(w) !== -1; });
      score = inter.length;
      if (/\bebola\b/.test(title) && /\bebola\b/.test(vw)) score += 3;
      if (/\bparaguay\b/.test(title) && /\bparaguay\b/.test(vw) && /\bbank\b/.test(vw)) score += 3;
      if (score >= 3 || (score >= 2 && /\bebola\b|\bparaguay\b/.test(title))) {
        out.push({ score: score, v: v });
      }
    }
    out.sort(function (a, b) { return b.score - a.score; });
    return out.slice(0, 3).map(function (x) { return x.v; });
  }

  function isIHeartSyndicate(c) {
    var fams = c.families || [];
    if (fams.length < 3) return false;
    var n = 0;
    fams.forEach(function (f) { if (/iheart\.com$/i.test(String(f))) n++; });
    return n >= 3 && n === fams.length;
  }

  function norm(c, watch) {
    var title = cleanTitle(c.title || "");
    if (/Timothy Snyder/i.test(c.title || "") || /Coup Attempt/i.test(c.title || "")) {
      title = "Timothy Snyder: “Trump’s Next Coup Attempt”";
    }
    var loc = String(c.location || "").trim();
    if (/Ocean Shores/i.test(title) && !loc) loc = "Ocean Shores, WA";
    if (/Qatar/i.test(title) && !loc) loc = "Qatar";
    var event = c.event_time || c.first_seen;
    var first = parseT(c.first_seen);
    var ev = parseT(event);
    var gen = parseT(state && state.generated) || Date.now();
    var flags = [];
    if (isIHeartSyndicate(c)) flags.push("same syndicate");
    return {
      id: c.cluster_id,
      title: title,
      raw_title: c.title || title,
      location: loc,
      category: c.category || "other",
      rank: parseInt(c.rank || 0, 10) || 0,
      score: parseInt(c.score || 0, 10) || 0,
      families_n: familiesN(c),
      families: c.families || [],
      links: c.links || [],
      official: isOfficial(c),
      confirmed: confirmed(c),
      watchlist: !!(watch || c.watchlist),
      rising: !!c.rising,
      new24: !!(first && first >= gen - 864e5),
      event: event,
      first: c.first_seen,
      when: fmtET(ev, false),
      when_full: fmtET(ev, true),
      band: band(c.rank),
      flags: flags
    };
  }

  function pills(c) {
    var out = [];
    if (c.location) out.push("<span>" + esc(c.location) + "</span>");
    if (c.when) out.push("<span>" + esc(c.when) + "</span>");
    if (c.official) out.push('<span class="pill off">Official</span>');
    else if (c.confirmed) out.push('<span class="pill">' + c.families_n + " source" + (c.families_n === 1 ? "" : "s") + "</span>");
    else out.push('<span class="pill">Single source</span>');
    if (c.new24) out.push('<span class="pill new">New</span>');
    if (c.rising) out.push('<span class="pill rise">Rising</span>');
    if (/Commentary|Coup Attempt|Snyder/i.test(c.title)) out.push('<span class="pill">Commentary</span>');
    if (c.flags.indexOf("same syndicate") !== -1) out.push('<span class="pill">Same syndicate</span>');
    return out.join("");
  }

  function sourceList(c) {
    var rows = [];
    var recs = (itemsById && itemsById[c.id]) || [];
    function rankSrc(it) {
      var s = String((it.source || "") + " " + (it.family || "")).toLowerCase();
      var official = !!it.official;
      var major = /who |cidrap|reuters|ap news|associated press|apnews|bbc|new york times|nytimes|washington post|npr|al jazeera|un news|news\.un\.org|cdc|nws|usgs|fox 13|kiro|meduza|kyiv post/.test(s);
      var socialish = /bluesky|twitter|mastodon|telegram|bsky\.app|\bsocial\b/.test(s);
      return (official ? 0 : 1) + (major ? 0 : 2) + (socialish ? 4 : 0);
    }
    recs = recs.slice().sort(function (a, b) { return rankSrc(a) - rankSrc(b); });
    var seen = {};
    var i, it, label, key;
    for (i = 0; i < recs.length && rows.length < 8; i++) {
      it = recs[i];
      label = hostLabel(it.source || "");
      key = label.toLowerCase();
      if (!label || seen[key]) continue;
      seen[key] = 1;
      rows.push({
        source: label,
        title: cleanTitle(it.title || ""),
        url: it.url || "",
        when: fmtET(parseT(it.published || it.first_seen), true),
        official: !!it.official
      });
    }
    if (!rows.length) {
      (c.links || []).slice(0, 6).forEach(function (l) {
        rows.push({ source: hostLabel(l.source || ""), title: "", url: l.url || "", when: "", official: false });
      });
    }
    if (!rows.length) return "";
    var lis = rows.map(function (s) {
      var inner = '<span class="src-n">' + esc(s.source || "Source") + "</span>";
      if (s.title && s.title !== c.title) inner += " — " + esc(s.title);
      if (s.when) inner += ' <span class="src-m">' + esc(s.when) + "</span>";
      if (/^https?:\/\//.test(s.url)) {
        return "<li><a href=\"" + esc(s.url) + "\" target=\"_blank\" rel=\"noopener\">" + inner + "</a></li>";
      }
      return "<li>" + inner + "</li>";
    }).join("");
    var extra = c.families_n > rows.length
      ? "Showing " + rows.length + " of " + c.families_n + " source families. "
      : "";
    return '<div class="means"><b>Sources</b></div><ul class="srcs">' + lis + "</ul>" +
      '<div class="note">' + extra + "<a href=\"/wire/" + esc(c.id) + "\">Open the full story</a>.</div>";
  }

  function vidsHtml(c) {
    var vids = relatedVideos(c);
    if (!vids.length) return "";
    var blocks = vids.map(function (v) {
      var id = v.id || "";
      var thumb = v.thumb || ("https://i.ytimg.com/vi/" + id + "/hqdefault.jpg");
      var when = fmtET(parseT(v.published), false);
      return '<div><div class="vid"><button type="button" data-yt="' + esc(id) + '" aria-label="Play ' + esc(v.title || "video") + '">' +
        '<img src="' + esc(thumb) + '" alt=""><span class="play"></span></button></div>' +
        '<div class="vidcap">@BlkoutNtw' + (when ? " · " + esc(when) : "") + " · " + esc(v.title || "") + "</div></div>";
    }).join("");
    return '<div class="means"><b>Our coverage</b></div><div class="vids">' + blocks + "</div>";
  }

  function bodyHtml(c) {
    var a = analysis(c);
    var html = "";
    if (a.means) html += '<p class="means"><b>What we know</b>' + esc(a.means) + "</p>";
    if (a.action) html += '<p class="do"><b>What to do</b>' + esc(a.action) + "</p>";
    html += vidsHtml(c);
    html += sourceList(c);
    return html;
  }

  function accHtml(c) {
    var opened = c.id === openId;
    return '<article class="acc ' + c.band + (opened ? " open" : "") + '" id="s-' + esc(c.id) + '" data-cid="' + esc(c.id) + '">' +
      '<button class="acc-h" type="button" aria-expanded="' + (opened ? "true" : "false") + '" aria-controls="b-' + esc(c.id) + '">' +
      '<span class="rk"><b>' + c.rank + "</b><i>/10</i></span>" +
      '<span class="mid"><span class="t">' + esc(c.title) + '</span><span class="meta">' + pills(c) + "</span></span>" +
      '<svg class="chev" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 7.5 L10 12.5 L15 7.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      "</button>" +
      '<div class="acc-body" id="b-' + esc(c.id) + '"><div class="acc-in"><div class="acc-pad" data-body="' + esc(c.id) + '">' +
      (opened ? bodyHtml(c) : "") +
      "</div></div></div></article>";
  }

  function sortHigh(a, b) {
    if (a.new24 !== b.new24) return a.new24 ? -1 : 1;
    return (b.score - a.score) || String(a.first || "").localeCompare(String(b.first || ""));
  }
  function sortScore(a, b) { return (b.score - a.score) || String(a.first || "").localeCompare(String(b.first || "")); }

  function bulletin(main) {
    var gen = parseT(state.generated) || Date.now();
    var cut = gen - 864e5;
    var new24 = main.filter(function (c) { return parseT(c.first) >= cut; });
    var highNew = main.filter(function (c) { return c.band === "high" && c.new24; });
    var bullets = [];
    if (highNew.length) {
      var h = highNew[0];
      var extra = /Ocean Shores/i.test(h.title) ? " A boil-water advisory is in the latest local coverage." : "";
      bullets.push("<li><a href=\"#s-" + esc(h.id) + "\"><strong>New high.</strong> " + esc(h.title) + "</a></li>");
    } else {
      bullets.push("<li><strong>No new high-rank items</strong> in the last 24 hours.</li>");
    }
    var rising = main.filter(function (c) { return c.rising; }).sort(function (a, b) { return b.rank - a.rank; })[0];
    if (rising) {
      bullets.push("<li><a href=\"#s-" + esc(rising.id) + "\"><strong>Rising.</strong> " + esc(rising.title) + "</a></li>");
    }
    var bliz = main.filter(function (c) { return /Blizzard Warning/i.test(c.raw_title) && c.new24; })[0];
    if (bliz) {
      var until = (bliz.raw_title.match(/until (.+?) by NWS/i) || [])[1];
      bullets.push("<li><strong>Official.</strong> Blizzard Warning from NWS Fairbanks" + (until ? ", in effect until " + until : "") + ".</li>");
    }
    var fl = main.filter(function (c) { return /Melbourne/i.test(c.raw_title) && /Flood Warning/i.test(c.raw_title) && /November 14|Nov 14/i.test(c.raw_title + " " + (c.when_full || "")); })[0];
    if (!fl) fl = main.filter(function (c) { return /Melbourne/i.test(c.raw_title) && /Flood Warning/i.test(c.raw_title) && c.new24; })[0];
    if (fl) {
      bullets.push("<li><a href=\"#s-" + esc(fl.id) + "\"><strong>Official.</strong> Flood Warning from NWS Melbourne, Florida, issued this morning.</a></li>");
    }
    var mers = main.filter(function (c) { return /\bMERS\b/i.test(c.title); })[0];
    var ebo = main.filter(function (c) { return /Ebola/i.test(c.title) && /Congo|Kenya/i.test(c.title); })[0];
    if (mers || ebo) {
      var bits = [];
      if (mers) bits.push("WHO MERS notice for Qatar");
      if (ebo) bits.push("DRC Ebola outbreak, with Kenya in a countdown");
      bullets.push("<li><strong>Still high.</strong> " + esc(bits.join(" · ")) + ".</li>");
    }
    var ndNew = new24.filter(function (c) { return c.category === "natural disaster"; });
    var quakes = ndNew.map(function (c) {
      var m = (c.title + " " + c.raw_title).match(/\bM\s?(\d+(?:\.\d+)?)/);
      return m ? { c: c, mag: parseFloat(m[1]) } : null;
    }).filter(Boolean).sort(function (a, b) { return b.mag - a.mag; });
    if (ndNew.length) {
      var line = "<li><strong>Hazards.</strong> " + ndNew.length + " new in 24 hours.";
      if (quakes.length) {
        line += " Strongest quake M" + quakes[0].mag + ".";
      }
      bullets.push(line + "</li>");
    }
    var ul = $("w-bullets");
    ul.innerHTML = bullets.join("");
    var allb = $("w-allb");
    if (bullets.length > 2) {   // new theme: two headlines first, the rest one tap away
      if (!allb) {
        allb = document.createElement("button"); allb.type = "button"; allb.id = "w-allb"; allb.className = "w-allb";
        allb.setAttribute("aria-controls", "w-bullets");
        allb.addEventListener("click", function () { var o = !ul.classList.contains("all"); ul.classList.toggle("all", o); allb.setAttribute("aria-expanded", o ? "true" : "false"); allb.textContent = o ? "Show fewer" : "Show all " + ul.children.length + " changes"; });
        ul.parentNode.insertBefore(allb, ul.nextSibling);
      }
      ul.classList.add("fold");
      if (!ul.classList.contains("all")) { allb.setAttribute("aria-expanded", "false"); allb.textContent = "Show all " + bullets.length + " changes"; }
      allb.hidden = false;
    } else { ul.classList.remove("fold"); if (allb) allb.hidden = true; }
    var notice = window.BN_WIRE_NOTICE;
    var coming = $("w-coming");
    if (notice && notice.title) {
      coming.hidden = false;
      var open = coming.querySelector(".bnt-acc-h[aria-expanded=true]");   // keep it open across refreshes
      coming.innerHTML = '<button type="button" class="bnt-acc-h w-nh" aria-expanded="' + (open ? "true" : "false") + '" aria-controls="w-nb"><span>' +
        '<span class="k">' + esc(notice.kicker || "Featured notice") + (notice.tag ? " · " + esc(notice.tag) : "") + "</span>" +
        "<strong>" + esc(notice.title) + "</strong></span></button>" +
        '<div class="bnt-acc-b" id="w-nb"' + (open ? "" : " hidden") + '><div class="bnt-acc-in">' + (notice.text ? esc(notice.text) : "") +
        (notice.href ? ' <a class="w-nl" href="' + esc(notice.href) + '">Read the notice &rarr;</a>' : "") + "</div></div>";
    } else {
      coming.hidden = true;
      coming.innerHTML = "";
    }
    $("w-bulletin").hidden = false;
  }

  function render() {
    if (!state) return;
    var main = (state.main || []).map(function (c) { return norm(c, false); });
    var watch = (state.watchlist || []).map(function (c) { return norm(c, true); });
    var gen = parseT(state.generated);
    stampUp(gen);
    $("w-updated").textContent = main.length + " stories";
    $("w-updated").title = "Scanner checks about every " + (state.interval_minutes || 5) + " minutes · " + main.length + " stories on The Wire · " + (state.watchlist_count || watch.length) + " single-source on the watchlist";
    bulletin(main);
    var nHigh = main.filter(function (c) { return c.band === "high"; }).length;
    var nElev = main.filter(function (c) { return c.band === "elev"; }).length;
    var nLow = main.filter(function (c) { return c.band === "low"; }).length;
    $("w-stats").innerHTML =
      '<div class="stat high"><b>' + nHigh + "</b><span>High · 7–10</span></div>" +
      '<div class="stat elev"><b>' + nElev + "</b><span>Elevated · 4–6</span></div>" +
      '<div class="stat low"><b>' + nLow + "</b><span>Lower · 0–3</span></div>";

    var high = main.filter(function (c) { return c.band === "high"; }).sort(sortHigh);
    var elev = main.filter(function (c) { return c.band === "elev" && c.confirmed; }).sort(sortScore);
    var low = main.filter(function (c) { return c.band === "low" && c.confirmed; }).sort(sortScore);
    var elevShow = more.elev ? elev : elev.slice(0, 7);
    var lowShow = more.low ? low : low.slice(0, 3);
    var html = "";
    if (mode === "confirmed") {
      html += '<section><div class="bandh"><h2 class="high">High</h2><span class="n">' + high.length + " confirmed or official</span></div>";
      html += high.map(accHtml).join("");
      html += '<div class="bandh"><h2 class="elev">Elevated</h2><span class="n">' + elev.length + " confirmed or official</span></div>";
      html += elevShow.map(accHtml).join("");
      if (!more.elev && elev.length > elevShow.length) {
        html += '<button class="more" type="button" data-more="elev">Show ' + (elev.length - elevShow.length) + " more elevated items</button>";
      }
      html += '<div class="bandh"><h2 class="low">Lower</h2><span class="n">' + low.length + " confirmed or official, still on the board</span></div>";
      html += lowShow.map(accHtml).join("");
      if (!more.low && low.length > lowShow.length) {
        html += '<button class="more" type="button" data-more="low">Show ' + (low.length - lowShow.length) + " more lower-ranked items</button>";
      }
      html += "</section>";
    } else {
      var show = watch.slice().sort(function (a, b) { return (b.rank - a.rank) || (b.score - a.score); }).slice(0, 10);
      html += '<section><div class="bandh"><h2 class="elev">Single-source watchlist</h2><span class="n">' +
        (state.watchlist_count || watch.length) + " items · scores capped until a second source confirms</span></div>";
      html += '<p class="dek" style="margin-top:0">These are not on The Wire yet. If a second independent source agrees, they move up automatically.</p>';
      html += show.map(accHtml).join("");
      html += '<p class="note">Showing ' + show.length + " of " + (state.watchlist_count || watch.length) +
        ". The live watchlist is longer; this page keeps the list short on purpose.</p></section>";
    }
    $("w-feed").innerHTML = html;
    var mn = $("main"); if (mn) { mn.classList.remove("w-loading"); mn.removeAttribute("aria-busy"); }
    fillOpen();
  }

  function fillOpen() {
    if (!openId) return;
    var pad = document.querySelector('[data-body="' + openId + '"]');
    if (!pad) return;
    if (pad.getAttribute("data-filled") === "1") return;
    var c = findItem(openId);
    if (!c) return;
    pad.innerHTML = bodyHtml(c);
    pad.setAttribute("data-filled", "1");
  }

  function findItem(id) {
    var bag = (state.main || []).concat(state.watchlist || []);
    var raw = null;
    for (var i = 0; i < bag.length; i++) if (bag[i].cluster_id === id) { raw = bag[i]; break; }
    return raw ? norm(raw, !!raw.watchlist) : null;
  }

  function ensureItems(cb) {
    if (itemsById) { cb(); return; }
    if (itemsPending) { itemsPending.push(cb); return; }
    itemsPending = [cb];
    fetch("/api/state_items", { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (j) {
      itemsById = (j && j.items) || {};
      var cbs = itemsPending; itemsPending = null;
      cbs.forEach(function (fn) { try { fn(); } catch (e) {} });
    }).catch(function () {
      itemsById = itemsById || {};
      var cbs = itemsPending; itemsPending = null;
      cbs.forEach(function (fn) { try { fn(); } catch (e) {} });
    });
  }

  function toggleAcc(acc) {
    var id = acc.getAttribute("data-cid");
    var willOpen = !acc.classList.contains("open");
    document.querySelectorAll(".bn-wire .acc.open").forEach(function (el) {
      if (el !== acc) {
        el.classList.remove("open");
        var b = el.querySelector(".acc-h");
        if (b) b.setAttribute("aria-expanded", "false");
      }
    });
    acc.classList.toggle("open", willOpen);
    var btn = acc.querySelector(".acc-h");
    if (btn) btn.setAttribute("aria-expanded", willOpen ? "true" : "false");
    openId = willOpen ? id : null;
    if (willOpen) {
      ensureItems(function () {
        var pad = acc.querySelector("[data-body]");
        var c = findItem(id);
        if (pad && c) { pad.innerHTML = bodyHtml(c); pad.setAttribute("data-filled", "1"); }
      });
    }
  }

  document.addEventListener("click", function (e) {
    var h = e.target.closest && e.target.closest(".acc-h");
    if (h) { e.preventDefault(); toggleAcc(h.closest(".acc")); return; }
    var moreBtn = e.target.closest && e.target.closest("[data-more]");
    if (moreBtn) { more[moreBtn.getAttribute("data-more")] = true; render(); return; }
    var seg = e.target.closest && e.target.closest(".seg button[data-mode]");
    if (seg) {
      mode = seg.getAttribute("data-mode");
      document.querySelectorAll(".seg button[data-mode]").forEach(function (b) {
        b.setAttribute("aria-pressed", b === seg ? "true" : "false");
      });
      openId = null;
      render();
      return;
    }
    var yt = e.target.closest && e.target.closest("button[data-yt]");
    if (yt) {
      var f = document.createElement("iframe");
      f.src = "https://www.youtube-nocookie.com/embed/" + yt.getAttribute("data-yt") + "?autoplay=1&rel=0&modestbranding=1&playsinline=1";
      f.title = yt.getAttribute("aria-label") || "Video";
      f.allow = "accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture";
      f.allowFullscreen = true;
      f.referrerPolicy = "strict-origin-when-cross-origin";
      var v = yt.closest(".vid");
      v.innerHTML = "";
      v.appendChild(f);
    }
  });

  /* per-module refresh (Matt Nov 17 1:10 AM): "Updated h:mm AM ET · next in Xm" + a button that reloads just the feed */
  function stampUp(gen) {
    if (!window.BNT || !BNT.up) return;
    var iv = ((state && state.interval_minutes) || 5) * 60000, at = gen || Date.now(), nx = at + iv;
    while (nx < Date.now() - 30000) nx += iv;
    BNT.up($("w-up"), { label: "The Wire", at: at, next: nx, run: function () { return loadState(); } });
  }
  function loadState() {
    return fetch("/api/state", { credentials: "same-origin", cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("state " + r.status);
      return r.json();
    }).then(function (j) { state = j; render(); }).catch(function () {});
  }
  setInterval(function () { if (!document.hidden && state) loadState(); }, 300000);
  function boot() {
    var err = $("w-err");
    fetch("/api/state", { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("state " + r.status);
      return r.json();
    }).then(function (j) {
      state = j;
      render();
    }).catch(function () {
      err.hidden = false;
      err.textContent = "The live feed could not be loaded. Refresh the page, or open the dashboard at the homepage.";
      $("w-updated").textContent = "The live feed is unavailable right now.";
      var mn = $("main"); if (mn) { mn.classList.remove("w-loading"); mn.removeAttribute("aria-busy"); }
      $("w-feed").innerHTML = ""; $("w-bulletin").hidden = true;
    });
    fetch("/api/social", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      social = j;
      if (openId) {
        var pad = document.querySelector('[data-body="' + openId + '"]');
        if (pad) pad.removeAttribute("data-filled");
        fillOpen();
      }
    }).catch(function () { social = social || { youtube: [] }; });
  }
  boot();
})();
