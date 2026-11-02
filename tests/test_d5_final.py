import pandas as pd
import pytest

from src.d5_final import compare_csv
from src import d5_final as rerun_d5
import json
from types import SimpleNamespace
import stat


def test_comparison_detects_changed_counts_and_verdicts(tmp_path):
    old, new = tmp_path/'old.csv', tmp_path/'new.csv'
    pd.DataFrame({'run_id':['old'], 'count':[3], 'verdict':['FLY']}).to_csv(old, index=False)
    pd.DataFrame({'run_id':['new'], 'count':[4], 'verdict':['NO_FLY']}).to_csv(new, index=False)
    rows = compare_csv(new, old)
    assert {r['column']:r['mismatches'] for r in rows} == {'count':1, 'verdict':1}
    assert rows[0]['max_absolute_difference'] == 1


def test_comparison_rejects_extra_rows(tmp_path):
    old, new = tmp_path/'old.csv', tmp_path/'new.csv'
    pd.DataFrame({'count':[3]}).to_csv(old, index=False)
    pd.DataFrame({'count':[3, 4]}).to_csv(new, index=False)
    with pytest.raises(ValueError, match='Row count mismatch'):
        compare_csv(new, old)


def test_historical_source_requires_exact_recovery_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(rerun_d5, 'ROOT', tmp_path)
    root = tmp_path/'reports/d5'
    original = root/'all_scenarios_dev_01'
    recovery = root/'mc_csv_recovery_20261026_01'
    original.mkdir(parents=True)
    recovery.mkdir()
    name = 'monte_carlo_fractions.csv'
    (original/name).write_text('rounded')
    (recovery/name).write_text('exact')
    (original/'run_status.json').write_text(json.dumps({'output_hashes':{name:rerun_d5.sha(recovery/name)}}))
    selected, audit = rerun_d5.historical_source('mc', name)
    assert selected == recovery/name
    assert audit['verified']
    (recovery/name).write_text('also corrupted')
    with pytest.raises(ValueError, match='Historical output hash mismatch'):
        rerun_d5.historical_source('mc', name)


@pytest.mark.parametrize('version,frozen,approval',[
    ('0.6.1',False,'PENDING'),('1.0.0',False,'APPROVED'),('1.0.0',True,'PENDING')])
def test_final_run_rejects_unapproved_protocol(version,frozen,approval):
    context=SimpleNamespace(d5={'meta':dict(version=version,frozen=frozen,cross_check_status=approval)})
    with pytest.raises(ValueError,match='frozen D5 protocol'):
        rerun_d5.require_frozen(context)


def test_gate_rejects_source_change(tmp_path,monkeypatch):
    gate=tmp_path/'gate.json'
    gate.write_text(json.dumps(dict(exit_code=0,passed=10,code_hashes={'src/model.py':'old'})))
    monkeypatch.setattr(rerun_d5,'code_hashes',lambda:{'src/model.py':'new'})
    with pytest.raises(ValueError,match='changed after'):
        rerun_d5.verify_test_gate(gate)


def test_seal_records_hash_and_sets_readonly(tmp_path):
    artifact=tmp_path/'result.csv'
    artifact.write_text('count\n42\n')
    try:
        rerun_d5.seal(tmp_path)
        ledger=json.loads((tmp_path/'output_hashes.json').read_text())
        assert ledger['result.csv']==rerun_d5.sha(artifact)
        assert not artifact.stat().st_mode & stat.S_IWRITE
    finally:
        import os
        os.chmod(tmp_path,stat.S_IREAD|stat.S_IWRITE|stat.S_IEXEC)
        for path in tmp_path.iterdir():
            os.chmod(path,stat.S_IREAD|stat.S_IWRITE)


def test_boundary_membership_uses_each_reference_separately():
    scenarios=pd.DataFrame(dict(scenario_id=[1,2],margin_ratio_ref1=[0.,.6],margin_ratio_ref2=[.6,.2]))
    chunk=pd.DataFrame(dict(scenario_id=[1,2,1],battery_type=['TB47D']*3,
        baseline_verdict=['FLY']*3,reassessed_verdict=['NO_FLY','CONDITIONAL','FLY'],
        status=['OK','OK','INVALID'],sweep_kind=['input_error']*3))
    result=rerun_d5.boundary_transition_counts([chunk],scenarios,[.05],.2)
    assert result[result.reference_model=='REF-1'].iloc[0].reassessed_verdict=='NO_FLY'
    assert result[result.reference_model=='REF-2'].iloc[0].reassessed_verdict=='CONDITIONAL'
    assert result['count'].sum()==2
