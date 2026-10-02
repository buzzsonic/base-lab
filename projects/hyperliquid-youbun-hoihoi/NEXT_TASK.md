# NEXT_TASK

更新: 2026-10-02 JST。PR #14・#20はmainへ統合済み。初回収集・100候補の観察は成功し、data branchのdiscovery pool 200件を復元した。1,000-wallet拡大はHOLD。

1. 修正後の収集・連動観察は成功。pool 200件、registry 100件、sample 0件、成功観察日は79件が1日・21件が0日で同日重複なしを実データで確認済み。定刻収集に由来する観察はpush限定条件によりskipped。翌JST日の増分観察が2日目として加算されることを確認する。
2. JST 4時間帯のpublic Trades coverageを蓄積する。失敗した取得区間を完全な観察日として数えない。
3. [PR #21](https://github.com/buzzsonic/base-lab/pull/21)で小型アルト公開約定を独立層として抽出済み。JST 00–05時帯の収集を経て新しいdiscoveryから200→100件の層化再PoCを行う。イベント由来100候補ではsmall_alt 32件に増えたが、実際のsmall_alt_core比率とretention率は未検証。旧2,000件cap 63/100、今回の10,000件retentionによる不完全21/100を区別して評価する。
4. 100件から20件を層別目視し、BOT/MM/farm/裁定heuristicの誤検知を確認する。
5. snapshot/weeklyの永続化とsample品質ゲートを統合し、7日経過・7 JST日分完全取得後のpromotionを実データで検証する。
6. coverageと品質の再ゲートを通過した場合にのみ1,000-wallet拡大を検討する。
