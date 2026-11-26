"""'Storm' as a verb is a raid, not weather (Matt, Nov 25 2026 9:27 PM ET: "Israeli occupation forces storm a
Palestinian residential building ... Nablus" was filed as Natural disaster with a NOAA hurricane photo and #Storm).
Weather needs weather context (tropical/winter storm, thunderstorm, storm surge, hurricane, ...); bare storm/stormed/
storming next to forces, police, troops, settlers or protesters is a raid. Display only: never changes scanner data."""
import re

STORM_VERB = re.compile(
    r"\b(?:stormed|storming)\b(?!\s+(?:surge|warning|watch|system|front|season|clouds?))"
    r"|\b(?:forces|troops|police|policemen|soldiers|settlers|army|military|protesters|protestors|rioters|militants|gunmen|"
    r"officers|commandos|crowds?|mobs?|demonstrators|fighters|raiders|agents|occupation|IDF|soldier|squads?|units?)\s+"
    r"(?:\w+\s+){0,2}?storms?\b(?!\s+(?:surge|warning|watch|system|front|season|clouds?))", re.I)
_SOFT_CATS = {"", "natural disaster", "weather", "other"}

def is_raid(text):
    return bool(STORM_VERB.search(text or ""))

def strip(text):
    """Text with storm-as-verb removed, for weather/hazard matching."""
    return STORM_VERB.sub(" ", text or "")

def fix_category(category, title):
    """Stored category for display: a raid misfiled as natural disaster/weather/other is war/conflict."""
    c = (category or "").strip()
    if c.lower() in _SOFT_CATS and is_raid(title):
        return "war/conflict"
    return category
