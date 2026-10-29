"""Build a traceable D5 case catalogue from saved OAT/MC/workflow evidence.

Streams the saved OAT CSV, never samples again or refits. Representatives are
the smallest scenario ID per declared category/battery/reference group, with
ties broken by the original manifest's grid order. Workflow fixtures have
assessment IDs, not invented D4 scenario IDs. Warnings and scoring-policy
effects are explicitly distinguished from verdict changes and shortfalls.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from src.available_energy import available_energy
from src.mission_record import load_snapshot
from src.physics_m100 import landing_energy_Wh
from src.safety_invariants import check_hard_rules, takeoff_mass_g
from src.sensitivity import sha, sweep_points
from src.uncertainty import INPUT_FIELDS, ROOT, load_context

TITLES = {
    "energy_underprediction": "Năng lượng cần có thể cao hơn dự đoán",
    "soc_overstatement": "Mức pin thực tế thấp hơn mức đã báo",
    "degraded_capacity": "Pin chai hơn trong dải tình huống được thử",
    "battery_identity_assumption": "Kết quả phụ thuộc giả định loại pin",
    "boundary_verdict_flip": "Quyết định thay đổi ở tình huống gần ngưỡng",
    "marginal_mapping_effect": "Cách chấm nhóm sát ngưỡng làm thay đổi cách tính điểm",
    "distance_extrapolation": "Quãng đường nằm ngoài phạm vi dữ liệu mô hình",
    "wind_extrapolation": "Gió nằm ngoài phạm vi đã đo trong dữ liệu",
    "temperature_clamp": "Nhiệt độ thấp hơn dải hiệu chỉnh hệ số pin",
    "hard_veto_with_high_margin": "Pin đủ nhưng một giới hạn an toàn chặn bay",
    "missing_or_stale_input": "Dữ liệu thiếu, không hợp lệ hoặc đánh giá đã cũ",
}
EVENTS = {
    "VERDICT_CHANGE": "Đổi quyết định khi tính lại",
    "RESERVE_SHORTFALL": "Có điểm thử thiếu dự trữ",
    "SCORING_POLICY_CHANGE": "Đổi cách chấm, quyết định giữ nguyên",
    "MODEL_SUPPORT_WARNING": "Cảnh báo phạm vi mô hình",
    "WORKFLOW_BLOCK": "Bị chặn trong quy trình giả lập",
}
CRITERIA = {
    "energy_underprediction": "Valid energy_error point; negative signed residual; baseline FLY; perturbed reserve_met=0",
    "soc_overstatement": "Valid soc_error point in primary range; negative offset; baseline FLY; perturbed reserve_met=0",
    "degraded_capacity": "Valid soh_domain point below original SoH; baseline FLY; verdict changes",
    "battery_identity_assumption": "Valid battery_assumption point with effective battery changed; verdict changes",
    "boundary_verdict_flip": "Valid changed verdict; original selected REF ratio within w of 0 or r_ref; w from protocol",
    "marginal_mapping_effect": "Valid zero soc_error point; original selected REF label=marginal; compare two binary mappings",
    "distance_extrapolation": "Valid zero soc_error point; distance outside support; CONDITIONAL; no VETO; energy meets FLY threshold",
    "wind_extrapolation": "Valid wind_domain point outside measured wind support; baseline wind inside support; no VETO",
    "temperature_clamp": "Valid temperature_domain point below calibration lower bound; baseline temperature at/above bound",
    "hard_veto_with_high_margin": "Valid point; baseline FLY; changed NO_FLY; VETO true; energy still meets reserve+uncertainty FLY threshold",
    "missing_or_stale_input": "Predefined saved missing/NaN/invalid/weather-expiry/mitigation/reassessment fixtures with a passing blocking check",
}


def describe_point(row):
    factor, value = row["factor"], row["point_value"]
    if factor == "battery_assumption":
        return f"Đổi giả định sang pin {value}"
    number = float(value)
    if factor in ("soc_error", "soh_error", "kappa_error"):
        name = {"soc_error":"Mức pin", "soh_error":"Sức khỏe pin", "kappa_error":"Hệ số pin κ"}[factor]
        if number == 0:
            return "Giữ nguyên đầu vào gốc"
        unit = "điểm phần trăm" if factor != "kappa_error" else "đơn vị hệ số"
        magnitude = abs(number)*100 if factor != "kappa_error" else abs(number)
        return f"{name} {'tăng' if number>0 else 'giảm'} {magnitude:g} {unit}"
    if factor == "energy_error":
        return f"Nhu cầu năng lượng {'tăng' if number<0 else 'giảm'} {abs(number):.4f} Wh theo sai số D2"
    if factor == "soh_domain":
        return f"Thử sức khỏe pin ở {number:.0%}"
    if factor in ("wind_domain", "wind_error"):
        return f"{'Thử gió ở' if factor=='wind_domain' else 'Thay đổi gió thêm'} {number:g} m/s"
    if factor == "temperature_domain":
        return f"Thử nhiệt độ {number:g}°C"
    if factor == "reserve_policy":
        return f"Thử mức dự trữ {number:.0%}"
    raise ValueError(f"Unknown point factor: {factor}")


def point_scope(row):
    kind = row["sweep_kind"]
    if kind == "input_error":
        return "Khoảng sai lệch chính" if row["primary_error_point"] else "Khoảng sai lệch rộng"
    return {"empirical_error":"Sai số từ các chuyến kiểm tra D2", "scenario_domain":"Thay đổi toàn dải giả định",
            "battery_assumption":"Thay giả định loại pin", "policy":"Thay chính sách dự trữ"}[kind]


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(clean(value), stream, ensure_ascii=False, indent=2, allow_nan=False)


def verify_file(path, expected):
    actual = sha(path)
    if actual != expected:
        raise ValueError(f"Saved input hash mismatch: {path}")
    return actual


def _number(value):
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.4f}"


class Selector:
    """Keep bounded representatives and distinct eligible IDs, independent of chunks."""
    def __init__(self, point_order):
        self.point_order = point_order
        self.best = {}
        self.observed = {}
        self.ids = {}

    def consider(self, frame, mask, category, reference=None):
        selected = frame.loc[mask]
        for battery, group in selected.groupby("battery_type", sort=False):
            key = (category, str(battery), reference)
            self.observed[key] = self.observed.get(key, 0) + len(group)
            self.ids.setdefault(key, set()).update(group.scenario_id.astype(int))
            lowest = int(group.scenario_id.min())
            candidates = group[group.scenario_id == lowest]
            for _, row in candidates.iterrows():
                order = self.point_order[(row.factor, str(row.point_id))]
                priority = (lowest, order)
                if key not in self.best or priority < self.best[key][0]:
                    self.best[key] = (priority, clean(row.to_dict()))


def scan_oat(path, metadata, scenarios, context, chunksize=100_000):
    order = {(p["factor"], str(p["point_id"])): i for i, p in enumerate(metadata["points"])}
    selector = Selector(order)
    width = context.d5["experiments"]["boundary_analysis"]["primary_w"]
    reserve_ref = context.d5["experiments"]["boundary_analysis"]["reference_reserve_ratio"]
    allowance = context.d3["energy_required"]["measured_error"]["p95_abs_residual_Wh"]
    wind_lo, wind_hi = context.d5["factors"]["wind_magnitude"]["measured_coverage_ms"]
    cold, _ = context.d3["available_energy"]["kappa_temperature"]["calibrated_range_c"]
    baseline_reserve = context.d5["inherited_baseline"]["decision_policy"]["reserve_ratio"]
    scanned, valid_count = 0, 0
    for block in pd.read_csv(path, chunksize=chunksize, dtype={"point_id": str, "point_value": str}):
        block["source_record_index"] = np.arange(scanned+1, scanned+len(block)+1)
        scanned += len(block)
        valid = block.status == "OK"
        if (block.loc[block.factor != "reserve_policy", "reserve_ratio"] != baseline_reserve).any():
            raise ValueError("Saved baseline reserve differs from current catalogue protocol")
        valid_count += int(valid.sum())
        if block.scenario_id.map(scenarios.stratum).isna().any():
            raise ValueError("OAT contains unknown scenario IDs")
        original_soh = block.scenario_id.map(scenarios.soh)
        original_wind = block.scenario_id.map(scenarios.wind_forecast_ms)
        original_temp = block.scenario_id.map(scenarios.ambient_temp_c)
        point = pd.to_numeric(block.point_value, errors="coerce")
        changed = block.baseline_verdict != block.reassessed_verdict
        shortfall = block.reserve_met == 0
        fly = block.baseline_verdict == "FLY"
        zero = (block.factor == "soc_error") & (point == 0)
        energy_fly = block.margin_ratio >= block.reserve_ratio + allowance/block.required_Wh
        masks = {
            "energy_underprediction": valid & fly & shortfall & (block.factor == "energy_error") & (point < 0),
            "soc_overstatement": valid & fly & shortfall & (block.factor == "soc_error") & (point < 0) & block.primary_error_point,
            "degraded_capacity": valid & fly & changed & (block.factor == "soh_domain") & (point < original_soh),
            "battery_identity_assumption": valid & changed & (block.factor == "battery_assumption") & (block.effective_battery != block.battery_type),
            "distance_extrapolation": valid & zero & block.distance_extrapolated & (block.reassessed_verdict == "CONDITIONAL") & ~block.veto & energy_fly,
            "wind_extrapolation": valid & (block.factor == "wind_domain") & block.wind_extrapolated & ~block.veto & original_wind.between(wind_lo, wind_hi),
            "temperature_clamp": valid & (block.factor == "temperature_domain") & (point < cold) & (original_temp >= cold),
            "hard_veto_with_high_margin": valid & fly & block.veto & (block.reassessed_verdict == "NO_FLY") & energy_fly,
        }
        for category, mask in masks.items():
            selector.consider(block, mask, category)
        for reference in ("ref1", "ref2"):
            ratio = block.scenario_id.map(scenarios[f"margin_ratio_{reference}"])
            boundary = (ratio.abs() <= width) | ((ratio-reserve_ref).abs() <= width)
            selector.consider(block, valid & changed & boundary, "boundary_verdict_flip", reference)
            marginal = block.scenario_id.map(scenarios[f"label_{reference}"]) == "marginal"
            selector.consider(block, valid & zero & marginal, "marginal_mapping_effect", reference)
        if scanned % 1_000_000 < len(block):
            print(f"Read {scanned:,}/{metadata['total_evaluations']:,} saved OAT rows", flush=True)
    if scanned != metadata["total_evaluations"]:
        raise ValueError("OAT row count differs from its manifest")
    return selector, dict(scanned_rows=scanned, valid_rows=valid_count, invalid_rows=scanned-valid_count)


def reconstruct_rules(context, inputs, required, saved_available=None):
    """Check a selected saved point only; never rerun the population or Monte Carlo."""
    report = check_hard_rules(**{k: inputs[k] for k in INPUT_FIELDS},
                              battery_type=inputs["battery_type"], profile=inputs["profile"], protocol=context.d3)
    checks = [asdict(c) for c in report.checks]
    if saved_available is not None:
        mass = takeoff_mass_g(inputs["payload_g"], inputs["battery_type"], inputs["profile"], context.d3["aircraft_profiles"])
        descent = context.d3["hard_rules"]["physics_derived"][0]["descent_rate_ms"]
        floor = landing_energy_Wh(inputs["altitude_m"], mass, inputs["battery_type"], descent_rate_ms=descent)
        for check in checks:
            if check["rule_id"] == "PH-1":
                check.update(status="VIOLATED" if saved_available < floor else "PASS",
                             detail=f"Saved available {saved_available:.12g} Wh vs landing floor {floor:.12g} Wh")
    return checks


def explain(category, row, before, after):
    point = row["point_value"]
    verdict = row["reassessed_verdict"]
    if category == "energy_underprediction":
        delta = after["e_required_Wh"]-before["e_required_Wh"]
        return (f"Nhu cầu tăng {delta:.4f} Wh khi áp một sai số dự đoán đã lưu từ D2; từ đủ dự trữ thành thiếu dự trữ.",
                "Phần dư = dự đoán − đo được; phần dư âm được trừ khỏi dự đoán nên nhu cầu tăng. Đây là phép thử kịch bản, không phải sự cố bay đã đo.")
    if category == "soc_overstatement":
        return (f"Chỉ giảm mức pin từ {before['soc']:.2%} xuống {after['soc']:.2%} đã làm thiếu dự trữ.",
                "Khoảng sai lệch SoC do nhóm giả định; chưa được xác nhận là sai số đo thực tế.")
    if category == "degraded_capacity":
        return (f"Giảm sức khỏe pin từ {before['soh']:.2%} xuống {after['soh']:.2%} làm quyết định đổi thành {verdict}.",
                "Đây là thay đổi tình trạng pin trong toàn dải thử; khác với sai số đo SoH ±2 điểm phần trăm.")
    if category == "battery_identity_assumption":
        return (f"Đổi giả định pin từ {before['battery_type']} sang {after['battery_type']} làm đổi kết quả.",
                "Đây là độ nhạy với giả định loại pin, không chứng minh người dùng đã lắp nhầm pin; nhãn tham chiếu D4 vẫn cố định theo giả định ban đầu.")
    if category == "boundary_verdict_flip":
        return (f"Kịch bản gần ngưỡng theo nhãn tham chiếu đã chọn. {describe_point(row)} làm đổi quyết định.",
                "Gần ngưỡng được xác định riêng theo REF-1/REF-2 gốc với w=0,05; việc đổi quyết định không đồng nghĩa đã xảy ra sự cố.")
    if category == "marginal_mapping_effect":
        return ("Giữ nguyên dữ liệu và quyết định; chỉ đổi cách xếp nhóm sát ngưỡng vào nhóm khả thi hay không khả thi khi chấm điểm.",
                "Đây là thay đổi cách chấm và mẫu số, không phải đầu vào hay quyết định của hệ thống thay đổi.")
    if category == "distance_extrapolation":
        return ("Pin đủ theo ngưỡng FLY, nhưng quãng đường ngoài dải dữ liệu khiến hệ thống giữ mức CONDITIONAL.",
                "Không thay đổi quãng đường trong phép quét này; đây là cảnh báo có sẵn ở kịch bản gốc, không phải một chuyển FLY→CONDITIONAL mới.")
    if category == "wind_extrapolation":
        return (f"Thử gió {after['wind_forecast_ms']:.4f} m/s, ngoài dải đã đo 2,81–6,67 m/s, cho kết quả {verdict}.",
                "Ngoài dải dữ liệu khác với vượt giới hạn gió DJI. D3 hiện không có luật tự hạ cấp chỉ vì ngoại suy gió; đây là giới hạn cần công bố.")
    if category == "temperature_clamp":
        return (f"Thử nhiệt độ {after['ambient_temp_c']:.2f}°C; hệ số pin được giữ ở giá trị biên lạnh κ={row['kappa']:.6f}.",
                "Dưới 4,5°C dùng giá trị tại 4,5°C, không kéo dài đa thức xuống nhiệt độ thấp hơn; ảnh hưởng nhiệt độ là giả định từ tài liệu.")
    return ("Dù năng lượng đủ cả mức dự trữ và khoản dự phòng sai số, một luật VETO vẫn chặn quyết định FLY.",
            "Đây là một ca chặn đúng theo quy tắc, không phải lỗi thuật toán. Ngoại lệ MTOW của hồ sơ CMU vẫn phải được ghi rõ.")


def oat_case(context, scenarios, category, battery, reference, row, source, mc):
    sid = int(row["scenario_id"])
    original = scenarios.loc[sid]
    before = {k: float(original[k]) for k in INPUT_FIELDS}
    before.update(battery_type=battery, profile="CMU_instrumented", reserve_factor=float(context.d5["inherited_baseline"]["decision_policy"]["reserve_ratio"]))
    before.update(e_required_Wh=row["required_Wh"]-row["delta_required_Wh"],
                  e_available_Wh=row["available_Wh"]-row["delta_available_Wh"],
                  margin_Wh=row["margin_Wh"]-row["delta_margin_Wh"])
    before["reserve_slack_Wh"] = before["e_available_Wh"]-(1+before["reserve_factor"])*before["e_required_Wh"]
    prediction = context.model.predict(before, context.d4)
    availability = available_energy(before["soc"], before["soh"], before["ambient_temp_c"],
                                    battery_type=battery, protocol=context.d3).value_Wh
    if not (math.isclose(before["e_required_Wh"],prediction,abs_tol=1e-8,rel_tol=1e-8) and
            math.isclose(before["e_available_Wh"],availability,abs_tol=1e-8,rel_tol=1e-8)):
        raise ValueError(f"Saved baseline differs from frozen D2/D3: {sid}/{battery}")
    after = {**before, "soc":row["soc"], "soh":row["soh"], "wind_forecast_ms":row["wind_ms"],
             "ambient_temp_c":row["temperature_c"], "battery_type":row["effective_battery"],
             "reserve_factor":row["reserve_ratio"], "e_required_Wh":row["required_Wh"],
             "e_available_Wh":row["available_Wh"], "margin_Wh":row["margin_Wh"],
             "reserve_slack_Wh":row["reserve_slack_Wh"], "kappa":row["kappa"]}
    for key, actual in (("margin_Wh", after["e_available_Wh"]-after["e_required_Wh"]),
                        ("reserve_slack_Wh", after["e_available_Wh"]-(1+after["reserve_factor"])*after["e_required_Wh"])):
        if not math.isclose(after[key], actual, abs_tol=1e-8, rel_tol=1e-8):
            raise ValueError(f"Inconsistent saved OAT energy: {sid}/{battery}/{key}")
    if bool(row["reserve_met"]) != (after["reserve_slack_Wh"] >= 0):
        raise ValueError("Saved reserve flag differs from saved energy values")
    checks = reconstruct_rules(context, after, after["e_required_Wh"], after["e_available_Wh"])
    forces_no_fly = any(c["severity"] == "VETO" and c["status"] == "VIOLATED" for c in checks)
    if forces_no_fly != row["veto"]:
        raise ValueError(f"Saved VETO differs from rule reconstruction: {sid}/{battery}")
    explanation, limitation = explain(category, row, before, after)
    if category == "hard_veto_with_high_margin":
        active = [c["rule_id"] for c in checks if c["severity"] == "VETO" and c["status"] == "VIOLATED"]
        explanation += f" Luật chặn: {', '.join(active)}. Gió trước/sau: {before['wind_forecast_ms']:.4f}/{after['wind_forecast_ms']:.4f} m/s."
    changed = row["baseline_verdict"] != row["reassessed_verdict"]
    shortfall = not bool(row["reserve_met"])
    event = ("SCORING_POLICY_CHANGE" if category == "marginal_mapping_effect" else
             "VERDICT_CHANGE" if changed else "RESERVE_SHORTFALL" if shortfall else "MODEL_SUPPORT_WARNING")
    policy = None
    if reference:
        label = original[f"label_{reference}"]
        policy = dict(reference_label=label, fixed_original_margin_ratio=original[f"margin_ratio_{reference}"],
                      reference_labels_recomputed=False, original_battery_assumption="TB47D")
        if category == "marginal_mapping_effect":
            policy.update(mapping_before="INFEASIBLE", mapping_after="FEASIBLE",
                          false_safe_contribution_before=int(row["baseline_verdict"] == "FLY"),
                          false_safe_contribution_after=0,
                          unnecessary_rejection_contribution_before=0,
                          unnecessary_rejection_contribution_after=int(row["baseline_verdict"] == "NO_FLY"))
    return dict(scenario_id=sid, assessment_id=None, category=category, battery_type=battery,
                source_kind="SAVED_OAT", event_kind=event, baseline_inputs=before, changed_inputs=after,
                perturbation_and_source=dict(factor=row["factor"], sweep_kind=row["sweep_kind"],
                                              point_id=row["point_id"], value=row["point_value"],
                                              unit=row["point_unit"], primary_error_point=row["primary_error_point"],
                                              description=describe_point(row), scope=point_scope(row)),
                reference_model=reference.upper().replace("REF", "REF-") if reference else "NOT_SCORED_AGAINST_REFERENCE",
                reference_details=policy, baseline_verdict=row["baseline_verdict"],
                changed_verdict_or_reserve_failure=dict(reassessed_verdict=row["reassessed_verdict"],
                                                        verdict_changed=changed, reserve_shortfall=shortfall,
                                                        workflow_blocked=None),
                margin_before_after=dict(margin_before_Wh=before["margin_Wh"], margin_after_Wh=after["margin_Wh"],
                                         reserve_slack_before_Wh=before["reserve_slack_Wh"], reserve_slack_after_Wh=after["reserve_slack_Wh"]),
                rule_results=dict(origin="Reconstructed for selected point using verified D3 and saved available energy",
                                  saved_veto=row["veto"], checks=checks),
                mitigation_if_valid=None, explanation=explanation, limitation=limitation,
                mc_context=mc.get((sid,battery)),
                source=dict(file=str(source.resolve()), record_index=row["source_record_index"],
                            locator={k:row[k] for k in ("scenario_id","battery_type","factor","point_id")}),
                diagnostic_only=True, operational_recommendation=False)


def workflow_cases(run):
    names = ["missing_soc", "nan_wind", "invalid_soc", "expired_weather", "missing_weather_window",
             "conditional_fake_mitigation", "preflight_degraded"]
    explanations = {
        "missing_soc": "Thiếu mức pin; hệ thống không đủ thông tin để cho FLY.",
        "nan_wind": "Giá trị gió NaN được chuẩn hóa thành dữ liệu thiếu và bị chặn.",
        "invalid_soc": "Mức pin lớn hơn 100% là đầu vào không hợp lệ và bị chặn.",
        "expired_weather": "Đến đúng thời điểm hết hiệu lực của dữ liệu thời tiết thì đánh giá bị chặn.",
        "missing_weather_window": "Không có thời điểm hết hiệu lực của thời tiết; hệ thống không tự điền thời hạn.",
        "conditional_fake_mitigation": "Chỉ điền một tên biện pháp tùy ý không làm CONDITIONAL được duyệt.",
        "preflight_degraded": "Đánh giá lại xấu hơn đánh giá FLY đã được duyệt trước đó; quyền duyệt cũ không chuyển sang bản mới.",
    }
    evidence = json.loads((run/"workflow_checks.json").read_text(encoding="utf-8"))
    result = []
    for name in names:
        saved = load_snapshot(run,name).data
        current = saved["result"]
        previous = load_snapshot(run,saved["previous_assessment_id"]).data if saved.get("previous_assessment_id") else None
        check_name = f"blocks_{name}"
        check = next(c for c in evidence if c["check"] == check_name)
        if not check["passed"]:
            raise ValueError(f"Workflow evidence did not pass: {check_name}")
        before = previous["inputs"] if previous else saved["inputs"]
        before_decision = previous["result"]["decision"] if previous else current["decision"]
        after_decision = current["decision"]
        mitigation = None
        if name == "conditional_fake_mitigation":
            valid = load_snapshot(run,"conditional_mitigated").data
            if valid["result"]["mitigation_validated"]:
                mitigation = dict(source_assessment_id=valid["assessment_id"], action=valid["mitigation"],
                                  changed_inputs=valid["inputs"], resulting_verdict=valid["result"]["verdict"],
                                  validated_in_saved_workflow=True, counterfactual_reference_validation=False)
        result.append(dict(scenario_id=None, assessment_id=name, category="missing_or_stale_input",
                    battery_type=saved["inputs"]["battery_type"], source_kind="SAVED_SYNTHETIC_WORKFLOW_FIXTURE",
                    event_kind="WORKFLOW_BLOCK", baseline_inputs=before, changed_inputs=saved["inputs"],
                    perturbation_and_source=dict(fixture=name, weather=saved["weather"],
                                                  assessed_at=saved["assessed_at"], previous_assessment_id=saved.get("previous_assessment_id")),
                    reference_model="NOT_APPLICABLE_WORKFLOW_CHECK", reference_details=None,
                    baseline_verdict=previous["result"]["verdict"] if previous else None,
                    changed_verdict_or_reserve_failure=dict(reassessed_verdict=current["verdict"],
                                                            verdict_changed=(previous["result"]["verdict"] != current["verdict"]) if previous else None,
                                                            reserve_shortfall=None, workflow_blocked=True),
                    margin_before_after=dict(margin_before_Wh=before_decision.get("margin_Wh"), margin_after_Wh=after_decision.get("margin_Wh"),
                                             reserve_slack_before_Wh=None, reserve_slack_after_Wh=None),
                    rule_results=dict(origin="Stored assessment and completed workflow check", checks=after_decision.get("hard_rule_report",{}),
                                      workflow_check=check, weather_issues=current["weather_issues"]),
                    mitigation_if_valid=mitigation, explanation=explanations[name],
                    limitation="Đây là ca thử phần mềm có đầu vào/thời tiết giả lập; không có ID D4 và không phải chuyến bay thật. Khi không có bản trước, không suy diễn quyết định ban đầu.",
                    mc_context=None, source=dict(file=str((run/"snapshots"/f"{name}.json").resolve()), record_index=None,
                                                 locator=dict(assessment_id=name, workflow_check=check_name)),
                    diagnostic_only=False, operational_recommendation=False))
    return result


def _human_rows(cases):
    result = []
    for case in cases:
        event = case["changed_verdict_or_reserve_failure"]
        perturb = case["perturbation_and_source"]
        result.append(dict(Ma_ca=case["case_id"], Nhom=TITLES[case["category"]],
                           ID_D4=case["scenario_id"], Ma_ca_thu=case["assessment_id"], Loai_pin=case["battery_type"],
                           Loai_ket_qua=EVENTS[case["event_kind"]],
                           Diem_thay_doi=perturb.get("description",case["explanation"]),
                           Pham_vi_thu=perturb.get("scope","Ca thử quy trình giả lập"),
                           Quyet_dinh_truoc=case["baseline_verdict"], Quyet_dinh_sau=event["reassessed_verdict"],
                           Co_doi_quyet_dinh=event["verdict_changed"], Thieu_du_tru_sau=event["reserve_shortfall"],
                           Bi_chan_quy_trinh=event["workflow_blocked"],
                           Du_so_voi_du_tru_truoc_Wh=case["margin_before_after"]["reserve_slack_before_Wh"],
                           Du_so_voi_du_tru_sau_Wh=case["margin_before_after"]["reserve_slack_after_Wh"],
                           Tham_chieu=case["reference_model"] if case["reference_model"].startswith("REF-") else None,
                           Dien_giai=case["explanation"], Gioi_han=case["limitation"],
                           File_nguon=case["source"]["file"], Ban_ghi_nguon=case["source"]["record_index"]))
    return result


def render_report(out, cases, coverage, statistics):
    lines = ["# Các tình huống D5 cần chú ý", "",
             f"Bảng này tổng hợp **{len(cases)} ví dụ**, thuộc **{coverage.category.nunique()} nhóm** đã quy định trong D5. Đây là ví dụ đại diện, không phải tổng số kịch bản có vấn đề. Nguồn là các kết quả đã lưu; không chạy thêm Monte Carlo hay huấn luyện lại mô hình.", "",
             "Mỗi ID D4 là một kịch bản gốc. Nhiều dòng cùng ID có thể mô tả loại pin, điểm thử hoặc cách tham chiếu khác nhau. Các ca thử thời tiết/dữ liệu thiếu có mã riêng, không gán ID D4 giả.", "",
             "## Đọc kết quả", "",
             "- Đổi quyết định: so sánh kết luận gốc và kết luận sau khi tính lại một điểm thử.",
             "- Thiếu dự trữ: pin không đủ nhu cầu cộng thêm mức dự trữ. Đây không tự động là pin cạn hay sự cố thực tế.",
             "- Cảnh báo phạm vi mô hình: có thể vẫn giữ nguyên quyết định, nhưng dữ liệu thử nằm ngoài phạm vi đã đo.",
             "- Đổi cách chấm: dữ liệu và quyết định không đổi; chỉ cách xếp nhãn sát ngưỡng khi tính điểm thay đổi.",
             "- Bị chặn trong quy trình: kiểm tra phần mềm xử lý đúng dữ liệu thiếu/hết hạn hoặc điều kiện duyệt. Chặn đúng không phải lỗi thuật toán.", "",
             "Các kết quả CMU_instrumented dùng chế độ phân tích có ghi nhận ngoại lệ HR-3. Cấu hình này vượt MTOW đã công bố; nhãn FLY không xác nhận quyền bay thực tế. Dải tải 0–500 g không thay thế giới hạn MTOW.", "",
             "REF-1/REF-2 là hai cách gán nhãn tham chiếu mô phỏng đã lưu trong D4. Các nhãn này giữ nguyên giả định pin TB47D ban đầu, kể cả khi xem ứng viên TB48D; chưa tái tính nhãn theo giả định đã đổi.", "",
             "## Cách chọn ví dụ", "",
             "Chọn ID nhỏ nhất thỏa điều kiện trong từng nhóm và từng loại pin; nếu cần tham chiếu thì giữ riêng REF-1/REF-2. Nếu cùng ID có nhiều điểm phù hợp, chọn điểm xuất hiện trước trong lưới đã khai. Không chọn ví dụ vì có tỷ lệ thiếu lớn nhất hoặc đẹp nhất.",
             f"Đã đọc {statistics['scanned_rows']:,} bản ghi OAT đã lưu; {statistics['invalid_rows']:,} điểm không hợp lệ được loại khỏi việc chọn ví dụ. Điều kiện chọn và số ca đủ điều kiện của từng nhóm có trong `category_coverage.csv`.", ""]
    for category in TITLES:
        selected = [c for c in cases if c["category"] == category]
        lines += [f"## {TITLES[category]}", ""]
        if not selected:
            lines += ["Không quan sát được trường hợp thỏa điều kiện chọn trong kết quả hiện có; không tạo ví dụ thay thế.", ""]
            continue
        for c in selected:
            label = f"ID {c['scenario_id']}" if c["scenario_id"] is not None else f"ca thử `{c['assessment_id']}`"
            before = c["baseline_verdict"] or "không có bản trước"
            after = c["changed_verdict_or_reserve_failure"]["reassessed_verdict"]
            ref = f" · {c['reference_model']}" if c["reference_model"].startswith("REF-") else ""
            lines += [f"**{c['case_id']} — {label}, {c['battery_type']}{ref}**", "",
                      f"{before} → {after}. {c['explanation']}", ""]
            perturb = c["perturbation_and_source"]
            if "description" in perturb:
                lines += [f"Điểm thử: {perturb['description']}. Phạm vi: {perturb['scope']}.", ""]
            m = c["margin_before_after"]
            if m["reserve_slack_after_Wh"] is not None:
                lines += [f"Năng lượng dư so với mức cần **kèm dự trữ**: {_number(m['reserve_slack_before_Wh'])} → {_number(m['reserve_slack_after_Wh'])} Wh. Số âm nghĩa là thiếu mức dự trữ.", ""]
            lines += [f"Giới hạn cách hiểu: {c['limitation']}", "",
                      f"Nguồn: `{Path(c['source']['file']).name}`; {json.dumps(c['source']['locator'],ensure_ascii=False)}.", ""]
    lines += ["## File để xem tiếp", "",
              "- `failure_cases_explained.csv`: bảng giải thích tiếng Việt; mở bằng Excel và lọc theo ID/nhóm/pin.",
              "- `failure_catalogue.json` và `failure_catalogue.csv`: đủ đầu vào trước/sau, năng lượng, kết quả luật, tham chiếu, nguồn từng bản ghi.",
              "- `category_coverage.csv`: điều kiện chọn, số ví dụ và nhóm không quan sát được nếu có.",
              "- `catalogue_manifest.json`: hash nguồn/kết quả, phiên bản, số dòng đã đọc và các giới hạn.", "",
              "Đây là danh mục phát triển. Nhãn tham chiếu tính lại theo giả định thay đổi và đánh giá đầy đủ bộ đề xuất điều chỉnh vẫn cần hoàn tất; kiểm tra chéo cuối còn PENDING. Danh mục không xác nhận an toàn bay ngoài thực tế.", ""]
    (out/"failure_catalogue.md").write_text("\n".join(lines),encoding="utf-8")


def build(out, *, oat_run, replay_run, fly_review, root=ROOT, chunksize=100_000):
    out, oat_run, replay_run, fly_review = map(Path, (out,oat_run,replay_run,fly_review))
    if out.exists():
        raise FileExistsError("Choose a new output directory")
    context = load_context(root)
    if list(TITLES) != context.d5["failure_catalogue"]["categories"]:
        raise ValueError("Catalogue categories differ from the protocol; review selection rules")
    source_hashes = {}
    meta = json.loads((oat_run/"input_manifest.json").read_text(encoding="utf-8"))
    if meta["status"] != "COMPLETED_OAT_DEVELOPMENT" or meta["diagnostic_profile"] != "CMU_instrumented":
        raise ValueError("Expected a completed CMU diagnostic OAT run")
    if meta["diagnostic_profile"] != context.d5["inherited_baseline"]["aircraft_profile"]["primary_diagnostic"]:
        raise ValueError("Saved aircraft profile differs from current catalogue protocol")
    if meta["points"] != [asdict(p) for p in sweep_points(context)]:
        raise ValueError("Saved grid differs from the protocol; review before selecting cases")
    for relative, expected in meta["input_hashes"].items():
        if relative != "configs/d5_protocol.yaml":
            verify_file(context.root/relative,expected)
    for name in ("input_manifest.json", "one_factor_evaluations.csv.gz"):
        path = oat_run/name
        source_hashes[str(path.resolve())] = verify_file(path,meta["output_hashes"][name]) if name in meta["output_hashes"] else sha(path)
    replay_meta = json.loads((replay_run/"validation_manifest.json").read_text(encoding="utf-8"))
    if replay_meta["status"] != "COMPLETED_REPLAY_WORKFLOW_DEVELOPMENT":
        raise ValueError("Expected completed workflow evidence")
    for relative, expected in replay_meta["outputs"].items():
        path=replay_run/relative
        source_hashes[str(path.resolve())] = verify_file(path,expected)
    source_hashes[str((replay_run/"validation_manifest.json").resolve())] = sha(replay_run/"validation_manifest.json")
    review = json.loads((fly_review/"analysis_manifest.json").read_text(encoding="utf-8"))
    if review["source_input_manifest_hash"] != meta["source_manifest_hash"]:
        raise ValueError("MC review and OAT refer to different source runs")
    review_path=fly_review/"fly_reserve_failures.csv"
    source_hashes[str(review_path.resolve())]=verify_file(review_path,review["output_hashes"][review_path.name])
    source_hashes[str((fly_review/"analysis_manifest.json").resolve())]=sha(fly_review/"analysis_manifest.json")
    mc_frame=pd.read_csv(review_path)
    primary=mc_frame[mc_frame.assumption_config_id=="PRIMARY_INDEPENDENT"]
    if primary.duplicated(["scenario_id","battery_type"]).any():
        raise ValueError("Duplicate primary MC review cases")
    mc={(int(r.scenario_id),r.battery_type):dict(config_id="PRIMARY_INDEPENDENT",failure_fraction_min=r.failure_fraction_min,
                                               failure_fraction_max=r.failure_fraction_max,seed_count=int(r.seed_count),
                                               note="MC summary only; not the probability of this deterministic point")
        for r in primary.itertuples()}
    scenarios=pd.read_csv(context.root/"reports/d4_scenarios_labelled.csv",low_memory=False).set_index("scenario_id")
    if not scenarios.index.is_unique:
        raise ValueError("Duplicate source scenario IDs")
    path=oat_run/"one_factor_evaluations.csv.gz"
    stat=path.stat()
    print("Verified saved source hashes. Selecting cases from the complete OAT output...",flush=True)
    selector,statistics=scan_oat(path,meta,scenarios,context,chunksize)
    if (path.stat().st_size,path.stat().st_mtime_ns)!=(stat.st_size,stat.st_mtime_ns):
        raise ValueError("OAT file changed while reading")
    cases,coverage=[],[]
    for category in TITLES:
        if category=="missing_or_stale_input":
            continue
        for battery in meta["batteries"]:
            for reference in (("ref1","ref2") if category in ("boundary_verdict_flip","marginal_mapping_effect") else (None,)):
                key=(category,battery,reference)
                found=selector.best.get(key)
                coverage.append(dict(category=category,battery_type=battery,reference_model=reference,
                                     status="OBSERVED" if found else "NOT_OBSERVED",selected_case_count=int(found is not None),
                                     eligible_evaluations=selector.observed.get(key,0),eligible_scenarios=len(selector.ids.get(key,())),
                                     criterion=CRITERIA[category],
                                     selection="Smallest eligible scenario_id, then original point order; per battery/reference"))
                if found:
                    cases.append(oat_case(context,scenarios,category,battery,reference,found[1],path,mc))
    fixtures=workflow_cases(replay_run)
    cases.extend(fixtures)
    coverage.append(dict(category="missing_or_stale_input",battery_type="TB47D",reference_model=None,status="OBSERVED",
                         selected_case_count=len(fixtures),eligible_evaluations=None,eligible_scenarios=None,
                         criterion=CRITERIA["missing_or_stale_input"],
                         selection="Predefined saved workflow fixtures; assessment IDs, no D4 ID"))
    for i,case in enumerate(cases,1):
        case["case_id"]=f"FC-{i:03d}"
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/"failure_catalogue.json",cases)
    machine=pd.DataFrame(cases)
    machine["scenario_id"]=machine.scenario_id.astype("Int64")
    for column in machine:
        if machine[column].map(lambda x:isinstance(x,(dict,list))).any():
            machine[column]=machine[column].map(lambda x:json.dumps(clean(x),ensure_ascii=False,allow_nan=False) if isinstance(x,(dict,list)) else x)
    machine.to_csv(out/"failure_catalogue.csv",index=False,encoding="utf-8-sig")
    human=pd.DataFrame(_human_rows(cases))
    human["ID_D4"]=human.ID_D4.astype("Int64")
    human.to_csv(out/"failure_cases_explained.csv",index=False,encoding="utf-8-sig")
    coverage=pd.DataFrame(coverage)
    coverage.to_csv(out/"category_coverage.csv",index=False,encoding="utf-8-sig")
    render_report(out,cases,coverage,statistics)
    shutil.copyfile(__file__,out/"catalogue_source.py")
    shutil.copyfile(context.root/"configs/d5_protocol.yaml",out/"protocol_snapshot.yaml")
    manifest=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),status="COMPLETED_FAILURE_CATALOGUE_DEVELOPMENT",
                  final_d5_complete=False,cross_check_status="PENDING",protocol_version=context.d5["meta"]["version"],
                  oat_protocol_version=meta["protocol_version"],source_hashes=source_hashes,
                  current_protocol_sha256=sha(context.root/"configs/d5_protocol.yaml"),code_sha256=sha(__file__),
                  case_count=len(cases),category_count=len(TITLES),observed_categories=int(coverage[coverage.status=="OBSERVED"].category.nunique()),
                  coverage=clean(coverage.to_dict("records")),statistics=statistics,
                  selection_rules="Explicit masks in scan_oat; minimum ID per category/battery/ref, ties by saved point order; predefined workflow fixtures",
                  selection_criteria=CRITERIA,
                  limitations=["CMU diagnostic profile with HR-3 record-only; not operational approval",
                               "Fixed D4 reference labels; matched-reference secondary pending",
                               "Warnings/scoring effects are not observed flight failures",
                               "MC fractions kept separate from deterministic grid points",
                               "Full counterfactual evaluation and final cross-check pending"],
                  outputs={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    write_json(out/"catalogue_manifest.json",manifest)
    print(f"Saved {len(cases)} cases; {manifest['observed_categories']}/{len(TITLES)} categories observed. Output: {out}",flush=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oat-run",type=Path,required=True)
    parser.add_argument("--replay-run",type=Path,required=True)
    parser.add_argument("--fly-review",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    build(args.out,oat_run=args.oat_run,replay_run=args.replay_run,fly_review=args.fly_review)


if __name__=="__main__":
    main()
