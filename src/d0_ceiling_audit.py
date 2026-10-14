#!/usr/bin/env python3
"""Development-only D0 ceiling audit: fix rule dependency extraction over list-valued Sigma selections.

Original S1 D0 result (13/15) is preserved unchanged. This audits whether
those two errors were a deterministic parser bug, NOT evidence of AI advantage.
DO NOT use results from seen pilot cases as blind held-out performance.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import yaml
from feasibility_spike import diagnosis_d0,required_fields as required_fields_v1
from json_eval_core import compile_rule,load_json_stream,to_sigma_logical_event,run_matcher
from telemetry_transform import apply_case

ROOT=Path(__file__).resolve().parents[1]

def fields_v2(rule_path:Path)->set[str]:
    parsed=yaml.safe_load(rule_path.read_text(encoding="utf-8"))
    detection=parsed["detection"]
    found=set()
    def visit(item):
        if isinstance(item,dict):
            for key,value in item.items():
                if isinstance(value,dict):
                    visit(value)
                elif isinstance(value,list):
                    # A field can have many comparison values: 'OriginalFileName: [a,b]'.
                    # Or an OR selection may contain dict clauses: '[{field:a},{field:b}]'.
                    if any(isinstance(v,dict) for v in value):
                        for v in value:visit(v)
                    else:found.add(key.split("|",1)[0])
                else:
                    found.add(key.split("|",1)[0])
        elif isinstance(item,list):
            for value in item:visit(value)
    for group,criteria in detection.items():
        if group not in ("condition","timeframe"):
            visit(criteria)
    return found

def main(matcher:Path,output:Path):
    manifest=json.loads((ROOT/"metadata/pilot_manifest.json").read_text(encoding="utf-8"))
    cases=json.loads((ROOT/"metadata/telemetry_changes_v1.json").read_text(encoding="utf-8"))["cases"]
    manifest_by_id={x["id"]:x for x in manifest["rules"]}
    exprs={}
    records=[]
    for case in cases:
        rule=manifest_by_id[case["rule_id"]]
        path=ROOT/rule["rule_path"]
        before=[to_sigma_logical_event(e) for e in load_json_stream(ROOT/rule["json_path"])]
        after,_=apply_case(before,case)
        if case["rule_id"] not in exprs:exprs[case["rule_id"]]=compile_rule(path)
        expr=exprs[case["rule_id"]]
        n1,orig,*_=run_matcher(matcher,expr,before)
        n2,changed,*_=run_matcher(matcher,expr,after)
        impact=("AFFECTED" if set(orig)-set(changed) else
                "UNAFFECTED" if orig==changed else "DETECTION_SET_CHANGED")
        old_fields=required_fields_v1(path)
        new_fields=fields_v2(path)
        old=diagnosis_d0(before,after,old_fields,impact)["category"]
        new=diagnosis_d0(before,after,new_fields,impact)["category"]
        gold=("NO_DETECTION_LOSS" if impact=="UNAFFECTED" else
              {"field_schema_change":"FIELD_RELOCATION",
               "missing_telemetry":"ESSENTIAL_FIELD_LOSS",
               "value_format_change":"VALUE_REPRESENTATION",
               "non_impact_control":"NO_DETECTION_LOSS"}.get(case["category"],"UNKNOWN"))
        records.append({"case_id":case["id"],"impact":impact,"gold_dev":gold,
                        "v1":old,"v2":new,"v1_correct":old==gold,"v2_correct":new==gold,
                        "dependency_fields_added":sorted(new_fields-old_fields)})
    affected=[r for r in records if r["impact"]=="AFFECTED"]
    fixed=[r for r in records if not r["v1_correct"] and r["v2_correct"]]
    still_wrong=[r for r in records if not r["v2_correct"]]
    output.parent.mkdir(parents=True,exist_ok=True)
    summary={
      "stage":"DEVELOPMENT_ONLY_POST_HOC_BUG_AUDIT",
      "run_utc":datetime.now(timezone.utc).isoformat(),
      "original_v1_all_correct":sum(r["v1_correct"] for r in records),
      "corrected_v2_all_correct":sum(r["v2_correct"] for r in records),
      "total":len(records),
      "original_v1_affected_correct":sum(r["v1_correct"] for r in affected),
      "corrected_v2_affected_correct":sum(r["v2_correct"] for r in affected),
      "affected_total":len(affected),
      "corrected_cases":fixed,
      "remaining_errors":still_wrong,
      "baseline_message":"Baseline parser v1 dropped selection list-valued fields; post-hoc v2 adds them. These seen cases must NOT substantiate AI advantage; real held-out and additional data required.",
      "recommendation":"Implement a complete Sigma dependency parser, freeze D0 rules/heuristics BEFORE fresh blinded evaluation; do not build artificially weak D0. Evaluate plausible ambiguous mapping and hard negatives before committing both AI scopes."
    }
    output.write_text(json.dumps({"summary":summary,"cases":records},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
    return not still_wrong

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--matcher",type=Path,default=ROOT/"tools/bin/json_matcher")
    ap.add_argument("--output",type=Path,default=ROOT/"results/feasibility_spike/d0_parser_audit.json")
    args=ap.parse_args()
    raise SystemExit(0 if main(args.matcher,args.output) else 1)
