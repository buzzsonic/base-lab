from __future__ import annotations
import argparse, json
from pathlib import Path
from scripts.audit_market_coverage import read_csv, write_csv
from scripts.apply_preregistered_labels import market_labels

LABELS=("fomo","late","averaging_down","profit_pyramiding","revenge")

def select(rows):
    true_rows=[r for r in rows if any(r[f"{x}_status"]=="TRUE" for x in LABELS)]
    selected={r["episode_id"]:r for r in true_rows}
    for side in ("LONG","SHORT"):
        for row in rows:
            if row["side"]==side and not any(row[f"{x}_status"]=="TRUE" for x in LABELS):
                selected.setdefault(row["episode_id"],row); break
    for alias in sorted({r["account_alias"] for r in rows}):
        for row in rows:
            if row["account_alias"]==alias and row["episode_id"] not in selected:
                selected[row["episode_id"]]=row; break
    return [selected[k] for k in sorted(selected)]

def build(labels, features, config):
    f={r["episode_id"]:r for r in features}; output=[]
    for row in select(labels):
        fomo,late=market_labels(f[row["episode_id"]],config)
        checks={"fomo":fomo.status==row["fomo_status"],"late":late.status==row["late_status"],
                "averaging_down":(row["averaging_down_status"]!="TRUE" or int(row["adverse_add_count"])>0),
                "profit_pyramiding":(row["profit_pyramiding_status"]!="TRUE" or int(row["profit_add_count"])>0),
                "revenge":(row["revenge_status"]!="TRUE" or (float(row["revenge_gap_minutes"])<=60 and float(row["revenge_initial_notional_ratio"])>=1.25))}
        output.append({"episode_id":row["episode_id"],"account_alias":row["account_alias"],"coin":row["coin"],"side":row["side"],
          "sample_role":"ALL_TRUE" if any(row[f"{x}_status"]=="TRUE" for x in LABELS) else "STRATIFIED_FALSE",
          **{f"{x}_status":row[f"{x}_status"] for x in LABELS},
          "market_rules_recomputed":str(checks["fomo"] and checks["late"]),"add_aggregate_consistent":str(checks["averaging_down"] and checks["profit_pyramiding"]),
          "revenge_sequence_consistent":str(checks["revenge"]),"review_status":"PASS" if all(checks.values()) else "FAIL"})
    return output

def main():
    p=argparse.ArgumentParser(); p.add_argument("--labels",type=Path,required=True); p.add_argument("--features",type=Path,required=True); p.add_argument("--config",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    rows=build(read_csv(a.labels),read_csv(a.features),json.loads(a.config.read_text())); a.output.mkdir(parents=True,exist_ok=True)
    write_csv(a.output/"label_review.csv",rows)
    failures=sum(r["review_status"]!="PASS" for r in rows); trues=sum(r["sample_role"]=="ALL_TRUE" for r in rows)
    (a.output/"README.md").write_text(f"""# Outcome-blind label quality review v1

## Result

PASS: {len(rows)-failures}/{len(rows)} reviewed episodes matched the frozen v1 implementation. The sample includes all {trues} episodes with at least one TRUE label plus {len(rows)-trues} stratified all-FALSE episodes across available sides/accounts.

No outcome, PnL, win/loss, MFE/MAE, post-entry return, or counter-trade result was loaded into the review.

## Checks

- FOMO and Late were independently recomputed from past-only features.
- TRUE Averaging Down and Profit Pyramiding rows require positive qualifying aggregate add counts.
- TRUE Revenge Candidate rows require gap <= 60 minutes and initial-notional ratio >= 1.25.
- v1 thresholds were not changed.

## Audit limitation

The current dry-run output stores add counts, size ratios, and worst adverse distance but not per-fill pre-add average, add price, and stable-order trace. Classification is reproducible from raw fills, but scaled human review needs a dedicated outcome-free add-evidence table. This is a v2 pipeline evidence requirement, not a v1 threshold change.
""")
    (a.output/"v2_candidates.md").write_text("""# v2 candidates

- Preserve one outcome-free evidence row per qualifying add: stable sequence index, timestamp, pre-add weighted average, add price, added quantity, existing quantity, size ratio, signed distance, and classification.
- Keep v1 thresholds unchanged until expanded, held-out data is available.
- Do not add historical OI, margin, or liquidation values unless directly observed.
""")
    if failures: raise RuntimeError(f"label review failures: {failures}")
if __name__=="__main__": main()
