"""/midterms poll-closing times match the sourced table (NCSL, 270toWin) in /workspace/seo/data/poll_close_2026-11-03.json."""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import midterms as M, midterms_hub as H

TABLE = os.environ.get("BN_POLL_CLOSE_JSON", "/workspace/seo/data/poll_close_2026-11-03.json")

def _rows():
    return {r["state"]: r for r in json.load(open(TABLE))["states"]}

def test_all_51():
    rows = _rows(); assert len(rows) == 51 and set(M.POLL_CLOSE) == set(rows)

def test_last_and_first_match():
    for st, r in _rows().items():
        cl = sorted(datetime.fromisoformat(c["at_et"]) for c in r["closes"])
        assert datetime.fromisoformat(M.POLL_CLOSE[st]) == cl[-1] and datetime.fromisoformat(M.POLL_CLOSE_FIRST[st]) == cl[0], st

def test_texas_render():
    con = {"t": "Safe R", "n": 3}
    html = H._race({"state": "TX", "label": "Texas", "state_name": "Texas", "consensus": con, "poll_close": M.POLL_CLOSE["TX"], "candidates": []}, {}, "senate")
    assert "Polls close 8:00 PM ET in most of Texas (Central time), 9:00 PM ET in the Mountain-time area" in html
    html = H._race({"state": "GA", "label": "Georgia", "consensus": con, "poll_close": M.POLL_CLOSE["GA"], "candidates": []}, {}, "senate")
    assert "Polls close 7:00 PM ET" in html and " to " not in html.split("Polls close")[1][:30]

def test_county_caveat():
    for st, nm in (("KS", "Kansas"), ("ND", "North Dakota"), ("OR", "Oregon"), ("TX", "Texas")):
        html = H._race({"state": st, "label": nm, "state_name": nm, "consensus": {"t": "Safe R", "n": 3}, "poll_close": M.POLL_CLOSE[st], "candidates": []}, {}, "senate")
        assert ("; local hours vary by county" in html) == (st != "TX"), st

def test_office_links():
    rows = _rows()
    for st in M.POLL_CLOSE:
        o = M.ELECTION_OFFICES.get(st) or {}
        assert o.get("office_url", "").startswith("https://") and o.get("office_name"), st
        assert rows[st].get("office_url") == o["office_url"] and rows[st].get("office_name") == o["office_name"], st
        html = H._race({"state": st, "label": st, "state_name": st, "consensus": {}, "poll_close": M.POLL_CLOSE[st], "candidates": []}, {}, "senate")
        assert f'href="{o["office_url"]}" target="_blank" rel="noopener"' in html, st
        assert html.index("Election office:") > html.index("Published race ratings"), st
    assert M.ELECTION_OFFICES["DC"]["office_name"] == "DC Board of Elections"

def test_vote_gov_line():
    assert H.VOTE_GOV_TEXT == "Confirm your polling place and hours with your state election office"
    assert 'href="https://vote.gov" target="_blank" rel="noopener"' in H.VOTE_GOV_LINE
    for w in ("verified", "first", "official results"):
        assert all(w not in (o["office_name"]).lower() for o in M.ELECTION_OFFICES.values()), w

def test_render_page_lines():
    races = [{"state": "TX", "label": "Texas", "state_name": "Texas", "office": "senate", "consensus": {}, "poll_close": M.POLL_CLOSE["TX"], "candidates": []},
             {"state": "DC", "label": "District of Columbia", "state_name": "District of Columbia", "office": "governor", "consensus": {}, "poll_close": M.POLL_CLOSE["DC"], "candidates": []}]
    orig, H._wire_items = M.summary, H._wire_items
    M.summary = lambda: (200, {"races": races, "house": []})
    try: out = H.render()
    finally: M.summary = orig
    page = out if isinstance(out, str) else str(out)
    assert page.count(H.VOTE_GOV_TEXT) == 3   # where-to-vote, Senate and Governor sections
    assert M.ELECTION_OFFICES["DC"]["office_url"] in page and M.ELECTION_OFFICES["TX"]["office_url"] in page

if __name__ == "__main__":
    for f in (test_all_51, test_last_and_first_match, test_texas_render, test_county_caveat, test_office_links, test_vote_gov_line, test_render_page_lines): f(); print("ok", f.__name__)
