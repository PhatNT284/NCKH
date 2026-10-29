"""D6 exchange contract and historical replay; D5 tests cover workflow gates."""
from copy import deepcopy
import json
import shutil

import pytest
from jsonschema import Draft202012Validator

from src import mission_record as mr
from src import mission_schema as ms
from src.replay_validation import _spec, AT, LATER


@pytest.fixture(scope="module")
def original_store(tmp_path_factory):
    store = tmp_path_factory.mktemp("d6-store")
    artifact = mr.create_artifacts(store)
    mr.save_assessments(store, artifact, [
        _spec("fly"), _spec("conditional", soc=.235), _spec("veto", wind_forecast_ms=12),
        _spec("missing", soc=None), _spec("nan", wind_forecast_ms=float("nan")),
        _spec("invalid", battery_type=[]),
    ])
    return store, artifact


@pytest.fixture
def store(tmp_path, original_store):
    path = tmp_path / "store"
    shutil.copytree(original_store[0], path)
    return path, original_store[1]


def test_schema_is_valid_json_schema():
    Draft202012Validator.check_schema(json.loads(ms.SCHEMA_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("field", ["margin_Wh", "e_available_Wh", "hard_rule_report"])
def test_missing_numerical_or_rule_evidence_rejected(original_store, field):
    record = ms.build_record(original_store[0], "fly", at=AT)
    del record["snapshot"]["assessment"]["result"]["decision"][field]
    with pytest.raises(mr.RecordError, match="required property"):
        ms.validate_record(record)


def test_relocated_store_replays_without_original_absolute_path(store, tmp_path):
    path, _ = store
    output = tmp_path / "mission.json"
    ms.write_record(output, ms.build_record(path, "fly", at=AT))
    moved = tmp_path / "relocated"
    path.rename(moved)
    assert ms.replay_record(output, moved)["all_outputs_match"]


def test_round_trip_replays_archived_verdict_and_numbers(store, tmp_path):
    path, artifact = store
    before = mr.load_snapshot(path, "fly").sha256
    record = ms.build_record(path, "fly", at=AT)
    output = tmp_path / "mission.json"
    ms.write_record(output, record)
    assert ms.read_record(output) == record
    result = ms.replay_record(output, path)
    assert result["exact_verdict_match"] and result["all_outputs_match"]
    assert result["max_absolute_difference"] == 0
    assert mr.load_snapshot(path, "fly").sha256 == before
    assert record["metadata"]["versions"]["model_sha256"]
    assert record["metadata"]["wind_direction"]["value"] is None
    assert record["workflow"]["observed_outcome"]["outcome"] == "UNKNOWN"
    with pytest.raises(FileExistsError):
        ms.write_record(output, record)


@pytest.mark.parametrize("case", ["fly", "conditional", "veto", "missing", "nan", "invalid"])
def test_schema_preserves_valid_and_fail_closed_assessments(original_store, case):
    record = ms.build_record(original_store[0], case, at=AT)
    assert record["snapshot"]["assessment"]["assessment_id"] == case
    if case == "nan":
        assert record["snapshot"]["assessment"]["inputs"]["wind_forecast_ms"] is None
        assert record["snapshot"]["assessment"]["normalization_nonfinite_to_null"]


@pytest.mark.parametrize("field", ["schema_version", "snapshot", "workflow", "metadata", "assumptions"])
def test_missing_required_sections_rejected(original_store, field):
    record = ms.build_record(original_store[0], "fly", at=AT)
    del record[field]
    with pytest.raises(mr.RecordError):
        ms.validate_record(record)


@pytest.mark.parametrize("section", ["record", "snapshot", "artifact"])
def test_unknown_schema_versions_rejected(original_store, section):
    record = ms.build_record(original_store[0], "fly", at=AT)
    target = {"record": record, "snapshot": record["snapshot"]["assessment"],
              "artifact": record["artifact_manifest"]}[section]
    target["schema_version"] = "99.0.0"
    with pytest.raises(mr.RecordError):
        ms.validate_record(record)


def test_tampered_record_and_recomputed_outer_checksum_rejected(original_store, tmp_path):
    record = ms.build_record(original_store[0], "fly", at=AT)
    output = tmp_path / "mission.json"
    ms.write_record(output, record)
    wrapper = json.loads(output.read_text(encoding="utf-8"))
    wrapper["record"]["snapshot"]["assessment"]["inputs"]["soc"] = .1
    output.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(mr.RecordError, match="checksum"):
        ms.read_record(output)
    wrapper["sha256"] = mr.digest(wrapper["record"])
    output.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(mr.RecordError, match="Snapshot checksum"):
        ms.read_record(output)


def test_metadata_cannot_claim_a_different_model(original_store):
    record = ms.build_record(original_store[0], "fly", at=AT)
    record["metadata"]["versions"]["model_sha256"] = "0" * 64
    with pytest.raises(mr.RecordError, match="Metadata"):
        ms.validate_record(record)


def test_history_survives_later_workflow_events(store, tmp_path):
    path, _ = store
    mr.workflow_action(path, "fly", "APPROVE", at=AT, actor_role="REVIEWER")
    record = ms.build_record(path, "fly", at=AT)
    assert record["workflow"]["mission_status"] == "APPROVED"
    output = tmp_path / "approved.json"
    ms.write_record(output, record)
    mr.record_outcome(path, "fly", "NOT_FLOWN", at=LATER,
                      note="Synthetic cancellation", evidence_source="TEST_FIXTURE")
    assert ms.replay_record(output, path)["all_outputs_match"]
    assert ms.read_record(output)["workflow"]["observed_outcome"]["outcome"] == "UNKNOWN"
    assert ms.build_record(path, "fly", at=LATER)["workflow"]["mission_status"] == "CANCELLED"


def test_changed_event_chain_rejected(store):
    path, _ = store
    mr.workflow_action(path, "fly", "APPROVE", at=AT, actor_role="REVIEWER")
    record = ms.build_record(path, "fly", at=AT)
    record["workflow"]["events"][0]["detail"]["actor_role"] = "PILOT"
    with pytest.raises(mr.RecordError, match="chain"):
        ms.validate_record(record)


def test_missing_historical_model_never_falls_back(store, tmp_path):
    path, artifact = store
    output = tmp_path / "mission.json"
    ms.write_record(output, ms.build_record(path, "fly", at=AT))
    (path / "artifacts" / artifact / "reports/d4_d2_frozen_coefficients.csv").unlink()
    with pytest.raises(mr.ReplayUnavailable):
        ms.replay_record(output, path)


def test_unknown_fields_and_nonfinite_metadata_rejected(original_store):
    original = ms.build_record(original_store[0], "fly", at=AT)
    record = deepcopy(original)
    record["unversioned_extra"] = "not allowed"
    with pytest.raises(mr.RecordError):
        ms.validate_record(record)
    record = deepcopy(original)
    record["snapshot"]["assessment"]["inputs"]["soc"] = float("nan")
    with pytest.raises(mr.RecordError):
        ms.validate_record(record)


@pytest.mark.parametrize("at", ["2026-10-25T01:00:00+00:00", "2026-10-26T01:00:00"])
def test_invalid_export_time_rejected(original_store, at):
    with pytest.raises(mr.RecordError):
        ms.build_record(original_store[0], "fly", at=at)
