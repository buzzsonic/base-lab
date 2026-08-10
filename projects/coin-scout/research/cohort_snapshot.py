"""cohort-fade 本番検証の"種": Hyperdash公開コホートL/Sを定期記録する収集器。

背景([[hl-cohort-fade-edge]]): HLは全ポジ公開。Hyperdashはアカウントを
PNL階層(超収益+$1M〜REKT-$1M)と規模階層(Apex$5M〜Small)に分類し、
各コホートのLong$/Short$を集計表示する。データはWebSocket配信でDOMに描画される
ため、生HTML取得(requests)では取れず、ヘッドレスブラウザでのDOM読取が必要。

このスクリプトは現在スナップショットを1行JSONLで追記する。数週間〜数ヶ月貯めれば、
養分コホートと大口コホートの乖離が順方向リターンを予測するかを、検出力のある形で
バックテストできる(HLの過去fillsは2000件=約2週間しか遡れず即時の本番検証は不可)。

使い方:
    # CI/実運用(Playwrightでライブ取得して追記)
    <venv>/bin/python cohort_snapshot.py --out data/cohorts.jsonl
    # 同じUTC時のレコードが既にあればスキップ(高頻度cronから安全に叩くため)
    <venv>/bin/python cohort_snapshot.py --out data/cohorts.jsonl --once-per-hour
    # パーサ単体テスト(保存済みinnerTextから)
    <venv>/bin/python cohort_snapshot.py --from-file sample.txt

なぜ --once-per-hour が要るか(2026-08-10):
    GitHub Actions の schedule は繁忙時にスキップ・遅延する。毎時5分の設定にもかかわらず
    実測の時単位カバー率は52%(中央値1.57時間間隔、最大8.8時間の欠測)だった。
    cronを10分毎に上げて「1時間に6回試行し、最初に成功した1回だけ記録する」ことで、
    スケジューラの取りこぼしを冗長化で吸収する。等間隔サンプルは cohort-fade 検証の前提。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COHORTS_URL = "https://hyperdash.com/explore/cohorts"
HL_INFO = "https://api.hyperliquid.xyz/info"
PRICE_REF_COINS = ["BTC", "ETH", "SOL", "HYPE"]  # 各記録に同時刻の参照価格を残す


def fetch_ref_prices() -> dict[str, float]:
    """後日の順方向リターン計算用に、スナップショット時刻の参照価格を残す。

    HLローソクは約17日しか遡れないため、貯めたデータ自体に価格を同梱して
    データセットを自己完結にする。取得失敗しても収集は続行(価格は空)。"""
    import requests
    try:
        r = requests.post(HL_INFO, json={"type": "allMids"}, timeout=15)
        mids = r.json()
        return {c: float(mids[c]) for c in PRICE_REF_COINS if c in mids}
    except Exception:
        return {}

# 表示名(日英どちらのロケールでも拾えるように両方)→ 安定id / 階層種別
NAME_TO_ID: dict[str, tuple[str, str]] = {
    "超収益": ("extremely_profitable", "pnl"), "Extremely Profitable": ("extremely_profitable", "pnl"),
    "高収益": ("very_profitable", "pnl"), "Very Profitable": ("very_profitable", "pnl"),
    "収益": ("profitable", "pnl"), "Profitable": ("profitable", "pnl"),
    "損失": ("unprofitable", "pnl"), "Unprofitable": ("unprofitable", "pnl"),
    "大きな損失": ("very_unprofitable", "pnl"), "Very Unprofitable": ("very_unprofitable", "pnl"),
    "REKT": ("rekt", "pnl"),
    "Apex": ("apex", "equity"),
    "ホエール": ("whale", "equity"), "Whale": ("whale", "equity"),
    "Large": ("large", "equity"),
    "Medium": ("medium", "equity"),
    "Small": ("small", "equity"),
}
# 逐次パースで「名前」とみなす行(降順に長い名前優先でマッチ)
KNOWN_NAMES = sorted(NAME_TO_ID.keys(), key=len, reverse=True)


def parse_usd(tok: str) -> float | None:
    m = re.match(r"\$([\d,]+(?:\.\d+)?)\s*([MBK]?)", tok.strip())
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return v * {"B": 1e9, "M": 1e6, "K": 1e3, "": 1.0}[m.group(2)]


def parse_cohorts(text: str) -> list[dict[str, Any]]:
    """main innerText からコホート行を構造化する。

    データ部の各ブロックは以下の順で並ぶ(空行は無視):
        NAME / THRESHOLD / SENTIMENT / "N ウォレット" / "$LONG" / ロング / "$SHORT" / ショート
    「N ウォレット」をアンカーにし、直後2つの$トークンをLong/Short、
    直前の既知コホート名を名前とする。
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for i, ln in enumerate(lines):
        m = re.match(r"([\d,]+)\s*(?:ウォレット|wallets?)", ln, re.I)
        if not m:
            continue
        wallets = int(m.group(1).replace(",", ""))

        # 直後の$トークン2つ(Long, Short)
        usd: list[float] = []
        for j in range(i + 1, min(i + 8, len(lines))):
            if lines[j].startswith("$"):
                v = parse_usd(lines[j])
                if v is not None:
                    usd.append(v)
            if len(usd) >= 2:
                break
        if len(usd) < 2:
            continue
        long_usd, short_usd = usd[0], usd[1]

        # 直前の既知コホート名
        name_id = None
        for k in range(i - 1, max(i - 8, -1), -1):
            for nm in KNOWN_NAMES:
                if lines[k] == nm:
                    name_id = NAME_TO_ID[nm]
                    break
            if name_id:
                break
        if not name_id or name_id[0] in seen:
            continue
        seen.add(name_id[0])

        net = long_usd - short_usd
        gross = long_usd + short_usd
        out.append({
            "id": name_id[0],
            "tier": name_id[1],
            "wallets": wallets,
            "long_usd": long_usd,
            "short_usd": short_usd,
            "net_usd": net,
            "ls_ratio": (long_usd / short_usd) if short_usd else None,
            "net_frac": (net / gross) if gross else None,  # +1=総ロング / -1=総ショート
        })
    return out


def fetch_innertext(timeout_s: int = 40) -> str:
    """Playwrightでライブ取得(CI用)。WS描画完了を待ってmainのinnerTextを返す。"""
    from playwright.sync_api import sync_playwright  # 遅延import(パーサ単体テストでは不要)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ja-JP")
        page.goto(COHORTS_URL, wait_until="domcontentloaded", timeout=timeout_s * 1000)
        # 「ショート」が複数出るまで(=コホート行が描画されるまで)待つ
        page.wait_for_function(
            "() => (document.querySelector('main')?.innerText.match(/ショート|Short/g)||[]).length >= 5",
            timeout=timeout_s * 1000,
        )
        text = page.eval_on_selector("main", "el => el.innerText")
        browser.close()
        return text


def last_recorded_hour(path: Path) -> datetime | None:
    """追記先の最終レコードのUTC時(分以下切り捨て)。ファイルが無ければNone。

    末尾だけを読むために全行を走査するが、この規模(数千行)では十分速い。
    壊れた行は無視して、読めた最後のtsを採用する。
    """
    if not path.exists():
        return None
    last: datetime | None = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                ts = json.loads(line)["ts"]
                last = datetime.fromisoformat(ts)
            except (ValueError, KeyError, TypeError):
                continue
    return last.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) if last else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, help="追記先JSONL")
    ap.add_argument("--from-file", type=Path, help="保存済みinnerTextからパース(テスト用)")
    ap.add_argument(
        "--once-per-hour",
        action="store_true",
        help="同じUTC時のレコードが既にあれば取得せず終了する(高頻度cron用)",
    )
    args = ap.parse_args()

    # 取得前に判定する。スキップできるならブラウザを起動しないぶん実行が軽くなる。
    if args.once_per_hour and args.out:
        current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        recorded = last_recorded_hour(args.out)
        if recorded is not None and recorded >= current_hour:
            print(f"{current_hour:%Y-%m-%dT%H}Z は記録済みのためスキップ")
            return 0

    text = args.from_file.read_text(encoding="utf-8") if args.from_file else fetch_innertext()
    cohorts = parse_cohorts(text)

    expected = {v[0] for v in NAME_TO_ID.values()}
    got = {c["id"] for c in cohorts}
    missing = expected - got
    if missing:
        print(f"警告: 未取得コホート {sorted(missing)}", file=sys.stderr)
    if len(cohorts) < 6:
        print(f"エラー: コホート数が少なすぎる({len(cohorts)})。描画未完了かフォーマット変更。", file=sys.stderr)
        return 1

    prices = {} if args.from_file else fetch_ref_prices()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prices": prices,
        "cohorts": cohorts,
    }

    # 検算表示
    print(f"取得 {len(cohorts)}コホート @ {record['ts']}")
    for c in cohorts:
        arrow = "L" if c["net_usd"] > 0 else "S"
        print(f"  {c['id']:<20} {c['wallets']:>7,}w  L/S={c['ls_ratio'] and round(c['ls_ratio'],2)!r:<5} "
              f"net={arrow} {abs(c['net_usd'])/1e6:>8.1f}M  net_frac={c['net_frac']:+.2f}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"追記 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
