/* BLACKOUT.NETWORK GA4 events (analyst/ga4-events, 2026-11-02). Schema: launch/team/analyst/ga4_event_schema.md.
   Sanitizer: window.bnPII (server.py GA_JS) is shared; ecommerce helpers apply it too (fail closed if missing).
   Consent: every event goes through window.bnTrack (server.py GA_JS), which drops events unless gtag loaded WITH consent
   (EEA/UK/CH banner, GPC, DNT, opt-out all respected) and strips email/phone-like strings. Nothing is queued before consent.
   Primary hook: delegation on [data-ga-event] + data-ga-* params. Fallback selectors cover today's markup.
   Already sent by GA_JS (not duplicated here): tab_view, newsletter_signup/generate_lead, push_subscribe, broadcast_play, affiliate_click
   (rel=sponsored / data-affiliate), share, settings_change, expand, story_view, alert_view. */
(function(){
if(window.bnGAEvents)return;
function T(n,p){return window.bnTrack?window.bnTrack(n,p||{}):false;}
var ALLOWED={newsletter_signup:1,alert_subscribe:1,push_optin:1,section_add:1,section_remove:1,menu_open:1,accordion_open:1,noise_expand:1,
 ticker_click:1,network_search:1,map_interaction:1,video_play:1,broadcast_play:1,outbound_source_click:1,tip_click:1,affiliate_click:1,ad_click:1,sponsor_click:1};
/* attribute suffix -> GA param (reuses existing GA4 dims content_category, story_rank, partner, station, method) */
var PARAMS={category:'content_category',rank:'story_rank',source:'source',section:'section',item_id:'item_id',map_id:'map_id',action:'action',source_domain:'source_domain',partner:'partner',station:'station',placement:'placement',method:'method'};
function host(u){try{return new URL(u,location.href).hostname.replace(/^www\./,'');}catch(e){return '';}}
function rk(v){var n=parseInt(v,10);return isNaN(n)?undefined:n;}
function ctx(el){var s=el.closest('[data-cat],[data-tab],section[id]');return {
 content_category:el.getAttribute('data-ga-category')||el.getAttribute('data-cat')||(s&&(s.getAttribute('data-cat')||''))||'',
 story_rank:rk(el.getAttribute('data-ga-rank')||el.getAttribute('data-rank')||(el.closest('[data-rank]')||{getAttribute:function(){return null;}}).getAttribute('data-rank')),
 section:el.getAttribute('data-ga-section')||(s&&(s.getAttribute('data-tab')||s.id))||''};}
function params(el){var o=ctx(el);for(var k in PARAMS){var v=el.getAttribute('data-ga-'+k.replace(/_/g,'-'));if(v!=null&&v!=='')o[PARAMS[k]]=k==='rank'?rk(v):v;}return o;}
var PAY=/(^|\.)(paypal\.(com|me)|ko-fi\.com|buymeacoffee\.com|patreon\.com|cash\.app|venmo\.com)$/;
document.addEventListener('click',function(e){var t=e.target;if(!t||!t.closest)return;
 var g=t.closest('[data-ga-event]');
 if(g){var n=g.getAttribute('data-ga-event');if(ALLOWED[n]&&n!=='newsletter_signup'){var p=params(g);if(n==='outbound_source_click'&&!p.source_domain)p.source_domain=host(g.href||'');T(n,p);}return;}
 var a=t.closest('a[href]');var h=a?host(a.href):'';
 if(a&&h&&PAY.test(h)){T('tip_click',{source_domain:h,section:ctx(a).section});return;}
 if(a&&a.hasAttribute('data-sponsor')){T('sponsor_click',{partner:a.getAttribute('data-sponsor')||h});return;}
 if(t.closest('ins.adsbygoogle,[data-ad-slot],.bn-ad')){T('ad_click',{placement:(t.closest('[data-ad-slot]')||{getAttribute:function(){return '';}}).getAttribute('data-ad-slot')});return;}
 var tk=t.closest('.ticker a,.tk a,[data-ticker] a');if(tk){var c=ctx(tk);T('ticker_click',{content_category:c.content_category,story_rank:c.story_rank});return;}
 if(t.closest('[data-bn-alerts],[data-bnal]')&&t.closest('button,a,[role=button]')){T('alert_subscribe',{section:ctx(t).section});return;}
 if(t.closest('.leaflet-control-zoom-in,.leaflet-control-zoom-out,.maplibregl-ctrl-zoom-in,.maplibregl-ctrl-zoom-out')){var m=t.closest('[data-map-id],[id]');T('map_interaction',{map_id:m?(m.getAttribute('data-map-id')||m.id):'',action:'zoom'});return;}
 if(t.closest('.leaflet-marker-icon,.leaflet-interactive,.maplibregl-marker')){var m2=t.closest('[data-map-id],.leaflet-container,.maplibregl-map');T('map_interaction',{map_id:m2?(m2.getAttribute('data-map-id')||m2.id):'',action:'marker'});return;}
 if(t.closest('.bn-menu-btn,[aria-controls][aria-haspopup],button[aria-expanded="false"].menu,#bn_menu_btn')){T('menu_open',{section:ctx(t).section});return;}
 if(a&&h&&h!==location.hostname.replace(/^www\./,'')&&!/(^|\.)blackout\.network$/.test(h)&&t.closest('[data-cat],[data-rank],.card,.src,[data-src]')&&!a.hasAttribute('data-affiliate')&&!/sponsored/.test(a.getAttribute('rel')||'')){var c2=ctx(a);T('outbound_source_click',{source_domain:h,content_category:c2.content_category,story_rank:c2.story_rank});return;}
},true);
/* accordions: <details> toggles (existing [data-bn-expand] already send 'expand'; noise panels send noise_expand) */
document.addEventListener('toggle',function(e){var d=e.target;if(!d||d.tagName!=='DETAILS'||!d.open||d.hasAttribute('data-bn-bulk'))return;
 var n=d.getAttribute('data-ga-event');var c=ctx(d);var id=(d.getAttribute('data-ga-item-id')||d.getAttribute('data-id')||d.id||'').slice(0,60);
 if(n==='noise_expand'||d.closest('[data-noise],.noise,#noise')){T('noise_expand',{section:c.section,item_id:id});return;}
 if(n==='accordion_open'||!d.hasAttribute('data-bn-expand'))T('accordion_open',{section:c.section,item_id:id});},true);
/* sections: checkboxes/buttons with data-ga-section-toggle (checked = add) */
document.addEventListener('change',function(e){var el=e.target;if(!el||!el.closest)return;var s=el.closest('[data-ga-section-toggle]');if(!s||el.type!=='checkbox')return;
 T(el.checked?'section_add':'section_remove',{section:s.getAttribute('data-ga-section-toggle')});setUP();},true);
/* video_play for <video> outside broadcasts (GA_JS sends broadcast_play for all media; video_play only for data-ga-event="video_play" or YouTube iframe focus) */
document.addEventListener('play',function(e){var m=e.target;if(m&&m.tagName==='VIDEO'&&m.closest&&m.closest('[data-ga-event="video_play"]'))T('video_play',params(m.closest('[data-ga-event]')));},true);
window.addEventListener('blur',function(){setTimeout(function(){var f=document.activeElement;if(f&&f.tagName==='IFRAME'&&/youtube(-nocookie)?\.com\/embed\//.test(f.src||'')&&!f.bnPlayed){f.bnPlayed=1;T('video_play',{source:'youtube',section:ctx(f).section});}},0);});
/* site search: search UI sets #search=<q>. Only a 'network_search' count is sent, NEVER the query text (no search_term, no free text).
   Repeated identical hashes are de-duplicated locally without sending anything. */
var lastQ='';function srch(){var m=/^#search=(.+)$/.exec(location.hash);if(!m||m[1]===lastQ)return;lastQ=m[1];T('network_search',{section:ctx(document.body).section||'site'});}
window.addEventListener('hashchange',srch);setTimeout(srch,1500);
/* user properties (no PII) */
function setUP(){if(!window.bnGALoaded||window.BN_GA_SKIP||!window.gtag)return;var up={};
 try{var th=document.documentElement.getAttribute('data-theme');if(th)up.preferred_theme=th.slice(0,20);}catch(e){}
 up.preferred_language=(document.documentElement.lang||navigator.language||'').slice(0,10).toLowerCase();
 var secs=[].slice.call(document.querySelectorAll('[data-ga-section-toggle] input[type=checkbox]:checked')).map(function(i){return i.closest('[data-ga-section-toggle]').getAttribute('data-ga-section-toggle');});
 if(secs.length){up.subscribed_sections_count=secs.length;up.subscribed_sections=secs.sort().join(',').slice(0,36);}
 window.gtag('set','user_properties',up);}
setTimeout(setUP,2000);
/* Monetization stubs for the future shop. NOT called anywhere. Pass real items only; never call with placeholder values. */
function ec(n,o){if(!o||!Array.isArray(o.items)||!o.items.length)return false;if(!window.bnGALoaded||window.BN_GA_SKIP||!window.gtag)return false;
 var P=window.bnPII||function(){return true;},I=window.bnIdOK||function(){return false;},S=function(v,k){return P(v)&&!I(k,v);};for(var k in o){if(o[k]==null||(typeof o[k]==='string'&&S(o[k],k)))delete o[k];}
 o.items=o.items.map(function(it){var c={};for(var j in it){var v=it[j];if(v==null)continue;if(typeof v==='string'){if(S(v,j))continue;v=v.slice(0,100);}else if(typeof v!=='number')continue;c[j]=v;}return c;});
 window.gtag('event',n,o);return true;} /* direct gtag: bnTrack drops arrays; same consent gate */
window.bnGAEvents={
 track:T,setUserProperties:setUP,
 viewItem:function(items,value,currency){return ec('view_item',{currency:currency||'USD',value:value,items:items});},
 addToCart:function(items,value,currency){return ec('add_to_cart',{currency:currency||'USD',value:value,items:items});},
 beginCheckout:function(items,value,currency,coupon){return ec('begin_checkout',{currency:currency||'USD',value:value,coupon:coupon,items:items});},
 purchase:function(transaction_id,items,value,currency,tax,shipping){if(!transaction_id)return false;return ec('purchase',{transaction_id:String(transaction_id),currency:currency||'USD',value:value,tax:tax,shipping:shipping,items:items});}
};
})();
