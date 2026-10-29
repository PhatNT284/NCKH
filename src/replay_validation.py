"""Create a new development run demonstrating D5 snapshots/replay/workflow.

python -m src.replay_validation --out reports/d5/replay_workflow_dev_01
All weather timestamps here are explicit synthetic test fixtures, not observed
weather or an operational forecast-validity policy. Does not rerun Monte Carlo.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

from src import mission_record as mr

AT = "2026-10-26T01:00:00+00:00"
LATER = "2026-10-26T01:03:00+00:00"
WEATHER = dict(observed_at="2026-10-26T00:55:00+00:00",
               valid_until="2026-10-26T01:30:00+00:00", source="SYNTHETIC_TEST_FIXTURE")
INPUTS = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50, distance_2d_m=472,
              wind_forecast_ms=3, ambient_temp_c=15, soc=.7, soh=.95,
              battery_type="TB47D", profile="M100_stock", reserve_factor=.2)


def _spec(name, **changes):
    return dict(assessment_id=name, mission_id=f"mission_{name}", assessed_at=AT,
                inputs={**INPUTS, **changes}, weather=deepcopy(WEATHER),
                provenance=dict(source_kind="SYNTHETIC_WORKFLOW_FIXTURE", actual_flight=False))


def _csv(path, rows):
    with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()} for row in rows)


def validate(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    artifact = mr.create_artifacts(out)
    print("Archived source, frozen model/scaler and D2-D5 configurations.", flush=True)
    specs = [_spec("stock_fly"), _spec("stock_launch"), _spec("stock_changes"),
             _spec("conditional", soc=.235), _spec("reserve_shortfall", soc=.2),
             _spec("wind_veto", wind_forecast_ms=12, soc=1),
             _spec("mass_veto", payload_g=1500, soc=1),
             _spec("missing_soc", soc=None), _spec("nan_soc", soc=float("nan")),
             _spec("nan_wind", wind_forecast_ms=float("nan")), _spec("missing_altitude", altitude_m=None),
             _spec("invalid_soc", soc=1.5), _spec("invalid_battery", battery_type="UNKNOWN"),
             _spec("cmu_diagnostic", profile="CMU_instrumented"),
             _spec("expired_weather"), _spec("missing_weather_window"), _spec("future_weather")]
    next(s for s in specs if s["assessment_id"] == "expired_weather")["weather"]["valid_until"] = AT
    next(s for s in specs if s["assessment_id"] == "missing_weather_window")["weather"].pop("valid_until")
    next(s for s in specs if s["assessment_id"] == "future_weather")["weather"]["observed_at"] = LATER
    base_prediction = mr._evaluate({**_spec("temporary"), "artifact_id": artifact})["prediction_Wh"]
    boundary_soc = (1.2 * base_prediction) / (99.9 * .95 * .9954)
    specs.append(_spec("reserve_boundary", soc=boundary_soc))
    # Preserve three complete rows from the hash-verified D4 synthetic dataset.
    source = mr.ROOT / "reports/d4_scenarios_labelled.csv"
    wanted = {1: "TB47D", 2681: "TB47D", 4757: "TB48D"}
    with source.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            sid = int(row["scenario_id"])
            if sid in wanted:
                item = _spec(f"d4_{sid}_{wanted[sid]}", **{key: float(row[key]) for key in mr.NUMERIC_INPUTS},
                             battery_type=wanted[sid], profile="CMU_instrumented")
                item["source_row"] = row
                item["provenance"] = dict(source_kind="FROZEN_D4_SYNTHETIC_SCENARIO", scenario_id=sid,
                                          source_file="reports/d4_scenarios_labelled.csv",
                                          source_sha256=mr.file_digest(source), actual_flight=False,
                                          weather_times="SYNTHETIC_TEST_FIXTURE")
                specs.append(item)
    mr.save_assessments(out, artifact, specs)
    checks = []
    def check(name, passed, detail=""):
        checks.append(dict(check=name, passed=bool(passed), detail=detail))
    def blocked(name, assessment_id, action="APPROVE", at=LATER, **kw):
        try:
            mr.workflow_action(out, assessment_id, action, at=at, actor_role="REVIEWER", **kw)
        except mr.RecordError as exc:
            check(name, True, str(exc))
        else:
            check(name, False, "Unexpectedly permitted")
    initial_hashes = {s["assessment_id"]: mr.load_snapshot(out, s["assessment_id"]).sha256 for s in specs}
    blocked("start_requires_human_approval", "stock_launch", action="START")
    mr.workflow_action(out, "stock_launch", "APPROVE", at=LATER, actor_role="REVIEWER")
    mr.workflow_action(out, "stock_launch", "START", at=LATER)
    check("fresh_stock_fly_can_advance_in_research_workflow",
          mr.workflow_status(out, "stock_launch", at=LATER)["in_flight"])
    mr.workflow_action(out, "stock_fly", "APPROVE", at="2026-10-26T01:01:00+00:00", actor_role="REVIEWER")
    degraded = _spec("preflight_degraded", soc=.235)
    degraded.update(mission_id="mission_stock_fly", assessed_at="2026-10-26T01:02:00+00:00",
                    previous_assessment_id="stock_fly")
    mitigated = _spec("conditional_mitigated", soc=.24)
    mitigated.update(mission_id="mission_conditional", assessed_at="2026-10-26T01:02:00+00:00",
                     previous_assessment_id="conditional", mitigation=dict(id="M1", approved_by_role="REVIEWER",
                                                                          approved_at="2026-10-26T01:01:00+00:00"))
    fake = deepcopy(mitigated)
    fake["assessment_id"] = "conditional_fake_mitigation"
    fake["mitigation"]["id"] = "ARBITRARY_TEXT"
    mr.save_assessments(out, artifact, [degraded, mitigated, fake])
    specs += [degraded, mitigated, fake]
    for case in ("conditional", "conditional_fake_mitigation", "wind_veto", "mass_veto",
                 "missing_soc", "nan_soc", "nan_wind", "missing_altitude", "invalid_soc",
                 "invalid_battery", "expired_weather", "missing_weather_window", "future_weather",
                 "cmu_diagnostic", "preflight_degraded"):
        blocked(f"blocks_{case}", case)
    check("new_reassessment_requires_new_review",
          not mr.workflow_status(out, "preflight_degraded", at=LATER)["approved"])
    check("prior_approved_assessment_becomes_stale",
          mr.workflow_status(out, "stock_fly", at=LATER)["assessment_status"] == "STALE")
    mr.workflow_action(out, "conditional_mitigated", "APPROVE", at=LATER, actor_role="REVIEWER")
    check("validated_mitigation_and_reassessment_can_be_reviewed",
          mr.workflow_status(out, "conditional_mitigated", at=LATER)["may_proceed"])
    blocked("weather_expiry_at_exact_boundary_blocks_previously_approved_start", "conditional_mitigated",
            action="START", at=WEATHER["valid_until"])
    for key, value in (("soc", .6), ("soh", .8), ("payload_g", 500), ("distance_2d_m", 500),
                       ("altitude_m", 75), ("speed_commanded_ms", 10), ("wind_forecast_ms", 4),
                       ("ambient_temp_c", 14), ("battery_type", "TB48D"),
                       ("profile", "CMU_instrumented"), ("reserve_factor", .3)):
        status = mr.workflow_status(out, "stock_changes", at=LATER, current_inputs={key: value})
        check(f"change_{key}_marks_stale", f"INPUT_CHANGED:{key}" in status["stale_reasons"])
    changed_weather = {**WEATHER, "valid_until": "2026-10-26T01:40:00+00:00"}
    check("weather_validity_update_marks_stale", "WEATHER_CHANGED" in
          mr.workflow_status(out, "stock_changes", at=LATER, current_weather=changed_weather)["stale_reasons"])
    with tempfile.TemporaryDirectory(prefix="d5-live-config-") as tmp:
        fake_live = Path(tmp) / "source"
        shutil.copytree(out / "artifacts" / artifact, fake_live)
        config = fake_live / "configs/d3_protocol.yaml"
        config.write_text(config.read_text(encoding="utf-8") + "\n# simulated later update\n", encoding="utf-8")
        state = mr.workflow_status(out, "stock_changes", at=LATER, root=fake_live)
        check("live_config_change_marks_stale", "ARTIFACT_CHANGED:configs/d3_protocol.yaml" in state["stale_reasons"])
        check("live_config_change_does_not_change_historical_replay", mr.replay(out, ["stock_changes"])[0]["all_outputs_match"])
    check("unknown_outcome_is_independent_of_no_fly",
          mr.workflow_status(out, "wind_veto", at=LATER)["observed_outcome"]["outcome"] == "UNKNOWN")
    mr.record_outcome(out, "wind_veto", "NOT_FLOWN", at=LATER, note="Cancelled in synthetic workflow",
                      evidence_source="SYNTHETIC_TEST_FIXTURE")
    check("recording_outcome_preserves_assessment", mr.load_snapshot(out, "wind_veto").sha256 == initial_hashes["wind_veto"])
    check("all_initial_snapshots_unchanged_after_workflow_and_config_update",
          all(mr.load_snapshot(out, key).sha256 == value for key, value in initial_hashes.items()))
    print(f"Saved {len(specs)} immutable assessments; replaying archived calculations...", flush=True)
    replay_rows = mr.replay(out, [s["assessment_id"] for s in specs])
    check("all_four_verdicts_covered", {r["expected_verdict"] for r in replay_rows} == set(mr.VERDICT_RANK))
    check("every_saved_record_replays_exact_verdict", all(r["exact_verdict_match"] for r in replay_rows))
    check("every_saved_record_replays_numerical_outputs", all(r["all_outputs_match"] for r in replay_rows))
    cases = []
    for item in specs:
        record = mr.load_snapshot(out, item["assessment_id"]).data
        result = record["result"]
        cases.append(dict(assessment_id=record["assessment_id"], mission_id=record["mission_id"],
                          source_kind=record["provenance"]["source_kind"], profile=record["inputs"]["profile"],
                          verdict=result["verdict"], diagnostic_only=result["diagnostic_only"],
                          prediction_Wh=result["prediction_Wh"], review_eligible=result["review_eligible"],
                          mitigation_validated=result["mitigation_validated"],
                          weather_issues=result["weather_issues"],
                          nonfinite_normalized=record["normalization_nonfinite_to_null"]))
    _csv(out / "replay_results.csv", replay_rows)
    _csv(out / "workflow_checks.csv", checks)
    _csv(out / "assessment_summary.csv", cases)
    mr._write_new(out / "replay_results.json", replay_rows)
    mr._write_new(out / "workflow_checks.json", checks)
    passed = sum(c["passed"] for c in checks)
    maximum = max(r["max_absolute_difference"] for r in replay_rows)
    lines = ["# Kiểm tra lưu và chạy lại quyết định D5", "",
             "Đây là lần kiểm tra phát triển. Thời tiết và thời điểm trong các ca thử là giả lập; không phải dữ liệu thời tiết thực tế.", "",
             f"- Đã lưu {len(specs)} bản đánh giá, bao gồm ba kịch bản D4 đã đối chiếu hash: 1, 2681 và 4757.",
             f"- {sum(r['exact_verdict_match'] for r in replay_rows)}/{len(replay_rows)} bản chạy lại cho đúng kết luận ban đầu.",
             f"- {sum(r['all_outputs_match'] for r in replay_rows)}/{len(replay_rows)} bản khớp đầy đủ đầu ra; chênh lệch số lớn nhất: {maximum:.12g}.",
             f"- {passed}/{len(checks)} kiểm tra quy trình đạt.", "",
             "## Cách đọc", "",
             "- `snapshots/`: mỗi file lưu đầu vào, đơn vị, thời tiết, kết quả luật, năng lượng, kết luận và mã bản cấu hình/mô hình.",
             "- `artifacts/`: bản mã nguồn, cấu hình D2–D5, mô hình đã chốt và bộ chuẩn hóa. Chạy lại sử dụng bản này trong tiến trình riêng.",
             "- `workflow_events/`: các sự kiện duyệt, bắt đầu, hết hạn và ghi kết cục; chỉ tạo sự kiện mới, không sửa bản đánh giá cũ.",
             "- `assessment_summary.csv`: xem trước các trường hợp; `replay_results.csv`: đối chiếu từng bản đã lưu.",
             "- `workflow_checks.csv`: từng điều kiện đã kiểm tra và lý do chặn.", "",
             "## Phạm vi MTOW", "",
             "Các ca CMU_instrumented kế thừa cấu hình phân tích D4: HR-3 ghi nhận vượt giới hạn khối lượng, không chặn phép phân tích. Nhãn FLY ở đây là kết quả trong chế độ phân tích, không phải quyền cho bay thực tế. Bộ kiểm tra mới không cho duyệt các ca CMU này để tiến hành nhiệm vụ. Các phép duyệt mẫu dùng riêng M100_stock và vẫn áp HR-3 theo cấu hình đó.", "",
             "Dải tải 0–500 g là phạm vi dữ liệu mô hình, không thay thế giới hạn khối lượng cất cánh. Mô hình năng lượng học từ CMU chưa được xác nhận riêng cho M100 nguyên bản; các ca M100_stock ở đây chỉ kiểm logic phần mềm.", "",
             "## Thời tiết và chạy lại", "",
             "Mỗi ca khai rõ thời điểm dữ liệu được ghi và thời điểm hết hiệu lực. Đến đúng thời điểm hết hạn thì bản đánh giá cũ bị chặn; thiếu thời hạn cũng không cho FLY. Không tự đặt thời hạn vận hành 30 phút hay lấy thời tiết trực tuyến.", "",
             "Chạy lại lịch sử dùng thời điểm đã lưu, kể cả khi hôm nay thời tiết đó đã hết hạn. Duyệt một nhiệm vụ dùng thời điểm hiện tại do người gọi cung cấp và kiểm tra hạn lại. Hai thao tác có mục đích khác nhau.", "",
             "Nếu thiếu mã nguồn/mô hình/cấu hình đã lưu, checksum thay đổi hoặc phiên bản Python/thư viện không phù hợp, chương trình báo không thể chạy lại. Đây là cơ chế chống sửa nhầm và ghi đè qua API; không phải kho lưu trữ WORM hay chữ ký chống sửa đổi ác ý.", "",
             "## Chưa phải nghiệm thu D5", "",
             "Quy trình vẫn là bản nháp, chưa có kiểm tra chéo cuối. Danh mục ca thất bại đầy đủ, nhãn tham chiếu tính lại theo giả định thay đổi và đánh giá đầy đủ các đề xuất điều chỉnh còn cần hoàn tất. Không chạy lại Monte Carlo trong bước này.", ""]
    (out / "replay_report.md").write_text("\n".join(lines), encoding="utf-8")
    files = [p for p in out.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    manifest = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), artifact_id=artifact,
                    status="COMPLETED_REPLAY_WORKFLOW_DEVELOPMENT" if passed == len(checks) else "FAILED",
                    final_d5_complete=False, cross_check_status="PENDING", assessment_count=len(specs),
                    replay_matches=sum(r["all_outputs_match"] for r in replay_rows),
                    workflow_checks_passed=passed, workflow_checks_total=len(checks),
                    max_absolute_difference=maximum, weather_policy="EXPLICIT_SYNTHETIC_VALID_UNTIL_NO_OPERATIONAL_TTL",
                    outputs={p.relative_to(out).as_posix(): mr.file_digest(p) for p in sorted(files)})
    mr._write_new(out / "validation_manifest.json", manifest)
    print(f"Replay: {manifest['replay_matches']}/{len(specs)} matched; maximum difference {maximum:g}.", flush=True)
    print(f"Workflow checks: {passed}/{len(checks)} passed. Saved to {out}", flush=True)
    return passed == len(checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output already exists; use a new directory")
    try:
        succeeded = validate(args.out)
    except Exception as exc:
        if args.out.is_dir() and not (args.out / "run_status.json").exists():
            mr._write_new(args.out / "run_status.json",
                          dict(status="FAILED", error_type=type(exc).__name__, error=str(exc),
                               final_d5_complete=False, created_at_utc=datetime.now(timezone.utc).isoformat()))
        raise
    raise SystemExit(0 if succeeded else 1)


if __name__ == "__main__":
    main()
