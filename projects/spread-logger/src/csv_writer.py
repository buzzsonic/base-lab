"""data/YYYY-MM.csv への1行追記。列は固定スキーマ(初回にヘッダを書く)。"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import HL_SPOT_BASIS_TARGETS

DATA_DIR = Path("data")


POINTFARM_FIELD_SUFFIXES = (
    "hl_funding_apr_pct",
    "var_mark",
    "var_funding_apr_pct",
    "var_oi_skew_pct",
    "var_volume_24h",
    "var_spread_bps",
    "var_hl_dev_pct",
    "var_hl_fr_spread_apr_pct",
    "nado_mid",
    "nado_oracle",
    "nado_open_interest",
    "nado_funding_apr_pct",
    "nado_hl_dev_pct",
    "nado_hl_fr_spread_apr_pct",
)


def build_fieldnames(coins: tuple[str, ...], pointfarm_coins: tuple[str, ...] = ()) -> list[str]:
    fields = ["ts_utc", "ts_jst", "usdjpy_ref", "usdjpy_ref_is_weekend", "usdjpy_ref_source"]
    for coin in coins:
        fields += [
            f"{coin}_bitflyer_bid",
            f"{coin}_bitflyer_ask",
            f"{coin}_bitbank_bid",
            f"{coin}_bitbank_ask",
            f"{coin}_gmo_bid",
            f"{coin}_gmo_ask",
            f"{coin}_coincheck_bid",
            f"{coin}_coincheck_ask",
            f"{coin}_domestic_mid",
            f"{coin}_hl_perp_mid",
            f"{coin}_hl_funding_hourly",
            f"{coin}_funding_apr_pct",
            f"{coin}_effective_usdjpy",
            f"{coin}_effective_usdjpy_dev_pct",
            f"{coin}_domestic_cross_pct",
            f"{coin}_domestic_cross_pair",
        ]
    for token in HL_SPOT_BASIS_TARGETS:
        fields += [f"hl_spot_{token}_mid", f"hl_basis_{token}_pct"]
    # ポイ活DEX列は既存列の後ろにまとめて足す(既存の列位置を動かさないため)
    for coin in pointfarm_coins:
        fields += [f"{coin}_{suffix}" for suffix in POINTFARM_FIELD_SUFFIXES]
    return fields


def _fmt(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    return value if value is not None else ""


def build_row(
    coins: tuple[str, ...],
    run_at_utc: datetime,
    run_at_jst: datetime,
    usdjpy_ref: float | None,
    usdjpy_ref_is_weekend: bool,
    usdjpy_ref_source: str,
    domestic: dict[str, dict[str, dict[str, float]]],
    metrics: dict[str, Any],
    pointfarm_coins: tuple[str, ...] = (),
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ts_utc": run_at_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "ts_jst": run_at_jst.strftime("%Y-%m-%d %H:%M:%S"),
        "usdjpy_ref": _fmt(usdjpy_ref),
        "usdjpy_ref_is_weekend": usdjpy_ref_is_weekend,
        "usdjpy_ref_source": usdjpy_ref_source,
    }

    for coin in coins:
        coin_metrics = metrics["per_coin"].get(coin, {})
        for exchange in ("bitflyer", "bitbank", "gmo", "coincheck"):
            entry = domestic.get(exchange, {}).get(coin)
            row[f"{coin}_{exchange}_bid"] = _fmt(entry["bid"]) if entry else ""
            row[f"{coin}_{exchange}_ask"] = _fmt(entry["ask"]) if entry else ""
        row[f"{coin}_domestic_mid"] = _fmt(coin_metrics.get("domestic_mid"))
        row[f"{coin}_hl_perp_mid"] = _fmt(coin_metrics.get("hl_perp_mid"))
        row[f"{coin}_hl_funding_hourly"] = _fmt(coin_metrics.get("hl_perp_funding_hourly"))
        row[f"{coin}_funding_apr_pct"] = _fmt(coin_metrics.get("funding_apr_pct"))
        row[f"{coin}_effective_usdjpy"] = _fmt(coin_metrics.get("effective_usdjpy"))
        row[f"{coin}_effective_usdjpy_dev_pct"] = _fmt(coin_metrics.get("effective_usdjpy_dev_pct"))
        row[f"{coin}_domestic_cross_pct"] = _fmt(coin_metrics.get("domestic_cross_pct"))
        row[f"{coin}_domestic_cross_pair"] = coin_metrics.get("domestic_cross_pair") or ""

    for token in HL_SPOT_BASIS_TARGETS:
        basis = metrics["hl_basis"].get(token, {})
        row[f"hl_spot_{token}_mid"] = _fmt(basis.get("spot_mid"))
        row[f"hl_basis_{token}_pct"] = _fmt(basis.get("basis_pct"))

    pointfarm = metrics.get("pointfarm", {})
    for coin in pointfarm_coins:
        coin_pointfarm = pointfarm.get(coin, {})
        for suffix in POINTFARM_FIELD_SUFFIXES:
            row[f"{coin}_{suffix}"] = _fmt(coin_pointfarm.get(suffix))

    return row


def _migrate_schema(path: Path, existing_header: list[str], fieldnames: list[str], logger: Any) -> None:
    """列が増えただけの場合に、既存CSVを新ヘッダで書き直す(増えた列は空欄で埋める)。

    列が増えるたびに月次ファイルを分けると解析側が煩雑になるため、その場で移行する。
    書き込み途中で落ちても原本を壊さないよう、一時ファイルに書いてから置き換える。
    """
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    tmp_path = path.with_suffix(".csv.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for old_row in rows:
            writer.writerow({key: old_row.get(key, "") for key in fieldnames})
    tmp_path.replace(path)

    added = [name for name in fieldnames if name not in existing_header]
    logger.info(f"{path}: スキーマを移行しました(既存{len(rows)}行、追加列{len(added)}個: {', '.join(added[:6])}...)")


def append_row(
    row: dict[str, Any],
    coins: tuple[str, ...],
    run_at_jst: datetime,
    logger: Any,
    pointfarm_coins: tuple[str, ...] = (),
) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{run_at_jst.strftime('%Y-%m')}.csv"
    fieldnames = build_fieldnames(coins, pointfarm_coins)

    file_exists = path.exists() and path.stat().st_size > 0
    if file_exists:
        with path.open(encoding="utf-8", newline="") as f:
            existing_header = f.readline().strip().split(",")
        if existing_header != fieldnames:
            if set(existing_header) <= set(fieldnames):
                _migrate_schema(path, existing_header, fieldnames, logger)
            else:
                logger.warning(
                    f"{path}: 既存ヘッダと現在のスキーマが一致しません(SPREAD_LOGGER_COINS変更等)。"
                    "そのまま追記しますが列がずれる可能性があります。"
                )

    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    logger.info(f"CSV追記完了: {path}")
    return path
