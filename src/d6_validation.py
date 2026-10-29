"""Produce D6 schema/serialization/replay evidence on synthetic mission records.

Usage: python -m src.d6_validation --out reports/d6/validation_20261027_01
Never overwrites a run; does not retrain D2 or rerun D5 Monte Carlo.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import shutil

from src import mission_record as mr
from src import mission_schema as ms
from src.d6_export import export_tables
from src.replay_validation import _spec, AT, LATER, WEATHER


def validate(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    store = out / "store"
    artifact = mr.create_artifacts(store)
    specs = [
        _spec("fly"), _spec("tb48d", battery_type="TB48D"),
        _spec("conditional", soc=.235), _spec("no_fly", soc=.2),
        _spec("wind_veto", wind_forecast_ms=12, soc=1),
        _spec("missing_soc", soc=None), _spec("nan_wind", wind_forecast_ms=float("nan")),
        _spec("invalid_soc", soc=1.5), _spec("expired_weather"),
        _spec("cmu_diagnostic", profile="CMU_instrumented"),
    ]
    next(s for s in specs if s["assessment_id"] == "expired_weather")["weather"]["valid_until"] = AT
    prediction = mr._evaluate({**_spec("temporary"), "artifact_id": artifact})["prediction_Wh"]
    specs.append(_spec("reserve_boundary", soc=1.2 * prediction / (99.9 * .95 * .9954)))
    mr.save_assessments(store, artifact, specs)
    new = _spec("preflight_reassessment", soc=.235)
    new.update(mission_id="mission_fly", previous_assessment_id="fly", assessed_at=LATER)
    mr.workflow_action(store, "fly", "APPROVE", at=AT, actor_role="REVIEWER")
    mr.save_assessments(store, artifact, [new])
    mr.workflow_action(store, "tb48d", "APPROVE", at=LATER, actor_role="REVIEWER")
    mr.workflow_action(store, "tb48d", "START", at=LATER)
    mr.record_outcome(store, "wind_veto", "NOT_FLOWN", at=LATER,
                      note="Synthetic scenario cancelled; not a real flight outcome",
                      evidence_source="SYNTHETIC_WORKFLOW_FIXTURE")
    ids = [s["assessment_id"] for s in specs] + [new["assessment_id"]]
    before = {key: mr.load_snapshot(store, key).sha256 for key in ids}
    rows = []
    print(f"D6: validating and replaying {len(ids)} saved records...", flush=True)
    for key in ids:
        exported = ms.build_record(store, key, at=LATER)
        path = out / "records" / f"{key}.json"
        ms.write_record(path, exported)
        row = ms.replay_record(path, store)
        row.update(schema_valid=True, serialization_round_trip=(ms.read_record(path) == exported),
                   snapshot_preserved=(mr.load_snapshot(store, key).sha256 == before[key]))
        rows.append(row)
    checks = dict(
        all_four_verdicts={r["expected_verdict"] for r in rows} == set(mr.VERDICT_RANK),
        schema_and_round_trip=all(r["schema_valid"] and r["serialization_round_trip"] for r in rows),
        exact_verdicts=all(r["exact_verdict_match"] for r in rows),
        numerical_outputs=all(r["all_outputs_match"] for r in rows),
        snapshots_preserved=all(r["snapshot_preserved"] for r in rows),
        old_assessment_stale=ms.build_record(store, "fly", at=LATER)["workflow"]["assessment_status"] == "STALE",
        explicit_reassessment_link=ms.build_record(store, "preflight_reassessment", at=LATER)["workflow"]["preflight_reassessment_id"] == "preflight_reassessment",
        outcome_independent=ms.build_record(store, "no_fly", at=LATER)["workflow"]["observed_outcome"]["outcome"] == "UNKNOWN",
    )
    for name, mutate in [
        ("unknown_schema_rejected", lambda r: r.update(schema_version="99.0.0")),
        ("missing_field_rejected", lambda r: r.pop("workflow")),
        ("modified_prediction_rejected", lambda r: r["snapshot"]["assessment"]["result"].update(prediction_Wh=999)),
    ]:
        record = ms.build_record(store, "no_fly", at=LATER)
        mutate(record)
        try:
            ms.validate_record(record)
        except mr.RecordError:
            checks[name] = True
        else:
            checks[name] = False
    # Missing model must stop replay, not silently substitute the current model.
    model = store / "artifacts" / artifact / "reports/d4_d2_frozen_coefficients.csv"
    content = model.read_bytes()
    try:
        model.unlink()
        try:
            ms.replay_record(out / "records/no_fly.json", store)
        except mr.ReplayUnavailable:
            checks["missing_model_rejected"] = True
        else:
            checks["missing_model_rejected"] = False
    finally:
        model.write_bytes(content)
    mr.verify_artifacts(store, artifact)
    shutil.copyfile(ms.SCHEMA_PATH, out / "mission_record.schema.json")
    mr._write_new(out / "replay_results.json", rows)
    mr._write_new(out / "checks.json", checks)
    with (out / "replay_results.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({**r, "mismatched_fields": json.dumps(r["mismatched_fields"])} for r in rows)
    succeeded = all(checks.values())
    maximum = max(r["max_absolute_difference"] for r in rows)
    report = [
        "# D6 — Bản ghi nhiệm vụ có thể tái lập", "",
        "Căn cứ: proposal §12 (D6), §5.10; phương pháp kiểm thử theo E5. "
        "Duy thực hiện, Phát kiểm tra chéo. Trạng thái kiểm tra chéo: PENDING.", "",
        "## Kết quả kiểm chứng", "",
        f"- Bản ghi: {len(rows)}; đủ bốn phán quyết, hai pin, ca cận biên, luật chặn, "
        "thiếu/NaN/đầu vào sai, thời tiết hết hạn và đánh giá lại trước bay.",
        f"- Lược đồ và lưu/đọc: {sum(r['serialization_round_trip'] for r in rows)}/{len(rows)} đạt.",
        f"- Replay phán quyết: {sum(r['exact_verdict_match'] for r in rows)}/{len(rows)} khớp chính xác.",
        f"- Replay toàn bộ đầu ra: {sum(r['all_outputs_match'] for r in rows)}/{len(rows)} khớp; "
        f"chênh lệch tuyệt đối lớn nhất {maximum:g}.",
        "- Dung sai số: atol=1e-8, rtol=1e-8, lấy từ protocol D5 đã lưu cùng bản ghi.",
        f"- Kiểm tra bổ sung: {sum(checks.values())}/{len(checks)} đạt; "
        "gồm từ chối schema lạ, trường thiếu, kết quả bị sửa và mô hình lịch sử bị thiếu.", "",
        "## Hai đầu ra D6 theo proposal", "",
        "1. `schemas/mission_record/1.0.0.json`: lược đồ có phiên bản; "
        "`src/mission_schema.py`: kiểm tra, lưu, đọc và replay bản ghi.",
        "2. `tests/test_mission_schema.py`, `tests/test_mission_record.py`: "
        "kiểm thử hợp đồng bản ghi, replay và bất biến quy trình; "
        "`replay_results.csv`, `checks.json`: bằng chứng của lần chạy này.", "",
        "## Phạm vi", "",
        "D6 kế thừa snapshot/replay từ D5; không thay công thức năng lượng hay mô hình D2. "
        "Các ca thử là tổng hợp, thời điểm và thời tiết là fixture lịch sử rõ ràng. "
        "M100_stock chỉ kiểm logic; CMU_instrumented là cấu hình chẩn đoán không cấp quyền bay.", "",
        "Hướng gió không có: lưu null và lý do. Đánh giá tất định không lấy mẫu: seed=null. "
        "Độ nhạy riêng từng bản ghi chưa chạy: lưu trạng thái NOT_RUN; không tạo kết quả giả. "
        "Bản ghi lưu nguồn giả định pin từ cấu hình lịch sử. Kết cục UNKNOWN được giữ "
        "độc lập với FLY/NO_FLY. Không có dữ liệu bay thực tế mới.", "",
        "Replay cần cả bản ghi và thư mục store chứa mô hình/mã/config lịch sử; "
        "file JSON xuất riêng không thay thế kho hiện vật. Thiếu phiên bản hoặc sai checksum "
        "thì báo lỗi. Bản ghi quy trình phản ánh thời điểm as_of, không phải quyền duyệt hiện tại.", "",
        "Kết quả này là bằng chứng kỹ thuật, chưa có xác nhận kiểm tra chéo; "
        "không tự nghiệm thu D6 hoặc thay trạng thái nghiệm thu D5.", "",
    ]
    (out / "d6_report.md").write_text("\n".join(report), encoding="utf-8")
    print("D6: exporting Excel reading tables...", flush=True)
    export_tables(out / "records", out / "mission_records.xlsx")
    files = [p for p in out.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    manifest = dict(
        status="TECHNICAL_VALIDATION_PASSED" if succeeded else "FAILED",
        cross_check_status="PENDING", owner="Duy", cross_checker="Phat",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        schema_version=ms.SCHEMA_VERSION, jsonschema_version=version("jsonschema"),
        schema_sha256=mr.file_digest(ms.SCHEMA_PATH), artifact_id=artifact,
        record_count=len(rows), checks_passed=sum(checks.values()), checks_total=len(checks),
        max_absolute_difference=maximum,
        outputs={p.relative_to(out).as_posix(): mr.file_digest(p) for p in sorted(files)},
    )
    mr._write_new(out / "validation_manifest.json", manifest)
    print(f"D6: {len(rows)} records; {sum(checks.values())}/{len(checks)} checks; max difference {maximum:g}.", flush=True)
    return succeeded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output already exists; choose a new run directory")
    try:
        succeeded = validate(args.out)
    except Exception as exc:
        if args.out.is_dir():
            mr._write_new(args.out / "run_failure.json", dict(status="FAILED", error=str(exc)))
        raise
    raise SystemExit(0 if succeeded else 1)


if __name__ == "__main__":
    main()
