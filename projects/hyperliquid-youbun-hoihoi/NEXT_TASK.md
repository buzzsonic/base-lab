# NEXT_TASK

更新: 2026-10-02 JST。PR #14・#20はmainへ統合済み。初回収集・100候補の観察は成功し、data branchのdiscovery pool 200件を復元した。1,000-wallet拡大はHOLD。

1. 修正後の[収集run 36990610067](https://github.com/buzzsonic/base-lab/actions/runs/36990610067)と、その成功後に連動する観察を確認する。poolが200件、registryが選抜100件のままか、同じJST日に成功観察日が二重加算されないかを検証する。
2. JST 4時間帯のpublic Trades coverageを蓄積する。失敗した取得区間を完全な観察日として数えない。
3. 新しいdiscoveryから200→100件の層化再PoCを行う。小型アルト中心2/100の偏り、旧2,000件cap 63/100、今回の10,000件retentionによる不完全21/100を区別して評価する。
4. 100件から20件を層別目視し、BOT/MM/farm/裁定heuristicの誤検知を確認する。
5. snapshot/weeklyの永続化とsample品質ゲートを統合し、7日経過・7 JST日分完全取得後のpromotionを実データで検証する。
6. coverageと品質の再ゲートを通過した場合にのみ1,000-wallet拡大を検討する。
