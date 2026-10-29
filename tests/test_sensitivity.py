"""OAT equations and vectorized verdicts checked against the scalar D3 engine."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.available_energy import available_energy
from src.decision_rules import assess
from src.sensitivity import Point, evaluate, prepare, reference_rows, sweep_points
from src.uncertainty import load_context


@pytest.fixture(scope="module")
def context():
    return load_context()


@pytest.fixture
def scenarios():
    base=dict(scenario_id=1,stratum="main",payload_g=250.,speed_commanded_ms=8.,altitude_m=25.,
              distance_2d_m=500.,wind_forecast_ms=4.,ambient_temp_c=15.,soc=.4,soh=.9)
    return pd.DataFrame([base,{**base,"scenario_id":2,"soc":.2,"wind_forecast_ms":9.8},
                         {**base,"scenario_id":3,"distance_2d_m":800.},
                         {**base,"scenario_id":4,"speed_commanded_ms":18.}])


@pytest.mark.parametrize("battery",["TB47D","TB48D"])
@pytest.mark.parametrize("factor,value",[(None,0.),("soc_error",-.02),("soh_error",-.05),
    ("wind_error",2.),("kappa_error",-.02),("energy_error",-2.),("reserve_policy",.3),
    ("temperature_domain",4.5),("temperature_domain",18.4),("temperature_domain",-10.),
    ("temperature_domain",40.),("soh_domain",.7),("wind_domain",10.),("battery_assumption","TB48D")])
def test_vectorized_matches_scalar_d3(context,scenarios,battery,factor,value,monkeypatch):
    raw=prepare(context,scenarios)
    point=None if factor is None else Point(factor,"test","test",value,"test")
    got=evaluate(context,raw,battery,point)
    for i,row in enumerate(scenarios.to_dict("records")):
        inputs={key:row[key] for key in ["payload_g","speed_commanded_ms","altitude_m","distance_2d_m","wind_forecast_ms","ambient_temp_c","soc","soh"]}
        inputs.update(battery_type=got["effective_battery"],profile="CMU_instrumented")
        for key,field in [("soc","soc"),("soh","soh"),("wind","wind_forecast_ms"),("temp","ambient_temp_c")]:
            inputs[field]=got[key][i]
        # Independent scalar D3 uses the same overridden physical budget for PH-1.
        with monkeypatch.context() as patch:
            if factor=="kappa_error":
                def override(**kw):
                    original=available_energy(**kw)
                    return replace(original,value_Wh=original.e_nominal_Wh*kw['soc']*kw['soh']*(original.kappa+value))
                patch.setattr("src.decision_rules.available_energy",override)
                patch.setattr("src.safety_invariants.available_energy",override)
            expected=assess(**inputs,e_required_Wh=got["required"][i],reserve_factor=got['reserve'][i],protocol=context.d3)
        assert got["verdict"][i]==expected.verdict,(factor,battery,i)
        assert got["veto"][i]==expected.hard_rule_report.must_no_fly
        if expected.margin_Wh is not None:
            assert got["margin"][i]==pytest.approx(expected.margin_Wh)
        original_prediction=context.model.predict(row,context.d4)
        expected_demand=original_prediction+context.model.wind_coefficient*(inputs['wind_forecast_ms']-row['wind_forecast_ms'])
        if factor=="energy_error":expected_demand-=value
        assert got['required'][i]==pytest.approx(expected_demand)


def test_zero_offsets_preserve_every_value(context,scenarios):
    raw=prepare(context,scenarios); base=evaluate(context,raw,"TB47D")
    for factor in ("soc_error","soh_error","wind_error","kappa_error","energy_error"):
        new=evaluate(context,raw,"TB47D",Point(factor,"test","zero",0.,"test"))
        for key in ("required","available","margin","ratio","verdict","slack","veto"):
            np.testing.assert_array_equal(new[key],base[key])


def test_invalid_offset_is_excluded_not_clipped(context,scenarios):
    scenarios['soc']=.99
    got=evaluate(context,prepare(context,scenarios),'TB47D',Point('soc_error','test','p',.05,'fraction'))
    assert not got['valid'].any()
    assert np.all(got['soc']==1.04)
    assert set(got['verdict'])=={'NOT_EVALUATED_INVALID_PERTURBATION'}


def test_kappa_offset_used_in_landing_veto(context,scenarios):
    scenarios=scenarios.iloc[:1].copy()
    raw=prepare(context,scenarios); original=evaluate(context,raw,'TB47D')
    # Place baseline slightly above its physical landing floor.
    scenarios['soc']=raw['landing_TB47D'][0]/(99.9*.9*.9954)*1.005
    raw=prepare(context,scenarios)
    before=evaluate(context,raw,'TB47D')
    after=evaluate(context,raw,'TB47D',Point('kappa_error','test','p',-.05,'absolute'))
    assert not before['landing_veto'][0]
    assert after['landing_veto'][0]


def test_protocol_grid_complete_and_residual_sign(context):
    points=sweep_points(context)
    assert len(points)==254
    assert len([p for p in points if p.factor=='energy_error'])==192
    assert {p.value for p in points if p.factor=='reserve_policy'}=={.1,.15,.2,.25,.3}
    temperatures={p.value for p in points if p.factor=='temperature_domain'}
    assert {4.5,18.4,-10.,40.}<=temperatures
    assert len(temperatures)==13
    assert {p.value for p in points if p.factor=='soc_error' and p.primary_error}=={-.02,0.,.02}


def test_reference_denominators_and_unknowns():
    evaluation=dict(valid=np.array([True,True,True,False]),verdict=np.array(['FLY','CONDITIONAL','NO_FLY','FLY']))
    labels=np.array(['infeasible','marginal','feasible','unknown'])
    rows=reference_rows(evaluation,evaluation,labels,{'all':np.ones(4,bool)}, {},'ref1')
    conservative=rows[0]
    assert conservative['reference_infeasible']==2
    assert conservative['false_safe_count']==1
    assert conservative['false_safe_rate']==.5
    assert conservative['unnecessary_rejection_rate']==1
    assert conservative['invalid_perturbations']==1
    assert conservative['unknown_reference']==1
    assert rows[1]['reference_infeasible']==1
    assert rows[1]['reference_feasible']==2
    assert rows[1]['false_safe_rate']==1.


def test_zero_reference_denominator_is_missing():
    evaluation=dict(valid=np.ones(2,bool),verdict=np.array(['FLY','FLY']))
    rows=reference_rows(evaluation,evaluation,np.array(['feasible','feasible']),{'all':np.ones(2,bool)}, {},'ref1')
    assert rows[0]['false_safe_rate'] is None
    assert rows[0]['infeasible_recall'] is None
