"""Wikidata connector (Layer 1) — biographical enrichment for player profiles.

Wikidata (CC0, free) complements event data with what StatsBomb open data does
not carry: **birth date, height, position, citizenship**. This connector maps
the public MediaWiki API onto a small, provenance-carrying bio record:

    search "Lamine Yamal" -> entity filtered to *association football player*
    (occupation P106 = Q937857 — never a same-named non-footballer) ->
    claims P569 (birth date), P2048 (height), P413 (position), P27 (country)

Honesty rules, as everywhere in FUT-K:

* A player with no confident Wikidata match gets **no bio** — never the wrong
  person's. The occupation filter is mandatory; label-only hits are rejected.
* Every record carries ``source="wikidata"``, the matched QID and the fetch
  date, so a claim can always be traced and re-checked.
* An on-disk JSON cache (one file per query) means the same fact is **never
  downloaded twice** across runs.

Standard-library only; ``http_get`` is injectable so mapping is tested offline.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "FUT-K/0.1 (open-source football research; AGPL)"
FOOTBALLER_QID = "Q937857"  # occupation: association football player

# Common football-position QIDs -> readable labels (documented, extensible).
POSITION_LABELS = {
    "Q201330": "goalkeeper",
    "Q336286": "defender",
    "Q193592": "midfielder",
    "Q280658": "forward",
    "Q11681748": "winger",
    "Q1048902": "centre-back",
    "Q1055206": "full-back",
    "Q6642741": "defensive midfielder",
    "Q2643686": "attacking midfielder",
    "Q484876": "striker",
}


def _http_get_json(url: str, timeout: int = 30, retries: int = 4) -> dict:
    """GET+parse with polite backoff: 429/503 honor Retry-After (capped)."""
    last: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 503):
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                wait = min(30.0, float(retry_after)) if retry_after else 2.0 * (attempt + 1)
            except ValueError:
                wait = 2.0 * (attempt + 1)
            time.sleep(wait)
    raise last  # type: ignore[misc]


def _first_value(claims: dict, pid: str):
    for c in claims.get(pid, []):
        dv = c.get("mainsnak", {}).get("datavalue")
        if dv is not None:
            return dv.get("value")
    return None


def _qid(value) -> str | None:
    return value.get("id") if isinstance(value, dict) else None


class WikidataSource:
    """Bio lookups over the Wikidata API, with a never-download-twice cache."""

    name = "wikidata"
    base_trust = 0.85  # crowd-curated; strong on bios, always carries the QID

    def __init__(self, cache_dir: str | None = None, *, http_get=None,
                 sleep_seconds: float = 0.0) -> None:
        self.cache_dir = cache_dir
        self._http_get = http_get or _http_get_json
        self._sleep = sleep_seconds  # polite spacing for batch runs

    # -- cached transport ---------------------------------------------------- #
    def _cached(self, kind: str, key: str, fetch) -> dict:
        path = None
        if self.cache_dir:
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
            path = os.path.join(self.cache_dir, f"{kind}_{digest}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
        data = fetch()
        if self._sleep:
            time.sleep(self._sleep)
        if path:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        return data

    # -- API steps ----------------------------------------------------------- #
    def search(self, name: str) -> list[dict]:
        q = urllib.parse.urlencode({
            "action": "wbsearchentities", "search": name, "language": "en",
            "format": "json", "limit": 5,
        })
        return self._cached("search", name,
                            lambda: self._http_get(f"{API}?{q}")).get("search", [])

    def entity(self, qid: str) -> dict:
        q = urllib.parse.urlencode({
            "action": "wbgetentities", "ids": qid,
            "props": "claims|labels", "languages": "en", "format": "json",
        })
        data = self._cached("entity", qid, lambda: self._http_get(f"{API}?{q}"))
        return data.get("entities", {}).get(qid, {})

    def labels(self, qids: list[str]) -> dict:
        """Readable English labels for a batch of QIDs (one cached call)."""
        wanted = sorted({q for q in qids if q})
        if not wanted:
            return {}
        q = urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(wanted),
            "props": "labels", "languages": "en", "format": "json",
        })
        data = self._cached("labels", ",".join(wanted),
                            lambda: self._http_get(f"{API}?{q}"))
        out = {}
        for qid, ent in data.get("entities", {}).items():
            label = ent.get("labels", {}).get("en", {}).get("value")
            if label:
                out[qid] = label
        return out

    # -- the product: one honest bio record ----------------------------------- #
    def bio_for_name(self, name: str) -> dict | None:
        """The bio of the *footballer* named ``name``, or None.

        Scans search hits and returns the first whose occupation (P106)
        includes association-football-player — a same-named given name, list
        article or musician is skipped, and no hit means no bio (never a
        guess).
        """
        for hit in self.search(name):
            qid = hit.get("id")
            if not qid:
                continue
            ent = self.entity(qid)
            claims = ent.get("claims", {})
            occupations = {
                _qid(c.get("mainsnak", {}).get("datavalue", {}).get("value"))
                for c in claims.get("P106", [])
                if c.get("mainsnak", {}).get("datavalue")
            }
            if FOOTBALLER_QID not in occupations:
                continue

            dob = _first_value(claims, "P569")
            height = _first_value(claims, "P2048")
            pos_qid = _qid(_first_value(claims, "P413"))
            country_qid = _qid(_first_value(claims, "P27"))
            birth_date = None
            if isinstance(dob, dict) and dob.get("time"):
                birth_date = dob["time"].lstrip("+")[:10]  # +2007-07-13T.. -> 2007-07-13
            height_cm = None
            if isinstance(height, dict) and height.get("amount"):
                try:
                    metres = float(height["amount"])
                    height_cm = round(metres * 100) if metres < 3 else round(metres)
                except ValueError:
                    height_cm = None

            country = None
            if country_qid:
                country = self.labels([country_qid]).get(country_qid)
            position = POSITION_LABELS.get(pos_qid) if pos_qid else None

            return {
                "name": name,
                "qid": qid,
                "birth_date": birth_date,
                "height_cm": height_cm,
                "position": position or pos_qid,
                "citizenship": country or country_qid,
                "source": self.name,
            }
        return None
