"""Step 0 - Extract the source archive into flat raw CSV files WITHOUT changing any value.

The source package (racing_f1_data.zip) mixes JSON Lines, pretty-printed JSON arrays and CSV.
This step only flattens it so that every later step reads one tabular format. Two provenance
columns (source_file, source_line) are prepended to the results table so that every raw record
can be traced back to the exact line it came from.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile

import pandas as pd

from src import config

RESULT_FILE_RE = re.compile(r"results/results_(\d{4})\.json$")
RESULT_COLUMNS = ["date", "raceName", "round", "season", "url", "constructorId", "driverId",
                  "grid", "laps", "number", "points", "position", "positionText", "status"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_archive() -> None:
    digest = sha256_bytes(config.SOURCE_ARCHIVE.read_bytes())
    if digest != config.SOURCE_ARCHIVE_SHA256:
        raise ValueError(f"Source archive checksum mismatch: {digest}")


def detect_format(name: str, payload: bytes) -> tuple[str, int, int]:
    """Return (format, record_count, lines_not_parseable_as_jsonl)."""
    base = name.rsplit("/", 1)[-1]
    if base == ".DS_Store":
        return "os_metadata_file", 0, 0
    if not payload.strip():
        return "empty_file", 0, 0
    text = payload.decode("utf-8")
    if name.endswith(".csv"):
        return "csv", max(len(text.strip().splitlines()) - 1, 0), 0
    lines = [l for l in text.splitlines() if l.strip()]
    bad = 0
    for line in lines:
        try:
            json.loads(line)
        except json.JSONDecodeError:
            bad += 1
    if bad == 0:
        return "json_lines", len(lines), 0
    parsed = json.loads(text)
    return "json_array_pretty_printed", len(parsed) if isinstance(parsed, list) else 1, bad


def build_manifest(zf: zipfile.ZipFile) -> pd.DataFrame:
    rows = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        payload = zf.read(info)
        fmt, n_records, bad = detect_format(info.filename, payload)
        rows.append({
            "archive_path": info.filename,
            "size_bytes": info.file_size,
            "sha256": sha256_bytes(payload),
            "detected_format": fmt,
            "record_count": n_records,
            "lines_not_valid_jsonl": bad,
        })
    return pd.DataFrame(rows).sort_values("archive_path", ignore_index=True)


def read_jsonl(zf: zipfile.ZipFile, member: str) -> list[dict]:
    text = zf.read(member).decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def extract_results(zf: zipfile.ZipFile) -> pd.DataFrame:
    frames = []
    members = sorted(m for m in zf.namelist() if RESULT_FILE_RE.search(m))
    for member in members:
        records = read_jsonl(zf, member)
        df = pd.DataFrame(records, columns=RESULT_COLUMNS, dtype=object)
        df.insert(0, "source_line", range(1, len(df) + 1))
        df.insert(0, "source_file", member.rsplit("/", 1)[-1])
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def extract_reference_jsonl(zf: zipfile.ZipFile, member: str) -> pd.DataFrame:
    df = pd.json_normalize(read_jsonl(zf, member)).astype(object)
    df.insert(0, "source_line", range(1, len(df) + 1))
    return df


def run() -> dict:
    config.ensure_dirs()
    verify_archive()
    with zipfile.ZipFile(config.SOURCE_ARCHIVE) as zf:
        manifest = build_manifest(zf)
        results = extract_results(zf)
        drivers = extract_reference_jsonl(zf, config.ARCHIVE_PREFIX + "drivers.json")
        constructors = extract_reference_jsonl(zf, config.ARCHIVE_PREFIX + "constructors.json")
        races_bytes = zf.read(config.ARCHIVE_PREFIX + "races.csv")
        circuits_bytes = zf.read(config.ARCHIVE_PREFIX + "circuits.csv")

    manifest.to_csv(config.SOURCE_MANIFEST_CSV, index=False)
    results.to_csv(config.RAW_RESULTS_CSV, index=False, lineterminator="\n")
    drivers.to_csv(config.RAW_DRIVERS_CSV, index=False, lineterminator="\n")
    constructors.to_csv(config.RAW_CONSTRUCTORS_CSV, index=False, lineterminator="\n")
    config.RAW_RACES_CSV.write_bytes(races_bytes)
    config.RAW_CIRCUITS_CSV.write_bytes(circuits_bytes)

    races = pd.read_csv(io.BytesIO(races_bytes))
    circuits = pd.read_csv(io.BytesIO(circuits_bytes))
    summary = {
        "results_rows": len(results), "results_columns": len(RESULT_COLUMNS),
        "races_rows": len(races), "circuits_rows": len(circuits),
        "drivers_rows": len(drivers), "constructors_rows": len(constructors),
        "archive_members": len(manifest),
    }
    print("[step 0] raw extraction:", summary)
    return summary


if __name__ == "__main__":
    run()
