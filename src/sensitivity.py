"""D5 one-factor-at-a-time sensitivity over the full declared scenario population.

Deterministic grids are read from the protocol. Each evaluation changes one
factor, keeps original reference labels/membership fixed and reassesses D3's
decision. Grid frequencies are not Monte Carlo probabilities or causal effects.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from src.physics_m100 import landing_energy_Wh
from src.reference_labeller import scenario_features
from src.uncertainty import ROOT, load_context

VERDICTS = ["FLY", "CONDITIONAL", "NO_FLY", "INSUFFICIENT_DATA"]
ERROR_FACTORS = ["soc_error", "soh_error", "wind_error", "kappa_error", "energy_error"]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class Point:
    factor: str
    kind: str
    point_id: str
    value: float | str
    unit: str
    primary_error: bool = False


def sweep_points(context):
    oat = context.d5["experiments"]["one_factor_at_a_time"]
    specs = [("soc_error", oat["soc_error_sweep"]["offsets"], "fraction", .02),
             ("soh_error", oat["other_input_error_sweeps"]["soh_offsets"], "fraction", .02),
             ("wind_error", oat["other_input_error_sweeps"]["wind_offsets_ms"], "m/s", 1.),
             ("kappa_error", oat["other_input_error_sweeps"]["kappa_offsets"], "absolute", .02)]
    widths = context.d5["sources"]["assumption_decision"]["primary_half_widths"]
    limits = dict(soc_error=widths["soc_fraction"], soh_error=widths["soh_fraction"],
                  wind_error=widths["wind_ms"], kappa_error=widths["kappa_absolute"])
    points = [Point(name, "input_error", str(i), float(value), unit, abs(value) <= limits[name])
              for name, values, unit, _ in specs for i, value in enumerate(values)]
    factors = context.d5["factors"]
    n = oat["numeric_grid"]["points_per_continuous_domain"]
    for name, domain, unit in [("soh_domain", factors["soh_capacity_retention"]["scenario_domain"], "fraction"),
                               ("wind_domain", factors["wind_magnitude"]["scenario_domain_ms"], "m/s"),
                               ("temperature_domain", factors["temperature_derating"]["scenario_domain_c"], "degC")]:
        grid = np.linspace(*domain, n)
        if name == "temperature_domain":
            grid = np.unique(np.r_[grid, factors["temperature_derating"]["calibrated_range_c"]])
        points.extend(Point(name, "scenario_domain", str(i), float(value), unit) for i, value in enumerate(grid))
    points += [Point("reserve_policy", "policy", str(i), float(value), "fraction")
               for i, value in enumerate(factors["reserve_policy"]["plotting_values"])]
    points += [Point("battery_assumption", "battery_assumption", c["battery_type"], c["battery_type"], "battery")
               for c in factors["nominal_battery_energy"]["cases"]]
    cfg = factors["energy_prediction_error"]
    pool = pd.read_csv(context.root / cfg["file"]).sort_values(cfg["id_column"])
    points += [Point("energy_error", "empirical_error", f"flight_{row[cfg['id_column']]}",
                     float(row[cfg["value_column"]]), "Wh", True) for row in pool.to_dict("records")]
    return points


def prepare(context, scenarios):
    raw = {name: scenarios[name].to_numpy(float) for name in
           ["payload_g", "speed_commanded_ms", "altitude_m", "distance_2d_m", "wind_forecast_ms", "ambient_temp_c", "soc", "soh"]}
    x = scenario_features(scenarios, context.d4, list(context.model.features)).to_numpy(float)
    if not np.isfinite(x).all() or not all(np.isfinite(a).all() for a in raw.values()):
        raise ValueError("Primary population has missing/nonfinite required inputs")
    raw["prediction"] = ((x-context.model.means)/context.model.scales) @ context.model.coefficients + context.model.intercept
    return raw


def evaluate(context, raw, baseline_battery, point=None):
    """Vectorized D3 reassessment; independent scalar-D3 equivalence is tested."""
    n = len(raw["prediction"])
    soc, soh, wind, temp = (raw[k].copy() for k in ("soc", "soh", "wind_forecast_ms", "ambient_temp_c"))
    r = np.full(n, context.d5["inherited_baseline"]["decision_policy"]["reserve_ratio"], dtype=float)
    battery = baseline_battery
    if point:
        if point.factor == "soc_error": soc += point.value
        elif point.factor == "soh_error": soh += point.value
        elif point.factor == "wind_error": wind += point.value
        elif point.factor == "soh_domain": soh[:] = point.value
        elif point.factor == "wind_domain": wind[:] = point.value
        elif point.factor == "temperature_domain": temp[:] = point.value
        elif point.factor == "reserve_policy": r[:] = point.value
        elif point.factor == "battery_assumption": battery = str(point.value)
        elif point.factor not in ("kappa_error", "energy_error"):
            raise ValueError(f"Unsupported factor {point.factor}")
    lo, hi = context.d3["available_energy"]["kappa_temperature"]["calibrated_range_c"]
    polynomial = lambda t: .8814 + .0091*t - .0001*t*t
    kap = np.where(temp < lo, polynomial(lo), np.where(temp > hi, 1., np.minimum(1., polynomial(temp))))
    if point and point.factor == "kappa_error": kap += point.value
    required = raw["prediction"] + context.model.wind_coefficient*(wind-raw["wind_forecast_ms"])
    if point and point.factor == "energy_error": required -= point.value
    nominal = {c["battery_type"]: c["nominal_Wh"] for c in context.d5["factors"]["nominal_battery_energy"]["cases"]}[battery]
    available = nominal*soc*soh*kap
    physical = ((soc >= 0)&(soc <= 1)&(soh >= 0)&(soh <= 1)&(kap >= 0)&(kap <= 1)&(wind >= 0))
    valid = physical & np.isfinite(required) & (required > 0)
    manufacturer = {c["id"]: c for c in context.d3["hard_rules"]["manufacturer"]}
    wind_limit = float(manufacturer["HR-1"]["check"].split("<=")[-1])
    speed_limit = float(manufacturer["HR-4"]["check"].split("<=")[-1])
    tparts = manufacturer["HR-2"]["check"].split("<=")
    profile = context.d5["inherited_baseline"]["aircraft_profile"]["primary_diagnostic"]
    pcfg = context.d3["aircraft_profiles"][profile]
    mass = pcfg["airframe_mass_g"]
    mass = (mass[battery] if isinstance(mass, dict) else mass) + raw["payload_g"]
    descent = context.d3["hard_rules"]["physics_derived"][0]["descent_rate_ms"]
    floor_key = f"landing_{battery}"
    if floor_key not in raw:
        raw[floor_key] = np.array([landing_energy_Wh(a, m, battery, descent_rate_ms=descent)
                                  for a, m in zip(raw["altitude_m"], mass)])
    floor = raw[floor_key]
    mtow_veto = np.zeros(n, bool) if profile == "CMU_instrumented" else mass > pcfg["mtow_g"]
    wind_veto = wind > wind_limit
    landing_veto = available < floor
    veto = wind_veto | landing_veto | mtow_veto | (temp < float(tparts[0])) | (temp > float(tparts[-1])) | (raw["speed_commanded_ms"] > speed_limit)
    limits = {c["id"]: c["check"].split("<=") for c in context.d3["hard_rules"]["project_derived"]}
    outside_distance = (raw["distance_2d_m"] < float(limits["PD-1"][0])) | (raw["distance_2d_m"] > float(limits["PD-1"][-1]))
    outside_payload = (raw["payload_g"] < float(limits["PD-2"][0])) | (raw["payload_g"] > float(limits["PD-2"][-1]))
    margin = available-required
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = margin/required
        threshold = r + context.d3["energy_required"]["measured_error"]["p95_abs_residual_Wh"]/required
    verdict = np.full(n, "NO_FLY", dtype=object)
    enough = valid & ~veto & (ratio >= r)
    verdict[enough] = "CONDITIONAL"
    verdict[enough & (ratio >= threshold) & ~outside_distance & ~outside_payload] = "FLY"
    verdict[~valid] = "NOT_EVALUATED_INVALID_PERTURBATION"
    return dict(valid=valid, verdict=verdict, required=required, available=available, margin=margin,
                ratio=ratio, reserve=r, slack=available-(1+r)*required, reserve_ok=available >= (1+r)*required,
                veto=veto, wind_veto=wind_veto, landing_veto=landing_veto, soc=soc, soh=soh, wind=wind,
                temp=temp, kappa=kap, effective_battery=battery, distance_extrapolated=outside_distance,
                wind_extrapolated=(wind < 2.81)|(wind > 6.67), temperature_extrapolated=(temp < lo)|(temp > hi))


def reference_scopes(context, scenarios, ref):
    ratio = scenarios[f"margin_ratio_{ref}"].to_numpy(float)
    r = context.d5["experiments"]["boundary_analysis"]["reference_reserve_ratio"]
    masks = {"all": np.ones(len(scenarios), bool)}
    for w in context.d5["experiments"]["boundary_analysis"]["sweep_w"]:
        boundary = (np.abs(ratio) <= w)|(np.abs(ratio-r) <= w)
        masks[f"boundary_w={w}"] = boundary
        masks[f"outside_boundary_w={w}"] = ~boundary
    masks["marginal"] = scenarios[f"label_{ref}"].to_numpy() == "marginal"
    for name in context.d5["inherited_baseline"]["primary_strata"]:
        masks[f"stratum={name}"] = scenarios.stratum.to_numpy() == name
    for name, values, domain in [("distance", scenarios.distance_2d_m.to_numpy(), context.d3["energy_required"]["validity_envelope"]["distance_2d_m"]),
                                  ("wind", scenarios.wind_forecast_ms.to_numpy(), context.d5["factors"]["wind_magnitude"]["measured_coverage_ms"]),
                                  ("temperature", scenarios.ambient_temp_c.to_numpy(), context.d5["factors"]["temperature_derating"]["calibrated_range_c"])]:
        inside = (values >= domain[0])&(values <= domain[1])
        masks[f"original_{name}_in_support"] = inside
        masks[f"original_{name}_outside_support"] = ~inside
    return masks


def reference_rows(evaluation, baseline, labels, scopes, metadata, ref):
    rows = []
    for mapping in ("INFEASIBLE", "FEASIBLE"):
        bad = (labels == "infeasible") | ((labels == "marginal") if mapping == "INFEASIBLE" else False)
        good = (labels == "feasible") | ((labels == "marginal") if mapping == "FEASIBLE" else False)
        known = bad | good
        for scope_name, scope in scopes.items():
            valid = scope & evaluation["valid"] & known
            neg, pos = valid & bad, valid & good
            nbad, ngood = int(neg.sum()), int(pos.sum())
            fs = int((neg & (evaluation["verdict"] == "FLY")).sum())
            reject = int((pos & (evaluation["verdict"] == "NO_FLY")).sum())
            cond = int((pos & (evaluation["verdict"] == "CONDITIONAL")).sum())
            rows.append({**metadata, "reference_model": ref.upper().replace("REF", "REF-"),
                         "reference_policy": "FIXED_ORIGINAL_D4", "marginal_mapping": mapping, "scope": scope_name,
                         "scope_scenarios": int(scope.sum()), "invalid_perturbations": int((scope & ~evaluation["valid"]).sum()),
                         "unknown_reference": int((scope & ~known).sum()), "scored_scenarios": int(valid.sum()),
                         "reference_infeasible": nbad, "reference_feasible": ngood,
                         "false_safe_count": fs, "false_safe_rate": fs/nbad if nbad else None,
                         "infeasible_recall": 1-fs/nbad if nbad else None,
                         "unnecessary_rejection_count": reject, "unnecessary_rejection_rate": reject/ngood if ngood else None,
                         "conditional_count_among_feasible": cond, "conditional_rate_among_feasible": cond/ngood if ngood else None,
                         "baseline_false_safe_count": int((neg & (baseline["verdict"] == "FLY")).sum())})
    return rows


def run(out, *, source_run, fly_review, root=ROOT):
    out, source_run, fly_review = Path(out), Path(source_run), Path(fly_review)
    if out.exists(): raise FileExistsError(f"Choose a new output directory: {out}")
    context = load_context(root)
    source_status = json.loads((source_run/"run_status.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((source_run/"input_manifest.json").read_text(encoding="utf-8"))
    if source_status["status"] != "COMPLETED_DEVELOPMENT_PARTIAL" or sha(source_run/"input_manifest.json") != source_status["input_manifest_hash"]:
        raise ValueError("Invalid completed Monte Carlo source")
    source_csv = source_run/"monte_carlo_fractions.csv"
    if sha(source_csv) != source_status["output_hashes"][source_csv.name]: raise ValueError("Monte Carlo CSV changed")
    for relative, digest in context.input_hashes.items():
        if relative != "configs/d5_protocol.yaml" and digest != source_manifest["input_hashes"][relative]:
            raise ValueError(f"Different upstream artifact: {relative}")
    review_meta = json.loads((fly_review/"analysis_manifest.json").read_text(encoding="utf-8"))
    if review_meta["source_csv_sha256"] != source_status["output_hashes"][source_csv.name]: raise ValueError("FLY review comes from another run")
    selected_cases = fly_review/"fly_reserve_failures.csv"
    if sha(selected_cases) != review_meta["output_hashes"][selected_cases.name]: raise ValueError("FLY review changed")
    affected = pd.read_csv(selected_cases)
    affected = affected[affected.assumption_config_id == "PRIMARY_INDEPENDENT"]
    scenarios = pd.read_csv(context.root/context.d5["inherited_baseline"]["scenario_file"], low_memory=False)
    audit = scenarios[~scenarios.stratum.isin(context.d5["inherited_baseline"]["primary_strata"])]
    scenarios = scenarios[scenarios.stratum.isin(context.d5["inherited_baseline"]["primary_strata"])].sort_values("scenario_id").reset_index(drop=True)
    if set(scenarios.scenario_id) != set(source_manifest["selected_scenario_ids"]): raise ValueError("Scenario population differs from Monte Carlo")
    raw = prepare(context, scenarios)
    points = sweep_points(context)
    batteries = [c["battery_type"] for c in context.d5["factors"]["nominal_battery_energy"]["cases"]]
    baselines = {b: evaluate(context, raw, b) for b in batteries}
    if not all(v["valid"].all() for v in baselines.values()): raise ValueError("Invalid baseline population")
    # Independent saved-run baseline agreement, not merely self-comparison.
    check_cols = ["scenario_id","battery_type","seed","assumption_config_id","baseline_verdict","baseline_prediction_Wh"]
    saved = []
    for chunk in pd.read_csv(source_csv, usecols=check_cols, chunksize=30000):
        saved.append(chunk[(chunk.seed == source_manifest["seeds"][0]) & (chunk.assumption_config_id == "RESIDUAL_ONLY")])
    saved = pd.concat(saved)
    for battery in batteries:
        expected = saved[saved.battery_type == battery].set_index("scenario_id").loc[scenarios.scenario_id]
        if not np.array_equal(expected.baseline_verdict, baselines[battery]["verdict"]): raise ValueError(f"Baseline verdict mismatch: {battery}")
        np.testing.assert_allclose(expected.baseline_prediction_Wh, raw["prediction"], atol=1e-8, rtol=1e-8)
    scopes = {ref: reference_scopes(context, scenarios, ref) for ref in ("ref1","ref2")}
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(started_at_utc=datetime.now(timezone.utc).isoformat(), status="RUNNING_OAT_DEVELOPMENT",
                    protocol_version=context.d5["meta"]["version"], final_d5_complete=False,
                    source_run_id=source_manifest["run_id"], source_manifest_hash=source_status["input_manifest_hash"],
                    input_hashes=context.input_hashes, source_csv_hash=source_status["output_hashes"][source_csv.name],
                    code_hashes={name:sha(context.root/name) for name in ["src/sensitivity.py","src/uncertainty.py","src/physics_m100.py",
                                "src/decision_rules.py","src/safety_invariants.py","src/reference_labeller.py","src/available_energy.py"]},
                    runtime=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
                    scenario_count=len(scenarios), diagnostic_profile=context.d5["inherited_baseline"]["aircraft_profile"]["primary_diagnostic"],
                    batteries=batteries, points=[asdict(p) for p in points], focus_cases=len(affected),
                    baseline_verdict_matches_saved_MC=True, exclusions=audit.stratum.value_counts().to_dict(),
                    reference_policy="Original D4 labels and boundary membership remain fixed, including TB48D",
                    grid_frequency_note="Frequencies over deterministic grids are not probabilities; OOF values have equal flight weights")
    path = out/"input_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    curve_rows, metric_rows, transition_rows, rank_rows, focus_rows = [], [], [], [], []
    all_case_path = out/"scenario_factor_sensitivity.csv.gz"
    long_path = out/"one_factor_evaluations.csv.gz"
    try:
        with gzip.open(long_path,"wt",encoding="utf-8",newline="",compresslevel=1) as long_file, gzip.open(all_case_path,"wt",encoding="utf-8",newline="",compresslevel=1) as case_file:
            long_header = case_header = True
            for battery in batteries:
                base = baselines[battery]
                focus_mask = scenarios.scenario_id.isin(affected[affected.battery_type == battery].scenario_id).to_numpy()
                for factor in dict.fromkeys(p.factor for p in points):
                    family = [p for p in points if p.factor == factor]
                    count=np.zeros(len(scenarios),int); changes=count.copy(); fails=count.copy(); primary_fail=np.zeros(len(scenarios),bool)
                    lows=np.full(len(scenarios),np.inf); highs=np.full(len(scenarios),-np.inf)
                    reqlo=lows.copy(); reqhi=highs.copy(); avlo=lows.copy(); avhi=highs.copy(); slacklo=lows.copy()
                    for point in family:
                        result = evaluate(context, raw, battery, point)
                        valid = result["valid"]
                        changed = valid & (result["verdict"] != base["verdict"])
                        failed = valid & ~result["reserve_ok"]
                        count += valid; changes += changed; fails += failed
                        if point.primary_error: primary_fail |= failed
                        for low, high, values in [(lows,highs,result["margin"]),(reqlo,reqhi,result["required"]),(avlo,avhi,result["available"])]:
                            low[:] = np.minimum(low,np.where(valid,values,np.inf)); high[:] = np.maximum(high,np.where(valid,values,-np.inf))
                        slacklo[:] = np.minimum(slacklo,np.where(valid,result["slack"],np.inf))
                        metadata = dict(battery_type=battery, effective_battery=result["effective_battery"], factor=factor, sweep_kind=point.kind,
                                        point_id=point.point_id, point_value=point.value, point_unit=point.unit, primary_error_point=point.primary_error)
                        mean = lambda a: float(np.mean(a[valid])) if valid.any() else None
                        curve_rows.append({**metadata,"valid_scenarios":int(valid.sum()),"invalid_perturbations":int((~valid).sum()),
                                           "verdict_changes":int(changed.sum()),"reserve_shortfalls":int(failed.sum()),
                                           "initial_fly_valid":int((valid&(base["verdict"]=="FLY")).sum()),
                                           "initial_fly_reserve_shortfalls":int((failed&(base["verdict"]=="FLY")).sum()),
                                           "required_mean_Wh":mean(result["required"]),"available_mean_Wh":mean(result["available"]),
                                           "margin_mean_Wh":mean(result["margin"]),"margin_ratio_mean":mean(result["ratio"]),
                                           "delta_required_mean_Wh":mean(result["required"]-base["required"]),
                                           "delta_available_mean_Wh":mean(result["available"]-base["available"]),
                                           "delta_margin_mean_Wh":mean(result["margin"]-base["margin"]),
                                           "veto_count":int((valid&result["veto"]).sum()),"wind_veto_count":int((valid&result["wind_veto"]).sum()),
                                           "landing_veto_count":int((valid&result["landing_veto"]).sum())})
                        for old in VERDICTS:
                            for new in VERDICTS:
                                transition_rows.append({**metadata,"baseline_verdict":old,"reassessed_verdict":new,
                                                        "count":int((valid&(base["verdict"]==old)&(result["verdict"]==new)).sum())})
                        for ref in ("ref1","ref2"):
                            metric_rows.extend(reference_rows(result,base,scenarios[f"label_{ref}"].to_numpy(),scopes[ref],metadata,ref))
                        details = pd.DataFrame(dict(scenario_id=scenarios.scenario_id, stratum=scenarios.stratum,
                            baseline_verdict=base["verdict"], reassessed_verdict=result["verdict"],
                            status=np.where(valid,"OK","NOT_EVALUATED_INVALID_PERTURBATION"),
                            required_Wh=np.where(valid,result["required"],np.nan), available_Wh=np.where(valid,result["available"],np.nan),
                            margin_Wh=np.where(valid,result["margin"],np.nan),margin_ratio=np.where(valid,result["ratio"],np.nan),
                            delta_required_Wh=np.where(valid,result["required"]-base["required"],np.nan),
                            delta_available_Wh=np.where(valid,result["available"]-base["available"],np.nan),
                            delta_margin_Wh=np.where(valid,result["margin"]-base["margin"],np.nan),
                            reserve_ratio=result["reserve"],reserve_slack_Wh=np.where(valid,result["slack"],np.nan),
                            reserve_met=np.where(valid,result["reserve_ok"].astype(float),np.nan), veto=result["veto"],
                            soc=result["soc"],soh=result["soh"],wind_ms=result["wind"],temperature_c=result["temp"],kappa=result["kappa"],
                            distance_extrapolated=result["distance_extrapolated"],wind_extrapolated=result["wind_extrapolated"],
                            temperature_outside_calibration=result["temperature_extrapolated"],
                            fixed_label_ref1=scenarios.label_ref1,fixed_label_ref2=scenarios.label_ref2)).assign(**metadata)
                        details.to_csv(long_file,index=False,header=long_header); long_header=False
                    has = count > 0
                    per_case = pd.DataFrame(dict(scenario_id=scenarios.scenario_id,battery_type=battery,factor=factor,sweep_kind=family[0].kind,
                        baseline_verdict=base["verdict"],valid_points=count,invalid_points=len(family)-count,verdict_changes=changes,
                        reserve_shortfall_points=fails,primary_error_shortfall=primary_fail,
                        margin_min_Wh=np.where(has,lows,np.nan),margin_max_Wh=np.where(has,highs,np.nan),margin_range_Wh=np.where(has,highs-lows,np.nan),
                        required_min_Wh=np.where(has,reqlo,np.nan),required_max_Wh=np.where(has,reqhi,np.nan),
                        available_min_Wh=np.where(has,avlo,np.nan),available_max_Wh=np.where(has,avhi,np.nan),
                        reserve_slack_min_Wh=np.where(has,slacklo,np.nan)))
                    per_case.to_csv(case_file,index=False,header=case_header);case_header=False
                    focus_rows.append(per_case[focus_mask].copy())
                    rank_rows.append(dict(battery_type=battery,factor=factor,sweep_kind=family[0].kind,grid_points=len(family),
                        valid_evaluations=int(count.sum()),invalid_evaluations=int((len(family)-count).sum()),
                        changed_verdict_evaluations=int(changes.sum()),change_rate=float(changes.sum()/count.sum()) if count.sum() else None,
                        scenarios_any_verdict_change=int((changes>0).sum()),
                        mean_margin_range_Wh=float(np.mean((highs-lows)[has])),max_margin_range_Wh=float(np.max((highs-lows)[has])),
                        initial_fly_primary_error_shortfall_cases=int((primary_fail&(base["verdict"]=="FLY")).sum()) if any(p.primary_error for p in family) else None))
                    print(f"Completed {battery}: {factor} ({len(family)} grid points x {len(scenarios):,} scenarios)",flush=True)
        outputs = {"one_factor_curves.csv":pd.DataFrame(curve_rows),"reference_metrics.csv":pd.DataFrame(metric_rows),
                   "verdict_transitions.csv":pd.DataFrame(transition_rows),"sensitivity_ranking.csv":pd.DataFrame(rank_rows),
                   "fly_case_factor_details.csv":pd.concat(focus_rows,ignore_index=True)}
        for name,frame in outputs.items(): frame.to_csv(out/name,index=False)
        focused = outputs["fly_case_factor_details.csv"]
        diagnosis = focused[focused.factor.isin(ERROR_FACTORS)].pivot(index=["scenario_id","battery_type"],columns="factor",values="primary_error_shortfall").reset_index()
        for name in ERROR_FACTORS:
            if name not in diagnosis: diagnosis[name] = False
        diagnosis["single_factor_response"] = diagnosis[ERROR_FACTORS].apply(lambda row:
            ", ".join(name for name in ERROR_FACTORS if row[name]) or "NONE_ON_PRIMARY_GRID",axis=1)
        diagnosis = affected[["scenario_id","battery_type","failure_fraction_min","failure_fraction_max"]].merge(diagnosis,on=["scenario_id","battery_type"],validate="one_to_one")
        diagnosis.to_csv(out/"fly_case_diagnosis.csv",index=False)
        for relative,digest in {**context.input_hashes,**manifest["code_hashes"]}.items():
            if sha(context.root/relative) != digest: raise ValueError(f"Input/code changed during OAT: {relative}")
        if sha(source_csv) != manifest["source_csv_hash"]: raise ValueError("Source Monte Carlo changed during OAT")
        manifest.update(status="COMPLETED_OAT_DEVELOPMENT",completed_at_utc=datetime.now(timezone.utc).isoformat(),
                        total_evaluations=len(scenarios)*len(batteries)*len(points),
                        output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != path.name})
    except Exception as error:
        manifest.update(status="FAILED",error=str(error));raise
    finally:
        path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--source-run",type=Path,required=True)
    p.add_argument("--fly-review",type=Path,required=True)
    a=p.parse_args();run(a.out,source_run=a.source_run,fly_review=a.fly_review)


if __name__ == "__main__": main()
