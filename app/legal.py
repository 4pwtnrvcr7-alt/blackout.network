"""Legal pages add-on (t270): GET /privacy (Privacy Policy) and GET /tos (Terms of Service; alias /terms).
t285: Privacy adds 'YouTube and Google user data' (Google OAuth consent screen / API Services User Data Policy, Limited Use);
Terms adds 'YouTube content'. Static, self-contained HTML (no scripts, no data reads), so both pages are served even while the public node warms up.
Styled like /scoring: shared /theme.css palette plus a small inline stylesheet. Never touches scanner.py, scoring,
push.py, jets.py, aviation_watch.py or config.json."""
import html

EFFECTIVE = "October 31, 2026"
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
section{background:var(--pn);border:1px solid var(--bd);border-radius:var(--radius);padding:16px 18px;margin:0 0 14px;scroll-margin-top:12px}
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
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}: blackout.network</title><meta name="description" content="{html.escape(desc)}">'
            f'<link rel="canonical" href="https://blackout.network/{slug}">'
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any">'
            f'<style>{CSS}</style></head><body><a class="skip" href="#main">Skip to content</a>'
            f'<header><h1>BLACKOUT.<b>NETWORK</b> · {html.escape(title)}<small>The world\'s threats, scored and sourced, before cable news catches up.</small></h1>'
            f'<nav class="site" aria-label="Site">{nav}</nav></header>'
            f'<main class="wrap" id="main"><h2 class="title">{html.escape(title)}</h2>'
            f'<p class="upd">Effective date: {EFFECTIVE} · Last updated: {EFFECTIVE}</p>{intro}'
            f'<nav class="toc" aria-label="Contents"><b>Contents</b><ol>{toc_html}</ol></nav>{sections}</main>'
            '<footer>Research-only data · blackout.network · <a href="/#wire">Dashboard</a> · <a href="/scoring">How we score</a> · '
            '<a href="/sources">Sources</a> · <a href="/newsletter">Newsletter</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></footer>'
            '</body></html>')

def _build(slug, title, desc, intro, parts):
    toc = [(a, t) for a, t, _ in parts]
    secs = "".join(f'<section id="{a}"><h2>{i}. {html.escape(t)}</h2>{body}</section>' for i, (a, t, body) in enumerate(parts, 1))
    return _page(slug, title, desc, toc, secs, intro)

# ------------------------------------------------------------------ Privacy Policy
PRIVACY_PARTS = [
("scope", "Who we are and what this policy covers", f"""
<p>blackout.network (the "Site") is operated by the operator of blackout.network ("we," "us," or "our"). This Privacy Policy explains what
information the Site displays, what information we collect when you visit or use it, how that information is used and shared, and the
choices you have. It applies to the Site at blackout.network and its pages, its email newsletter, and any related features that link to
this policy.</p>
<p>By using the Site you acknowledge this Privacy Policy. Your use of the Site is also governed by our <a href="/tos">Terms of Service</a>.
If you do not agree, please do not use the Site.</p>"""),
("glance", "Summary", """
<ul>
<li>The Site has <b>no user accounts</b>, shows <b>no advertising</b>, and uses <b>no advertising or third-party analytics trackers</b>.</li>
<li>Visitors <b>never sign in with Google</b>. The only Google account connected to the Site is its own @BlkoutNtw YouTube channel; see
<a href="#youtube">YouTube and Google user data</a>.</li>
<li>We <b>do not sell or rent</b> personal information, and we do not share it for cross-context behavioral advertising.</li>
<li>Most of what you see is publicly available information collected from third-party sources.</li>
<li>Personal information is collected only when you choose to provide it (for example, a newsletter email address) and in limited
technical form needed to run, secure and improve the Site (for example, standard server logs and anti-spam hashes).</li>
</ul>"""),
("shown", "Information shown on the Site", """
<p>The Site aggregates, scores and displays information that is publicly available from third parties, including:</p>
<ul>
<li>Public health and outbreak reporting, such as ProMED and the World Health Organization (WHO);</li>
<li>Geophysical and hazard data, such as the U.S. Geological Survey (USGS), EMSC, GEOFON, INGV and GDACS;</li>
<li>Weather and space-weather data, such as NOAA and the National Weather Service, and MeteoAlarm;</li>
<li>Cybersecurity and infrastructure data, such as CISA, and internet-connectivity data, such as IODA;</li>
<li>News and RSS feeds, and posts from public Telegram, Discord and Mastodon channels and similar public sources;</li>
<li>Publicly broadcast aviation data (for example, aircraft position and registration data).</li>
</ul>
<p>This content belongs to its respective owners and is shown for informational purposes. It may occasionally include names or
statements of public figures, organizations or public accounts as they appear in the original public source. We do not use this
content to build profiles of private individuals. If you believe content on the Site concerns you and should be removed or corrected,
contact us using the details below.</p>"""),
("collect", "Information we collect from visitors", """
<h3>Server, hosting and network logs</h3>
<p>Like virtually every website, the Site is served through infrastructure providers (currently Render for hosting and Cloudflare for
content delivery and security). When your browser requests a page, these providers automatically process technical information such
as your IP address, browser user agent, the page or resource requested, the referring page, and the date and time of the request, and
may keep it in their logs under their own policies. Our own application does not write per-request access logs containing IP
addresses.</p>
<h3>Aggregate usage counts</h3>
<p>We keep aggregate, daily counts of page views, requests per section of the Site, response status (error) rates, and an approximate
count of unique visitors. Unique visitors are estimated using a keyed hash that rotates daily and is held only in server memory; we do not
store IP addresses, user agents or per-visitor records for these counts.</p>
<h3>Newsletter</h3>
<p>If you sign up for the newsletter, we collect and store your email address; your chosen frequency and categories; the dates and times you
signed up, confirmed, changed settings or unsubscribed; where on the Site you signed up; a hashed (not plain-text) form of the IP address
used to sign up, kept as a consent record and to prevent abuse; a record of which issues and items were sent to you and whether delivery
succeeded; and, if you choose to give one, your reason for unsubscribing. Signup uses double opt-in: you are not subscribed until you click
the confirmation link we email you. Every newsletter includes an unsubscribe link, and you can also unsubscribe by contacting us.</p>
<p>Confirmation emails and newsletters are delivered through a third-party email delivery provider (such as Resend), which processes your
email address and the message content on our behalf in order to send the email.</p>
<h3>Problem reports</h3>
<p>If you use the "Report a problem" feature, we receive what is shown in its preview: the category and description you enter, the page
address (without any query string), the dashboard tab, the time, your browser's user agent, window size, language and time zone, the site
build, the last scan time on screen and up to 10 recent script error messages from the page. We do not store your IP address; we keep only
a daily-rotating, anonymous hash to limit spam. You receive a reference ID that is the only way to look up the report.</p>
<h3>Source suggestions</h3>
<p>If you suggest a source, we collect the source name, link, category and your reason, and, only if you provide it, your email address so
we can follow up. Submitter email addresses are never shown publicly. A hashed form of your IP address is used to limit spam.</p>
<h3>Ratings and votes</h3>
<p>If you rate a threat or a source, your browser generates a random, anonymous voter ID (stored in your browser) that is sent with your
rating so that each browser counts once. IP addresses are used only in memory for rate limiting and are not written to disk.</p>
<h3>Site search</h3>
<p>Search terms you enter are processed to return results and may be logged, without your IP address, to measure and improve search
performance.</p>
<h3>Location and weather features</h3>
<p>The Site has no default location. If you choose a location, type a place name, or allow your browser to share your location for the
weather and nearby-alert features, your choice is saved in your own browser. To look up a place or forecast, the place name or rounded
coordinates are sent to our server, which queries third-party geocoding and weather services (such as Open-Meteo, OpenStreetMap Nominatim
and NOAA/National Weather Service) on your behalf. We do not store these lookups on our server. Your browser will ask your permission
before sharing your precise location, and you can decline.</p>
<h3>Tips</h3>
<p>The Site may link to a PayPal page for optional tips. We do not process payments or receive your payment card details; any payment is
handled by PayPal under its own terms and privacy policy.</p>
<h3>Information you send us</h3>
<p>If you email us, we receive your email address and whatever you choose to include in your message.</p>"""),
("cookies", "Cookies and browser storage", """
<p>We do not use advertising cookies or third-party analytics cookies. The Site uses a small number of first-party cookies and your
browser's local storage only to remember your choices and make features work, for example: your selected language; your saved weather
location and units; your anonymous voter ID; map, chart and view preferences; audio volume; and the reference IDs of problem reports you
submitted. This information stays in your browser unless a feature sends it to our server as described above. You can clear cookies and
site data at any time in your browser settings; some features will then reset to their defaults.</p>"""),
("thirdparty", "Third-party content and embedded services", """
<p>To show maps, imagery, video, audio and other media, some pages load content directly from third-party servers. When that happens,
your browser connects to those providers, which can see your IP address and browser information and may set their own cookies or keep
their own logs. Depending on the page, these can include: map tile providers (such as OpenFreeMap, VersaTiles and NASA GIBS); weather
radar (such as RainViewer and NOAA); YouTube (using its privacy-enhanced mode where available); NASA solar imagery (such as SDO and SOHO);
live radio streams from broadcasters (such as NPR, BBC, CBC, RFI, Al Jazeera, ABC, RNZ, Radio France and Deutschlandfunk); images hosted
on Wikimedia Commons; and code libraries delivered by content-delivery networks (such as unpkg and jsDelivr).</p>
<p>We do not control these providers and are not responsible for their privacy practices. Their use of information is governed by their
own privacy policies.</p>"""),
("youtube", "YouTube and Google user data", f"""
<p>blackout.network runs a YouTube channel, <b>@BlkoutNtw</b>, and uses Google's YouTube API Services (the YouTube Data API v3 and the
YouTube Analytics API) through a Google OAuth client to manage that channel. This section explains exactly what Google user data that
connection accesses and how it is handled.</p>
<h3>Whose Google account is connected</h3>
<p>The only Google account ever connected to blackout.network is the Site's own @BlkoutNtw YouTube channel, which is owned and authorized by
the operator of blackout.network. <b>Visitors never sign in with Google</b>, and the Site does not request, receive or store any visitor's
Google or YouTube account data.</p>
<h3>Data accessed</h3>
<p>With the operator's permission (OAuth scopes <code>youtube</code>, <code>youtube.upload</code> and <code>yt-analytics.readonly</code>),
blackout.network accesses the following data about its own @BlkoutNtw channel only:</p>
<ul>
<li><b>Channel information:</b> channel title, description, channel and playlist IDs, and branding settings (such as banner, profile picture
and watermark);</li>
<li><b>Video metadata:</b> titles, descriptions, tags, categories, privacy status (public, unlisted or private), publish times and
thumbnails;</li>
<li><b>Uploads:</b> the video files we upload and their upload and processing status;</li>
<li><b>Playlists:</b> the channel's playlists and the videos in them;</li>
<li><b>Comments:</b> comments posted on the channel's own videos, including the commenter's public display name as YouTube shows it, so that
we can read, reply to and moderate them; and</li>
<li><b>Analytics (read-only):</b> aggregate channel and video performance, such as views, watch time and subscriber counts.</li>
</ul>
<h3>How the data is used</h3>
<p>This data is used <b>only</b> to publish and manage blackout.network's own videos, playlists, channel details and comments, and to read
the channel's own performance. We do not use Google user data for advertising, we do not sell, rent or share it with anyone, we do not use
it to build profiles of any person, and we do not use it to develop, improve or train artificial-intelligence or machine-learning models.
No person reads this data except the operator, for the purposes above.</p>
<h3>Storage and protection</h3>
<ul>
<li>The OAuth client credentials and the OAuth access and refresh tokens are kept in <b>restricted-access environment variables</b> on
blackout.network's private, access-controlled operations server, which is separate from the public website. They are never placed in
source code, in the code repository, or on any public page, and they are never sent to visitors' browsers.</li>
<li>All communication with Google and YouTube uses encrypted HTTPS (TLS) connections only.</li>
<li>No Google account password is ever requested, received or stored; access works only through Google's OAuth consent, which the channel
owner can revoke at any time.</li>
</ul>
<h3>Retention and deletion</h3>
<ul>
<li><b>OAuth tokens</b> are kept only until access is revoked or the YouTube integration is discontinued, and are deleted from our server
within 30 days after that.</li>
<li><b>YouTube Analytics data</b> is read on demand and is <b>not stored</b> by blackout.network.</li>
<li><b>Comments</b> are read on demand to reply to and moderate them and are not copied into any blackout.network database.</li>
<li><b>Video metadata and uploads</b> are our own published content; any copies we keep are only the working files we created for the
channel.</li>
</ul>
<p><b>To revoke access</b>, the owner of the connected Google account can remove blackout.network at any time at
<a href="https://myaccount.google.com/permissions">https://myaccount.google.com/permissions</a>. To ask us to delete any data described in
this section, email {MAIL}; we will complete deletion requests within 30 days.</p>
<h3>Google and YouTube policies</h3>
<ul>
<li>Our use of YouTube API Services is subject to the <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>, and Google's
handling of data is described in the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>.</li>
<li><b>blackout.network's use and transfer of information received from Google APIs adheres to the
<a href="https://developers.google.com/terms/api-services-user-data-policy">Google API Services User Data Policy</a>, including the
Limited Use requirements.</b></li>
</ul>
<p>Questions about this section can be sent to {MAIL}.</p>"""),
("use", "How we use information", """
<ul>
<li>To operate, maintain, secure and improve the Site and its features;</li>
<li>To send the newsletter you requested and related service messages (such as confirmation emails);</li>
<li>To review and respond to problem reports, source suggestions and messages;</li>
<li>To detect, prevent and respond to spam, abuse, fraud, security incidents and violations of our <a href="/tos">Terms of Service</a>;</li>
<li>To understand aggregate usage and fix errors;</li>
<li>To comply with law and to establish, exercise or defend legal claims.</li>
</ul>"""),
("share", "How we share information", """
<p>We do not sell or rent personal information, and we do not share it for advertising. We share information only:</p>
<ul>
<li>With service providers that host, deliver, secure or email for the Site (such as our hosting, content-delivery and email delivery
providers), who process it on our behalf;</li>
<li>When we believe in good faith that disclosure is required by law, subpoena, court order or other legal process, or is necessary to
protect the rights, property or safety of the Site, its operator, its users or the public;</li>
<li>In connection with a merger, sale, transfer or reorganization of the Site or its assets, in which case information may be transferred
as part of that transaction subject to this policy;</li>
<li>In aggregated or de-identified form that does not reasonably identify you; or</li>
<li>With your consent or at your direction.</li>
</ul>"""),
("retention", "Data retention", """
<p>We keep personal information only as long as reasonably necessary for the purposes described in this policy, unless a longer period is
required or permitted by law. Newsletter records are kept while you are subscribed; after you unsubscribe we may keep your email address
and unsubscribe record so that we honor your choice and can demonstrate compliance. Problem reports, source suggestions and messages are
kept as long as needed to handle them and maintain the Site. Anti-spam hashes and rate-limit records are short-lived. Logs held by our
infrastructure providers are retained according to their policies.</p>"""),
("security", "Security", """
<p>We use reasonable administrative, technical and physical measures designed to protect the information we hold, such as encrypted
connections (HTTPS), hashing of IP addresses where we keep a record, and restricted access to stored data. No method of transmission
over the internet or method of storage is completely secure, however, and we cannot guarantee absolute security.</p>"""),
("choices", "Your choices and rights", f"""
<ul>
<li><b>Newsletter:</b> unsubscribe at any time using the link in any newsletter, or change your settings using the link in your emails.</li>
<li><b>Browser data:</b> clear cookies and site data in your browser, and decline or revoke location permission in your browser settings.</li>
<li><b>Access, correction and deletion:</b> you may ask us to access, correct or delete personal information we hold about you (for example,
your newsletter record or a source suggestion you submitted) by emailing {MAIL}. We may need to verify your request, and we may keep
information where we are required or permitted by law to do so.</li>
</ul>
<p>Depending on where you live, you may have additional rights under applicable law. We will respond to requests as required by the law
that applies to you.</p>"""),
("children", "Children's privacy", f"""
<p>The Site is not directed to children under 13, and we do not knowingly collect personal information from children under 13. If you
believe a child under 13 has provided us personal information, contact us at {MAIL} and we will delete it.</p>"""),
("intl", "Visitors outside the United States", """
<p>The Site is operated from the United States. If you access it from elsewhere, you understand that your information will be processed
in the United States and other countries where our service providers operate, whose data protection laws may differ from those of
your country.</p>"""),
("dnt", "Do Not Track", """
<p>Because the Site does not track visitors across third-party websites or use advertising trackers, it does not change its behavior in
response to browser "Do Not Track" signals.</p>"""),
("advice", "Informational use only; not professional or emergency advice", """
<p>The Site is provided for general informational and research purposes only. It is not medical, legal, financial, investment, safety or
other professional advice, and it is not an official emergency alerting or warning service. <b>In an emergency, call 911 (or your local
emergency number)</b> and follow instructions from official authorities. See our <a href="/tos">Terms of Service</a> for details.</p>"""),
("links", "Third-party links", """
<p>The Site contains links to third-party websites and sources. We are not responsible for the content, accuracy or privacy practices of
those websites. Visiting them is at your own risk and subject to their terms and policies.</p>"""),
("warranty", "No warranties; limitation of liability", """
<p class="caps">The Site and all information on it are provided "as is" and "as available," without warranties of any kind, express or
implied. To the maximum extent permitted by law, the operator of blackout.network will not be liable for any indirect, incidental, special,
consequential, exemplary or punitive damages, or any loss of data, profits or goodwill, arising out of or relating to the Site or this
Privacy Policy.</p>
<p>The full disclaimers and limitations of liability in our <a href="/tos">Terms of Service</a> apply to this Privacy Policy.</p>"""),
("law", "Governing law", """
<p>This Privacy Policy is governed by the laws of the State of Florida, United States, without regard to its conflict-of-laws rules. Any
dispute relating to it is subject to the exclusive jurisdiction and venue described in our <a href="/tos#law">Terms of Service</a>
(the state and federal courts located in or for Seminole County, Florida).</p>"""),
("changes", "Changes to this policy", """
<p>We may update this Privacy Policy from time to time. When we do, we will change the "Last updated" date at the top of this page and,
where the changes are material, we may provide additional notice (for example, on the Site or in the newsletter). Your continued use of
the Site after an update takes effect means you accept the updated policy.</p>"""),
("contact", "Contact us", f"""
<p>Questions or requests about this Privacy Policy can be sent to the operator of blackout.network at {MAIL}.</p>"""),
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
("contact", "Contact", f"""
<p>Questions about these Terms can be sent to the operator of blackout.network at {MAIL}.</p>"""),
]

PRIVACY_INTRO = ('<p class="lead">This policy describes how blackout.network handles information: what it shows, what it collects from '
                 'visitors, how it handles YouTube and Google user data, and the choices you have.</p>')
TOS_INTRO = ('<p class="lead">Please read these Terms carefully. blackout.network is an informational research tool, not an emergency '
             'alerting service. <b>In an emergency, call 911.</b></p>')

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
    return 404, {"error": "not found"}
