"""D5 sampling contracts, signed errors, boundary handling and VETO propagation."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest
import yaml

from src.uncertainty import (
    RESIDUAL_ONLY, bounded_uniform, configuration_ids, load_context,
    format_terminal_summary, print_saved_summary, run_development,
    main, simulate_scenario, summarize_results, uniform_stream,
)


@pytest.fixture(scope="module")
def context():
    return load_context()


@pytest.fixture
def scenario():
    return dict(scenario_id=1, stratum="main", payload_g=250., speed_commanded_ms=8.,
                altitude_m=25., distance_2d_m=500., wind_forecast_ms=4.,
                ambient_temp_c=15., soc=.8, soh=.9)


@pytest.mark.parametrize("config", [RESIDUAL_ONLY, "PRIMARY_INDEPENDENT", "WIDER_RANGES",
                                   "ADVERSE_RESIDUAL_POOL", "ADVERSE_DEPENDENCE"])
def test_all_configurations_reproducible_and_equations_match(context, scenario, config):
    first = simulate_scenario(context, scenario, config_id=config, draws=1000, return_draws=True)
    second = simulate_scenario(context, scenario, config_id=config, draws=1000, return_draws=True)
    assert first.summary == second.summary
    for name, values in first.draws.items():
        np.testing.assert_array_equal(values, second.draws[name])
    d, s = first.draws, first.summary
    np.testing.assert_allclose(d["e_available_Wh"], 99.9*d["soc"]*d["soh"]*d["kappa"])
    np.testing.assert_allclose(d["e_demand_Wh"], s["baseline_prediction_Wh"] +
                               context.model.wind_coefficient*(d["wind"]-scenario["wind_forecast_ms"]) - d["residual_Wh"])
    assert s["draws_total"] == s["valid_draws"] + s["invalid_draws"] == 1000
    assert s["energy_success_count"] == int((d["valid"] & d["reserve_ok"]).sum())
    assert s["joint_success_count"] == int((d["valid"] & d["reserve_ok"] & d["veto_ok"]).sum())
    assert s["joint_feasibility_fraction"] <= s["energy_feasibility_fraction"]
    assert next(c for c in s["baseline_rules"] if c["id"] == "HR-3")["status"] == "KNOWN_EXCEEDED"


def test_seed_and_stream_identity():
    expected = np.random.Generator(np.random.PCG64(np.random.SeedSequence([42, 7, 2]))).random(50)
    np.testing.assert_array_equal(uniform_stream(42, 7, 2, 50), expected)
    assert not np.array_equal(expected, uniform_stream(43, 7, 2, 50))


def test_battery_and_reserve_reuse_identical_samples(context, scenario):
    kw = dict(config_id="PRIMARY_INDEPENDENT", draws=1000, return_draws=True)
    a = simulate_scenario(context, scenario, **kw)
    # Evaluate a different scenario in between: loop order cannot alter streams.
    simulate_scenario(context, {**scenario, "scenario_id": 2}, **kw)
    b = simulate_scenario(context, scenario, battery_type="TB48D", reserve_ratio=.3, **kw)
    for key in ("soc", "soh", "wind", "kappa", "residual_Wh", "e_demand_Wh"):
        np.testing.assert_array_equal(a.draws[key], b.draws[key])
    np.testing.assert_allclose(b.draws["e_available_Wh"] / a.draws["e_available_Wh"], 129.96/99.9)


def test_range_comparisons_share_uniform_quantiles(context, scenario):
    kw = dict(draws=1000, return_draws=True)
    a = simulate_scenario(context, scenario, config_id="PRIMARY_INDEPENDENT", **kw)
    b = simulate_scenario(context, scenario, config_id="WIDER_RANGES", **kw)
    np.testing.assert_array_equal(a.draws["residual_Wh"], b.draws["residual_Wh"])
    for key in ("soc", "soh", "wind", "kappa"):
        def quantiles(result):
            bounds = result.summary["effective_intervals"][key]
            return (result.draws[key] - bounds["effective_lower"]) / (bounds["effective_upper"]-bounds["effective_lower"])
        np.testing.assert_allclose(quantiles(a), quantiles(b), atol=1e-13)


def test_physical_boundary_uses_truncated_interval_without_clipping(context, scenario):
    values, bounds = bounded_uniform(1., .02, np.array([0., .25, .5, .75, 1.]))
    np.testing.assert_allclose(values, [.98, .985, .99, .995, 1.])
    assert bounds["mean_delta"] == pytest.approx(-.01)
    result = simulate_scenario(context, {**scenario, "ambient_temp_c": 25., "soc": 1.},
                               config_id="PRIMARY_INDEPENDENT", draws=1000, return_draws=True)
    assert result.summary["effective_intervals"]["kappa"]["mean_delta"] == pytest.approx(-.01)
    assert np.all(result.draws["kappa"] < 1.)


@pytest.mark.parametrize("field,value", [("soc", None), ("soc", np.nan), ("soc", 1.01),
    ("soh", -.01), ("wind_forecast_ms", np.inf), ("wind_forecast_ms", -1.),
    ("speed_commanded_ms", 0.), ("distance_2d_m", -1.), ("altitude_m", -1.),
    ("payload_g", np.nan), ("ambient_temp_c", 41.)])
def test_invalid_baselines_not_repaired_or_sampled(context, scenario, field, value):
    result = simulate_scenario(context, {**scenario, field: value}, draws=20)
    assert result.summary["status"] == "INVALID_BASELINE"
    assert field in result.summary["invalid_fields"]
    assert result.summary["draws_total"] == 0
    assert result.summary["energy_feasibility_fraction"] is None
    assert result.summary["joint_feasibility_fraction"] is None


def test_audit_strata_not_mixed_with_monte_carlo(context, scenario):
    result = simulate_scenario(context, {**scenario, "stratum": "hard_rule_probe"})
    assert result.summary["status"] == "AUDIT_ONLY_STRATUM"
    assert result.summary["draws_total"] == 0


@pytest.mark.parametrize("error", [-2., 0., 2.])
def test_signed_residual_and_no_added_allowance(context, scenario, error):
    ctx = replace(context, residuals=np.array([error]))
    result = simulate_scenario(ctx, scenario, draws=100, return_draws=True)
    np.testing.assert_allclose(result.draws["e_demand_Wh"], result.summary["baseline_prediction_Wh"]-error)


def test_invalid_demand_counted_without_resampling(context, scenario):
    ctx = replace(context, residuals=np.array([-1., 1000.]))
    result = simulate_scenario(ctx, scenario, draws=1000, return_draws=True)
    invalid = result.draws["residual_Wh"] == 1000.
    assert 0 < invalid.sum() < 1000
    assert result.summary["invalid_draws"] == int(invalid.sum())
    assert result.summary["energy_feasibility_fraction"] == pytest.approx(
        result.summary["energy_success_count"] / (1000-invalid.sum()))
    empty = simulate_scenario(replace(ctx, residuals=np.array([1000.])), scenario, draws=100)
    assert empty.summary["status"] == "NO_VALID_DRAWS"
    assert empty.summary["invalid_draws"] == 100
    assert empty.summary["energy_feasibility_fraction"] is None


def test_negative_pool_is_explicit_stress(context, scenario):
    result = simulate_scenario(context, scenario, config_id="ADVERSE_RESIDUAL_POOL", draws=1000, return_draws=True)
    assert np.all(result.draws["residual_Wh"] < 0)
    assert result.summary["residual_pool_size"] == int((context.residuals < 0).sum())


def test_adverse_coupling_matches_declared_inverse_cdf(context, scenario):
    result = simulate_scenario(context, scenario, config_id="ADVERSE_DEPENDENCE", draws=1000, return_draws=True)
    mc = context.d5["experiments"]["monte_carlo"]
    u = uniform_stream(42, 1, mc["random_number_contract"]["coupled_stream_id"], 1000)
    pool = np.sort(context.residuals)
    expected = pool[np.minimum(len(pool)-1, (len(pool)*(1-u)).astype(int))]
    np.testing.assert_array_equal(result.draws["residual_Wh"], expected)
    order = np.argsort(u)
    assert np.all(np.diff(result.draws["wind"][order]) >= 0)
    for key in ("soc", "soh", "kappa", "residual_Wh"):
        assert np.all(np.diff(result.draws[key][order]) <= 0)


def test_adverse_coupling_rejects_wrong_wind_sign(context, scenario):
    model = deepcopy(context.model)
    coefficient = model.coefficients.copy()
    coefficient[model.features.index("wind_raw_mean_ms")] *= -1
    ctx = replace(context, model=replace(model, coefficients=coefficient))
    with pytest.raises(ValueError, match="positive frozen wind"):
        simulate_scenario(ctx, scenario, config_id="ADVERSE_DEPENDENCE", draws=10)


def test_wind_veto_draws_remain_in_denominator(context, scenario):
    result = simulate_scenario(context, {**scenario, "wind_forecast_ms": 9.8},
                               config_id="WIDER_RANGES", draws=1000, return_draws=True)
    expected = result.draws["wind"] > 10.
    assert 0 < expected.sum() < 1000
    assert result.summary["valid_draws"] == 1000
    assert result.summary["veto_failure_counts"]["HR-1"] == int(expected.sum())


def test_landing_floor_uses_perturbed_kappa(context, scenario):
    baseline = simulate_scenario(context, scenario, draws=10)
    floor = baseline.summary["landing_floor_Wh"]
    # Center exactly at PH-1; perturbing kappa must make draws cross the floor.
    soc = floor / (99.9 * scenario["soh"] * .9954)
    result = simulate_scenario(context, {**scenario, "soc": soc},
                               config_id="PRIMARY_INDEPENDENT", draws=1000, return_draws=True)
    failed = result.draws["e_available_Wh"] < floor
    assert 0 < failed.sum() < 1000
    assert result.summary["veto_failure_counts"]["PH-1"] == int(failed.sum())


def test_fixed_veto_preserved(context, scenario):
    result = simulate_scenario(context, {**scenario, "speed_commanded_ms": 18.}, draws=100)
    assert result.summary["veto_failure_counts"]["HR-4"] == 100
    assert result.summary["joint_success_count"] == 0


def test_changed_upstream_rejected(context, tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/d5_protocol.yaml").write_text(yaml.safe_dump(context.d5), encoding="utf-8")
    (tmp_path / "configs/d2_protocol.yaml").write_text("changed: true", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_context(tmp_path)


@pytest.mark.parametrize("kw", [{"draws": 0}, {"draws": 2.5}, {"seed": -1}, {"seed": True},
                                {"config_id": "unknown"}, {"battery_type": "unknown"}, {"reserve_ratio": -.1}])
def test_invalid_run_parameters_rejected(context, scenario, kw):
    with pytest.raises(ValueError):
        simulate_scenario(context, scenario, **kw)


def test_partial_runner_saves_manifest_and_refuses_overwrite(tmp_path, capsys):
    out = tmp_path / "partial"
    rows = run_development(out, scenario_ids=[1], draws=32)
    assert len(rows) == 3 * 5 * 2
    manifest = json.loads((out / "input_manifest.json").read_text(encoding="utf-8"))
    status = json.loads((out / "run_status.json").read_text(encoding="utf-8"))
    assert manifest["run_kind"] == "DEVELOPMENT_PARTIAL"
    assert status["status"] == "COMPLETED_DEVELOPMENT_PARTIAL"
    assert manifest["final_d5_complete"] is False
    assert manifest["draws_override"] is True
    assert manifest["draws_per_scenario"] == 32
    assert len(status["output_hashes"]) == 4
    assert all(row["input_manifest_hash"] == status["input_manifest_hash"] for row in rows)
    assert all(row["fixed_label_ref1"] == "feasible" for row in rows)
    text = capsys.readouterr().out
    assert "TOM TAT MONTE CARLO D5" in text
    assert "(1/1; 100.0%)" in text
    assert (out / "terminal_summary.csv").exists()
    csv_text = (out / "terminal_summary.csv").read_text(encoding="utf-8")
    assert "run_id,protocol_version,input_manifest_hash" in csv_text.splitlines()[0]
    assert status["input_manifest_hash"] in csv_text
    assert (out / "terminal_summary.txt").exists()
    original_files = {p.name: p.read_bytes() for p in out.iterdir()}
    summary = print_saved_summary(out)
    assert summary["simulated_scenarios"] == 1
    assert {p.name: p.read_bytes() for p in out.iterdir()} == original_files
    with pytest.raises(FileExistsError):
        run_development(out, scenario_ids=[1], draws=32)


def _summary_manifest():
    return dict(run_id="summary-test", protocol_version="0.3.0", run_kind="DEVELOPMENT_PARTIAL",
                selected_scenario_ids=[1, 2, 3, 4], configurations=["PRIMARY_INDEPENDENT", "WIDER_RANGES"])


def _summary_row(scenario_id=1, **overrides):
    return dict(dict(scenario_id=scenario_id, status="OK", aircraft_profile="CMU_instrumented",
                     reserve_ratio=.2, assumption_config_id="PRIMARY_INDEPENDENT", battery_type="TB47D",
                     seed=42, draws_total=100, valid_draws=100, invalid_draws=0,
                     energy_success_count=100, joint_success_count=90), **overrides)


def test_summary_pools_counts_and_keeps_seed_battery_config_separate():
    rows = [_summary_row(),
            _summary_row(2, draws_total=10, valid_draws=10, energy_success_count=0, joint_success_count=0),
            _summary_row(seed=43, energy_success_count=30, joint_success_count=20),
            _summary_row(battery_type="TB48D", energy_success_count=50, joint_success_count=40),
            _summary_row(assumption_config_id="WIDER_RANGES", energy_success_count=20, joint_success_count=10)]
    summary = summarize_results(rows, _summary_manifest())
    assert summary["simulated_scenarios"] == 2
    assert len(summary["groups"]) == 4
    group = summary["groups"][0]
    assert group["scenario_count"] == 2
    assert group["valid_draws"] == 110
    assert group["energy_feasibility_fraction"] == pytest.approx(100/110)
    assert group["joint_feasibility_fraction"] == pytest.approx(90/110)
    assert summary["draws_total"] == 410


def test_summary_deduplicates_skips_and_excludes_them_from_fraction():
    audit = _summary_row(3, status="AUDIT_ONLY_STRATUM", draws_total=0, valid_draws=0,
                         energy_success_count=0, joint_success_count=0)
    invalid = _summary_row(4, status="INVALID_BASELINE", draws_total=0, valid_draws=0,
                           energy_success_count=0, joint_success_count=0, invalid_fields=["soc"])
    summary = summarize_results([_summary_row(), audit, {**audit, "seed": 43}, invalid,
                                 {**invalid, "battery_type": "TB48D"}], _summary_manifest())
    assert summary["selected_scenarios"] == 4
    assert summary["simulated_scenarios"] == 1
    assert len(summary["skipped_scenarios"]) == 2
    assert summary["skipped_scenarios"][1]["reason"] == "soc"
    assert summary["groups"][0]["energy_feasibility_fraction"] == 1.
    text = format_terminal_summary(summary)
    assert "AUDIT_ONLY_STRATUM: 1" in text
    assert "INVALID_BASELINE: 1" in text
    assert "ID 4: INVALID_BASELINE (soc)" in text


def test_summary_zero_denominator_is_na():
    row = _summary_row(status="NO_VALID_DRAWS", valid_draws=0, invalid_draws=100,
                       energy_success_count=0, joint_success_count=0)
    summary = summarize_results([row], _summary_manifest())
    assert summary["groups"][0]["energy_feasibility_fraction"] is None
    assert summary["groups"][0]["joint_feasibility_fraction"] is None
    assert summary["simulated_scenarios"] == 1
    assert summary["invalid_draws"] == 100
    assert "NA" in format_terminal_summary(summary)


def test_summary_with_only_skipped_scenarios_has_no_fraction():
    row = _summary_row(3, status="AUDIT_ONLY_STRATUM", draws_total=0, valid_draws=0,
                       energy_success_count=0, joint_success_count=0)
    summary = summarize_results([row], _summary_manifest())
    assert summary["groups"] == []
    assert "Khong co kich ban duoc lay mau" in format_terminal_summary(summary)


def _write_legacy_summary_run(path):
    manifest = path / "input_manifest.json"
    manifest.write_text(json.dumps(_summary_manifest()), encoding="utf-8")
    output = path / "monte_carlo_fractions.json"
    output.write_text(json.dumps([_summary_row()]), encoding="utf-8")
    status = dict(status="COMPLETED_DEVELOPMENT_PARTIAL",
                  input_manifest_hash=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  output_hashes={output.name: hashlib.sha256(output.read_bytes()).hexdigest()})
    (path / "run_status.json").write_text(json.dumps(status), encoding="utf-8")
    return status


def test_summary_only_reads_legacy_run_without_sampling(tmp_path, monkeypatch):
    _write_legacy_summary_run(tmp_path)
    def no_sampling(*args, **kwargs):
        raise AssertionError("Summary must not rerun Monte Carlo or load current model")
    monkeypatch.setattr("src.uncertainty.load_context", no_sampling)
    monkeypatch.setattr("src.uncertainty.simulate_scenario", no_sampling)
    assert print_saved_summary(tmp_path)["draws_total"] == 100


@pytest.mark.parametrize("filename", ["input_manifest.json", "monte_carlo_fractions.json"])
def test_summary_only_rejects_tampered_saved_output(tmp_path, filename):
    _write_legacy_summary_run(tmp_path)
    (tmp_path / filename).write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        print_saved_summary(tmp_path)


def test_summary_only_rejects_incomplete_run(tmp_path):
    (tmp_path / "run_status.json").write_text(json.dumps(dict(status="RUNNING_DEVELOPMENT_PARTIAL")), encoding="utf-8")
    with pytest.raises(ValueError, match="not completed"):
        print_saved_summary(tmp_path)


def test_summary_cli_missing_directory_reports_clear_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["uncertainty", "--summary-only", str(tmp_path / "absent")])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "Cannot read saved summary" in stderr
    assert "Traceback" not in stderr


@pytest.mark.parametrize("arguments", [[], ["--summary-only", "old", "--out", "new"]])
def test_summary_cli_rejects_missing_or_conflicting_run_options(arguments, monkeypatch):
    monkeypatch.setattr("sys.argv", ["uncertainty", *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
