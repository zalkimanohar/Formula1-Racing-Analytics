"""Component A - persistent identifiers for the key entities (drivers, constructors, circuits).

Every reference record already carries an English Wikipedia URL. The Wikipedia API resolves each
page (following redirects) to its Wikidata item (QID), a persistent, resolvable identifier
(https://www.wikidata.org/entity/Q...). Results are cached in data/reference/wikidata_crosswalk.csv
and reused, so later runs work offline and return identical identifiers.

The module also queries the Research Organization Registry (ROR) for the publishing institution.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request

import pandas as pd

from src import config

USER_AGENT = ("F1-DataManagement-StudentProject/1.0 "
              "(educational use; https://github.com/zalkimanohar/Formula1-Racing-Analytics)")
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
ROR_API = "https://api.ror.org/v2/organizations"
BATCH_SIZE = 50
PAUSE_SECONDS = 1.0

CROSSWALK_CSV = config.REFERENCE_DIR / "wikidata_crosswalk.csv"
ROR_JSON = config.REFERENCE_DIR / "ror_candidates.json"
ROR_CSV = config.REFERENCE_DIR / "ror_candidates.csv"
ZENODO_RECORD = "23416916"
ZENODO_JSON = config.REFERENCE_DIR / "zenodo_source_record.json"
ROR_QUERIES = ("SRH University", "SRH Hochschule", "SRH Berlin University of Applied Sciences")

CROSSWALK_COLUMNS = ["entity_type", "entity_id", "source_url", "wikipedia_url", "wikidata_qid",
                     "lookup_status", "resolved_title"]


def normalise_url(url: str) -> str:
    return url.replace("http://", "https://", 1) if isinstance(url, str) else url


def title_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    return urllib.parse.unquote(path.split("/wiki/", 1)[1]).replace("_", " ")


def http_get_json(url: str, params: dict) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def entity_table() -> pd.DataFrame:
    drivers = pd.read_csv(config.RAW_DRIVERS_CSV, dtype=str)
    constructors = pd.read_csv(config.RAW_CONSTRUCTORS_CSV, dtype=str)
    circuits = pd.read_csv(config.RAW_CIRCUITS_CSV, dtype=str)
    frames = [
        pd.DataFrame({"entity_type": "driver", "entity_id": drivers["driverId"], "source_url": drivers["url"]}),
        pd.DataFrame({"entity_type": "constructor", "entity_id": constructors["constructorId"],
                      "source_url": constructors["url"]}),
        pd.DataFrame({"entity_type": "circuit", "entity_id": circuits["circuitId"], "source_url": circuits["url"]}),
    ]
    table = pd.concat(frames, ignore_index=True)
    table["wikipedia_url"] = table["source_url"].map(normalise_url)
    return table


def resolve_titles(titles: list[str]) -> dict[str, tuple[str | None, str, str | None]]:
    """Map each requested title to (qid, status, resolved_title)."""
    resolved: dict[str, tuple[str | None, str, str | None]] = {}
    for start in range(0, len(titles), BATCH_SIZE):
        batch = titles[start:start + BATCH_SIZE]
        data = http_get_json(WIKIPEDIA_API, {
            "action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1,
            "titles": "|".join(batch), "format": "json", "formatversion": 2,
        })
        query = data.get("query", {})
        normalised = {n["from"]: n["to"] for n in query.get("normalized", [])}
        redirects = {r["from"]: r["to"] for r in query.get("redirects", [])}
        pages = {p["title"]: p for p in query.get("pages", [])}
        for title in batch:
            step1 = normalised.get(title, title)
            final = redirects.get(step1, step1)
            page = pages.get(final)
            if page is None or page.get("missing") or page.get("invalid"):
                resolved[title] = (None, "page_missing", final)
                continue
            qid = page.get("pageprops", {}).get("wikibase_item")
            status = "resolved_via_redirect" if step1 in redirects else "resolved"
            resolved[title] = (qid, status if qid else "no_wikidata_item", final)
        time.sleep(PAUSE_SECONDS)
    return resolved


def build_crosswalk() -> pd.DataFrame:
    table = entity_table()
    with_url = table["wikipedia_url"].notna()
    titles = sorted({title_from_url(u) for u in table.loc[with_url, "wikipedia_url"]})
    lookup = resolve_titles(titles)

    def row_result(url):
        if not isinstance(url, str):
            return pd.Series([None, "no_url", None])
        return pd.Series(lookup[title_from_url(url)])

    table[["wikidata_qid", "lookup_status", "resolved_title"]] = table["wikipedia_url"].apply(row_result)
    return table[CROSSWALK_COLUMNS]


def query_ror() -> pd.DataFrame:
    rows, raw = [], {}
    for q in ROR_QUERIES:
        data = http_get_json(ROR_API, {"query": q})
        raw[q] = data
        for item in data.get("items", []):
            names = item.get("names", [])
            display = next((n["value"] for n in names if "ror_display" in n.get("types", [])),
                           names[0]["value"] if names else None)
            location = (item.get("locations") or [{}])[0].get("geonames_details", {})
            rows.append({
                "query": q, "ror_id": item.get("id"), "name": display,
                "aliases_labels": "; ".join(n["value"] for n in names if "ror_display" not in n.get("types", [])),
                "city": location.get("name"), "country": location.get("country_name"),
                "status": item.get("status"), "types": "; ".join(item.get("types", [])),
            })
        time.sleep(PAUSE_SECONDS)
    ROR_JSON.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    table = pd.DataFrame(rows).drop_duplicates("ror_id")
    table.to_csv(ROR_CSV, index=False)
    return table


def coverage(crosswalk: pd.DataFrame) -> pd.DataFrame:
    summary = crosswalk.assign(has_qid=crosswalk["wikidata_qid"].notna()).groupby("entity_type").agg(
        records=("entity_type", "size"), with_url=("source_url", lambda s: s.notna().sum()),
        with_qid=("has_qid", "sum"))
    summary["qid_coverage_percent"] = (100 * summary["with_qid"] / summary["records"]).round(1)
    return summary.reset_index()


def zenodo_source_record(refresh: bool = False) -> dict:
    """The group's Zenodo deposit of the raw archive (Manohar Zalki, 16 Oct 2026): the DOI of data/source.

    The record's file checksum is compared with the local archive, so the DOI is only used as the identifier of
    the source if the two are byte-identical. Cached in data/reference/ for offline runs.
    """
    if ZENODO_JSON.exists() and not refresh:
        return json.loads(ZENODO_JSON.read_text(encoding="utf-8"))
    rec = http_get_json(f"https://zenodo.org/api/records/{ZENODO_RECORD}", {})
    meta = rec.get("metadata", {})
    local = config.SOURCE_ARCHIVE.read_bytes()
    local_md5 = hashlib.md5(local).hexdigest()
    files = [{"key": f["key"], "size": f["size"], "checksum": f["checksum"]} for f in rec.get("files", [])]
    match = any(f["checksum"] == f"md5:{local_md5}" and f["size"] == len(local) for f in files)
    out = {
        "doi": rec.get("doi"), "doi_url": f"https://doi.org/{rec.get('doi')}", "record_url": rec.get("links", {}).get("self_html"),
        "title": meta.get("title"), "creators": [c.get("name") for c in meta.get("creators", [])],
        "publication_date": meta.get("publication_date"), "resource_type": meta.get("resource_type", {}).get("type"),
        "declared_license": (meta.get("license") or {}).get("id"), "keywords": meta.get("keywords") or [],
        "files": files, "local_archive": config.SOURCE_ARCHIVE.name, "local_size": len(local), "local_md5": local_md5,
        "local_sha256": hashlib.sha256(local).hexdigest(), "byte_identical": match,
        "source_license_required": "CC-BY-NC-SA-4.0",
        "license_conflict": (meta.get("license") or {}).get("id", "").lower() != "cc-by-nc-sa-4.0",
        "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    ZENODO_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def run(refresh: bool = False) -> pd.DataFrame:
    config.ensure_dirs()
    z = zenodo_source_record(refresh=refresh)
    print(f"[PID] source archive DOI {z['doi']} (Zenodo, {z['publication_date']}): byte-identical "
          f"{z['byte_identical']}; declared licence {z['declared_license']}"
          + (" - conflicts with the source terms (CC BY-NC-SA 4.0)" if z["license_conflict"] else ""))
    if CROSSWALK_CSV.exists() and not refresh:
        crosswalk = pd.read_csv(CROSSWALK_CSV, dtype=str)
        print(f"[PID] using cached crosswalk {CROSSWALK_CSV.name}")
    else:
        crosswalk = build_crosswalk()
        crosswalk.to_csv(CROSSWALK_CSV, index=False)
    if refresh or not ROR_CSV.exists():
        query_ror()
    cov = coverage(crosswalk)
    cov.to_csv(config.FAIR_DIR / "pid_coverage.csv", index=False)
    print(cov.to_string(index=False))
    print(crosswalk["lookup_status"].value_counts().to_string())
    return crosswalk


if __name__ == "__main__":
    run()
