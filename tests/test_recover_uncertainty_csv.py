import json

import pandas as pd
import pytest

from src.recover_uncertainty_csv import iter_records,recover
from src.sensitivity import sha


def test_incremental_parser_handles_split_objects_strings_and_unicode(tmp_path):
    rows=[dict(scenario_id=1,nested={'text':'chuỗi " } , ['},value=1.2345),dict(scenario_id=2,nested=[],value=None)]
    path=tmp_path/'source.json';path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    assert list(iter_records(path,block_size=3))==rows


@pytest.mark.parametrize('text',['[{"a":1}', '[{"a":1}] trailing', '[{"a":1},]', '{"a":1}'])
def test_invalid_json_is_not_silently_recovered(tmp_path,text):
    path=tmp_path/'bad.json';path.write_text(text,encoding='utf-8')
    with pytest.raises(ValueError):list(iter_records(path,block_size=4))


def test_reconstruction_matches_original_export_and_preserves_edited_csv(tmp_path):
    source=tmp_path/'run';source.mkdir()
    rows=[dict(scenario_id=1,rate=1.0,ok=True,detail={'x':.123456789}),dict(scenario_id=2,rate=.123456789,ok=False,detail={'x':2})]
    raw=source/'monte_carlo_fractions.json';raw.write_text(json.dumps(rows,indent=2),encoding='utf-8')
    csv=source/'monte_carlo_fractions.csv'
    pd.DataFrame([{k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows]).to_csv(csv,index=False)
    expected=sha(csv)
    (source/'run_status.json').write_text(json.dumps(dict(output_hashes={raw.name:sha(raw),csv.name:expected})),encoding='utf-8')
    csv.write_text(csv.read_text(encoding='utf-8').replace('.123456789','.123457'),encoding='utf-8')
    edited=sha(csv)
    audit=recover(source,tmp_path/'recovery',chunksize=1)
    assert audit['exact_original_hash_match'] and audit['recovered_rows']==2
    assert audit['semantic_difference_cells']>0
    assert sha(csv)==edited
    assert sha(tmp_path/'recovery'/csv.name)==expected
