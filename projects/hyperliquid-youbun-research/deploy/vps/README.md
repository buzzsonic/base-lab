# Youbun forward v3 VPS runtime

Ubuntu VPS上のDocker + systemd timerを正本schedulerにする。売買・署名・秘密鍵は扱わず、公開Info APIだけを読む。

## 契約

- 5分ごとに起動要求し、systemd oneshotと`flock`でsingle-flightにする。
- collector上限は19分。20分以内に完走または明示的FAILしないrunはGate不合格。
- v3は`forward-data-v3/`のみ使用し、v1/v2へ書かない。
- endpoint failure、retention risk、cap hitではraw manifestを保存するがcheckpointを進めない。
- timeoutでは一時runを削除しcheckpointを進めない。
- data branchがfast-forwardできない、またはpushできない場合は新規収集を始めない／次runへ進まない。

## 初期セットアップ

1. `/opt/base-lab`へmainをcheckoutし、`/var/lib/youbun-collector/data-repo`へdata branchをcheckoutする。
2. `/etc/youbun-collector.env`を`.env.example`から作り、mode 600にする。秘密値をGitへ置かない。
3. HTTPS push用のfine-grained tokenはdata checkoutのcredential helper等、rootだけが読める場所へ設定する。
4. `docker compose build`を実行する。
5. service/timerを`/etc/systemd/system/`へcopyし、`systemctl daemon-reload`する。
6. `systemctl enable --now youbun-collector.timer`で起動する。

## 段階検証

最初はenvの`MAX_WALLETS=1`でcanaryを1回実行する。成功後に空欄へ戻し、fixed-100を少なくとも3回連続で観測する。各runの開始間隔が20分以内で、failure / retention / cap / gap / push conflictが0になるまで7日Gateを開始しない。

```bash
systemctl start youbun-collector.service
bash /opt/base-lab/projects/hyperliquid-youbun-research/deploy/vps/health.sh
journalctl -u youbun-collector.service -f
```

VPS再起動後は`health.sh`でtimerがenabled/active、次回時刻が存在することを確認する。障害時はtimerを止め、欠落を推定・前方補完しない。
