#!/usr/bin/env python3
"""Development-only targeted risk checks. Does NOT create independent held-out data.

F1: verify candidates 6-10 using SigmaHQ data pinned to the project's original SHA.
F2: synthetic negative, conflicting alias, missing field and ambiguous field evidence.
F3: preserve and report original D0 wrong cases. No tuning.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen
import yaml
from feasibility_spike import (
    apply_alias, diagnosis_d0, required_fields, run as run_feasibility
)
from json_eval_core import (
    compile_rule, load_json_stream, run_matcher, sha256_bytes, to_sigma_logical_event
)

ROOT=Path(__file__).resolve().parents[1]
PIN="16eb58704e941956d29b1a27da6f967c5525a9bb"
BASE=f"https://raw.githubusercontent.com/SigmaHQ/sigma/{PIN}"
OUT=ROOT/"results/feasibility_spike/risk_audit.json"
CASES=[
    ("DNS","4d07b1f4-cb00-4470-b9f8-b0191d48ff52",
     "rules/windows/dns_query/dns_query_win_remote_access_software_domains_non_browsers.yml",
     "regression_data/rules/windows/dns_query/dns_query_win_remote_access_software_domains_non_browsers"),
    ("NET","992a6cae-db6a-43c8-9cec-76d7195c96fc",
     "rules/windows/network_connection/net_connection_win_wscript_cscript_outbound_connection.yml",
     "regression_data/rules/windows/network_connection/net_connection_win_wscript_cscript_outbound_connection"),
    ("FW","974515da-6cc5-4c95-ae65-f97f9150ec7f",
     "rules/windows/registry/registry_set/registry_set_disable_defender_firewall.yml",
     "regression_data/rules/windows/registry/registry_set/registry_set_disable_defender_firewall"),
    ("RDP","509e84b9-a71a-40e0-834f-05470369bd1e",
     "rules/windows/registry/registry_set/registry_set_change_rdp_port.yml",
     "regression_data/rules/windows/registry/registry_set/registry_set_change_rdp_port"),
    ("PIPE","d36f87ea-c403-44d2-aa79-1a0ac7c24456",
     "rules/windows/pipe_created/pipe_created_pua_remcom_default_pipe.yml",
     "regression_data/rules/windows/pipe_created/pipe_created_pua_remcom_default_pipe")
]

def download(path: str) -> bytes:
    url=f"{BASE}/{path}"
    request=Request(url,headers={"User-Agent":"DriftLens-X-fyp-dev-audit"})
    with urlopen(request,timeout=40) as resp:
        return resp.read()

def check_rules(matcher:Path):
    outcome=[]
    for short,rule_id,rule_path,folder in CASES:
        item={"rule":short,"rule_id":rule_id,"rule_path":rule_path}
        try:
            with tempfile.TemporaryDirectory(prefix="fyp_candidate_") as t:
                p=Path(t)
                yml=download(rule_path)
                info=download(folder+"/info.yml")
                event_data=download(folder+"/"+rule_id+".json")
                # Metadata pinned to SAME historical SHA. Binary EVTX presence audited separately.
                rule=yaml.safe_load(yml)
                meta=yaml.safe_load(info)
                if rule["id"]!=rule_id:
                    raise ValueError("official rule ID mismatch")
                recs=meta["regression_tests_info"]
                pos=[q for q in recs if q.get("name")=="Positive Detection Test"
                     and q.get("type")=="evtx" and q.get("path","").endswith(rule_id+".evtx")]
                if len(pos)!=1:
                    raise ValueError("not exactly one positive EVTX metadata entry")
                expected=pos[0]["match_count"]
                rp=p/(short+".yml")
                jp=p/(short+".json")
                rp.write_bytes(yml); jp.write_bytes(event_data)
                src=load_json_stream(jp)
                logical=[to_sigma_logical_event(e) for e in src]
                expr=compile_rule(rp)
                n,idx,*_=run_matcher(matcher,expr,logical)
                item.update({"status":"PASS" if n==expected else "FAIL",
                             "positive_expected":expected,
                             "positive_matched":n,
                             "source_events":len(logical),
                             "json_sha256":sha256_bytes(event_data),
                             "rule_sha256":sha256_bytes(yml),
                             "compiled_expr_nonempty":bool(expr),
                             "regression_info_path":folder+"/info.yml"})
        except Exception as e:
            item.update({"status":"ERROR","error":type(e).__name__+": "+str(e)})
        outcome.append(item)
        print("F1 "+short+" "+item["status"]+
              " "+str(item.get("positive_matched","?"))+"/"+str(item.get("positive_expected","?"))+
              (" ("+item["error"]+")" if "error" in item else ""),flush=True)
    return outcome

def check_negative(matcher:Path):
    rule=ROOT/"rules/proc_creation_win_certutil_encode.yml"
    data=ROOT/"dataset/source/sigmahq/certutil_encode/e62a9f0c-ca1e-46b2-85d5-a6da77f86d1a.json"
    obs=to_sigma_logical_event(load_json_stream(data)[0])
    expr=compile_rule(rule)
    positive_count,*_=run_matcher(matcher,expr,[obs])
    if positive_count!=1:
        raise ValueError("original positive did not match")
    # An explicitly SYNTHETIC negative, derived by modifying a known positive.
    # It is NOT independent benign capture evidence and is NOT a general FPR metric.
    negative=deepcopy(obs)
    negative["CommandLine"]="cmd.exe /c echo routine-health-check"
    before_count,*_=run_matcher(matcher,expr,[negative])
    changed=deepcopy(negative)
    changed["process.command_line"]=changed.pop("CommandLine")
    changed_count,*_=run_matcher(matcher,expr,[changed])
    restored=apply_alias([changed],"CommandLine","process.command_line")
    restored_count,*_=run_matcher(matcher,expr,restored)
    collisions=deepcopy(changed)
    collisions["CommandLine"]="different value"
    try:
        apply_alias([collisions],"CommandLine","process.command_line")
        collision_rejected=False
    except ValueError:
        collision_rejected=True
    try:
        apply_alias([{"ProcessId":123}],"CommandLine","process.command_line")
        missing_rejected=False
    except ValueError:
        missing_rejected=True
    ambiguous=deepcopy(obs)
    value=ambiguous.pop("CommandLine")
    ambiguous["process.command_line"]=value
    ambiguous["alternative.command_line"]=value
    prediction=diagnosis_d0([obs],[ambiguous],required_fields(rule),"AFFECTED")
    return {
        "source_type":"SYNTHETIC_NEGATIVE_FROM_EXISTING_POSITIVE_NOT_HELDOUT",
        "original_positive_matched":positive_count==1,
        "synthetic_negative_before_matches":before_count,
        "synthetic_negative_changed_matches":changed_count,
        "synthetic_negative_adapter_matches":restored_count,
        "synthetic_no_new_fp_in_single_case":before_count==0 and restored_count==0,
        "collision_rejected":collision_rejected,
        "missing_source_alias_rejected":missing_rejected,
        "duplicated_equal_candidate_diagnosis":prediction["category"],
        "ambiguity_diagnosis_abstains":prediction["category"]=="INSUFFICIENT_EVIDENCE",
        "nontrivial_limitation":"The raw adapter does not implement a general document-backed semantic equivalence gate; one synthetic negative is not independent benign safety evaluation."
    }

def run(matcher:Path,out:Path):
    feasibility_out=out.parent/"d0_dev_rerun.json"
    first=run_feasibility(matcher,feasibility_out)
    rows=json.loads(feasibility_out.read_text(encoding="utf-8"))["cases"]
    errors=[{"case_id":r["case_id"],"observed_impact":r["impact"],
             "d0_prediction":r["d0_prediction"],
             "dev_expected_category":r["dev_expected_category"],
             "evidence_refs":r["evidence_refs"]}
            for r in rows if r.get("status")=="VALID" and not r.get("correct")]
    rules=check_rules(matcher)
    checks=check_negative(matcher)
    result={
       "stage":"DEVELOPMENT_ONLY_NOT_HELDOUT",
       "timestamp_utc":datetime.now(timezone.utc).isoformat(),
       "source_sigmahq_commit":PIN,
       "d0_dev_original":{"n":first["valid_scored"],"correct":first["d0_correct"],
                          "wrong_cases":errors,
                          "note":"Already-seen development material; do not tune a final baseline based on this score."},
       "candidate_rules":{"n":len(rules),"runtime_match_pass":sum(r["status"]=="PASS" for r in rules),
                          "rows":rules,
                          "warning":"Positive regression file is one source example per rule, NOT 10 source-distinct sessions or independent benign capture."},
       "adapter_negative_safety_exercises":checks,
       "unresolved":[
         "Actual independent benign capture source plus positive/benign held-out windows and provenance",
         "Strong deterministic D0 vs L1/A2 AI value and safety on a NEW blinded controlled set",
         "End-to-end AI-module integration and review of full 10/30/200 target",
         "A full semantic mapping safety validator with allowlisted type/source constraints"
       ]
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return all(x["status"]=="PASS" for x in rules) and all([
      checks["original_positive_matched"],checks["synthetic_no_new_fp_in_single_case"],
      checks["collision_rejected"],checks["missing_source_alias_rejected"],
      checks["ambiguity_diagnosis_abstains"]
    ])

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--matcher",type=Path,default=ROOT/"tools/bin/json_matcher")
    ap.add_argument("--output",type=Path,default=OUT)
    args=ap.parse_args()
    raise SystemExit(0 if run(args.matcher,args.output) else 1)
