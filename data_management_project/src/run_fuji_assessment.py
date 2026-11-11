"""Component A - automated FAIR assessment with F-UJI (https://www.f-uji.net, PANGAEA).

F-UJI must be running locally (python -m fuji_server -c fuji_server/config/server.ini, see
README). When the service is reachable every resource is re-evaluated and the raw JSON response
is stored under outputs/component_a_fair/fuji/. When it is not reachable, the stored responses
are summarised again, so the pipeline stays reproducible offline.

Metric version 0.8 is the one the public F-UJI service uses (and the one of the group's earlier web run on the
Zenodo record, MetaData-FAIR/ in the repository root), so all four locations are scored on the same scale.
A first run with metrics v0.5 (9 Nov 2026) is kept for reference in fuji/metrics_v0.5/.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from src import config

FUJI_URL = os.environ.get("FUJI_URL", "http://localhost:1071/fuji/api/v1/evaluate")
FUJI_USER = os.environ.get("FUJI_USER", "marvel")
FUJI_PASSWORD = os.environ.get("FUJI_PASSWORD", "wonderwoman")
METRIC_VERSION = "metrics_v0.8"

TARGETS = {
    "github_repository": {
        "url": "https://github.com/zalkimanohar/Formula1-Racing-Analytics",
        "role": "Where the group's raw archive racing_f1_data.zip is published",
    },
    "jolpica_ergast_api": {
        "url": "http://api.jolpi.ca/ergast/f1/",
        "role": "API the raw data was downloaded from (Ergast-compatible endpoint)",
    },
    "kaggle_ergast_mirror": {
        "url": "https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020",
        "role": "Most-used public mirror of the Ergast database (approved source type)",
    },
    "zenodo_raw_archive": {
        "url": "https://doi.org/10.5281/zenodo.23416916",
        "role": "The group's raw archive racing_f1_data.zip deposited on Zenodo (DOI, 16 Oct 2026; "
                "byte-identical to data/source, checksum verified)",
    },
}

FUJI_DIR = config.FAIR_DIR / "fuji"


def _auth_header() -> str:
    token = base64.b64encode(f"{FUJI_USER}:{FUJI_PASSWORD}".encode()).decode()
    return f"Basic {token}"


def evaluate(url: str, timeout: int = 600) -> dict:
    body = json.dumps({
        "object_identifier": url,
        "test_debug": True,
        "use_datacite": True,
        "use_github": False,
        "metric_version": METRIC_VERSION,
    }).encode()
    request = urllib.request.Request(FUJI_URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "Authorization": _auth_header(),
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def service_available() -> bool:
    try:
        evaluate_probe = urllib.request.Request(FUJI_URL.replace("/evaluate", "/ui/"),
                                                headers={"Authorization": _auth_header()})
        urllib.request.urlopen(evaluate_probe, timeout=5)
        return True
    except (urllib.error.URLError, OSError):
        return False


def run_live() -> None:
    FUJI_DIR.mkdir(parents=True, exist_ok=True)
    for label, target in TARGETS.items():
        print(f"[F-UJI] evaluating {label}: {target['url']}")
        result = evaluate(target["url"])
        result["_assessment_context"] = {
            "label": label, "role": target["role"], "evaluated_url": target["url"],
            "requested_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "metric_version": METRIC_VERSION,
        }
        (FUJI_DIR / f"fuji_{label}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def summarise() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows, metric_rows = [], []
    for label in TARGETS:
        path = FUJI_DIR / f"fuji_{label}.json"
        if not path.exists():
            raise FileNotFoundError(f"No stored F-UJI result for {label}: run F-UJI first ({path})")
        data = json.loads(path.read_text(encoding="utf-8"))
        ctx = data.get("_assessment_context", {})
        pct = data["summary"]["score_percent"]
        earned = data["summary"]["score_earned"]
        total = data["summary"]["score_total"]
        summary_rows.append({
            "resource": label, "url": ctx.get("evaluated_url", TARGETS[label]["url"]),
            "role": TARGETS[label]["role"], "evaluated_at_utc": ctx.get("requested_at_utc"),
            "metric_version": data.get("metric_version", METRIC_VERSION),
            "software_version": data.get("software_version"),
            "fair_percent": pct.get("FAIR"), "F_percent": pct.get("F"), "A_percent": pct.get("A"),
            "I_percent": pct.get("I"), "R_percent": pct.get("R"),
            "fair_score_earned": earned.get("FAIR"), "fair_score_total": total.get("FAIR"),
        })
        for metric in data.get("results", []):
            score = metric.get("score", {})
            metric_rows.append({
                "resource": label,
                "metric_identifier": metric.get("metric_identifier"),
                "metric_name": metric.get("metric_name"),
                "score_earned": score.get("earned"), "score_total": score.get("total"),
                "maturity": metric.get("maturity"),
                "test_status": metric.get("test_status"),
            })
    summary = pd.DataFrame(summary_rows)
    metrics = pd.DataFrame(metric_rows)
    summary.to_csv(config.FAIR_DIR / "fuji_summary.csv", index=False)
    metrics.to_csv(config.FAIR_DIR / "fuji_metric_results.csv", index=False)
    return summary, metrics


def run(live: bool | None = None) -> pd.DataFrame:
    config.ensure_dirs()
    if live is None:
        live = service_available()
    if live:
        run_live()
    else:
        print("[F-UJI] service not reachable - summarising stored responses")
    summary, _ = summarise()
    print(summary[["resource", "fair_percent", "F_percent", "A_percent", "I_percent", "R_percent"]]
          .to_string(index=False))
    return summary


if __name__ == "__main__":
    run()
