"""Human-readable exports must preserve saved evidence and refuse overwrite."""
import hashlib
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from src.d6_export import export_tables
from src import mission_record as mr
from src import mission_schema as ms
from src.replay_validation import _spec, AT


def test_export_validates_evidence_and_preserves_missing_and_workflow(tmp_path):
    store = tmp_path / "store"
    artifact = mr.create_artifacts(store)
    mr.save_assessments(store, artifact, [_spec("fly"), _spec("missing_soc", soc=None)])
    records = tmp_path / "records"
    for key in ("fly", "missing_soc"):
        ms.write_record(records / f"{key}.json", ms.build_record(store, key, at=AT))
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in records.glob("*.json")}
    (output,) = export_tables(records, tmp_path / "reading.xlsx")
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(output) as z:
        assert z.testzip() is None
        assert len(ET.fromstring(z.read("xl/workbook.xml")).find("s:sheets", ns)) == 4
        strings = " ".join(" ".join(ET.fromstring(z.read(f"xl/worksheets/sheet{i}.xml")).itertext())
                           for i in range(1, 5))
        assert "Không có dữ liệu" in strings
        assert "BLOCKED" in strings
        for i in (1, 2, 4):
            rows = ET.fromstring(z.read(f"xl/worksheets/sheet{i}.xml")).findall("s:sheetData/s:row", ns)
            assert sum(int(r.attrib["r"]) >= 2 for r in rows) == 2
            assert "Mã đánh giá" in " ".join(rows[0].itertext())
    assert not output.with_suffix(".csv").exists()
    assert not list(tmp_path.rglob("*.inspect.ndjson"))
    assert {p.name for p in tmp_path.iterdir() if p.is_file()} == {"reading.xlsx"}
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in records.glob("*.json")}
    with pytest.raises(FileExistsError):
        export_tables(records, output)


def test_empty_input_does_not_create_a_successful_workbook(tmp_path):
    records = tmp_path / "records"
    records.mkdir()
    with pytest.raises(ValueError, match="No D6 records"):
        export_tables(records, tmp_path / "empty.xlsx")
    assert not (tmp_path / "empty.xlsx").exists()


def test_validation_pipeline_has_only_documented_outputs(tmp_path):
    from src.d6_validation import validate

    out = tmp_path / "run"
    assert validate(out)
    assert {p.name for p in out.iterdir()} == {
        "records", "store", "checks.json", "d6_report.md",
        "mission_record.schema.json", "mission_records.xlsx",
        "replay_results.csv", "replay_results.json", "validation_manifest.json",
    }
    import json
    manifest = json.loads((out / "validation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["record_count"] == 12
    assert len(list((out / "records").glob("*.json"))) == 12
    assert not list(out.rglob("*.inspect.ndjson"))
    for name, expected in manifest["outputs"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == expected
