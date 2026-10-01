# PROJECT_CONTEXT

- 目的: Hyperliquidの公開データから多様な活動walletを発見・分類し、固定versionの研究sampleを養分くんへ渡す。
- 非目的: 養分度、FOMO/Late/Nanpin/Revenge/Liquidation分析、売買、署名、資金移動。
- Sampling: 複数source、PnL非参照、広くcandidate化して7日観察、source/whale/bot偏りを品質ゲート化。
- 分離: BOT/MM/arbitrage/funding-arbitrage/farmは削除せずregistryと別一覧へ保存し、通常sampleから除外。
- Depletion: 比較可能な7日snapshotで50%/70%。withdrawal疑いを除外。snapshot失敗週は判定保留。
- Actions: JST日曜0時snapshot、月曜0時weekly。UTC cronは土曜/日曜15時。
- Discord: 専用secret `YOUBUN_HOIHOI_DISCORD_WEBHOOK_URL`。payloadにsecretを含めない。
- Security: 公式/信頼できる公開read-only dataのみ。秘密鍵、exchange action、注文コードは禁止。
- Codex開始時: `PROJECT_CONTEXT.md`→`CURRENT_STATUS.md`→`NEXT_TASK.md`→`DECISIONS.md`を読む。
