"""Compile a traceable D5 report from completed saved development runs.

Verifies manifests and quantitative reconciliation; does not rerun simulations,
train a model, change historical outputs or sign off a reviewer on their behalf.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from src.failure_catalogue import TITLES,clean,write_json
from src.sensitivity import sha
from src.uncertainty import ROOT,load_context

RUNS=dict(mc="all_scenarios_dev_01",review="fly_reserve_review_20261025_01",
          oat="oat_all_scenarios_20261025_01",replay="replay_workflow_20261026_03",
          catalogue="failure_catalogue_20261026_03",matched="matched_counterfactual_20261026_01")
CONFIG_NAMES={"RESIDUAL_ONLY":"Chỉ sai số dự đoán năng lượng", "PRIMARY_INDEPENDENT":"Các sai số độc lập, khoảng chính",
              "WIDER_RANGES":"Khoảng sai số rộng", "ADVERSE_RESIDUAL_POOL":"Lấy sai số phía dự đoán thiếu",
              "ADVERSE_DEPENDENCE":"Ghép các sai lệch theo hướng bất lợi"}


def require(condition,message):
    if not bool(condition):raise ValueError(message)


class Evidence:
    def __init__(self,alternatives=None):
        self.files={}
        self.alternatives={str(Path(k).resolve()):Path(v).resolve() for k,v in (alternatives or {}).items()}
        self.replacements={}
        self.missing_optional={}

    def verify(self,path,expected=None):
        path=Path(path).resolve();key=str(path)
        info=path.stat()
        signature=(info.st_size,info.st_mtime_ns)
        if key not in self.files:
            self.files[key]=dict(sha256=sha(path),size_bytes=info.st_size,mtime_ns=info.st_mtime_ns)
        elif signature!=(self.files[key]["size_bytes"],self.files[key]["mtime_ns"]):
            raise ValueError(f"Evidence changed during consolidation: {path}")
        if expected is not None and self.files[key]["sha256"]!=expected:
            if key not in self.alternatives:raise ValueError(f"Evidence hash mismatch: {path}")
            replacement=self.alternatives[key]
            self.verify(replacement,expected)
            self.replacements[key]=dict(current_sha256=self.files[key]["sha256"],expected_original_sha256=expected,
                                        verified_replacement=str(replacement))
            return expected
        return self.files[key]["sha256"]

    def json(self,path,expected=None):
        self.verify(path,expected)
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def csv(self,path,**kwargs):
        self.verify(path)
        replacement=self.replacements.get(str(Path(path).resolve()))
        return pd.read_csv(replacement["verified_replacement"] if replacement else path,**kwargs)

    def outputs(self,directory,manifest,key,allow_missing_suffixes=()):
        for relative,expected in manifest[key].items():
            path=Path(directory)/relative
            if not path.exists() and path.suffix in allow_missing_suffixes:
                self.missing_optional[str(path.resolve())]=dict(expected_sha256=expected,reason='Optional historical export; not used as current evidence')
            else:self.verify(path,expected)


def one(frame,message):
    require(len(frame)==1,message)
    return frame.iloc[0]


def candidate_fly_count(row):
    """Reference partitions cover all scored cases; recover total FLY consistently."""
    result=(int(row.false_safe_count)+int(row.reference_feasible)-int(row.unnecessary_rejection_count)
            -int(row.conditional_count_among_feasible))
    require(0<=result<=int(row.scored_scenarios),"Reference partition does not reconcile candidate FLY")
    return result


def validate_mc(frame,manifest):
    keys=["assumption_config_id","battery_type","seed"]
    require(not frame.duplicated(keys).any(),"Duplicate MC summary groups")
    expected=len(manifest["configurations"])*len(manifest["battery_types"])*len(manifest["seeds"])
    require(len(frame)==expected,"Missing MC groups")
    require(set(frame.seed)==set(manifest["seeds"]),"MC seed mismatch")
    require(set(frame.battery_type)==set(manifest["battery_types"]),"MC battery mismatch")
    require(set(frame.assumption_config_id)==set(manifest["configurations"]),"MC configuration mismatch")
    n=len(manifest["selected_scenario_ids"])
    require(frame.scenario_count.eq(n).all(),"MC population differs between summary groups")
    require(frame.draws_total.eq(n*manifest["draws_per_scenario"]).all(),"MC draw counts differ from declared settings")
    require((frame.valid_draws+frame.invalid_draws).eq(frame.draws_total).all(),"MC valid/invalid counts do not reconcile")
    require(frame.energy_success_count.le(frame.valid_draws).all() and frame.joint_success_count.le(frame.energy_success_count).all(),"MC numerators exceed denominators")
    for prefix,count in (("energy","energy_success_count"),("joint","joint_success_count")):
        fractions=frame[count]/frame.valid_draws.replace(0,np.nan)
        require(np.allclose(fractions,frame[f"{prefix}_feasibility_fraction"],rtol=1e-12,atol=1e-12,equal_nan=True),"MC weighted fractions differ from counts")
    return dict(scenarios=n,result_rows=n*expected,total_draws=int(frame.draws_total.sum()),
                valid_draws=int(frame.valid_draws.sum()),invalid_draws=int(frame.invalid_draws.sum()))


def table(headers,rows):
    def cell(value):return str(value).replace("|","/").replace("\n"," ")
    return ["| "+" | ".join(map(cell,headers))+" |","|"+"---|"*len(headers)]+[
        "| "+" | ".join(cell(v) for v in row)+" |" for row in rows]


def link(path,label=None):
    path=Path(path).resolve()
    return f"[{label or path.name}](<{path.as_posix()}>)"


def verified_link(registry,path):
    path=Path(path).resolve()
    replacement=registry.replacements.get(str(path))
    return link(replacement['verified_replacement'],f'{path.name} (bản khôi phục đúng nguồn gốc)') if replacement else link(path)


def ratio(count,denominator):
    if not denominator:return f"{count}/0 (NA)"
    return f"{int(count)}/{int(denominator)} ({100*count/denominator:.2f}%)"


def collect(root):
    root=Path(root)
    context=load_context(root)
    recovery=root/'reports/d5/mc_csv_recovery_20261026_01'
    recovered=recovery/'monte_carlo_fractions.csv'
    original=root/'reports/d5'/RUNS['mc']/'monte_carlo_fractions.csv'
    alternatives={original:recovered} if recovered.exists() else {}
    friendly=root/'reports/d5/oat_csv_recovery_20261026_01/fly_cases_explained.csv'
    if friendly.exists():alternatives[root/'reports/d5'/RUNS['oat']/'fly_cases_explained.csv']=friendly
    evidence=Evidence(alternatives)
    evidence.verify(__file__)
    directories={name:root/"reports/d5"/run for name,run in RUNS.items()}
    for relative,expected in context.input_hashes.items():evidence.verify(root/relative,expected)
    proposal=Path(context.d5["sources"]["primary_proposal"]["path"])
    evidence.verify(proposal)
    proposal_lines=proposal.read_text(encoding="utf-8").splitlines()
    acceptance=[(i+1,line) for i,line in enumerate(proposal_lines) if "**D5 — Robustness package**" in line]
    require(len(acceptance)==1,"Cannot identify proposal D5 acceptance criteria")
    proposal_line=acceptance[0][0]
    mc_status=evidence.json(directories["mc"]/"run_status.json")
    require(mc_status["status"]=="COMPLETED_DEVELOPMENT_PARTIAL","MC source is not completed development evidence")
    mc_meta=evidence.json(directories["mc"]/"input_manifest.json",mc_status["input_manifest_hash"])
    evidence.outputs(directories["mc"],mc_status,"output_hashes")
    mc=evidence.csv(directories["mc"]/"terminal_summary.csv")
    require(mc.input_manifest_hash.eq(mc_status["input_manifest_hash"]).all(),"MC summary points to a different manifest")
    mc_numbers=validate_mc(mc,mc_meta)
    recovery_audit=None
    if evidence.replacements:
        recovery_audit=evidence.json(recovery/'recovery_audit.json')
        require(recovery_audit['exact_original_hash_match'] and recovery_audit['recovered_rows']==mc_numbers['result_rows'],
                'CSV recovery evidence is not exact/complete')
    review_meta=evidence.json(directories["review"]/"analysis_manifest.json")
    evidence.outputs(directories["review"],review_meta,"output_hashes")
    require(review_meta["source_input_manifest_hash"]==mc_status["input_manifest_hash"],"FLY review source differs from MC")
    require(review_meta["source_csv_sha256"]==mc_status["output_hashes"]["monte_carlo_fractions.csv"],"FLY review CSV source differs")
    review=evidence.csv(directories["review"]/"fly_case_summary.csv")
    priority=evidence.csv(directories["review"]/"fly_priority_cases.csv")
    oat_meta=evidence.json(directories["oat"]/"input_manifest.json")
    require(oat_meta["status"]=="COMPLETED_OAT_DEVELOPMENT","OAT not completed")
    require(oat_meta["source_manifest_hash"]==mc_status["input_manifest_hash"],"OAT source differs from MC")
    evidence.outputs(directories["oat"],oat_meta,"output_hashes")
    figure_meta=evidence.json(directories["oat"]/"report_manifest.json")
    require(figure_meta["source_manifest_sha256"]==evidence.verify(directories["oat"]/"input_manifest.json"),"Figure source manifest differs")
    evidence.outputs(directories["oat"],figure_meta,"output_hashes",allow_missing_suffixes=('.svg',))
    figure_rebuild=root/'reports/d5/figure_rebuild_20261026_01'
    if evidence.missing_optional:
        rebuilt=evidence.json(figure_rebuild/'figure_rebuild_audit.json')
        require(rebuilt['all_png_match_original'],'Rebuilt figures do not match verified PNG originals')
        rebuild_meta=evidence.json(figure_rebuild/'report_manifest.json')
        evidence.outputs(figure_rebuild,rebuild_meta,'output_hashes')
        if friendly.exists():evidence.json(friendly.parent/'recovery_audit.json')
    curves=evidence.csv(directories["oat"]/"one_factor_curves.csv",dtype={"point_id":str})
    fixed=evidence.csv(directories["oat"]/"reference_metrics.csv",dtype={"point_id":str})
    ranks=evidence.csv(directories["oat"]/"sensitivity_ranking.csv")
    diagnosis=evidence.csv(directories["oat"]/"fly_case_diagnosis.csv")
    require(int(curves.valid_scenarios.sum()+curves.invalid_perturbations.sum())==oat_meta["total_evaluations"],"OAT totals differ")
    require(len(diagnosis)==oat_meta["focus_cases"],"Missing focused FLY cases")
    replay_meta=evidence.json(directories["replay"]/"validation_manifest.json")
    require(replay_meta["status"]=="COMPLETED_REPLAY_WORKFLOW_DEVELOPMENT","Replay evidence incomplete")
    evidence.outputs(directories["replay"],replay_meta,"outputs")
    replay=evidence.csv(directories["replay"]/"replay_results.csv")
    workflow=evidence.json(directories["replay"]/"workflow_checks.json")
    require(len(replay)==replay_meta["assessment_count"] and replay.all_outputs_match.all(),"Historical replay mismatch")
    require(len(workflow)==replay_meta["workflow_checks_total"] and all(r["passed"] for r in workflow),"Workflow check failed")
    catalogue_meta=evidence.json(directories["catalogue"]/"catalogue_manifest.json")
    evidence.outputs(directories["catalogue"],catalogue_meta,"outputs")
    catalogue=evidence.json(directories["catalogue"]/"failure_catalogue.json")
    require(len(catalogue)==catalogue_meta["case_count"] and len(set(c["category"] for c in catalogue))==catalogue_meta["category_count"],"Catalogue coverage differs")
    matched_status=evidence.json(directories["matched"]/"run_status.json")
    require(matched_status["status"]=="COMPLETED_MATCHED_REFERENCE_AND_COUNTERFACTUAL_DEVELOPMENT","Matched/counterfactual run incomplete")
    matched_meta=evidence.json(directories["matched"]/"input_manifest.json",matched_status["input_manifest_sha256"])
    evidence.outputs(directories["matched"],matched_status,"output_hashes")
    ref_summary=evidence.csv(directories["matched"]/"baseline_reference_comparison.csv")
    matched_metrics=evidence.csv(directories["matched"]/"matched_reference_metrics.csv",dtype={"point_id":str})
    comparisons=evidence.csv(directories["matched"]/"fixed_vs_matched_metrics.csv",dtype={"point_id":str})
    proposals=evidence.csv(directories["matched"]/"counterfactual_proposals.csv")
    cases=evidence.csv(directories["matched"]/"counterfactual_case_summary.csv")
    cf_summary=evidence.csv(directories["matched"]/"counterfactual_validation_summary.csv")
    selection=evidence.json(directories["matched"]/"selection_manifest.json")
    statistics=matched_status["statistics"]
    require(statistics["matched"]["evaluated_rows"]==oat_meta["total_evaluations"],"Matched reference population differs")
    require(len(proposals)==statistics["counterfactual"]["offered_proposals"] and len(cases)==selection["case_count"],"Counterfactual rows differ")
    require(proposals.proposed_by_candidate.all() and proposals.candidate_verdict.eq("FLY").all(),"Invalid model-proposal evidence")
    for battery,group in proposals.groupby("baseline_battery"):
        for ref in (1,2):
            row=one(cf_summary[(cf_summary.battery_type==battery)&(cf_summary.action=="ALL")&(cf_summary.support=="all")
                               &(cf_summary.mapping=="PRIMARY_FEASIBLE_ONLY")&(cf_summary.reference_model==f"REF-{ref}")],"Missing counterfactual summary")
            require(int(row.offered_proposals)==len(group) and int(row.reference_passed)==int(group[f"reference{ref}_primary_pass"].sum()),"Counterfactual denominators differ")
    source_data=evidence.csv(root/"reports/d4_scenarios_labelled.csv",low_memory=False)
    source_counts={str(k):int(v) for k,v in source_data.stratum.value_counts().items()}
    primary_count=sum(source_counts[k] for k in context.d5["inherited_baseline"]["primary_strata"])
    require(primary_count==mc_numbers["scenarios"]==oat_meta["scenario_count"],"D4/MC/OAT primary populations differ")
    require(set(source_data[source_data.stratum.isin(context.d5['inherited_baseline']['primary_strata'])].scenario_id)==set(mc_meta['selected_scenario_ids']),"MC selected IDs differ from D4 primary population")
    evidence.verify(root/"reports/parameter_table.md")
    # Saved reports give context; their old 'pending' descriptions are historical.
    for key,name in (("mc","terminal_summary.txt"),("review","fly_reserve_review.md"),("oat","sensitivity_report.md"),
                      ("replay","replay_report.md"),("catalogue","failure_catalogue.md"),("matched","robustness_completion_report.md")):
        evidence.verify(directories[key]/name)
    return dict(context=context,evidence=evidence,directories=directories,proposal=proposal,proposal_line=proposal_line,
                mc=mc,mc_meta=mc_meta,mc_numbers=mc_numbers,review=review,priority=priority,curves=curves,fixed=fixed,ranks=ranks,
                diagnosis=diagnosis,oat_meta=oat_meta,replay_meta=replay_meta,replay=replay,workflow=workflow,
                catalogue_meta=catalogue_meta,catalogue=catalogue,matched_meta=matched_meta,statistics=statistics,
                ref_summary=ref_summary,matched_metrics=matched_metrics,comparisons=comparisons,proposals=proposals,
                cases=cases,cf_summary=cf_summary,selection=selection,source_counts=source_counts,recovery_audit=recovery_audit,
                figure_rebuild=figure_rebuild if evidence.missing_optional else None)


def checklist(data):
    dirs=data["directories"];ctx=data["context"]
    base=(data["fixed"].factor=="soc_error")&(data["fixed"].point_id=="2")&(data["fixed"].marginal_mapping=="INFEASIBLE")
    rows=[]
    def add(number,requirement,condition,summary,paths,limitation):
        rows.append(dict(criterion_id=f"D5-{number}",requirement_vi=requirement,
                         technical_evidence_complete=bool(condition),evidence_status="CO_BANG_CHUNG_PHAT_TRIEN" if condition else "CAN_BO_SUNG",
                         formal_review_status="PENDING",summary=summary,
                         proposal_file=str(data["proposal"].resolve()),proposal_line=data["proposal_line"],
                         evidence_files=[str(Path(p).resolve()) for p in paths],limitation=limitation))
    reserves=data["curves"][data["curves"].factor=="reserve_policy"]
    expected=set(ctx.d5["factors"]["reserve_policy"]["plotting_values"])
    sweep_ok=all(set(pd.to_numeric(g.point_value))==expected for _,g in reserves.groupby("battery_type")) and reserves.battery_type.nunique()==2
    add(1,"Quét nhiều mức dự trữ",sweep_ok,f"{len(expected)} mức × hai pin; cả REF-1 và REF-2, nhãn cố định và tính lại",
        [dirs["oat"]/"one_factor_curves.csv",dirs["oat"]/"reference_metrics.csv",dirs["matched"]/"fixed_vs_matched_metrics.csv"],
        "Mức dự trữ là giả định chính sách của nghiên cứu, không phải quy định phổ quát.")
    boundary_ok=True
    for ref in ("REF-1","REF-2"):
        for battery in ("TB47D","TB48D"):
            for w in ctx.d5["experiments"]["boundary_analysis"]["sweep_w"]:
                part=data["fixed"][base&(data["fixed"].reference_model==ref)&(data["fixed"].battery_type==battery)]
                b=part[part.scope==f"boundary_w={w}"];o=part[part.scope==f"outside_boundary_w={w}"]
                boundary_ok &= len(b)==len(o)==1 and int(b.iloc[0].scope_scenarios+o.iloc[0].scope_scenarios)==data["mc_numbers"]["scenarios"]
    add(2,"Phân tích tình huống gần ngưỡng",boundary_ok,"Ba độ rộng w; nhóm biên/ngoài biên riêng theo hai REF và hai pin",
        [dirs["oat"]/"reference_metrics.csv",dirs["matched"]/"matched_reference_metrics.csv"],
        "Không dùng thành viên nhóm REF-1 thay cho REF-2; nhóm tính lại có thể đổi mẫu số.")
    add(3,"Kiểm tra bất định và độ nhạy",len(data["mc"] )==30 and len(data["curves"] )==508,
        f"{data['mc_numbers']['total_draws']:,} lượt MC; {data['oat_meta']['total_evaluations']:,} điểm thử từng yếu tố",
        [dirs["mc"]/"terminal_summary.csv",dirs["oat"]/"sensitivity_ranking.csv",dirs["oat"]/"fly_case_diagnosis.csv"],
        "Các phạm vi sai số là giả định; tỷ lệ mô phỏng không phải xác suất thành công ngoài thực tế.")
    add(4,"Danh mục các trường hợp cần chú ý",len(data["catalogue"] )==31 and data["catalogue_meta"]["observed_categories"]==11,
        "31 ví dụ, đủ 11 nhóm đã khai; nguồn/đầu vào/kết quả trước–sau rõ ràng",
        [dirs["catalogue"]/"failure_catalogue.json",dirs["catalogue"]/"failure_cases_explained.csv"],
        "31 là số ví dụ đại diện; cảnh báo hoặc chặn đúng không phải sự cố bay quan sát được.")
    add(5,"Bản đánh giá bất biến và chạy lại được",len(data["replay"] )==24 and data["replay"].all_outputs_match.all(),
        "24/24 bản chạy lại khớp; chênh lệch số lớn nhất bằng 0",
        [dirs["replay"]/"replay_results.csv",dirs["replay"]/"snapshots",dirs["replay"]/"artifacts"],
        "Bất biến qua API và phát hiện thay đổi bằng hash; không phải WORM hay chữ ký chống sửa đổi ác ý.")
    add(6,"Kiểm tra dữ liệu cũ/thiếu, luật chặn và điều kiện duyệt",len(data["workflow"] )==41 and all(r["passed"] for r in data["workflow"]),
        "41/41 kiểm tra quy trình; có chặn hết hạn, dữ liệu sai/thiếu, VETO và CONDITIONAL chưa xử lý",
        [dirs["replay"]/"workflow_checks.json",ctx.root/"tests/test_mission_record.py",dirs["matched"]/"counterfactual_validation_summary.csv"],
        "Kiểm tra quy trình dùng entry point D5 mới; thời tiết là fixture, chưa thiết lập TTL vận hành thực tế.")
    pngs=list((dirs["oat"]/"figures").glob("*.png"))
    add(7,"Bảng và hình có thể tạo lại",len(pngs)==6,"Sáu hình PNG đúng hash; các bảng và bản xuất hình có script, manifest, hash nguồn",
        [ctx.root/"src/sensitivity_report.py",ctx.root/"src/complete_robustness.py",ctx.root/"src/failure_catalogue.py",ctx.root/"src/d5_report.py",dirs['oat']/'figures']
          +([data['figure_rebuild']/'figure_rebuild_audit.json'] if data['figure_rebuild'] else []),
        "Các lần chạy vẫn là phát triển; cần chốt quy trình và thực hiện bản cuối theo quy trình đã chốt.")
    return rows


def render(out,data,checks):
    ctx=data["context"];dirs=data["directories"];n=data["mc_numbers"];stats=data["statistics"]
    diagnosis=data["diagnosis"]
    none_count=int((~diagnosis[["soc_error","soh_error","wind_error","kappa_error","energy_error"]].any(axis=1)).sum())
    lines=["# D5 — Báo cáo tổng hợp độ bền của quyết định trước chuyến bay", "",
           "**Bản tổng hợp ngày 26/10/2026 — phục vụ kiểm tra chéo; chưa nghiệm thu.**", "",
           f"Người thực hiện ghi trong protocol: {ctx.d5['meta']['owner']}. Người kiểm tra chéo: {ctx.d5['meta']['cross_checker']}. Protocol hiện tại v{ctx.d5['meta']['version']}, trạng thái {ctx.d5['meta']['status']}, frozen={str(ctx.d5['meta']['frozen']).lower()}, kiểm tra chéo {ctx.d5['meta']['cross_check_status']}.", "",
           "Báo cáo này gom bằng chứng đã lưu của D5 thành một tài liệu. Các mô phỏng, bảng nhạy, catalogue, replay và đối chiếu tham chiếu đều giữ phiên bản/lần chạy gốc. Không chạy thêm Monte Carlo, không huấn luyện mô hình khi tổng hợp.","",
           "## 1. Kết quả chính", "",
           f"- Phạm vi chính: {n['scenarios']:,} ID kịch bản tổng hợp, hai giả định pin TB47D/TB48D.",
           f"- Monte Carlo: {n['total_draws']:,} lượt đánh giá mẫu, ba seed, năm cấu hình sai số; {n['result_rows']:,} dòng kết quả.",
           f"- Thử từng yếu tố: {data['oat_meta']['total_evaluations']:,} điểm; {int(data['curves'].valid_scenarios.sum()):,} hợp lệ, {int(data['curves'].invalid_perturbations.sum()):,} không hợp lệ.",
           "- Cấu hình sai số chính có 248 ca TB47D và 209 ca TB48D ban đầu FLY nhưng có mẫu thiếu dự trữ; tổng 457 cặp ID–pin.",
           f"- Trong 457 ca đó, riêng sai số năng lượng tạo thiếu dự trữ ở {int(diagnosis.energy_error.sum())} ca; riêng SoC ở {int(diagnosis.soc_error.sum())} ca. Có {none_count} ca không thiếu khi thử riêng từng yếu tố trên lưới chính.",
           "- Danh mục tình huống: 31 ví dụ đại diện cho 11 nhóm; gồm cả cảnh báo và ca bị chặn đúng.",
           "- Lưu và chạy lại: 24/24 bản khớp toàn bộ đầu ra; 41/41 kiểm tra quy trình đạt.",
           "- Tính nhãn tham chiếu lại cho TB48D: 2.099 nhãn REF-1 và 3.188 nhãn REF-2 đổi ở đầu vào gốc.",
           f"- Kiểm tra đề xuất: {stats['counterfactual']['selected_scenario_ids']:,} ID × hai pin; {stats['counterfactual']['evaluated_trials']:,} thay đổi áp dụng được; {stats['counterfactual']['offered_proposals']:,} đề xuất ứng viên. Không phải mọi đề xuất FLY đều qua cả hai REF.", "",
           "Các số trên là bằng chứng mô phỏng và kiểm tra phần mềm. Chưa có nhãn kết cục đủ để biến chúng thành xác suất an toàn bay ngoài thực tế.","",
           "## 2. Phạm vi, đơn vị và cách đọc", "",
           "D2 ước tính năng lượng từ dữ liệu chuyến bay; D3 ghép ngân sách pin với các quy tắc để ra quyết định; D4 cung cấp bộ kịch bản và nhãn tham chiếu mô phỏng. D5 kiểm tra kết quả biến động thế nào khi giả định/đầu vào thay đổi, đồng thời kiểm tra lưu và tái tạo quyết định.","",
           "Dữ liệu thực nghiệm nền là 192 chuyến bay CMU sau lọc và 192 phần dư kiểm định cấp chuyến dùng trong D2. Các ID D4 và các giá trị SoC/SoH/nhiệt độ trong D5 là tình huống tổng hợp hoặc giả định đã khai, không phải 14.700 chuyến bay thật có kết cục đã quan sát.","",
           *table(["Thuật ngữ","Cách hiểu"],[
               ["ID","Một kịch bản gốc; không phải seed hay một mẫu ngẫu nhiên."],
               ["Một dòng Monte Carlo","Một ID + pin + cấu hình sai số + seed; tóm tắt 10.000 mẫu."],
               ["Seed 42, 43, 44","Ba bộ số ngẫu nhiên để kiểm tra độ ổn định và chạy lại được."],
               ["Điểm thử từng yếu tố (OAT)","Thay một giá trị đã định sẵn rồi tính lại; khác mẫu ngẫu nhiên."],
               ["SoC / SoH","Mức pin hiện tại / sức khỏe pin; dùng tỷ lệ 0–1."],
               ["κ (kappa)","Hệ số điều chỉnh năng lượng pin theo nhiệt độ, là giả định từ tài liệu."],
               ["Margin","Năng lượng pin khả dụng trừ nhu cầu, chưa trừ phần dự trữ."],
               ["Dư so với dự trữ","E_available − (1+r) × E_required; âm nghĩa là thiếu mức dự trữ."],
               ["REF-1 / REF-2","Hai cách ước tính năng lượng để gán nhãn tham chiếu; không phải kết cục chuyến bay thật."],
               ["FLY / CONDITIONAL / NO_FLY","Kết luận của bộ quyết định trong chế độ phân tích; còn có INSUFFICIENT_DATA khi thiếu dữ liệu."],
               ["Feasible / marginal / infeasible","Khả thi / sát ngưỡng / không khả thi theo tham chiếu năng lượng."],
               ["VETO","Luật chặn quyết định FLY dù năng lượng có thể đủ."],
               ["Snapshot / replay","Bản lưu đầu vào–cấu hình–kết quả / tính lại bằng đúng bản đã lưu."]]),"",
           "Đơn vị chính: năng lượng Wh, quãng đường m (tổng đường bay kế hoạch), gió và tốc độ m/s, tải g, nhiệt độ °C. SoC 0,47 tương đương 47%; sai lệch −0,02 tương đương giảm 2 điểm phần trăm.","",
           *table(["Tầng D4","Số ID","Cách dùng ở D5"],[[key,data['source_counts'][key],"Tập chính" if key in ctx.d5['inherited_baseline']['primary_strata'] else "Kiểm tra/audit riêng; không nhập mẫu số MC chính"] for key in ("main","short_high","hard_rule_probe","missing_input")]),"",
           "## 3. Giả định được dùng", "",
           "Năng lượng khả dụng = năng lượng danh định × SoC × SoH × κ(T). TB47D dùng 99,9 Wh; TB48D dùng 129,96 Wh. Mức dự trữ chính r=0,20: pin cần ít nhất 1,20 lần nhu cầu. Quyết định FLY còn phải đạt khoản dự phòng sai số D3 1,4687 Wh và qua các luật đang áp dụng.",
           "REF-1 = dự đoán D2 đã chốt + 1,2924 Wh. Phần cộng được lấy từ phía dự đoán thiếu của phần dư D2. REF-2 = 7,44 × công suất bay treo lý tưởng × thời lượng kế hoạch / 3.600; hệ số đã chốt từ dữ liệu CMU. Hai REF khác họ công thức nhưng vẫn dùng cùng bộ dữ liệu nền và đều có hạn chế.",
           "Phần dư D2 = dự đoán − đo được. Khi mô phỏng, nhu cầu = dự đoán − phần dư; phần dư âm làm nhu cầu tăng. Không cộng lại khoản dự phòng vào nhu cầu MC để tránh đếm hai lần.",
           "Mức sai lệch chính: SoC/SoH ±2 điểm phần trăm, gió ±1 m/s, κ ±0,02. Nhóm giả định phân bố đều trong khoảng cắt tại biên vật lý và độc lập ở nhánh chính. Có các nhánh thử rộng, phần dư phía bất lợi và ghép hạng bất lợi. Chúng là giả định được khai, chưa phải sai số cảm biến đã được đo xác nhận.","",
           "### Giới hạn MTOW cần giữ rõ", "",
           "MTOW là tổng khối lượng tối đa lúc cất cánh. M100 theo DJI có giới hạn 3.600 g; cấu hình CMU gắn thiết bị đo được ghi 3.680 g trước tải. HR-3 là mã nhóm đặt cho luật khối lượng trong D3, không phải tên luật được ghi nguyên văn trong proposal.",
           "D5 kế thừa CMU_instrumented của benchmark D4: HR-3 ghi nhận vượt giới hạn ở mức RECORD_ONLY để phân tích dữ liệu. Nhãn FLY vì thế là kết quả của chế độ chẩn đoán có ngoại lệ đã công bố; không phải quyền cho bay thực tế. Dải tải 0–500 g là phạm vi dữ liệu, không thay thế MTOW. Workflow D5 mới chặn duyệt các ca CMU để tiến hành nhiệm vụ. Các ca M100_stock trong kiểm tra chỉ xác minh logic phần mềm, không xác nhận việc chuyển mô hình năng lượng sang máy bay nguyên bản.",
           f"Nguồn tham số: {link(ctx.root/'reports/parameter_table.md')}. Sai khác giữa mô tả mặc định D3 và cấu hình thực thi D4/CMU vẫn thuộc mục kiểm tra chéo OI-D5-6.","",
           "## 4. Monte Carlo: khi nhiều sai số cùng xuất hiện", "",
           f"Mỗi ID/pin/cấu hình/seed có {data['mc_meta']['draws_per_scenario']:,} mẫu; mỗi dòng tổng hợp theo seed có {int(data['mc'].valid_draws.min()):,} mẫu hợp lệ. Tỷ lệ nhóm tính bằng tổng số mẫu đạt chia tổng mẫu hợp lệ. Không lấy trung bình các cấu hình hoặc gộp pin/seed thành một xác suất.","",
           *table(["Cấu hình","Pin","Đủ năng lượng + dự trữ, khoảng qua 3 seed","Đồng thời qua VETO đang áp dụng"],
              [[CONFIG_NAMES[config],battery,
                f"{100*g.energy_feasibility_fraction.min():.4f}–{100*g.energy_feasibility_fraction.max():.4f}%",
                f"{100*g.joint_feasibility_fraction.min():.4f}–{100*g.joint_feasibility_fraction.max():.4f}%"]
               for (config,battery),g in data['mc'].groupby(['assumption_config_id','battery_type'],sort=False)]),"",
           "Các seed cho kết quả nhóm gần nhau trong lần chạy này. Điều đó chỉ kiểm tra biến động do lấy mẫu với số mẫu đã dùng, không kiểm chứng toàn bộ giả định mô hình. Tỷ lệ qua VETO ở MC chưa bao gồm thời tiết hết hạn hay quyền duyệt workflow, và không áp chặn MTOW trong hồ sơ CMU.",
           "Các nhánh bất lợi không bảo đảm mọi tỷ lệ đều thấp hơn nhánh chính: cách ghép sai số và vị trí từng kịch bản so với ngưỡng có thể làm thứ tự đổi. Phải giữ riêng các bảng cấu hình.","",
           "### Những ca ban đầu FLY nhưng có mẫu thiếu dự trữ", "",
           "__FLY_TABLE__", "",
           "457 cặp ID–pin được lọc ở cấu hình chính không đồng nghĩa 457 chuyến bay thực tế thất bại. Một mẫu thiếu trong 10.000 mẫu đã đủ để vào nhóm. Thiếu dự trữ có thể vẫn còn đủ năng lượng cơ bản của chuyến bay.",
           "ID 4757/TB48D là ví dụ có tỷ lệ mẫu thiếu khoảng 24,32–25,16% qua ba seed ở cấu hình chính. Đây là tỷ lệ theo giả định mô phỏng, không phải xác suất sự cố ngoài thực tế.","",
           "## 5. Thử riêng từng yếu tố và nhóm gần ngưỡng", "",
           "Mỗi loại pin có 254 điểm quét đã khai; mỗi điểm chạy đủ 14.700 ID. Điểm sai lệch đưa đầu vào ra ngoài miền vật lý được ghi không đánh giá và loại khỏi mẫu số, không kẹp về biên để biến thành mẫu hợp lệ.","",
           *table(["Pin","Yếu tố sai lệch","Số ID có ít nhất một điểm đổi quyết định","Lượt đổi / lượt hợp lệ"],
              [[r.battery_type,{"soc_error":"Mức pin","soh_error":"Sức khỏe pin","wind_error":"Gió","kappa_error":"Hệ số pin κ"}[r.factor],int(r.scenarios_any_verdict_change),f"{100*r.change_rate:.2f}%"]
               for r in data['ranks'][data['ranks'].sweep_kind=='input_error'].itertuples()]),"",
           "Các con số này là tần suất trên lưới đã khai, không phải xác suất. Không so xếp hạng giữa những phép quét có phạm vi/số điểm khác nhau như thể chúng đo cùng một ảnh hưởng nhân quả.",
           "Gió có thể đổi quyết định do vượt giới hạn 10 m/s, dù phần thay đổi năng lượng dự đoán nhỏ. Đổi quyết định và thiếu dự trữ là hai tiêu chí khác nhau.",
           f"Trong 457 ca đã lọc: {int(diagnosis.energy_error.sum())} ca thiếu khi chỉ thay sai số năng lượng; {int(diagnosis.soc_error.sum())} ca thiếu khi chỉ thay SoC. Cả 31 ca SoC cũng thuộc nhóm 184 ca năng lượng, nên không cộng hai số. Còn {none_count} ca không thiếu trên lưới thử riêng chính, dù MC phối hợp đã quan sát mẫu thiếu. Điều đó chưa phân rã được tương tác giữa các sai số.","",
           "### Quét mức dự trữ", "",
           "Bảng sau dùng nhãn tính lại theo đúng pin, cùng tập 14.700 ID. Nhóm marginal được gộp vào nhóm không khả thi trong cách chấm chính. Cột FLY trái tham chiếu là FLY trong khi REF xếp không khả thi hoặc sát ngưỡng; không phải sự cố bay thật.","",
           "__RESERVE_TABLE__", "",
           "Khi tăng mức dự trữ, điều kiện FLY nghiêm hơn. Cần xem đồng thời số cho FLY, số trái tham chiếu và số từ chối khi tham chiếu cho khả thi; không chỉ chọn ngưỡng vì một tỷ lệ đẹp hơn.","",
           "### Định nghĩa và phạm vi nhóm biên", "",
           "Một ID ở nhóm biên nếu |R_ref| ≤ w hoặc |R_ref − 0,20| ≤ w. Nhóm được xác định riêng cho REF-1/REF-2. Bảng dưới dùng nhãn và thành viên D4 gốc, để thấy phạm vi so sánh chính.","",
           "__BOUNDARY_TABLE__", "",
           "Các bảng đầy đủ có điểm số ở nhóm biên/ngoài biên, cả hai pin và hai cách gộp marginal. Phân tích bổ sung còn tính lại nhóm biên theo thế giới đã thay đổi; không so hai nhóm khác thành viên như thể mẫu số được giữ nguyên.","",
           "__FIGURES__", "",
           "## 6. Danh mục tình huống cần chú ý", "",
           "Các ví dụ chọn ID nhỏ nhất đủ điều kiện trong từng nhóm/pin/tham chiếu; nếu có nhiều điểm ở cùng ID thì dùng thứ tự lưới đã khai. Không chọn vì tỷ lệ đẹp hay chỉ lấy các đề xuất thành công.","",
           *table(["Nhóm","Số ví dụ","ID hoặc ca thử minh họa"],
              [[TITLES[category],len(group),", ".join(dict.fromkeys(str(c['scenario_id']) if c['scenario_id'] is not None else c['assessment_id'] for c in group))]
               for category in TITLES for group in [[c for c in data['catalogue'] if c['category']==category]]]),"",
           "Có dòng giữ nguyên quyết định vì đó là cảnh báo phạm vi dữ liệu hoặc thay cách chấm. Các ca thời tiết/dữ liệu thiếu là fixture có mã assessment riêng và không có ID D4; ô ID trống không phải mất dữ liệu.",
           f"Bảng giải thích từng dòng: {link(dirs['catalogue']/'failure_cases_explained.csv')}. Đủ đầu vào và luật: {link(dirs['catalogue']/'failure_catalogue.json')}.","",
           "## 7. Lưu quyết định, chạy lại và kiểm tra quy trình", "",
           "Đã lưu 24 trường hợp gồm đủ bốn kết luận, ca biên, vi phạm gió/khối lượng, đầu vào thiếu/NaN/sai và thời tiết hết hạn; ba ví dụ lấy từ kịch bản D4 là 1, 2681, 4757. Cả 24 bản tái tạo đúng kết luận và số liệu, chênh lệch số lớn nhất bằng 0. Có 41/41 kiểm tra quy trình đạt.",
           "Bản lưu gồm đầy đủ đầu vào/đơn vị, thời điểm và hiệu lực thời tiết, phiên bản mã nguồn/mô hình/bộ chuẩn hóa/YAML, kết quả luật, năng lượng và kết luận. Chạy lại dùng mã/config đã lưu trong tiến trình riêng; thiếu hoặc sai hash/phiên bản môi trường thì báo không chạy lại được, không lấy cấu hình mới thay lịch sử.","",
           *table(["Nhóm yêu cầu E5","Bằng chứng"],[
               ["Đổi đầu vào/máy bay/pin/mô hình/ngưỡng/luật","Đánh giá cũ bị STALE; ca mới không thừa hưởng quyền duyệt cũ."],
               ["Thời tiết hết hạn","Đến đúng valid_until hoặc thiếu thời hạn thì chặn dùng như dữ liệu hiện hành."],
               ["Dữ liệu thiếu/sai/NaN","Không tạo FLY; chuẩn hóa giá trị không hữu hạn tại ranh giới dữ liệu."],
               ["VETO khi năng lượng vẫn cao","Người duyệt không thể đảo thành FLY qua API mới."],
               ["CONDITIONAL chưa có xử lý hợp lệ","Tên biện pháp tùy ý không mở khóa; cần liên kết bản cũ, thay đổi đúng và đánh giá lại."],
               ["Đánh giá trước bay xấu hơn","Cần người xem xét lại; không tự kế thừa duyệt trước."],
               ["Lịch sử sau đổi cấu hình","Snapshot giữ nguyên; sự kiện workflow thêm mới theo chuỗi hash."],
               ["Kết cục độc lập","UNKNOWN là mặc định; không lấy FLY làm kết cục thành công."]]),"",
           "Thời tiết trong kiểm tra là dữ liệu giả lập có observed_at/valid_until rõ ràng. Không đặt mặc định thời tiết thực tế có hiệu lực 30 phút. Replay lịch sử dùng thời điểm đã lưu; duyệt tiếp dùng thời điểm hiện tại được cung cấp và kiểm hạn lại.",
           "Module D5 mới là src/mission_record.py; API src/workflow_state.py cũ không phải đường bằng chứng E5 này. Cơ chế bất biến được thực hiện qua API, chống ghi đè ID và phát hiện sửa nhầm bằng hash; không phải lưu trữ WORM, chữ ký số hay chứng nhận kiểm soát bay.","",
           "## 8. Tính lại tham chiếu và kiểm tra đề xuất điều chỉnh", "",
           "Nhãn D4 gốc giữ giả định pin TB47D. Phép so sánh chính vẫn giữ nguyên nhãn đó. Phân tích matched-world bổ sung tính lại REF ở cùng SoC/SoH/κ, pin và đầu vào nhiệm vụ để xem kết luận phụ thuộc giả định tham chiếu ra sao.","",
           *table(["Pin","REF","Nhãn đổi so với D4 ở đầu vào gốc","FLY trái tham chiếu: nhãn gốc → nhãn tính lại"],
              [[r.battery_type,r.reference_model,int(r.changed_reference_labels),f"{int(r.false_safe_count_fixed)}/{int(r.reference_infeasible_fixed)} → {int(r.false_safe_count_matched)}/{int(r.reference_infeasible_matched)}"]
               for r in data['ref_summary'][data['ref_summary'].marginal_mapping=='INFEASIBLE'].itertuples()]),"",
           "Đổi nhãn có thể làm cả tử số và mẫu số đổi. Các con số này sửa sự nhất quán của giả định so sánh, không phải bằng chứng tự thân rằng thuật toán đã được cải tiến.",
           "REF-1 giữ mô hình và khoản dự phòng; REF-2 giữ mô hình vật lý và k đã chốt. Không chép phần dư thử ứng viên sang các REF. Khi quét chính sách ứng viên, mức dự trữ REF giữ 20%. REF-2 không có ánh xạ nhu cầu theo gió đã được xác minh. Khối lượng CMU vẫn theo hồ sơ 3.680 g; không tự cộng một hiệu chỉnh khối lượng pin chưa khai.","",
           f"Chọn trước toàn bộ {stats['counterfactual']['selected_scenario_ids']:,} ID marginal theo ít nhất một REF D4; hai pin thành {stats['counterfactual']['selected_battery_cases']:,} cặp ID–pin. Đã đánh giá {stats['counterfactual']['evaluated_trials']:,} thay đổi áp dụng được và lưu {stats['counterfactual']['saved_trial_rows']:,} dòng, gồm cả không áp dụng/đã FLY. Có {stats['counterfactual']['offered_proposals']:,} đề xuất ứng viên trên {stats['counterfactual']['cases_with_proposal']:,} cặp.",
           "Thử một biến mỗi lần: mức pin trên lưới 1 điểm phần trăm; tải/tốc độ theo mức có trong dữ liệu; đường bay trên lưới 10 m trong dải hỗ trợ. Chọn thay đổi nhỏ nhất trong từng biện pháp đạt FLY của ứng viên, rồi mới chấm bằng REF. Không dùng kết quả REF để lọc đề xuất và không khẳng định tối ưu liên tục hay chi phí giữa các loại hành động.","",
           *table(["Pin","Đề xuất ứng viên","Qua REF-1 (feasible)","Qua REF-2 (feasible)"],
              [[battery,len(group),int(group.reference1_primary_pass.sum()),int(group.reference2_primary_pass.sum())] for battery,group in data['proposals'].groupby('baseline_battery')]),"",
           "Một số đề xuất làm ứng viên FLY nhưng không qua tham chiếu; chúng được giữ trong mẫu số. Các bảng có cách gộp marginal thứ hai và phân tách trong/ngoài phạm vi dữ liệu. Các biện pháp chờ gió/nhiệt độ là giả định có điều kiện, cần quan trắc mới trước khi áp dụng.",
           "Ví dụ ID 41/TB47D: tăng mức pin 44,17% → 47% làm NO_FLY → FLY. Pin khả dụng sau đổi khoảng 35,23 Wh; REF-1 cho khả thi, REF-2 ước nhu cầu khoảng 45,25 Wh nên vẫn không khả thi. Đây là bất đồng giữa các mô hình, không có kết cục bay thật để chọn một bên làm sự thật.",
           "Ví dụ ID 10/TB47D: nếu nhiệm vụ cho phép giảm quãng đường 775,59 m → 610 m, ứng viên đổi CONDITIONAL → FLY và cả hai REF đạt. Việc sửa số quãng đường trong mô phỏng chưa chứng minh tuyến thực tế có thể rút ngắn.",
           "Giảm tốc độ đã được thử nhưng không tạo đề xuất đạt FLY trong nhóm đã chọn; bay chậm có thể làm thời lượng tăng. Hành động chờ gió không áp dụng ở tập này vì không có gió vượt HR-1; tỷ lệ khi không có đề xuất được ghi NA, không ghi 0%.","",
           "## 9. Đối chiếu 7 tiêu chí D5 của proposal", "",
           f"Cơ sở: {link(data['proposal'],f'proposal, mục 12.1, dòng {data["proposal_line"]}')}. Bảng sau xác nhận sự hiện diện của bằng chứng phát triển, không thay chữ ký kiểm tra chéo.","",
           *table(["Mã","Tiêu chí","Bằng chứng hiện có","Trạng thái"],[[c['criterion_id'],c['requirement_vi'],c['summary'],"Có bằng chứng; chờ kiểm tra chéo" if c['technical_evidence_complete'] else "Cần bổ sung"] for c in checks]),"",
           f"Bảng kiểm có đường dẫn chi tiết: {link(out/'d5_acceptance_checklist.csv')}. Người kiểm tra chéo vẫn PENDING; không tự ghi nhận Phát đã duyệt hoặc D5 đã nghiệm thu.","",
           "## 10. Khả năng tái lập và phiên bản bằng chứng", "",
           "__RUN_TABLE__", "",
           "Các mô tả 'còn thiếu' trong báo cáo cũ phản ánh thời điểm tạo file đó. Bản tổng hợp này dùng bằng chứng mới hơn cho catalogue, replay và đối chiếu tham chiếu mà không sửa lịch sử các lần chạy cũ.",
           "Lần MC cũ lưu hash/metadata của protocol v0.3.1; các bản phát triển sau đã thay đổi phần mô tả và bổ sung module. Không đồng nhất YAML hiện tại với nguyên file YAML v0.3.1 chỉ vì các thiết lập định lượng kế thừa. Khi chốt phạm vi chạy cuối, phải lưu nguyên mã, cấu hình, mô hình, môi trường và manifest cho bản cuối theo quy trình đã chốt. Bản replay v0.5.0 và đợt matched/counterfactual v0.6.0 đã có bản cấu hình/mã nguồn lưu kèm.",
           "Bộ tạo báo cáo này đối chiếu hash hiện vật nguồn, liên kết các manifest và đối soát tử số/mẫu số trước khi kết xuất. Danh sách file đã xác minh nằm trong evidence_manifest.json; source raw được đọc theo luồng để kiểm hash, không tải toàn bộ JSON/CSV lớn vào bộ nhớ để tổng hợp.","",
           "__RECOVERY_NOTE__", "",
           "## 11. Kết luận và việc cần chốt", "",
           "D5 hiện có bằng chứng cho đủ bảy nhóm yêu cầu kỹ thuật trong phạm vi mô phỏng đã khai. Kết quả cho thấy cả những ca đổi quyết định, thiếu dự trữ khi phối hợp sai số và bất đồng giữa hai mô hình tham chiếu; không chỉ trình bày các ví dụ thành công.",
           "Giới hạn chính: cấu hình CMU vượt MTOW; dữ liệu không có nhãn kết cục đủ để kiểm chứng an toàn thực tế; SoH/nhiệt độ/sai số đầu vào chủ yếu là giả định; REF-1 có phụ thuộc mô hình D2 và REF-2 là xấp xỉ; các phép ngoại suy và dải thử ảnh hưởng kết luận; kết quả Monte Carlo không phải xác suất thành công đã hiệu chuẩn.",
           "Bước chốt: Phát kiểm tra chéo cách áp hồ sơ CMU/HR-3 (OI-D5-6), giả định/tính toán/workflow và bảy tiêu chí (OI-D5-7); ghi rõ điều chỉnh nếu có. Sau đó mới chốt phiên bản quy trình và thực hiện lần chạy cuối theo quy trình đã chốt. Nếu đổi thiết lập ảnh hưởng kết quả thì chạy lại các thí nghiệm bị ảnh hưởng; không nâng nhãn 'development' thành 'final' bằng sửa metadata.","",
           "## 12. File nên mở", "",
           *[f"- {verified_link(data['evidence'],dirs[key]/file)} — {description}" for key,file,description in [
               ("mc","terminal_summary.csv","30 dòng theo cấu hình/pin/seed; có tử số và mẫu số."),
               ("oat","fly_cases_explained.csv","đủ 457 cặp FLY có mẫu thiếu, giải thích thử riêng từng yếu tố."),
               ("catalogue","failure_cases_explained.csv","31 ví dụ đại diện, cột tiếng Việt."),
               ("replay","replay_results.csv","đối chiếu 24 bản lịch sử."),
               ("matched","battery_reference_examples.csv","ví dụ nhãn tham chiếu đổi khi đổi pin."),
               ("matched","counterfactual_examples_explained.csv","ví dụ điều chỉnh và kết quả hai REF."),
               ("matched","counterfactual_case_summary.csv","đủ 4.490 cặp ID/pin trong tập kiểm tra đề xuất.")]],"",
           "Các tệp chi tiết .csv.gz nhiều triệu dòng dùng Python đọc theo lô; báo cáo và các bảng nhỏ trên là điểm bắt đầu để xem bằng mắt.",""]
    # Table columns are taken from the saved review file, without assuming old labels.
    review=data['review'][data['review'].assumption_config_id=='PRIMARY_INDEPENDENT']
    fly_table=table(["Pin","FLY ban đầu","Có mẫu thiếu ở ≥1 seed","Có mẫu thiếu ở cả 3 seed"],
                    [[r.battery_type,int(r.initial_fly_cases),int(r.cases_with_shortfall),int(r.cases_with_shortfall_all_seeds)] for r in review.itertuples()])
    policy=[]
    refs=data['matched_metrics']
    primary=refs[(refs.factor=='reserve_policy')&(refs.scope=='all')&(refs.scope_membership_policy=='ORIGINAL_D4')&(refs.marginal_mapping=='INFEASIBLE')]
    for battery in ('TB47D','TB48D'):
        for rvalue in sorted(pd.to_numeric(data['curves'][data['curves'].factor=='reserve_policy'].point_value).unique()):
            pieces=primary[(primary.battery_type==battery)&pd.to_numeric(primary.point_value).eq(rvalue)]
            a=one(pieces[pieces.reference_model=='REF-1'],'Missing REF-1 policy point')
            b=one(pieces[pieces.reference_model=='REF-2'],'Missing REF-2 policy point')
            require(candidate_fly_count(a)==candidate_fly_count(b),'Candidate FLY total differs across references')
            policy.append([battery,f"{rvalue:.0%}",candidate_fly_count(a),ratio(a.false_safe_count,a.reference_infeasible),ratio(b.false_safe_count,b.reference_infeasible)])
    boundary=[]
    fixed=data['fixed']
    for ref in ('REF-1','REF-2'):
        for width in ctx.d5['experiments']['boundary_analysis']['sweep_w']:
            group=fixed[(fixed.battery_type=='TB47D')&(fixed.factor=='soc_error')&(fixed.point_id=='2')&(fixed.reference_model==ref)&(fixed.marginal_mapping=='INFEASIBLE')]
            inside=one(group[group.scope==f'boundary_w={width}'],'Missing boundary group')
            outside=one(group[group.scope==f'outside_boundary_w={width}'],'Missing outside group')
            boundary.append([ref,width,int(inside.scope_scenarios),int(outside.scope_scenarios)])
    versions={'mc':data['mc_meta']['protocol_version'],'review':data['mc_meta']['protocol_version'],
              'oat':data['oat_meta']['protocol_version'],'replay':'0.5.0',
              'catalogue':data['catalogue_meta']['protocol_version'],'matched':data['matched_meta']['protocol_version']}
    run_table=table(['Phần','Thư mục nguồn','Protocol khi chạy'],[[key,RUNS[key],versions[key]] for key in RUNS])
    figures=[]
    for name,description in [('sensitivity_ranking','Đổi quyết định khi thay từng sai lệch; tần suất trên lưới.'),
                              ('verdict_transitions','Chuyển giữa các kết luận; không phải số chuyến bay thật.'),
                              ('false_safe_vs_reserve','Điểm số theo nhãn D4 cố định. Bảng nhãn tính lại nằm ở phần 8.')]:
        destination=out/'figures'/f'{name}.png'
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(dirs['oat']/'figures'/f'{name}.png',destination)
        figures.extend([f"![{description}]({destination.resolve().as_posix()})","",description,""])
    body='\n'.join(lines)
    body=body.replace('__FLY_TABLE__','\n'.join(fly_table)).replace('__RESERVE_TABLE__','\n'.join(table(['Pin','Mức dự trữ','Số FLY','FLY trái REF-1','FLY trái REF-2'],policy)))
    body=body.replace('__BOUNDARY_TABLE__','\n'.join(table(['REF','w','ID nhóm biên','ID ngoài biên'],boundary))).replace('__RUN_TABLE__','\n'.join(run_table)).replace('__FIGURES__','\n'.join(figures))
    audit=data['recovery_audit']
    note=(f"**Ghi nhận thay đổi định dạng dữ liệu MC:** CSV tại thư mục lần chạy hiện khác hash gốc; JSON vẫn khớp. Đã dựng lại đủ {audit['recovered_rows']:,} dòng CSV từ JSON sang thư mục mới, hash trùng chính xác hash CSV ban đầu. Có {audit['scalar_numeric_difference_cells']:,} ô số khác về độ chính xác trong CSV hiện tại, chênh lệch tuyệt đối lớn nhất {audit['maximum_scalar_absolute_difference']:.12g}; không suy đoán người/phần mềm đã sửa file. Báo cáo dùng bằng chứng gốc/bản khôi phục đã xác minh, không bỏ qua lỗi hash và không ghi đè CSV hiện tại. Nhật ký: {link(Path(audit['recovered_csv']).parent/'recovery_audit.json')}." if audit else "Không cần dùng bản thay thế cho các file nguồn đã xác minh.")
    body=body.replace('__RECOVERY_NOTE__',note)
    if data['evidence'].missing_optional:
        body=body.replace('## 11. Kết luận và việc cần chốt',
             f"Sáu SVG được liệt kê trong manifest hình cũ hiện không còn ở thư mục gốc. Đã tái tạo hình từ các bảng nguồn đã xác minh sang {link(data['figure_rebuild']/'figure_rebuild_audit.json')}; cả sáu PNG tái tạo khớp byte với bản PNG gốc. Các SVG mới có hash mới do metadata/ID của bộ xuất hình, không giả nhận chúng là nguyên byte SVG lịch sử. Bản CSV giải thích 457 ca cũng được khôi phục riêng với đúng hash gốc.\n\n## 11. Kết luận và việc cần chốt")
    (out/'robustness_report.md').write_text(body,encoding='utf-8')
    return dict(mc=n,oat_total=data['oat_meta']['total_evaluations'],oat_valid=int(data['curves'].valid_scenarios.sum()),
                oat_invalid=int(data['curves'].invalid_perturbations.sum()),fly_cases=len(diagnosis),
                single_energy_shortfall=int(diagnosis.energy_error.sum()),single_soc_shortfall=int(diagnosis.soc_error.sum()),
                none_on_primary_single_factor_grid=none_count,catalogue_examples=len(data['catalogue']),catalogue_categories=len(TITLES),
                replay_records=len(data['replay']),replay_max_absolute_difference=data['replay_meta']['max_absolute_difference'],
                workflow_checks=len(data['workflow']),matched_and_counterfactual_statistics=stats)


def run(out,root=ROOT):
    out=Path(out)
    require(not out.exists(),'Choose a new summary directory')
    print('Verifying saved D5 evidence and manifest links (no new simulation)...',flush=True)
    data=collect(root)
    checks=checklist(data)
    require(all(c['technical_evidence_complete'] for c in checks),'At least one D5 criterion lacks technical evidence')
    out.mkdir(parents=True,exist_ok=False)
    frame=pd.DataFrame(checks)
    frame['evidence_files']=frame.evidence_files.map(lambda paths:'\n'.join(paths))
    frame.to_csv(out/'d5_acceptance_checklist.csv',index=False,encoding='utf-8-sig')
    write_json(out/'d5_acceptance_checklist.json',checks)
    findings=render(out,data,checks)
    if data['figure_rebuild']:
        for source in (data['figure_rebuild']/'figures').glob('*.svg'):
            shutil.copyfile(source,out/'figures'/source.name)
    write_json(out/'summary_findings.json',findings)
    shutil.copyfile(__file__,out/'report_source.py')
    shutil.copyfile(data['context'].root/'configs/d5_protocol.yaml',out/'protocol_snapshot.yaml')
    for path in data['evidence'].files:data['evidence'].verify(path)
    write_json(out/'evidence_manifest.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
               status='TECHNICAL_EVIDENCE_READY_PENDING_CROSS_CHECK',final_d5_complete=False,
               protocol_version=data['context'].d5['meta']['version'],protocol_frozen=data['context'].d5['meta']['frozen'],
               cross_check_status=data['context'].d5['meta']['cross_check_status'],seven_criteria_have_evidence=True,
               source_runs=RUNS,source_files=data['evidence'].files,report_generator_sha256=sha(__file__),
               verified_source_replacements=data['evidence'].replacements,
               missing_optional_historical_exports=data['evidence'].missing_optional,
               outputs={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()},
               validation_scope='Saved source outputs and parent-manifest links; historical D5 YAML hashes are not checked against the current YAML as if unchanged'))
    print(f'Saved integrated report and 7-row checklist to {out}; final acceptance remains pending.',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    run(args.out,args.root)


if __name__=='__main__':main()
