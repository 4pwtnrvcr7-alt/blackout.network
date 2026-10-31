"""Shared catalog/config for the Radio tab (radio.py) and its recorder (radio_archive.py). Read-only research monitoring:
nothing here transmits, posts or logs in anywhere. Only HTTPS sources (the box egress blocks plain HTTP; we don't route around it)."""
import os, json, time
BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(BASE, "archive", "radio")          # rolling audio archive: <station>/<YYYYMMDD>/<HHMMSS>.mp3 (times UTC)
LIVE = os.path.join(BASE, "archive", "radio_live")        # short HLS windows for the SDR relays (deleted as they roll)
STATUS = os.path.join(BASE, "logs", "radio_archive_status.json")
PIDF = os.path.join(BASE, "logs", "radio_archive.pid")
KIWI_TLS = os.path.join(BASE, "radio_tools", "kiwi_tls.py")

# Retention: whichever limit hits first. Oldest files are deleted first.
RETAIN_DAYS = 7
RETAIN_BYTES = 5_000_000_000         # 5 GB total cap for archive/radio
MIN_FREE_BYTES = 15 * 1024 ** 3       # stop recording if the disk ever gets below 15 GB free
SEGMENT_S = 900                        # 15-minute archive files
ARCHIVE_KBPS = 16                      # mono MP3 re-encode for the archive (speech / HF audio): ~173 MB per stream per day

# Direct HTTPS audio streams (played by the browser straight from the source; status checked server-side).
# archive=True -> radio_archive.py also records it (re-encoded to 16 kbps mono).
DIRECT = [
    {"id": "noaa_orlando", "name": "NOAA Weather Radio KIH63 Orlando", "group": "NOAA Weather Radio (US)", "kind": "mp3", "featured": False,
     "url": "https://wxradio.org/FL-Orlando-KIH63", "freq": "162.475 MHz", "archive": True,
     "desc": "NWS Melbourne transmitter for the Orlando area: watches, warnings, forecasts.",
     "src": "WXRadio.org (noaaweatherradio.org volunteer relay)", "src_url": "https://wxradio.org/"},
    {"id": "noaa_daytona", "name": "NOAA Weather Radio KIH26 Daytona Beach", "group": "NOAA Weather Radio (US)", "kind": "mp3", "featured": False,
     "url": "https://wxradio.org/FL-DaytonaBeach-KIH26", "freq": "162.400 MHz", "archive": True,
     "desc": "NWS Melbourne transmitter for Volusia / coastal Central Florida.",
     "src": "WXRadio.org (noaaweatherradio.org volunteer relay)", "src_url": "https://wxradio.org/"},
    {"id": "sf_scanner", "name": "SomaFM SF Police Scanner", "group": "Scanner", "kind": "mp3",
     "url": "https://ice2.somafm.com/scanner-128-mp3", "freq": "", "archive": True,
     "desc": "San Francisco police/fire scanner audio mixed with ambient music (curated, may be delayed). Example scanner feed that plays inline.",
     "src": "SomaFM", "src_url": "https://somafm.com/scanner/"},
    {"id": "bbc_ws", "name": "BBC World Service", "group": "International broadcasters", "kind": "mp3",
     "url": "https://stream.live.vc.bbcmedia.co.uk/bbc_world_service", "freq": "also on shortwave", "archive": False,
     "desc": "Global news radio; also transcribed in Live Broadcasts.", "src": "BBC", "src_url": "https://www.bbc.co.uk/worldserviceradio"},
    {"id": "npr", "name": "NPR live news", "group": "International broadcasters", "kind": "mp3",
     "url": "https://npr-ice.streamguys1.com/live.mp3", "freq": "", "archive": False,
     "desc": "US national news stream; also transcribed in Live Broadcasts.", "src": "NPR", "src_url": "https://www.npr.org/"},
    {"id": "voa_le", "name": "VOA Learning English", "group": "International broadcasters", "kind": "hls",
     "url": "https://voa-ingest.akamaized.net/hls/live/2035234/160_342L/playlist.m3u8", "freq": "", "archive": False,
     "desc": "Voice of America live audio (US government international broadcaster).", "src": "Voice of America", "src_url": "https://www.voanews.com/"},
    {"id": "nhk_world", "name": "NHK World Radio Japan", "group": "International broadcasters", "kind": "hls",
     "url": "https://nhkworld-radio.nhkworld.jp/hls/live/nhkworld-radio-media2/index.m3u8", "freq": "", "archive": False,
     "desc": "Japan's international public broadcaster (English and other languages by schedule).", "src": "NHK World-Japan", "src_url": "https://www3.nhk.or.jp/nhkworld/"},
    {"id": "radio_farda", "name": "Radio Farda (RFE/RL Persian)", "group": "International broadcasters", "kind": "mp3",
     "url": "https://stream.radiojar.com/cp13r2cpn3quv", "freq": "", "archive": False,
     "desc": "US-funded Persian-language news for Iran (listed as the official stream on radio-browser.info).", "src": "RFE/RL via Radiojar", "src_url": "https://www.radiofarda.com/"},
]

# Public KiwiSDR receivers reachable over HTTPS (the operators publish them for public listening; we take at most
# 2 of their 8 slots, never the last free ones, identify as "blackout.network", and back off when told to).
KIWIS = [{"host": "hasenberg02.kiwisdr.ch", "label": "KiwiSDR Hasenberg 02, Switzerland (HB9HEH)"},
         {"host": "hasenberg03.kiwisdr.ch", "label": "KiwiSDR Hasenberg 03, Switzerland (HB9HEH)"},
         {"host": "hasenberg01.kiwisdr.ch", "label": "KiwiSDR Hasenberg 01, Switzerland (HB9HEH)"}]
KIWI_FREE_SLOTS_MIN = 3        # only connect if at least this many slots are free

# SDR relays recorded/relayed by radio_archive.py from a public KiwiSDR.
RELAYS = [
    {"id": "uvb76", "name": "UVB-76 “The Buzzer” (S28)", "group": "Number & military stations", "freq_khz": 4625, "mode": "usb",
     "desc": "Russian military channel marker: a buzz ~25×/min, occasionally interrupted by voice messages (callsign + number groups + codeword). "
             "Reception from Switzerland is strongest in the European evening/night; by day it can be faint or noise.",
     "src": "Priyom.org (station profile)", "src_url": "https://priyom.org/military-stations/russia/the-buzzer", "archive": True},
    {"id": "hfgcs", "name": "HFGCS 8992 kHz (USAF HF Global Communications)", "group": "Number & military stations", "freq_khz": 8992, "mode": "usb",
     "desc": "US Air Force HF network: Emergency Action Messages (EAMs) and “Skyking” broadcasts are sent in the clear. Mostly silent between messages. "
             "This slot switches to a Priyom-scheduled number-station transmission when one is due.",
     "src": "USAF HFGCS (public frequencies) / Priyom.org schedule", "src_url": "https://priyom.org/military-stations/united-states/hfgcs", "archive": True},
]

def twente(khz, mode="usb"):
    return f"http://websdr.ewi.utwente.nl:8901/?tune={khz}{mode}"

def read_status():
    try:
        with open(STATUS) as f: return json.load(f)
    except Exception: return {}
