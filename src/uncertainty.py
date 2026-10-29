"""D5: Monte Carlo energy feasibility under explicitly stated assumptions.

Uses saved D2 coefficients and signed flight-level OOF residuals; never refits.
Each scenario is processed separately, bounding memory independently of the
number of scenarios. Fractions describe model-based feasibility, not calibrated
flight success probabilities. This module does not authorize a mission.

Development run: python -m src.uncertainty --limit 3 --out reports/d5/dev_run
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import platform
import subprocess

import numpy as np
import pandas as pd
import yaml

from src.available_energy import available_energy, kappa
from src.decision_rules import assess
from src.physics_m100 import landing_energy_Wh
from src.reference_labeller import scenario_features
from src.safety_invariants import MISSING, VETO, check_hard_rules, takeoff_mass_g

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.1"
RESIDUAL_ONLY = "RESIDUAL_ONLY"
INPUT_FIELDS = ("payload_g", "speed_commanded_ms", "altitude_m", "distance_2d_m",
                "wind_forecast_ms", "ambient_temp_c", "soc", "soh")


class UniqueLoader(yaml.SafeLoader):
    """Fail if a YAML key is repeated rather than silently changing a setting."""


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _integer(value, name, minimum=0):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


@dataclass(frozen=True)
class FrozenEstimator:
    features: tuple[str, ...]
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray
    intercept: float

    def predict(self, scenario, d4):
        x = scenario_features(pd.DataFrame([scenario]), d4, list(self.features)).to_numpy(float)[0]
        if not np.isfinite(x).all():
            raise ValueError("Missing or invalid model features")
        return float(((x - self.means) / self.scales) @ self.coefficients + self.intercept)

    @property
    def wind_coefficient(self):
        i = self.features.index("wind_raw_mean_ms")
        return float(self.coefficients[i] / self.scales[i])


@dataclass(frozen=True)
class Context:
    root: Path
    d3: dict
    d4: dict
    d5: dict
    model: FrozenEstimator
    residuals: np.ndarray
    input_hashes: dict


def load_context(root=ROOT):
    """Verify frozen upstream hashes before any sampling; reject changed inputs."""
    root = Path(root)
    def load(relative):
        return yaml.load((root / relative).read_text(encoding="utf-8"), Loader=UniqueLoader)
    d5 = load("configs/d5_protocol.yaml")
    hashes = {}
    for relative, expected in d5["input_snapshot_at_draft"]["sha256"].items():
        hashes[relative] = _sha(root / relative)
        if hashes[relative] != expected:
            raise ValueError(f"Upstream hash mismatch: {relative}; review the changed input before running D5")
    d2, d3, d4 = [load(f"configs/{name}_protocol.yaml") for name in ("d2", "d3", "d4")]
    for name, protocol in (("d2", d2), ("d3", d3), ("d4", d4)):
        if str(protocol["meta"]["version"]) != d5["sources"]["upstream_protocols"][name]["version"]:
            raise ValueError(f"Upstream version mismatch: {name}")
    energy_cases = d5["factors"]["nominal_battery_energy"]["cases"]
    expected_energy = dict(TB47D=d3["available_energy"]["e_nominal"]["primary_Wh"],
                           TB48D=d3["available_energy"]["e_nominal"]["sensitivity_Wh"])
    if {c["battery_type"]: c["nominal_Wh"] for c in energy_cases} != expected_energy:
        raise ValueError("D5 nominal battery energies disagree with D3")
    table = pd.read_csv(root / d5["inherited_baseline"]["frozen_estimator_artifact"])
    features = tuple(d2["features"]["preflight"])
    if tuple(table.feature) != features or table.intercept.nunique() != 1:
        raise ValueError("Frozen estimator feature order or intercept is inconsistent")
    arrays = [table[c].to_numpy(float) for c in ("scaler_mean", "scaler_scale", "coef_standardised")]
    if not all(np.isfinite(a).all() for a in arrays) or not (arrays[1] > 0).all():
        raise ValueError("Invalid frozen estimator coefficients/scaler")
    if not np.isfinite(table.intercept.iloc[0]):
        raise ValueError("Invalid frozen estimator intercept")
    for array in arrays:
        array.setflags(write=False)
    model = FrozenEstimator(features, *arrays, float(table.intercept.iloc[0]))
    pool_cfg = d5["factors"]["energy_prediction_error"]
    pool = pd.read_csv(root / pool_cfg["file"]).sort_values(pool_cfg["id_column"])
    residuals = pool[pool_cfg["value_column"]].to_numpy(float)
    if (len(pool) != pool_cfg["expected_unique_flights"] or not pool[pool_cfg["id_column"]].is_unique
            or not np.isfinite(residuals).all()):
        raise ValueError("OOF residual pool must contain the declared number of unique finite flights")
    residuals.setflags(write=False)
    hashes["configs/d5_protocol.yaml"] = _sha(root / "configs/d5_protocol.yaml")
    return Context(root, d3, d4, d5, model, residuals, hashes)


def uniform_stream(seed, scenario_id, stream_id, size):
    """Scenario-local stream: independent of loop order, battery or reserve."""
    values = [_integer(v, n) for v, n in ((seed, "seed"), (scenario_id, "scenario_id"), (stream_id, "stream_id"))]
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(values))).random(_integer(size, "size", 1))


def bounded_uniform(center, half_width, u, lower=0., upper=1.):
    """Truncate the sampling interval first; never clip draws or repair inputs."""
    if (not np.isfinite(center) or not np.isfinite(half_width) or half_width < 0
            or not np.isfinite(lower) or np.isnan(upper) or upper < lower or not lower <= center <= upper):
        raise ValueError("Invalid center, half width or physical support")
    u = np.asarray(u, float)
    if not (np.isfinite(u).all() and ((0 <= u) & (u <= 1)).all()):
        raise ValueError("Sampling quantiles must lie in [0,1]")
    lo, hi = max(lower, center - half_width), min(upper, center + half_width)
    return lo + u * (hi - lo), dict(effective_lower=float(lo), effective_upper=float(hi),
                                    mean_delta=float((lo + hi) / 2 - center))


def configuration_ids(context):
    return [RESIDUAL_ONLY] + [c["id"] for c in context.d5["experiments"]["monte_carlo"]["full_input_uncertainty"]["configurations"]]


@dataclass
class SimulationResult:
    summary: dict
    draws: dict[str, np.ndarray] | None = None


def _baseline_inputs(scenario, d3):
    inputs, invalid = {}, []
    for name in INPUT_FIELDS:
        try:
            value = float(scenario.get(name))
        except (TypeError, ValueError):
            value = float("nan")
        inputs[name] = value
        if not np.isfinite(value):
            invalid.append(name)
    if invalid:
        return inputs, invalid
    for name in ("payload_g", "altitude_m", "wind_forecast_ms"):
        if inputs[name] < 0:
            invalid.append(name)
    for name in ("distance_2d_m", "speed_commanded_ms"):
        if inputs[name] <= 0:
            invalid.append(name)
    for name in ("soc", "soh"):
        if not 0 <= inputs[name] <= 1:
            invalid.append(name)
    temperature_rule = next(r for r in d3["hard_rules"]["manufacturer"] if r["id"] == "HR-2")
    pieces = temperature_rule["check"].split("<=")
    if not float(pieces[0]) <= inputs["ambient_temp_c"] <= float(pieces[-1]):
        invalid.append("ambient_temp_c")
    return inputs, invalid


def simulate_scenario(context, scenario, *, config_id=RESIDUAL_ONLY, seed=42,
                      draws=None, battery_type="TB47D", reserve_ratio=None, return_draws=False):
    """Simulate one scenario; keep the original candidate verdict fixed.

    Nonpositive demand draws remain counted as invalid and are never resampled.
    Wind/landing/MTOW violations are constraint failures, not invalid draws.
    Missing or physically invalid baselines receive no feasibility fraction.
    """
    mc = context.d5["experiments"]["monte_carlo"]
    choices = mc["computational_choices"]
    n = _integer(choices["draws_per_scenario"] if draws is None else draws, "draws", 1)
    seed = _integer(seed, "seed")
    sid = _integer(scenario.get("scenario_id"), "scenario_id")
    configs = {c["id"]: c for c in mc["full_input_uncertainty"]["configurations"]}
    if config_id not in configuration_ids(context):
        raise ValueError(f"Unknown uncertainty configuration: {config_id}")
    cases = context.d5["factors"]["nominal_battery_energy"]["cases"]
    nominal = {c["battery_type"]: float(c["nominal_Wh"]) for c in cases}
    if battery_type not in nominal:
        raise ValueError(f"Unknown battery: {battery_type}")
    r = context.d5["inherited_baseline"]["decision_policy"]["reserve_ratio"] if reserve_ratio is None else reserve_ratio
    if not np.isfinite(r) or r < 0:
        raise ValueError("Reserve ratio must be finite and nonnegative")
    summary = dict(scenario_id=sid, stratum=scenario.get("stratum"), seed=seed, battery_type=battery_type,
                   assumption_config_id=config_id, reserve_ratio=float(r), draws_requested=n,
                   protocol_version=context.d5["meta"]["version"], module_version=VERSION,
                   constraint_scope="D3 physical VETO checks; weather freshness and historical replay belong to E5",
                   output_label=mc["output_label"], draws_total=0, valid_draws=0, invalid_draws=0,
                   energy_success_count=0, joint_success_count=0,
                   energy_feasibility_fraction=None, joint_feasibility_fraction=None)
    inputs, invalid = _baseline_inputs(scenario, context.d3)
    if invalid:
        return SimulationResult({**summary, "status": "INVALID_BASELINE", "invalid_fields": invalid})
    if scenario.get("stratum") not in context.d5["inherited_baseline"]["primary_strata"]:
        return SimulationResult({**summary, "status": "AUDIT_ONLY_STRATUM"})
    profile = context.d5["inherited_baseline"]["aircraft_profile"]["primary_diagnostic"]
    inputs.update(profile=profile, battery_type=battery_type)
    prediction = context.model.predict(inputs, context.d4)
    if not np.isfinite(prediction) or prediction <= 0:
        return SimulationResult({**summary, "status": "INVALID_BASELINE_PREDICTION"})
    decision = assess(**inputs, e_required_Wh=prediction, reserve_factor=float(r), protocol=context.d3)
    summary.update(aircraft_profile=profile, baseline_verdict=decision.verdict,
                   baseline_prediction_Wh=prediction, baseline_available_Wh=decision.e_available_Wh,
                   baseline_margin_Wh=decision.margin_Wh, baseline_actionable=decision.actionable,
                   baseline_rules=[dict(id=c.rule_id, status=c.status, severity=c.severity)
                                   for c in decision.hard_rule_report.checks])
    for ref in ("ref1", "ref2"):
        summary[f"fixed_label_{ref}"] = scenario.get(f"label_{ref}")
    centers = dict(soc=inputs["soc"], soh=inputs["soh"], wind=inputs["wind_forecast_ms"],
                   kappa=kappa(inputs["ambient_temp_c"], context.d3)[0])
    pool = context.residuals
    contract = mc["random_number_contract"]
    streams = contract["independent_stream_ids"]
    coupled = False
    if config_id == RESIDUAL_ONLY:
        widths = {key: 0. for key in centers}
    else:
        cfg = configs[config_id]
        source = context.d5["sources"]["assumption_decision"][f"{cfg['widths']}_half_widths"]
        widths = dict(soc=source["soc_fraction"], soh=source["soh_fraction"],
                      wind=source["wind_ms"], kappa=source["kappa_absolute"])
        if cfg["residual_pool"] == "NEGATIVE_OOF_RESIDUALS_ONLY":
            pool = pool[pool < 0]
        elif cfg["residual_pool"] != "ALL_SIGNED_OOF_RESIDUALS":
            raise ValueError("Unsupported residual pool")
        if cfg["dependence"] not in ("INDEPENDENT", "ADVERSE_RANK_COUPLING"):
            raise ValueError("Unsupported dependence model")
        coupled = cfg["dependence"] == "ADVERSE_RANK_COUPLING"
    if not len(pool):
        raise ValueError("Empty empirical residual pool")
    if coupled:
        if context.model.wind_coefficient <= 0:
            raise ValueError("Adverse wind coupling requires a positive frozen wind coefficient")
        u = uniform_stream(seed, sid, contract["coupled_stream_id"], n)
        pool = np.sort(pool)
        quantiles = dict(soc=1-u, soh=1-u, kappa=1-u, wind=u, residual=1-u)
    else:
        quantiles = {key: uniform_stream(seed, sid, streams[key], n) for key in (*centers, "residual")}
    sampled, bounds = {}, {}
    for key, center in centers.items():
        sampled[key], bounds[key] = bounded_uniform(center, widths[key], quantiles[key], upper=np.inf if key == "wind" else 1.)
    indices = np.minimum(len(pool)-1, (len(pool) * quantiles["residual"]).astype(int))
    residual = pool[indices]
    demand = prediction + context.model.wind_coefficient * (sampled["wind"] - centers["wind"]) - residual
    available = nominal[battery_type] * sampled["soc"] * sampled["soh"] * sampled["kappa"]
    valid = np.isfinite(demand) & (demand > 0) & np.isfinite(available)
    energy_ok = available >= (1 + r) * demand

    # Reuse D3 fixed VETO checks. Only HR-1 and PH-1 vary across draws.
    rules = check_hard_rules(**inputs, protocol=context.d3)
    failures = {}
    for c in rules.checks:
        if c.rule_id not in ("HR-1", "PH-1") and c.severity == VETO:
            failures[c.rule_id] = np.full(n, c.forces_no_fly or c.status == MISSING, dtype=bool)
    wind_rule = next(c for c in context.d3["hard_rules"]["manufacturer"] if c["id"] == "HR-1")
    wind_limit = float(wind_rule["check"].split("<=")[-1])
    failures["HR-1"] = sampled["wind"] > wind_limit
    floor_cfg = context.d3["hard_rules"]["physics_derived"][0]
    mass = takeoff_mass_g(inputs["payload_g"], battery_type, profile, context.d3["aircraft_profiles"])
    floor = landing_energy_Wh(inputs["altitude_m"], mass, battery_type, descent_rate_ms=float(floor_cfg["descent_rate_ms"]))
    failures["PH-1"] = available < floor
    veto_ok = ~np.logical_or.reduce(list(failures.values()))
    total_valid = int(valid.sum())
    success = int((valid & energy_ok).sum())
    joint = int((valid & energy_ok & veto_ok).sum())
    factors = context.d5["factors"]
    def outside(values, limits):
        return (values < limits[0]) | (values > limits[1])
    support_counts = dict(
        wind_outside_observed=int(outside(sampled["wind"], factors["wind_magnitude"]["measured_coverage_ms"]).sum()),
        wind_outside_scenario=int(outside(sampled["wind"], factors["wind_magnitude"]["scenario_domain_ms"]).sum()),
        soh_outside_scenario=int(outside(sampled["soh"], factors["soh_capacity_retention"]["scenario_domain"]).sum()))
    distance_limits = context.d3["energy_required"]["validity_envelope"]["distance_2d_m"]
    temperature_limits = factors["temperature_derating"]["calibrated_range_c"]
    summary.update(status="OK" if total_valid else "NO_VALID_DRAWS", draws_total=n, valid_draws=total_valid,
                   invalid_draws=n-total_valid, energy_success_count=success, joint_success_count=joint,
                   energy_feasibility_fraction=success/total_valid if total_valid else None,
                   joint_feasibility_fraction=joint/total_valid if total_valid else None,
                   veto_failure_counts={key: int((valid & mask).sum()) for key, mask in failures.items()},
                   veto_failure_count=int((valid & ~veto_ok).sum()), effective_intervals=bounds,
                   residual_pool_size=len(pool), residual_pool_mean_Wh=float(pool.mean()),
                   landing_floor_Wh=float(floor), support_counts=support_counts,
                   distance_extrapolated=not distance_limits[0] <= inputs["distance_2d_m"] <= distance_limits[1],
                   temperature_outside_calibration=not temperature_limits[0] <= inputs["ambient_temp_c"] <= temperature_limits[1],
                   temperature_regime=kappa(inputs["ambient_temp_c"], context.d3)[1],
                   valid_margin_min_Wh=float(np.min((available-demand)[valid])) if total_valid else None,
                   valid_margin_max_Wh=float(np.max((available-demand)[valid])) if total_valid else None)
    values = dict(**sampled, residual_Wh=residual, e_demand_Wh=demand, e_available_Wh=available,
                  valid=valid, reserve_ok=energy_ok, veto_ok=veto_ok)
    return SimulationResult(summary, values if return_draws else None)


def summarize_results(rows, manifest):
    """Aggregate counts within each profile/reserve/config/battery/seed only.

    Fractions use pooled valid-draw counts, not an unlabelled average of the
    scenario fractions. No fractions are pooled across uncertainty assumptions.
    Skipped scenario IDs are deduplicated independently of their repeated rows.
    """
    groups, skipped = {}, {}
    simulated = set()
    for row in rows:
        if row["draws_total"] == 0:
            key = (row["scenario_id"], row["status"])
            skipped[key] = dict(scenario_id=row["scenario_id"], status=row["status"],
                                reason=", ".join(row.get("invalid_fields", [])) or row["status"])
            continue
        simulated.add(row["scenario_id"])
        key = (row["aircraft_profile"], row["reserve_ratio"], row["assumption_config_id"], row["battery_type"], row["seed"])
        if key not in groups:
            groups[key] = dict(aircraft_profile=key[0], reserve_ratio=key[1], assumption_config_id=key[2],
                               battery_type=key[3], seed=key[4], scenario_ids=set(), draws_total=0,
                               valid_draws=0, invalid_draws=0, energy_success_count=0, joint_success_count=0)
        group = groups[key]
        group["scenario_ids"].add(row["scenario_id"])
        for field in ("draws_total", "valid_draws", "invalid_draws", "energy_success_count", "joint_success_count"):
            group[field] += row[field]
    grouped = []
    order = {name: index for index, name in enumerate(manifest["configurations"])}
    for key in sorted(groups, key=lambda k: (k[0], k[1], order[k[2]], k[3], k[4])):
        group = groups[key]
        group["scenario_count"] = len(group.pop("scenario_ids"))
        denominator = group["valid_draws"]
        group["energy_feasibility_fraction"] = group["energy_success_count"]/denominator if denominator else None
        group["joint_feasibility_fraction"] = group["joint_success_count"]/denominator if denominator else None
        grouped.append(group)
    return dict(run_id=manifest["run_id"], protocol_version=manifest["protocol_version"],
                run_kind=manifest["run_kind"], selected_scenarios=len(set(manifest["selected_scenario_ids"])),
                simulated_scenarios=len(simulated), result_rows=len(rows),
                draws_total=sum(r["draws_total"] for r in rows),
                valid_draws=sum(r["valid_draws"] for r in rows),
                invalid_draws=sum(r["invalid_draws"] for r in rows),
                skipped_scenarios=[skipped[k] for k in sorted(skipped)], groups=grouped)


def format_terminal_summary(summary):
    """Readable console/text report with explicit units, grouping and exclusions."""
    lines = ["", "=" * 92, "TOM TAT MONTE CARLO D5", "=" * 92,
             f"Run: {summary['run_id']} | Protocol: {summary['protocol_version']} | {summary['run_kind']}",
             f"Kich ban da chon: {summary['selected_scenarios']:,} | Co lay mau: {summary['simulated_scenarios']:,}",
             f"So dong ket qua: {summary['result_rows']:,}",
             f"Tong luot lay mau: {summary['draws_total']:,}",
             f"Mau hop le: {summary['valid_draws']:,} | Mau khong hop le: {summary['invalid_draws']:,}"]
    skip_groups = {}
    for row in summary["skipped_scenarios"]:
        skip_groups[row["status"]] = skip_groups.get(row["status"], 0) + 1
    for status, count in sorted(skip_groups.items()):
        lines.append(f"Kich ban bo qua - {status}: {count:,}")
    if summary["skipped_scenarios"] and len(summary["skipped_scenarios"]) <= 10:
        for row in summary["skipped_scenarios"]:
            lines.append(f"  ID {row['scenario_id']}: {row['status']} ({row['reason']})")
    tables = {}
    for group in summary["groups"]:
        tables.setdefault((group["aircraft_profile"], group["reserve_ratio"]), []).append(group)
    for (profile, reserve), groups in tables.items():
        lines.extend(["", f"Ho so: {profile} | Muc du tru: {reserve:.0%}",
                      "Ket qua tach rieng theo cau hinh, pin va seed:"])
        table = []
        for group in groups:
            def percent(field):
                value = group[field]
                return f"{100*value:.2f}" if value is not None else "NA"
            table.append(dict(Cau_hinh=group["assumption_config_id"], Pin=group["battery_type"],
                              Seed=group["seed"], Kich_ban=group["scenario_count"],
                              Mau_hop_le=f"{group['valid_draws']:,}",
                              Dat_du_tru_pct=percent("energy_feasibility_fraction"),
                              Kem_VETO_pct=percent("joint_feasibility_fraction")))
        lines.append(pd.DataFrame(table).to_string(index=False))
    if not tables:
        lines.append("Khong co kich ban duoc lay mau; khong tinh ty le.")
    lines.extend(["", "Dat_du_tru_pct: tong mau du nang luong va du tru / tong mau hop le x 100.",
                  "Kem_VETO_pct: dong thoi du du tru va qua cac VETO vat ly D3.",
                  "NA: mau so bang 0. Kich ban bo qua khong nam trong mau so.",
                  "Ty le tren phu thuoc tap kich ban va gia dinh; chua la xac suat bay thanh cong.",
                  "Trang thai: ban chay phat trien; E4/E5 day du va nghiem thu D5 con chua hoan tat."])
    return "\n".join(lines)


def print_saved_summary(out):
    """Read verified saved output; never rerun sampling or rewrite the old run."""
    out = Path(out)
    status = json.loads((out / "run_status.json").read_text(encoding="utf-8"))
    if status["status"] != "COMPLETED_DEVELOPMENT_PARTIAL":
        raise ValueError(f"Run is not completed: {status['status']}")
    manifest_path = out / "input_manifest.json"
    if _sha(manifest_path) != status["input_manifest_hash"]:
        raise ValueError("Saved input manifest hash mismatch")
    output = out / "monte_carlo_fractions.json"
    if _sha(output) != status["output_hashes"][output.name]:
        raise ValueError("Saved results hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = json.loads(output.read_text(encoding="utf-8"))
    summary = summarize_results(rows, manifest)
    print(format_terminal_summary(summary))
    return summary


def run_development(out, *, root=ROOT, limit=3, scenario_ids=None, draws=None):
    """Save a partial development run with provenance. Never label it final D5."""
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing run: {out}")
    context = load_context(root)
    source = context.root / context.d5["inherited_baseline"]["scenario_file"]
    scenarios = pd.read_csv(source, low_memory=False)
    if not scenarios.scenario_id.is_unique:
        raise ValueError("Duplicate scenario IDs")
    if scenario_ids is not None:
        ids = [_integer(i, "scenario_id") for i in scenario_ids]
        if not ids or len(set(ids)) != len(ids) or not set(ids) <= set(scenarios.scenario_id):
            raise ValueError("Scenario IDs must be unique, nonempty and present in the saved input")
        selected = scenarios[scenarios.scenario_id.isin(ids)].sort_values("scenario_id")
    else:
        _integer(limit, "limit", 1)
        selected = scenarios[scenarios.stratum.isin(context.d5["inherited_baseline"]["primary_strata"])].sort_values("scenario_id").head(limit)
    seeds = context.d5["experiments"]["monte_carlo"]["computational_choices"]["seeds"]
    batteries = [c["battery_type"] for c in context.d5["factors"]["nominal_battery_energy"]["cases"]]
    code_paths = ["src/uncertainty.py", "src/available_energy.py", "src/decision_rules.py", "src/reference_labeller.py",
                  "src/safety_invariants.py", "src/physics_m100.py"]
    manifest = dict(run_id=out.name, run_kind="DEVELOPMENT_PARTIAL", final_d5_complete=False,
                    started_at_utc=datetime.now(timezone.utc).isoformat(), protocol_version=context.d5["meta"]["version"],
                    protocol_frozen=context.d5["meta"]["frozen"], selected_scenario_ids=selected.scenario_id.tolist(),
                    configurations=configuration_ids(context), seeds=seeds, battery_types=batteries,
                    draws_per_scenario=draws if draws is not None else context.d5["experiments"]["monte_carlo"]["computational_choices"]["draws_per_scenario"],
                    draws_override=draws is not None, input_hashes=context.input_hashes,
                    code_hashes={p: _sha(context.root / p) for p in code_paths},
                    runtime=dict(python=platform.python_version(), platform=platform.platform(), numpy=np.__version__,
                                 pandas=pd.__version__, pyyaml=yaml.__version__,
                                 scikit_learn=package_version("scikit-learn"), scipy=package_version("scipy")),
                    rng=context.d5["experiments"]["monte_carlo"]["random_number_contract"],
                    output_label=context.d5["experiments"]["monte_carlo"]["output_label"])
    for command, key in ((["git", "rev-parse", "HEAD"], "source_commit"), (["git", "status", "--porcelain"], "git_status")):
        proc = subprocess.run(command, cwd=context.root, capture_output=True, text=True, check=False)
        manifest[key] = proc.stdout.strip() if proc.returncode == 0 else None
    out.mkdir(parents=True, exist_ok=False)
    manifest_path = out / "input_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    manifest_hash = _sha(manifest_path)
    status_path = out / "run_status.json"
    status = dict(run_id=out.name, status="RUNNING_DEVELOPMENT_PARTIAL", final_d5_complete=False,
                  input_manifest_hash=manifest_hash)
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    print(f"D5 protocol {manifest['protocol_version']} | DEVELOPMENT_PARTIAL", flush=True)
    print(f"Kich ban: {len(selected):,} | Mau/kich ban/cau hinh/pin/seed: {manifest['draws_per_scenario']:,}", flush=True)
    print(f"Seeds: {seeds} | Pin: {', '.join(batteries)} | Cau hinh: {len(manifest['configurations'])}", flush=True)
    try:
        for completed, row in enumerate(selected.to_dict("records"), 1):
            for seed in seeds:
                for config in configuration_ids(context):
                    for battery in batteries:
                        result = simulate_scenario(context, row, seed=seed, config_id=config, battery_type=battery, draws=draws).summary
                        rows.append({**result, "run_id": out.name, "input_manifest_hash": manifest_hash})
            print(f"Completed scenario {row['scenario_id']} ({completed:,}/{len(selected):,}; {completed/len(selected):.1%})", flush=True)
        output = out / "monte_carlo_fractions.json"
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        flat = [{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows]
        pd.DataFrame(flat).to_csv(out / "monte_carlo_fractions.csv", index=False)
        summary = summarize_results(rows, manifest)
        summary_text = format_terminal_summary(summary)
        (out / "terminal_summary.txt").write_text(summary_text + "\n", encoding="utf-8")
        summary_columns = ["aircraft_profile", "reserve_ratio", "assumption_config_id", "battery_type", "seed",
                           "scenario_count", "draws_total", "valid_draws", "invalid_draws", "energy_success_count",
                           "joint_success_count", "energy_feasibility_fraction", "joint_feasibility_fraction"]
        pd.DataFrame(summary["groups"], columns=summary_columns).assign(
            run_id=out.name, protocol_version=manifest["protocol_version"], input_manifest_hash=manifest_hash
        ).to_csv(out / "terminal_summary.csv", index=False)
        changed = [p for p, expected in {**manifest["input_hashes"], **manifest["code_hashes"]}.items()
                   if _sha(context.root / p) != expected]
        if changed:
            raise RuntimeError(f"Inputs/code changed during run: {changed}")
        status.update(status="COMPLETED_DEVELOPMENT_PARTIAL", completed_at_utc=datetime.now(timezone.utc).isoformat(),
                      output_hashes={p.name: _sha(p) for p in (output, out / "monte_carlo_fractions.csv",
                                                             out / "terminal_summary.txt", out / "terminal_summary.csv")})
    except Exception as error:
        status.update(status="FAILED", error=str(error))
        raise
    finally:
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(summary_text)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary-only", type=Path, metavar="RUN_DIRECTORY",
                        help="Print summary of saved results without rerunning Monte Carlo")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--limit", type=int)
    group.add_argument("--scenario-ids", type=int, nargs="+")
    parser.add_argument("--draws", type=int, help="Development override, explicitly recorded in manifest")
    args = parser.parse_args()
    if args.summary_only is not None:
        if any(value is not None for value in (args.out, args.limit, args.scenario_ids, args.draws)):
            parser.error("--summary-only cannot be combined with run options")
        try:
            print_saved_summary(args.summary_only)
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(f"Cannot read saved summary: {error}")
        return
    if args.out is None:
        parser.error("--out is required for a new run")
    results = run_development(args.out, limit=3 if args.limit is None else args.limit, scenario_ids=args.scenario_ids, draws=args.draws)
    print(f"Saved {len(results)} result rows to {args.out}; development run only.")


if __name__ == "__main__":
    main()
