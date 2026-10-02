# NEXT_TASK

更新: 2026-10-02 JST。PR #14・#20はmainへ統合済み。初回収集・100候補の観察は成功し、data branchのdiscovery pool 200件を復元した。1,000-wallet拡大はHOLD。

1. 修正後の収集・連動観察は成功。pool 200件、registry 100件、sample 0件、成功観察日は79件が1日・21件が0日で同日重複なしを実データで確認済み。定刻収集に由来する観察はpush限定条件によりskipped。翌JST日の増分観察が2日目として加算されることを確認する。
2. JST 4時間帯のpublic Trades coverageを蓄積する。失敗した取得区間を完全な観察日として数えない。
3. [PR #23](https://github.com/buzzsonic/base-lab/pull/23)・[PR #24](https://github.com/buzzsonic/base-lab/pull/24)で独立した200→100件再PoCを用意済み。JST 00:05の定刻収集成功後に一度だけ自動起動し、artifactのmanifest・pool/registryを解析する。小型アルト由来イベント候補32/100が、30日履歴でのsmall_alt_core 2/100、履歴不完全21/100、BOT/MM偏重をどう変えるか比較する。既存registry 100件の継続観察は維持する。
4. 100件から20件を層別目視し、BOT/MM/farm/裁定heuristicの誤検知を確認する。
5. snapshot/weeklyの永続化とsample品質ゲートを統合し、7日経過・7 JST日分完全取得後のpromotionを実データで検証する。
6. coverageと品質の再ゲートを通過した場合にのみ1,000-wallet拡大を検討する。
