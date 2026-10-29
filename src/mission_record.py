"""Immutable D5 assessment bundles, historical replay and research workflow.

New D5 entry point. Frozen D2--D4 modules and their legacy workflow API stay
unchanged. Replay executes the archived sources, model/scaler and configuration
in an isolated Python process; missing or changed artifacts never fall back to
the current repository. This is a research prototype, not flight authorization.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0.0"
NUMERIC_INPUTS = ("payload_g", "speed_commanded_ms", "altitude_m", "distance_2d_m",
                  "wind_forecast_ms", "ambient_temp_c", "soc", "soh")
INPUT_KEYS = NUMERIC_INPUTS + ("battery_type", "profile", "reserve_factor")
UNITS = dict(payload_g="g", speed_commanded_ms="m/s", altitude_m="m",
             distance_2d_m="m (total planned path)", wind_forecast_ms="m/s",
             ambient_temp_c="degC", soc="fraction [0,1]", soh="fraction [0,1]",
             reserve_factor="fraction", energy="Wh", timestamp="UTC ISO-8601")
PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "PyYAML", "joblib", "threadpoolctl")
VERDICT_RANK = {"INSUFFICIENT_DATA": 0, "NO_FLY": 1, "CONDITIONAL": 2, "FLY": 3}
ROLES = {"REVIEWER", "PILOT", "COORDINATOR"}


class RecordError(ValueError):
    """Stored evidence or a requested transition is invalid."""


class ReplayUnavailable(RecordError):
    """The exact historical artifacts/runtime are unavailable."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def utc(value):
    if not isinstance(value, str):
        raise RecordError("Timestamp must be a timezone-aware ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecordError("Invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecordError("Timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def timestamp(value):
    return utc(value).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", value):
        raise RecordError("ID must contain 1--96 letters, digits, underscores or hyphens")
    return value


def normalize(value):
    """Normalize None/NaN/infinity at the JSON boundary, keeping an audit list."""
    notices = []
    def visit(item, path):
        if isinstance(item, dict):
            return {str(k): visit(v, f"{path}.{k}") for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(v, f"{path}[{i}]") for i, v in enumerate(item)]
        if hasattr(item, "item"):
            item = item.item()
        if isinstance(item, float) and not math.isfinite(item):
            notices.append(path)
            return None
        return item
    return visit(value, "$"), notices


def runtime():
    return dict(python=platform.python_version(), implementation=platform.python_implementation(),
                packages={name: version(name) for name in PACKAGES})


def _write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value))


def _artifact_path(root, relative):
    part = PurePosixPath(relative)
    if part.is_absolute() or ".." in part.parts or "\\" in relative or ":" in relative:
        raise ReplayUnavailable("Unsafe artifact path")
    path = root.joinpath(*part.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ReplayUnavailable("Artifact escapes its bundle")
    return path


def create_artifacts(store, root=ROOT):
    """One shared, content-addressed source/config/model archive per run."""
    from src.uncertainty import load_context
    root, store = Path(root), Path(store)
    context = load_context(root)  # verify frozen upstream hashes; no training
    names = [p.relative_to(root).as_posix() for p in sorted((root / "src").rglob("*.py"))
             if "__pycache__" not in p.parts]
    names += [f"configs/d{n}_protocol.yaml" for n in (2, 3, 4, 5)]
    names += [context.d5["inherited_baseline"]["frozen_estimator_artifact"],
              context.d5["factors"]["energy_prediction_error"]["file"]]
    names = sorted(set(names))
    git = {}
    for key, command in (("commit", ["git", "rev-parse", "HEAD"]),
                         ("dirty_state", ["git", "status", "--porcelain"])):
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8")
        git[key] = result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"
    manifest = dict(schema_version=SCHEMA_VERSION, runtime=runtime(), git=git,
                    files={name: file_digest(root / name) for name in names},
                    upstream_data_hashes=context.input_hashes,
                    dataset_policy="Frozen dataset hashes plus complete selected scenario inputs; no refit",
                    final_d5_complete=False)
    artifact_id = digest(manifest)
    destination = store / "artifacts" / artifact_id
    if destination.exists():
        verify_artifacts(store, artifact_id)
        return artifact_id
    (store / "artifacts").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".archive-", dir=store / "artifacts") as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name in names:
            target = _artifact_path(staging, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
            if file_digest(target) != manifest["files"][name]:
                raise RecordError(f"Input changed while archiving: {name}")
        _write_new(staging / "artifact_manifest.json", manifest)
        staging.rename(destination)
    return artifact_id


def verify_artifacts(store, artifact_id, check_runtime=True):
    if not isinstance(artifact_id, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_id):
        raise ReplayUnavailable("Invalid artifact ID")
    root = (Path(store) / "artifacts" / artifact_id).resolve()
    try:
        manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
        if digest(manifest) != artifact_id:
            raise ReplayUnavailable("Artifact manifest checksum differs")
        for name, expected in manifest["files"].items():
            if file_digest(_artifact_path(root, name)) != expected:
                raise ReplayUnavailable(f"Archived artifact changed: {name}")
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ReplayUnavailable(f"Historical artifact missing or unreadable: {exc}") from exc
    if check_runtime and manifest["runtime"] != runtime():
        raise ReplayUnavailable("Historical Python/dependency versions unavailable; no fallback")
    return root, manifest


def weather_issues(weather, at):
    errors = []
    try:
        observed, expires = utc(weather.get("observed_at")), utc(weather.get("valid_until"))
        if observed >= expires:
            errors.append("WEATHER_INVALID_INTERVAL")
        if observed > at:
            errors.append("WEATHER_FROM_FUTURE")
        if at >= expires:
            errors.append("WEATHER_EXPIRED")
    except (RecordError, AttributeError):
        errors.append("WEATHER_MISSING_OR_INVALID_TIMESTAMPS")
    if not isinstance(weather, dict) or not isinstance(weather.get("source"), str) or not weather["source"].strip():
        errors.append("WEATHER_MISSING_SOURCE")
    return errors


def _mitigation_valid(spec, previous, result):
    action = spec.get("mitigation")
    if not action:
        return False
    if not previous or previous["result"]["verdict"] != "CONDITIONAL":
        return False
    if (previous["mission_id"] != spec["mission_id"] or
            previous["artifact_id"] != spec["artifact_id"] or
            spec.get("previous_assessment_id") != previous["assessment_id"] or
            action.get("approved_by_role") not in ROLES):
        return False
    try:
        if not (utc(previous["assessed_at"]) <= utc(action["approved_at"]) <= utc(spec["assessed_at"])):
            return False
    except (RecordError, KeyError):
        return False
    field_directions = {"M1": ("soc", 1), "M2": ("battery_type", 0),
                        "M3": ("wind_forecast_ms", -1), "M4": ("ambient_temp_c", 1),
                        "M5": ("payload_g", -1), "M6": ("speed_commanded_ms", -1),
                        "M7": ("distance_2d_m", -1)}
    if action.get("id") not in field_directions:
        return False
    field, direction = field_directions[action["id"]]
    old, new = previous["inputs"], spec["inputs"]
    changed = {k for k in INPUT_KEYS if old.get(k) != new.get(k)}
    if changed != {field} or old.get(field) is None or new.get(field) is None:
        return False
    if direction and (new[field] - old[field]) * direction <= 0:
        return False
    if result["verdict"] not in ("FLY", "CONDITIONAL"):
        return False
    before = previous["result"]["decision"].get("margin_ratio")
    after = result["decision"].get("margin_ratio")
    return (VERDICT_RANK[result["verdict"]] > VERDICT_RANK[previous["result"]["verdict"]]
            or (before is not None and after is not None and after > before))


def _evaluate(spec, previous=None):
    """Executed by the archived worker, using only that archive's modules."""
    from dataclasses import asdict
    import numpy as np
    import pandas as pd
    import yaml
    from src.decision_rules import assess
    from src.reference_labeller import scenario_features
    at = utc(spec["assessed_at"])
    inputs = spec["inputs"]
    d2, d3, d4 = [yaml.safe_load((ROOT / f"configs/d{n}_protocol.yaml").read_text(encoding="utf-8"))
                  for n in (2, 3, 4)]
    missing, invalid = [], []
    for key in NUMERIC_INPUTS:
        value = inputs.get(key)
        if value is None:
            missing.append(key)
        elif isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            invalid.append(key)
        elif ((key in ("soc", "soh") and not 0 <= value <= 1) or
              (key in ("payload_g", "altitude_m", "wind_forecast_ms") and value < 0) or
              (key in ("speed_commanded_ms", "distance_2d_m") and value <= 0)):
            invalid.append(key)
    if not isinstance(inputs.get("battery_type"), str) or inputs["battery_type"] not in ("TB47D", "TB48D"):
        invalid.append("battery_type")
    if not isinstance(inputs.get("profile"), str) or inputs["profile"] not in d3["aircraft_profiles"]:
        invalid.append("profile")
    reserve = inputs.get("reserve_factor")
    if isinstance(reserve, bool) or not isinstance(reserve, (float, int)) or not math.isfinite(reserve) or reserve < 0:
        invalid.append("reserve_factor")
    weather_errors = weather_issues(spec["weather"], at)
    prediction, decision = None, {}
    if not invalid:
        features_ok = not any(k in missing for k in ("payload_g", "speed_commanded_ms", "altitude_m",
                                                     "distance_2d_m", "wind_forecast_ms"))
        if features_ok:
            table = pd.read_csv(ROOT / "reports/d4_d2_frozen_coefficients.csv")
            features = list(table.feature)
            if features != d2["features"]["preflight"]:
                raise ReplayUnavailable("Archived feature order differs from D2")
            x = scenario_features(pd.DataFrame([inputs]), d4, features).to_numpy(float)[0]
            prediction = float(((x - table.scaler_mean.to_numpy()) / table.scaler_scale.to_numpy())
                               @ table.coef_standardised.to_numpy() + table.intercept.iloc[0])
            if not np.isfinite(prediction):
                raise RecordError("Frozen model produced a nonfinite prediction")
        d = assess(**inputs, e_required_Wh=prediction, protocol=d3)
        decision = asdict(d)
        decision["actionable"] = d.actionable
        verdict = d.verdict
        reasons = list(d.reasons)
    else:
        verdict, reasons = "NO_FLY", [f"INVALID_INPUT:{key}" for key in invalid]
    if missing and verdict != "NO_FLY":
        verdict = "INSUFFICIENT_DATA"
    if weather_errors and verdict not in ("NO_FLY", "INSUFFICIENT_DATA"):
        verdict = "INSUFFICIENT_DATA"
    reasons += [f"MISSING_INPUT:{key}" for key in missing] + weather_errors
    diagnostic = inputs["profile"] == "CMU_instrumented"
    result = dict(verdict=verdict, decision=decision, prediction_Wh=prediction,
                  missing_inputs=missing, invalid_inputs=invalid, weather_issues=weather_errors,
                  assessment_status="STALE" if weather_errors else "CURRENT", reasons=reasons,
                  diagnostic_only=diagnostic, operational_recommendation=False,
                  mitigation_validated=False, review_eligible=False,
                  profile_note=("CMU diagnostic: HR-3 remains RECORD_ONLY; FLY is not operational approval"
                                if diagnostic else "Research workflow test using M100_stock constraints"))
    result["mitigation_validated"] = _mitigation_valid(spec, previous, result)
    result["review_eligible"] = bool(not diagnostic and not weather_errors and not missing and not invalid
                                     and (verdict == "FLY" or
                                          (verdict == "CONDITIONAL" and result["mitigation_validated"])))
    if result["mitigation_validated"]:
        result["decision"]["mitigation_applied"] = spec["mitigation"]["id"]
        result["decision"]["actionable"] = True
    return result


def _worker_run(artifact_root, specs, previous):
    request = dict(specs=specs, previous=previous)
    result = subprocess.run([sys.executable, "-I", str(artifact_root / "src/mission_record.py"), "--worker"],
                            input=canonical(request).decode("utf-8"), capture_output=True, text=True,
                            encoding="utf-8", cwd=artifact_root, timeout=120)
    if result.returncode:
        raise ReplayUnavailable(f"Archived computation failed: {result.stderr[-2500:]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReplayUnavailable("Archived worker returned invalid JSON") from exc


@dataclass(frozen=True)
class AssessmentSnapshot:
    """Canonical JSON keeps nested inputs immutable, including through properties."""
    content: str
    sha256: str

    @property
    def data(self):
        return json.loads(self.content)


def load_snapshot(store, assessment_id):
    path = Path(store) / "snapshots" / f"{identifier(assessment_id)}.json"
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        data = wrapper["assessment"]
        if digest(data) != wrapper["sha256"] or data["assessment_id"] != assessment_id:
            raise RecordError("Assessment checksum or ID differs")
        return AssessmentSnapshot(canonical(data).decode("utf-8"), wrapper["sha256"])
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise RecordError(f"Assessment unavailable: {assessment_id}") from exc


def save_assessments(store, artifact_id, specifications):
    """Write new assessment IDs only; linked prior assessments must already exist."""
    root, _ = verify_artifacts(store, artifact_id)
    existing = [load_snapshot(store, p.stem).data for p in sorted((Path(store) / "snapshots").glob("*.json"))]
    specs, prior = [], []
    for raw in specifications:
        spec, notices = normalize(raw)
        spec["assessment_id"] = identifier(spec["assessment_id"])
        spec["mission_id"] = identifier(spec["mission_id"])
        spec["assessed_at"] = timestamp(spec["assessed_at"])
        spec["artifact_id"] = artifact_id
        unknown = set(spec["inputs"]) - set(INPUT_KEYS)
        if unknown:
            raise RecordError(f"Unknown inputs (no externally supplied prediction allowed): {sorted(unknown)}")
        spec["inputs"] = {k: spec["inputs"].get(k) for k in INPUT_KEYS}
        spec["weather"] = spec.get("weather") or {}
        if spec.get("mitigation") is not None and not isinstance(spec["mitigation"], dict):
            raise RecordError("Mitigation must contain its ID and review evidence")
        spec["units"] = UNITS
        spec["normalization_nonfinite_to_null"] = notices
        spec["schema_version"] = SCHEMA_VERSION
        spec["uncertainty"] = dict(mode="DETERMINISTIC_ASSESSMENT", sampled=False, seed=None)
        previous_id = spec.get("previous_assessment_id")
        if not previous_id and any(p["mission_id"] == spec["mission_id"] for p in existing):
            raise RecordError("Existing mission requires previous_assessment_id and a new assessment")
        previous = load_snapshot(store, previous_id).data if previous_id else None
        if previous:
            if previous["mission_id"] != spec["mission_id"] or utc(previous["assessed_at"]) > utc(spec["assessed_at"]):
                raise RecordError("Reassessment must follow the same mission in time")
            spec["previous_snapshot_sha256"] = digest(previous)
        else:
            spec["previous_snapshot_sha256"] = None
        spec["mitigation"] = spec.get("mitigation")
        if (Path(store) / "snapshots" / f"{spec['assessment_id']}.json").exists():
            raise FileExistsError(f"Immutable assessment already exists: {spec['assessment_id']}")
        specs.append(spec)
        prior.append(previous)
    if len({s["assessment_id"] for s in specs}) != len(specs):
        raise RecordError("Duplicate assessment IDs in batch")
    results = _worker_run(root, specs, prior)
    snapshots = []
    for spec, result in zip(specs, results, strict=True):
        spec["result"] = result
        checksum = digest(spec)
        _write_new(Path(store) / "snapshots" / f"{spec['assessment_id']}.json",
                   dict(sha256=checksum, assessment=spec))
        snapshots.append(AssessmentSnapshot(canonical(spec).decode("utf-8"), checksum))
    return snapshots


def replay(store, assessment_ids):
    """Batch replay with archived sources; return numerical and verdict evidence."""
    groups, output = {}, []
    for assessment_id in assessment_ids:
        snapshot = load_snapshot(store, assessment_id)
        groups.setdefault(snapshot.data["artifact_id"], []).append(snapshot)
    for artifact_id, snapshots in groups.items():
        root, _ = verify_artifacts(store, artifact_id)
        specs, previous = [], []
        for snapshot in snapshots:
            spec = snapshot.data
            old_id = spec.get("previous_assessment_id")
            old = load_snapshot(store, old_id).data if old_id else None
            if old and digest(old) != spec["previous_snapshot_sha256"]:
                raise RecordError("Prior assessment differs from mitigation/reassessment evidence")
            specs.append(spec)
            previous.append(old)
        started = time.perf_counter()
        recalculated = _worker_run(root, specs, previous)
        elapsed = time.perf_counter() - started
        import yaml
        policy = yaml.safe_load((root / "configs/d5_protocol.yaml").read_text(encoding="utf-8"))["replay_and_workflow"]["comparison"]
        for snapshot, actual in zip(snapshots, recalculated, strict=True):
            differences, maximum = [], [0.0]
            def compare(a, b, path="result"):
                if isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
                    for k in a:
                        compare(a[k], b[k], f"{path}.{k}")
                elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
                    for i, (x, y) in enumerate(zip(a, b)):
                        compare(x, y, f"{path}[{i}]")
                elif (isinstance(a, (float, int)) and not isinstance(a, bool)
                      and isinstance(b, (float, int)) and not isinstance(b, bool)):
                    maximum[0] = max(maximum[0], abs(a-b))
                    if not math.isclose(a, b, abs_tol=policy["numerical_atol"], rel_tol=policy["numerical_rtol"]):
                        differences.append(path)
                elif type(a) is not type(b) or a != b:
                    differences.append(path)
            expected = snapshot.data["result"]
            compare(expected, actual)
            output.append(dict(assessment_id=snapshot.data["assessment_id"], artifact_id=artifact_id,
                               expected_verdict=expected["verdict"], replayed_verdict=actual["verdict"],
                               exact_verdict_match=expected["verdict"] == actual["verdict"],
                               all_outputs_match=not differences, mismatched_fields=differences,
                               max_absolute_difference=maximum[0],
                               batch_seconds=elapsed, batch_size=len(snapshots),
                               numerical_atol=policy["numerical_atol"], numerical_rtol=policy["numerical_rtol"]))
    return output


def read_events(store, assessment_id):
    folder = Path(store) / "workflow_events" / identifier(assessment_id)
    previous, result = None, []
    if not folder.exists():
        return result
    for index, path in enumerate(sorted(folder.glob("*.json")), 1):
        event = json.loads(path.read_text(encoding="utf-8"))
        payload = {k: v for k, v in event.items() if k != "sha256"}
        if (path.name != f"{index:06d}.json" or event["previous_sha256"] != previous
                or event["sha256"] != digest(payload) or event["sequence"] != index
                or event["assessment_id"] != assessment_id):
            raise RecordError("Workflow event chain was changed")
        if result and utc(event["at"]) < utc(result[-1]["at"]):
            raise RecordError("Workflow event time moved backwards")
        previous = event["sha256"]
        result.append(event)
    return result


def _append_event(store, snapshot, event_type, at, detail):
    assessment_id = snapshot.data["assessment_id"]
    events = read_events(store, assessment_id)
    if utc(at) < utc(snapshot.data["assessed_at"]) or (events and utc(at) < utc(events[-1]["at"])):
        raise RecordError("Workflow event precedes assessment or previous event")
    payload = dict(assessment_id=assessment_id, snapshot_sha256=snapshot.sha256,
                   sequence=len(events)+1, previous_sha256=events[-1]["sha256"] if events else None,
                   event_type=event_type, at=timestamp(at), detail=detail)
    event = {**payload, "sha256": digest(payload)}
    _write_new(Path(store) / "workflow_events" / assessment_id / f"{len(events)+1:06d}.json", event)
    return event


def workflow_status(store, assessment_id, *, at, current_inputs=None, current_weather=None,
                    current_artifact_id=None, root=ROOT):
    snapshot = load_snapshot(store, assessment_id)
    data, stale = snapshot.data, []
    _, manifest = verify_artifacts(store, data["artifact_id"])
    now = utc(at)
    if now < utc(data["assessed_at"]):
        stale.append("ASSESSMENT_FROM_FUTURE")
    stale += weather_issues(data["weather"], now)
    if current_inputs is not None:
        patch, _ = normalize(current_inputs)
        if set(patch) - set(INPUT_KEYS):
            raise RecordError("Unknown current safety input")
        stale += [f"INPUT_CHANGED:{k}" for k, v in patch.items() if data["inputs"].get(k) != v]
    if current_weather is not None:
        weather, _ = normalize(current_weather)
        if weather != data["weather"]:
            stale.append("WEATHER_CHANGED")
    if current_artifact_id is not None:
        if current_artifact_id != data["artifact_id"]:
            stale.append("ARTIFACT_VERSION_CHANGED")
    else:
        for name, expected in manifest["files"].items():
            path = Path(root) / name
            if not path.is_file() or file_digest(path) != expected:
                stale.append(f"ARTIFACT_CHANGED:{name}")
    for path in sorted((Path(store) / "snapshots").glob("*.json")):
        other = load_snapshot(store, path.stem).data
        if (utc(other["assessed_at"]) <= now and
                (other.get("previous_assessment_id") == assessment_id or
                 (other["mission_id"] == data["mission_id"] and
                  utc(other["assessed_at"]) > utc(data["assessed_at"])))):
            stale.append(f"SUPERSEDED_BY:{other['assessment_id']}")
    events = read_events(store, assessment_id)
    if any(e["snapshot_sha256"] != snapshot.sha256 for e in events):
        raise RecordError("Workflow events refer to a different snapshot")
    if events and utc(events[-1]["at"]) > now:
        stale.append("WORKFLOW_EVENT_FROM_FUTURE")
    stale += [reason for e in events if e["event_type"] == "STALE" for reason in e["detail"]["reasons"]]
    stale = sorted(set(stale))
    blocked = list(stale)
    result = data["result"]
    if result["diagnostic_only"]:
        blocked.append("CMU_DIAGNOSTIC_ONLY")
    if not result["review_eligible"]:
        blocked.append("ASSESSMENT_NOT_ELIGIBLE")
    approved = any(e["event_type"] == "APPROVED" for e in events)
    flight_started = any(e["event_type"] == "IN_FLIGHT" for e in events)
    outcomes = [e["detail"] for e in events if e["event_type"] == "OUTCOME_RECORDED"]
    if outcomes:
        blocked.append("MISSION_OUTCOME_ALREADY_RECORDED")
    return dict(assessment_status="STALE" if stale or result["assessment_status"] == "STALE" else "CURRENT",
                stale_reasons=stale, blocking_reasons=blocked, approved=approved, in_flight=flight_started,
                may_proceed=bool(approved and not blocked),
                observed_outcome=outcomes[-1] if outcomes else dict(outcome="UNKNOWN", note="", evidence_source=None))


def workflow_action(store, assessment_id, action, *, at, actor_role=None,
                    current_inputs=None, current_weather=None, current_artifact_id=None, root=ROOT):
    if action not in ("APPROVE", "START"):
        raise RecordError("Action must be APPROVE or START")
    snapshot = load_snapshot(store, assessment_id)
    status = workflow_status(store, assessment_id, at=at, current_inputs=current_inputs,
                             current_weather=current_weather, current_artifact_id=current_artifact_id, root=root)
    if status["stale_reasons"]:
        _append_event(store, snapshot, "STALE", at, dict(reasons=status["stale_reasons"]))
    if status["blocking_reasons"]:
        raise RecordError("Transition blocked: " + "; ".join(status["blocking_reasons"]))
    if action == "APPROVE" and actor_role not in ROLES:
        raise RecordError("Human reviewer role required")
    if action == "START" and not status["may_proceed"]:
        raise RecordError("New human approval required before START")
    if status["in_flight"]:
        raise RecordError("Mission already started")
    return _append_event(store, snapshot, "APPROVED" if action == "APPROVE" else "IN_FLIGHT", at,
                         dict(actor_role=actor_role))


def record_outcome(store, assessment_id, outcome, *, at, note="", evidence_source=None):
    if outcome not in ("UNKNOWN", "COMPLETED", "ABORTED", "NOT_FLOWN"):
        raise RecordError("Unknown observed outcome")
    if outcome != "UNKNOWN" and (not note.strip() or not isinstance(evidence_source, str) or not evidence_source.strip()):
        raise RecordError("Observed outcome requires independent note and evidence source")
    snapshot = load_snapshot(store, assessment_id)
    return _append_event(store, snapshot, "OUTCOME_RECORDED", at,
                         dict(outcome=outcome, note=note, evidence_source=evidence_source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--replay", nargs="+")
    parser.add_argument("--capture", type=Path, help="JSON request (one specification or a list); new IDs only")
    args = parser.parse_args()
    if args.worker:
        # -I removes cwd/PYTHONPATH; insert only this verified historical archive.
        sys.path.insert(0, str(ROOT))
        request = json.loads(sys.stdin.buffer.read())
        response = [_evaluate(s, p) for s, p in zip(request["specs"], request["previous"], strict=True)]
        sys.stdout.buffer.write(canonical(response))
    elif args.store and args.replay:
        results = replay(args.store, args.replay)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        raise SystemExit(0 if all(r["all_outputs_match"] for r in results) else 1)
    elif args.store and args.capture:
        specification = json.loads(args.capture.read_text(encoding="utf-8-sig"))
        artifact = create_artifacts(args.store)
        records = save_assessments(args.store, artifact,
                                   specification if isinstance(specification, list) else [specification])
        print(json.dumps([dict(assessment_id=r.data["assessment_id"], sha256=r.sha256,
                               verdict=r.data["result"]["verdict"]) for r in records], indent=2))
    else:
        parser.error("Use --store RUN_DIRECTORY with --replay ASSESSMENT_IDS or --capture REQUEST.json")


if __name__ == "__main__":
    main()
