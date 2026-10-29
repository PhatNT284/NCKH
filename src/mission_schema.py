"""D6 versioned mission-record exchange, reusing the D5 historical engine.

An exported record is evidence at a caller-specified time, not permission to fly.
The source store and its archived artifacts remain necessary for replay.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from src import mission_record as mr

SCHEMA_VERSION = "1.0.0"
SCHEMA_PATH = mr.ROOT / "schemas/mission_record/1.0.0.json"


def validate_record(record):
    """Reject unknown schemas, structural errors and damaged embedded evidence."""
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
        raise mr.RecordError("Unsupported D6 schema version; no implicit migration")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(record),
                    key=lambda error: str(list(error.absolute_path)))
    if errors:
        error = errors[0]
        raise mr.RecordError(f"Invalid D6 record at {list(error.absolute_path)}: {error.message}")
    try:
        mr.canonical(record)  # JSON must not contain NaN/infinity, even in optional metadata.
        snapshot = record["snapshot"]
        data = snapshot["assessment"]
        if mr.digest(data) != snapshot["sha256"]:
            raise mr.RecordError("Snapshot checksum differs")
        if mr.digest(record["artifact_manifest"]) != data["artifact_id"]:
            raise mr.RecordError("Artifact manifest checksum differs")
        previous = None
        previous_at = mr.utc(data["assessed_at"])
        for index, event in enumerate(record["workflow"]["events"], 1):
            payload = {k: v for k, v in event.items() if k != "sha256"}
            if (event["sequence"] != index or event["previous_sha256"] != previous
                    or event["assessment_id"] != data["assessment_id"]
                    or event["snapshot_sha256"] != snapshot["sha256"]
                    or event["sha256"] != mr.digest(payload)):
                raise mr.RecordError("Workflow event chain differs")
            if not previous_at <= mr.utc(event["at"]) <= mr.utc(record["workflow"]["as_of"]):
                raise mr.RecordError("Workflow event time is inconsistent")
            previous = event["sha256"]
            previous_at = mr.utc(event["at"])
        expected = _metadata(data, record["artifact_manifest"], record["assumptions"])
        if record["metadata"] != expected:
            raise mr.RecordError("Metadata differs from archived evidence")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, mr.RecordError):
            raise
        raise mr.RecordError(f"Invalid D6 evidence: {exc}") from exc
    return record


def _metadata(data, manifest, assumptions):
    files = manifest["files"]
    return dict(
        distance_convention="TOTAL_PLANNED_PATH_M_NOT_ONE_WAY_DELIVERY",
        wind_direction=dict(value=None, status="NOT_AVAILABLE_NOT_USED_BY_MODEL"),
        versions=dict(dataset=manifest["upstream_data_hashes"],
                      model_sha256=files["reports/d4_d2_frozen_coefficients.csv"],
                      config_sha256={k: v for k, v in files.items() if k.startswith("configs/")},
                      software=dict(git=manifest["git"], runtime=manifest["runtime"])),
        battery=dict(available=data["result"]["decision"].get("available"),
                     assumptions=assumptions),
        explanation=dict(reasons=data["result"]["reasons"],
                         sensitivity=dict(status="NOT_RUN_FOR_THIS_DETERMINISTIC_ASSESSMENT",
                                          results=None)),
    )


def build_record(store, assessment_id, *, at):
    """Read existing evidence without modifying its snapshots or workflow history."""
    snapshot = mr.load_snapshot(store, assessment_id)
    data = snapshot.data
    if mr.utc(at) < mr.utc(data["assessed_at"]):
        raise mr.RecordError("Export time precedes assessment")
    root, manifest = mr.verify_artifacts(store, data["artifact_id"])
    protocol = yaml.safe_load((root / "configs/d3_protocol.yaml").read_text(encoding="utf-8"))
    assumptions = dict(
        source="ARCHIVED_CONFIG:configs/d3_protocol.yaml",
        config_sha256=manifest["files"]["configs/d3_protocol.yaml"],
        energy_available=protocol["available_energy"],
        input_provenance=data.get("provenance", {"status": "NOT_RECORDED_IN_SOURCE"}),
    )
    events = mr.read_events(store, assessment_id)
    if any(mr.utc(e["at"]) > mr.utc(at) for e in events):
        raise mr.RecordError("Export time precedes a recorded workflow event")
    status = mr.workflow_status(store, assessment_id, at=at, root=root,
                                current_artifact_id=data["artifact_id"])
    approval = next((e for e in reversed(events) if e["event_type"] == "APPROVED"), None)
    outcome = status["observed_outcome"]["outcome"]
    mission_status = ("COMPLETED" if outcome == "COMPLETED" else
                      "ABORTED" if outcome == "ABORTED" else
                      "CANCELLED" if outcome == "NOT_FLOWN" else
                      "BLOCKED" if status["blocking_reasons"] else
                      "IN_FLIGHT" if status["in_flight"] else
                      "APPROVED" if status["approved"] else "ASSESSED")
    workflow = dict(
        as_of=mr.timestamp(at), mission_status=mission_status,
        assessment_status=status["assessment_status"], stale_reason=status["stale_reasons"],
        approval_action=("APPROVED_WITH_MITIGATION" if data["result"]["mitigation_validated"]
                         else "APPROVED") if approval else None,
        approval_actor_role=approval["detail"]["actor_role"] if approval else None,
        approval_timestamp=approval["at"] if approval else None,
        preflight_reassessment_id=(data["assessment_id"] if data.get("previous_assessment_id") else None),
        observed_outcome=status["observed_outcome"], events=events,
    )
    record = dict(schema_version=SCHEMA_VERSION, record_kind="RESEARCH_MISSION_RECORD",
                  snapshot=dict(sha256=snapshot.sha256, assessment=data),
                  artifact_manifest=manifest, assumptions=assumptions,
                  metadata=_metadata(data, manifest, assumptions), workflow=workflow)
    return validate_record(record)


def write_record(path, record):
    """Validate and write once; never overwrite an existing record."""
    validate_record(record)
    mr._write_new(path, dict(sha256=mr.digest(record), record=record))


def read_record(path):
    try:
        wrapper = json.loads(Path(path).read_text(encoding="utf-8"))
        record = wrapper["record"]
        if mr.digest(record) != wrapper["sha256"]:
            raise mr.RecordError("D6 record checksum differs")
        return validate_record(record)
    except (OSError, KeyError, ValueError, TypeError) as exc:
        if isinstance(exc, mr.RecordError):
            raise
        raise mr.RecordError(f"D6 record unavailable: {exc}") from exc


def replay_record(path, store):
    record = read_record(path)
    data = record["snapshot"]["assessment"]
    snapshot = mr.load_snapshot(store, data["assessment_id"])
    if snapshot.sha256 != record["snapshot"]["sha256"]:
        raise mr.RecordError("Replay store differs from exported snapshot")
    root, manifest = mr.verify_artifacts(store, data["artifact_id"])
    if manifest != record["artifact_manifest"]:
        raise mr.RecordError("Replay archive differs from exported manifest")
    events = record["workflow"]["events"]
    if mr.read_events(store, data["assessment_id"])[:len(events)] != events:
        raise mr.RecordError("Exported workflow differs from source history")
    protocol = yaml.safe_load((root / "configs/d3_protocol.yaml").read_text(encoding="utf-8"))
    if (record["assumptions"]["energy_available"] != protocol["available_energy"]
            or record["assumptions"]["config_sha256"] != manifest["files"]["configs/d3_protocol.yaml"]
            or record["assumptions"]["input_provenance"] != data.get("provenance", {"status": "NOT_RECORDED_IN_SOURCE"})):
        raise mr.RecordError("Exported assumptions differ from source archive")
    return mr.replay(store, [data["assessment_id"]])[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--store", type=Path, required=True)
    export.add_argument("--assessment", required=True)
    export.add_argument("--at", required=True)
    export.add_argument("--out", type=Path, required=True)
    check = commands.add_parser("validate")
    check.add_argument("record", type=Path)
    replay = commands.add_parser("replay")
    replay.add_argument("record", type=Path)
    replay.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        from src.d6_export import export_tables

        for target in (args.out, args.out.with_suffix(".xlsx")):
            if target.exists():
                parser.error(f"Output already exists: {target}")
        write_record(args.out, build_record(args.store, args.assessment, at=args.at))
        print(f"Saved {args.out}")
        for target in export_tables(args.out, args.out.with_suffix(".xlsx")):
            print(f"Saved {target}")
    elif args.command == "validate":
        read_record(args.record)
        print("Valid D6 mission record (schema 1.0.0)")
    else:
        result = replay_record(args.record, args.store)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not (result["all_outputs_match"] and result["exact_verdict_match"]):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
