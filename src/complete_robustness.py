"""D5 development: matched-world references and full predefined counterfactual set.

Uses saved OAT results and frozen D2/D3/D4 artifacts. No new Monte Carlo draws,
no training or reference recalibration. Selection/settings are saved before any
counterfactual trials; failed and inapplicable changes remain in the output.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from src.failure_catalogue import clean, verify_file, write_json
from src.mission_record import runtime
from src.reference_world import WorldEvaluator
from src.sensitivity import reference_rows, reference_scopes, sha, sweep_points
from src.uncertainty import INPUT_FIELDS, ROOT, load_context

POINT_KEYS=["battery_type","effective_battery","factor","point_id","reference_model","marginal_mapping","scope"]
META_KEYS=["battery_type","effective_battery","factor","sweep_kind","point_id","point_value","point_unit","primary_error_point"]
ACTION_NAMES={"M1":"Tăng mức pin", "M2":"Đổi sang TB48D", "M3":"Chờ gió giảm",
              "M4":"Chờ nhiệt độ phù hợp", "M5":"Giảm tải", "M6":"Giảm tốc độ", "M7":"Rút ngắn đường bay"}


def changed_scopes(context,base,world,ref,inputs):
    ratio=world[f"{ref}_ratio"]
    labels=world[f"{ref}_label"]
    r=context.d4["reference_label"]["method"]["reserve_policy_for_reference"]["r"]
    scopes={"all":np.ones(len(base),bool)}
    for width in context.d5["experiments"]["boundary_analysis"]["sweep_w"]:
        boundary=(np.abs(ratio)<=width)|(np.abs(ratio-r)<=width)
        scopes[f"boundary_w={width}"]=boundary
        scopes[f"outside_boundary_w={width}"]=~boundary
    scopes["marginal"]=labels=="marginal"
    for stratum in context.d5["inherited_baseline"]["primary_strata"]:
        scopes[f"stratum={stratum}"]=base.stratum.to_numpy()==stratum
    ranges={"distance":("distance_2d_m",context.d3["energy_required"]["validity_envelope"]["distance_2d_m"]),
            "wind":("wind_forecast_ms",context.d5["factors"]["wind_magnitude"]["measured_coverage_ms"]),
            "temperature":("ambient_temp_c",context.d5["factors"]["temperature_derating"]["calibrated_range_c"])}
    for name,(field,domain) in ranges.items():
        values=inputs[field].to_numpy(float)
        inside=(values>=domain[0])&(values<=domain[1])
        scopes[f"world_{name}_in_support"]=inside
        scopes[f"world_{name}_outside_support"]=~inside
    return scopes


def _point_meta(block):
    meta=clean(block.iloc[0][META_KEYS].to_dict())
    if block[META_KEYS].drop_duplicates().shape[0]!=1:
        raise ValueError("Saved OAT order is not one complete scenario population per grid point")
    return meta


def _label_hash(ids,labels):
    return hashlib.sha256("\n".join(f"{i}:{label}" for i,label in zip(ids,labels,strict=True)).encode()).hexdigest()


def matched_references(out,context,scenarios,oat_run,metadata):
    evaluator=WorldEvaluator(context)
    expected_ids=scenarios.scenario_id.to_numpy(int)
    original_scopes={ref:reference_scopes(context,scenarios,ref) for ref in ("ref1","ref2")}
    base_world={}
    baseline_frames=[]
    for battery in metadata["batteries"]:
        inputs=scenarios[list(INPUT_FIELDS)].assign(battery_type=battery)
        base_world[battery]=evaluator.evaluate(inputs)
        world=base_world[battery]
        table=scenarios.copy().assign(battery_type=battery,candidate_verdict=world["verdict"],
                                      candidate_prediction_Wh=world["prediction"],matched_available_Wh=world["available"])
        for ref in ("ref1","ref2"):
            table[f"matched_demand_{ref}_Wh"]=world[f"{ref}_demand"]
            table[f"matched_ratio_{ref}"]=world[f"{ref}_ratio"]
            table[f"matched_label_{ref}"]=world[f"{ref}_label"]
            if battery=="TB47D":
                if not np.array_equal(world[f"{ref}_label"],scenarios[f"label_{ref}"].to_numpy()):
                    raise ValueError(f"No-change TB47D labels differ from frozen D4 {ref}")
                if not np.allclose(world[f"{ref}_demand"],scenarios[f"e_reference_{ref}_Wh"],rtol=1e-8,atol=1e-8):
                    raise ValueError(f"No-change reference demand differs from D4 {ref}")
        baseline_frames.append(table)
    baseline=pd.concat(baseline_frames,ignore_index=True)
    baseline.to_csv(out/"matched_baseline_labels.csv",index=False,encoding="utf-8-sig")
    metrics,transitions,checks=[],[],[]
    count,valid_count=0,0
    header=True
    path=oat_run/"one_factor_evaluations.csv.gz"
    before=path.stat()
    started=time.perf_counter()
    with gzip.open(out/"matched_reference_labels.csv.gz","wt",encoding="utf-8",newline="",compresslevel=1) as output:
        for step,block in enumerate(pd.read_csv(path,chunksize=len(scenarios),dtype={"point_id":str,"point_value":str}),1):
            point=_point_meta(block)
            if not np.array_equal(block.scenario_id.to_numpy(int),expected_ids):
                raise ValueError("OAT scenario IDs/order changed or population is incomplete")
            inputs=scenarios[list(INPUT_FIELDS)].copy()
            inputs["soc"]=block.soc.to_numpy(float)
            inputs["soh"]=block.soh.to_numpy(float)
            inputs["wind_forecast_ms"]=block.wind_ms.to_numpy(float)
            inputs["ambient_temp_c"]=block.temperature_c.to_numpy(float)
            inputs["battery_type"]=point["effective_battery"]
            inputs["reserve_factor"]=block.reserve_ratio.to_numpy(float)
            world=evaluator.evaluate(inputs,candidate_demand=block.required_Wh.to_numpy(float),
                                     kappa_override=block.kappa.to_numpy(float))
            valid=block.status.to_numpy()=="OK"
            if not np.array_equal(valid,world["valid"]):
                raise ValueError(f"Saved validity differs: {point}")
            if not np.array_equal(world["verdict"][valid],block.reassessed_verdict.to_numpy()[valid]):
                raise ValueError(f"Saved D3 verdict differs: {point}")
            if not np.allclose(world["available"][valid],block.available_Wh.to_numpy()[valid],rtol=1e-8,atol=1e-8):
                raise ValueError(f"Saved energy differs: {point}")
            world["valid"]=valid
            count+=len(block)
            valid_count+=int(valid.sum())
            labels=pd.DataFrame(dict(scenario_id=expected_ids,status=block.status.to_numpy(),
                                      matched_available_Wh=np.where(valid,world["available"],np.nan)))
            labels=labels.assign(**{k:point[k] for k in ("battery_type","effective_battery","factor","point_id")})
            for ref in ("ref1","ref2"):
                new=world[f"{ref}_label"]
                old=scenarios[f"label_{ref}"].to_numpy()
                labels[f"fixed_label_{ref}"]=old
                labels[f"matched_demand_{ref}_Wh"]=np.where(valid,world[f"{ref}_demand"],np.nan)
                labels[f"matched_label_{ref}"]=new
                labels[f"matched_ratio_{ref}"]=np.where(valid,world[f"{ref}_ratio"],np.nan)
                for membership,scopes in (("ORIGINAL_D4",original_scopes[ref]),
                                           ("RECOMPUTED_WORLD",changed_scopes(context,scenarios,world,ref,inputs))):
                    rows=reference_rows(world,base_world[point["battery_type"]],new,scopes,point,ref)
                    for row in rows:
                        row.update(reference_policy="MATCHED_WORLD",scope_membership_policy=membership)
                    metrics.extend(rows)
                for old_class in ("feasible","marginal","infeasible"):
                    for new_class in ("feasible","marginal","infeasible"):
                        transitions.append({**point,"reference_model":ref.upper().replace("REF","REF-"),
                                            "fixed_label":old_class,"matched_label":new_class,
                                            "count":int((valid&(old==old_class)&(new==new_class)).sum())})
                checks.append({**point,"reference_model":ref.upper().replace("REF","REF-"),
                               "valid_scenarios":int(valid.sum()),"invalid_points":int((~valid).sum()),
                               "changed_reference_labels":int((valid&(old!=new)).sum()),
                               "matched_label_sha256":_label_hash(expected_ids,new)})
            labels.to_csv(output,index=False,header=header)
            header=False
            if step%50==0:
                print(f"Matched references: {step}/508 points; {count:,} saved rows",flush=True)
    if count!=metadata["total_evaluations"] or (path.stat().st_size,path.stat().st_mtime_ns)!=(before.st_size,before.st_mtime_ns):
        raise ValueError("OAT changed or row count differs")
    metrics=pd.DataFrame(metrics)
    metrics.to_csv(out/"matched_reference_metrics.csv",index=False)
    pd.DataFrame(transitions).to_csv(out/"reference_label_transitions.csv",index=False)
    pd.DataFrame(checks).to_csv(out/"matched_point_checks.csv",index=False)
    fixed=pd.read_csv(oat_run/"reference_metrics.csv",dtype={"point_id":str})
    matched=metrics[metrics.scope_membership_policy=="ORIGINAL_D4"]
    fields=["scored_scenarios","reference_infeasible","reference_feasible","false_safe_count","false_safe_rate",
            "unnecessary_rejection_count","unnecessary_rejection_rate","conditional_count_among_feasible"]
    comparison=fixed[POINT_KEYS+fields].merge(matched[POINT_KEYS+fields],on=POINT_KEYS,validate="one_to_one",suffixes=("_fixed","_matched"))
    if len(comparison)!=len(fixed):raise ValueError("Missing fixed/matched comparison rows")
    comparison["false_safe_rate_difference"]=comparison.false_safe_rate_matched-comparison.false_safe_rate_fixed
    comparison.to_csv(out/"fixed_vs_matched_metrics.csv",index=False)
    summary=comparison[(comparison.factor=="soc_error")&(comparison.point_id=="2")&(comparison.scope=="all")].copy()
    for index,row in summary.iterrows():
        ref=row.reference_model.lower().replace("-","")
        group=baseline[baseline.battery_type==row.battery_type]
        summary.loc[index,"changed_reference_labels"]=int((group[f"label_{ref}"]!=group[f"matched_label_{ref}"]).sum())
    summary.to_csv(out/"baseline_reference_comparison.csv",index=False,encoding="utf-8-sig")
    return baseline,summary,dict(evaluated_rows=count,valid_rows=valid_count,point_count=count//len(scenarios),
                                 elapsed_seconds=time.perf_counter()-started,metric_rows=len(metrics))


def action_targets(action,before,context):
    """Finite, prespecified one-control targets, ordered by smallest change."""
    plan=context.d5["replay_and_workflow"]["counterfactual_validation"]
    if action=="M1":
        step=plan["soc_absolute_grid_step"]
        targets=np.arange(math.floor(before["soc"]/step+1e-10)+1,round(1/step)+1)*step
        return "soc",[round(float(v),10) for v in targets if v<=1]
    if action=="M2":return "battery_type",["TB48D"] if before["battery_type"]=="TB47D" else []
    if action=="M3":
        rule=next(r for r in context.d3["hard_rules"]["manufacturer"] if r["id"]=="HR-1")
        limit=float(rule["check"].split("<=")[-1])
        return "wind_forecast_ms",[limit] if before["wind_forecast_ms"]>limit else []
    if action=="M4":
        endpoint=context.d3["available_energy"]["kappa_temperature"]["calibrated_range_c"][1]
        return "ambient_temp_c",[float(endpoint)] if before["ambient_temp_c"]<endpoint else []
    if action=="M5":return "payload_g",sorted([float(v) for v in plan["payload_levels_g"] if v<before["payload_g"]],reverse=True)
    if action=="M6":return "speed_commanded_ms",sorted([float(v) for v in plan["commanded_speed_levels_ms"] if v<before["speed_commanded_ms"]],reverse=True)
    if action=="M7":
        low,high=context.d3["energy_required"]["validity_envelope"]["distance_2d_m"]
        grid=np.unique(np.r_[np.arange(low,high+1e-9,plan["distance_grid_step_m"]),low,high])
        return "distance_2d_m",sorted([float(v) for v in grid if v<before["distance_2d_m"]],reverse=True)
    raise ValueError(f"Unknown action {action}")


TRIAL_COLUMNS=["trial_id","case_id","scenario_id","baseline_battery","action","status","evaluated","changed_field","target_value",
               "change_size","baseline_verdict","candidate_verdict","proposed_by_candidate","reference1_primary_pass","reference2_primary_pass",
               "reference1_secondary_pass","reference2_secondary_pass","both_references_primary_pass","within_model_support",
               "requires_future_weather","hypothetical_only","operational_approval",*INPUT_FIELDS,"battery_type","reserve_factor",
               "prediction_Wh","available_Wh","margin_Wh","reserve_slack_Wh","veto","wind_veto","mass_veto","landing_veto",
               "ref1_demand_Wh","ref2_demand_Wh","ref1_label","ref2_label","ref1_ratio","ref2_ratio","processing_batch_seconds"]


def select_model_proposals(trials):
    """Reference outcomes must not influence proposal selection."""
    eligible=trials[(trials.evaluated)&(trials.candidate_verdict=="FLY")&~trials.veto.fillna(True).astype(bool)
                    &(trials.baseline_verdict!="FLY")]
    return eligible.sort_values(["case_id","change_size","trial_id"]).groupby(["case_id","action"],sort=False).head(1).index


def counterfactuals(out,context,scenarios):
    evaluator=WorldEvaluator(context)
    selection=scenarios[(scenarios.label_ref1=="marginal")|(scenarios.label_ref2=="marginal")].sort_values("scenario_id")
    base=pd.concat([selection.assign(battery_type=b) for b in ("TB47D","TB48D")],ignore_index=True)
    base["case_id"]=[f"CF-{sid}-{battery}" for sid,battery in zip(base.scenario_id,base.battery_type,strict=True)]
    base["profile"]=evaluator.profile
    base["reserve_factor"]=evaluator.primary_reserve
    write_json(out/"selection_manifest.json",dict(selection_rule=context.d5["replay_and_workflow"]["counterfactual_validation"],
                timing="Written before any proposed changes were evaluated",scenario_count=len(selection),case_count=len(base),
                cases=base[["case_id","scenario_id","battery_type","label_ref1","label_ref2"]].to_dict("records")))
    initial=evaluator.evaluate(base)
    base["baseline_verdict"]=initial["verdict"]
    for name,key in (("baseline_prediction_Wh","prediction"),("baseline_available_Wh","available"),("baseline_margin_Wh","margin"),
                      ("baseline_ref1_label","ref1_label"),("baseline_ref2_label","ref2_label")):
        base[name]=initial[key]
    proposals=[]
    activity=[]
    started=time.perf_counter()
    header=True
    with gzip.open(out/"counterfactual_trials.csv.gz","wt",encoding="utf-8",newline="",compresslevel=1) as stream:
        for action in ACTION_NAMES:
            evaluated_count,attempt_count=0,0
            for offset in range(0,len(base),200):
                batch=base.iloc[offset:offset+200]
                rows=[]
                for before in batch.to_dict("records"):
                    field,targets=action_targets(action,before,context)
                    status="EVALUATED" if targets else "NOT_APPLICABLE"
                    if before["baseline_verdict"]=="FLY":targets=[];status="BASELINE_ALREADY_FLY"
                    for i,target in enumerate(targets if targets else [None]):
                        inputs={k:before[k] for k in INPUT_FIELDS}
                        inputs.update(battery_type=before["battery_type"],reserve_factor=evaluator.primary_reserve)
                        if target is not None:inputs[field]=target
                        change=(1. if field=="battery_type" else abs(target-before[field])) if target is not None else None
                        rows.append(dict(trial_id=f"{before['case_id']}-{action}-{i:03d}",case_id=before["case_id"],
                                         scenario_id=int(before["scenario_id"]),baseline_battery=before["battery_type"],action=action,
                                         status=status,evaluated=target is not None,changed_field=field,target_value=target,change_size=change,
                                         baseline_verdict=before["baseline_verdict"],candidate_verdict=None,proposed_by_candidate=False,
                                         requires_future_weather=action in ("M3","M4"),hypothetical_only=True,operational_approval=False,**inputs))
                trials=pd.DataFrame(rows)
                applicable=trials.evaluated
                for column in TRIAL_COLUMNS:
                    if column not in trials:trials[column]=None
                if applicable.any():
                    moment=time.perf_counter()
                    result=evaluator.evaluate(trials.loc[applicable])
                    elapsed=time.perf_counter()-moment
                    for column,key in (("candidate_verdict","verdict"),("prediction_Wh","prediction"),("available_Wh","available"),
                                       ("margin_Wh","margin"),("reserve_slack_Wh","slack"),("veto","veto"),
                                       ("wind_veto","wind_veto"),("mass_veto","mass_veto"),("landing_veto","landing_veto"),
                                       ("ref1_demand_Wh","ref1_demand"),("ref2_demand_Wh","ref2_demand"),("ref1_label","ref1_label"),
                                       ("ref2_label","ref2_label"),("ref1_ratio","ref1_ratio"),("ref2_ratio","ref2_ratio")):
                        trials.loc[applicable,column]=result[key]
                    support=~(result["distance_extrapolated"]|result["payload_extrapolated"]|result["wind_extrapolated"])
                    trials.loc[applicable,"within_model_support"]=support
                    for ref in (1,2):
                        common=result["valid"]&~result["veto"]
                        trials.loc[applicable,f"reference{ref}_primary_pass"]=common&(result[f"ref{ref}_label"]=="feasible")
                        trials.loc[applicable,f"reference{ref}_secondary_pass"]=common&np.isin(result[f"ref{ref}_label"],["feasible","marginal"])
                    trials.loc[applicable,"both_references_primary_pass"]=(trials.loc[applicable,"reference1_primary_pass"].astype(bool)
                                                                           &trials.loc[applicable,"reference2_primary_pass"].astype(bool))
                    trials.loc[applicable,"processing_batch_seconds"]=elapsed
                selected=select_model_proposals(trials)
                trials.loc[selected,"proposed_by_candidate"]=True
                if len(selected):proposals.append(trials.loc[selected,TRIAL_COLUMNS].copy())
                trials[TRIAL_COLUMNS].to_csv(stream,index=False,header=header)
                header=False
                evaluated_count+=int(applicable.sum());attempt_count+=len(trials)
            activity.append(dict(action=action,evaluated_trials=evaluated_count,total_saved_trial_rows=attempt_count))
            print(f"Counterfactual {action}: {evaluated_count:,} applicable trials, {attempt_count:,} rows including exclusions",flush=True)
    offered=pd.concat(proposals,ignore_index=True) if proposals else pd.DataFrame(columns=TRIAL_COLUMNS)
    offered.to_csv(out/"counterfactual_proposals.csv",index=False,encoding="utf-8-sig")
    counts=offered.groupby("case_id").agg(proposal_count=("trial_id","count"),
                 passing_ref1=("reference1_primary_pass","sum"),passing_ref2=("reference2_primary_pass","sum"),
                 passing_both=("both_references_primary_pass","sum")) if len(offered) else pd.DataFrame()
    case_summary=base.merge(counts,on="case_id",how="left") if len(counts) else base.copy()
    for field in ("proposal_count","passing_ref1","passing_ref2","passing_both"):
        if field not in case_summary:case_summary[field]=0
        case_summary[field]=case_summary[field].fillna(0).astype(int)
    case_summary.to_csv(out/"counterfactual_case_summary.csv",index=False,encoding="utf-8-sig")
    summaries=[]
    for battery in ("TB47D","TB48D"):
        for action in ("ALL",*ACTION_NAMES):
            group=offered[offered.baseline_battery==battery]
            if action!="ALL":group=group[group.action==action]
            for support in ("all","within_model_support","outside_model_support"):
                part=group if support=="all" else group[group.within_model_support.astype(bool)==(support=="within_model_support")]
                for ref in (1,2):
                    for mapping in ("PRIMARY_FEASIBLE_ONLY","SECONDARY_MARGINAL_ALLOWED"):
                        column=f"reference{ref}_{'primary' if mapping.startswith('PRIMARY') else 'secondary'}_pass"
                        numerator=int(part[column].sum()) if len(part) else 0
                        summaries.append(dict(battery_type=battery,action=action,support=support,reference_model=f"REF-{ref}",
                                              mapping=mapping,offered_proposals=len(part),reference_passed=numerator,
                                              pass_rate=numerator/len(part) if len(part) else None,
                                              distinct_cases=part.case_id.nunique()))
    summary=pd.DataFrame(summaries)
    summary.to_csv(out/"counterfactual_validation_summary.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(activity).to_csv(out/"counterfactual_activity.csv",index=False)
    return case_summary,offered,summary,dict(selected_scenario_ids=len(selection),selected_battery_cases=len(base),
              evaluated_trials=sum(a["evaluated_trials"] for a in activity),saved_trial_rows=sum(a["total_saved_trial_rows"] for a in activity),
              offered_proposals=len(offered),cases_with_proposal=int((case_summary.proposal_count>0).sum()),
              elapsed_seconds=time.perf_counter()-started)


def render(out,baseline,reference_summary,cases,proposals,validation,statistics):
    # Plain-language examples are chosen by ID, independently of reference success.
    battery_examples=[]
    left=baseline[baseline.battery_type=="TB47D"].set_index("scenario_id")
    right=baseline[baseline.battery_type=="TB48D"].set_index("scenario_id")
    for ref in ("ref1","ref2"):
        different=left[f"matched_label_{ref}"]!=right[f"matched_label_{ref}"]
        if different.any():
            sid=int(left.index[different][0]);a,b=left.loc[sid],right.loc[sid]
            battery_examples.append(dict(ID=sid,Tham_chieu=ref.upper().replace("REF","REF-"),
                  Pin_truoc="TB47D",Pin_sau="TB48D",Nang_luong_pin_truoc_Wh=a.matched_available_Wh,Nang_luong_pin_sau_Wh=b.matched_available_Wh,
                  Nhan_cu_D4=a[f"label_{ref}"],Nhan_tinh_lai_TB48D=b[f"matched_label_{ref}"],
                  Quyet_dinh_TB47D=a.candidate_verdict,Quyet_dinh_TB48D=b.candidate_verdict))
    pd.DataFrame(battery_examples).to_csv(out/"battery_reference_examples.csv",index=False,encoding="utf-8-sig")
    examples=[]
    for action in ACTION_NAMES:
        pool=proposals[proposals.action==action].sort_values(["scenario_id","baseline_battery"])
        if len(pool):
            row=pool.iloc[0]
            original=cases[cases.case_id==row.case_id].iloc[0]
            examples.append(dict(ID=int(row.scenario_id),Loai_pin=row.baseline_battery,Bien_phap=ACTION_NAMES[action],
                                  Truoc=original[row.changed_field],Sau=row.target_value,
                                  Quyet_dinh_truoc=row.baseline_verdict,Quyet_dinh_sau=row.candidate_verdict,
                                  Nhan_REF1_sau=row.ref1_label,Nhan_REF2_sau=row.ref2_label,
                                  Dat_REF1=bool(row.reference1_primary_pass),Dat_REF2=bool(row.reference2_primary_pass),
                                  Can_doi_thoi_tiet=bool(row.requires_future_weather)))
    pd.DataFrame(examples).to_csv(out/"counterfactual_examples_explained.csv",index=False,encoding="utf-8-sig")
    lines=["# Hoàn thiện đối chiếu tham chiếu và kiểm tra đề xuất D5", "",
           "Đây là kết quả phát triển dưới các giả định mô phỏng đã khai; quy trình còn DRAFT và kiểm tra chéo PENDING. Không phải xác nhận quyền bay thực tế.","",
           "## Tính lại nhãn tham chiếu", "",
           f"Đã tính lại cả REF-1 và REF-2 trên {statistics['matched']['evaluated_rows']:,} điểm OAT đã lưu, đủ 14.700 ID và hai loại pin. Có {statistics['matched']['valid_rows']:,} điểm hợp lệ; các điểm không hợp lệ giữ nhãn unknown và không vào mẫu số.",
           "Nhãn D4 ban đầu giữ giả định TB47D. Bảng mới đối chiếu từng điểm bằng cùng mức pin, sức khỏe pin, hệ số nhiệt độ và giả định pin với hệ thống đang được đánh giá. Không sửa nhãn D4 cũ.","",
           "REF-1 giữ công thức D2 đã chốt cộng khoản dự phòng D4; REF-2 giữ công thức vật lý và hệ số đã chốt. Sai số phần dư dùng để thử ứng viên không tự chép sang hai REF. REF-2 chưa có ánh xạ nhu cầu theo gió đã được kiểm chứng, nên thay gió không tự tạo thêm một công thức gió cho REF-2.",
           "Mức dự trữ tham chiếu vẫn là 20% khi quét chính sách của ứng viên. Có bảng giữ nguyên thành viên nhóm biên D4 để so sánh công bằng và bảng tính lại thành viên nhóm biên theo thế giới đã thay đổi.","",
           "| Pin | Tham chiếu | Số nhãn đổi so với D4 ở đầu vào gốc | FLY trái nhãn không khả thi: giữ nhãn / tính lại nhãn |", "|---|---|---:|---|" ]
    primary=reference_summary[reference_summary.marginal_mapping=="INFEASIBLE"]
    for row in primary.itertuples():
        lines.append(f"| {row.battery_type} | {row.reference_model} | {int(row.changed_reference_labels)} | {row.false_safe_count_fixed}/{row.reference_infeasible_fixed} → {row.false_safe_count_matched}/{row.reference_infeasible_matched} |")
    lines += ["", "Đây là số đếm trên kịch bản mô phỏng. Khi nhãn đổi, mẫu số có thể đổi; không so tỷ lệ mà bỏ qua số đếm.", "",
              "## Kiểm tra các đề xuất điều chỉnh", "",
              f"Đã chọn trước toàn bộ {statistics['counterfactual']['selected_scenario_ids']:,} ID sát ngưỡng theo ít nhất một REF D4, thử cả hai pin: {statistics['counterfactual']['selected_battery_cases']:,} ca. Đã tính {statistics['counterfactual']['evaluated_trials']:,} thay đổi áp dụng được và lưu cả các trường hợp không áp dụng/đã FLY.",
              f"Hệ thống đưa ra {statistics['counterfactual']['offered_proposals']:,} đề xuất nhỏ nhất theo từng biện pháp, trên {statistics['counterfactual']['cases_with_proposal']:,} ca. Một ca có thể có nhiều biện pháp; không cộng số đề xuất thành số ID.","",
              "Thử một biến mỗi lần: mức pin theo lưới 1 điểm phần trăm; tải/tốc độ theo mức đã đo; quãng đường theo lưới 10 m trong dải hỗ trợ. Hệ thống chọn đề xuất bằng kết quả ứng viên FLY trước khi chấm bằng hai REF. Các đề xuất không qua REF vẫn được lưu và tính vào mẫu số.",
              "Mức thay đổi nhỏ nhất chỉ đúng trong lưới đã khai và trong từng biện pháp; không khẳng định tối ưu liên tục hay so chi phí sạc pin với giảm hàng. Các biện pháp chờ gió/nhiệt độ là điều kiện giả định trong tương lai, cần dữ liệu thời tiết mới trước khi dùng.","",
              "| Pin | Tham chiếu | Đề xuất đạt nhãn feasible / tổng đề xuất |", "|---|---|---:|"]
    for row in validation[(validation.action=="ALL")&(validation.support=="all")&(validation.mapping=="PRIMARY_FEASIBLE_ONLY")].itertuples():
        lines.append(f"| {row.battery_type} | {row.reference_model} | {row.reference_passed}/{row.offered_proposals} |")
    lines += ["", "Các tỷ lệ này đánh giá đề xuất theo mô hình tham chiếu, không phải xác suất chuyến bay thực tế thành công. Có bảng riêng cho cách cho phép nhóm marginal và nhóm trong/ngoài phạm vi dữ liệu.","",
              "## Ví dụ dễ đọc", ""]
    for example in battery_examples:
        lines.append(f"- ID {example['ID']}, {example['Tham_chieu']}: pin khả dụng {example['Nang_luong_pin_truoc_Wh']:.4f} → {example['Nang_luong_pin_sau_Wh']:.4f} Wh; nhãn D4 `{example['Nhan_cu_D4']}` → nhãn tính lại cho TB48D `{example['Nhan_tinh_lai_TB48D']}`.")
    for example in examples:
        lines.append(f"- ID {example['ID']}/{example['Loai_pin']}, {example['Bien_phap']}: {example['Truoc']} → {example['Sau']}; ứng viên {example['Quyet_dinh_truoc']} → {example['Quyet_dinh_sau']}; REF-1 `{example['Nhan_REF1_sau']}`, REF-2 `{example['Nhan_REF2_sau']}`.")
    lines += ["", "## File kết quả", "",
              "- `matched_baseline_labels.csv`: đủ các ID ở đầu vào gốc, mỗi pin một dòng, nhãn trước/sau và năng lượng tham chiếu.",
              "- `matched_reference_labels.csv.gz`: nhãn tính lại của từng điểm OAT; tệp lớn, đọc theo lô bằng Python.",
              "- `fixed_vs_matched_metrics.csv`: so sánh nhãn cố định và nhãn tính lại trên cùng thành viên nhóm gốc.",
              "- `matched_reference_metrics.csv`: đủ hai cách chia nhóm; `reference_label_transitions.csv`: số nhãn chuyển lớp.",
              "- `counterfactual_case_summary.csv`: từng ca có bao nhiêu đề xuất, bao nhiêu đề xuất qua mỗi REF.",
              "- `counterfactual_proposals.csv`: mọi đề xuất ứng viên đã đưa ra, kể cả không qua REF.",
              "- `counterfactual_trials.csv.gz`: toàn bộ thử nghiệm và lý do không áp dụng; không chỉ lưu thành công.",
              "- `counterfactual_validation_summary.csv`: tử số/mẫu số, hai cách gộp marginal và nhóm hỗ trợ dữ liệu.",
              "- Hai file `*_examples*.csv` là các ví dụ có cột tiếng Việt để xem nhanh.","",
              "## Giới hạn", "",
              "CMU_instrumented vượt giới hạn MTOW đã công bố; HR-3 là record-only trong chế độ phân tích. Tất cả kết quả ở đây chỉ là chẩn đoán mô phỏng, không phải quyền cho bay. Khối lượng CMU được giữ theo cấu hình 3.680 g, không tự cộng một hiệu chỉnh khối lượng pin mới. D2 không có đặc trưng loại pin; REF-2 không có mô hình gió đã xác minh. Ảnh hưởng SoH/nhiệt độ vẫn là giả định chứ không học được từ dữ liệu này.",
              "Các đầu ra kỹ thuật này không tự thay thế kiểm tra chéo của Phát hay đóng băng quy trình. Không đánh dấu D5 đã nghiệm thu.",""]
    (out/"robustness_completion_report.md").write_text("\n".join(lines),encoding="utf-8")


def run(out,oat_run,root=ROOT):
    out,oat_run=Path(out),Path(oat_run)
    if out.exists():raise FileExistsError("Choose a new output directory")
    context=load_context(root)
    metadata=json.loads((oat_run/"input_manifest.json").read_text(encoding="utf-8"))
    if metadata["status"]!="COMPLETED_OAT_DEVELOPMENT":raise ValueError("OAT run not completed")
    if metadata["points"]!=[asdict(p) for p in sweep_points(context)]:raise ValueError("Saved OAT grid differs")
    sources={}
    for name in ("one_factor_evaluations.csv.gz","reference_metrics.csv"):
        sources[str((oat_run/name).resolve())]=verify_file(oat_run/name,metadata["output_hashes"][name])
    for relative,expected in metadata["input_hashes"].items():
        if relative!="configs/d5_protocol.yaml":verify_file(context.root/relative,expected)
    sources[str((oat_run/"input_manifest.json").resolve())]=sha(oat_run/"input_manifest.json")
    scenarios=pd.read_csv(context.root/"reports/d4_scenarios_labelled.csv",low_memory=False)
    scenarios=scenarios[scenarios.stratum.isin(context.d5["inherited_baseline"]["primary_strata"])].sort_values("scenario_id").reset_index(drop=True)
    if len(scenarios)!=metadata["scenario_count"] or not scenarios.scenario_id.is_unique:raise ValueError("Primary population differs")
    out.mkdir(parents=True)
    shutil.copyfile(context.root/"configs/d5_protocol.yaml",out/"protocol_snapshot.yaml")
    code_names=["src/reference_world.py","src/complete_robustness.py","src/sensitivity.py","src/uncertainty.py",
                "src/reference_labeller.py","src/physics_m100.py","src/decision_rules.py","src/safety_invariants.py","src/available_energy.py"]
    for name in code_names:
        destination=out/"code_snapshot"/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(context.root/name,destination)
    manifest=dict(started_at_utc=datetime.now(timezone.utc).isoformat(),status="RUNNING_DEVELOPMENT",protocol_version=context.d5["meta"]["version"],
                  final_d5_complete=False,cross_check_status="PENDING",source_hashes=sources,
                  upstream_input_hashes=context.input_hashes,code_hashes={n:sha(context.root/n) for n in code_names},runtime=runtime())
    write_json(out/"input_manifest.json",manifest)
    try:
        baseline,reference_summary,matched_stats=matched_references(out,context,scenarios,oat_run,metadata)
        cases,proposals,validation,counter_stats=counterfactuals(out,context,scenarios)
        statistics=dict(matched=matched_stats,counterfactual=counter_stats)
        render(out,baseline,reference_summary,cases,proposals,validation,statistics)
        for name,expected in manifest["code_hashes"].items():verify_file(context.root/name,expected)
        if sha(context.root/"configs/d5_protocol.yaml")!=context.input_hashes["configs/d5_protocol.yaml"]:raise ValueError("Protocol changed during run")
        result=dict(status="COMPLETED_MATCHED_REFERENCE_AND_COUNTERFACTUAL_DEVELOPMENT",final_d5_complete=False,cross_check_status="PENDING",
                    completed_at_utc=datetime.now(timezone.utc).isoformat(),statistics=statistics,
                    input_manifest_sha256=sha(out/"input_manifest.json"),
                    output_hashes={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob("*")) if p.is_file()})
        write_json(out/"run_status.json",result)
        print(json.dumps(statistics,indent=2),flush=True)
        print(f"Saved report to {out/'robustness_completion_report.md'}",flush=True)
        return result
    except Exception as error:
        write_json(out/"run_status.json",dict(status="FAILED",error=f"{type(error).__name__}: {error}",final_d5_complete=False))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--oat-run",type=Path,required=True)
    args=parser.parse_args()
    run(args.out,args.oat_run)


if __name__=="__main__":main()
