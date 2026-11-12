"""Legal pages add-on (t270): GET /privacy (Privacy Policy) and GET /tos (Terms of Service; alias /terms).
t285: Privacy adds 'YouTube and Google user data' (Google OAuth consent screen / API Services User Data Policy, Limited Use);
Terms adds 'YouTube content'. Static, self-contained HTML (no scripts, no data reads), so both pages are served even while the public node warms up.
Styled like /scoring: shared /theme.css palette plus a small inline stylesheet. Never touches scanner.py, scoring,
push.py, jets.py, aviation_watch.py or config.json."""
import html
import sitenav   # shared header, tab bar and SEO tags (t301/t302)

EFFECTIVE = "October 31, 2026"
UPDATED = {"privacy": "November 2, 2026", "tos": "November 12, 2026"}   # seo/batch-1 GA4 go-live (Nov 1) + newsletter open/click measurement disclosure (#email-tracking)
CONTACT = "hello@blackout.network"
MAIL = f'<a href="mailto:{CONTACT}">{CONTACT}</a>'

CSS = """
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--ac)}a:focus-visible{outline:2px solid var(--ac);outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:8px;background:var(--pn);padding:6px 10px;z-index:9}
header{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--bd)}
h1{font-size:18px;margin:0;letter-spacing:.5px}h1 b{color:var(--hi)}h1 small{display:block;font-size:12px;font-weight:400;color:var(--mu);margin-top:4px;letter-spacing:.2px}
nav.site{display:flex;flex-wrap:wrap;gap:6px}
nav.site a{border:1px solid var(--bd2);border-radius:8px;padding:6px 12px;text-decoration:none;color:var(--tx);background:var(--pn2);font-size:13px}
nav.site a.on{border-color:var(--ac);color:var(--ac)}
.wrap{max-width:860px;margin:0 auto;padding:18px 20px 40px}
.title{margin:4px 0 4px;font-size:26px;letter-spacing:.2px}.upd{color:var(--mu);font-size:13px;margin:0 0 14px}
.lead{font-size:15.5px}
nav.toc{background:var(--pn);border:1px solid var(--bd);border-radius:var(--radius);padding:12px 16px;margin:0 0 18px}
nav.toc b{display:block;font-size:12px;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
nav.toc ol{margin:0;padding-left:22px;columns:2;column-gap:28px}nav.toc li{font-size:13.5px;margin:2px 0;break-inside:avoid}
nav.toc a{text-decoration:none}nav.toc a:hover{text-decoration:underline}
table.ck{width:100%;border-collapse:collapse;margin:8px 0 12px;font-size:14px}table.ck th,table.ck td{border:1px solid var(--bd);padding:6px 8px;text-align:left;vertical-align:top}
section{background:var(--pn);border:1px solid var(--bd);border-radius:var(--radius);padding:16px 18px;margin:0 0 14px;scroll-margin-top:84px}
h2{font-size:17px;margin:0 0 8px}h3{font-size:13px;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin:16px 0 4px}
p{margin:0 0 10px}ul{margin:0 0 10px;padding-left:22px}li{margin:3px 0}
.caps{text-transform:uppercase;font-size:13.5px;letter-spacing:.01em}
.note{background:var(--pn2);border:1px solid var(--bd2);border-left:3px solid var(--hi);border-radius:8px;padding:10px 12px;margin:0 0 16px}
.mu{color:var(--mu)}
footer{max-width:860px;margin:0 auto;padding:12px 20px 28px;color:var(--mu);font-size:12px;text-align:center;border-top:1px solid var(--bd)}
@media(max-width:700px){header{padding:12px 14px}.wrap{padding:14px 12px 32px}.title{font-size:22px}
 nav.toc ol{columns:1}section{padding:14px}nav.site a{padding:5px 10px;font-size:12.5px}}
"""

def _page(slug, title, desc, toc, sections, intro):
    nav = "".join(f'<a href="{h}"{" class=on" if h == "/" + slug else ""}>{t}</a>' for h, t in
                  (("/#wire", "← Dashboard"), ("/scoring", "How we score"), ("/sources", "Sources"), ("/newsletter", "Newsletter"),
                   ("/privacy", "Privacy"), ("/tos", "Terms")))
    toc_html = "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
            sitenav.head_html(slug) +
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico?v=3" sizes="any">'
            f'<style>{CSS}</style></head><body><a class="skip" href="#main">Skip to content</a>'
            + sitenav.site_top(slug) +
            f'<main class="wrap" id="main"><h2 class="title">{html.escape(title)}</h2>'
            f'<p class="upd">Effective date: {EFFECTIVE} · Last updated: {UPDATED.get(slug, EFFECTIVE)}</p>{intro}'
            f'<nav class="toc" aria-label="Contents"><b>Contents</b><ol>{toc_html}</ol></nav>{sections}</main>'
            '<footer>Research-only data · blackout.network · <a href="/#wire">Dashboard</a> · <a href="/scoring">How we score</a> · '
            '<a href="/sources">Sources</a> · <a href="/newsletter">Newsletter</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a>'
            '<br>BLACKOUT.NETWORK · PO Box 1228, Lake Mary, FL 32746</footer>'
            '</body></html>')

def _build(slug, title, desc, intro, parts):
    toc = [(a, t) for a, t, _ in parts]
    secs = "".join(f'<section id="{a}"><h2>{i}. {html.escape(t)}</h2>{body}</section>' for i, (a, t, body) in enumerate(parts, 1))
    return _page(slug, title, desc, toc, secs, intro)

# ------------------------------------------------------------------ Privacy Policy
# Compliance rewrite (review/compliance/2026-11-01_privacy-ga4.md), generated for seo/batch-1: Google Analytics 4 with consent (#analytics)
PRIVACY_PARTS = [
("scope", 'Who we are and what this policy covers', """
<p>blackout.network (the "Site") is published by <b>BLACKOUT.NETWORK</b>, an independent publisher based in Florida, USA. BLACKOUT.NETWORK is the data controller for the personal information described in this policy. Contact: <b><a href="mailto:hello@blackout.network">hello@blackout.network</a></b>, or by post: BLACKOUT.NETWORK, PO Box 1228, Lake Mary, FL 32746. We haven't appointed a data protection officer; privacy questions go to the same address.</p>
<p>This Privacy Policy explains what information the Site displays, what we collect when you visit or use it, how that information is used and shared, and the choices you have ("BLACKOUT.NETWORK," "we," "us," or "our"). It applies to the Site at blackout.network and its pages, its email newsletter, and any related features that link to this policy.</p>
<p>By using the Site you acknowledge this Privacy Policy. Your use of the Site is also governed by our <a href="/tos">Terms of Service</a>. If you do not agree, please do not use the Site.</p>"""),
("glance", 'Summary', """
<ul>
<li>The Site has no user accounts and shows no advertising.</li>
<li>We use Google Analytics 4 to see which pages people read and how the Site performs. It sets first-party cookies and runs with Google's advertising features and Google Signals turned off. In the EEA, the UK and Switzerland it stays off unless you choose <b>Accept analytics</b> in our cookie banner; you can change your mind any time with <b>Cookie settings</b> in the footer. Everywhere else it's on by default and you can turn it off with one click on <a href="/privacy-choices">Your Privacy Choices</a>, and we treat a Global Privacy Control or Do Not Track signal as "off". See <a href="#analytics">Google Analytics</a> and our <a href="/cookies">Cookie Policy</a>.</li>
<li>Visitors never sign in with Google. The only Google account connected to the Site is our own @BlkoutNtw YouTube channel; see <a href="#youtube">YouTube and Google user data</a>.</li>
<li>We do not sell personal information, and we do not share it for cross-context behavioral advertising.</li>
<li>Most of what you see is publicly available information collected from third-party sources.</li>
<li>We collect personal information only when you choose to provide it (a newsletter email address, for example), plus the limited technical data needed to run, secure, measure and improve the Site.</li>
</ul>"""),
("shown", 'Information shown on the Site', """
<p>The Site aggregates, scores and displays information that is publicly available from third parties, including:</p>
<ul>
<li>Public health and outbreak reporting, such as ProMED and the World Health Organization (WHO);</li>
<li>Geophysical and hazard data, such as the U.S. Geological Survey (USGS), EMSC, GEOFON, INGV and GDACS;</li>
<li>Weather and space-weather data, such as NOAA and the National Weather Service, and MeteoAlarm;</li>
<li>Cybersecurity and infrastructure data, such as CISA, and internet-connectivity data, such as IODA;</li>
<li>News and RSS feeds, and posts from public Telegram, Discord and Mastodon channels and similar public sources;</li>
<li>Publicly broadcast aviation data (for example, aircraft position and registration data).</li>
</ul>
<p>This content belongs to its respective owners and is shown for informational purposes. It may occasionally include names or statements of public figures, organizations or public accounts as they appear in the original public source. We do not use this content to build profiles of private individuals. If you believe content on the Site concerns you and should be removed or corrected, contact us using the details below.</p>"""),
("collect", 'Information we collect from visitors', """
<h3>Server, hosting and network logs</h3>
<p>Like virtually every website, the Site is served through infrastructure providers (currently Render for hosting and Cloudflare for content delivery and security). When your browser requests a page, these providers automatically process technical information such as your IP address, browser user agent, the page or resource requested, the referring page, and the date and time of the request, and may keep it in their logs under their own policies. Our own application does not write per-request access logs containing IP addresses.</p>
<h3>Aggregate usage counts (our public stats page)</h3>
<p>Our own server keeps aggregate, daily counts of page views per page (including individual story pages), requests per section of the Site, response status (error) rates, and an approximate count of unique visitors. A page view is counted only when a browser asks for a web page. A unique visitor is counted only when the page's own script sends our server a small, cookie-free signal that it was shown (it carries only the page address), so automated checkers that never run the page aren't counted. Unique visitors are estimated with a keyed hash of the connecting address, the browser's user-agent string and the date; the key is random, changes every day, is held only in server memory and is discarded at the end of the day, so the hash cannot be linked across days or reversed. We do not store IP addresses, user agents, cookies or any per-visitor records for these counts. We also count, as totals only, the site name of the page that linked to us (for example google.com, never the full address), campaign tags in our own links (utm_source), and, when our network provider (Cloudflare) supplies it, the visitor's country code; we never look up locations from IP addresses ourselves. Known bots and crawlers are excluded, and so is our own staff and automated test traffic. Browsers that send a Do Not Track (DNT) or Global Privacy Control (GPC) signal are not included in these counts at all, and their pages don't send the signal.</p>
<p>These first-party counts are separate from Google Analytics, which is described in section 5.</p>
<p>A summary of these totals, together with the public follower and view counts of our YouTube and X accounts, is published for anyone at <a href="/stats">blackout.network/stats</a>. Any number under 5 is hidden or shown as "&lt;5" so that no individual visit can be singled out.</p>
<h3>Newsletter</h3>
<p>If you sign up for the newsletter, we collect and store your email address; your chosen frequency and categories; the dates and times you signed up, confirmed, changed settings or unsubscribed; where on the Site you signed up; a hashed (not plain-text) form of the IP address used to sign up, kept as a consent record and to prevent abuse; a record of which issues and items were sent to you and whether delivery succeeded; the two-letter country our network provider (Cloudflare) reports for your signup request, used only to tell whether we need your consent before measuring opens and clicks; your open and click measurement choice and when you made it; whether our emails were opened and which links were clicked, where that measurement is on (see <a href="#email-tracking">Open and click measurement</a>); and, if you choose to give one, your reason for unsubscribing. Signup uses double opt-in: you are not subscribed until you click the confirmation link we email you. Every newsletter includes an unsubscribe link, and you can also unsubscribe by contacting us. Your email address is never sent to Google Analytics.</p>
<p>Optional location for local news. If you choose to give an area (a US ZIP code, a city or a country) when you sign up or on your preferences page, we store only the place name you chose (for example "Sanford, FL 32771") and a rough centre point for it, rounded to about 10 km. We look it up on our own server from bundled public datasets (US Census ZIP centroids, GeoNames); it is never sent to a third party, and we never ask for or store a street address. It is used only to add a "Near you" section and local breaking alerts to your emails. You can change or remove it at any time from the preferences link in every email. Your email address, area and topic choices are never shown on any public page or shared; our public statistics show subscriber totals only.</p>
<p>Confirmation emails and newsletters are delivered through a third-party email delivery provider (such as Resend), which processes your email address and the message content on our behalf in order to send the email.</p>
<p id="email-tracking"><b>Open and click measurement.</b> Newsletters sent from BLACKOUT.NETWORK may route links through our email provider (Resend) so we can count which links are clicked, and may include a small image that tells us when an email is opened. We record this per email address, and use it only to see which stories are useful, to send less often or stop emailing inactive addresses, and to keep the list healthy. We never sell it or use it for advertising. If you're in the European Economic Area, the UK or Switzerland, we do this only if you said yes when you signed up or on your preferences page. Elsewhere it's on by default, and you can switch it off on your preferences page or with the link in any email. Many email apps load images automatically, so open counts are approximate. We delete individual open and click records after 12 months. Legal basis (EEA/UK/CH): consent.</p>
<p>Other ways to opt out: unsubscribing stops all measurement and deletes your individual open and click records, and turning off automatic image loading in your email app stops open measurement. Confirmation emails are never measured. Questions: <a href="mailto:hello@blackout.network">hello@blackout.network</a>.</p>
<h3>Alerts (push notifications)</h3>
<p>If you tap the bell and turn on alerts, your browser asks your permission and then gives us a push subscription: a web address at your browser's push service (for example Google, Apple, Mozilla or Microsoft) plus two public encryption keys. We store that subscription, the alert level and categories you chose, your browser family (for example "Chrome on Android"), the dates you turned alerts on or changed them, and a record of which alerts were sent to it, so nobody gets the same alert twice. We do not store your IP address, name or email for alerts. Alerts are encrypted and delivered through your browser's push service. You can turn alerts off at any time with the bell (Turn off alerts) or in your browser or phone settings; when you do, or when your browser tells us the subscription has ended, we delete it.</p>
<h3>Problem reports</h3>
<p>If you use the "Report a problem" feature, we receive what is shown in its preview: the category and description you enter, the page address (without any query string), the dashboard tab, the time, your browser's user agent, window size, language and time zone, the site build, the last scan time on screen and up to 10 recent script error messages from the page. We do not store your IP address; we keep only a daily-rotating, anonymous hash to limit spam. You receive a reference ID that is the only way to look up the report.</p>
<h3>Source suggestions</h3>
<p>If you suggest a source, we collect the source name, link, category and your reason, and, only if you provide it, your email address so we can follow up. Submitter email addresses are never shown publicly. A hashed form of your IP address is used to limit spam.</p>
<h3>Ratings and votes</h3>
<p>If you rate a threat or a source, your browser generates a random, anonymous voter ID (stored in your browser) that is sent with your rating so that each browser counts once. IP addresses are used only in memory for rate limiting and are not written to disk.</p>
<h3>Site search</h3>
<p>Search terms you enter are processed to return results. We may log them, without your IP address, for up to 30 days to measure and improve search. If Google Analytics is on for you, the search term is also recorded there as a site-search event, so please don't type personal details into the search box.</p>
<h3>Location and weather features</h3>
<p>The Site has no default location. If you choose a location, type a place name, or allow your browser to share your location for the weather and nearby-alert features, your choice is saved in your own browser. To look up a place or forecast, the place name or rounded coordinates are sent to our server, which queries third-party geocoding and weather services (such as Open-Meteo, OpenStreetMap Nominatim and NOAA/National Weather Service) on your behalf. We do not store these lookups on our server, and they are not sent to Google Analytics. Your browser will ask your permission before sharing your precise location, and you can decline.</p>
<h3>Tips</h3>
<p>The Site may link to a PayPal page for optional tips. We do not process payments or receive your payment card details; any payment is handled by PayPal under its own terms and privacy policy.</p>
<h3>Information you send us</h3>
<p>If you email us, we receive your email address and whatever you choose to include in your message.</p>"""),
("cookies", 'Cookies, analytics and browser storage', """
<p>We do not use advertising cookies. The Site uses:</p>
<ul>
<li><b>Preference storage (first-party, always on).</b> A small number of first-party cookies and your browser's local storage remember your choices and make features work: your selected language, saved weather location and units, anonymous voter ID, map, chart and view preferences, audio volume, your analytics choice and cookie-banner choice (<code>bn_consent</code>: the choice, its date and the policy version), and the reference IDs of problem reports you submitted. This information stays in your browser unless a feature sends it to our server as described above. If you pick a language other than English, a <code>googtrans</code> cookie tells Google's website translator which language to show, and the page text is sent to Google to be translated.</li>
<li><b>Staff cookie (first-party, functional, staff only).</b> Our own team opens the Site once with a special staff link, which sets a <code>bn_internal</code> cookie so their visits are left out of our visitor counts and are marked as internal in Google Analytics. It is never set for other visitors, holds only the value 1, and lasts 1 year or until it is cleared.</li>
<li><b>Google Analytics cookies (first-party, set by Google's script, only when analytics is on).</b> Full list: <a href="/cookies">Cookie Policy</a>.</li>
</ul>
<table class="ck"><thead><tr><th>Cookie</th><th>What it does</th><th>How long it lasts</th></tr></thead><tbody><tr><td><code>_ga</code></td><td>Holds a random ID so Google Analytics can tell one browser from another and count returning visits</td><td>Up to 13 months after your last visit</td></tr><tr><td><code>_ga_KND6CPBB1X</code></td><td>Keeps track of the current visit (session) for our Google Analytics property</td><td>Up to 13 months after your last visit</td></tr></tbody></table>
<p>You can clear cookies and site data at any time in your browser settings; some features will then reset to their defaults, and Google Analytics will treat your next visit as a new browser.</p>
<h3 id="analytics">Google Analytics</h3>
<p>We use Google Analytics 4, a web analytics service from Google, to understand which stories and tools people use, where visitors come from, and where the Site is slow or broken. It helps us decide what to cover and what to fix. We don't use it to identify anyone.</p>
<p><b>What it collects.</b> When analytics is on, Google's script records:</p>
<ul>
<li>the pages you view, including their address and title, and the page that sent you to us;</li>
<li>events on those pages, such as scrolling, clicks on links to other sites, file downloads (for example our printable maps), site searches, video plays, and whether a newsletter signup form was submitted (never the email address you typed);</li>
<li>device and browser information, such as device type, operating system, browser, screen size and language;</li>
<li>approximate location (country, region and city) that Google works out from your IP address when the data arrives;</li>
<li>the date and time of each visit and roughly how long it lasted.</li>
</ul>
<p><b>IP addresses.</b> Google Analytics 4 does not log or store IP addresses. Google uses the address briefly to estimate your general location and then discards it. We never receive your IP address from Google Analytics.</p>
<p><b>Who processes it.</b> Google acts as our processor (service provider) for this data, under Google's data processing terms. We have turned off the settings that let Google use our Analytics data for its own products and services. Google may process the data in the United States and other countries. You can read how Google handles data in the <a href="https://policies.google.com/privacy">Google Privacy Policy</a> and in <a href="https://policies.google.com/technologies/partner-sites">How Google uses information from sites or apps that use our services</a>.</p>
<p><b>No advertising features.</b> Google Signals, advertising features, ad personalization and links to Google advertising products are turned off for our property. We will update this policy before we turn any of them on.</p>
<p><b>How long it's kept.</b> We set Google Analytics to keep visit-level data for 2 months, the shortest setting Google offers. After that, only aggregate reports remain, such as total page views per day, and they can't be traced to a browser.</p>
<p><b>Your choice.</b></p>
<ul>
<li>In the European Economic Area, the United Kingdom and Switzerland, we ask first. A banner offers <b>Accept analytics</b> and <b>Reject</b>, with equal weight. Until you accept, Google Analytics doesn't load: no analytics cookies are set and no analytics data is sent to Google. We use the country our network provider (Cloudflare) reports for each request, without storing it. If no country is reported, we show the banner when your browser's time zone is in Europe, or when we can't tell where you are.</li>
<li>We record your choice in your own browser only (local storage <code>bn_consent</code>: the choice, the date and time, and the policy version), and we don't send it to our servers. We ask again after 6 months, or sooner if this policy or our Cookie Policy changes in a material way. To withdraw or change your choice, use <b>Cookie settings</b> in the footer of every page; rejecting after accepting turns Google Analytics off and deletes its cookies.</li>
<li>Outside those countries it's on by default. You can turn it off at any time on <a href="/privacy-choices">Your Privacy Choices</a>, linked in the footer of every page.</li>
<li>If your browser sends a Global Privacy Control or Do Not Track signal, we treat it as "off" and don't load Google Analytics.</li>
<li>You can also install Google's <a href="https://tools.google.com/dlpage/gaoptout">Google Analytics Opt-out Browser Add-on</a>, which blocks Google Analytics on every site.</li>
</ul>
<p>Turning analytics off doesn't change how the Site works.</p>"""),
("thirdparty", 'Third-party content and embedded services', """
<p>To show maps, imagery, video, audio and other media, and to measure site use, some pages load content directly from third-party servers. When that happens, your browser connects to those providers, which can see your IP address and browser information and may set their own cookies or keep their own logs. Depending on the page, these can include: Google Analytics (only when analytics is on; see section 5); map tile providers (such as OpenFreeMap, VersaTiles and NASA GIBS); weather radar (such as RainViewer and NOAA); YouTube (using its privacy-enhanced mode where available) and YouTube video thumbnails (i.ytimg.com), which load when a page lists videos; NASA solar imagery (such as SDO and SOHO); live radio streams from broadcasters (such as NPR, BBC, CBC, RFI, Al Jazeera, ABC, RNZ, Radio France and Deutschlandfunk); images hosted on Wikimedia Commons; and code libraries delivered by content-delivery networks (such as unpkg and jsDelivr).</p>
<p>We do not control these providers and are not responsible for their privacy practices. Their use of information is governed by their own privacy policies.</p>"""),
("youtube", 'YouTube and Google user data', """
<p>BLACKOUT.NETWORK runs a YouTube channel, @BlkoutNtw, and uses Google's YouTube API Services (the YouTube Data API v3 and the YouTube Analytics API) through a Google OAuth client to manage that channel. This section explains exactly what Google user data that connection accesses and how it is handled. (Google Analytics, described in section 5, is a separate service and doesn't use this connection.)</p>
<h3>Whose Google account is connected</h3>
<p>The only Google account ever connected to blackout.network is the Site's own @BlkoutNtw YouTube channel, which is owned and authorized by BLACKOUT.NETWORK. Visitors never sign in with Google, and the Site does not request, receive or store any visitor's Google or YouTube account data.</p>
<h3>Data accessed</h3>
<p>With the channel owner's permission (OAuth scopes <code>youtube</code>, <code>youtube.upload</code>, <code>youtube.force-ssl</code> and <code>yt-analytics.readonly</code>), blackout.network accesses the following data about its own @BlkoutNtw channel only:</p>
<ul>
<li>Channel information: channel title, description, channel and playlist IDs, and branding settings (such as banner, profile picture and watermark);</li>
<li>Video metadata: titles, descriptions, tags, categories, privacy status (public, unlisted or private), publish times and thumbnails;</li>
<li>Uploads: the video files we upload and their upload and processing status;</li>
<li>Captions: the caption tracks we upload for our own videos;</li>
<li>Playlists: the channel's playlists and the videos in them;</li>
<li>Comments: comments posted on the channel's own videos, including the commenter's public display name as YouTube shows it, so that we can read, reply to, pin and moderate them; and</li>
<li>Analytics (read-only): aggregate channel and video performance, such as views, watch time and subscriber counts.</li>
</ul>
<p>We use the <code>youtube.force-ssl</code> scope only to upload captions to our own videos and to post, pin and moderate comments on our own videos.</p>
<h3>How the data is used</h3>
<p>This data is used only to publish and manage BLACKOUT.NETWORK's own videos, playlists, captions, channel details and comments, and to read the channel's own performance. We do not use Google user data for advertising, we do not sell, rent or share it with anyone, we do not use it to build profiles of any person, and we do not use it to develop, improve or train artificial-intelligence or machine-learning models. No person reads this data except BLACKOUT.NETWORK's editors, for the purposes above.</p>
<h3>Storage and protection</h3>
<ul>
<li>The OAuth client credentials and the OAuth access and refresh tokens are kept in restricted-access environment variables on BLACKOUT.NETWORK's private, access-controlled operations server, which is separate from the public website. They are never placed in source code, in the code repository, or on any public page, and they are never sent to visitors' browsers.</li>
<li>All communication with Google and YouTube uses encrypted HTTPS (TLS) connections only.</li>
<li>No Google account password is ever requested, received or stored; access works only through Google's OAuth consent, which the channel owner can revoke at any time.</li>
</ul>
<h3>Retention and deletion</h3>
<ul>
<li>OAuth tokens are kept only while the channel owner's authorization is active. We check at least every 30 days that it is still valid. If access is revoked or the YouTube integration is discontinued, we delete the tokens and any stored YouTube API data within 7 days.</li>
<li>YouTube Analytics data is read on demand and is not stored by blackout.network.</li>
<li>Comments are read on demand to reply to and moderate them and are not copied into any blackout.network database.</li>
<li>Video metadata and uploads are our own published content; any copies we keep are only the working files we created for the channel.</li>
</ul>
<p><b>Revoking access and asking for deletion.</b> In addition to our own deletion process, the owner of the connected Google account can revoke blackout.network's access at any time on Google's security settings page: <a href="https://security.google.com/settings/security/permissions">https://security.google.com/settings/security/permissions</a>. To ask us to delete any data described in this section, email <a href="mailto:hello@blackout.network">hello@blackout.network</a>. We will complete the deletion within 7 calendar days. Deleting data held by BLACKOUT.NETWORK does not delete anything stored by YouTube; to remove data from YouTube itself, use YouTube or YouTube Studio.</p>
<h3>Google and YouTube policies</h3>
<ul>
<li>Our use of YouTube API Services is subject to the <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>, and Google's handling of data is described in the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>.</li>
<li>blackout.network's use and transfer of information received from Google APIs adheres to the <a href="https://developers.google.com/terms/api-services-user-data-policy">Google API Services User Data Policy</a>, including the Limited Use requirements.</li>
</ul>
<p>Questions about this section can be sent to <a href="mailto:hello@blackout.network">hello@blackout.network</a>.</p>"""),
("use", 'How we use information', """
<ul>
<li>To operate, maintain, secure and improve the Site and its features;</li>
<li>To send the newsletter you requested and related service messages (such as confirmation emails);</li>
<li>To review and respond to problem reports, source suggestions and messages;</li>
<li>To detect, prevent and respond to spam, abuse, fraud, security incidents and violations of our <a href="/tos">Terms of Service</a>;</li>
<li>To understand aggregate usage, measure which pages and features are used (including through Google Analytics, where it is on), and fix errors;</li>
<li>To comply with law and to establish, exercise or defend legal claims.</li>
</ul>
<h3 id="legal-bases">Why we're allowed to use your information</h3>
<table class="ck"><thead><tr><th>Purpose</th><th>Data</th><th>Legal basis (GDPR / UK GDPR)</th></tr></thead><tbody>
<tr><td>Google Analytics</td><td>Pages, events, device/browser, approximate location, <code>_ga</code> cookies</td><td><b>Consent</b> (Art. 6(1)(a)); in the EEA, UK and CH it's off until you accept. Elsewhere it's on by default, with an opt-out on <a href="/privacy-choices">Your Privacy Choices</a></td></tr>
<tr><td>Newsletter and breaking alerts by email</td><td>Email, preferences, optional area, consent record</td><td><b>Consent</b></td></tr>
<tr><td>Newsletter open and click measurement</td><td>Opened and clicked events per email, signup country, your measurement choice</td><td><b>Consent</b> in the EEA, UK and CH (off unless you say yes). Elsewhere on by default with an opt-out</td></tr>
<tr><td>Web push alerts</td><td>Push subscription, alert settings</td><td><b>Consent</b> (your browser permission)</td></tr>
<tr><td>Location and weather lookups</td><td>Place name or rounded coordinates</td><td><b>Consent</b> (you choose to share)</td></tr>
<tr><td>Running and securing the Site: hosting logs, anti-spam hashes, rate limits, aggregate counts</td><td>Technical data</td><td><b>Legitimate interests</b> (Art. 6(1)(f)) in keeping a free public-safety resource online, fast and safe from abuse</td></tr>
<tr><td>Problem reports, source suggestions, ratings, messages</td><td>What you send</td><td><b>Legitimate interests</b> in fixing and improving the Site and answering you</td></tr>
<tr><td>Honoring unsubscribes, legal requests, defending claims</td><td>Minimal records</td><td><b>Legal obligation</b> (Art. 6(1)(c)) and legitimate interests</td></tr>
<tr><td>YouTube channel management (section 7)</td><td>Our own channel's data</td><td>Not visitor data; it's processed with the channel owner's consent under Google's OAuth</td></tr>
</tbody></table>
<p>You can withdraw consent at any time; doing so doesn't affect processing that already happened. You can object to processing based on legitimate interests (see section 12).</p>"""),
("share", 'How we share information', """
<p>We share information only:</p>
<ul>
<li>With service providers that host, deliver, secure, measure or email for the Site (our hosting, content-delivery, analytics (Google Analytics) and email delivery providers), who process it on our behalf;</li>
<li>When we believe in good faith that disclosure is required by law, subpoena, court order or other legal process, or is necessary to protect the rights, property or safety of the Site, BLACKOUT.NETWORK, its users or the public;</li>
<li>In connection with a merger, sale, transfer or reorganization of the Site or its assets, in which case information may be transferred as part of that transaction subject to this policy;</li>
<li>In aggregated or de-identified form that does not reasonably identify you; or</li>
<li>With your consent or at your direction.</li>
</ul>
<p><b>We do not sell or share your personal information.</b> We do not sell personal information, and we do not share it for cross-context behavioral advertising (targeted ads based on your activity across other sites), as those terms are used in California and other U.S. state privacy laws. We have not done so in the past 12 months. We run Google Analytics with advertising features and Google Signals off, and we limit Google to acting as our processor. Even so, you can switch analytics off at any time on <a href="/privacy-choices">Your Privacy Choices</a>, and we honor Global Privacy Control signals automatically.</p>"""),
("retention", 'Data retention', """
<p>We keep personal information only as long as reasonably necessary for the purposes described in this policy, unless a longer period is required or permitted by law:</p>
<ul>
<li><b>Google Analytics:</b> visit-level data 2 months; cookies expire up to 13 months after your last visit; aggregate reports kept without identifiers.</li>
<li><b>Your cookie-banner choice</b> (EEA, UK and Switzerland): kept only in your own browser for 6 months, then we ask again. We keep no copy on our servers.</li>
<li><b>Newsletter:</b> while you're subscribed. After you unsubscribe we keep your email address and the unsubscribe record so we never email you again by mistake.</li>
<li><b>Newsletter open and click records:</b> 12 months, then deleted (totals only are kept); deleted straight away if you unsubscribe.</li>
<li><b>Push subscriptions:</b> until you turn alerts off or your browser ends the subscription; then deleted.</li>
<li><b>Search logs:</b> up to 30 days, no IP address.</li>
<li><b>Problem reports, source suggestions, messages:</b> as long as needed to handle them, then deleted or kept as anonymous records.</li>
<li><b>Anti-spam hashes and rate limits:</b> about a day.</li>
<li><b>Hosting and network logs:</b> per Render's and Cloudflare's own policies.</li>
<li><b>YouTube API data:</b> see section 7.</li>
</ul>"""),
("security", 'Security', """
<p>We use reasonable administrative, technical and physical measures designed to protect the information we hold, such as encrypted connections (HTTPS), hashing of IP addresses where we keep a record, and restricted access to stored data. No method of transmission over the internet or method of storage is completely secure, however, and we cannot guarantee absolute security.</p>"""),
("choices", 'Your choices and rights', """
<ul>
<li><b>Analytics:</b> turn Google Analytics off (or back on) on <a href="/privacy-choices">Your Privacy Choices</a> (linked in the footer), send a Global Privacy Control signal, or use Google's opt-out add-on. See section 5 and our <a href="/cookies">Cookie Policy</a>.</li>
<li><b>Newsletter:</b> unsubscribe at any time using the link in any newsletter, or change your settings using the link in your emails. Switch open and click measurement on or off on your preferences page, or use "Stop tracking my opens and clicks" in any measured email; see <a href="#email-tracking">Open and click measurement</a>.</li>
<li><b>Browser data:</b> clear cookies and site data in your browser, and decline or revoke location permission in your browser settings.</li>
<li><b>Your rights.</b> Wherever you live, you can ask us to see, correct or delete the personal information we hold about you. If you're in the EEA, the UK, Switzerland, Brazil, Canada or another place with similar laws, you also have the right to: get a copy in a portable format; restrict or object to how we use it (including anything based on our legitimate interests); and withdraw consent at any time.</li>
<li><b>How:</b> email <b><a href="mailto:hello@blackout.network">hello@blackout.network</a></b> with "Privacy request" in the subject. Tell us what you want and the email address involved, if any. We may ask you to confirm the request from that address. We answer within one month (EEA/UK), or within the time your law sets, and we don't charge for it.</li>
<li><b>Complaints:</b> we'd like the chance to fix things first, but you can complain to a data protection authority at any time: in the EU, the authority in your country (list at <a href="https://edpb.europa.eu">edpb.europa.eu</a>); in the UK, the Information Commissioner's Office (<a href="https://ico.org.uk">ico.org.uk</a>, 0303 123 1113); in Switzerland, the FDPIC; in Brazil, the ANPD; in Canada, the Office of the Privacy Commissioner.</li>
<li><b>California and other U.S. states:</b> see <a href="/privacy-choices">Your Privacy Choices</a>. We don't discriminate against anyone for using their rights.</li>
</ul>
<p>Depending on where you live, you may have additional rights under applicable law. We will respond to requests as required by the law that applies to you.</p>"""),
("children", "Children's privacy", """
<p><b>Children.</b> blackout.network is a general-audience news and safety site. It isn't directed to children under 13, and we don't knowingly collect personal information from them. If you think a child under 13 has given us personal information (for example, signed up for the newsletter), email <a href="mailto:hello@blackout.network">hello@blackout.network</a> and we'll delete it promptly.</p>"""),
("intl", 'Visitors outside the United States', """
<p>BLACKOUT.NETWORK is based in the United States, and so are the main providers that help us run the Site. If you visit from another country, your information is processed in the U.S. and wherever those providers operate. For personal information from the European Economic Area, the United Kingdom and Switzerland, each provider uses the following transfer mechanism:</p>
<ul>
<li><b>Google LLC</b> (Google Analytics) relies on the EU-U.S. Data Privacy Framework, the UK Extension and the Swiss-U.S. Data Privacy Framework.</li>
<li><b>Render Services, Inc.</b> (hosting) relies on the EU-U.S. Data Privacy Framework (and UK Extension / Swiss-U.S. DPF where applicable) and/or Standard Contractual Clauses.</li>
<li><b>Cloudflare, Inc.</b> (content delivery and security) relies on the EU-U.S. Data Privacy Framework (and UK Extension / Swiss-U.S. DPF where applicable) and/or Standard Contractual Clauses.</li>
<li><b>Resend</b> (Plus Five Five, Inc.; newsletter delivery) relies on Standard Contractual Clauses, including the UK Addendum for UK data and a Swiss adaptation for Swiss data, and on the EU-U.S. Data Privacy Framework and its UK Extension.</li>
</ul>
<p>You can check a provider's Data Privacy Framework certification at <a href="https://www.dataprivacyframework.gov">dataprivacyframework.gov</a>. To ask for details of these safeguards, email <a href="mailto:hello@blackout.network">hello@blackout.network</a>.</p>
<p><b>EEA, UK and Switzerland.</b> Google Analytics runs only if you accept it in our cookie banner (consent), and you can withdraw that consent any time with Cookie settings in the footer. We rely on consent for the newsletter, push alerts and location features, and on our legitimate interest in running and securing the Site for server logs, anti-spam hashes and aggregate counts (see <a href="#legal-bases">Why we're allowed to use your information</a>). Your rights, including the right to complain to a data protection authority, are in section 12.</p>"""),
("dnt", 'Do Not Track and Global Privacy Control', """
<p>The Site does not track visitors across third-party websites or use advertising trackers. When your browser sends a Do Not Track (DNT) or Global Privacy Control (GPC) signal, we leave your visits out of our own aggregate usage counts and we do not load Google Analytics. You can also turn analytics off on <a href="/privacy-choices">Your Privacy Choices</a>. For California residents, we treat GPC as a valid request to opt out of sale and sharing.</p>"""),
("advice", 'Informational use only; not professional or emergency advice', """
<p>The Site is provided for general informational and research purposes only. It is not medical, legal, financial, investment, safety or other professional advice, and it is not an official emergency alerting or warning service. In an emergency, call 911 (or your local emergency number) and follow instructions from official authorities. See our <a href="/tos">Terms of Service</a> for details.</p>"""),
("links", 'Third-party links', """
<p>The Site contains links to third-party websites and sources. We are not responsible for the content, accuracy or privacy practices of those websites. Visiting them is at your own risk and subject to their terms and policies.</p>"""),
("warranty", 'No warranties; limitation of liability', """
<p>The Site and all information on it are provided "as is" and "as available," without warranties of any kind, express or implied. To the maximum extent permitted by law, BLACKOUT.NETWORK will not be liable for any indirect, incidental, special, consequential, exemplary or punitive damages, or any loss of data, profits or goodwill, arising out of or relating to the Site or this Privacy Policy.</p>"""),
("law", 'Governing law', """
<p>This Privacy Policy is governed by the laws of the State of Florida, United States, without regard to its conflict-of-laws rules. Any dispute relating to it is subject to the exclusive jurisdiction and venue described in our <a href="/tos">Terms of Service</a> (the state and federal courts located in or for Seminole County, Florida).</p>"""),
("changes", 'Changes to this policy', """
<p>We may update this Privacy Policy from time to time. When we do, we will change the "Last updated" date at the top of this page and, where the changes are material, we may provide additional notice (for example, on the Site or in the newsletter). We will update this policy before we start any new kind of data collection, such as turning on Google advertising features. Your continued use of the Site after an update takes effect means you accept the updated policy.</p>"""),
("contact", 'Contact us', """
<p>Questions or requests about this Privacy Policy can be sent to BLACKOUT.NETWORK at <a href="mailto:hello@blackout.network">hello@blackout.network</a>, or by mail to BLACKOUT.NETWORK · PO Box 1228, Lake Mary, FL 32746.</p>"""),
]

# ------------------------------------------------------------------ Terms of Service
TOS_PARTS = [
("accept", "Acceptance of these Terms", """
<p>These Terms of Service (the "Terms") govern your access to and use of blackout.network, its pages, features and email newsletter
(together, the "Site"), operated by the operator of blackout.network ("we," "us," or "our"). By accessing or using the Site, you agree to
be bound by these Terms and by our <a href="/privacy">Privacy Policy</a>. If you do not agree, do not use the Site.</p>
<p>You must be at least 13 years old to use the Site. If you use the Site on behalf of an organization, you represent that you have
authority to bind it to these Terms.</p>"""),
("nature", "Informational and research use only", """
<p>The Site automatically collects, aggregates, translates, scores and displays information from publicly available third-party sources.
It is provided for general informational, educational and research purposes only. Threat levels, ranks, scores, summaries, translations,
maps, charts, correlations and similar outputs are automated estimates that may be incomplete, out of date or wrong.</p>"""),
("emergency", "Not an emergency alerting service", """
<div class="note"><b>The Site is not an official emergency, warning or alerting service, and it must not be relied on for life-safety
decisions.</b> In an emergency, call 911 (or your local emergency number). Always follow instructions from official authorities, such as
the National Weather Service, local emergency management, public health agencies and law enforcement.</div>
<p>Alerts, notifications and newsletters may be delayed, missed, duplicated or inaccurate, and the Site may be unavailable at any time.
You are solely responsible for your decisions and actions and for verifying information with official sources before acting on it.</p>"""),
("advice", "No professional advice", """
<p>Nothing on the Site is medical, health, legal, financial, investment, tax, security, safety or other professional advice, and no
professional or fiduciary relationship is created by your use of the Site. Consult a qualified professional for advice about your
situation. Financial and market information is provided for informational purposes only and is not a recommendation to buy, sell or
hold any security or asset.</p>"""),
("accuracy", "Accuracy and timeliness not guaranteed", """
<p>We do not guarantee that any information on the Site is accurate, complete, reliable, current or error-free. Source data can be
corrected, retracted or removed by its publisher; automated processing can misclassify, mistranslate or mis-score items; and correlations
shown on the Site do not imply causation. We may change, correct or remove any content at any time without notice.</p>"""),
("thirdparty", "Third-party content and links", """
<p>The Site displays and links to content, media, streams, maps and services owned and operated by third parties. We do not control, endorse
or assume responsibility for any third-party content, websites or services, and your use of them is at your own risk and subject to their
terms. Inclusion of a source does not mean that the source endorses the Site or that we endorse the source.</p>"""),
("ip", "Intellectual property and attribution", f"""
<p>Third-party content shown on the Site, including news, data, images, audio, video, logos and trademarks, belongs to its respective owners
and is attributed or linked to its source where practicable. Except for that third-party content, the Site's design, text, software,
scoring methods, compilations and branding are owned by the operator of blackout.network and protected by applicable intellectual property
laws. You may view and share links to the Site for personal, non-commercial use; you may not copy, reproduce, republish or commercially
exploit the Site or its content except as permitted by law or with our written permission.</p>
<p>If you believe content on the Site infringes your copyright or other rights, email {MAIL} with a description of the work, its location on
the Site, your contact information and a statement that you have a good-faith belief the use is not authorized. We will review and, where
appropriate, remove or disable access to it.</p>"""),
("youtube", "YouTube content", """
<p>The Site and its @BlkoutNtw YouTube channel use YouTube API Services. YouTube videos, embeds and channel content are subject to the
<a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>, and by viewing or interacting with YouTube content through the Site
or the channel you agree to be bound by them. Google's handling of data is described in the
<a href="https://policies.google.com/privacy">Google Privacy Policy</a>.</p>"""),
("use", "Acceptable use", """
<p>You agree not to, and not to attempt to:</p>
<ul>
<li>Use the Site for any unlawful, harmful, fraudulent or deceptive purpose, or in violation of any applicable law or third-party right;</li>
<li>Scrape, crawl, mirror or download the Site or its data by automated means in a way that places an unreasonable load on the Site, or
circumvent any rate limits or access controls;</li>
<li>Access or attempt to access administrative areas, non-public endpoints, accounts, systems or data you are not authorized to access;</li>
<li>Probe, scan or test the vulnerability of the Site, or interfere with or disrupt its operation, servers or networks, including by
introducing malware or by denial-of-service attacks;</li>
<li>Submit spam, false or misleading reports, abusive or harassing content, or content that infringes the rights of others through any
form, vote, report or suggestion feature;</li>
<li>Manipulate ratings, votes or other community features, or impersonate any person or entity;</li>
<li>Use the Site or its content to harass, stalk, surveil, threaten or harm any person; or</li>
<li>Present the Site's content as official warnings, or remove or obscure attributions or notices.</li>
</ul>
<p>We may block, rate-limit or remove access, content or submissions at our sole discretion to protect the Site and its users.</p>"""),
("submissions", "Your submissions", """
<p>If you submit a problem report, source suggestion, rating, message or other content, you represent that you have the right to submit it,
and you grant us a non-exclusive, worldwide, royalty-free, perpetual license to use, store, reproduce, modify and display it for operating
and improving the Site. We are under no obligation to use, keep or respond to any submission.</p>"""),
("newsletter", "Newsletter", """
<p>The newsletter is free and optional. You subscribe by confirming your email address (double opt-in), and you can unsubscribe at any time
using the link in any issue. Newsletter content is subject to the same disclaimers as the Site and is not an emergency alert. We may change
the newsletter's content, schedule or format, or discontinue it, at any time. We may decline or end any subscription, for example to prevent
abuse or protect deliverability. Our handling of subscriber information is described in our <a href="/privacy">Privacy Policy</a>.</p>"""),
("warranty", "Disclaimer of warranties", """
<p class="caps">The Site and all content, features, alerts, newsletters and services are provided "as is" and "as available," with all
faults and without warranties of any kind. To the maximum extent permitted by law, the operator of blackout.network disclaims all
warranties, express, implied or statutory, including any warranties of merchantability, fitness for a particular purpose, title,
non-infringement, accuracy, timeliness, availability, and any warranties arising from course of dealing or usage of trade. We do not
warrant that the Site will be uninterrupted, secure or error-free, that defects will be corrected, or that the Site or its servers are
free of viruses or other harmful components.</p>"""),
("liability", "Limitation of liability", """
<p class="caps">To the maximum extent permitted by law, in no event will the operator of blackout.network, or its affiliates, contributors,
agents or service providers, be liable for any indirect, incidental, special, consequential, exemplary or punitive damages, or for any
loss of profits, revenue, data, goodwill, or for personal injury, property damage or other loss arising from reliance on, or failure to
receive, any information, alert or notification, arising out of or relating to your access to or use of (or inability to use) the Site,
whether based on warranty, contract, tort (including negligence), strict liability or any other legal theory, even if advised of the
possibility of such damages.</p>
<p class="caps">To the maximum extent permitted by law, our total liability for all claims arising out of or relating to the Site or these
Terms will not exceed one hundred U.S. dollars (US $100).</p>
<p>Some jurisdictions do not allow the exclusion or limitation of certain damages, so some of the above may not apply to you; in that case
our liability is limited to the fullest extent permitted by law.</p>"""),
("indemnity", "Indemnification", """
<p>You agree to defend, indemnify and hold harmless the operator of blackout.network and its affiliates, contributors, agents and service
providers from and against any claims, liabilities, damages, losses, costs and expenses (including reasonable attorneys' fees) arising
out of or relating to your use or misuse of the Site, your submissions, your violation of these Terms, or your violation of any law or
the rights of any third party.</p>"""),
("changes", "Changes to the Site and these Terms", """
<p>We may modify, suspend or discontinue any part of the Site at any time without notice or liability. We may also update these Terms from
time to time; when we do, we will change the "Last updated" date at the top of this page. Your continued use of the Site after an update
takes effect means you accept the updated Terms.</p>"""),
("termination", "Termination", """
<p>We may suspend or terminate your access to all or part of the Site at any time, for any reason, without notice, including if we believe
you have violated these Terms. Sections that by their nature should survive termination (including intellectual property, disclaimers,
limitation of liability, indemnification and governing law) will survive.</p>"""),
("law", "Governing law and venue", """
<p>These Terms and any dispute arising out of or relating to them or the Site are governed by the laws of the State of Florida, United States,
without regard to its conflict-of-laws rules. You agree that any legal action or proceeding arising out of or relating to these Terms or
the Site will be brought exclusively in the state or federal courts located in or for Seminole County, Florida, and you consent to the
personal jurisdiction and venue of those courts. To the extent permitted by law, any claim must be brought within one (1) year after it
arises, and claims may be brought only on an individual basis and not as a plaintiff or class member in any class or representative
proceeding.</p>"""),
("misc", "Severability, waiver and entire agreement", """
<p>If any provision of these Terms is held invalid or unenforceable, it will be enforced to the maximum extent permissible and the remaining
provisions will remain in full force and effect. Our failure to enforce any right or provision is not a waiver of it. These Terms, together
with our <a href="/privacy">Privacy Policy</a>, are the entire agreement between you and us regarding the Site and supersede any prior
agreements on that subject. You may not assign these Terms; we may assign them without restriction. Headings are for convenience only.</p>"""),
("acknowledgments", "Acknowledgments", """
<p>The off-grid network pages (<a href="/mesh">network map</a>, <a href="/mesh/chat">network chat</a>, <a href="/mesh/guide">setup guide</a>) and the Push to Mesh
button work with LoRa radios running the open-source <a href="https://meshtastic.org/" target="_blank" rel="noopener">Meshtastic®</a> firmware and apps.
Meshtastic® is a registered trademark of Meshtastic LLC. Meshtastic software components are released under various licenses, see
<a href="https://github.com/meshtastic" target="_blank" rel="noopener">GitHub</a> for details. No warranty is provided - use at your own risk.
This site is not affiliated with or endorsed by the Meshtastic project.</p>
<p><b>Open-source software.</b> Network chat and Push to Mesh load an unmodified build of @meshtastic/core 2.6.7, @meshtastic/transport-web-bluetooth 0.1.5
and @meshtastic/transport-web-serial 0.2.5, licensed under the <a href="https://www.gnu.org/licenses/gpl-3.0.html" target="_blank" rel="noopener">GNU General Public License v3.0</a>,
with bundled MIT-licensed code (crc, Strongly Typed Events). Corresponding source: <a href="https://github.com/meshtastic/js" target="_blank" rel="noopener">github.com/meshtastic/js</a>
(the exact versions are on npm) and our build script, <a href="/api/mesh/build_lib.sh">build_lib.sh</a>. License notices: <a href="/api/mesh/LICENSES.txt">LICENSES.txt</a>.
Those components are not covered by the ownership and copying limits in section 7; their own licenses apply.</p>
<p><b>Data.</b> Public node positions on the network map come from <a href="https://meshmap.net/" target="_blank" rel="noopener">MeshMap.net</a>.
Map tiles: <a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a>,
data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>.</p>"""),
("contact", "Contact", f"""
<p>Questions about these Terms can be sent to the operator of blackout.network at {MAIL}, or by mail to BLACKOUT.NETWORK · PO Box 1228, Lake Mary, FL 32746.</p>"""),
]

PRIVACY_INTRO = ('<p class="lead">This policy describes how blackout.network handles information: what it shows, what it collects from '
                 'visitors, how it measures site use, how it handles YouTube and Google user data, and the choices you have.</p>')
TOS_INTRO = ('<p class="lead">Please read these Terms carefully. blackout.network is an informational research tool, not an emergency '
             'alerting service. <b>In an emergency, call 911.</b></p>')


# ------------------------------------------------------------------ Cookie Policy and Your Privacy Choices (seo/batch-1; Compliance global-legal-gap H and I)
UPDATED["cookies"] = UPDATED["privacy"]; UPDATED["privacy-choices"] = UPDATED["privacy"]
COOKIES_BODY = """
<p class="lead">This page lists every cookie and similar storage blackout.network uses, what each does and how long it lasts. It's part of our <a href="/privacy">Privacy Policy</a>.</p>
<section id="necessary"><h2>Strictly necessary and preferences (always on)</h2>
<p>These make features you choose work. They stay in your browser and aren't used for tracking.</p>
<div class="tw"><table class="ck"><thead><tr><th>Name</th><th>Type</th><th>Purpose</th><th>Duration</th></tr></thead><tbody>
<tr><td><code>bn_consent</code></td><td>Local storage</td><td>Records your cookie-banner choice (accept or reject), when you made it and which policy version you saw, so we don't ask on every page. It stays in your browser and isn't sent to us</td><td>6 months, then we ask again (sooner if the policy changes)</td></tr>
<tr><td><code>bn_internal</code></td><td>First-party cookie (functional, staff only)</td><td>Set only when a member of our team opens the Site with our staff link, so their own visits are left out of our visitor counts and are marked as internal traffic in Google Analytics. Holds only the value 1; never set for other visitors</td><td>1 year, or until cleared</td></tr>
<tr><td><code>bn_analytics</code></td><td>Local storage</td><td>Remembers that you turned analytics off on Your Privacy Choices</td><td>Until you clear it</td></tr>
<tr><td>Language, theme, weather location and units, map and chart views, audio volume</td><td>Local storage / first-party cookies</td><td>Remember your settings</td><td>Until you clear them</td></tr>
<tr><td><code>bn_lang</code>, <code>googtrans</code></td><td>Local storage and first-party cookies</td><td>Only if you pick a language other than English: remember it and tell Google's website translator which language to show. When you pick a language, the page loads Google's translation service, which receives the page text to translate</td><td>1 year (cookies); removed when you switch back to English. <code>bn_lang</code> in local storage stays until you clear it</td></tr>
<tr><td>Voter ID</td><td>Local storage</td><td>Counts each browser's rating once</td><td>Until you clear it</td></tr>
<tr><td>Report IDs</td><td>Local storage</td><td>Lets you look up problem reports you sent</td><td>Until you clear them</td></tr>
<tr><td>Push subscription</td><td>Browser push service</td><td>Delivers alerts you turned on</td><td>Until you turn alerts off</td></tr>
</tbody></table></div></section>
<section id="analytics"><h2>Analytics (only with your consent in the EEA, UK and Switzerland; on by default elsewhere, with an opt-out)</h2>
<div class="tw"><table class="ck"><thead><tr><th>Name</th><th>Provider</th><th>Purpose</th><th>Duration</th></tr></thead><tbody>
<tr><td><code>_ga</code></td><td>Google Analytics (first-party cookie)</td><td>Tells one browser from another to count visits</td><td>Up to 13 months after your last visit</td></tr>
<tr><td><code>_ga_KND6CPBB1X</code></td><td>Google Analytics (first-party cookie)</td><td>Keeps track of the current visit</td><td>Up to 13 months after your last visit</td></tr>
</tbody></table></div>
<p>We don't use advertising cookies. Google Signals and ad features are off. In the European Economic Area, the United Kingdom and Switzerland these cookies are set only after you choose <b>Accept analytics</b> in the cookie banner.</p></section>
<section id="embeds"><h2>Third-party embeds</h2>
<p>Some pages load content from other services (YouTube in privacy-enhanced mode, map tiles, radio streams). YouTube videos load only when you press play; those services may set their own cookies then. See <a href="/privacy#thirdparty">section 6 of the Privacy Policy</a>.</p></section>
<section id="choices"><h2 id="settings">Your choices</h2>
<p>Change your analytics choice any time with <b>Cookie settings</b> in the footer (<a href="/cookies#settings" data-bn-cookie-settings>open Cookie settings</a>), or on <a href="/privacy-choices">Your Privacy Choices</a>; both are linked in the footer of every page. A Global Privacy Control or Do Not Track signal turns analytics off automatically. You can also block or delete cookies in your browser, or install <a href="https://tools.google.com/dlpage/gaoptout">Google's opt-out add-on</a>.</p>
<p>Questions: <a href="mailto:hello@blackout.network">hello@blackout.network</a>.</p></section>"""

CHOICES_BODY = """
<section id="nosale"><h2>We don't sell or share your personal information</h2>
<p>BLACKOUT.NETWORK doesn't sell personal information and doesn't share it for cross-context behavioral advertising, as California and other state laws define those terms. We haven't in the past 12 months. We run no ads.</p></section>
<section id="analytics"><h2>Analytics</h2>
<div class="pc-row"><label class="pc-sw" for="pc_toggle"><input type="checkbox" id="pc_toggle" role="switch" checked disabled><span class="pc-track" aria-hidden="true"></span>
<span class="pc-lbl">Google Analytics: <b id="pc_state">checking…</b></span></label></div>
<p id="pc_note" class="pc-note" hidden></p>
<p>We use Google Analytics, with ad features and Google Signals off, to see which pages are useful. Turn it off here and we won't load it in this browser. In the EEA, the UK and Switzerland it's off until you accept it; you can also use <a href="/cookies#settings" data-bn-cookie-settings>Cookie settings</a>.</p>
<noscript><p class="pc-note">This switch needs JavaScript. With JavaScript off, Google Analytics can't load either.</p></noscript></section>
<section id="gpc"><h2>Global Privacy Control</h2>
<p>If your browser sends a GPC signal, we treat it as an opt-out of sale and sharing and switch analytics off automatically. No form needed.</p></section>
<section id="requests"><h2>Other requests</h2>
<p>To see, correct or delete your data, email <a href="mailto:hello@blackout.network">hello@blackout.network</a> with "Privacy request" in the subject. You can use an authorized agent. We'll answer within 45 days and won't treat you differently for asking. More in our <a href="/privacy#choices">Privacy Policy</a>.</p></section>"""

CHOICES_CSS = """
.pc-row{margin:4px 0 12px}.pc-sw{display:flex;align-items:center;gap:12px;cursor:pointer;min-height:44px}
.pc-sw input{position:absolute;opacity:0;width:1px;height:1px}
.pc-track{flex:0 0 auto;width:52px;height:30px;border-radius:15px;background:var(--bd2);position:relative;transition:background .15s}
.pc-track:after{content:"";position:absolute;top:3px;left:3px;width:24px;height:24px;border-radius:50%;background:#fff;transition:transform .15s}
.pc-sw input:checked+.pc-track{background:var(--hi)}.pc-sw input:checked+.pc-track:after{transform:translateX(22px)}
.pc-sw input:focus-visible+.pc-track{outline:2px solid var(--ac);outline-offset:2px}.pc-sw input:disabled+.pc-track{opacity:.55}
.pc-lbl{font-family:var(--bn-font-ui,Montserrat,system-ui,sans-serif);font-size:15px}
.pc-note{background:var(--pn2);border:1px solid var(--bd2);border-left:3px solid var(--hi);border-radius:8px;padding:10px 12px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
"""
CHOICES_JS = """<script>(function(){var t=document.getElementById('pc_toggle'),st=document.getElementById('pc_state'),nt=document.getElementById('pc_note');
function get(){try{return localStorage.getItem('bn_analytics')}catch(e){return null}}
function set(v){try{if(v)localStorage.setItem('bn_analytics',v);else localStorage.removeItem('bn_analytics')}catch(e){}}
var gpc=navigator.globalPrivacyControl===true,dnt=navigator.doNotTrack==='1'||window.doNotTrack==='1';
function draw(){var c=window.bnConsent?window.bnConsent():null,cr=c&&c.region==='consent',off=cr?!(c.record&&c.record.choice==='granted'):get()==='denied';
 if(gpc||dnt){t.checked=false;t.disabled=true;st.textContent='Off';nt.hidden=false;nt.textContent=gpc?"Your browser's Global Privacy Control signal is on, so analytics is off.":"Your browser's Do Not Track signal is on, so analytics is off.";return}
 t.disabled=false;t.checked=!off;st.textContent=off?'Off':'On';nt.hidden=!(off||cr);
 nt.textContent=cr?(off?"You're in the EEA, the UK or Switzerland (or we couldn't tell), so analytics stays off unless you turn it on here or choose Accept analytics in Cookie settings.":"You accepted analytics. Turn it off here or in Cookie settings at any time."):(off?"Analytics is off in this browser. We won't load Google Analytics here until you turn it back on.":'')}
t.addEventListener('change',function(){var v=t.checked?'granted':'denied';if(window.bnSetAnalytics)window.bnSetAnalytics(v);else set(v==='denied'?'denied':null);draw()});
draw()})();</script>"""

def _simple(slug, title, desc_slug, body, css="", js=""):
    nav = "".join(f'<a href="{h}"{" class=on" if h == "/" + slug else ""}>{t}</a>' for h, t in
                  (("/#wire", "← Dashboard"), ("/privacy", "Privacy"), ("/cookies", "Cookie Policy"), ("/privacy-choices", "Your Privacy Choices"), ("/tos", "Terms")))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
            sitenav.head_html(desc_slug) +
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico?v=3" sizes="any">'
            f'<style>{CSS}{css}</style></head><body><a class="skip" href="#main">Skip to content</a>'
            + sitenav.site_top(desc_slug) +
            f'<main class="wrap" id="main"><h2 class="title">{html.escape(title)}</h2>'
            f'<p class="upd">Last updated: {UPDATED.get(slug, EFFECTIVE)}</p><nav class="site" aria-label="Privacy pages" style="margin:0 0 14px">{nav}</nav>{body}</main>'
            '<footer>Research-only data · BLACKOUT.NETWORK · <a href="/#wire">Dashboard</a> · <a href="/scoring">How we score</a> · '
            '<a href="/sources">Sources</a> · <a href="/newsletter">Newsletter</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a>'
            '<br>BLACKOUT.NETWORK · PO Box 1228, Lake Mary, FL 32746</footer>' + js + '</body></html>')

_CACHE = {}
def _html(which):
    if which not in _CACHE:
        if which == "privacy":
            _CACHE[which] = _build("privacy", "Privacy Policy", "How blackout.network handles information: what it shows, what it collects "
                                   "from visitors, and your choices.", PRIVACY_INTRO, PRIVACY_PARTS).encode()
        else:
            _CACHE[which] = _build("tos", "Terms of Service", "Terms of Service for blackout.network, an informational research tool. "
                                   "Not an emergency alerting service.", TOS_INTRO, TOS_PARTS).encode()
    return _CACHE[which]

def handle_get(path, qs):
    p = path.rstrip("/")
    if p in ("/privacy", "/privacy-policy"): return 200, _html("privacy"), "text/html"
    if p in ("/tos", "/terms", "/terms-of-service"): return 200, _html("tos"), "text/html"
    if p in ("/cookies", "/cookie-policy"): return 200, _simple("cookies", "Cookie Policy", "cookies", COOKIES_BODY, CHOICES_CSS).encode(), "text/html"
    if p in ("/privacy-choices", "/do-not-sell"): return 200, _simple("privacy-choices", "Your Privacy Choices", "privacy-choices", CHOICES_BODY, CHOICES_CSS, CHOICES_JS).encode(), "text/html"
    return 404, {"error": "not found"}
