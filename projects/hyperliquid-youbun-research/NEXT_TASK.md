# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 0. Discord通知（完了）

- 養分くん専用Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN` を使用。
- 403対策済み。
- 最終成功run: `36873755127`。
- Discord関連の追加修正は不要。研究品質確認を優先する。

## 1. 完結61episodeの層別目視検証（完了）

結果: 全61episodeの自動照合61/61 PASS、層別20episodeの匿名化レビュー20/20 PASS、重大差異0。

成果物: `reviews/episode-quality-2026-10-02/README.md` と `episode_review.csv`。

目的: 再構成済みepisodeが、FOMO・Late Long/Short・ナンピン等の行動分類の土台として十分正確か確認する。

### 対象
- 10口座
- 完結61 episode

### 層別
偏りなく、以下を跨ぐサンプルを選ぶ。
- 勝ち / 負け
- Long / Short
- 追加あり / なし
- 部分決済あり / なし
- 反転あり / なし
- 保有時間 短 / 中 / 長
- fill数 少 / 中 / 多

最低20 episodeを層別抽出する。必要なら重大差異が収束するまで追加確認する。

### 原fillとの照合項目
episodeごとに以下をraw fillと突合する。
- entry / exit時刻
- side
- entry / exit数量
- 平均entry / exit価格
- 追加ポジション
- 部分決済
- 反転
- closedPnl
- fee
- builderFee
- Funding帰属
- zero-to-zero境界
- fill時系列順序

### 成果物
匿名化したレビュー表を作り、最低限以下を記録する。
- episode ID
- 層別属性
- raw値
- reconstructed値
- 差分
- PASS / WARN / FAIL
- 差異理由
- 修正有無

目視結果をMarkdownレポートへ保存する。

### 品質ゲート結果
- 重大差異0
- 再構成ロジックの修正なし
- 数量許容誤差1e-8、価格・PnL・fee・Fundingは1e-6以内で全件一致
- 次工程へ進行可

## 2. 今回は行動分類を開始しない

以下はまだ実装・判定しない。
- FOMO
- Late Long / Short
- ナンピン
- Revenge
- Trapped
- Crowding
- 「養分は逆指標」等の結論

61 episodeの再構成品質ゲート通過前に進めない。

## 3. 次工程【最優先】

1. TWAP / Funding / builder fee会計照合の最終確認
   - eligible 10口座ではTWAP追加0件。TWAP上限2,000件の1口座は引き続き除外し、fixtureと除外理由を会計レポートに残す。
   - Funding帰属が発生したepisode数・金額、builderFee非zero episode数・fee包含関係を全61件で集計する。
2. 5分市場系列coverage定量化
3. coverage十分なepisodeへのpast-only市場特徴量付与

行動分類はその後。

## 作業終了時

- `CURRENT_STATUS.md` を更新
- `NEXT_TASK.md` を更新
- 必要なら `DECISIONS.md` に追記
- テスト実行
- 対象プロジェクトのみcommit/push
- push成功後のみ養分くん専用Discordへ完了通知

既存の養分ホイホイには変更を加えない。
