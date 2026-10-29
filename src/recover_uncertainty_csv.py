"""Recover an exact historical CSV from its hash-verified JSON, into a new folder.

Never changes the existing CSV or its manifest. Bounded-memory JSON-array reader;
recovery succeeds only if the reconstructed CSV has the original declared hash.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime,timezone
import json
import math
from pathlib import Path

import pandas as pd

from src.sensitivity import sha


def iter_records(path,block_size=1024*1024):
    decoder=json.JSONDecoder()
    with Path(path).open(encoding='utf-8') as stream:
        buffer='';position=0;eof=False
        def refill():
            nonlocal buffer,position,eof
            more=stream.read(block_size)
            buffer=buffer[position:]+more;position=0
            eof=not more
        def token():
            nonlocal position
            while True:
                while position<len(buffer) and buffer[position].isspace():position+=1
                if position<len(buffer):return buffer[position]
                if eof:raise ValueError('Truncated JSON array')
                refill()
        if token()!='[':raise ValueError('Expected a top-level JSON array')
        position+=1
        if token()==']':position+=1
        else:
            while True:
                while True:
                    try:record,end=decoder.raw_decode(buffer,position)
                    except json.JSONDecodeError as exc:
                        if eof:raise ValueError('Invalid/truncated JSON record') from exc
                        refill();continue
                    break
                if not isinstance(record,dict):raise ValueError('Expected JSON object records')
                position=end
                yield record
                separator=token()
                position+=1
                if separator==']':break
                if separator!=',':raise ValueError('Expected comma between JSON records')
                token()  # skip whitespace before the next object
        if buffer[position:].strip() or stream.read().strip():raise ValueError('Trailing JSON content')


def same_value(expected,text):
    try:
        if isinstance(expected,(dict,list)):return json.loads(text)==expected
        if isinstance(expected,bool):return text.strip().lower()==str(expected).lower()
        if expected is None:return text==''
        if isinstance(expected,(int,float)):return float(text)==expected
        return text==expected
    except (TypeError,ValueError):return False


def recover(run,out,chunksize=10000):
    run,out=Path(run),Path(out)
    if out.exists():raise FileExistsError('Use a new recovery directory')
    status=json.loads((run/'run_status.json').read_text(encoding='utf-8'))
    original_json=run/'monte_carlo_fractions.json'
    original_csv=run/'monte_carlo_fractions.csv'
    if sha(original_json)!=status['output_hashes'][original_json.name]:raise ValueError('Original JSON hash differs; cannot recover')
    original_csv_hash=sha(original_csv)
    out.mkdir(parents=True)
    target=out/original_csv.name
    differences=0;numeric_differences=0;max_difference=0.;examples=[];count=0;pending=[];columns=None;header=True
    with original_csv.open(encoding='utf-8-sig',newline='') as stream:
        current=csv.DictReader(stream)
        for record in iter_records(original_json):
            if columns is None:columns=list(record)
            if list(record)!=columns:raise ValueError('JSON field order/schema differs across records')
            current_row=next(current,None)
            for key,value in record.items():
                actual=current_row.get(key) if current_row else None
                if not same_value(value,actual):
                    differences+=1
                    if isinstance(value,(int,float)) and not isinstance(value,bool):
                        try:
                            delta=abs(float(actual)-value)
                            if math.isfinite(delta):max_difference=max(max_difference,delta)
                            numeric_differences+=1
                        except (TypeError,ValueError):pass
                    if len(examples)<8:examples.append(dict(record_index=count+1,field=key,expected=value,current=actual))
            pending.append({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in record.items()})
            count+=1
            if len(pending)>=chunksize:
                pd.DataFrame(pending,columns=columns).to_csv(target,index=False,mode='w' if header else 'a',header=header)
                pending=[];header=False
                if count%100000==0:print(f'Recovered {count:,} saved rows',flush=True)
        extra=sum(1 for _ in current)
    if pending:pd.DataFrame(pending,columns=columns).to_csv(target,index=False,mode='w' if header else 'a',header=header)
    recovered_hash=sha(target)
    exact=recovered_hash==status['output_hashes'][original_csv.name]
    audit=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),status='RECOVERED_EXACT_ORIGINAL_CSV' if exact else 'FAILED_CSV_HASH_DIFFERENT',
               source_json=str(original_json.resolve()),source_json_sha256=sha(original_json),
               existing_csv=str(original_csv.resolve()),existing_csv_sha256=original_csv_hash,
               expected_original_csv_sha256=status['output_hashes'][original_csv.name],
               recovered_csv=str(target.resolve()),recovered_csv_sha256=recovered_hash,exact_original_hash_match=exact,
               recovered_rows=count,existing_csv_extra_rows=extra,semantic_difference_cells=differences,
               scalar_numeric_difference_cells=numeric_differences,maximum_scalar_absolute_difference=max_difference,
               first_differences=examples,original_files_modified=False,simulation_rerun=False)
    (out/'recovery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if not exact:raise ValueError('Reconstructed CSV does not match the original declared hash')
    print(f'Exact CSV recovered: {count:,} rows; current CSV semantic differences: {differences}; no original files changed.',flush=True)
    return audit


def recover_oat_explained(run,out):
    from src.sensitivity import ERROR_FACTORS
    from src.sensitivity_report import LABELS
    run,out=Path(run),Path(out)
    if out.exists():raise FileExistsError('Use a new recovery directory')
    metadata=json.loads((run/'input_manifest.json').read_text(encoding='utf-8'))
    report=json.loads((run/'report_manifest.json').read_text(encoding='utf-8'))
    source=run/'fly_case_diagnosis.csv'
    if sha(source)!=metadata['output_hashes'][source.name]:raise ValueError('Diagnosis source changed')
    generator=Path(__file__).resolve().parent/'sensitivity_report.py'
    if sha(generator)!=report['code_sha256']:raise ValueError('Original report generator version unavailable')
    diagnosis=pd.read_csv(source)
    explained=diagnosis.rename(columns={'scenario_id':'ID','battery_type':'Loai_pin',
        'failure_fraction_min':'Ty_le_MC_thieu_min','failure_fraction_max':'Ty_le_MC_thieu_max',
        'soc_error':'SoC_don_le','soh_error':'SoH_don_le','wind_error':'Gio_don_le',
        'kappa_error':'Kappa_don_le','energy_error':'Phan_du_nang_luong_don_le'}).copy()
    def explanation(row):
        active=[LABELS[name] for name in ERROR_FACTORS if row[name]]
        return ('Có điểm thiếu dự trữ khi chỉ thay riêng: '+', '.join(active)+'. Các yếu tố khác giữ ở đầu vào gốc.') if active else (
            'Không thiếu khi đổi riêng từng yếu tố trên lưới chính; có mẫu thiếu trong Monte Carlo phối hợp nhiều sai lệch.')
    explained['Dien_giai']=diagnosis.apply(explanation,axis=1)
    explained=explained.drop(columns='single_factor_response')
    out.mkdir(parents=True)
    target=out/'fly_cases_explained.csv'
    explained.to_csv(target,index=False,encoding='utf-8-sig')
    expected=report['output_hashes'][target.name]
    if sha(target)!=expected:raise ValueError('Friendly CSV does not match original declared hash')
    audit=dict(status='RECOVERED_EXACT_OAT_EXPLAINED_CSV',source_diagnosis=str(source.resolve()),source_sha256=sha(source),
               recovered_csv=str(target.resolve()),recovered_csv_sha256=sha(target),expected_original_csv_sha256=expected,
               existing_csv=str((run/target.name).resolve()),existing_csv_sha256=sha(run/target.name),
               recovered_rows=len(explained),semantic_tables_equal=pd.read_csv(target).equals(pd.read_csv(run/target.name)),
               exact_original_hash_match=True,original_files_modified=False,simulation_rerun=False)
    (out/'recovery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Exact OAT explanation CSV recovered: {len(explained)} rows.',flush=True)
    return audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--kind',choices=['mc','oat_explained'],default='mc')
    args=parser.parse_args()
    (recover if args.kind=='mc' else recover_oat_explained)(args.run,args.out)


if __name__=='__main__':main()
