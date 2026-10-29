from dataclasses import replace
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from src.complete_robustness import action_targets, select_model_proposals
from src.decision_rules import assess
from src.physics_m100 import ideal_hover_power_W
from src.reference_world import WorldEvaluator,label_energy
from src.uncertainty import load_context

BASE=dict(payload_g=250.,speed_commanded_ms=8.,altitude_m=50.,distance_2d_m=472.,wind_forecast_ms=3.,
          ambient_temp_c=15.,soc=.235,soh=.95,battery_type="TB47D",reserve_factor=.2)


@pytest.fixture(scope="module")
def context():return load_context()


def test_no_change_references_reproduce_entire_original_d4_population(context):
    source=pd.read_csv(context.root/"reports/d4_scenarios_labelled.csv",low_memory=False)
    source=source[source.stratum.isin(["main","short_high"])].assign(battery_type="TB47D")
    result=WorldEvaluator(context).evaluate(source)
    assert result["valid"].all()
    np.testing.assert_allclose(result["available"],source.e_available_Wh,rtol=1e-10,atol=1e-10)
    for ref in ("ref1","ref2"):
        np.testing.assert_allclose(result[f"{ref}_demand"],source[f"e_reference_{ref}_Wh"],rtol=1e-10,atol=1e-10)
        assert np.array_equal(result[f"{ref}_label"],source[f"label_{ref}"])


@pytest.mark.parametrize("battery",["TB47D","TB48D"])
@pytest.mark.parametrize("profile",["CMU_instrumented","M100_stock"])
@pytest.mark.parametrize("changes",[{},dict(soc=.7),dict(soc=.1),dict(wind_forecast_ms=12),dict(payload_g=1500),
                                    dict(ambient_temp_c=-10),dict(distance_2d_m=300),dict(soc=1.5),dict(ambient_temp_c=18.4)])
def test_vector_world_matches_scalar_d3(context,battery,profile,changes):
    inputs={**BASE,**changes,"battery_type":battery,"profile":profile}
    result=WorldEvaluator(context).evaluate(pd.DataFrame([inputs]))
    prediction=context.model.predict(inputs,context.d4)
    scalar=assess(**inputs,e_required_Wh=prediction,protocol=context.d3)
    assert result["verdict"][0]==scalar.verdict
    assert result["prediction"][0]==pytest.approx(prediction,abs=1e-12)
    if scalar.e_available_Wh is not None:
        assert result["available"][0]==pytest.approx(scalar.e_available_Wh,abs=1e-10)


def test_candidate_residual_and_policy_do_not_move_reference_goalposts(context):
    evaluator=WorldEvaluator(context)
    original=evaluator.evaluate(pd.DataFrame([BASE]))
    changed=evaluator.evaluate(pd.DataFrame([{**BASE,"reserve_factor":.3}]),candidate_demand=original["required"]+2)
    assert changed["required"][0]==pytest.approx(original["required"][0]+2)
    for ref in ("ref1","ref2"):
        np.testing.assert_array_equal(changed[f"{ref}_label"],original[f"{ref}_label"])
        np.testing.assert_allclose(changed[f"{ref}_demand"],original[f"{ref}_demand"])


def test_changed_payload_route_and_speed_recompute_both_demands(context):
    inputs={**BASE,"payload_g":0.,"distance_2d_m":420.,"speed_commanded_ms":6.}
    result=WorldEvaluator(context).evaluate(pd.DataFrame([inputs]))
    expected1=context.model.predict(inputs,context.d4)+1.2924
    expected2=7.44*ideal_hover_power_W(3.680)*420/6/3600
    assert result["ref1_demand"][0]==pytest.approx(expected1,abs=1e-12)
    assert result["ref2_demand"][0]==pytest.approx(expected2,abs=1e-12)


def test_kappa_override_is_shared_by_both_reference_labels_and_landing_check(context):
    evaluator=WorldEvaluator(context)
    normal=evaluator.evaluate(pd.DataFrame([BASE]))
    changed=evaluator.evaluate(pd.DataFrame([BASE]),kappa_override=[.01])
    assert changed["available"][0]<normal["available"][0]
    assert changed["landing_veto"][0]
    assert changed["ref1_label"][0]==changed["ref2_label"][0]=="infeasible"


def test_battery_assumption_uses_same_configured_cmu_mass_and_new_capacity(context):
    evaluator=WorldEvaluator(context)
    result=evaluator.evaluate(pd.DataFrame([BASE,{**BASE,"battery_type":"TB48D"}]))
    assert result["mass_g"][0]==result["mass_g"][1]
    assert result["ref2_demand"][0]==result["ref2_demand"][1]
    assert result["available"][1]/result["available"][0]==pytest.approx(129.96/99.9)


def test_reference_classes_and_invalid_unknown_are_not_zeroed():
    available=np.array([20.,22.,24.,100.])
    labels,_=label_energy(available,np.array([20.,20.,20.,20.]),np.array([True,True,True,False]),.2)
    assert list(labels)==["infeasible","marginal","feasible","unknown"]


def test_targets_are_ordered_smallest_change_and_inside_supported_control_ranges(context):
    field,targets=action_targets("M1",BASE,context)
    assert field=="soc" and targets[0]==.24 and targets[-1]==1.
    assert all(a<b for a,b in zip(targets,targets[1:]))
    field,targets=action_targets("M7",BASE,context)
    assert targets==[470.,460.,450.,440.,430.,420.]
    assert action_targets("M7",{**BASE,"distance_2d_m":300.},context)[1]==[]
    assert action_targets("M5",{**BASE,"payload_g":400.},context)[1]==[250.,0.]
    assert action_targets("M6",{**BASE,"speed_commanded_ms":9.},context)[1]==[8.,6.,4.]
    assert action_targets("M3",BASE,context)[1]==[]
    assert action_targets("M3",{**BASE,"wind_forecast_ms":12.},context)[1]==[10.]


def test_proposal_selection_is_reference_blind_and_retains_minimum_change():
    trials=pd.DataFrame([
        dict(case_id="A",action="M1",trial_id="first",evaluated=True,candidate_verdict="CONDITIONAL",veto=False,baseline_verdict="CONDITIONAL",change_size=.01,reference1_primary_pass=False),
        dict(case_id="A",action="M1",trial_id="model_accepts",evaluated=True,candidate_verdict="FLY",veto=False,baseline_verdict="CONDITIONAL",change_size=.02,reference1_primary_pass=False),
        dict(case_id="A",action="M1",trial_id="ref_accepts",evaluated=True,candidate_verdict="FLY",veto=False,baseline_verdict="CONDITIONAL",change_size=.03,reference1_primary_pass=True),
        dict(case_id="B",action="M1",trial_id="veto",evaluated=True,candidate_verdict="FLY",veto=True,baseline_verdict="CONDITIONAL",change_size=.01,reference1_primary_pass=True)])
    selected=select_model_proposals(trials)
    assert trials.loc[selected].trial_id.tolist()==["model_accepts"]
    swapped=trials.copy();swapped["reference1_primary_pass"]=~swapped.reference1_primary_pass
    assert selected.tolist()==select_model_proposals(swapped).tolist()


def test_unknown_battery_and_nan_do_not_produce_fly(context):
    result=WorldEvaluator(context).evaluate(pd.DataFrame([{**BASE,"battery_type":"UNKNOWN"},{**BASE,"soc":np.nan}]))
    assert not (result["verdict"]=="FLY").any()
    assert (result["ref1_label"]=="unknown").all()
