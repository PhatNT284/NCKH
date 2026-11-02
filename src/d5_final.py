"""Execute the frozen D5 v1.0.0 protocol and preserve verifiable evidence.

Run from the repository after the full pytest gate has passed:
python -m src.d5_final --run-id final_v1_NEW_ID --test-gate PATH
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import os
import stat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from src.uncertainty import load_context, INPUT_FIELDS
from src.sensitivity import prepare, evaluate, sha
from src.decision_rules import assess
from src.reference_labeller import e_reference_ref2


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def baseline(out, context):
    frame = pd.read_csv(ROOT / context.d5['inherited_baseline']['scenario_file'], low_memory=False)
    primary = frame[frame.stratum.isin(context.d5['inherited_baseline']['primary_strata'])].sort_values('scenario_id')
    raw = prepare(context, primary)
    checks = []
    def numbers(name, actual, expected):
        delta = float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))
        passed = bool(np.allclose(actual, expected, atol=1e-8, rtol=1e-8))
        checks.append(dict(check=name, passed=passed, max_absolute_difference=delta))
    prediction = raw['prediction']
    numbers('D2_prediction_vs_saved_D4_REF1_minus_allowance', prediction,
            primary.e_reference_ref1_Wh.to_numpy()-context.d5['inherited_baseline']['reference1_allowance_Wh'])
    numbers('REF2_energy_vs_saved_D4', e_reference_ref2(primary, context.d4), primary.e_reference_ref2_Wh)
    for battery in ('TB47D', 'TB48D'):
        vector = evaluate(context, raw, battery)
        scalar = [assess(**{k: row[k] for k in INPUT_FIELDS}, battery_type=battery,
                         profile=context.d5['inherited_baseline']['aircraft_profile']['primary_diagnostic'],
                         e_required_Wh=float(prediction[i]), protocol=context.d3)
                  for i, row in enumerate(primary.to_dict('records'))]
        checks.append(dict(check=f'{battery}_vector_vs_D3_scalar_verdict', passed=bool(np.array_equal(
            vector['verdict'], [d.verdict for d in scalar])), evaluated=len(scalar)))
        numbers(f'{battery}_available_vs_D3_scalar', vector['available'], [d.available.value_Wh for d in scalar])
        if battery == 'TB47D':
            numbers('available_vs_saved_D4', vector['available'], primary.e_available_Wh)
            for ref in ('ref1', 'ref2'):
                energy = primary[f'e_reference_{ref}_Wh'].to_numpy()
                margin = vector['available']-energy
                ratio = margin/energy
                numbers(f'{ref}_margin_vs_saved_D4', margin, primary[f'margin_{ref}_Wh'])
                numbers(f'{ref}_ratio_vs_saved_D4', ratio, primary[f'margin_ratio_{ref}'])
                labels = np.where(margin <= 0, 'infeasible', np.where(
                    ratio < context.d5['inherited_baseline']['reference_reserve_ratio'], 'marginal', 'feasible'))
                checks.append(dict(check=f'{ref}_labels_vs_saved_D4', passed=bool(np.array_equal(labels, primary[f'label_{ref}']))))
    result = dict(status='PASSED' if all(c['passed'] for c in checks) else 'FAILED',
                  total_scenarios=len(frame), primary_scenarios=len(primary),
                  excluded_strata=frame[~frame.index.isin(primary.index)].stratum.value_counts().to_dict(),
                  estimator_artifact=context.d5['inherited_baseline']['frozen_estimator_artifact'],
                  estimator_sha256=context.input_hashes[context.d5['inherited_baseline']['frozen_estimator_artifact']],
                  input_hashes=context.input_hashes, numerical_atol=1e-8, numerical_rtol=1e-8, checks=checks)
    save(out/'baseline_consistency.json', result)
    if result['status'] != 'PASSED':
        raise ValueError('Baseline consistency failed; simulations were not started')
    return result


def compare_csv(new, old, columns=None):
    """Compare parsed values exactly, excluding only declared provenance/timing columns."""
    ignored = {'run_id', 'protocol_version', 'input_manifest_hash', 'artifact_id', 'batch_seconds', 'processing_batch_seconds'}
    rows = []
    for a, b in zip(pd.read_csv(new, chunksize=20000, low_memory=False),
                    pd.read_csv(old, chunksize=20000, low_memory=False)):
        if len(a) != len(b):
            raise ValueError(f'Row count mismatch: {new}')
        cols = columns if columns is not None else [c for c in a if c not in ignored]
        for col in cols:
            x, y = a[col], b[col]
            same = (x.eq(y) | (x.isna() & y.isna()))
            numeric = pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y)
            delta = (x.astype(float)-y.astype(float)).abs().max() if numeric else None
            rows.append(dict(table=new.name, column=col, rows=len(a), mismatches=int((~same).sum()),
                             max_absolute_difference=None if delta is None or pd.isna(delta) else float(delta)))
    # Check full lengths independently, including unmatched final chunks.
    counts = [sum(len(c) for c in pd.read_csv(p, chunksize=50000, usecols=[0])) for p in (new, old)]
    if counts[0] != counts[1]:
        raise ValueError(f'Row count mismatch: {new}: {counts}')
    return rows


def historical_source(folder, name):
    runs = {'mc':('all_scenarios_dev_01', 'run_status.json', 'output_hashes'),
            'oat':('oat_all_scenarios_20261025_01', 'input_manifest.json', 'output_hashes'),
            'replay':('replay_workflow_20261026_03', 'validation_manifest.json', 'outputs'),
            'catalogue':('failure_catalogue_20261026_03', 'catalogue_manifest.json', 'outputs'),
            'matched':('matched_counterfactual_20261026_01', 'run_status.json', 'output_hashes')}
    run, manifest_name, key = runs[folder]
    directory = ROOT/'reports/d5'/run
    metadata = json.loads((directory/manifest_name).read_text(encoding='utf-8'))
    expected = metadata[key][name]
    original = directory/name
    original_hash = sha(original) if original.exists() else None
    selected = original
    if original_hash != expected and folder == 'mc' and name == 'monte_carlo_fractions.csv':
        selected = ROOT/'reports/d5/mc_csv_recovery_20261026_01'/name
    if not selected.exists() or sha(selected) != expected:
        raise ValueError(f'Historical output hash mismatch: {selected}')
    return selected, dict(original_path=str(original), original_sha256=original_hash,
                          selected_path=str(selected), expected_sha256=expected, verified=True)


def figures(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    dest = out/'figures'
    dest.mkdir()
    for source, name in [('false_safe_vs_reserve', 'reserve_tradeoff')]:
        shutil.copy2(out/'oat/figures'/f'{source}.png', dest/f'{name}.png')
    context = load_context()
    scenarios = pd.read_csv(ROOT/context.d5['inherited_baseline']['scenario_file'],low_memory=False)
    columns = ['scenario_id','battery_type','baseline_verdict','reassessed_verdict','status','sweep_kind']
    chunks = pd.read_csv(out/'oat/one_factor_evaluations.csv.gz',usecols=columns,chunksize=100000)
    counts = boundary_transition_counts(chunks,scenarios,
        context.d5['experiments']['boundary_analysis']['sweep_w'],
        context.d5['experiments']['boundary_analysis']['reference_reserve_ratio'])
    counts.to_csv(out/'boundary_verdict_transition_counts.csv',index=False)
    order = ['FLY','CONDITIONAL','NO_FLY']
    fig,axes = plt.subplots(2,2,figsize=(11,8))
    w = context.d5['experiments']['boundary_analysis']['primary_w']
    for i,ref in enumerate(('REF-1','REF-2')):
        for j,battery in enumerate(('TB47D','TB48D')):
            part=counts[(counts.reference_model==ref)&(counts.battery_type==battery)&(counts.w==w)]
            matrix=part.pivot_table(index='baseline_verdict',columns='reassessed_verdict',values='count',aggfunc='sum',fill_value=0).reindex(index=order,columns=order,fill_value=0).to_numpy(float)
            denominator=matrix.sum(axis=1,keepdims=True)
            pct=np.divide(matrix,denominator,out=np.zeros_like(matrix),where=denominator>0)*100
            ax=axes[i,j]
            ax.imshow(pct,vmin=0,vmax=100,cmap='Blues')
            for a in range(3):
                for b in range(3):
                    ax.text(b,a,'NA' if denominator[a,0]==0 else f'{pct[a,b]:.1f}',ha='center',va='center',color='white' if pct[a,b]>55 else 'black')
            ax.set_xticks(range(3),order,rotation=30,ha='right')
            ax.set_yticks(range(3),order)
            ax.set_title(f'{ref} / {battery} / original boundary w={w}')
    fig.suptitle('Input-error grid verdict transitions in boundary cases (%)')
    fig.tight_layout()
    fig.savefig(dest/'boundary_verdict_transitions.png',dpi=180)
    plt.close(fig)
    curves = pd.read_csv(out/'one_factor_sensitivity.csv')
    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    for ax, factor in zip(axes.flat, ('soc_error', 'soh_error', 'wind_error', 'kappa_error', 'energy_error', 'temperature_domain')):
        for battery in ('TB47D', 'TB48D'):
            part = curves[(curves.factor == factor) & (curves.battery_type == battery)].copy()
            part['x'] = pd.to_numeric(part.point_value)
            part = part.sort_values('x')
            for field, style in [('delta_required_mean_Wh', '-'), ('delta_available_mean_Wh', '--'), ('delta_margin_mean_Wh', ':')]:
                ax.plot(part.x, part[field], style, label=f'{battery} {field.split("_")[1]}')
        ax.set_title(factor)
        ax.set_ylabel('Mean change (Wh)')
    axes[0, 0].legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(dest/'energy_and_margin_sensitivity.png', dpi=180)
    plt.close(fig)

    frame = pd.read_csv(out/'mc/terminal_summary.csv')
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, battery in zip(axes, ('TB47D', 'TB48D')):
        part = frame[frame.battery_type == battery]
        for seed, group in part.groupby('seed'):
            ax.plot(group.assumption_config_id, group.joint_feasibility_fraction, 'o-', label=f'seed {seed}')
        ax.set_title(battery)
        ax.set_ylim(0, 1)
        ax.tick_params(axis='x', labelrotation=65, labelsize=7)
        ax.set_ylabel('Model-based joint feasibility fraction')
        ax.legend()
    fig.tight_layout()
    fig.savefig(dest/'monte_carlo_fraction_sensitivity.png', dpi=180)
    plt.close(fig)


def boundary_transition_counts(chunks, scenarios, widths, reserve):
    members={}
    for ref in ('ref1','ref2'):
        ratio=scenarios.set_index('scenario_id')[f'margin_ratio_{ref}']
        for width in widths:
            members[ref,width]=(ratio.abs()<=width)|((ratio-reserve).abs()<=width)
    parts=[]
    keys=['battery_type','baseline_verdict','reassessed_verdict']
    for chunk in chunks:
        valid=chunk[(chunk.status=='OK')&chunk.sweep_kind.isin(['input_error','empirical_error'])]
        for (ref,width),membership in members.items():
            selected=valid[valid.scenario_id.map(membership).fillna(False)]
            if len(selected):
                group=selected.groupby(keys).size().reset_index(name='count')
                group['reference_model']=ref.upper().replace('REF','REF-')
                group['w']=width
                parts.append(group)
    if not parts:
        raise ValueError('No scored boundary transitions')
    return pd.concat(parts).groupby(['reference_model','w',*keys],as_index=False)['count'].sum()


def require_frozen(context):
    meta = context.d5['meta']
    if not (meta['version'] == '1.0.0' and meta['frozen'] is True
            and meta['cross_check_status'] == 'APPROVED'):
        raise ValueError('Requires Phat-approved frozen D5 protocol v1.0.0')


def code_hashes():
    paths = list((ROOT/'src').glob('*.py')) + list((ROOT/'tests').glob('test_*.py'))
    paths += list((ROOT/'configs').glob('*.yaml')) + list((ROOT/'schemas/mission_record').glob('*.json'))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def verify_test_gate(path):
    gate = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if gate.get('exit_code') != 0 or gate.get('passed', 0) < 1:
        raise ValueError('A successful full pytest gate is required')
    if gate.get('code_hashes') != code_hashes():
        raise ValueError('Source/config/schema changed after the full pytest gate')
    return gate


def run_tests(path):
    import re
    path=Path(path)
    log=path.with_suffix('.pytest.log')
    if path.exists() or log.exists():
        raise FileExistsError('Use a new test-gate path; previous evidence is preserved')
    path.parent.mkdir(parents=True,exist_ok=True)
    before=code_hashes()
    started=time.perf_counter()
    command=[sys.executable,'-m','pytest','-o','addopts=','-q']
    print(f'START full pytest gate; log: {log}',flush=True)
    with log.open('x',encoding='utf-8') as stream:
        process=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    output=log.read_text(encoding='utf-8')
    counts=re.findall(r'(\d+) passed',output)
    gate=dict(command=command,exit_code=process.returncode,passed=int(counts[-1]) if counts else 0,
        elapsed_seconds=time.perf_counter()-started,code_hashes=before,
        pytest_log_sha256=sha(log),created_at_utc=datetime.now(timezone.utc).isoformat())
    save(path,gate)
    if process.returncode or not counts or before!=code_hashes():
        raise RuntimeError(f'Full test gate failed or source changed; see {log}')
    print(f'DONE full pytest gate: {gate["passed"]} passed',flush=True)


def export_schema_records(out):
    from src import mission_record as mr, mission_schema as ms
    from src.replay_validation import LATER
    target = out/'mission_records'
    target.mkdir()
    rows = []
    for path in sorted((out/'replay/snapshots').glob('*.json')):
        identity = path.stem
        snapshot = mr.load_snapshot(out/'replay', identity)
        times = [LATER, snapshot.data['assessed_at']]
        times += [event['at'] for event in mr.read_events(out/'replay', identity)]
        record = ms.build_record(out/'replay', identity, at=max(times,key=mr.utc))
        destination = target/path.name
        ms.write_record(destination, record)
        recovered = ms.read_record(destination)
        if recovered['snapshot']['sha256'] != snapshot.sha256:
            raise ValueError('Schema export changed the historical assessment')
        rows.append(dict(assessment_id=identity, schema_version=recovered['schema_version'],
                         snapshot_sha256=snapshot.sha256, validated=True))
    if len(rows) != 24:
        raise ValueError('Expected exactly the 24 D5 assessments; do not add D6 records')
    pd.DataFrame(rows).to_csv(out/'schema_validation_results.csv', index=False)
    shutil.copy2(ms.SCHEMA_PATH, out/'mission_record_schema_1.0.0.json')
    save(out/'schema_consistency.json', dict(schema_version=ms.SCHEMA_VERSION,
         schema_path='schemas/mission_record/1.0.0.json', schema_sha256=sha(ms.SCHEMA_PATH),
         raw_snapshot_version=mr.SCHEMA_VERSION, validated_records=len(rows),
         d6_records_added=0, all_original_snapshot_hashes_preserved=True,
         note='Raw D5 assessments are embedded unchanged in the same versioned exchange envelope used by D6.'))


COPIES = {
    'monte_carlo_fractions.csv':'mc/monte_carlo_fractions.csv',
    'one_factor_sensitivity.csv':'oat/one_factor_curves.csv',
    'verdict_transitions.csv':'oat/verdict_transitions.csv',
    'reference_policy_sensitivity.csv':'oat/reference_metrics.csv',
    'failure_catalogue.csv':'catalogue/failure_catalogue.csv',
    'replay_results.csv':'replay/replay_results.csv',
    'workflow_invariant_results.csv':'replay/workflow_checks.csv',
    'monte_carlo_summary.csv':'mc/terminal_summary.csv',
    'matched_reference_metrics.csv':'matched/matched_reference_metrics.csv',
    'fixed_vs_matched_metrics.csv':'matched/fixed_vs_matched_metrics.csv',
    'reference_label_transitions.csv':'matched/reference_label_transitions.csv',
    'counterfactual_proposals.csv':'matched/counterfactual_proposals.csv',
    'counterfactual_case_summary.csv':'matched/counterfactual_case_summary.csv',
    'counterfactual_validation_summary.csv':'matched/counterfactual_validation_summary.csv',
    'counterfactual_activity.csv':'matched/counterfactual_activity.csv',
    'matched_point_checks.csv':'matched/matched_point_checks.csv',
    'matched_baseline_labels.csv':'matched/matched_baseline_labels.csv',
}


def compare_history(out):
    comparisons, audit = [], []
    for name, source in COPIES.items():
        folder, original_name = source.split('/')
        old, verified = historical_source(folder, original_name)
        audit.append(verified)
        columns = (['scenario_id', 'assessment_id', 'category', 'battery_type', 'baseline_verdict',
                    'changed_verdict_or_reserve_failure', 'baseline_inputs', 'changed_inputs',
                    'reference_details', 'margin_before_after', 'mc_context',
                    'diagnostic_only', 'operational_recommendation', 'case_id'] if folder == 'catalogue' else None)
        rows = compare_csv(out/name, old, columns)
        for row in rows:
            row['table'] = name
        comparisons.extend(rows)
    result = pd.DataFrame(comparisons).groupby(['table','column'], as_index=False).agg(
        rows=('rows','sum'), mismatches=('mismatches','sum'),
        max_absolute_difference=('max_absolute_difference','max'))
    result.to_csv(out/'old_vs_new_comparison.csv', index=False)
    save(out/'historical_source_verification.json', audit)
    return result


def check_final(out, context, comparisons):
    replay = json.loads((out/'replay/validation_manifest.json').read_text())
    oat = json.loads((out/'oat/input_manifest.json').read_text())
    mc = json.loads((out/'mc/input_manifest.json').read_text())
    matched = json.loads((out/'matched/run_status.json').read_text())['statistics']
    schema = json.loads((out/'schema_consistency.json').read_text())
    boundary = pd.read_csv(out/'boundary_breakdown.csv')
    checks = dict(
        frozen_protocol_v1=context.d5['meta']['version'] == '1.0.0' and context.d5['meta']['frozen'],
        complete_mc_population=len(mc['selected_scenario_ids']) == oat['scenario_count'] == 14700,
        declared_mc_design=mc['draws_per_scenario'] == 10000 and mc['seeds'] == [42,43,44]
            and len(mc['configurations']) == 5 and set(mc['battery_types']) == {'TB47D','TB48D'},
        complete_oat=oat['total_evaluations'] == 7467600,
        boundary_scoring_all_w=set(boundary.w) == set(context.d5['experiments']['boundary_analysis']['sweep_w'])
            and {'false_safe_count','false_safe_rate','reference_infeasible','reference_feasible'} <= set(boundary.columns),
        matched_all_oat=matched['matched']['evaluated_rows'] == oat['total_evaluations'],
        full_counterfactual_set=matched['counterfactual']['selected_scenario_ids'] == 2245
            and matched['counterfactual']['selected_battery_cases'] == 4490,
        replay_24=replay['replay_matches'] == replay['assessment_count'] == 24,
        workflow_41=replay['workflow_checks_passed'] == replay['workflow_checks_total'] == 41,
        shared_schema_1_0_0=schema['schema_version'] == '1.0.0' and schema['validated_records'] == 24,
        same_numerical_results=int(comparisons.mismatches.sum()) == 0,
        four_figures=len(list((out/'figures').glob('*.png'))) == 4,
    )
    for directory in ('mc','oat','matched'):
        meta = json.loads((out/directory/'input_manifest.json').read_text())
        checks[f'{directory}_protocol_v1'] = meta['protocol_version'] == '1.0.0'
    save(out/'acceptance_checks.json', checks)
    if not all(checks.values()):
        raise ValueError(f'Final checks failed: {[k for k,v in checks.items() if not v]}')
    return checks


def seal(out):
    """Write a hash ledger once, verify it, then mark every artifact read-only."""
    files = [p for p in sorted(out.rglob('*')) if p.is_file()]
    ledger = {p.relative_to(out).as_posix(): sha(p) for p in files}
    save(out/'output_hashes.json', ledger)
    for path in files:
        if sha(path) != ledger[path.relative_to(out).as_posix()]:
            raise ValueError(f'Output changed before sealing: {path}')
        os.chmod(path, stat.S_IREAD)
    os.chmod(out/'output_hashes.json', stat.S_IREAD)
    for directory in sorted([p for p in out.rglob('*') if p.is_dir()], reverse=True):
        os.chmod(directory, stat.S_IREAD | stat.S_IEXEC)
    os.chmod(out, stat.S_IREAD | stat.S_IEXEC)


def run(out, test_gate):
    if out.exists():
        raise FileExistsError('Use a new run_id; existing evidence is never overwritten')
    context = load_context()
    require_frozen(context)
    gate = verify_test_gate(test_gate)
    started = time.perf_counter()
    inputs = {**context.input_hashes, **code_hashes()}
    out.mkdir(parents=True)
    timings = []
    manifest = dict(run_id=out.name, protocol_version='1.0.0', run_kind='FROZEN_PROTOCOL_FULL_EXECUTION',
        started_at_utc=datetime.now(timezone.utc).isoformat(), input_hashes=context.input_hashes,
        code_hashes=code_hashes(), protocol_review_status='APPROVED_BY_PHAT_2026_10_31',
        run_acceptance_status='PENDING_REVIEW', source_commit=subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    save(out/'input_manifest.json', manifest)
    save(out/'test_gate.json', gate)
    for name in inputs:
        target = out/'source_snapshot'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, target)
        if sha(target) != inputs[name]:
            raise ValueError(f'Source snapshot differs: {name}')
    shutil.copy2(ROOT/'configs/d5_protocol.yaml', out/'protocol_snapshot.yaml')
    def stage(name, command):
        t = time.perf_counter()
        print(f'START {name}', flush=True)
        with (out/f'{name}.log').open('x', encoding='utf-8') as log:
            proc = subprocess.run([sys.executable,'-u','-m',*command],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        timings.append(dict(stage=name,elapsed_seconds=time.perf_counter()-t,exit_code=proc.returncode))
        if proc.returncode:
            raise RuntimeError(f'{name} failed; see {out/(name+".log")}')
        print(f'DONE {name}: {timings[-1]["elapsed_seconds"]:.2f}s', flush=True)
    try:
        t = time.perf_counter()
        base = baseline(out, context)
        timings.append(dict(stage='baseline',elapsed_seconds=time.perf_counter()-t,exit_code=0))
        stage('mc',['src.uncertainty','--limit',str(base['primary_scenarios']),'--out',str(out/'mc')])
        stage('fly_review',['src.analyze_uncertainty','--run',str(out/'mc'),'--out',str(out/'fly_review')])
        stage('oat',['src.sensitivity','--source-run',str(out/'mc'),'--fly-review',str(out/'fly_review'),'--out',str(out/'oat')])
        stage('oat_figures',['src.sensitivity_report','--run',str(out/'oat')])
        stage('matched',['src.complete_robustness','--oat-run',str(out/'oat'),'--out',str(out/'matched')])
        stage('replay',['src.replay_validation','--out',str(out/'replay')])
        t = time.perf_counter()
        export_schema_records(out)
        timings.append(dict(stage='schema_validation',elapsed_seconds=time.perf_counter()-t,exit_code=0))
        stage('catalogue',['src.failure_catalogue','--oat-run',str(out/'oat'),'--replay-run',str(out/'replay'),
                           '--fly-review',str(out/'fly_review'),'--out',str(out/'catalogue')])
        for name, source in COPIES.items():
            shutil.copy2(out/source, out/name)
            if sha(out/source) != sha(out/name):
                raise ValueError(f'CSV copy changed: {name}')
        save(out/'table_sources.json', COPIES)
        refs = pd.read_csv(out/'reference_policy_sensitivity.csv')
        boundary = refs[refs.scope.str.startswith(('boundary_w=','outside_boundary_w='))].copy()
        boundary['w'] = boundary.scope.str.split('=').str[-1].astype(float)
        boundary.to_csv(out/'boundary_breakdown.csv',index=False)
        comparisons = compare_history(out)
        figures(out)
        checks = check_final(out, context, comparisons)
        for name, expected in inputs.items():
            if sha(ROOT/name) != expected:
                raise ValueError(f'Input/source changed during the run: {name}')
        elapsed = time.perf_counter()-started
        save(out/'runtime.json',dict(started_at_utc=manifest['started_at_utc'],
             completed_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=elapsed,stages=timings,
             note='Includes final comparisons/figures; excludes full pytest gate and final hash sealing.'))
        save(out/'run_status.json',dict(status='COMPLETED_FROZEN_PROTOCOL_V1',protocol_version='1.0.0',
             all_required_technical_checks_passed=True,run_acceptance_status='PENDING_REVIEW',
             protocol_review_status='APPROVED_BY_PHAT_2026_10_31',comparison_mismatches=int(comparisons.mismatches.sum()),
             checks=checks,integrity='SHA256 ledger verified before setting all output files and directories read-only'))
        render_report(out, elapsed, comparisons)
    except Exception as exc:
        if not (out/'run_status.json').exists():
            save(out/'run_status.json',dict(status='FAILED',error=f'{type(exc).__name__}: {exc}'))
        raise
    seal(out)
    print(f'COMPLETE v1.0.0: {out}; elapsed {elapsed:.3f}s; all files read-only',flush=True)


def render_report(out, elapsed, comparisons):
    mc = pd.read_csv(out/'monte_carlo_summary.csv')
    matched = json.loads((out/'matched/run_status.json').read_text())['statistics']
    text = f'''# D5 — Lần chạy đầy đủ theo protocol v1.0.0

Run ID: `{out.name}`. Protocol được Phát duyệt và đóng băng ngày 31/10/2026.
Lần chạy này có đầy đủ bằng chứng kỹ thuật; nghiệm thu kết quả mới vẫn chờ kiểm tra.

## Kết quả và phạm vi

Tất cả tỷ lệ FLY của D4/D5 trong phân tích này dùng cấu hình **CMU_instrumented
vượt MTOW**. HR-3 ghi nhận KNOWN_EXCEEDED ở tầng chẩn đoán; workflow chặn
duyệt/thực thi. Lớp chặn workflow không bị áp vào mẫu số thước đo.
Dải tải 0–500 g là độ phủ dữ liệu, không thay thế giới hạn MTOW.
Không phân tích hiệu năng M100_stock: mô hình D2 hiệu chỉnh trên khung 3.680 g;
áp sang khung 2.355 g là ngoại suy khối lượng chưa có số đo. Fixture M100_stock
chỉ kiểm logic phần mềm. Nhãn tham chiếu là simulation-derived.

- Baseline: đúng hệ số/scaler/intercept D2 của D4; kiểm nhãn, margin và API D3 scalar.
- Monte Carlo: 14.700 kịch bản × 10.000 draw × 3 seed × 2 pin × 5 cấu hình;
  {int(mc.draws_total.sum()):,} lượt lấy mẫu; {int(mc.invalid_draws.sum()):,} draw không hợp lệ.
- OAT: 7.467.600 lượt đánh giá; quét reserve và điểm số vùng biên tại từng w.
- Matched-reference: {matched['matched']['evaluated_rows']:,} lượt; hai REF,
  membership gốc/tính lại và nhãn cố định/tính lại được lưu riêng.
- Counterfactual: {matched['counterfactual']['selected_scenario_ids']:,} ID,
  {matched['counterfactual']['selected_battery_cases']:,} ca pin,
  {matched['counterfactual']['evaluated_trials']:,} phép thử áp dụng được,
  {matched['counterfactual']['offered_proposals']:,} đề xuất; giữ cả thất bại/không áp dụng.
- Replay **24/24**, workflow **41/41**. Không cộng 12 bản D6 thành 36.
- 24 snapshot D5 được nhúng nguyên checksum vào bản ghi theo schema D6
  `schemas/mission_record/1.0.0.json`; kiểm cấu trúc, metadata và chuỗi sự kiện.

## Đầu ra và đối chiếu

Mười file bắt buộc ở gốc run: input_manifest.json, baseline_consistency.json,
monte_carlo_fractions.csv, one_factor_sensitivity.csv, boundary_breakdown.csv,
verdict_transitions.csv, reference_policy_sensitivity.csv, failure_catalogue.csv,
replay_results.csv, workflow_invariant_results.csv; bốn hình trong figures/.
Các thư mục mc/oat/matched/replay/catalogue/fly_review giữ đầy đủ bằng chứng,
bao gồm snapshot, trial bị loại và manifest từng bước. source_snapshot/ lưu
mã, cấu hình, schema và đầu vào đúng phiên bản của lần chạy.

`old_vs_new_comparison.csv`: {len(comparisons)} cột đối chiếu, tổng
{int(comparisons.mismatches.sum())} ô sai khác. So sánh giá trị đọc từ CSV
chính xác, tách định danh phiên bản/hash và thời gian khỏi số liệu thí nghiệm.
Catalogue đối chiếu 14 cột, gồm các JSON chứa đầu vào, năng lượng, margin và MC.
Nguồn CSV MC cũ dùng bản khôi phục khớp SHA-256 gốc, không dùng file đã làm tròn.
Chi tiết: historical_source_verification.json và table_sources.json.

Các manifest của module con giữ nhãn DEVELOPMENT/PENDING từ giao diện cũ:
chúng là bước thành phần, không tự đại diện toàn bộ D5. Protocol thực dùng
v1.0.0 được kiểm bằng hash và manifest, không sửa metadata của lần chạy cũ.
Trạng thái kỹ thuật của toàn bộ run nằm ở run_status.json và acceptance_checks.json;
không tự ký nghiệm thu thay Phát.

## Giả định và thời gian D9

SoC/SoH/kappa ±0,02 ở nhánh chính là giả định thí nghiệm, có thể lạc quan.
Phải đọc cùng nhánh stress ±0,05 (gió ±2 m/s), adverse residual/dependence;
không diễn giải fraction thành xác suất an toàn thực tế đã hiệu chuẩn.

Pipeline: **{elapsed:.3f} giây**; chi tiết từng bước trong runtime.json.
Thời gian kiểm thử nằm riêng ở test_gate.json. Thời gian pipeline chưa gồm
bước niêm phong hash cuối. CSV được tạo một lần, kiểm hash và đặt toàn bộ
file/thư mục của run ở thuộc tính chỉ đọc; đây không phải lưu trữ WORM.
Không mở rồi lưu lại CSV bằng Excel. output_hashes.json kiểm chứng nội dung.
'''
    (out/'robustness_report.md').write_text(text,encoding='utf-8')
    (out/'README.md').write_text('Mở [báo cáo đầy đủ](robustness_report.md).\n',encoding='utf-8')


def create_share(out):
    """Keep the complete local evidence and add a size-bounded Git review bundle."""
    destination = ROOT/'reports/d5/published'/out.name
    if destination.exists():
        raise FileExistsError(f'Shared bundle exists: {destination}')
    destination.mkdir(parents=True)
    names = [name for name in COPIES if name != 'monte_carlo_fractions.csv']
    names += ['boundary_breakdown.csv','old_vs_new_comparison.csv','schema_validation_results.csv',
              'boundary_verdict_transition_counts.csv',
              'baseline_consistency.json','schema_consistency.json','acceptance_checks.json',
              'input_manifest.json','run_status.json','runtime.json','test_gate.json',
              'historical_source_verification.json','table_sources.json','robustness_report.md',
              'mission_record_schema_1.0.0.json']
    for name in names:
        shutil.copy2(out/name,destination/name)
    shutil.copytree(out/'figures',destination/'figures')
    shutil.copy2(out/'output_hashes.json',destination/'full_run_hashes.json')
    (destination/'README.md').write_text(
        f'# D5 v1.0.0 — {out.name}\n\n'
        'Xem [báo cáo](robustness_report.md), [kiểm tra](acceptance_checks.json), '
        '[đối chiếu](old_vs_new_comparison.csv) và [thời gian D9](runtime.json).\n\n'
        'Đây là bản nhỏ để đưa lên Git: có bảng MC tổng hợp, OAT, vùng biên, '
        'matched-reference, counterfactual, replay/workflow, bốn hình và bằng chứng hash. '
        f'Bộ đầy đủ ở `reports/d5/{out.name}/` trên máy chạy, gồm MC CSV/JSON, '
        'các bảng nén lớn và kho snapshot/mã nguồn lịch sử. '
        'Các file lớn vẫn giữ nguyên, không bị xóa hoặc ép thành bảng tổng hợp. '
        '`full_run_hashes.json` liệt kê checksum để kiểm chứng bộ đầy đủ. '
        'Không dùng git add -f cho CSV Monte Carlo vượt giới hạn kích thước GitHub.\n',
        encoding='utf-8')
    save(destination/'shared_files_hashes.json', {p.relative_to(destination).as_posix():sha(p)
         for p in destination.rglob('*') if p.is_file()})
    print(f'Git review bundle: {destination}',flush=True)


if __name__ == '__main__':
    import re
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--test-gate',type=Path,required=True)
    parser.add_argument('--run-tests',action='store_true',help='Run the full pytest gate first and save its evidence')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',args.run_id):
        parser.error('run-id must be a plain directory name')
    output = ROOT/'reports/d5'/args.run_id
    if args.run_tests:
        run_tests(args.test_gate)
    run(output,args.test_gate)
    create_share(output)
