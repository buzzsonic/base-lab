# NEXT_TASK

更新: 2026-10-03 JST。新100件の別namespace永続化、初回shadow観察、現行cohort非変更の実データ確認まで完了。1,000-wallet拡大はHOLD。

1. shadow cohortを日次観察し、成功JST日を7日まで蓄積する。初回live再取得は完全97、不完全3、BOT 29、MM 4、farm 6、small-alt 10。欠測・retention gapを成功日に数えない。
2. 完全→不完全へ変化した1 walletを追跡し、retention/gapがlookback外へ出るまでpromotionを禁止する。farm疑い6件と単一銘柄MM疑い2件も重点確認する。
3. 現行cohortは79件が2成功JST日、21件が0日。7日経過・7 JST日分完全取得後のpromotionを実データで検証する。
4. weekly実行と両cohortのsample品質ゲートを実データで検証する。snapshotはrun 37116871931で永続化成功済み。
5. JST 4時間帯は最低1回ずつ到達したが、run数は1/1/1/7で18–23時偏重。曜日差を含むcoverageを追加する。
6. 両cohortの7日比較とAPI所要時間のgateを通過した場合にのみ、置換・統合と1,000-wallet拡大を検討する。
