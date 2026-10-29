from dataclasses import asdict
import json

import pandas as pd
import pytest

from src.complete_robustness import counterfactuals,matched_references
from src.sensitivity import Point,evaluate,prepare,reference_rows,reference_scopes
from src.uncertainty import load_context


@pytest.fixture(scope="module")
def context():return load_context()


@pytest.fixture
def scenarios(context):
    source=pd.read_csv(context.root/"reports/d4_scenarios_labelled.csv",low_memory=False)
    return source[source.scenario_id.isin([5,10,13])].sort_values("scenario_id").reset_index(drop=True)


def test_matched_pipeline_reconciles_small_saved_oat_population(tmp_path,context,scenarios):
    source=tmp_path/"source";source.mkdir()
    out=tmp_path/"result";out.mkdir()
    points=[Point("soc_error","input_error","2",0.,"fraction",True),
            Point("battery_assumption","battery_assumption","TB48D","TB48D","battery"),
            Point("energy_error","empirical_error","negative",-2.,"Wh",True),
            Point("wind_error","input_error","wind",1.,"m/s",True)]
    blocks=[];metrics=[]
    raw=prepare(context,scenarios)
    for battery in ("TB47D","TB48D"):
        before=evaluate(context,raw,battery)
        for point in points:
            world=evaluate(context,raw,battery,point)
            meta=dict(battery_type=battery,effective_battery=world["effective_battery"],factor=point.factor,
                      sweep_kind=point.kind,point_id=point.point_id,point_value=point.value,point_unit=point.unit,
                      primary_error_point=point.primary_error)
            rows=pd.DataFrame(dict(scenario_id=scenarios.scenario_id,status="OK",required_Wh=world["required"],
                                  available_Wh=world["available"],reserve_ratio=world["reserve"],
                                  reassessed_verdict=world["verdict"],soc=world["soc"],soh=world["soh"],
                                  wind_ms=world["wind"],temperature_c=world["temp"],kappa=world["kappa"])).assign(**meta)
            blocks.append(rows)
            for ref in ("ref1","ref2"):
                metrics.extend(reference_rows(world,before,scenarios[f"label_{ref}"].to_numpy(),reference_scopes(context,scenarios,ref),meta,ref))
    pd.concat(blocks).to_csv(source/"one_factor_evaluations.csv.gz",index=False,compression="gzip")
    pd.DataFrame(metrics).to_csv(source/"reference_metrics.csv",index=False)
    baseline,summary,stats=matched_references(out,context,scenarios,source,dict(batteries=["TB47D","TB48D"],total_evaluations=24))
    assert stats["evaluated_rows"]==24 and stats["valid_rows"]==24
    assert len(baseline)==6 and len(summary)==8
    labels=pd.read_csv(out/"matched_reference_labels.csv.gz")
    assert len(labels)==24
    before=labels[(labels.factor=="soc_error")&(labels.battery_type=="TB47D")].set_index("scenario_id")
    residual=labels[(labels.factor=="energy_error")&(labels.battery_type=="TB47D")].set_index("scenario_id")
    assert before.matched_demand_ref1_Wh.equals(residual.matched_demand_ref1_Wh)
    assert before.matched_demand_ref2_Wh.equals(residual.matched_demand_ref2_Wh)
    transitions=pd.read_csv(out/"reference_label_transitions.csv")
    assert transitions["count"].sum()==48  # 24 cases, two reference models
    metrics=pd.read_csv(out/"matched_reference_metrics.csv")
    assert set(metrics.scope_membership_policy)=={"ORIGINAL_D4","RECOMPUTED_WORLD"}
    assert set(metrics.marginal_mapping)=={"INFEASIBLE","FEASIBLE"}


def test_counterfactual_pipeline_retains_failed_and_inapplicable_trials(tmp_path,context,scenarios):
    cases,proposals,summary,stats=counterfactuals(tmp_path,context,scenarios)
    selection=json.loads((tmp_path/"selection_manifest.json").read_text(encoding="utf-8"))
    trials=pd.read_csv(tmp_path/"counterfactual_trials.csv.gz")
    assert selection["case_count"]==4 and stats["selected_scenario_ids"]==2
    assert len(cases)==4
    assert trials.groupby("case_id").action.nunique().eq(7).all()
    assert (trials.status=="NOT_APPLICABLE").any()
    assert ((trials.candidate_verdict!="FLY")&trials.evaluated).any()
    assert trials.evaluated.sum()==stats["evaluated_trials"]
    assert len(proposals)==trials.proposed_by_candidate.sum()
    assert proposals.candidate_verdict.eq("FLY").all()
    assert not proposals.veto.astype(bool).any()
    assert not proposals.operational_approval.astype(bool).any()
    missing=summary[(summary.action=="M3")&(summary.support=="all")]
    assert missing.offered_proposals.eq(0).all() and missing.pass_rate.isna().all()
    assert summary.reference_passed.le(summary.offered_proposals).all()
