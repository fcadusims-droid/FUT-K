"""Wikidata connector — offline mapping tests (injected transport).

The fixture mirrors the real API shapes measured live (wbsearchentities +
wbgetentities): a same-named *given name* entity appears before the footballer,
so the occupation filter is what keeps the wrong person out.
"""

from __future__ import annotations

from fie.sources.wikidata import FOOTBALLER_QID, WikidataSource

SEARCH = {"search": [
    {"id": "Q118132466", "label": "Lamine Yamal", "description": "male given name"},
    {"id": "Q113704154", "label": "Lamine Yamal", "description": "Spanish footballer"},
]}

GIVEN_NAME_ENTITY = {"entities": {"Q118132466": {"claims": {
    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q12308941"}}}}],
}}}}

FOOTBALLER_ENTITY = {"entities": {"Q113704154": {"claims": {
    "P106": [{"mainsnak": {"datavalue": {"value": {"id": FOOTBALLER_QID}}}}],
    "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+2007-07-13T00:00:00Z"}}}}],
    "P2048": [{"mainsnak": {"datavalue": {"value": {"amount": "+1.78"}}}}],
    "P413": [{"mainsnak": {"datavalue": {"value": {"id": "Q11681748"}}}}],
    "P27": [{"mainsnak": {"datavalue": {"value": {"id": "Q29"}}}}],
}}}}

LABELS = {"entities": {"Q29": {"labels": {"en": {"value": "Spain"}}}}}


def _router(calls=None):
    def http_get(url):
        if calls is not None:
            calls.append(url)
        if "wbsearchentities" in url:
            return SEARCH
        if "Q118132466" in url:
            return GIVEN_NAME_ENTITY
        if "Q113704154" in url:
            return FOOTBALLER_ENTITY
        if "Q29" in url:
            return LABELS
        raise AssertionError(f"unexpected url {url}")
    return http_get


def test_bio_skips_the_given_name_and_maps_the_footballer():
    src = WikidataSource(http_get=_router())
    bio = src.bio_for_name("Lamine Yamal")
    assert bio == {
        "name": "Lamine Yamal", "qid": "Q113704154",
        "birth_date": "2007-07-13", "height_cm": 178,
        "position": "winger", "citizenship": "Spain", "source": "wikidata",
    }


def test_no_footballer_match_returns_none_never_a_guess():
    src = WikidataSource(http_get=lambda url: (
        {"search": [{"id": "Q118132466"}]} if "wbsearchentities" in url
        else GIVEN_NAME_ENTITY))
    assert src.bio_for_name("Lamine Yamal") is None


def test_disk_cache_never_downloads_twice(tmp_path):
    calls: list = []
    src = WikidataSource(cache_dir=str(tmp_path), http_get=_router(calls))
    first = src.bio_for_name("Lamine Yamal")
    n = len(calls)
    assert n > 0
    second = src.bio_for_name("Lamine Yamal")   # every step served from cache
    assert second == first
    assert len(calls) == n
