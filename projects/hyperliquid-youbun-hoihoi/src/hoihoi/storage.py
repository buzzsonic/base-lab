from __future__ import annotations

import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def write_parquet(path: Path, rows: list[dict], schema_fields: list[tuple[str, pa.DataType]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        table = pa.Table.from_pylist(rows)
    else:
        schema = pa.schema(schema_fields or [("wallet", pa.string())])
        table = pa.Table.from_pylist([], schema=schema)
    pq.write_table(table, path, compression="zstd")


def read_parquet(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist() if path.exists() else []


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
