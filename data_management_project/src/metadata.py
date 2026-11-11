"""Component A - metadata record for the curated dataset.

Generates, from the cleaned CSVs and src/schema.py:
  * DataCite Metadata Schema 4.5 record (JSON and XML; the XML is validated against the official XSD)
  * schema.org Dataset JSON-LD (Google Dataset Search, variableMeasured from the data dictionary)
  * Frictionless Data Package descriptor (datapackage.json) with Table Schemas and keys
  * W3C PROV-O provenance graph (JSON-LD) from the source manifest and the cleaning audit log
  * data dictionary (CSV + Markdown) and a data licence notice

Row counts, coverage and SHA-256 checksums are computed at run time, so the record always
describes the files actually delivered.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from src import config
from src.schema import RESULTS_COLUMNS, RESULTS_PRIMARY_KEY

USER_AGENT = ("F1-DataManagement-StudentProject/1.0 "
              "(educational use; https://github.com/zalkimanohar/Formula1-Racing-Analytics)")

# ---- Values the group must confirm before deposit -------------------------------------------
DOI_PLACEHOLDER = "10.5281/zenodo.TO-BE-MINTED"
VERSION = "1.0.0"
REPOSITORY_URL = "https://github.com/zalkimanohar/Formula1-Racing-Analytics"
PUBLICATION_BASE_URL = (
    "https://raw.githubusercontent.com/zalkimanohar/Formula1-Racing-Analytics/main/"
    "data_management_project/data/cleaned/")
CREATORS = [{"family_name": m["family_name"], "given_name": m["given_name"], "orcid": m["orcid"],
             "role": "Author (joint work on all components)" if config.JOINT_WORK else m["title"]}
            for m in config.TEAM]
INSTITUTION = {"name": "SRH University [campus and ROR to be confirmed]", "ror": None,
               "ror_candidate": "https://ror.org/00g07sz63 (SRH University of Applied Sciences Heidelberg)"}
# ---------------------------------------------------------------------------------------------

TITLE = "Formula 1 World Championship Race Results 1950-2025: Curated and Quality-Assessed Dataset"
SUBTITLE = "Cleaned, FAIR-documented derivative of the Ergast/Jolpica-F1 race results"
LICENSE = {
    "name": "Creative Commons Attribution Non Commercial Share Alike 4.0 International",
    "spdx": "CC-BY-NC-SA-4.0",
    "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "legalcode": "https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode",
}
SOURCES = {
    "jolpica_api": {"url": "https://api.jolpi.ca/ergast/f1/", "name": "Jolpica-F1 Ergast-compatible API",
                    "type": "Service", "relation": "IsDerivedFrom"},
    "ergast": {"url": "http://ergast.com/mrd/", "name": "Ergast Developer API (discontinued)",
               "type": "Service", "relation": "IsDerivedFrom"},
    "raw_archive": {"url": "https://doi.org/10.5281/zenodo.23416916", "identifier": "10.5281/zenodo.23416916",
                    "id_type": "DOI", "name": "racing_f1_data.zip (raw archive on Zenodo, DOI 10.5281/zenodo.23416916)",
                    "type": "Dataset", "relation": "IsDerivedFrom",
                    "copy": f"{REPOSITORY_URL}/blob/main/racing_f1_data.zip"},
    "repository": {"url": REPOSITORY_URL, "name": "Formula1-Racing-Analytics repository",
                   "type": "Software", "relation": "IsSupplementTo"},
    "kaggle": {"url": "https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020",
               "name": "Formula 1 World Championship (1950 - 2024), Kaggle mirror of Ergast",
               "type": "Dataset", "relation": "References"},
}
SUBJECTS = [
    ("Formula One", "Q1968"), ("auto racing", "Q5386"), ("sport", "Q349"),
]
KEYWORDS = ["Formula One", "motorsport", "race results", "sports analytics", "data quality",
            "data cleaning", "FAIR data", "Ergast"]

CLEAN_FILES = {
    "f1_race_results_clean": config.CLEAN_RESULTS_CSV,
    "races_clean": config.CLEAN_RACES_CSV,
    "circuits_clean": config.CLEAN_CIRCUITS_CSV,
    "drivers_clean": config.CLEAN_DRIVERS_CSV,
    "constructors_clean": config.CLEAN_CONSTRUCTORS_CSV,
}
RAW_FILES = {
    "f1_race_results_raw": config.RAW_RESULTS_CSV,
    "races_raw": config.RAW_RACES_CSV,
    "circuits_raw": config.RAW_CIRCUITS_CSV,
    "drivers_raw": config.RAW_DRIVERS_CSV,
    "constructors_raw": config.RAW_CONSTRUCTORS_CSV,
}
TABLE_DESCRIPTIONS = {
    "f1_race_results_clean": "One row per driver entry per World Championship Grand Prix (fact table).",
    "races_clean": "One row per Grand Prix, including the scheduled 2026 rounds without results.",
    "circuits_clean": "One row per circuit with ISO country code, coordinates and Wikidata QID.",
    "drivers_clean": "One row per driver with ISO nationality code and Wikidata QID.",
    "constructors_clean": "One row per constructor entry (chassis-engine combination) with Wikidata QID.",
}
REFERENCE_DESCRIPTIONS = {
    "race_id": "Grand Prix identifier: season and two-digit round (YYYY_RR).",
    "season": "Championship season (year).", "round": "Round number within the season.",
    "race_name": "Grand Prix name in title case.", "race_date": "Race day (ISO 8601).",
    "circuit_id": "Circuit identifier (Ergast convention).",
    "wikipedia_url": "English Wikipedia page (https).",
    "wikidata_qid": "Wikidata item identifier (persistent identifier of the entity).",
    "has_results": "True when the results table contains this race.",
    "circuit_name": "Circuit name in title case.", "locality": "City or locality.",
    "country": "Country name (abbreviations expanded).", "country_iso3": "ISO 3166-1 alpha-3 country code.",
    "latitude": "WGS84 latitude (decimal degrees).", "longitude": "WGS84 longitude (decimal degrees).",
    "driver_id": "Driver identifier, lowercase snake case.", "given_name": "Given name in title case.",
    "family_name": "Family name in title case.", "full_name": "Given and family name.",
    "date_of_birth": "Date of birth (ISO 8601).", "nationality": "Nationality (demonym, title case).",
    "nationality_iso3": "Nationality as ISO 3166-1 alpha-3 (ISO 3166-3 for former states).",
    "constructor_id": "Constructor identifier (Ergast convention).",
    "constructor_name": "Constructor name.",
}

DATACITE_XSD_URL = "https://schema.datacite.org/meta/kernel-4.5/metadata.xsd"
XSD_CACHE = config.REFERENCE_DIR / "xsd"
# Short folder per host keeps every cached path well under the 260-character Windows limit.
XSD_HOSTS = {"schema.datacite.org": "datacite", "www.w3.org": "w3"}
DATACITE_NS = "http://datacite.org/schema/kernel-4"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


# ---------------------------------------------------------------- inputs -----------------------

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_inputs(allow_raw: bool = False) -> tuple[dict[str, Path], bool]:
    """Return the files to describe; fail clearly when the cleaned CSVs are not there yet."""
    missing = [str(p) for p in CLEAN_FILES.values() if not p.exists()]
    if not missing:
        return dict(CLEAN_FILES), False
    if not allow_raw:
        raise FileNotFoundError("Cleaned CSVs not found - run the cleaning step (src.cleaning) first. "
                                f"Missing: {missing}")
    print("[metadata] cleaned CSVs missing - structural test on the RAW files only")
    return dict(RAW_FILES), True


def file_facts(files: dict[str, Path]) -> list[dict]:
    facts = []
    for name, path in files.items():
        df = pd.read_csv(path, low_memory=False)
        facts.append({"name": name, "path": path, "file_name": path.name, "rows": len(df),
                      "columns": len(df.columns), "bytes": path.stat().st_size, "sha256": sha256_file(path),
                      "frame": df})
    return facts


def dataset_facts(facts: list[dict], raw_mode: bool) -> dict:
    results = facts[0]["frame"]
    date_col = "race_date" if "race_date" in results.columns else "date"
    dates = pd.to_datetime(results[date_col], errors="coerce").dropna()
    out = {"rows": len(results), "start": dates.min().date().isoformat(), "end": dates.max().date().isoformat(),
           "raw_mode": raw_mode}
    if not raw_mode:
        out.update(seasons=int(results["season"].nunique()), races=int(results["race_id"].nunique()),
                   drivers=int(results["driver_id"].nunique()),
                   constructors=int(results["constructor_id"].nunique()),
                   circuits=int(results["circuit_id"].nunique()),
                   countries=int(results["circuit_country_iso3"].nunique()))
    with zipfile.ZipFile(config.SOURCE_ARCHIVE) as zf:
        stamps = [date(*i.date_time[:3]) for i in zf.infolist() if not i.is_dir()]
    first, last = min(stamps).isoformat(), max(stamps).isoformat()
    out["collected"] = first if first == last else f"{first}/{last}"
    return out


def circuit_points(raw_mode: bool) -> pd.DataFrame:
    if raw_mode:
        c = pd.read_csv(config.RAW_CIRCUITS_CSV).rename(columns={"circuitName": "circuit_name", "lat": "latitude",
                                                                   "long": "longitude"})
    else:
        c = pd.read_csv(config.CLEAN_CIRCUITS_CSV)
    c = c.dropna(subset=["latitude", "longitude"]).drop_duplicates(subset=["circuit_name"])
    return c


# ---------------------------------------------------------------- DataCite ---------------------

def descriptions(ds: dict) -> list[dict]:
    if ds["raw_mode"]:
        abstract = f"Structural test record built from the raw files ({ds['rows']} rows)."
    else:
        abstract = (
            f"Race results of every FIA Formula One World Championship Grand Prix from {ds['start']} to "
            f"{ds['end']} ({ds['seasons']} seasons, {ds['races']} Grands Prix, {ds['rows']:,} driver entries, "
            f"{ds['drivers']} drivers, {ds['constructors']} constructor entries, {ds['circuits']} circuits in "
            f"{ds['countries']} countries). The dataset is a cleaned, documented derivative of the Ergast "
            "database as served by the Jolpica-F1 API. Duplicates, missing keys, sentinel values, inconsistent "
            "identifiers and free-text categories were resolved; legitimate historical shared drives were kept "
            "and flagged; ISO 3166 country codes and Wikidata identifiers were added.")
    methods = (
        "Extracted from racing_f1_data.zip (Zenodo DOI 10.5281/zenodo.23416916; SHA-256 "
        + config.SOURCE_ARCHIVE_SHA256 + ") without modifying "
        "values, profiled across completeness, uniqueness, validity, consistency, accuracy and timeliness, "
        "and cleaned with a reproducible Python/pandas pipeline that logs before/after statistics for every "
        "step. Source code, audit log and quality report are part of the package.")
    technical = (
        "UTF-8 encoded CSV (RFC 4180), comma separated, header row, ISO 8601 dates. Primary key of the fact "
        f"table: {', '.join(RESULTS_PRIMARY_KEY)}. Column definitions in data_dictionary.csv and datapackage.json.")
    other = ("Points follow the scoring rules of each season; use points_normalised for cross-era comparisons. "
             "Indianapolis 500 rounds (1950-1960) are flagged with is_indy500. The raw archive this package is "
             "derived from has the DOI 10.5281/zenodo.23416916; the curated package is prepared for deposit in "
             "Zenodo as its own record, and the DOI shown for it is a placeholder until minted.")
    return [{"description": abstract, "descriptionType": "Abstract"},
            {"description": methods, "descriptionType": "Methods"},
            {"description": technical, "descriptionType": "TechnicalInfo"},
            {"description": other, "descriptionType": "Other"}]


def datacite_attributes(ds: dict, facts: list[dict], points: pd.DataFrame) -> dict:
    prefix, suffix = DOI_PLACEHOLDER.split("/", 1)
    return {
        "doi": DOI_PLACEHOLDER, "prefix": prefix, "suffix": suffix,
        "creators": [{
            "name": f"{c['family_name']}, {c['given_name']}", "nameType": "Personal",
            "givenName": c["given_name"], "familyName": c["family_name"],
            "nameIdentifiers": [{"nameIdentifier": c["orcid"], "nameIdentifierScheme": "ORCID",
                                 "schemeUri": "https://orcid.org"}],
            "affiliation": [{"name": INSTITUTION["name"]}],
        } for c in CREATORS],
        "titles": [{"title": TITLE, "lang": "en"}, {"title": SUBTITLE, "titleType": "Subtitle", "lang": "en"}],
        "publisher": {"name": "Zenodo"},
        "publicationYear": str(date.today().year),
        "subjects": [{"subject": s, "subjectScheme": "Wikidata", "schemeUri": "https://www.wikidata.org/wiki/",
                      "valueUri": f"https://www.wikidata.org/wiki/{q}", "lang": "en"} for s, q in SUBJECTS]
                    + [{"subject": k, "lang": "en"} for k in KEYWORDS if k not in {s for s, _ in SUBJECTS}],
        "contributors": [
            {"name": "Ergast Developer API", "nameType": "Organizational", "contributorType": "DataCollector"},
            {"name": "Jolpica-F1", "nameType": "Organizational", "contributorType": "Distributor"},
            {"name": INSTITUTION["name"], "nameType": "Organizational", "contributorType": "HostingInstitution"},
        ],
        "dates": [{"date": date.today().isoformat(), "dateType": "Created"},
                  {"date": ds["collected"], "dateType": "Collected",
                   "dateInformation": "Modification dates of the files in the raw archive"},
                  {"date": f"{ds['start']}/{ds['end']}", "dateType": "Other",
                   "dateInformation": "Temporal coverage: first and last race day in the dataset"}],
        "language": "en",
        "types": {"resourceTypeGeneral": "Dataset", "resourceType": "Tabular sports results"},
        "relatedIdentifiers": [{"relatedIdentifier": s.get("identifier", s["url"]),
                                "relatedIdentifierType": s.get("id_type", "URL"),
                                "relationType": s["relation"], "resourceTypeGeneral": s["type"]}
                               for s in SOURCES.values()],
        "sizes": [f"{f['file_name']}: {f['rows']} rows, {f['bytes']} bytes" for f in facts],
        "formats": ["text/csv", "application/ld+json", "application/xml"],
        "version": VERSION,
        "rightsList": [{"rights": LICENSE["name"], "rightsUri": LICENSE["legalcode"],
                        "rightsIdentifier": LICENSE["spdx"], "rightsIdentifierScheme": "SPDX",
                        "schemeUri": "https://spdx.org/licenses/", "lang": "en"}],
        "descriptions": descriptions(ds),
        "geoLocations": [{"geoLocationPlace": "Worldwide (all Formula One World Championship circuits)"}] + [
            {"geoLocationPlace": f"{r['circuit_name']}, {r.get('locality', '')}, {r.get('country', '')}".strip(", "),
             "geoLocationPoint": {"pointLongitude": round(float(r["longitude"]), 5),
                                  "pointLatitude": round(float(r["latitude"]), 5)}}
            for _, r in points.iterrows()],
    }


def datacite_xml(attrs: dict) -> ET.ElementTree:
    ET.register_namespace("", DATACITE_NS)
    ET.register_namespace("xsi", XSI_NS)
    q = lambda tag: f"{{{DATACITE_NS}}}{tag}"  # noqa: E731
    xml_lang = "{http://www.w3.org/XML/1998/namespace}lang"
    root = ET.Element(q("resource"), {f"{{{XSI_NS}}}schemaLocation":
                                      f"{DATACITE_NS} http://schema.datacite.org/meta/kernel-4.5/metadata.xsd"})
    ET.SubElement(root, q("identifier"), identifierType="DOI").text = attrs["doi"]
    creators = ET.SubElement(root, q("creators"))
    for c in attrs["creators"]:
        el = ET.SubElement(creators, q("creator"))
        ET.SubElement(el, q("creatorName"), nameType="Personal").text = c["name"]
        ET.SubElement(el, q("givenName")).text = c["givenName"]
        ET.SubElement(el, q("familyName")).text = c["familyName"]
        for n in c["nameIdentifiers"]:
            ET.SubElement(el, q("nameIdentifier"), nameIdentifierScheme=n["nameIdentifierScheme"],
                          schemeURI=n["schemeUri"]).text = n["nameIdentifier"]
        for a in c["affiliation"]:
            ET.SubElement(el, q("affiliation")).text = a["name"]
    titles = ET.SubElement(root, q("titles"))
    for t in attrs["titles"]:
        extra = {"titleType": t["titleType"]} if "titleType" in t else {}
        ET.SubElement(titles, q("title"), {xml_lang: t["lang"], **extra}).text = t["title"]
    ET.SubElement(root, q("publisher"), {xml_lang: "en"}).text = attrs["publisher"]["name"]
    ET.SubElement(root, q("publicationYear")).text = attrs["publicationYear"]
    ET.SubElement(root, q("resourceType"), resourceTypeGeneral=attrs["types"]["resourceTypeGeneral"]).text = \
        attrs["types"]["resourceType"]
    subjects = ET.SubElement(root, q("subjects"))
    for s in attrs["subjects"]:
        extra = {k: s[v] for k, v in (("subjectScheme", "subjectScheme"), ("schemeURI", "schemeUri"),
                                      ("valueURI", "valueUri")) if v in s}
        ET.SubElement(subjects, q("subject"), {xml_lang: s["lang"], **extra}).text = s["subject"]
    contributors = ET.SubElement(root, q("contributors"))
    for c in attrs["contributors"]:
        el = ET.SubElement(contributors, q("contributor"), contributorType=c["contributorType"])
        ET.SubElement(el, q("contributorName"), nameType=c["nameType"]).text = c["name"]
    dates = ET.SubElement(root, q("dates"))
    for d in attrs["dates"]:
        extra = {"dateInformation": d["dateInformation"]} if "dateInformation" in d else {}
        ET.SubElement(dates, q("date"), dateType=d["dateType"], **extra).text = d["date"]
    ET.SubElement(root, q("language")).text = attrs["language"]
    related = ET.SubElement(root, q("relatedIdentifiers"))
    for r in attrs["relatedIdentifiers"]:
        ET.SubElement(related, q("relatedIdentifier"), relatedIdentifierType=r["relatedIdentifierType"],
                      relationType=r["relationType"], resourceTypeGeneral=r["resourceTypeGeneral"]).text = \
            r["relatedIdentifier"]
    sizes = ET.SubElement(root, q("sizes"))
    for s in attrs["sizes"]:
        ET.SubElement(sizes, q("size")).text = s
    formats = ET.SubElement(root, q("formats"))
    for f in attrs["formats"]:
        ET.SubElement(formats, q("format")).text = f
    ET.SubElement(root, q("version")).text = attrs["version"]
    rights = ET.SubElement(root, q("rightsList"))
    for r in attrs["rightsList"]:
        ET.SubElement(rights, q("rights"), {xml_lang: r["lang"], "rightsURI": r["rightsUri"],
                                            "rightsIdentifier": r["rightsIdentifier"],
                                            "rightsIdentifierScheme": r["rightsIdentifierScheme"],
                                            "schemeURI": r["schemeUri"]}).text = r["rights"]
    descs = ET.SubElement(root, q("descriptions"))
    for d in attrs["descriptions"]:
        ET.SubElement(descs, q("description"), {xml_lang: "en", "descriptionType": d["descriptionType"]}).text = \
            d["description"]
    geos = ET.SubElement(root, q("geoLocations"))
    for g in attrs["geoLocations"]:
        el = ET.SubElement(geos, q("geoLocation"))
        ET.SubElement(el, q("geoLocationPlace")).text = g["geoLocationPlace"]
        if "geoLocationPoint" in g:
            p = ET.SubElement(el, q("geoLocationPoint"))
            ET.SubElement(p, q("pointLongitude")).text = str(g["geoLocationPoint"]["pointLongitude"])
            ET.SubElement(p, q("pointLatitude")).text = str(g["geoLocationPoint"]["pointLatitude"])
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    return tree


def _fetch_xsd(url: str, cache_root: Path, seen: dict[str, Path]) -> Path:
    """Download an XSD and everything it includes/imports, rewriting locations to local copies."""
    if url in seen:
        return seen[url]
    parsed = urllib.parse.urlparse(url)
    local = cache_root / XSD_HOSTS.get(parsed.netloc, parsed.netloc) / parsed.path.lstrip("/")
    seen[url] = local
    if local.exists():  # cached copies already point at their local includes: no network needed
        return local
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read().decode("utf-8")
    for loc in set(re.findall(r'schemaLocation="([^"]+)"', content)):
        target_url = urllib.parse.urljoin(url, loc)
        target = _fetch_xsd(target_url, cache_root, seen)
        rel = posixpath.relpath(target.as_posix(), local.parent.as_posix())
        content = content.replace(f'schemaLocation="{loc}"', f'schemaLocation="{rel}"')
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(content, encoding="utf-8")
    return local


def validate_datacite_xml(xml_path: Path) -> tuple[bool, str]:
    try:
        from lxml import etree
    except ImportError:
        return False, "lxml not installed - XSD validation skipped"
    try:
        xsd_path = _fetch_xsd(DATACITE_XSD_URL, XSD_CACHE, {})
    except OSError as exc:
        if not XSD_CACHE.exists():
            return False, f"XSD could not be downloaded ({exc}) - validation skipped"
        xsd_path = XSD_CACHE / "datacite" / "meta" / "kernel-4.5" / "metadata.xsd"
    schema = etree.XMLSchema(etree.parse(str(xsd_path)))
    doc = etree.parse(str(xml_path))
    ok = schema.validate(doc)
    log = "valid against DataCite kernel-4.5 XSD" if ok else "; ".join(str(e) for e in schema.error_log)
    return ok, log


# ---------------------------------------------------------------- schema.org --------------------

def schema_org(ds: dict, facts: list[dict], points: pd.DataFrame, attrs: dict) -> dict:
    variables = []
    for c in RESULTS_COLUMNS:
        v = {"@type": "PropertyValue", "name": c.name, "description": c.description}
        if c.unit_or_format:
            v["unitText"] = c.unit_or_format
        if c.allowed_values:
            v["valueReference"] = {"@type": "DefinedTermSet", "name": f"{c.name} vocabulary",
                                   "hasDefinedTerm": [{"@type": "DefinedTerm", "name": a} for a in c.allowed_values]}
        if "ISO 3166" in c.unit_or_format:
            v["propertyID"] = "https://www.iso.org/iso-3166-country-codes.html"
        variables.append(v)
    sources = [{"@type": "Dataset" if s["type"] == "Dataset" else "WebAPI" if s["type"] == "Service"
                else "SoftwareSourceCode", "@id": s["url"], "name": s["name"], "url": s["url"]}
               for k, s in SOURCES.items() if s["relation"] == "IsDerivedFrom"]
    return {
        "@context": {"@vocab": "https://schema.org/", "prov": "http://www.w3.org/ns/prov#"},
        "@type": "Dataset",
        "name": TITLE, "alternateName": SUBTITLE,
        "description": attrs["descriptions"][0]["description"],
        "identifier": [{"@type": "PropertyValue", "propertyID": "DOI", "value": DOI_PLACEHOLDER,
                        "description": "Placeholder - DOI to be minted when the package is deposited in Zenodo"}],
        "url": f"{REPOSITORY_URL}/tree/main/data_management_project",
        "version": VERSION,
        "license": LICENSE["url"],
        "isAccessibleForFree": True,
        "conditionsOfAccess": "Open access; reuse under CC BY-NC-SA 4.0 (attribution, non-commercial, share-alike).",
        "creator": [{"@type": "Person", "givenName": c["given_name"], "familyName": c["family_name"],
                     "identifier": c["orcid"], "roleName": c["role"],
                     "affiliation": {"@type": "Organization", "name": INSTITUTION["name"]}} for c in CREATORS],
        "publisher": {"@type": "Organization", "name": "Zenodo"},
        "dateCreated": date.today().isoformat(),
        "temporalCoverage": f"{ds['start']}/{ds['end']}",
        "spatialCoverage": {"@type": "Place", "name": "Worldwide - Formula One World Championship circuits",
                            "containsPlace": [{"@type": "Place", "name": r["circuit_name"],
                                               "geo": {"@type": "GeoCoordinates",
                                                       "latitude": round(float(r["latitude"]), 5),
                                                       "longitude": round(float(r["longitude"]), 5)}}
                                              for _, r in points.iterrows()]},
        "keywords": KEYWORDS,
        "about": [{"@id": f"http://www.wikidata.org/entity/{q}", "name": s} for s, q in SUBJECTS],
        "inLanguage": "en",
        "isBasedOn": sources,
        "prov:wasDerivedFrom": [{"@id": s["@id"]} for s in sources],
        "measurementTechnique": ["Automated data profiling across six quality dimensions",
                                 "Rule-based, audited data cleaning (Python/pandas)"],
        "variableMeasured": variables,
        "distribution": [{"@type": "DataDownload", "name": f["file_name"], "encodingFormat": "text/csv",
                          "contentUrl": PUBLICATION_BASE_URL + f["file_name"],
                          "contentSize": f"{f['bytes']} bytes", "sha256": f["sha256"],
                          "description": TABLE_DESCRIPTIONS.get(f["name"], "")} for f in facts],
    }


# ---------------------------------------------------------------- Data Package ------------------

FRICTIONLESS_TYPES = {"string": "string", "Int64": "integer", "float": "number", "boolean": "boolean",
                      "date": "date"}


def infer_field(name: str, series: pd.Series) -> dict:
    if name.endswith("date") or name.startswith("date_"):
        ftype = "date"
    elif pd.api.types.is_bool_dtype(series):
        ftype = "boolean"
    elif pd.api.types.is_integer_dtype(series):
        ftype = "integer"
    elif pd.api.types.is_float_dtype(series):
        ftype = "integer" if series.dropna().apply(float.is_integer).all() and name not in {"latitude", "longitude"} \
            else "number"
    else:
        ftype = "string"
    return {"name": name, "type": ftype, "description": REFERENCE_DESCRIPTIONS.get(name, "")}


def datapackage(facts: list[dict], raw_mode: bool) -> dict:
    by_name = {f["name"]: f for f in facts}
    resources = []
    for f in facts:
        df = f["frame"]
        if f["name"] == "f1_race_results_clean":
            fields = [{"name": c.name, "type": FRICTIONLESS_TYPES[c.dtype], "description": c.description,
                       **({"constraints": {"enum": list(c.allowed_values)}} if c.allowed_values else {}),
                       **({"constraints": {"required": True}} if not c.nullable and not c.allowed_values else {})}
                      for c in RESULTS_COLUMNS]
            schema = {"fields": fields, "primaryKey": list(RESULTS_PRIMARY_KEY), "missingValues": [""]}
            fks = []
            for col, table in (("race_id", "races_clean"), ("driver_id", "drivers_clean"),
                               ("constructor_id", "constructors_clean"), ("circuit_id", "circuits_clean")):
                if table in by_name and col in by_name[table]["frame"].columns:
                    fks.append({"fields": col, "reference": {"resource": table, "fields": col}})
            schema["foreignKeys"] = fks
        else:
            fields = [infer_field(c, df[c]) for c in df.columns]
            schema = {"fields": fields, "missingValues": [""]}
            key = {"races_clean": "race_id", "circuits_clean": "circuit_id", "drivers_clean": "driver_id",
                   "constructors_clean": "constructor_id"}.get(f["name"])
            if key and key in df.columns and df[key].is_unique:
                schema["primaryKey"] = [key]
        resources.append({"name": f["name"], "path": f"data/cleaned/{f['file_name']}" if not raw_mode
                          else f"data/raw/{f['file_name']}", "format": "csv", "mediatype": "text/csv",
                          "encoding": "utf-8", "bytes": f["bytes"], "hash": f"sha256:{f['sha256']}",
                          "description": TABLE_DESCRIPTIONS.get(f["name"], ""), "schema": schema})
    return {
        "profile": "tabular-data-package", "name": "f1-race-results-curated", "id": DOI_PLACEHOLDER,
        "title": TITLE, "version": VERSION, "created": date.today().isoformat(),
        "licenses": [{"name": LICENSE["spdx"], "path": LICENSE["url"], "title": LICENSE["name"]}],
        "sources": [{"title": s["name"], "path": s["url"]} for s in SOURCES.values() if s["relation"] == "IsDerivedFrom"],
        "contributors": [{"title": f"{c['given_name']} {c['family_name']}", "role": "author"} for c in CREATORS],
        "keywords": KEYWORDS, "resources": resources,
    }


# ---------------------------------------------------------------- PROV-O ------------------------

def provenance(facts: list[dict], raw_mode: bool) -> dict:
    base = "urn:f1-dm:"
    graph = [
        {"@id": base + "agent/pipeline", "@type": "prov:SoftwareAgent",
         "rdfs:label": "data_management_project pipeline (Python, pandas)"},
        {"@id": SOURCES["jolpica_api"]["url"], "@type": "prov:Entity", "rdfs:label": SOURCES["jolpica_api"]["name"],
         "prov:wasDerivedFrom": {"@id": SOURCES["ergast"]["url"]}},
        {"@id": SOURCES["ergast"]["url"], "@type": "prov:Entity", "rdfs:label": SOURCES["ergast"]["name"]},
        {"@id": base + "entity/racing_f1_data.zip", "@type": "prov:Entity", "rdfs:label": "racing_f1_data.zip",
         "schema:identifier": "https://doi.org/10.5281/zenodo.23416916",
         "prov:atLocation": [SOURCES["raw_archive"]["url"], SOURCES["raw_archive"]["copy"]],
         "schema:sha256": config.SOURCE_ARCHIVE_SHA256,
         "prov:wasDerivedFrom": {"@id": SOURCES["jolpica_api"]["url"]}},
        {"@id": base + "activity/step0_extract", "@type": "prov:Activity",
         "rdfs:label": "Step 0 - flatten the archive to raw CSV without changing values",
         "prov:used": {"@id": base + "entity/racing_f1_data.zip"},
         "prov:wasAssociatedWith": {"@id": base + "agent/pipeline"}},
    ]
    for name, path in RAW_FILES.items():
        if path.exists():
            graph.append({"@id": base + f"entity/{path.name}", "@type": "prov:Entity", "rdfs:label": path.name,
                          "schema:sha256": sha256_file(path),
                          "prov:wasGeneratedBy": {"@id": base + "activity/step0_extract"},
                          "prov:wasDerivedFrom": {"@id": base + "entity/racing_f1_data.zip"}})
    audit = config.CLEANING_DIR / "audit_log.csv"
    previous = base + "activity/step0_extract"
    if not raw_mode and audit.exists():
        log = pd.read_csv(audit)
        id_col = next((c for c in log.columns if c.lower() in {"step_id", "step"}), None)
        name_col = next((c for c in log.columns if c.lower() in {"step_name", "name", "description", "action"}), None)
        for i, row in log.iterrows():
            step = str(row[id_col]) if id_col else f"C{i + 1:02d}"
            act = base + f"activity/cleaning_{re.sub(r'[^A-Za-z0-9_-]', '_', step)}"
            graph.append({"@id": act, "@type": "prov:Activity",
                          "rdfs:label": f"Cleaning {step}" + (f" - {row[name_col]}" if name_col else ""),
                          "prov:wasInformedBy": {"@id": previous},
                          "prov:wasAssociatedWith": {"@id": base + "agent/pipeline"}})
            previous = act
    for f in facts:
        if raw_mode:
            break
        graph.append({"@id": base + f"entity/{f['file_name']}", "@type": "prov:Entity", "rdfs:label": f["file_name"],
                      "schema:sha256": f["sha256"], "prov:wasGeneratedBy": {"@id": previous},
                      "prov:wasDerivedFrom": [{"@id": base + f"entity/{p.name}"} for p in RAW_FILES.values()],
                      "prov:wasAttributedTo": {"@id": base + "agent/pipeline"}})
    return {"@context": {"prov": "http://www.w3.org/ns/prov#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                         "schema": "https://schema.org/"}, "@graph": graph}


# ---------------------------------------------------------------- data dictionary ---------------

def data_dictionary(facts: list[dict]) -> pd.DataFrame:
    rows = []
    for f in facts:
        df = f["frame"]
        documented = {c.name: c for c in RESULTS_COLUMNS} if f["name"] == "f1_race_results_clean" else {}
        for col in df.columns:
            s = df[col]
            c = documented.get(col)
            example = s.dropna().iloc[0] if s.notna().any() else ""
            rows.append({
                "table": f["file_name"], "column": col,
                "type": c.dtype if c else infer_field(col, s)["type"],
                "description": c.description if c else REFERENCE_DESCRIPTIONS.get(col, ""),
                "unit_or_format": c.unit_or_format if c else "",
                "allowed_values": "; ".join(c.allowed_values) if c and c.allowed_values else "",
                "nullable": c.nullable if c else bool(s.isna().any()),
                "source_field": c.source if c else "",
                "non_null": int(s.notna().sum()), "distinct": int(s.nunique()), "example": example,
            })
    return pd.DataFrame(rows)


def dictionary_markdown(dd: pd.DataFrame) -> str:
    lines = ["# Data dictionary", "", f"Generated from the delivered files on {date.today().isoformat()}.", ""]
    for table, group in dd.groupby("table", sort=False):
        lines += [f"## {table}", "", "| Column | Type | Description | Unit / format | Allowed values | Non-null | Distinct |",
                  "|---|---|---|---|---|---|---|"]
        for _, r in group.iterrows():
            desc = str(r["description"]).replace("|", "/")
            lines.append(f"| `{r['column']}` | {r['type']} | {desc} | {r['unit_or_format']} | "
                         f"{str(r['allowed_values']).replace('|', '/')} | {r['non_null']} | {r['distinct']} |")
        lines.append("")
    return "\n".join(lines)


LICENSE_NOTICE = f"""# Data licence

The data files in `data/cleaned/` and `data/raw/` are licensed under the
**{LICENSE['name']}** licence ({LICENSE['spdx']}): {LICENSE['url']}

They are a derivative of the Ergast motor-racing database as served by the Jolpica-F1 API, whose
Terms of Use (https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md, last updated 27 August 2025)
state: "The data is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International (CC BY-NC-SA 4.0)". The ShareAlike clause requires this derivative to use the same licence.

Attribution: Jolpica-F1 (https://github.com/jolpica/jolpica-f1) and the Ergast Developer API
(http://ergast.com/mrd/).

The source code of the project remains under its own licence (MIT, as stated in the repository README);
that licence does not apply to the data.
"""


# ---------------------------------------------------------------- summary -----------------------

def write_summary(ds: dict, xml_ok: bool, xml_log: str) -> None:
    out = config.FAIR_DIR
    lines = ["# Component A - FAIR assessment and metadata design: key findings", ""]
    fuji_path, rda_path = out / "fuji_summary.csv", out / "rda_fair_summary.csv"
    if fuji_path.exists():
        fuji = pd.read_csv(fuji_path)
        lines += [f"## Automated assessment (F-UJI {fuji['software_version'].iloc[0]}, metrics "
                  f"v{fuji['metric_version'].iloc[0]})", "",
                  "| Resource | FAIR | F | A | I | R |", "|---|---|---|---|---|---|"]
        for _, r in fuji.iterrows():
            lines.append(f"| {r['resource']} ({r['url']}) | {r['fair_percent']:.1f}% | {r['F_percent']:.1f}% | "
                         f"{r['A_percent']:.1f}% | {r['I_percent']:.1f}% | {r['R_percent']:.1f}% |")
        lines.append("")
    if rda_path.exists():
        rda = pd.read_csv(rda_path)
        lines += ["## RDA FAIR Data Maturity Model (41 indicators, 0-4 maturity scale)", "",
                  "| Area | Progress as obtained | RDA level | Progress curated | RDA level | Essential passed (obtained -> curated) |",
                  "|---|---|---|---|---|---|"]
        for _, r in rda.iterrows():
            lvl = lambda v: "-" if pd.isna(v) else int(v)  # noqa: E731
            lines.append(f"| {r['area']} | {r['as_obtained_progress_percent']}% | {lvl(r['as_obtained_rda_level'])} | "
                         f"{r['curated_progress_percent']}% | {lvl(r['curated_rda_level'])} | "
                         f"{r['as_obtained_essential_passed']} -> {r['curated_essential_passed']} |")
        lines.append("")
    gaps_path = out / "fair_gaps.csv"
    if gaps_path.exists():
        lines += ["## Gaps and improvements", ""]
        for _, g in pd.read_csv(gaps_path).iterrows():
            lines.append(f"- **{g['gap_id']} {g['title']}** ({g['indicators']}): {g['evidence']} "
                         f"-> {g['improvement']} *Status: {g['status_in_package']}*")
        lines.append("")
    cov_path = out / "pid_coverage.csv"
    if cov_path.exists():
        cov = pd.read_csv(cov_path)
        lines += ["## Persistent identifiers", "",
                  "- Raw archive: DOI 10.5281/zenodo.23416916 (Zenodo, published 16 Oct 2026 by Manohar Zalki); "
                  "byte-identical to data/source/racing_f1_data.zip (size and MD5 checked, "
                  "data/reference/zenodo_source_record.json).",
                  f"- Curated package: own DOI still to be minted (placeholder `{DOI_PLACEHOLDER}`, never cite "
                  "before minting); its metadata already cites the raw archive's DOI (IsDerivedFrom, PROV-O).",
                  "- Creators: ORCID iDs to be added by each student.",
                  f"- Institution: ROR to be confirmed; best candidate {INSTITUTION['ror_candidate']} "
                  "(see data/reference/ror_candidates.csv).",
                  "- Countries: ISO 3166-1 alpha-3 (ISO 3166-3 for former states); dates: ISO 8601; licence: SPDX.",
                  "- Entities: Wikidata QIDs from Wikipedia URLs (data/reference/wikidata_crosswalk.csv):"]
        for _, r in cov.iterrows():
            lines.append(f"  - {r['entity_type']}: {r['with_qid']}/{r['records']} ({r['qid_coverage_percent']}%)")
        lines.append("")
    lines += ["## Licence findings", "",
              "- Jolpica-F1 Terms of Use (TERMS.md, updated 27 Aug 2025, https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md): "
              "data licensed CC BY-NC-SA 4.0, non-commercial use; the code repository itself is Apache-2.0.",
              "- Ergast Developer API terms (Wayback snapshot 18 May 2024 of https://ergast.com/mrd/terms/, live page now 404): "
              "\"You may use this API for personal, non-commercial applications and services including educational and research purposes\"; attribution appreciated, not required.",
              "- Kaggle mirror (rohanrao/formula-1-world-championship-1950-2020, version 24, updated 29 Jan 2025): declared \"CC0: Public Domain\", "
              "although compiled from Ergast, whose terms were non-commercial - a licence inconsistency.",
              "- Group repository README: \"MIT License\" for the whole project, no data licence - conflicts with CC BY-NC-SA 4.0.",
              "- Zenodo record of the raw archive (10.5281/zenodo.23416916): declares CC BY 4.0, which drops the "
              "non-commercial and share-alike conditions of the source - to be corrected to CC BY-NC-SA 4.0 "
              "(a metadata edit; the DOI does not change). F-UJI scores the licence as present, not as compliant.",
              f"- Decision: curated data released under {LICENSE['spdx']} (ShareAlike obligation); MIT kept for code only.", "",
              "## Metadata record", "",
              f"- DataCite 4.5 XML: {'valid' if xml_ok else 'NOT validated'} ({xml_log}).",
              "- Files: datacite_metadata.xml, datacite_metadata.json, schema_org_dataset.jsonld, datapackage.json, "
              "provenance_prov.jsonld, data_dictionary.csv/.md, LICENSE-DATA.md.",
              f"- Coverage: {ds['start']} to {ds['end']}, {ds['rows']:,} rows in the results table; raw files collected {ds['collected']}.",
              ""]
    if ds["raw_mode"]:
        lines.insert(1, "> STRUCTURAL TEST ONLY - generated from raw files; rerun after cleaning.\n")
    (out / "component_a_summary.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- run ---------------------------

def run(allow_raw: bool = False) -> dict:
    config.ensure_dirs()
    files, raw_mode = collect_inputs(allow_raw)
    facts = file_facts(files)
    ds = dataset_facts(facts, raw_mode)
    points = circuit_points(raw_mode)
    out = config.FAIR_DIR

    attrs = datacite_attributes(ds, facts, points)
    (out / "datacite_metadata.json").write_text(
        json.dumps({"data": {"type": "dois", "attributes": attrs}}, indent=2, ensure_ascii=False), encoding="utf-8")
    xml_path = out / "datacite_metadata.xml"
    datacite_xml(attrs).write(xml_path, encoding="utf-8", xml_declaration=True)
    xml_ok, xml_log = validate_datacite_xml(xml_path)

    (out / "schema_org_dataset.jsonld").write_text(
        json.dumps(schema_org(ds, facts, points, attrs), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "datapackage.json").write_text(json.dumps(datapackage(facts, raw_mode), indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    (out / "provenance_prov.jsonld").write_text(json.dumps(provenance(facts, raw_mode), indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    dd = data_dictionary(facts)
    dd.to_csv(out / "data_dictionary.csv", index=False)
    (out / "data_dictionary.md").write_text(dictionary_markdown(dd), encoding="utf-8")
    (out / "LICENSE-DATA.md").write_text(LICENSE_NOTICE, encoding="utf-8")
    write_summary(ds, xml_ok, xml_log)

    print(f"[metadata] {'RAW structural test' if raw_mode else 'cleaned files'}: {len(facts)} files, "
          f"{ds['rows']} result rows, coverage {ds['start']}..{ds['end']}")
    print(f"[metadata] DataCite XML: {xml_log}")
    if not xml_ok and "skipped" not in xml_log:
        raise ValueError(f"DataCite XML invalid: {xml_log}")
    return {"xml_valid": xml_ok, "files": len(facts), **ds}


if __name__ == "__main__":
    run()
