# Fixed-100 forward collector contract

## 目的

過去30日を後追い取得せず、固定済み`pilot-100-v1`の100 walletについて、collector開始後のfills、TWAP slice fills、Fundingを欠落なく保存する。注文、署名、秘密鍵、資金移動は扱わない。

## Source選択

- 正本: REST `userFillsByTime`、`userTwapSliceFillsByTime`、`userFunding`
- user-specific WebSocketは正本にしない。公式上限がIPあたり10 unique usersで、固定100 walletを同条件で観測できないため。
- RESTは10,000 recent fillsの保持制約より十分短い20分周期で実行する。
- Fundingは60分周期、fills/TWAPは20分周期。応答件数から`20 + ceil(rows / 20)`でweightを見積もり、600 weight/minute以下（公式IP上限の50%）となるよう次requestまで待機する。空応答でも2.2秒以上空ける。

## 時点契約

- 初回成功runの`analysis_start_ms`をstateへ固定する。
- それ以前のrecordsは研究期間へ含めない。
- 各runは前回成功pollから20分overlapして再取得する。
- ページ境界は末尾timestampをinclusiveで再問い合わせし、`+1ms`しない。
- gapや失敗時はcheckpointを進めない。前方補完・0埋め・欠落fill推定は禁止。

## 保存

data branch:

```text
projects/hyperliquid-youbun-research/forward-data/
  state/collector_state.json
  raw/date=YYYY-MM-DD/run=YYYYMMDDTHHMMSSZ/
    fills.jsonl
    twap.jsonl
    funding.jsonl
    manifest.json
```

raw envelope:

- `schema_version`
- `sample_version`
- `wallet` / `anon_wallet_id`
- `source_endpoint`
- `source_time`
- `ingested_at`
- `run_id`
- `dedup_key`
- `payload`

run fileは作成後に変更しない。overlapによる重複はrawへ残し、canonical viewで`source_endpoint + wallet + dedup_key`により除外する。

## checkpoint

wallet×endpointごとに以下を保存する。

- `last_success_poll_ms`
- `last_source_time_ms`
- `last_status`
- `last_error`
- `consecutive_failures`
- `requests`
- `records`
- `retention_risk`
- `page_safety_cap_hit`

## Shadow Gate

最低7日間、以下をすべて満たすまでpilot分析を再開しない。

- scheduled run成功率100%
- 100 walletの各必須endpointに未解消gap 0
- page safety cap hit 0
- canonical duplicate除外後のfill continuity error 0
- quantity mismatch 0
- checkpoint巻き戻り0
- sampling manifest不変
- raw run fileの破損0

OHLCV、behavior label、500 wallet拡大はShadow Gate後のみ。
