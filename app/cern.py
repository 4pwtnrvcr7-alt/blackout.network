"""/cern: CERN and the Large Hadron Collider on BLACKOUT.NETWORK (t1333u, Nov 13 2026).

An interactive, sourced explainer: what CERN and the LHC are, how the machine works, how it was built, who pays, who runs it,
what it found, the popular theories about it (neutral, myth-vs-physics), live control-room displays and a labeled analysis.

Rules kept here:
  * Every fact carries a source link (SRC below). Numbers come from CERN's own pages and documents, Nobel, journals or courts.
  * Photos are rights-cleared (CC BY / CC BY-SA / public domain via Wikimedia Commons), resized and EXIF-stripped, credited
    in the caption and in the credits list. Drawings and the collision simulator are labeled illustrations.
  * Live data: CERN's public Vistar control-room display images (vistar-capture.s3.cern.ch, no login) are fetched by this
    server at most once per 60 s per display and only while someone is viewing, then served same-origin. CERN Open Data portal
    record counts (CC0 metadata) are cached for 6 h. Nothing needs a key; nothing behind a login is touched.
  * Maps: MapLibre GL JS + OpenFreeMap (same SRI pins as /crime and /mesh). No OSM tile servers. The ring outline is the
    OpenStreetMap "Large Hadron Collider" tunnel relation 9512017 (ODbL, credited).
Never touches scanner.py, scoring, push.py, jets.py, config.json, aviation_watch.py or blackout.db."""
import html, json, os, threading, time, urllib.request
from datetime import date, datetime, timezone
try:
    import sitenav
except Exception:
    sitenav = None

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "cern_static")
SITE = "https://blackout.network"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
UA = "BLACKOUT.NETWORK CERN explainer (+https://blackout.network/cern)"
FILES = {"app.js": "application/javascript", "app.css": "text/css", "ring.json": "application/json"}

# ------------------------------------------------------------------ sources
SRC = {
 "lhc": ("CERN: The Large Hadron Collider (facts, FAQ and costs)", "https://home.cern/science/accelerators/large-hadron-collider/"),
 "complex": ("CERN: The accelerator complex", "https://home.cern/science/accelerators/accelerator-complex"),
 "linac4": ("CERN: Linear accelerator 4", "https://home.cern/science/accelerators/linear-accelerator-4"),
 "psb": ("CERN: The Proton Synchrotron Booster", "https://home.cern/science/accelerators/proton-synchrotron-booster"),
 "ps": ("CERN: The Proton Synchrotron", "https://home.cern/science/accelerators/proton-synchrotron"),
 "sps": ("CERN: The Super Proton Synchrotron", "https://home.cern/science/accelerators/super-proton-synchrotron"),
 "lep": ("CERN: The Large Electron-Positron Collider", "https://home.cern/science/accelerators/large-electron-positron-collider"),
 "history": ("CERN: Our history", "https://home.cern/about/who-we-are/our-history"),
 "ls3": ("CERN: Long Shutdown 3, the road to HiLumi", "https://home.cern/science/long-shutdown-3/"),
 "ls3news": ("CERN, 29 June 2026: CERN bids farewell to the LHC and enters Long Shutdown 3", "https://home.cern/cern-bids-farewell-to-the-lhc-and-enters-long-shutdown-3/"),
 "finallaps": ("CERN, 7 March 2026: Final laps at the LHC", "https://home.cern/final-laps-lhc/"),
 "hilumi": ("CERN: HiLumi LHC", "https://home.cern/science/accelerators/hilumi-lhc/"),
 "fcc": ("CERN, 31 March 2025: report on the feasibility of a possible Future Circular Collider", "https://home.cern/cern-releases-report-feasibility-possible-future-circular-collider/"),
 "strategy": ("CERN, 22 May 2026: Council updates the European Strategy for Particle Physics", "https://home.cern/the-cern-council-decided-to-update-the-european-strategy-for-particle-physics/"),
 "council": ("CERN Council: Member and Associate States, Observers", "https://council.web.cern.ch/en/content/member-and-associate-states-observers"),
 "councilcomp": ("CERN Council: Composition as from January 2026", "https://council.web.cern.ch/en/content/council-composition-january-2026"),
 "stake": ("CERN: Our stakeholders", "https://home.cern/about/who-we-are/our-stakeholders/"),
 "budget": ("CERN Finance Department: 2026 Annual Contributions to CERN budget", "https://fap-dep.web.cern.ch/2026-annual-contributions-to-cern-budget/"),
 "chile": ("CERN, 2 April 2026: Chile becomes an Associate Member State", "https://home.cern/chile-becomes-associate-member-state-cern/"),
 "us531": ("CERN, 8 December 1997: U.S. to contribute $531 million to the LHC", "https://home.cern/us-to-contribute-531-million-to-cerns-large-hadron-collider-project/"),
 "aip97": ("AIP FYI, 1997: U.S. and CERN sign LHC agreement", "https://www.aip.org/fyi/1997/us-and-cern-sign-lhc-agreement"),
 "thomson": ("CERN: Mark Thomson, Director-General", "https://home.cern/about/who-we-are/our-people/mark-thomson/"),
 "atlasmgmt": ("ATLAS: Current management", "https://www.atlas.cern/Discover/Collaboration/Management"),
 "cmsmgmt": ("CMS: New management for 2026-2028", "https://cms.cern/news/cms-welcomes-new-management-2026-2028"),
 "alicemgmt": ("ALICE: ALICE welcomes its new management", "https://alice.cern/alice-welcomes-its-new-management/"),
 "lhcbmgmt": ("University of Warwick, 12 Feb 2026: Tim Gershon elected LHCb spokesperson", "https://warwick.ac.uk/news/pressreleases/warwick-professor-appointed_lhcb_spokesperson/"),
 "atlas": ("CERN: ATLAS", "https://home.cern/science/experiments/atlas"),
 "cms": ("CERN: CMS", "https://home.cern/science/experiments/cms"),
 "alice": ("CERN: ALICE", "https://home.cern/science/experiments/alice"),
 "lhcb": ("CERN: LHCb", "https://home.cern/science/experiments/lhcb"),
 "ams": ("CERN: AMS", "https://home.cern/science/experiments/ams"),
 "ad": ("CERN: The Antiproton Decelerator (and ELENA)", "https://home.cern/science/accelerators/antiproton-decelerator"),
 "ntof": ("CERN: n_TOF", "https://home.cern/science/experiments/n_tof"),
 "isolde": ("ISOLDE at CERN", "https://isolde.cern/"),
 "grid": ("CERN: The Worldwide LHC Computing Grid", "https://home.cern/science/computing/grid"),
 "opendata": ("CERN Open Data portal", "https://opendata.cern.ch/"),
 "higgs": ("CERN: The Higgs boson", "https://home.cern/science/physics/higgs-boson"),
 "nobel2013": ("NobelPrize.org: The Nobel Prize in Physics 2013", "https://www.nobelprize.org/prizes/physics/2013/summary/"),
 "nobel1984": ("NobelPrize.org: The Nobel Prize in Physics 1984", "https://www.nobelprize.org/prizes/physics/1984/summary/"),
 "qgp": ("CERN, 10 Feb 2000: New state of matter created at CERN", "https://home.cern/new-state-of-matter-created-at-cern/"),
 "athena": ("CERN, 2002: Thousands of cold anti-atoms produced at CERN", "https://home.cern/thousands-of-cold-anti-atoms-produced-at-cern/"),
 "alpha2010": ("CERN, 2010: Antimatter atoms produced and trapped at CERN", "https://home.cern/antimatter-atoms-produced-and-trapped-at-cern/"),
 "alphag": ("CERN, 2023: ALPHA observes the influence of gravity on antimatter", "https://home.cern/alpha-experiment-at-cern-observes-the-influence-of-gravity-on-antimatter/"),
 "alphagnature": ("Nature 621, 716 (2023): Observation of the effect of gravity on the motion of antimatter", "https://www.nature.com/articles/s41586-023-06527-1"),
 "penta": ("CERN, 14 July 2015: LHCb reports observation of exotic pentaquark particles", "https://home.cern/cerns-lhcb-experiment-reports-observation-of-exotic-pentaquark-particles/"),
 "bsmumu": ("Nature 522, 68 (2015): Observation of the rare Bs to mu mu decay (CMS and LHCb)", "https://www.nature.com/articles/nature14474"),
 "wmass": ("CMS, 17 Sep 2024: best-precision W boson mass measurement at the LHC", "https://cms.cern/news/cms-delivers-best-precision-measurement-w-boson-mass-lhc"),
 "web": ("CERN: The birth of the Web", "https://home.cern/science/computing/the-birth-of-the-web/"),
 "weblicense": ("CERN: Licensing the Web", "https://home.cern/science/computing/the-birth-of-the-web/licensing-web/"),
 "pet": ("CERN Innovation and Technology Transfer: forty years since the first PET image at CERN", "https://itt.cern/forty-years-since-the-first-pet-image-at-cern/"),
 "hadron": ("Frontiers in Oncology (2016): Medical applications at CERN and the ENLIGHT network", "https://www.frontiersin.org/journals/oncology/articles/10.3389/fonc.2016.00009/full"),
 "medipix": ("CERN Innovation and Technology Transfer: first 3D colour X-ray of a human using CERN technology", "https://itt.cern/first-3d-colour-x-ray-of-a-human-using-cern-technology/"),
 "incident": ("CERN, 16 Oct 2008: CERN releases analysis of LHC incident", "https://home.cern/cern-releases-analysis-of-lhc-incident/"),
 "magnet53": ("CERN, 30 April 2009: Final LHC magnet goes underground", "https://home.cern/final-lhc-magnet-goes-underground/"),
 "lsag": ("LHC Safety Assessment Group: Review of the Safety of LHC Collisions (2008)", "https://arxiv.org/abs/0806.3414"),
 "gm": ("Giddings and Mangano (2008): Astrophysical implications of hypothetical stable TeV-scale black holes", "https://arxiv.org/abs/0806.3381"),
 "safety": ("CERN, 2008: CERN reiterates safety of LHC on eve of first beam", "https://home.cern/cern-reiterates-safety-of-lhc-on-eve-of-first-beam/"),
 "sancho": ("U.S. Court of Appeals, 9th Circuit: Sancho v. U.S. Department of Energy, memorandum filed 24 Aug 2010", "https://cases.justia.com/federal/appellate-courts/ca9/08-17389/08-17389-2011-04-18.pdf"),
 "shiva": ("CERN Bulletin, June 2004: Lord Shiva statue unveiled", "https://repository.cern/records/k7ee7-r3334"),
 "geneve": ("Fritjof Capra, June 2004: Shiva's cosmic dance at CERN", "https://www.fritjofcapra.net/shivas-cosmic-dance-at-cern/"),
 "sacrifice": ("The Guardian, 18 Aug 2016: fake human sacrifice filmed at CERN", "https://www.theguardian.com/science/2016/aug/18/fake-human-sacrifice-filmed-at-cern-with-pranking-scientists-suspected"),
 "sacrificedw": ("DW, 2016: CERN looks into mock human sacrifice video", "https://www.dw.com/en/cern-looks-into-mock-human-sacrifice-video/a-19485174"),
 "register": ("The Register, 6 Nov 2009: 'Something may come through' dimensional 'doors' at LHC", "https://www.theregister.com/offbeat/2009/11/06/something-may-come-through-dimensional-doors-at-lhc/1130203"),
 "mandela": ("Prasad and Bainbridge, Psychological Science (2022): The Visual Mandela Effect", "https://doi.org/10.1177/09567976221108944"),
 "leadstories": ("Lead Stories, July 2022: no evidence the LHC restart opened portals or caused the Mandela effect", "https://leadstories.com/hoax-alert/2022/07/fact-check-no-evidence-restart-of-cern-collider-opened-portals-or-produced-mandela-effect-5d-timeline-shifts.html"),
 "vistar": ("CERN accelerator operations: Vistars (public live displays)", "https://op-webtools.web.cern.ch/vistar/"),
 "youtube": ("CERN on YouTube", "https://www.youtube.com/@CERN"),
 "power": ("CERN: Powering CERN", "https://home.cern/science/engineering/powering-cern"),
 "osmrel": ("OpenStreetMap: Large Hadron Collider tunnel (relation 9512017)", "https://www.openstreetmap.org/relation/9512017"),
}
def s(key, label=None):
    t, u = SRC[key]
    return f'<a class="cx-src" href="{E(u)}" target="_blank" rel="noopener">{E(label or t)}</a>'
def srcs(*keys):
    return '<p class="cx-cite"><span>Sources:</span> ' + " · ".join(s(k) for k in keys) + "</p>"

# ------------------------------------------------------------------ images (all rights-cleared, credited)
IMG = {
 "lhc-tunnel-2009.jpg": ("The LHC tunnel in sector 3-4, lined with blue superconducting magnet cryostats.", "LHC tunnel, sector 3-4, October 2009", "Maximilien Brice / CERN", "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/", "https://commons.wikimedia.org/wiki/File:Views_of_the_LHC_tunnel_sector_3-4,_tirage_2.jpg"),
 "lhc-tunnel-2004.jpg": ("The empty 27 km tunnel during LHC construction, with service pipes and a transport vehicle.", "The tunnel during LHC construction, October 2004 (archive)", "Juhanson", "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/", "https://commons.wikimedia.org/wiki/File:Inside_the_CERN_LHC_tunnel.jpg"),
 "lhc-tunnel-point5-2006.jpg": ("Magnets being installed in the LHC tunnel near Point 5.", "Installing magnets near Point 5 (CMS), January 2006 (archive)", "Muriel", "CC BY-SA 2.0", "https://creativecommons.org/licenses/by-sa/2.0/", "https://commons.wikimedia.org/wiki/File:LHC_tunnel_near_point_5.jpg"),
 "hl-lhc-tunnel-2025.jpg": ("A worker in a hard hat walks away from the camera down a new HiLumi LHC tunnel.", "A new HiLumi LHC tunnel, May 2025", "Mmma98", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/", "https://commons.wikimedia.org/wiki/File:Worker_walking_in_a_new_HL-LHC_tunnel_at_CERN.jpg"),
 "atlas-construction-2005.jpg": ("The ATLAS cavern during construction: eight huge toroid magnets surround the calorimeter. A person standing at the bottom shows the scale.", "ATLAS under construction, November 2005 (archive)", "Maximilien Brice / CERN", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/", "https://commons.wikimedia.org/wiki/File:Installing_the_ATLAS_Calorimeter.jpg"),
 "atlas-2007.jpg": ("A tall view inside the ATLAS cavern in 2007, between the detector's giant end-cap wheels.", "Inside the ATLAS cavern, February 2007 (archive)", "Sindre Skrede", "Public domain", "", "https://commons.wikimedia.org/wiki/File:Atlas_detector_CERN_feb2007.jpg"),
 "cms-construction-2008.jpg": ("Yellow scaffolding and cabling inside the CMS detector during assembly.", "CMS being assembled, January 2008 (archive)", "Thomas Guignard", "CC BY-SA 2.0", "https://creativecommons.org/licenses/by-sa/2.0/", "https://commons.wikimedia.org/wiki/File:CMS_(under_construction).jpg"),
 "cms-shaft-2008.jpg": ("The main access shaft above CMS, through which its 15 pre-built sections were lowered.", "The CMS access shaft, January 2008 (archive)", "Thomas Guignard", "CC BY-SA 2.0", "https://creativecommons.org/licenses/by-sa/2.0/", "https://commons.wikimedia.org/wiki/File:CMS_(main_access_well).jpg"),
 "magnet-factory.jpg": ("A magnet cold mass on tooling in CERN's magnet facility.", "CERN's LHC magnet facility, April 2008 (archive)", "Julian Herzog", "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/", "https://commons.wikimedia.org/wiki/File:CERN_LHC_Magnet_Factory2.jpg"),
 "lhc-dipole-2008.jpg": ("LHC dipole magnets lined up outdoors on concrete supports; the slight curve of each 15 m magnet is visible.", "LHC dipole magnets at CERN, May 2008 (archive)", "Muriel", "CC BY-SA 2.0", "https://creativecommons.org/licenses/by-sa/2.0/", "https://commons.wikimedia.org/wiki/File:Inside_of_an_LHC_dipole.jpg"),
 "lep-beam-pipe.jpg": ("A cut section of the LEP collider's aluminium beam pipe.", "A section of the LEP beam pipe (LEP ran 1989-2000), photographed 2016", "Geni", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/", "https://commons.wikimedia.org/wiki/File:LEP_Particle_beam_tube.JPG"),
 "elena-2024.jpg": ("The ELENA antiproton decelerator ring in CERN's antimatter factory, seen from above.", "ELENA in the antimatter factory, February 2024", "Unnerving duck", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/", "https://commons.wikimedia.org/wiki/File:CERN_ELENA.jpg"),
 "lhc-from-space-aster.jpg": ("Satellite image of farmland and towns between the Jura mountains and Lake Geneva, with a yellow circle marking the LHC ring underground and Geneva airport at lower right.", "The LHC ring outlined on a satellite image, 26 July 2012", "NASA/METI/AIST/Japan Space Systems and U.S./Japan ASTER Science Team", "Public domain", "", "https://commons.wikimedia.org/wiki/File:CERN_Collider,_France-Switzerland_(ASTER).jpg"),
}
DIMS = {}
def _dims(f):
    if f not in DIMS:
        try:
            with open(os.path.join(STATIC, "img", f), "rb") as fh: b = fh.read(65536)
            i = 2; w = h = 0
            while i < len(b) - 9:
                if b[i] != 0xFF: i += 1; continue
                m = b[i + 1]; ln = int.from_bytes(b[i + 2:i + 4], "big")
                if m in (0xC0, 0xC1, 0xC2): h = int.from_bytes(b[i + 5:i + 7], "big"); w = int.from_bytes(b[i + 7:i + 9], "big"); break
                i += 2 + ln
            DIMS[f] = (w or 1400, h or 933)
        except Exception: DIMS[f] = (1400, 933)
    return DIMS[f]
def credit(f):
    alt, cap, who, lic, lurl, page = IMG[f]
    l = f'<a href="{E(lurl)}" target="_blank" rel="noopener license">{E(lic)}</a>' if lurl else E(lic)
    return f'Photo: <a href="{E(page)}" target="_blank" rel="noopener">{E(who)}</a>, {l}, via Wikimedia Commons'
def fig(f, cls="", eager=False):
    alt, cap, *_ = IMG[f]; w, h = _dims(f)
    return (f'<figure class="cx-fig {cls}"><img src="/api/cern/img/{E(f)}" alt="{E(alt)}" width="{w}" height="{h}" '
            f'{"fetchpriority=high" if eager else "loading=lazy"} decoding="async"><figcaption><b>{E(cap)}.</b> {credit(f)}</figcaption></figure>')

# ------------------------------------------------------------------ data
FUND = [  # 2026 scale of contributions, CERN Finance Department (budget). (country, %, CHF, member since)
 ("Germany", 20.44134, 251868000, "1953"), ("United Kingdom", 15.07372, 185730850, "1953"), ("France", 12.96313, 159725200, "1953"),
 ("Italy", 9.63922, 118769600, "1953"), ("Spain", 7.01442, 86428200, "1961-68, again from 1983"), ("Netherlands", 5.06000, 62346750, "1953"),
 ("Switzerland", 3.77455, 46508200, "1953"), ("Poland", 3.31148, 40802400, "1991"), ("Belgium", 2.81659, 34704650, "1953"),
 ("Sweden", 2.52104, 31062950, "1953"), ("Norway", 2.50880, 30912200, "1953"), ("Israel", 2.33472, 28767250, "2014"),
 ("Austria", 2.11842, 26102050, "1959"), ("Denmark", 1.87138, 23058200, "1953"), ("Romania", 1.42906, 17608200, "2016"),
 ("Czech Republic", 1.30643, 16097200, "1993"), ("Finland", 1.23699, 15241500, "1991"), ("Portugal", 1.10311, 13592000, "1986"),
 ("Greece", 1.00703, 12408100, "1953"), ("Hungary", 0.75936, 9356450, "1992"), ("Slovak Republic", 0.52993, 6529500, "1993"),
 ("Bulgaria", 0.41917, 5164750, "1999"), ("Serbia", 0.31720, 3908350, "2019"), ("Slovenia", 0.27463, 3383800, "2025"),
 ("Estonia", 0.16829, 2073550, "2024"),
]
ASSOC = [  # 2026 associate member contributions in CHF (budget) + accession date (council)
 ("India", 18906850, "2017"), ("Brazil", 10953700, "2024"), ("Türkiye", 5441400, "2015"), ("Pakistan", 2009400, "2015"),
 ("Ireland", 1765400, "2025"), ("Chile", 1345100, "2026"), ("Cyprus (pre-stage to membership)", 1150850, ""), ("Latvia", 1070400, "2021"),
 ("Ukraine", 1021800, "2016"), ("Croatia", 1000000, "2019"), ("Lithuania", 1000000, "2018"),
]
OBSERVERS = [("United States", "since 1998"), ("Japan", "since 1995"), ("European Union", "since 1985"), ("UNESCO", "since 1955"),
             ("Russian Federation", "status suspended since March 2022"), ("JINR (Dubna)", "status suspended since March 2022")]
MEMBER_TOTAL = 1232149900; ASSOC_TOTAL = 44514050 + 1150850

STAGES = [  # accelerator chain (CERN accelerator complex page + machine pages)
 {"id": "linac4", "name": "Linac4", "energy": "160 MeV", "what": "A linear accelerator. It speeds up negative hydrogen ions (a proton with two electrons) and has been the proton source for the whole complex since 2020.", "fact": "Both electrons are stripped off on the way into the Booster, leaving bare protons.", "src": ["complex", "linac4"]},
 {"id": "psb", "name": "Proton Synchrotron Booster", "energy": "2 GeV", "what": "Four stacked small rings that take Linac4's beam to 2 GeV for the PS. It also feeds the ISOLDE nuclear-physics facility.", "fact": "The Booster is where hydrogen ions become a proton beam.", "src": ["complex", "psb"]},
 {"id": "ps", "name": "Proton Synchrotron", "energy": "26 GeV", "what": "CERN's oldest working synchrotron, 628 m around, with 277 room-temperature electromagnets. It began accelerating protons on 24 November 1959.", "fact": "Besides the LHC chain, it feeds the Antiproton Decelerator and the n_TOF neutron facility.", "src": ["ps", "complex"]},
 {"id": "sps", "name": "Super Proton Synchrotron", "energy": "450 GeV", "what": "A ring nearly 7 km around with 1317 room-temperature magnets. Switched on in 1976, it was run as a proton-antiproton collider when the W and Z bosons were discovered in 1983.", "fact": "Last stop before the LHC. It also feeds the North Area fixed-target experiments.", "src": ["sps", "nobel1984"]},
 {"id": "lhc", "name": "Large Hadron Collider", "energy": "6.8 TeV per beam", "what": "Two beams in separate pipes travel in opposite directions around the 26 659 m ring, 100 m underground, steered by 1232 superconducting dipole magnets cooled to 1.9 K (-271.3 °C).", "fact": "Filling each ring takes about 4 minutes 20 seconds; reaching full energy takes about 20 minutes. Collisions reach 13.6 TeV.", "src": ["lhc", "complex"]},
]
EXPTS = [  # (id, name, LHC point, place, size, people, focus, sources)
 {"id": "atlas", "name": "ATLAS", "pt": "Point 1", "place": "Meyrin, Switzerland", "size": "46 m long, 25 m high, 7000 tonnes: the largest-volume particle detector ever built", "people": "More than 5500 scientists, 245 institutes, 42 countries (CERN, March 2022)", "focus": "General-purpose: the Higgs boson, extra dimensions, dark-matter candidates.", "lead": "Spokesperson Stéphane Willocq (2025-2027)", "src": ["atlas", "atlasmgmt"]},
 {"id": "alice", "name": "ALICE", "pt": "Point 2", "place": "Saint-Genis-Pouilly, France", "size": "26 m long, 16 m high, 10 000 tonnes, 56 m underground", "people": "Almost 2000 scientists, 174 institutes, 40 countries (CERN, April 2022)", "focus": "Lead-ion collisions and the quark-gluon plasma, the state of matter of the very early universe.", "lead": "Spokesperson Kai Schweda (2026-2028)", "src": ["alice", "alicemgmt"]},
 {"id": "cms", "name": "CMS", "pt": "Point 5", "place": "Cessy, France", "size": "21 m long, 15 m wide and high, 14 000 tonnes, built around a 4-tesla solenoid", "people": "About 5500 people, 241 institutes, 54 countries (CERN, May 2022)", "focus": "General-purpose, with a different magnet design from ATLAS. Built at the surface in 15 sections and lowered underground.", "lead": "Spokesperson Anadi Canepa (2026-2028)", "src": ["cms", "cmsmgmt"]},
 {"id": "lhcb", "name": "LHCb", "pt": "Point 8", "place": "Ferney-Voltaire, France", "size": "21 m long, 10 m high, 5600 tonnes, a forward spectrometer", "people": "About 2000 members, 108 institutes, 27 countries (Feb 2026)", "focus": "Beauty-quark physics and the tiny differences between matter and antimatter.", "lead": "Spokesperson Tim Gershon (from July 2026)", "src": ["lhcb", "lhcbmgmt"]},
]
PTS = [  # LHC insertion points: OSM relation 9512017 member centres
 {"n": 1, "lat": 46.23568, "lon": 6.05547, "label": "Point 1 · ATLAS", "exp": "atlas"},
 {"n": 2, "lat": 46.25180, "lon": 6.02060, "label": "Point 2 · ALICE", "exp": "alice"},
 {"n": 3, "lat": 46.27979, "lon": 6.01234, "label": "Point 3 · beam cleaning", "exp": ""},
 {"n": 4, "lat": 46.30436, "lon": 6.03622, "label": "Point 4 · RF acceleration", "exp": ""},
 {"n": 5, "lat": 46.30977, "lon": 6.07743, "label": "Point 5 · CMS", "exp": "cms"},
 {"n": 6, "lat": 46.29380, "lon": 6.11131, "label": "Point 6 · beam dump", "exp": ""},
 {"n": 7, "lat": 46.26543, "lon": 6.11939, "label": "Point 7 · beam cleaning", "exp": ""},
 {"n": 8, "lat": 46.24138, "lon": 6.09619, "label": "Point 8 · LHCb", "exp": "lhcb"},
]
CITIES = [("sanford", "Sanford, FL", 28.8003, -81.2731), ("orlando", "Orlando, FL", 28.5384, -81.3789), ("nyc", "New York City", 40.7580, -73.9855),
          ("dc", "Washington, DC", 38.8899, -77.0091), ("chicago", "Chicago", 41.8789, -87.6359), ("la", "Los Angeles", 34.0522, -118.2437),
          ("london", "London", 51.5072, -0.1276), ("paris", "Paris", 48.8566, 2.3522), ("geneva", "Geneva (the real ring)", 46.27205, 6.06632)]

TIMELINE = [  # (year, title, text, image or "", source keys)
 ("1951", "A European lab is proposed", "A UNESCO meeting in Paris adopts the resolution that leads to a European Council for Nuclear Research, the source of the name CERN.", "", ["history"]),
 ("1953", "Twelve states sign the Convention", "The Convention says the lab will have no concern with military work and that its results will be published.", "", ["history"]),
 ("1954", "CERN begins", "The Organization is established; the foundation stone of the laboratory near Geneva is laid in 1955.", "", ["history"]),
 ("1959", "The Proton Synchrotron starts", "On 24 November 1959 the PS accelerates protons. It still runs today as part of the LHC chain.", "", ["ps"]),
 ("1976", "The SPS switches on", "The 7 km Super Proton Synchrotron becomes CERN's workhorse.", "", ["sps"]),
 ("1983", "W and Z bosons discovered", "Carriers of the weak force are found with the SPS run as a proton-antiproton collider. Carlo Rubbia and Simon van der Meer share the 1984 Nobel Prize.", "", ["sps", "nobel1984"]),
 ("1985", "Digging the 27 km tunnel", "Three tunnel-boring machines start in February 1985; the ring is complete three years later. It was Europe's largest civil-engineering project before the Channel Tunnel.", "lep-beam-pipe.jpg", ["lep"]),
 ("1989", "LEP collides electrons and positrons", "LEP's beam circulates on 14 July 1989. The same year, Tim Berners-Lee proposes the World Wide Web at CERN.", "", ["lep", "web"]),
 ("1993", "The Web is given away", "On 30 April 1993 CERN puts the Web software in the public domain.", "", ["weblicense"]),
 ("1994", "The LHC is approved", "In December 1994 the CERN Council votes to build the LHC in the LEP tunnel. The design report follows in October 1995.", "", ["lhc"]),
 ("1997", "The United States joins in", "The DOE and NSF agree to contribute $531 million in goods and services to the accelerator and to the ATLAS and CMS detectors.", "", ["us531"]),
 ("2000", "LEP shuts down", "LEP is switched off on 2 November 2000 to make way for LHC construction. Earlier that year CERN reports evidence for a quark-gluon plasma.", "", ["lep", "qgp"]),
 ("2004", "An empty tunnel", "The old LEP tunnel, emptied and refitted, waits for the LHC magnets. Two years earlier the ATHENA experiment made cold antihydrogen.", "lhc-tunnel-2004.jpg", ["lhc", "athena"]),
 ("2005", "Caverns fill up", "ATLAS's eight toroid magnets surround the space where the calorimeter will slide in.", "atlas-construction-2005.jpg", ["atlas"]),
 ("2006", "Magnets go underground", "Magnets are installed and connected around the ring, here near Point 5 in January 2006.", "lhc-tunnel-point5-2006.jpg", ["lhc"]),
 ("2008", "Start-up, then a setback", "Protons circulate on 10 September 2008. On 19 September a faulty electrical connection between two magnets causes an arc and a large helium release in sector 3-4. 53 magnets are removed for cleaning or repair.", "lhc-dipole-2008.jpg", ["lhc", "incident", "magnet53"]),
 ("2009", "Collisions begin", "The repaired LHC produces its initial collisions on 23 November 2009.", "lhc-tunnel-2009.jpg", ["lhc"]),
 ("2010", "7 TeV, lead ions and trapped antimatter", "7 TeV collisions on 30 March, lead ions on 8 November. The ALPHA experiment traps antihydrogen atoms.", "", ["lhc", "alpha2010"]),
 ("2012", "The Higgs boson", "On 4 July 2012 ATLAS and CMS announce the discovery of a new particle: the Higgs boson.", "", ["higgs"]),
 ("2013", "Nobel Prize", "François Englert and Peter Higgs share the Nobel Prize in Physics for the theory the LHC confirmed.", "", ["nobel2013"]),
 ("2015", "13 TeV and pentaquarks", "Run 2 starts at 13 TeV. LHCb reports pentaquarks; CMS and LHCb publish the rare Bs to two-muon decay.", "", ["lhc", "penta", "bsmumu"]),
 ("2020", "Linac4 takes over", "The new linear accelerator becomes the source of all CERN proton beams.", "", ["linac4"]),
 ("2022", "Run 3 at 13.6 TeV", "The upgraded LHC restarts at a record collision energy.", "", ["lhc"]),
 ("2023", "Antimatter falls down", "ALPHA shows antihydrogen responds to gravity like ordinary matter, within its precision.", "elena-2024.jpg", ["alphag", "alphagnature"]),
 ("2025", "Future Circular Collider study", "CERN publishes the feasibility study for a 91 km collider, with an initial stage estimated at 15 billion Swiss francs.", "", ["fcc"]),
 ("2026", "New leadership, last laps, LS3", "Mark Thomson becomes Director-General on 1 January. The Strategy update names FCC-ee the preferred next machine (22 May). The last LHC beams are dumped on 27 June and Long Shutdown 3 begins on 29 June.", "hl-lhc-tunnel-2025.jpg", ["thomson", "strategy", "ls3"]),
 ("2028", "Decision point", "The CERN Council aims to decide on FCC-ee by 2028. The rest of the accelerator complex restarts gradually from mid-2028.", "", ["strategy", "ls3"]),
 ("2030", "HiLumi LHC", "The upgraded collider is scheduled to start, aiming for 10 times the original design's integrated luminosity.", "", ["hilumi", "ls3news"]),
 ("2041", "End of the LHC era", "The 2026 Strategy text puts the end of the LHC's operational lifetime in 2041. An FCC could follow in the 2040s.", "", ["strategy", "fcc"]),
]

DISCOVERIES = [
 ("The Higgs boson (2012)", "ATLAS and CMS found the particle linked to the field that gives fundamental particles their mass, predicted in 1964. Englert and Higgs won the 2013 Nobel Prize.", "Why it matters: in CERN's words, stars, planets and life could only emerge because particles gained their mass from this field. The 2026 Strategy update recommends an electron-positron 'Higgs factory' as the next big machine, to study it in detail.", ["higgs", "nobel2013", "strategy"]),
 ("W and Z bosons (1983)", "Found at the SPS, these particles carry the weak force (the 1984 Nobel citation calls them 'communicators of weak interaction').", "In 2024 CMS measured the W mass at 80 360.2 ± 9.9 MeV, in line with the Standard Model, after a 2022 result from Fermilab's CDF experiment had deviated from the prediction.", ["sps", "nobel1984", "wmass"]),
 ("Three families of matter (LEP, 1990s)", "LEP produced about 17 million Z bosons and showed there are three, and only three, generations of matter particles.", "That fixed a basic count in the Standard Model.", ["lep"]),
 ("Quark-gluon plasma", "In 2000 CERN reported evidence that lead-ion collisions melted protons and neutrons into free quarks and gluons. ALICE now studies this state at the LHC.", "It is a sample of what the universe was like microseconds after the Big Bang.", ["qgp", "alice"]),
 ("Antimatter atoms", "ATHENA made cold antihydrogen in 2002, ALPHA trapped it in 2010, and in 2023 ALPHA showed it falls under gravity.", "Matter and antimatter should have been made in equal amounts, yet the universe is made of matter. These tests look for the difference.", ["athena", "alpha2010", "alphag"]),
 ("Pentaquarks (2015)", "LHCb observed particles made of five quarks, a new class of hadron.", "They test our understanding of the strong force that binds atomic nuclei.", ["penta"]),
 ("A one-in-billions decay (2015)", "CMS and LHCb jointly observed the Bs meson decaying to two muons, a process the Standard Model predicts to be extremely rare.", "Its measured rate agrees with the Standard Model, which constrains many proposed new theories.", ["bsmumu"]),
]
SPINOFFS = [
 ("The World Wide Web", "Proposed at CERN by Tim Berners-Lee in 1989 to share physics information; CERN released the software into the public domain on 30 April 1993.", ["web", "weblicense"]),
 ("Medical imaging (PET)", "In 1977 CERN's David Townsend and Alan Jeavons made an early PET image with detectors built for physics. Townsend later co-proposed combining PET with CT scanning, a major advance for cancer diagnosis.", ["pet"]),
 ("Cancer therapy with ions", "CERN's PIMMS study (1996-2000) designed a proton and carbon-ion synchrotron that became the basis for the CNAO centre in Italy and MedAustron in Austria.", ["hadron"]),
 ("Colour X-rays (Medipix)", "Medipix3 detector chips developed through CERN collaborations produced pioneering 3D colour X-ray images of a human in 2018 (MARS Bioimaging, New Zealand).", ["medipix"]),
 ("Grid computing", "The Worldwide LHC Computing Grid links about 1.4 million computer cores and 1.5 exabytes of storage at over 170 sites in 42 countries, serving more than 12 000 physicists.", ["grid"]),
 ("Open data", "CERN publishes collision data and tools for anyone to use; the portal's metadata is released under CC0.", ["opendata"]),
]
PROJECTS = [
 ("HiLumi LHC and Long Shutdown 3", "Now under way. 1.2 km of the LHC is being removed and replaced with new magnets and equipment; restart planned for 2030.", ["ls3news", "hilumi"]),
 ("Future Circular Collider (FCC)", "A proposed 91 km ring. The electron-positron stage is estimated at 15 billion Swiss francs over about 12 years from the early 2030s. Preferred option in the 2026 Strategy; decision targeted by 2028.", ["fcc", "strategy"]),
 ("Antimatter factory: AD and ELENA", "The Antiproton Decelerator and the 30 m ELENA ring slow antiprotons down for the AEgIS, ALPHA, ASACUSA, BASE and GBAR experiments.", ["ad"]),
 ("AMS on the Space Station", "The Alpha Magnetic Spectrometer, assembled at CERN and flown on Endeavour's final flight in 2011, hunts for dark matter and antimatter in cosmic rays. Data is relayed to CERN.", ["ams"]),
 ("ISOLDE", "Makes beams of unstable atomic nuclei from Booster protons for nuclear, atomic and medical-isotope research. Being renovated during LS3.", ["isolde", "complex", "ls3news"]),
 ("n_TOF", "A neutron time-of-flight facility fed by the PS, measuring how neutrons interact with nuclei, data used in astrophysics to study stellar evolution and supernovae.", ["ntof", "complex"]),
 ("North Area and ECN3", "SPS fixed-target halls being consolidated; the ECN3 cavern is being turned into a high-intensity fixed-target facility during LS3.", ["ls3news", "sps"]),
]
MYTHS = [
 {"id": "portal", "title": "Opening portals to other dimensions", "claim": "The LHC is said to tear open doorways to other dimensions or worlds, and some people point to a 2009 quote by CERN's then research director as an admission.",
  "physics": "Some theories predict extra spatial dimensions far smaller than an atom. In 2009 CERN's then research director Sergio Bertolucci told The Register that an 'open door' to such a dimension, if the LHC made one, would last about 10^-26 seconds, only long enough for detectors to 'peer into' it. No experiment has found extra dimensions, and even if found they would be a measurement in detector data, not a passage anything could travel through.",
  "src": ["register", "atlas", "cms"]},
 {"id": "mandela", "title": "The Mandela effect and timeline shifts", "claim": "Shared false memories, such as remembering a logo or a line differently, are blamed on the LHC switching timelines when it starts up.",
  "physics": "The LHC was switched off from June 2026 and stays off until 2030, so the claim can be checked against its own public Page 1 display. Psychologists have reproduced shared, specific false memories in the lab and explain them through how memory and familiar images work, with no physics involved.",
  "src": ["mandela", "leadstories", "ls3"]},
 {"id": "blackhole", "title": "Black holes that swallow the Earth", "claim": "Collisions could make a black hole that grows and destroys the planet. Lawsuits in 2008 tried to stop the start-up.",
  "physics": "CERN's safety panel (LSAG, 2008) found no danger. Cosmic rays hit the Earth, the Moon and dense stars at far higher energies than the LHC and have done so for billions of years; if such collisions made dangerous black holes, neutron stars and white dwarfs would not survive. A U.S. appeals court dismissed the main lawsuit in 2010 for lack of standing.",
  "src": ["lsag", "gm", "safety", "lhc", "sancho"]},
 {"id": "shiva", "title": "The Shiva statue", "claim": "A statue of the Hindu god Shiva at CERN is said to prove the lab is worshipping a destroyer or doing rituals.",
  "physics": "The 2 m statue of Shiva Nataraja, shown in his cosmic dance of creation and destruction, was a gift from India unveiled on 18 June 2004 to celebrate CERN's long association with India, which began in the 1960s. Carl Sagan and the physicist Fritjof Capra both used the dance as a metaphor for the constant creation and annihilation of subatomic particles.",
  "src": ["shiva", "geneve"]},
 {"id": "sacrifice", "title": "The 2016 'human sacrifice' video", "claim": "A video filmed at night from a window showed cloaked figures staging the 'stabbing' of a woman in front of the Shiva statue.",
  "physics": "CERN said it was filmed on its premises without official permission or knowledge by people who had access badges, that it does not condone this kind of spoof, and that it had opened an internal investigation. It was staged: no one was harmed.",
  "src": ["sacrifice", "sacrificedw"]},
 {"id": "abyss", "title": "'Opening the abyss' and summoning", "claim": "Online videos say the collider is meant to open 'the abyss' or summon entities, sometimes citing the statue or the CERN logo.",
  "physics": "CERN shows the state of its machines on public displays, and its Convention requires it to publish its results. What the detectors record is particle tracks and energy deposits, which the collaborations release and others can re-analyse through CERN's open data.",
  "src": ["history", "opendata", "vistar"]},
]
QUIZ = [
 ("How cold are the LHC's main magnets when running?", ["1.9 K (-271.3 °C)", "77 K (liquid nitrogen)", "0 K exactly"], 0, "They run at 1.9 K using superfluid helium, colder than outer space.", "lhc"),
 ("Who pays the largest share of CERN's 2026 member contributions?", ["France", "Germany", "United Kingdom"], 1, "Germany: 20.44%, about CHF 251.9 million.", "budget"),
 ("Is the LHC running right now (November 2026)?", ["Yes, at full power", "No, it is in Long Shutdown 3 until 2030", "Only at night"], 1, "Run 3 ended on 27 June 2026; HiLumi LHC is due to start in 2030.", "ls3news"),
 ("Why are LHC collisions considered safe?", ["The machine has a self-destruct switch", "Cosmic rays have done the same at higher energies for billions of years", "The tunnel is lined with lead"], 1, "Nature runs more energetic collisions all the time, and the Earth, Moon and stars are still here.", "lsag"),
 ("What did CERN give the world in 1993?", ["The World Wide Web software, free", "The smartphone", "GPS"], 0, "On 30 April 1993 CERN put the Web software in the public domain.", "weblicense"),
]

LIVE = [  # public Vistar display captures (allowlist)
 ("lhc1", "LHC Page 1", "Machine mode, beam energy, intensity and operator comments"),
 ("lhc3", "LHC Operation", "Operations overview"),
 ("lhc2", "LHC Cryogenics", "Temperatures of the cooling plants around the ring"),
 ("sps1", "SPS Page 1", "The 7 km injector ring"),
 ("cps", "PS (CPS)", "The Proton Synchrotron"),
 ("psb", "PS Booster", "The 2 GeV Booster"),
]
LIVE_IDS = {k for k, _, _ in LIVE}
LIVE_URL = "https://vistar-capture.s3.cern.ch/{}.png"
LIVE_TTL = 60

def machine_state(today=None):
    """Schedule-based state from CERN's published LS3 dates (not read from the image)."""
    d = today or datetime.now(timezone.utc).date()
    if d < date(2026, 6, 27): return {"lhc": "RUN 3", "lhc_note": "Run 3 physics (see Page 1 for live beam mode)", "inj": "RUNNING", "inj_note": "Injector chain in operation"}
    if d < date(2030, 1, 1): return {"lhc": "LS3 · NO BEAM", "lhc_note": "Long Shutdown 3 since 29 June 2026. HiLumi LHC restart planned for 2030.",
                                     "inj": "LS3" if d >= date(2026, 9, 1) else "RUNNING", "inj_note": "Injectors ran until the end of August 2026 and restart gradually from mid-2028." if d >= date(2026, 9, 1) else "Injectors run until the end of August 2026."}
    return {"lhc": "HILUMI ERA", "lhc_note": "Check Page 1 for the live beam mode.", "inj": "SEE PAGE 1", "inj_note": "Check the live displays."}

# ------------------------------------------------------------------ live fetchers (cached, polite)
_live = {}; _llock = threading.Lock()
def _get(url, timeout=12, limit=3_000_000):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}), timeout=timeout)
    return r.read(limit), r.headers.get("Last-Modified")
def live_image(name):
    if name not in LIVE_IDS: return None
    with _llock:
        c = _live.get(name)
        if c and time.time() - c["t"] < LIVE_TTL: return c
    try:
        body, lm = _get(LIVE_URL.format(name))
        if not body.startswith(b"\x89PNG"): raise ValueError("not a PNG")
        c = {"t": time.time(), "body": body, "lm": lm, "ok": True, "err": None}
    except Exception as ex:
        old = _live.get(name) or {}
        c = {"t": time.time(), "body": old.get("body"), "lm": old.get("lm"), "ok": False, "err": type(ex).__name__}
    with _llock: _live[name] = c
    return c
def _lm_iso(lm):
    if not lm: return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(lm).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception: return None
def status():
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "state": machine_state(), "displays": [],
           "note": "Display images come from CERN's public Vistar captures, fetched by our server at most once a minute. Machine state is from CERN's published Long Shutdown 3 schedule.",
           "source": SRC["vistar"][1]}
    for k, t, d in LIVE:
        c = live_image(k) if k == "lhc1" else _live.get(k)
        out["displays"].append({"id": k, "title": t, "desc": d, "updated": _lm_iso((c or {}).get("lm")), "ok": bool(c and c.get("body")), "img": f"/api/cern/live/{k}.png"})
    return out

_od = {"t": 0, "v": None}; _odl = threading.Lock()
def opendata():
    with _odl:
        if _od["v"] and time.time() - _od["t"] < 6 * 3600: return _od["v"]
    v = {"ok": False, "source": "https://opendata.cern.ch/", "license": "CC0 (portal metadata)"}
    try:
        body, _ = _get("https://opendata.cern.ch/api/records/?size=1", timeout=15)
        d = json.loads(body); a = d.get("aggregations") or {}
        v.update(ok=True, total=(d.get("hits") or {}).get("total"),
                 experiments=sorted(([b["key"], b["doc_count"]] for b in (a.get("experiment") or {}).get("buckets", [])), key=lambda x: -x[1]),
                 types=sorted(([b["key"], b["doc_count"]] for b in (a.get("type") or {}).get("buckets", [])), key=lambda x: -x[1]),
                 fetched=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    except Exception as ex:
        v["error"] = type(ex).__name__
        if _od["v"]: return _od["v"]
    with _odl: _od.update(t=time.time(), v=v)
    return v

# ------------------------------------------------------------------ page parts
SVGI = {
 "ring": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="4" r="1.6"/><circle cx="4.5" cy="15" r="1.6"/><circle cx="19.5" cy="15" r="1.6"/>',
 "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>', "map": '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
 "coin": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v10M9.5 9.5c0-1.2 1.1-2 2.5-2s2.5.8 2.5 2-1.1 1.8-2.5 2.2-2.5 1-2.5 2.3 1.1 2 2.5 2 2.5-.8 2.5-2"/>',
 "people": '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.4"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M15 14.6c3 .1 6 2 6 5.4"/>',
 "star": '<path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z"/>', "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 "live": '<circle cx="12" cy="12" r="2.5"/><path d="M7.8 16.2a6 6 0 0 1 0-8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.9 19.1a10 10 0 0 1 0-14.2M19.1 4.9a10 10 0 0 1 0 14.2"/>',
 "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
 "tools": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
 "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', "atom": '<circle cx="12" cy="12" r="1.8"/><ellipse cx="12" cy="12" rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/>',
}
def ic(n, cls="cx-i"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" focusable="false">{SVGI[n]}</svg>')

def stage(code, energy, label):
    """A section divider styled as the next accelerator in the chain."""
    return (f'<div class="cx-stage" data-stage="{E(code)}" data-energy="{E(energy)}" role="separator" aria-label="{E(label)}: {E(energy)}">'
            f'<span class="cx-stage-line" aria-hidden="true"><i></i></span><span class="cx-stage-tag"><b>{E(label)}</b><span>{E(energy)}</span></span>'
            f'<span class="cx-stage-line" aria-hidden="true"><i></i></span></div>')

def sec(id_, icon, kicker, title, body, cls=""):
    return (f'<section class="cx-sec {cls}" id="{id_}" aria-labelledby="{id_}-h"><p class="cx-kick">{ic(icon)}<span>{E(kicker)}</span></p>'
            f'<h2 id="{id_}-h">{E(title)}</h2>{body}</section>')

def fmt_chf(n): return f"{n / 1e6:,.1f}"

def funding_svg():
    mx = FUND[0][1]; rows = []
    for i, (c, pct, chf, since) in enumerate(FUND):
        w = max(1.2, pct / mx * 100)
        rows.append(f'<li><button type="button" class="cx-bar" data-i="{i}" aria-label="{E(c)}: {pct:.2f} percent, CHF {fmt_chf(chf)} million in 2026">'
                    f'<span class="cx-bl">{E(c)}</span><span class="cx-bt"><span class="cx-bf" style="width:{w:.1f}%"></span></span>'
                    f'<span class="cx-bv">{pct:.2f}%</span></button></li>')
    arows = []
    amx = ASSOC[0][1]
    for i, (c, chf, since) in enumerate(ASSOC):
        w = max(1.2, chf / amx * 100)
        arows.append(f'<li><button type="button" class="cx-bar cx-bar-a" data-a="{i}" aria-label="{E(c)}: CHF {fmt_chf(chf)} million in 2026">'
                     f'<span class="cx-bl">{E(c)}</span><span class="cx-bt"><span class="cx-bf" style="width:{w:.1f}%"></span></span>'
                     f'<span class="cx-bv">{fmt_chf(chf)}M</span></button></li>')
    return (f'<div class="cx-fund" data-view="m"><div class="cx-seg" role="group" aria-label="Choose which contributions to show">'
            f'<button type="button" class="cx-segb" data-v="m" aria-pressed="true">Member States (25)</button>'
            f'<button type="button" class="cx-segb" data-v="a" aria-pressed="false">Associate Members (11)</button></div>'
            f'<div class="cx-fund-grid"><div><ol class="cx-bars cx-bars-m" aria-label="2026 Member State contributions, share of total">{"".join(rows)}</ol>'
            f'<ol class="cx-bars cx-bars-a" aria-label="2026 Associate Member contributions in millions of Swiss francs">{"".join(arows)}</ol></div>'
            f'<aside class="cx-fund-detail" aria-live="polite"><p class="cx-mono cx-dim">SELECT A COUNTRY</p>'
            f'<p class="cx-fd-big">Germany</p><p>20.44% of Member State contributions: <b>CHF 251.9 million</b> in 2026. Member since 1953.</p></aside></div>'
            f'<p class="cx-note">Member State contributions for 2026 total <b>CHF {MEMBER_TOTAL / 1e9:.3f} billion</b>; Associate Members add <b>CHF {ASSOC_TOTAL / 1e6:.1f} million</b> '
            f'(our sum of CERN\'s published table).</p>'
            + srcs("budget", "council", "stake") + '</div>')

def det_svg(k):
    """Stylised end-on detector cross-sections (illustrations, simplified, not to scale)."""
    import math
    c = 'cx="40" cy="40"'
    if k == "lhcb":  # forward spectrometer, side view
        g = ('<rect x="6" y="36" width="68" height="8" rx="2" fill="none" stroke="#22d3ee" stroke-width="1.5"/>'
             '<path d="M10 40 L72 12 M10 40 L72 68" stroke="#e879f9" stroke-width="1.2" fill="none"/>'
             + "".join(f'<line x1="{x}" y1="{40 - (x - 10) * .45:.0f}" x2="{x}" y2="{40 + (x - 10) * .45:.0f}" stroke="#FFC21A" stroke-width="2"/>' for x in (26, 40, 54, 66)))
    else:
        rings = {"atlas": [(8, "#22d3ee"), (14, "#34d399"), (22, "#FFC21A"), (36, "#e879f9")],
                 "cms": [(9, "#22d3ee"), (14, "#34d399"), (19, "#FFC21A"), (23, "#9fb0bf"), (36, "#e879f9")],
                 "alice": [(18, "#22d3ee"), (24, "#34d399"), (32, "#e879f9")]}[k]
        g = "".join(f'<circle {c} r="{r}" fill="none" stroke="{col}" stroke-width="{3 if r > 30 else 2}"/>' for r, col in rings)
        if k == "atlas":
            g += "".join(f'<ellipse cx="{40 + 29 * math.cos(a):.1f}" cy="{40 + 29 * math.sin(a):.1f}" rx="3" ry="6" transform="rotate({math.degrees(a) + 90:.0f} {40 + 29 * math.cos(a):.1f} {40 + 29 * math.sin(a):.1f})" fill="none" stroke="#e879f9" stroke-width="1.2"/>' for a in [i * math.pi / 4 for i in range(8)])
        g += '<circle cx="40" cy="40" r="2" fill="#fff"/>'
    return f'<svg class="cx-det-svg" viewBox="0 0 80 80" aria-hidden="true" focusable="false">{g}</svg>'

def _ang(p):
    import math
    cx, cy = 6.06632, 46.27205
    return math.atan2((p["lat"] - cy) * 110.54, (p["lon"] - cx) * 111.32 * math.cos(math.radians(46.27)))
def ring_svg():
    """Interactive accelerator-chain diagram (illustration, not to scale). Experiment dots sit at their real compass bearing
    from the ring centre (OSM relation 9512017)."""
    import math
    C, R = (380, 205), 160
    exps = []
    for p in PTS:
        a = _ang(p); x = C[0] + R * math.cos(a); y = C[1] - R * math.sin(a)
        if p["exp"]:
            ex = next(e for e in EXPTS if e["id"] == p["exp"])
            lx = C[0] + (R + 30) * math.cos(a); ly = C[1] - (R + 30) * math.sin(a)
            anchor = "start" if math.cos(a) > 0.3 else "end" if math.cos(a) < -0.3 else "middle"
            exps.append(f'<g class="cx-hit cx-exp" tabindex="0" role="button" data-k="{ex["id"]}" aria-label="{E(ex["name"])}, {E(p["label"].split(" · ")[0])}">'
                        f'<circle class="cx-halo" cx="{x:.1f}" cy="{y:.1f}" r="17"/><circle class="cx-dot" cx="{x:.1f}" cy="{y:.1f}" r="8"/>'
                        f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}" class="cx-t cx-te">{E(ex["name"])}</text></g>')
        else:
            exps.append(f'<circle class="cx-pt" cx="{x:.1f}" cy="{y:.1f}" r="3.5"><title>{E(p["label"])}</title></circle>')
    return f'''<div class="cx-chain"><svg viewBox="0 0 640 420" class="cx-chain-svg" role="group" aria-labelledby="cx-chain-t cx-chain-d">
<title id="cx-chain-t">CERN accelerator chain</title><desc id="cx-chain-d">Illustration, not to scale. Select a machine or an experiment for details.</desc>
<defs><radialGradient id="cxg" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#22d3ee" stop-opacity=".16"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></radialGradient></defs>
<circle cx="{C[0]}" cy="{C[1]}" r="{R + 28}" fill="url(#cxg)"/>
<g class="cx-hit" tabindex="0" role="button" data-k="lhc" aria-label="Large Hadron Collider, 6.8 TeV per beam"><circle class="cx-r cx-r-lhc" cx="{C[0]}" cy="{C[1]}" r="{R}"/><circle class="cx-beam" cx="{C[0]}" cy="{C[1]}" r="{R}"/><circle class="cx-beam cx-beam2" cx="{C[0]}" cy="{C[1]}" r="{R}"/><text x="{C[0]}" y="{C[1] + 5}" text-anchor="middle" class="cx-t cx-big">LHC</text><text x="{C[0]}" y="{C[1] + 26}" text-anchor="middle" class="cx-t cx-sm">26.7 km · 6.8 TeV/beam</text></g>
<g class="cx-hit" tabindex="0" role="button" data-k="sps" aria-label="Super Proton Synchrotron, 450 GeV"><circle class="cx-r cx-r-sps" cx="172" cy="352" r="48"/><text x="172" y="356" text-anchor="middle" class="cx-t">SPS</text><text x="172" y="372" text-anchor="middle" class="cx-t cx-sm">450 GeV</text></g>
<g class="cx-hit" tabindex="0" role="button" data-k="ps" aria-label="Proton Synchrotron, 26 GeV"><circle class="cx-r cx-r-ps" cx="72" cy="318" r="24"/><text x="72" y="360" text-anchor="middle" class="cx-t">PS</text><text x="72" y="375" text-anchor="middle" class="cx-t cx-sm">26 GeV</text></g>
<g class="cx-hit" tabindex="0" role="button" data-k="psb" aria-label="Proton Synchrotron Booster, 2 GeV"><circle class="cx-r cx-r-psb" cx="44" cy="236" r="12"/><text x="64" y="232" class="cx-t">PSB</text><text x="64" y="247" class="cx-t cx-sm">2 GeV</text></g>
<g class="cx-hit" tabindex="0" role="button" data-k="linac4" aria-label="Linac4, 160 MeV"><path class="cx-r cx-r-lin" d="M18 128 L37 220"/><text x="10" y="112" class="cx-t">Linac4</text><text x="10" y="97" class="cx-t cx-sm">160 MeV</text></g>
<path class="cx-xfer" d="M48 249 L60 297 M96 322 L126 338 M216 334 Q 236 318 246 298"/>
{"".join(exps)}
<text x="630" y="412" text-anchor="end" class="cx-t cx-sm cx-dim">Illustration · not to scale</text>
</svg>
<div class="cx-chain-panel" id="cx-chain-panel" aria-live="polite"><p class="cx-mono cx-dim">SELECT A MACHINE OR EXPERIMENT</p>
<p class="cx-cp-t">Protons start in Linac4 and gain energy in four machines before colliding inside the LHC's detectors.</p></div></div>'''

def collider_html():
    return '''<div class="cx-sim" id="cx-sim">
<div class="cx-sim-ctl">
 <label class="cx-fl" for="cx-e">Collision energy</label>
 <select id="cx-e"><option value="0.9">0.9 TeV (Nov 2009)</option><option value="7">7 TeV (2010)</option><option value="8">8 TeV (2012, Higgs year)</option><option value="13">13 TeV (2015)</option><option value="13.6" selected>13.6 TeV (Run 3)</option></select>
 <label class="cx-fl" for="cx-p">What happens</label>
 <select id="cx-p"><option value="jets">Two jets (the common case)</option><option value="zmm">Z boson to two muons</option><option value="hgg">Higgs boson to two photons</option><option value="h4m">Higgs boson to four muons (via two Z bosons)</option><option value="wen">W boson to electron plus neutrino</option></select>
 <button type="button" class="cx-btn cx-btn-p" id="cx-go">Collide</button>
 <label class="cx-chk"><input type="checkbox" id="cx-lbl" checked> Show detector layers</label>
</div>
<div class="cx-sim-stage"><canvas id="cx-cv" width="720" height="720" role="img" aria-label="Illustrated end-on view of a CMS-style detector showing particle tracks from the selected collision"></canvas>
<p class="cx-sim-badge">Illustration · not real collision data</p></div>
<div class="cx-sim-read" aria-live="polite" id="cx-read"><p class="cx-mono cx-dim">PRESS COLLIDE</p></div>
<noscript><p class="cx-note">The collision simulator needs JavaScript. The explanation below works without it.</p></noscript>
</div>'''

def live_html():
    st = machine_state()
    cards = "".join(
        f'<figure class="cx-live-card" data-id="{k}"><div class="cx-live-img"><img src="/api/cern/live/{k}.png" alt="CERN {E(t)} live display ({E(d)})" width="1024" height="768" loading="lazy" decoding="async"></div>'
        f'<figcaption><b>{E(t)}</b><span class="cx-mono cx-live-age" data-age="{k}">loading</span><span class="cx-dim">{E(d)}</span></figcaption></figure>' for k, t, d in LIVE)
    return f'''<div class="cx-live" id="cx-live">
<div class="cx-readout" role="group" aria-label="Machine status">
 <div><span class="cx-mono cx-dim">LHC</span><b class="cx-mono" id="cx-st-lhc">{E(st["lhc"])}</b><span class="cx-dim" id="cx-st-lhcn">{E(st["lhc_note"])}</span></div>
 <div><span class="cx-mono cx-dim">INJECTORS</span><b class="cx-mono" id="cx-st-inj">{E(st["inj"])}</b><span class="cx-dim" id="cx-st-injn">{E(st["inj_note"])}</span></div>
 <div><span class="cx-mono cx-dim">PAGE 1 IMAGE</span><b class="cx-mono" id="cx-st-p1">checking</b><span class="cx-dim">Time CERN last refreshed its LHC Page 1 capture</span></div>
</div>
<p class="cx-note">The status words above come from CERN's published shutdown schedule. The images below are CERN's own public control-room displays
("Vistars"), refreshed here every minute while this page is open. While the LHC is in Long Shutdown 3 they mostly read "no beam"; once beams return,
Page 1 shows the beam mode, energy and intensity live.</p>
<div class="cx-live-grid">{cards}</div>
<p class="cx-cite"><span>Sources:</span> {s("vistar")} · {s("ls3")} · {s("ls3news")}</p>
<div class="cx-od" id="cx-od"><h3>CERN Open Data, live count</h3><p class="cx-dim">Loading record counts from the CERN Open Data portal...</p></div>
<div class="cx-links">
 <a class="cx-btn" href="{E(SRC["vistar"][1])}" target="_blank" rel="noopener">{ic("live")}All CERN live displays</a>
 <a class="cx-btn" href="{E(SRC["youtube"][1])}" target="_blank" rel="noopener">{ic("eye")}CERN on YouTube</a>
 <a class="cx-btn" href="{E(SRC["opendata"][1])}" target="_blank" rel="noopener">{ic("link")}CERN Open Data portal</a>
</div>
<p class="cx-note">We did not find a continuous live feed of the machine on CERN's YouTube channel, so we link the channel instead of embedding a video. The Vistar displays above are the live view CERN itself offers the public.</p>
</div>'''

def page_html():
    lede = ('<header class="cx-hero" id="top"><canvas class="cx-tracks" id="cx-tracks" aria-hidden="true"></canvas><div class="cx-hero-in">'
            '<p class="cx-kick cx-kick-hero">' + ic("atom") + '<span>Explainer · Science &amp; infrastructure</span></p>'
            '<h1 class="cx-h1">CERN and the Large Hadron Collider</h1>'
            '<p class="cx-dek">The 27 km machine under the French-Swiss border: how it works, how it was built, who pays for it, what it found, '
            'what people claim about it, and what it is doing right now.</p>'
            '<div class="cx-facts" role="list">'
            '<div role="listitem"><b class="cx-mono">26 659 m</b><span>ring circumference</span></div>'
            '<div role="listitem"><b class="cx-mono">100 m</b><span>underground</span></div>'
            '<div role="listitem"><b class="cx-mono">1.9 K</b><span>magnet temperature (-271.3 °C)</span></div>'
            '<div role="listitem"><b class="cx-mono">13.6 TeV</b><span>record collision energy</span></div>'
            '<div role="listitem"><b class="cx-mono">11 245</b><span>laps per second</span></div>'
            '<div role="listitem"><b class="cx-mono">CHF 4.3 bn</b><span>LHC construction cost</span></div>'
            '</div>' + srcs("lhc") +
            '<div class="cx-now"><span class="cx-live-dot" aria-hidden="true"></span><span class="cx-mono">NOW</span> The LHC is switched off for its biggest upgrade. '
            'Run 3 ended on 27 June 2026; the HiLumi LHC is due in 2030. <a href="#live">See the live displays</a></div>'
            '</div></header>')
    toc = ('<nav class="cx-toc" aria-label="On this page"><a href="#what">What it is</a><a href="#how">How it works</a><a href="#collide">Run a collision</a>'
           '<a href="#built">How it was built</a><a href="#scale">Map and scale</a><a href="#money">Who pays</a><a href="#people">People and projects</a>'
           '<a href="#found">Discoveries</a><a href="#myths">Theories vs physics</a><a href="#live">Live</a><a href="#dots">Analysis</a><a href="#sources">Sources</a></nav>')

    what = sec("what", "atom", "The basics", "What CERN and the LHC are", fig("lhc-tunnel-2009.jpg", "cx-wide", eager=True) + f'''
<p><b>CERN</b>, the European Organization for Nuclear Research, is a physics laboratory on the French-Swiss border near Geneva. It grew from a 1951 UNESCO resolution and a Convention signed by
12 states in 1953, and began work in 1954. Its Convention says it "shall have no concern with work for military requirements" and that its results must be published. {s("history", "Source: CERN history")}</p>
<p>Today it is run and mainly funded by <b>25 Member States</b>, with <b>11 Associate Members</b> and observers including the United States and Japan. {s("stake", "Source: CERN stakeholders")}</p>
<p>The <b>Large Hadron Collider</b> is CERN's largest machine and the most powerful particle accelerator in the world: a 26.7 km ring of superconducting magnets, 100 m underground,
that accelerates two beams of protons (or lead ions) to close to the speed of light in opposite directions and smashes them together inside four giant detectors:
ATLAS, CMS, ALICE and LHCb. {s("lhc", "Source: CERN LHC facts")}</p>
<h3>What it was built to do</h3>
<p>The LHC was designed to test the Standard Model of particle physics where it had never been tested: to find out whether the Higgs mechanism, proposed in 1964 to explain how particles get
mass, is real (it is: the Higgs boson was found in 2012), and to look for answers to open questions such as what dark matter is, why the universe contains matter but almost no antimatter,
and how matter behaved in the earliest instants after the Big Bang. {s("lhc", "Source: CERN LHC FAQ")}</p>''')

    how = sec("how", "bolt", "The machine", "How it works", f'''
<p>Protons are not shot straight into the LHC. They climb an energy ladder through four older machines, each feeding the next. Tap a stage or an experiment.</p>
{ring_svg()}
<div class="cx-grid3">
 <div class="cx-card"><h3>Superconducting magnets</h3><p>9593 magnets steer the beams, including 1232 main dipoles, each 15 m long, that bend them and 392 quadrupoles that focus them. Their coils carry current with no
 resistance only when cooled to 1.9 K. {s("lhc", "CERN")}</p></div>
 <div class="cx-card"><h3>Cryogenics</h3><p>The world's largest cryogenic system cools 23 km of the ring with superfluid helium, a liquid that conducts heat extremely well. {s("lhc", "CERN")}</p></div>
 <div class="cx-card"><h3>Vacuum</h3><p>The beam pipes are pumped down to about 10<sup>-13</sup> bar, ten million million times lower than air pressure at sea level and close to the pressure on the Moon. {s("lhc", "CERN")}</p></div>
 <div class="cx-card"><h3>Acceleration</h3><p>Eight superconducting radio-frequency cavities per beam, each giving 2 megavolts at 400 MHz, push the protons up to 6.8 TeV. {s("lhc", "CERN")}</p></div>
 <div class="cx-card"><h3>Bunches</h3><p>Each beam holds about 2500 bunches of up to 160 billion protons, normally 25 nanoseconds (about 7 m) apart. Beams circulate 10 to 15 hours before they are dumped. {s("lhc", "CERN")}</p></div>
 <div class="cx-card"><h3>Collisions</h3><p>About 1.5 billion collisions a second happen in ATLAS and CMS. Making them collide is likened to firing two needles 10 km apart so they meet halfway. {s("lhc", "CERN")}</p></div>
</div>
<p class="cx-note">For scale: 13.6 TeV is about the energy of a needle falling a few centimetres. The LHC's trick is concentrating it into a space trillions of times smaller. {s("lhc", "Source: CERN")}</p>''')

    collide = sec("collide", "star", "Interactive", "Run a collision", f'''
<p>Pick an energy and a process, then press Collide. You are looking down the beam pipe of a detector built like CMS. Charged particles curve in the magnetic field (positive and negative bend
opposite ways, and slower ones curl tighter), photons and electrons stop in the electromagnetic calorimeter, hadrons stop in the hadron calorimeter, muons punch through to the outer muon
chambers, and neutrinos escape unseen: physicists spot them as missing energy.</p>
{collider_html()}
<p class="cx-note">Curvature uses the real relation between momentum and bending radius (r = pT / 0.3B) in a field of about 4 tesla, like CMS's solenoid; outside the coil the steel yoke returns the field, so muons bend the other way. Layer sizes and particle counts are simplified.
Real events contain far more tracks, and processes like the Higgs boson are very rare among the 1.5 billion collisions a second. {s("cms", "CMS")} · {s("lhc", "LHC facts")}</p>''')

    tl = "".join(
        f'<li class="cx-tl-i" data-year="{E(y)}" id="tl-{E(y)}"><p class="cx-tl-y cx-mono">{E(y)}</p><h3>{E(t)}</h3>'
        + (fig(img, "cx-tl-fig") if img else "") + f'<p>{E(tx)}</p><p class="cx-cite">' + " · ".join(s(k) for k in ks) + '</p></li>' for y, t, tx, img, ks in TIMELINE)
    built = sec("built", "tools", "History", "How it was built", f'''
<p>The LHC reused the 27 km tunnel dug for LEP, an electron-positron collider that ran from 1989 to 2000. LHC construction and assembly ran from 1996 to 2008 and involved several thousand people
and companies around the world. {s("lep", "CERN: LEP")} · {s("lhc", "CERN: LHC FAQ")}</p>
<div class="cx-tl" id="cx-tl">
 <div class="cx-tl-ctl"><label for="cx-tl-r" class="cx-fl">Drag through time: <b class="cx-mono" id="cx-tl-yr">1951</b></label>
 <input type="range" id="cx-tl-r" min="0" max="{len(TIMELINE) - 1}" value="0" step="1" aria-valuetext="1951">
 <div class="cx-tl-btns"><button type="button" class="cx-btn" id="cx-tl-prev" aria-label="Previous event">Prev</button><button type="button" class="cx-btn" id="cx-tl-next" aria-label="Next event">Next</button></div></div>
 <ol class="cx-tl-track" id="cx-tl-track" tabindex="0" aria-label="Timeline, 1951 to 2041">{tl}</ol>
</div>
<h3>The 2008 incident</h3>
<p>Nine days after start-up, on 19 September 2008, a faulty electrical connection between two magnets in sector 3-4 developed resistance while current was ramping up. Within a second an electric
arc punctured the helium enclosure; helium flooded the insulating vacuum and burst into the tunnel, and the pressure tore some magnets from their floor anchors. Safety systems worked and no
one was hurt. 53 magnets were removed for cleaning or repair, new protection systems were added, and the LHC restarted in late 2009. {s("incident", "CERN analysis, Oct 2008")} · {s("magnet53", "CERN, April 2009")}</p>
<div class="cx-gal">{fig("atlas-2007.jpg", "cx-tall")}{fig("cms-shaft-2008.jpg", "cx-tall")}{fig("cms-construction-2008.jpg")}{fig("magnet-factory.jpg")}</div>
<h3>Upgrades and what is happening now</h3>
<p>Run 2 (2015) raised collisions to 13 TeV and Run 3 (2022) to 13.6 TeV. Run 3 ended on 27 June 2026. In <b>Long Shutdown 3</b>, about 1.2 km of the machine is being taken out and replaced
for the <b>HiLumi LHC</b>, which aims to deliver ten times the original design's integrated luminosity (total collisions) from 2030. The rest of the accelerator complex restarts gradually from mid-2028.
{s("lhc", "CERN")} · {s("ls3news", "CERN, 29 June 2026")} · {s("hilumi", "CERN HiLumi")}</p>''')

    scale = sec("scale", "map", "Interactive map", "Where it is, and how big", f'''
<p>The ring straddles the French-Swiss border, with Point 1 (ATLAS) beside CERN's main site at Meyrin in Switzerland and the other three big experiments at sites in France.
The map opens on the real tunnel at Geneva (as mapped in OpenStreetMap). Pick a city to drop the same-size ring over it and see how big 26.7 km really is, or use your location, and tap the experiment sites for details.</p>
<div class="cx-map-ctl"><label class="cx-fl" for="cx-city">Put the ring over</label><select id="cx-city">''' +
            "".join(f'<option value="{k}"{" selected" if k == "geneva" else ""}>{E(n)}</option>' for k, n, _, _ in CITIES) +
            f'''</select><button type="button" class="cx-btn" id="cx-geo">Use my location</button></div>
<div class="cx-map" id="cx-map" role="region" aria-label="Map of the LHC ring and experiment sites"><p class="cx-map-ph">Loading the map...</p></div>
<p class="cx-note" id="cx-geo-note">Your location is used only in your browser to place the ring; it is never sent to our server.</p>
<div class="cx-grid3">
 <div class="cx-card"><h3>8.5 km across</h3><p>A 26 659 m ring is about 8.5 km in diameter (our calculation). Walking it at 5 km/h would take about 5 hours 20 minutes.</p></div>
 <div class="cx-card"><h3>Longer than a half marathon</h3><p>One lap is 26.7 km: longer than a half marathon (21.1 km), shorter than a marathon (42.2 km). Protons do it 11 245 times a second. {s("lhc", "CERN")}</p></div>
 <div class="cx-card"><h3>Detectors the size of buildings</h3><p>ATLAS is 46 m long and 25 m high; CMS weighs 14 000 tonnes. {s("atlas", "ATLAS")} · {s("cms", "CMS")}</p></div>
</div>
{fig("lhc-from-space-aster.jpg", "cx-mid")}
<p class="cx-cite">Ring outline: {s("osmrel")} (© OpenStreetMap contributors, ODbL). Map tiles: <a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a>.</p>''')

    money = sec("money", "coin", "Funding", "Who pays for it", f'''
<p>CERN is funded mainly by annual contributions from its Member States, set as a fixed share of the budget for each country. Associate Members pay smaller, fixed amounts. Observers attend Council meetings; the United States, an observer, paid into the LHC through a separate agreement. Tap a bar for the numbers.</p>
{funding_svg()}
<div class="cx-grid2">
 <div class="cx-card"><h3>What the LHC cost</h3><table class="cx-tab"><caption class="cx-dim">Construction costs, millions of Swiss francs (CERN)</caption>
 <tr><th scope="row">LHC machine and areas (incl. R&amp;D, injectors, tests)</th><td class="cx-mono">3 756</td></tr>
 <tr><th scope="row">CERN share of detectors and detector areas</th><td class="cx-mono">493</td></tr>
 <tr><th scope="row">LHC computing (CERN share)</th><td class="cx-mono">83</td></tr>
 <tr><th scope="row"><b>Total</b></th><td class="cx-mono"><b>4 332</b></td></tr></table>
 <p class="cx-note">All four big detectors together cost about CHF 1.5 billion; the collaborations fund them separately from CERN. {s("lhc", "Source: CERN LHC FAQ")}</p></div>
 <div class="cx-card"><h3>The U.S. role</h3><p>The United States is not a member. After Congress cancelled its own Superconducting Super Collider in 1993, the U.S. signed an agreement in December 1997 to provide
 <b>$531 million</b> in goods and services: $450 million from the Department of Energy and $81 million from the National Science Foundation, covering $200 million of accelerator components and $331 million
 for the ATLAS and CMS detectors. Fermilab, Brookhaven and Berkeley Lab built parts of the machine. The U.S. has been a CERN Council observer since 1998.
 {s("us531", "CERN, 1997")} · {s("aip97", "AIP, 1997")} · {s("council", "CERN Council")}</p></div>
</div>
<div class="cx-card"><h3>Members, associates and observers</h3>
<p><b>Member States (25):</b> {E(", ".join(sorted(c for c, *_ in FUND)))}.</p>
<p><b>Associate Members (11):</b> Brazil, Chile, Croatia, Cyprus, India, Ireland, Latvia, Lithuania, Pakistan, Türkiye, Ukraine. Chile is the newest, from 2 April 2026.</p>
<p><b>Observers:</b> {E("; ".join(f"{a} ({b})" for a, b in OBSERVERS))}.</p>{srcs("council", "chile")}</div>''')

    exp_cards = "".join(
        f'<div class="cx-card cx-exp-card" id="exp-{e["id"]}"><h3>{E(e["name"])} <span class="cx-pill cx-mono">{E(e["pt"])}</span></h3>{det_svg(e["id"])}<p class="cx-dim">{E(e["place"])}</p>'
        f'<p>{E(e["focus"])}</p><ul class="cx-ul"><li>{E(e["size"])}</li><li>{E(e["people"])}</li><li>{E(e["lead"])}</li></ul>'
        f'<p class="cx-cite">' + " · ".join(s(k) for k in e["src"]) + '</p></div>' for e in EXPTS)
    proj = "".join(f'<li><b>{E(t)}.</b> {E(d)} <span class="cx-cite">' + " · ".join(s(k) for k in ks) + '</span></li>' for t, d, ks in PROJECTS)
    people = sec("people", "people", "Who runs it", "People, experiments and projects", f'''
<div class="cx-grid2">
 <div class="cx-card"><h3>Leadership</h3><ul class="cx-ul">
 <li><b>Mark Thomson</b>, Director-General since 1 January 2026 (five-year mandate). A British experimental particle physicist who worked on CERN's OPAL experiment at LEP. {s("thomson", "CERN")}</li>
 <li><b>Costas Fountas</b>, President of the CERN Council. {s("councilcomp", "CERN Council")}</li>
 <li><b>Oliver Brüning</b>, Director for Accelerators and Technology. {s("ls3news", "CERN")}</li>
 <li><b>Gautier Hamel de Monchenault</b>, Director of Research and Computing (former CMS spokesperson). {s("cmsmgmt", "CMS")}</li></ul></div>
 <div class="cx-card"><h3>The collaborations</h3><p>The experiments are run by international collaborations, separate from CERN itself, each led by an elected spokesperson. Thousands of physicists, engineers,
 technicians and students work on them from universities and labs worldwide, including in the United States: CMS's current spokesperson is a Fermilab scientist. {s("lhc", "CERN")} · {s("cmsmgmt", "CMS")}</p></div>
</div>
<div class="cx-grid2">{exp_cards}</div>
<p class="cx-note">Detector icons are simplified BLACKOUT.NETWORK illustrations of each layout, not to scale.</p>
<h3>Other projects now</h3><ul class="cx-ul cx-proj">{proj}</ul>
{fig("hl-lhc-tunnel-2025.jpg", "cx-mid")}''')

    disc = "".join(f'<div class="cx-card cx-disc"><h3>{E(t)}</h3><p>{E(a)}</p><p class="cx-why">{E(b)}</p><p class="cx-cite">' + " · ".join(s(k) for k in ks) + '</p></div>' for t, a, b, ks in DISCOVERIES)
    spin = "".join(f'<div class="cx-card"><h3>{E(t)}</h3><p>{E(d)}</p><p class="cx-cite">' + " · ".join(s(k) for k in ks) + '</p></div>' for t, d, ks in SPINOFFS)
    found = sec("found", "star", "Results", "What it discovered, and what it means", f'''
<div class="cx-grid2">{disc}</div>
<h3>Things you use that came out of CERN</h3>
<div class="cx-grid3">{spin}</div>
<h3>Why this work matters</h3>
<p>Most of what CERN finds has no immediate use; that is the nature of basic research. What CERN does deliver quickly is engineering
it had to invent to do the physics (superconducting magnets, ultra-high vacuum, fast detectors, huge distributed computing) and people trained to build it. The questions themselves, what mass is,
why matter beat antimatter, what dark matter is, remain open, and the HiLumi LHC and a possible FCC are designed to chase them. {s("strategy", "CERN Strategy update, 2026")}</p>''')

    myth_cards = "".join(
        f'''<article class="cx-myth" id="myth-{m["id"]}"><h3>{E(m["title"])}</h3>
<div class="cx-flip" data-side="claim"><div class="cx-face cx-face-claim"><p class="cx-mono cx-tagc">WHAT PEOPLE SAY</p><p>{E(m["claim"])}</p></div>
<div class="cx-face cx-face-phys"><p class="cx-mono cx-tagp">WHAT THE RECORD AND PHYSICS SAY</p><p>{E(m["physics"])}</p></div></div>
<button type="button" class="cx-btn cx-flipb" aria-expanded="false" aria-controls="myth-{m["id"]}">Show what physics says</button>
<p class="cx-cite"><span>Sources:</span> ''' + " · ".join(s(k) for k in m["src"]) + '</p></article>' for m in MYTHS)
    qz = "".join(f'<li class="cx-q" data-a="{a}"><p class="cx-q-t">{i + 1}. {E(q)}</p><div class="cx-q-o" role="group" aria-label="Answers">' +
                 "".join(f'<button type="button" class="cx-btn cx-qo" data-o="{j}">{E(o)}</button>' for j, o in enumerate(opts)) +
                 f'</div><p class="cx-q-r" aria-live="polite" hidden>{E(why)} {s(k, "Source")}</p></li>' for i, (q, opts, a, why, k) in enumerate(QUIZ))
    myths = sec("myths", "eye", "Neutral look", "The theories, and what physics says", f'''
<p>The LHC attracts more speculation than almost any machine on Earth. Here is what people say, laid out fairly, next to what the public record and physics show. Each card flips.</p>
<div class="cx-grid2 cx-myths">{myth_cards}</div>
<div class="cx-card cx-quiz" id="cx-quiz"><h3>Quick check: five questions</h3><ol class="cx-qs">{qz}</ol><p class="cx-mono" id="cx-q-score" aria-live="polite"></p></div>''')

    live = sec("live", "live", "Real time", "What CERN is doing right now", live_html())

    dots = sec("dots", "link", "Analysis", "Connecting the dots", f'''
<p class="cx-flag">BLACKOUT.NETWORK analysis. This section is our reading of the sourced facts above, not a CERN statement.</p>
<ol class="cx-dots">
<li><b>The shutdown is a built-in fact check.</b> From 27 June 2026 until the HiLumi restart planned for 2030, the LHC produces no collisions. Any claim that "CERN switched on" and something happened
in that window can be checked against CERN's public Page 1 display on this page. {s("ls3news", "CERN")} · {s("vistar", "Vistars")}</li>
<li><b>Science and geopolitics are tied together.</b> CERN suspended the observer status of Russia and of the Dubna-based JINR in March 2022, weeks after Russia invaded Ukraine; Ukraine itself has been an
Associate Member since 2016. A lab whose Convention bans military work still ends up reflecting the wars around it. {s("council", "CERN Council")} · {s("history", "CERN Convention")}</li>
<li><b>Europe now leads where the U.S. stepped back.</b> The U.S. cancelled its own super collider in 1993 and joined the LHC as a contributor instead. The next step, FCC-ee at about 15 billion Swiss
francs, would again be built in Europe, with a decision targeted by 2028. {s("aip97", "AIP")} · {s("fcc", "CERN FCC")} · {s("strategy", "CERN Strategy")}</li>
<li><b>Energy is the hidden constraint.</b> The LHC, its experiments and services use around 600 GWh of electricity a year, and all of CERN about 1.3 TWh, roughly 40% of the Geneva canton's annual
electricity production (our calculation from CERN's figures). Any future collider has to be justified against Europe's power supply and prices. {s("lhc", "CERN LHC FAQ")}</li>
<li><b>Openness is what makes the theories testable.</b> CERN must publish its results, releases collision data publicly, and shows its machine status live. That does not end speculation,
but it means each specific claim can be checked against records anyone can read. {s("history", "CERN Convention")} · {s("opendata", "CERN Open Data")}</li>
</ol>''')

    credits = "".join(f'<li><b>{E(IMG[f][1])}</b>: {credit(f)}. <a href="/api/cern/img/{E(f)}" target="_blank" rel="noopener">Image file</a></li>' for f in IMG)
    allsrc = "".join(f'<li>{s(k)}</li>' for k in SRC)
    sources = sec("sources", "link", "Sources", "Sources and credits", f'''
<p>Every fact on this page links to its source. Photos are credited below with their licences.</p>
<details class="cx-det"><summary>All sources ({len(SRC)})</summary><ol class="cx-srcl">{allsrc}</ol></details>
<details class="cx-det"><summary>Photo credits ({len(IMG)})</summary><ul class="cx-srcl">{credits}</ul></details>
<p class="cx-note">The accelerator-chain diagram, the collision simulator and the background particle tracks are BLACKOUT.NETWORK illustrations, not CERN imagery or real event data.
Live displays are CERN's public Vistar captures. Map tiles: OpenFreeMap © OpenMapTiles, data © OpenStreetMap contributors. Libraries: MapLibre GL JS (BSD-3-Clause).</p>''')

    data = {"stages": STAGES, "expts": EXPTS, "pts": PTS, "cities": [{"k": k, "n": n, "lat": la, "lon": lo} for k, n, la, lo in CITIES],
            "fund": [{"c": c, "pct": p, "chf": v, "since": y} for c, p, v, y in FUND], "assoc": [{"c": c, "chf": v, "since": y} for c, v, y in ASSOC],
            "src": {k: {"t": t, "u": u} for k, (t, u) in SRC.items()}}
    body = (lede + toc + '<div class="cx-body">' + what + stage("linac4", "160 MeV", "Linac4") + how + stage("psb", "2 GeV", "PS Booster") + collide
            + stage("ps", "26 GeV", "Proton Synchrotron") + built + scale + stage("sps", "450 GeV", "Super Proton Synchrotron") + money + people
            + stage("lhc", "6.8 TeV per beam", "LHC") + found + myths + stage("det", "13.6 TeV collisions", "Detectors") + live + dots + sources + '</div>'
            + '<div class="cx-beamchip" id="cx-beamchip" aria-hidden="true"><span class="cx-mono">BEAM</span><b class="cx-mono" id="cx-beamchip-e">0 eV</b><span id="cx-beamchip-s">source</span></div>'
            + f'<script type="application/json" id="cx-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>')
    return body

def _head():
    if sitenav is not None and "cern" in getattr(sitenav, "PAGES", {}):
        try: return sitenav.head_html("cern", "/cern")
        except Exception: pass
    return '<title>CERN and the Large Hadron Collider | BLACKOUT.NETWORK</title><link rel="stylesheet" href="/sitenav.css"><script src="/sitenav.js" defer></script>'
def _top():
    if sitenav is not None:
        try: return sitenav.header_html("@cern")
        except Exception: pass
    return '<header class="bn-hd"><a href="/">BLACKOUT.NETWORK</a></header>'

def full_page():
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": "CERN and the Large Hadron Collider: how it works, who pays, what it found, and what people claim",
          "about": [{"@type": "Organization", "name": "CERN", "url": "https://home.cern"}, {"@type": "Thing", "name": "Large Hadron Collider"}],
          "publisher": {"@type": "Organization", "name": "BLACKOUT.NETWORK", "url": SITE}, "datePublished": "2026-11-13", "dateModified": "2026-11-13",
          "image": SITE + "/api/cern/img/lhc-tunnel-2009.jpg", "mainEntityOfPage": SITE + "/cern"}
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + _head() +
            '<meta name="robots" content="index,follow,max-image-preview:large"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/api/cern/app.css">'
            '<link rel="icon" href="/favicon.ico?v=3" sizes="any"><link rel="preload" as="image" href="/api/cern/img/lhc-tunnel-2009.jpg">'
            f'<script type="application/ld+json">{json.dumps(ld)}</script>'
            '<style>body{margin:0;background:var(--bn-bg,#0B0D10);overflow-x:hidden}</style></head><body class="cx-page">'
            '<a class="skip bn-skip" href="#main" style="position:absolute;left:-999px">Skip to content</a>' + _top() +
            '<main class="cx" id="main">' + page_html() + '</main>'
            '<footer class="cx-foot">BLACKOUT.NETWORK · <a href="/">The Wire</a> · <a href="/#solar">Solar &amp; Seismic</a> · <a href="/#spacex">SpaceX</a> · '
            '<a href="/sources">Sources</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a><br>Independent explainer. Not affiliated with or endorsed by CERN. Signal over noise.</footer>'
            '<script src="/api/cern/app.js" defer></script></body></html>')

# ------------------------------------------------------------------ routes
def _file(name, ctype):
    try:
        with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), ctype
    except Exception: return 404, {"error": "not found"}

def handle_get(path, qs=None):
    p = path.rstrip("/") or "/"
    if p in ("/cern", "/lhc", "/cern/lhc"): return 200, full_page(), "text/html"
    if p == "/api/cern/status": return 200, status()
    if p == "/api/cern/opendata": return 200, opendata()
    if p.startswith("/api/cern/live/") and p.endswith(".png"):
        name = p[len("/api/cern/live/"):-4]
        c = live_image(name)
        if c and c.get("body"): return 200, c["body"], "image/png"
        return 404, {"error": "display unavailable"}
    if p.startswith("/api/cern/img/"):
        name = p[len("/api/cern/img/"):]
        if name in IMG: return _file(os.path.join("img", name), "image/jpeg")
        return 404, {"error": "not found"}
    if p.startswith("/api/cern/"):
        name = p.rsplit("/", 1)[-1]
        if name in FILES: return _file(name, FILES[name])
    return 404, {"error": "not found"}
