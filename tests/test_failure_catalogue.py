"""Selection integrity: minimum IDs, explicit scopes and no invented transitions."""
from copy import deepcopy
from dataclasses import replace
import json

import pandas as pd
import pytest

from src.failure_catalogue import (Selector, clean, describe_point, oat_case, point_scope,
                                   scan_oat, verify_file, workflow_cases)
from src.mission_record import digest
from src.sensitivity import Point, evaluate, prepare
from src.uncertainty import load_context


@pytest.fixture(scope="module")
def context():
    return load_context()


def row(sid, point_id="1", value="-0.02", primary=True, battery="TB47D", **changes):
    value0=dict(scenario_id=sid,stratum="main",baseline_verdict="FLY",reassessed_verdict="NO_FLY",status="OK",
                required_Wh=20.,available_Wh=23.,margin_Wh=3.,margin_ratio=.15,
                delta_required_Wh=0.,delta_available_Wh=-7.,delta_margin_Wh=-7.,reserve_ratio=.2,
                reserve_slack_Wh=-1.,reserve_met=0.,veto=False,soc=.38,soh=.9,wind_ms=3.,temperature_c=15.,
                kappa=.9954,distance_extrapolated=False,wind_extrapolated=False,temperature_outside_calibration=False,
                fixed_label_ref1="marginal",fixed_label_ref2="marginal",battery_type=battery,
                effective_battery=battery,factor="soc_error",sweep_kind="input_error",point_id=point_id,
                point_value=value,point_unit="fraction",primary_error_point=primary)
    return {**value0,**changes}


def source_scenarios(ids):
    return pd.DataFrame([dict(scenario_id=i,stratum="main",soc=.4,soh=.9,wind_forecast_ms=3.,ambient_temp_c=15.,
                              margin_ratio_ref1=.19,margin_ratio_ref2=.21,label_ref1="marginal",label_ref2="marginal")
                         for i in ids]).set_index("scenario_id")


def metadata(count):
    return dict(total_evaluations=count,points=[dict(factor="soc_error",point_id=str(i)) for i in (0,1,2)])


def test_selection_uses_smallest_id_not_biggest_shortfall_and_is_chunk_independent(tmp_path,context):
    rows=[row(10, reserve_slack_Wh=-100),row(1,"0","-0.05",False),row(5),row(1),
          row(0,status="NOT_EVALUATED_INVALID_PERTURBATION"),row(3,battery="TB48D")]
    path=tmp_path/"saved.csv.gz"
    pd.DataFrame(rows).to_csv(path,index=False,compression="gzip")
    a,stats=scan_oat(path,metadata(len(rows)),source_scenarios([0,1,3,5,10]),context,chunksize=2)
    b,_=scan_oat(path,metadata(len(rows)),source_scenarios([0,1,3,5,10]),context,chunksize=100)
    assert a.best==b.best
    chosen=a.best[("soc_overstatement","TB47D",None)][1]
    assert chosen["scenario_id"]==1
    assert chosen["primary_error_point"] is True
    assert chosen["point_id"]=="1"
    assert a.best[("soc_overstatement","TB48D",None)][1]["scenario_id"]==3
    assert stats==dict(scanned_rows=6,valid_rows=5,invalid_rows=1)
    # Boundary analysis may use the wider grid; it is explicitly labelled as such.
    boundary=a.best[("boundary_verdict_flip","TB47D","ref1")][1]
    assert boundary["scenario_id"]==1 and boundary["point_id"]=="0"
    assert point_scope(boundary)=="Khoảng sai lệch rộng"


def test_selector_keeps_references_distinct_and_counts_distinct_ids():
    frame=pd.DataFrame([row(1),row(1,"2","0"),row(2)])
    selector=Selector({("soc_error",str(i)):i for i in (1,2)})
    selector.consider(frame,frame.scenario_id>0,"boundary_verdict_flip","ref1")
    selector.consider(frame,frame.scenario_id==2,"boundary_verdict_flip","ref2")
    assert selector.best[("boundary_verdict_flip","TB47D","ref1")][1]["scenario_id"]==1
    assert selector.best[("boundary_verdict_flip","TB47D","ref2")][1]["scenario_id"]==2
    assert selector.observed[("boundary_verdict_flip","TB47D","ref1")]==3
    assert len(selector.ids[("boundary_verdict_flip","TB47D","ref1")])==2


def test_truncated_or_unknown_scenario_output_is_rejected(tmp_path,context):
    path=tmp_path/"saved.csv.gz"
    pd.DataFrame([row(1)]).to_csv(path,index=False,compression="gzip")
    with pytest.raises(ValueError,match="row count"):
        scan_oat(path,metadata(2),source_scenarios([1]),context)
    with pytest.raises(ValueError,match="unknown scenario"):
        scan_oat(path,metadata(1),source_scenarios([2]),context)


def test_modified_saved_file_is_rejected(tmp_path):
    path=tmp_path/"evidence.json"
    path.write_text("different",encoding="utf-8")
    with pytest.raises(ValueError,match="hash mismatch"):
        verify_file(path,"0"*64)


def test_changed_current_reserve_cannot_reinterpret_saved_results(tmp_path,context):
    path=tmp_path/"saved.csv.gz"
    pd.DataFrame([row(1)]).to_csv(path,index=False,compression="gzip")
    settings=deepcopy(context.d5)
    settings["inherited_baseline"]["decision_policy"]["reserve_ratio"]=.3
    with pytest.raises(ValueError,match="baseline reserve differs"):
        scan_oat(path,metadata(1),source_scenarios([1]),replace(context,d5=settings))


def actual_zero_row(context):
    inputs=dict(scenario_id=1,stratum="main",payload_g=250.,speed_commanded_ms=8.,altitude_m=50.,
                distance_2d_m=472.,wind_forecast_ms=3.,ambient_temp_c=15.,soc=.235,soh=.95,
                margin_ratio_ref1=.19,margin_ratio_ref2=.18,label_ref1="marginal",label_ref2="marginal")
    source=pd.DataFrame([inputs])
    r=evaluate(context,prepare(context,source),"TB47D")
    selected=row(1,"2","0",True,baseline_verdict=str(r["verdict"][0]),reassessed_verdict=str(r["verdict"][0]),
                 required_Wh=float(r["required"][0]),available_Wh=float(r["available"][0]),margin_Wh=float(r["margin"][0]),
                 margin_ratio=float(r["ratio"][0]),delta_required_Wh=0.,delta_available_Wh=0.,delta_margin_Wh=0.,
                 reserve_slack_Wh=float(r["slack"][0]),reserve_met=float(r["reserve_ok"][0]),
                 soc=.235,soh=.95,temperature_c=15.,source_record_index=1)
    return source.set_index("scenario_id"),selected


def test_marginal_mapping_does_not_claim_verdict_or_input_change(context,tmp_path):
    scenarios,selected=actual_zero_row(context)
    case=oat_case(context,scenarios,"marginal_mapping_effect","TB47D","ref1",selected,tmp_path/"source.csv.gz",{})
    assert case["event_kind"]=="SCORING_POLICY_CHANGE"
    assert not case["changed_verdict_or_reserve_failure"]["verdict_changed"]
    assert case["baseline_verdict"]==case["changed_verdict_or_reserve_failure"]["reassessed_verdict"]
    assert case["baseline_inputs"]["soc"]==case["changed_inputs"]["soc"]
    assert case["reference_details"]["mapping_before"]=="INFEASIBLE"
    assert case["reference_details"]["mapping_after"]=="FEASIBLE"
    assert case["mitigation_if_valid"] is None


@pytest.mark.parametrize("field",["margin_Wh","reserve_slack_Wh"])
def test_catalogue_rejects_inconsistent_saved_energy(context,tmp_path,field):
    scenarios,selected=actual_zero_row(context)
    selected[field]+=1
    with pytest.raises(ValueError,match="Inconsistent saved OAT energy"):
        oat_case(context,scenarios,"marginal_mapping_effect","TB47D","ref1",selected,tmp_path/"source.csv.gz",{})


def test_saved_veto_cannot_be_silently_ignored(context,tmp_path):
    scenarios,selected=actual_zero_row(context)
    selected["veto"]=True
    with pytest.raises(ValueError,match="VETO differs"):
        oat_case(context,scenarios,"marginal_mapping_effect","TB47D","ref1",selected,tmp_path/"source.csv.gz",{})


@pytest.mark.parametrize("point,expected",[(row(1),"giảm 2 điểm phần trăm"),
                                           (row(1,factor="energy_error",point_value="-2"),"tăng 2.0000 Wh"),
                                           (row(1,factor="battery_assumption",point_value="TB48D"),"pin TB48D"),
                                           (row(1,"2","0"),"Giữ nguyên")])
def test_plain_language_changes_keep_signs_and_units(point,expected):
    assert expected in describe_point(point)


def test_workflow_fixture_never_invents_scenario_id_or_previous_fly(tmp_path):
    names=["missing_soc","nan_wind","invalid_soc","expired_weather","missing_weather_window",
           "conditional_fake_mitigation","preflight_degraded","conditional","stock_fly","conditional_mitigated"]
    snapshots=tmp_path/"snapshots"
    snapshots.mkdir()
    evidence=[]
    for name in names:
        verdict="CONDITIONAL" if name.startswith("conditional") or name=="preflight_degraded" else "INSUFFICIENT_DATA"
        if name=="stock_fly":verdict="FLY"
        data=dict(assessment_id=name,inputs=dict(soc=None,battery_type="TB47D"),weather={},assessed_at="2026-10-26T01:00:00+00:00",
                  result=dict(verdict=verdict,decision={},weather_issues=[],mitigation_validated=name=="conditional_mitigated"),
                  mitigation=None)
        if name=="conditional_fake_mitigation":data["previous_assessment_id"]="conditional"
        if name=="preflight_degraded":data["previous_assessment_id"]="stock_fly"
        (snapshots/f"{name}.json").write_text(json.dumps(dict(sha256=digest(data),assessment=data)),encoding="utf-8")
        evidence.append(dict(check=f"blocks_{name}",passed=True,detail="blocked fixture"))
    (tmp_path/"workflow_checks.json").write_text(json.dumps(evidence),encoding="utf-8")
    cases=workflow_cases(tmp_path)
    assert len(cases)==7 and all(c["scenario_id"] is None for c in cases)
    assert next(c for c in cases if c["assessment_id"]=="missing_soc")["baseline_verdict"] is None
    worse=next(c for c in cases if c["assessment_id"]=="preflight_degraded")
    assert worse["baseline_verdict"]=="FLY"
    assert worse["changed_verdict_or_reserve_failure"]["reassessed_verdict"]=="CONDITIONAL"


def test_json_unknown_values_are_null_not_zero():
    assert clean(dict(value=float("nan"),nested=[float("inf"),None]))==dict(value=None,nested=[None,None])
