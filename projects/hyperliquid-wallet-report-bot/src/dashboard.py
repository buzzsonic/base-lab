from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .logger import JST


def build_dashboard(store: Any, output_path: Path, as_of_ms: int) -> Path:
    trades = store.closed_trades(0)
    snapshots = store.all_snapshot_rows()
    daily = store.daily_stats_rows()
    events = store.risk_event_rows(0)
    event_map: dict[str, list[str]] = defaultdict(list)
    for event in events:
        if event.get("coin"):
            event_map[str(event["coin"])].append(str(event["risk_type"]))
    payload = {
        "asOf": datetime.fromtimestamp(as_of_ms / 1000, JST).strftime("%Y-%m-%d %H:%M JST"),
        "trades": [_trade_row(t, event_map, store.market_volume_near(str(t["coin"]), int(t["opened_at"]))) for t in trades],
        "equity": [{"time": int(s["time_ms"]), "value": float(s["account_value"])} for s in snapshots],
        "daily": daily,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_document(payload), encoding="utf-8")
    return output_path


def _trade_row(t: dict[str, Any], event_map: dict[str, list[str]], volume24h: float | None) -> dict[str, Any]:
    net = float(t["realized_pnl"]) - float(t["fees"])
    labels = []
    if int(t["number_of_adds"]) == 0:
        labels.append("追加なし")
    else:
        labels.append(f"追加×{int(t['number_of_adds'])}")
    labels.extend(sorted(set(event_map.get(str(t["coin"]), []))))
    return {"id": t["trade_id"], "coin": t["coin"], "direction": t["direction"],
            "opened": int(t["opened_at"]), "closed": int(t["closed_at"]),
            "entry": float(t["avg_entry"]), "maxNotional": float(t["max_position_notional"]),
            "pnl": net, "fees": float(t["fees"]), "minutes": float(t["duration_minutes"] or 0),
            "adds": int(t["number_of_adds"]), "partials": int(t["number_of_partial_closes"]),
            "volume24h": volume24h, "labels": labels[:4]}


def _document(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hyperliquid 損益分析</title>
<style>{_css()}</style></head><body><main><header><h1>損益分析</h1><p id="asof"></p><nav><button class="tab active" data-tab="overview">概要</button><button class="tab" data-tab="trades">決済注文の詳細</button><button class="tab" data-tab="analysis">勝敗分析</button></nav></header><div class="periods"><button data-days="7">過去7日</button><button class="active" data-days="30">過去30日</button><button data-days="60">過去60日</button><button data-days="90">過去90日</button><button data-days="180">過去180日</button><button data-days="0">全期間</button></div><section id="view"></section><footer>公開Info APIと保存済みSQLiteから生成｜出来高が未収集の過去取引は欠測</footer></main>
<script id="payload" type="application/json">{data}</script><script>{_js()}</script></body></html>'''


def _css() -> str:
    return '''*{box-sizing:border-box}body{margin:0;background:#f6f7f9;color:#17191d;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1280px;margin:20px auto;background:#fff;border:1px solid #e7e9ee;border-radius:12px;overflow:hidden}header{padding:26px 30px 0;border-bottom:1px solid #eceef2}h1{font-size:26px;margin:0 0 4px}header p,footer,.muted{color:#8a909b;font-size:12px}nav{display:flex;gap:28px;margin-top:18px}.tab,.periods button{border:0;background:none;padding:12px 0;color:#757b86;font-weight:600}.tab.active{color:#17191d;border-bottom:2px solid #f7a600}.periods{display:flex;gap:8px;flex-wrap:wrap;padding:18px 30px}.periods button{padding:9px 14px;background:#f4f5f7;border-radius:6px}.periods button.active{background:#fff1dc;color:#ef8f00}.content{padding:0 30px 30px}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:22px;padding:18px 0 28px}.label{font-size:13px;color:#8a909b;margin-bottom:8px}.num{font-size:23px;font-weight:650}.green{color:#12b76a}.red{color:#f04452}.twocol{display:grid;grid-template-columns:1.45fr 1fr;gap:20px}.box{border:1px solid #e5e8ed;border-radius:10px;padding:18px}h2{font-size:18px;margin:0 0 15px}.chart{width:100%;height:260px}.rankrow,.row{display:grid;grid-template-columns:1fr auto;gap:10px;padding:10px 0;border-bottom:1px solid #eff1f4;font-size:13px}.rankrow:last-child,.row:last-child{border:0}.tablewrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px;min-width:900px}th{background:#f6f7f9;color:#747b87;text-align:left;font-weight:500;padding:12px 10px}td{padding:12px 10px;border-bottom:1px solid #eef0f3}.badge{display:inline-block;padding:3px 7px;margin:2px;border-radius:4px;background:#fff1dc;color:#df8300}.analysis{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.barrow{display:grid;grid-template-columns:135px 1fr 92px;gap:8px;align-items:center;font-size:12px;margin:10px 0}.track{height:8px;background:#eff1f4;border-radius:20px;overflow:hidden}.fill{height:100%;background:#12b76a}.fill.bad{background:#f04452}.callout{margin-top:12px;border-left:3px solid #f7a600;background:#fff8ed;padding:10px 12px;font-size:12px}footer{padding:16px 30px;border-top:1px solid #eceef2}@media(max-width:760px){main{margin:0;border:0;border-radius:0}.metrics{grid-template-columns:repeat(2,1fr)}.twocol,.analysis{grid-template-columns:1fr}.content{padding:0 14px 20px}header{padding:18px 14px 0}.periods{padding:14px}.barrow{grid-template-columns:100px 1fr 78px}}'''


def _js() -> str:
    return r'''const D=JSON.parse(document.getElementById("payload").textContent);let days=30,tab="overview";const usd=n=>(n>=0?"+$":"-$")+Math.abs(n).toFixed(2),pf=a=>{const w=a.filter(x=>x.pnl>0).reduce((s,x)=>s+x.pnl,0),l=-a.filter(x=>x.pnl<0).reduce((s,x)=>s+x.pnl,0);return l?w/l:(w?Infinity:0)},subset=()=>{if(!days)return D.trades;const cut=Date.now()-days*864e5;return D.trades.filter(x=>x.closed>=cut)},esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function summary(a){const w=a.filter(x=>x.pnl>0),l=a.filter(x=>x.pnl<0),net=a.reduce((s,x)=>s+x.pnl,0);return{net,w:w.length,l:l.length,rate:a.length?w.length/a.length*100:0,pf:pf(a),avgw:w.length?w.reduce((s,x)=>s+x.pnl,0)/w.length:0,avgl:l.length?l.reduce((s,x)=>s+x.pnl,0)/l.length:0}}
function metrics(s){return `<div class="metrics"><div><div class="label">合計損益</div><div class="num ${s.net>=0?'green':'red'}">${usd(s.net)}</div></div><div><div class="label">決済取引</div><div class="num">${s.w+s.l}</div></div><div><div class="label">勝率</div><div class="num">${s.rate.toFixed(1)}%</div></div><div><div class="label">Profit Factor</div><div class="num ${s.pf<1?'red':''}">${isFinite(s.pf)?s.pf.toFixed(2):'∞'}</div></div><div><div class="label">平均損失</div><div class="num red">${usd(s.avgl)}</div></div></div>`}
function chart(){let pts=D.equity;if(days)pts=pts.filter(x=>x.time>=Date.now()-days*864e5);if(pts.length<2)return '<div class="muted">資産履歴を蓄積中</div>';const W=650,H=250,min=Math.min(...pts.map(x=>x.value)),max=Math.max(...pts.map(x=>x.value)),span=max-min||1;const xy=pts.map((p,i)=>`${35+i*(W-55)/(pts.length-1)},${20+(max-p.value)*(H-45)/span}`).join(' ');return `<svg class="chart" viewBox="0 0 ${W} ${H}" aria-label="資産推移"><polyline points="${xy}" fill="none" stroke="#f7a600" stroke-width="3"/><line x1="35" y1="${H-25}" x2="${W-20}" y2="${H-25}" stroke="#e8ebef"/><text x="38" y="18" font-size="12" fill="#697180">最高 $${max.toFixed(2)}</text><text x="${W-130}" y="${H-8}" font-size="12" fill="#697180">現在 $${pts.at(-1).value.toFixed(2)}</text></svg>`}
function group(a,key){const m={};a.forEach(x=>(m[key(x)]??=[]).push(x));return Object.entries(m).map(([label,rows])=>({label,rows,s:summary(rows)})).sort((x,y)=>y.s.net-x.s.net)}
function bars(rows){if(!rows.length)return '<p class="muted">データなし</p>';const mx=Math.max(...rows.map(x=>Math.abs(x.s.net)),1);return rows.map(x=>`<div class="barrow"><span>${esc(x.label)}</span><div class="track"><div class="fill ${x.s.net<0?'bad':''}" style="width:${Math.max(5,Math.abs(x.s.net)/mx*100)}%"></div></div><strong class="${x.s.net>=0?'green':'red'}">PF ${isFinite(x.s.pf)?x.s.pf.toFixed(2):'∞'}｜${usd(x.s.net)}</strong></div>`).join('')}
function overview(a,s){const best=[...a].sort((x,y)=>y.pnl-x.pnl).slice(0,3),worst=[...a].sort((x,y)=>x.pnl-y.pnl).slice(0,3);return `<div class="content">${metrics(s)}<div class="twocol"><div class="box"><h2>資産チャート</h2>${chart()}</div><div class="box"><h2>損益ランキング</h2>${[...best,...worst].map(x=>`<div class="rankrow"><span>${esc(x.coin)} ${x.direction}</span><strong class="${x.pnl>=0?'green':'red'}">${usd(x.pnl)}</strong></div>`).join('')||'<p class="muted">データなし</p>'}</div></div></div>`}
function trades(a,s){return `<div class="content">${metrics(s)}<h2>決済注文の詳細</h2><div class="tablewrap"><table><thead><tr><th>銘柄</th><th>方向</th><th>平均Entry</th><th>最大建玉</th><th>純損益</th><th>手数料</th><th>保有</th><th>特徴</th><th>終了日時</th></tr></thead><tbody>${[...a].reverse().map(x=>`<tr><td><strong>${esc(x.coin)}</strong></td><td>${x.direction}</td><td>${x.entry}</td><td>$${x.maxNotional.toFixed(0)}</td><td class="${x.pnl>=0?'green':'red'}">${usd(x.pnl)}</td><td>$${x.fees.toFixed(2)}</td><td>${x.minutes.toFixed(0)}分</td><td>${x.labels.map(y=>`<span class="badge">${esc(y)}</span>`).join('')}</td><td>${new Date(x.closed).toLocaleString('ja-JP')}</td></tr>`).join('')}</tbody></table></div></div>`}
function analysis(a,s){const direction=group(a,x=>x.direction),duration=group(a,x=>x.minutes<30?'30分未満':x.minutes<60?'30–60分':'60分以上'),behavior=group(a,x=>x.adds?'追加あり':'追加なし');return `<div class="content">${metrics(s)}<div class="analysis"><div class="box"><h2>方向別</h2>${bars(direction)}</div><div class="box"><h2>Entry時24h出来高別</h2><p class="muted">監視開始後の市場snapshotを蓄積中。過去分は欠測です。</p>${bars(group(a,x=>x.volume24h==null?'欠測':x.volume24h>=5e7?'$50M以上':x.volume24h>=1e7?'$10M–50M':x.volume24h>=3e6?'$3M–10M':'$3M未満'))}</div><div class="box"><h2>行動別</h2>${bars(behavior)}</div><div class="box"><h2>保有時間別</h2>${bars(duration)}</div></div><div class="callout">標本30件未満の区分は参考値。勝率だけでなく、純損益・PF・平均損失を併記します。</div></div>`}
function render(){const a=subset(),s=summary(a);document.getElementById('asof').textContent='最終更新 '+D.asOf;document.getElementById('view').innerHTML=tab==='overview'?overview(a,s):tab==='trades'?trades(a,s):analysis(a,s)}document.querySelectorAll('[data-days]').forEach(b=>b.onclick=()=>{days=+b.dataset.days;document.querySelectorAll('[data-days]').forEach(x=>x.classList.toggle('active',x===b));render()});document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));render()});render();'''
