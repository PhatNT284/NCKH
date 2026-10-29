import hashlib

import numpy as np
import pandas as pd
import pytest

from src.d5_report import Evidence,candidate_fly_count,ratio,validate_mc


def mc_fixture():
    meta=dict(configurations=['PRIMARY'],battery_types=['TB47D'],seeds=[42],selected_scenario_ids=[1,2],draws_per_scenario=10)
    frame=pd.DataFrame([dict(assumption_config_id='PRIMARY',battery_type='TB47D',seed=42,scenario_count=2,
                            draws_total=20,valid_draws=18,invalid_draws=2,energy_success_count=15,joint_success_count=12,
                            energy_feasibility_fraction=15/18,joint_feasibility_fraction=12/18)])
    return frame,meta


def test_mc_summary_uses_counts_and_declared_sampling_grid():
    frame,meta=mc_fixture()
    numbers=validate_mc(frame,meta)
    assert numbers==dict(scenarios=2,result_rows=2,total_draws=20,valid_draws=18,invalid_draws=2)


@pytest.mark.parametrize('change', ['duplicates','missing_group','numerator','denominator','fraction'])
def test_inconsistent_mc_evidence_cannot_be_published(change):
    frame,meta=mc_fixture()
    if change=='duplicates':frame=pd.concat([frame,frame],ignore_index=True)
    elif change=='missing_group':meta['seeds']=[42,43]
    elif change=='numerator':frame.loc[0,'joint_success_count']=16
    elif change=='denominator':frame.loc[0,'invalid_draws']=0
    else:frame.loc[0,'energy_feasibility_fraction']=.99
    with pytest.raises(ValueError):validate_mc(frame,meta)


def test_zero_denominator_is_na_not_zero_rate():
    frame,meta=mc_fixture()
    frame.loc[0,['valid_draws','energy_success_count','joint_success_count']]=0
    frame.loc[0,'invalid_draws']=20
    frame.loc[0,['energy_feasibility_fraction','joint_feasibility_fraction']]=np.nan
    assert validate_mc(frame,meta)['valid_draws']==0
    assert ratio(0,0)=='0/0 (NA)'


def test_source_hash_mismatch_and_mid_run_change_are_rejected(tmp_path):
    path=tmp_path/'evidence.json';path.write_text('old',encoding='utf-8')
    registry=Evidence()
    with pytest.raises(ValueError,match='hash mismatch'):registry.verify(path,'0'*64)
    expected=hashlib.sha256(b'old').hexdigest()
    assert registry.verify(path,expected)==expected
    path.write_text('changed-length',encoding='utf-8')
    with pytest.raises(ValueError,match='changed during'):registry.verify(path)


def test_reference_partition_reconstructs_candidate_fly_without_pooling_refs():
    row=pd.Series(dict(false_safe_count=10,reference_feasible=20,unnecessary_rejection_count=5,
                       conditional_count_among_feasible=8,scored_scenarios=50))
    assert candidate_fly_count(row)==17
    row['false_safe_count']=100
    with pytest.raises(ValueError,match='does not reconcile'):candidate_fly_count(row)


def test_replacement_is_allowed_only_with_exact_original_hash_and_remains_auditable(tmp_path):
    original=tmp_path/'current.csv';original.write_text('rounded',encoding='utf-8')
    replacement=tmp_path/'recovered.csv';replacement.write_text('precise',encoding='utf-8')
    expected=hashlib.sha256(b'precise').hexdigest()
    registry=Evidence({original:replacement})
    assert registry.verify(original,expected)==expected
    recorded=registry.replacements[str(original.resolve())]
    assert recorded['verified_replacement']==str(replacement.resolve())
    assert registry.files[str(original.resolve())]['sha256']!=expected
    with pytest.raises(ValueError,match='hash mismatch'):Evidence({original:replacement}).verify(original,'0'*64)
