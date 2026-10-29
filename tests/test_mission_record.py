"""D5 historical replay and approval gates, independent of legacy D3 API."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from src import mission_record as mr

AT = "2026-10-26T08:00:00+00:00"
WEATHER = dict(observed_at="2026-10-26T07:55:00+00:00",
               valid_until="2026-10-26T08:30:00+00:00", source="SYNTHETIC_TEST_FIXTURE")
INPUTS = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50, distance_2d_m=472,
              wind_forecast_ms=3, ambient_temp_c=15, soc=.7, soh=.95,
              battery_type="TB47D", profile="M100_stock", reserve_factor=.2)


def spec(assessment_id="fly", **changes):
    result = dict(assessment_id=assessment_id, mission_id="mission", assessed_at=AT,
                  inputs={**INPUTS, **changes}, weather=deepcopy(WEATHER), artifact_id="test")
    return result


@pytest.fixture(scope="module")
def original_store(tmp_path_factory):
    store = tmp_path_factory.mktemp("d5-replay")
    artifact = mr.create_artifacts(store)
    cases = [spec(), spec("conditional", soc=.235), spec("veto", wind_forecast_ms=12, soc=1),
             spec("cmu", profile="CMU_instrumented"), spec("missing", soc=None)]
    # Separate missions avoid superseding unrelated representative cases.
    for case in cases:
        case["mission_id"] = f"mission_{case['assessment_id']}"
    mr.save_assessments(store, artifact, cases)
    valid = spec("mitigated", soc=.24)
    valid.update(mission_id="mission_conditional", assessed_at="2026-10-26T08:02:00+00:00",
                 previous_assessment_id="conditional",
                 mitigation=dict(id="M1", approved_by_role="REVIEWER", approved_at="2026-10-26T08:01:00+00:00"))
    fake = deepcopy(valid)
    fake["assessment_id"] = "fake"
    fake["mitigation"]["id"] = "ANY_STRING_IS_NOT_A_MITIGATION"
    degraded = spec("degraded", soc=.235)
    degraded.update(mission_id="mission_fly", assessed_at="2026-10-26T08:02:00+00:00", previous_assessment_id="fly")
    mr.save_assessments(store, artifact, [valid, fake, degraded])
    return store, artifact


@pytest.fixture
def saved(tmp_path, original_store):
    original, artifact = original_store
    store = tmp_path / "records"
    shutil.copytree(original, store)
    return store, artifact


def test_archived_replay_all_verdicts_and_mitigation(original_store):
    store, _ = original_store
    rows = mr.replay(store, ["fly", "conditional", "veto", "cmu", "missing", "mitigated", "fake", "degraded"])
    assert {r["replayed_verdict"] for r in rows} == {"FLY", "CONDITIONAL", "NO_FLY", "INSUFFICIENT_DATA"}
    assert all(r["exact_verdict_match"] and r["all_outputs_match"] for r in rows)
    assert max(r["max_absolute_difference"] for r in rows) == 0


def test_relative_store_path_works_from_project_terminal(saved, monkeypatch):
    monkeypatch.chdir(saved[0].parent)
    assert mr.replay(Path("records"), ["cmu"])[0]["all_outputs_match"]


def test_matching_verdict_does_not_hide_wrong_numerical_outputs(saved):
    path = saved[0] / "snapshots/fly.json"
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    wrapper["assessment"]["result"]["decision"]["margin_Wh"] += 1
    wrapper["sha256"] = mr.digest(wrapper["assessment"])
    path.write_text(json.dumps(wrapper), encoding="utf-8")
    result = mr.replay(saved[0], ["fly"])[0]
    assert result["exact_verdict_match"]
    assert not result["all_outputs_match"]
    assert "result.decision.margin_Wh" in result["mismatched_fields"]
    assert result["max_absolute_difference"] == 1


def test_saved_prediction_matches_upstream_frozen_model(original_store):
    import pandas as pd
    from src.uncertainty import load_context
    context = load_context()
    stored = mr.load_snapshot(original_store[0], "fly").data
    assert stored["result"]["prediction_Wh"] == pytest.approx(context.model.predict(INPUTS, context.d4), abs=1e-12)


def test_snapshot_nested_data_cannot_mutate_file(saved):
    store, _ = saved
    record = mr.load_snapshot(store, "fly")
    nested = record.data
    nested["inputs"]["soc"] = 0
    assert record.data["inputs"]["soc"] == .7
    assert mr.load_snapshot(store, "fly").sha256 == record.sha256


def test_assessment_id_cannot_be_overwritten(saved):
    with pytest.raises(FileExistsError):
        mr.save_assessments(saved[0], saved[1], [spec()])


def test_modified_snapshot_is_rejected(saved):
    path = saved[0] / "snapshots/fly.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["assessment"]["inputs"]["soc"] = 0
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(mr.RecordError, match="checksum"):
        mr.load_snapshot(saved[0], "fly")


@pytest.mark.parametrize("name", ["configs/d3_protocol.yaml", "reports/d4_d2_frozen_coefficients.csv",
                                  "src/decision_rules.py", "src/mission_record.py"])
def test_missing_historical_artifact_never_uses_current_source(saved, name):
    (saved[0] / "artifacts" / saved[1] / name).unlink()
    with pytest.raises(mr.ReplayUnavailable):
        mr.replay(saved[0], ["fly"])


def test_modified_archived_config_is_rejected(saved):
    path = saved[0] / "artifacts" / saved[1] / "configs/d3_protocol.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n# tampering\n", encoding="utf-8")
    with pytest.raises(mr.ReplayUnavailable, match="changed"):
        mr.replay(saved[0], ["fly"])


def test_unavailable_dependency_version_is_reported(saved, monkeypatch):
    original = mr.runtime()
    original["python"] = "UNAVAILABLE_VERSION"
    monkeypatch.setattr(mr, "runtime", lambda: original)
    with pytest.raises(mr.ReplayUnavailable, match="versions unavailable"):
        mr.replay(saved[0], ["fly"])


def test_new_live_config_invalidates_approval_without_changing_historical_replay(saved, tmp_path):
    store, artifact = saved
    archive = store / "artifacts" / artifact
    live = tmp_path / "changed-live-source"
    shutil.copytree(archive, live)
    config = live / "configs/d3_protocol.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("primary_Wh: 99.9", "primary_Wh: 50.0")
                      + "\n# simulated new configuration\n", encoding="utf-8")
    before = mr.load_snapshot(store, "cmu").sha256
    state = mr.workflow_status(store, "cmu", at=AT, root=live)
    assert "ARTIFACT_CHANGED:configs/d3_protocol.yaml" in state["stale_reasons"]
    assert mr.replay(store, ["cmu"])[0]["all_outputs_match"]
    assert mr.load_snapshot(store, "cmu").sha256 == before


@pytest.mark.parametrize("key", mr.NUMERIC_INPUTS)
@pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
def test_missing_or_nonfinite_required_input_cannot_produce_fly(key, value):
    item, _ = mr.normalize(spec(**{key: value}))
    result = mr._evaluate(item)
    assert result["verdict"] in ("INSUFFICIENT_DATA", "NO_FLY")
    assert not result["review_eligible"]


@pytest.mark.parametrize("changes", [dict(soc=1.5), dict(soh=-.01), dict(payload_g=-1),
                                      dict(distance_2d_m=0), dict(speed_commanded_ms=0),
                                      dict(battery_type="unknown"), dict(profile="unknown"),
                                      dict(reserve_factor=-1), dict(soc=True)])
def test_invalid_inputs_block(changes):
    assert mr._evaluate(spec(**changes))["verdict"] == "NO_FLY"


@pytest.mark.parametrize("weather", [{}, {**WEATHER, "valid_until": AT},
                                    {**WEATHER, "observed_at": "2026-10-26T08:01:00+00:00"},
                                    {**WEATHER, "valid_until": "2026-10-26T08:30:00"},
                                    {**WEATHER, "source": None}])
def test_expired_missing_or_invalid_weather_blocks_fly(weather):
    item = spec()
    item["weather"] = weather
    result = mr._evaluate(item)
    assert result["verdict"] == "INSUFFICIENT_DATA"
    assert result["assessment_status"] == "STALE"
    assert not result["review_eligible"]


def test_known_veto_still_returns_no_fly_even_when_weather_missing():
    item = spec(wind_forecast_ms=12, soc=1)
    item["weather"] = {}
    assert mr._evaluate(item)["verdict"] == "NO_FLY"


def test_fly_requires_human_approval_before_start(saved):
    store, artifact = saved
    # cmu/missing/conditional have separate missions; choose a new isolated stock case.
    spec0 = spec("standalone")
    spec0["mission_id"] = "standalone"
    mr.save_assessments(store, artifact, [spec0])
    with pytest.raises(mr.RecordError, match="approval"):
        mr.workflow_action(store, "standalone", "START", at=AT)
    mr.workflow_action(store, "standalone", "APPROVE", at=AT, actor_role="REVIEWER")
    assert mr.workflow_status(store, "standalone", at=AT)["may_proceed"]
    mr.workflow_action(store, "standalone", "START", at=AT)
    with pytest.raises(mr.RecordError, match="already started"):
        mr.workflow_action(store, "standalone", "START", at=AT)


def test_valid_mitigation_reassessed_but_arbitrary_name_does_not_unlock_conditional(saved):
    store, _ = saved
    valid = mr.load_snapshot(store, "mitigated").data
    assert valid["result"]["verdict"] == "CONDITIONAL"
    assert valid["result"]["mitigation_validated"]
    assert valid["result"]["prediction_Wh"] == pytest.approx(mr.load_snapshot(store, "conditional").data["result"]["prediction_Wh"])
    mr.workflow_action(store, "mitigated", "APPROVE", at="2026-10-26T08:03:00+00:00", actor_role="REVIEWER")
    assert mr.workflow_status(store, "mitigated", at="2026-10-26T08:03:00+00:00")["may_proceed"]
    assert not mr.load_snapshot(store, "fake").data["result"]["mitigation_validated"]
    with pytest.raises(mr.RecordError, match="blocked"):
        mr.workflow_action(store, "fake", "APPROVE", at="2026-10-26T08:03:00+00:00", actor_role="REVIEWER")


@pytest.mark.parametrize("assessment_id", ["conditional", "veto", "cmu", "missing", "degraded"])
def test_blocked_assessments_cannot_be_overridden_by_reviewer(saved, assessment_id):
    with pytest.raises(mr.RecordError, match="blocked"):
        mr.workflow_action(saved[0], assessment_id, "APPROVE", at="2026-10-26T08:03:00+00:00", actor_role="REVIEWER")


@pytest.mark.parametrize("patch", [dict(soc=.6), dict(soh=.8), dict(payload_g=500), dict(altitude_m=75),
                                  dict(distance_2d_m=500), dict(wind_forecast_ms=4), dict(ambient_temp_c=14),
                                  dict(battery_type="TB48D"), dict(profile="CMU_instrumented"),
                                  dict(reserve_factor=.3), dict(speed_commanded_ms=10)])
def test_every_changed_safety_input_marks_stale(saved, patch):
    state = mr.workflow_status(saved[0], "conditional", at=AT, current_inputs=patch)
    assert any(x.startswith("INPUT_CHANGED:") for x in state["stale_reasons"])
    assert not state["may_proceed"]


def test_exact_expiry_boundary_blocks_previously_approved_assessment(saved):
    store, _ = saved
    mr.workflow_action(store, "mitigated", "APPROVE", at="2026-10-26T08:03:00+00:00", actor_role="REVIEWER")
    before = mr.load_snapshot(store, "mitigated").sha256
    with pytest.raises(mr.RecordError, match="WEATHER_EXPIRED"):
        mr.workflow_action(store, "mitigated", "START", at=WEATHER["valid_until"])
    assert mr.read_events(store, "mitigated")[-1]["event_type"] == "STALE"
    assert mr.load_snapshot(store, "mitigated").sha256 == before


def test_superseded_assessment_stale_and_new_approval_not_inherited(saved):
    state = mr.workflow_status(saved[0], "fly", at="2026-10-26T08:03:00+00:00")
    assert "SUPERSEDED_BY:degraded" in state["stale_reasons"]
    assert not mr.workflow_status(saved[0], "degraded", at="2026-10-26T08:03:00+00:00")["approved"]


def test_events_are_append_only_and_tampering_is_detected(saved):
    store, _ = saved
    mr.record_outcome(store, "cmu", "UNKNOWN", at=AT)
    first = (store / "workflow_events/cmu/000001.json").read_bytes()
    mr.record_outcome(store, "cmu", "NOT_FLOWN", at=AT, note="Research-only fixture", evidence_source="fixture")
    assert (store / "workflow_events/cmu/000001.json").read_bytes() == first
    path = store / "workflow_events/cmu/000002.json"
    path.write_bytes(path.read_bytes().replace(b"NOT_FLOWN", b"COMPLETED"))
    with pytest.raises(mr.RecordError, match="chain"):
        mr.read_events(store, "cmu")


def test_outcome_is_not_inferred_from_recommendation(saved):
    store, _ = saved
    assert mr.workflow_status(store, "veto", at=AT)["observed_outcome"]["outcome"] == "UNKNOWN"
    with pytest.raises(mr.RecordError, match="independent"):
        mr.record_outcome(store, "veto", "COMPLETED", at=AT)
    before = mr.load_snapshot(store, "veto").sha256
    mr.record_outcome(store, "veto", "NOT_FLOWN", at=AT, note="Cancelled by fixture operator", evidence_source="fixture log")
    assert mr.load_snapshot(store, "veto").sha256 == before
    assert mr.workflow_status(store, "veto", at=AT)["observed_outcome"]["outcome"] == "NOT_FLOWN"


def test_naive_timestamp_rejected():
    with pytest.raises(mr.RecordError, match="timezone"):
        mr.utc("2026-10-26T08:00:00")


def test_new_assessment_of_existing_mission_must_link_prior_record(saved):
    item = spec("unlinked")
    item["mission_id"] = "mission_conditional"
    with pytest.raises(mr.RecordError, match="previous_assessment_id"):
        mr.save_assessments(saved[0], saved[1], [item])


def test_newest_mission_assessment_invalidates_older_sibling(saved):
    item = spec("newest")
    item.update(mission_id="mission_conditional", previous_assessment_id="fake",
                assessed_at="2026-10-26T08:04:00+00:00")
    mr.save_assessments(saved[0], saved[1], [item])
    state = mr.workflow_status(saved[0], "mitigated", at="2026-10-26T08:05:00+00:00")
    assert "SUPERSEDED_BY:newest" in state["stale_reasons"]
    assert not state["may_proceed"]


@pytest.mark.parametrize("changes", [dict(profile={}), dict(battery_type=[])])
def test_malformed_categorical_input_is_saved_as_no_fly(changes):
    assert mr._evaluate(spec(**changes))["verdict"] == "NO_FLY"
