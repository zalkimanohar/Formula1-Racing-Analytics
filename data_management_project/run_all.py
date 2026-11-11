"""Run the complete, reproducible project pipeline from the source archive to every deliverable.

    python run_all.py               # run every step
    python run_all.py --from-scratch  # delete all generated files first, then run (reproducibility check)

Network access is NOT required: Wikidata identifiers, ROR candidates, the DataCite XSD and the
F-UJI responses are read from the evidence cached in data/reference/ and outputs/component_a_fair/.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import shutil
import sys
import time

from src import config

KEEP_IN_FAIR_DIR = {"fuji", "license_evidence", "framework_evidence"}


def clean_generated() -> None:
    """Remove every regenerable artefact; keep the source archive and collected external evidence."""
    for folder in (config.RAW_DIR, config.CLEAN_DIR, config.QUALITY_DIR, config.CLEANING_DIR, config.GRAPH_DIR,
                   config.OUTPUT_DIR / "architecture"):
        shutil.rmtree(folder, ignore_errors=True)
    # the language-model evaluation is slow to repeat (stored evidence, like the F-UJI responses): keep it
    for item in (config.OUTPUT_DIR / "assistant").glob("*"):
        if item.is_file() and not item.name.startswith(("evaluation_llm", "api.log")):
            item.unlink()
    for item in config.FAIR_DIR.glob("*"):
        if item.name in KEEP_IN_FAIR_DIR:
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    print("[run_all] generated files removed (source archive and external evidence kept)")


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_dashboard_data() -> None:
    """Final stage: feed the interactive dashboard (../dashboard) from the validated outputs."""
    script = config.DASHBOARD_DIR / "build_web_data.py"
    if not script.exists():
        print("    dashboard folder not found - skipped")
        return
    spec = importlib.util.spec_from_file_location("build_web_data", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-scratch", action="store_true", help="delete generated files before running")
    args = parser.parse_args()
    if args.from_scratch:
        clean_generated()

    from src import (architecture, build_raw_dataset, cleaning, fair_assessment, graph_model, metadata,
                     pid_enrichment, profiling, quality_charts, run_fuji_assessment)
    from src.assistant import evaluate, knowledge, podium_model, reference

    steps = [
        ("Step 0   extract raw CSVs from the source archive", build_raw_dataset.run),
        ("Comp. A  persistent identifiers (cached Wikidata crosswalk)", pid_enrichment.run),
        ("Comp. B  profiling and quality issue register", profiling.run),
        ("Comp. C  cleaning pipeline, audit log, validation gates", cleaning.run),
        ("Comp. B/C quality and cleaning figures", quality_charts.run),
        ("Group    property graph and network analytics", graph_model.run),
        ("Comp. A  F-UJI evidence summary (stored responses)", lambda: run_fuji_assessment.run(live=False)),
        ("Comp. A  RDA FAIR maturity assessment and gaps", fair_assessment.run),
        ("Comp. A  DataCite / schema.org / Data Package metadata", metadata.run),
        ("Assistant official World Champions (cached Wikidata, reconciled with points)",
         reference.build_official_champions),
        ("Assistant podium model (time-based validation, model card)", podium_model.train),
        ("Assistant knowledge documents for retrieval", knowledge.run),
        ("Assistant routing benchmark (25 questions, evidence only)", lambda: evaluate.run(use_llm=False)),
        ("Dashboard web data from the validated outputs (../dashboard)", build_dashboard_data),
        ("Architecture: end-to-end data-flow diagram", architecture.run),
    ]
    started = time.perf_counter()
    for title, fn in steps:
        print(f"\n=== {title} ===")
        t0 = time.perf_counter()
        fn()
        print(f"    ({time.perf_counter() - t0:.1f}s)")

    print("\n=== SHA-256 of the cleaned dataset ===")
    for path in sorted(config.CLEAN_DIR.glob("*.csv")):
        print(f"  {sha256(path)}  {path.name}")
    print(f"\n[run_all] finished in {time.perf_counter() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
