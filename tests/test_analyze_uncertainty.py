"""Saved-run filtering and seed ranges without Monte Carlo resimulation."""
import json

import pandas as pd
import pytest

from src.analyze_uncertainty import analyze, sha, summarize_fly


def row(sid=1, seed=42, config="PRIMARY_INDEPENDENT", successes=10, **overrides):
    values = dict(scenario_id=sid, aircraft_profile="CMU_instrumented", reserve_ratio=.2,
                  battery_type="TB47D", assumption_config_id=config, seed=seed,
                  baseline_verdict="FLY", status="OK", draws_total=10, valid_draws=10,
                  invalid_draws=0, energy_success_count=successes, joint_success_count=max(0, successes-1),
                  baseline_prediction_Wh=20., baseline_available_Wh=30., baseline_margin_Wh=10.,
                  fixed_label_ref1="feasible", fixed_label_ref2="infeasible")
    return {**values, **overrides}


def test_seed_range_includes_seed_with_zero_shortfalls():
    by_seed, cases = summarize_fly(pd.DataFrame([row(), row(seed=43, successes=8)]))
    assert len(by_seed) == 2
    assert cases.iloc[0].failure_fraction_min == 0
    assert cases.iloc[0].failure_fraction_max == .2
    assert cases.iloc[0].seed_count == 2
    assert cases.iloc[0].seeds_with_shortfall == 1
    assert cases.iloc[0].baseline_reserve_slack_Wh == 6.


def test_no_fly_and_veto_only_failures_not_selected_as_reserve_failures():
    _, cases = summarize_fly(pd.DataFrame([row(joint_success_count=0),
                                           row(2, successes=0, baseline_verdict="NO_FLY")]))
    assert len(cases) == 1
    assert not cases.iloc[0].has_reserve_shortfall
    assert cases.iloc[0].extra_veto_failures_max == 10


def test_context_and_battery_not_pooled():
    _, cases = summarize_fly(pd.DataFrame([row(successes=9), row(battery_type="TB48D", successes=5),
                                           row(config="WIDER_RANGES", successes=2)]))
    assert len(cases) == 3
    assert cases.failure_fraction_max.tolist() == [.1, .5, .8]


def test_baseline_changes_across_seeds_rejected():
    with pytest.raises(ValueError, match="Baseline context changes"):
        summarize_fly(pd.DataFrame([row(), row(seed=43, baseline_prediction_Wh=21.)]))


def setup_run(tmp_path, *, duplicate=False, incomplete=False, bad_counts=False):
    root = tmp_path / "root"
    (root / "reports").mkdir(parents=True)
    scenarios = pd.DataFrame([dict(scenario_id=sid, payload_g=250., speed_commanded_ms=8., altitude_m=25.,
                                   distance_2d_m=500., wind_forecast_ms=4., soc=.8, soh=.9,
                                   ambient_temp_c=15., stratum="main") for sid in (1, 2)])
    scenario_file = root / "reports/d4_scenarios_labelled.csv"
    scenarios.to_csv(scenario_file, index=False)
    run = tmp_path / "run"
    run.mkdir()
    manifest = dict(run_id="source-test", protocol_version="0.3.1", selected_scenario_ids=[1, 2],
                    seeds=[42, 43], battery_types=["TB47D"],
                    configurations=["PRIMARY_INDEPENDENT", "WIDER_RANGES"],
                    input_hashes={"reports/d4_scenarios_labelled.csv": sha(scenario_file)})
    (run / "input_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_hash = sha(run / "input_manifest.json")
    rows = [row(sid, seed, config, successes=10 if seed == 42 else 8,
                baseline_verdict="FLY" if sid == 1 else "NO_FLY",
                run_id=manifest["run_id"], input_manifest_hash=manifest_hash)
            for sid in (1, 2) for seed in (42, 43) for config in manifest["configurations"]]
    if duplicate:
        rows[-1] = rows[-2].copy()
    if incomplete:
        rows.pop()
    if bad_counts:
        rows[0]["energy_success_count"] = 11
    output = run / "monte_carlo_fractions.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    status = dict(status="COMPLETED_DEVELOPMENT_PARTIAL", input_manifest_hash=manifest_hash,
                  output_hashes={output.name: sha(output)})
    (run / "run_status.json").write_text(json.dumps(status), encoding="utf-8")
    return root, run


def test_analysis_output_is_reproducible_and_source_untouched(tmp_path):
    root, run = setup_run(tmp_path)
    before = {p.name: sha(p) for p in run.iterdir()}
    out = tmp_path / "analysis"
    payload = analyze(run, out, root=root, chunksize=3)
    assert payload["metadata"]["affected_primary_cases"] == 1
    assert payload["priority"][0]["failure_fraction_min"] == 0
    assert payload["priority"][0]["failure_fraction_max"] == .2
    assert len(payload["summary"]) == 2
    assert {p.name: sha(p) for p in run.iterdir()} == before
    assert (out / "fly_reserve_failures.csv").exists()
    assert pd.read_csv(out / "fly_priority_cases.csv").scenario_id.tolist() == [1]
    with pytest.raises(FileExistsError):
        analyze(run, out, root=root)


@pytest.mark.parametrize("option,message", [("duplicate", "Duplicate result"),
                                            ("incomplete", "Incomplete source grid"),
                                            ("bad_counts", "Inconsistent simulation counts")])
def test_invalid_grid_or_counts_rejected(tmp_path, option, message):
    root, run = setup_run(tmp_path, **{option: True})
    with pytest.raises(ValueError, match=message):
        analyze(run, tmp_path / "analysis", root=root, chunksize=3)
    assert not (tmp_path / "analysis").exists()


def test_changed_source_csv_rejected(tmp_path):
    root, run = setup_run(tmp_path)
    with (run / "monte_carlo_fractions.csv").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="CSV hash mismatch"):
        analyze(run, tmp_path / "analysis", root=root)
