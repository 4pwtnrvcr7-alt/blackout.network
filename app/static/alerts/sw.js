/* BLACKOUT.NETWORK service worker (t341): Web Push alerts only. No fetch handler and no caching, so the site always loads fresh. */
var ICON = "/icons/icon-192.png", BADGE = "/alerts/badge.png";
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });

function safeUrl(u) {
  try { var x = new URL(u || "/", self.location.origin); if (x.origin === self.location.origin) return x.href; } catch (e) {}
  return self.location.origin + "/";
}
self.addEventListener("push", function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : "" }; }
  var title = String(d.title || "BLACKOUT.NETWORK").slice(0, 80);
  var opts = { body: String(d.body || "").slice(0, 200), icon: d.icon || ICON, badge: d.badge || BADGE, lang: "en", dir: "ltr",
               tag: d.tag || undefined, renotify: false, silent: false, timestamp: d.ts ? Date.parse(d.ts) || Date.now() : Date.now(),
               data: { url: safeUrl(d.url), id: d.id || null } };
  e.waitUntil(self.registration.showNotification(title, opts).then(function () {
    return self.clients.matchAll({ type: "window", includeUncontrolled: true });
  }).then(function (cs) {
    cs.forEach(function (c) { c.postMessage({ type: "bn-push", id: d.id || null, title: title, url: opts.data.url }); });
  }));
});
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = safeUrl(e.notification.data && e.notification.data.url);
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (cs) {
    for (var i = 0; i < cs.length; i++) { if (cs[i].url === url && "focus" in cs[i]) return cs[i].focus(); }
    var w = cs.filter(function (c) { return "navigate" in c && "focus" in c; })[0];   // t399: reuse the open app window (Home Screen app) when there is one
    if (w) return w.focus().then(function (c) { return (c || w).navigate(url); }).catch(function () { return self.clients.openWindow(url); });
    return self.clients.openWindow(url);
  }));
});
self.addEventListener("pushsubscriptionchange", function (e) {
  var old = e.oldSubscription;
  e.waitUntil((e.newSubscription ? Promise.resolve(e.newSubscription) :
      self.registration.pushManager.subscribe(old && old.options ? old.options : { userVisibleOnly: true }))
    .then(function (s) {
      if (!old) return;
      return fetch("/api/alerts/resubscribe", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_endpoint: old.endpoint, sub: s.toJSON() }) });
    }).catch(function () {}));
});
