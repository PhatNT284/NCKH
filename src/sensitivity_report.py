"""Render saved full-population OAT results into scientific figures and a review."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.sensitivity import ERROR_FACTORS, sha

LABELS={"soc_error":"Sai lệch SoC","soh_error":"Sai lệch SoH","wind_error":"Sai lệch gió",
        "kappa_error":"Sai lệch κ","energy_error":"Phần dư năng lượng OOF","soh_domain":"Dải SoH",
        "wind_domain":"Dải gió","temperature_domain":"Dải nhiệt độ","reserve_policy":"Mức dự trữ",
        "battery_assumption":"Đổi loại pin"}
COLORS={"TB47D":"#2563a6","TB48D":"#bf641d"}


def render(run, *, refresh=False):
    run=Path(run)
    meta=json.loads((run/"input_manifest.json").read_text(encoding="utf-8"))
    if meta["status"]!="COMPLETED_OAT_DEVELOPMENT":raise ValueError("OAT run is not completed")
    names=["one_factor_curves.csv","reference_metrics.csv","verdict_transitions.csv","sensitivity_ranking.csv",
           "fly_case_factor_details.csv","fly_case_diagnosis.csv"]
    for name in names:
        if sha(run/name)!=meta["output_hashes"][name]:raise ValueError(f"Output changed: {name}")
    curves,refs,transitions,ranks,focus,diagnosis=[pd.read_csv(run/name) for name in names]
    if int(curves.valid_scenarios.sum()+curves.invalid_perturbations.sum())!=meta["total_evaluations"]:
        raise ValueError("Evaluation totals do not reconcile")
    if len(diagnosis)!=meta["focus_cases"]:raise ValueError("Missing FLY case coverage")
    figdir=run/"figures"
    if figdir.exists() and not refresh:raise FileExistsError("Figures already exist; use --refresh to update only the report")
    figdir.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,
                         "axes.grid":True,"grid.alpha":.18,"savefig.dpi":180})
    def save(fig,name):
        fig.savefig(figdir/f"{name}.png",bbox_inches="tight")
        fig.savefig(figdir/f"{name}.svg",bbox_inches="tight")
        plt.close(fig)
    batteries=meta["batteries"]
    # Ranking is within a declared sweep kind, never a universal causal ranking.
    fig,axes=plt.subplots(2,2,figsize=(13,9))
    for i,kind in enumerate(["input_error","scenario_domain"]):
        for j,battery in enumerate(batteries):
            ax=axes[i,j];part=ranks[(ranks.battery_type==battery)&(ranks.sweep_kind==kind)].sort_values("change_rate")
            ax.barh([LABELS[f] for f in part.factor],100*part.change_rate,color=COLORS[battery])
            ax.set_title(f"{battery} · {'Lưới sai lệch đã khai' if i==0 else 'Toàn dải kịch bản đã khai'}")
            ax.set_xlabel("Lượt đánh giá có đổi verdict / lượt hợp lệ (%)")
    fig.suptitle(f"Độ nhạy trên {meta['scenario_count']:,} kịch bản. So sánh trong từng loại phép quét",fontsize=14)
    fig.tight_layout(rect=(0,0,1,.95));save(fig,"sensitivity_ranking")
    selected=["soc_error","soh_error","wind_error","kappa_error","energy_error","temperature_domain"]
    for quantity,title,filename in [("energy","Biến thiên năng lượng so với kịch bản gốc","energy_curves"),
                                    ("margin","Biến thiên mức dư năng lượng so với kịch bản gốc","margin_curves")]:
        fig,axes=plt.subplots(2,3,figsize=(15,8))
        for ax,factor in zip(axes.flat,selected):
            for battery in batteries:
                part=curves[(curves.factor==factor)&(curves.battery_type==battery)].copy()
                part["x"]=pd.to_numeric(part.point_value);part=part.sort_values("x")
                x=part.x*100 if factor in ("soc_error","soh_error") else part.x
                if quantity=="energy":
                    ax.plot(x,part.delta_available_mean_Wh,color=COLORS[battery],label=f"{battery}: khả dụng")
                    ax.plot(x,part.delta_required_mean_Wh,color=COLORS[battery],linestyle="--",label=f"{battery}: nhu cầu")
                else: ax.plot(x,part.delta_margin_mean_Wh,color=COLORS[battery],marker="." if len(part)<20 else None,label=battery)
            ax.axhline(0,color="gray",linewidth=.7);ax.set_title(LABELS[factor]);ax.set_ylabel("Thay đổi trung bình (Wh)")
            ax.set_xlabel("Sai lệch (điểm phần trăm)" if factor in ("soc_error","soh_error") else
                          "Sai lệch gió (m/s)" if factor=="wind_error" else "Sai lệch κ" if factor=="kappa_error" else
                          "Phần dư: dự đoán − thực tế (Wh)" if factor=="energy_error" else "Nhiệt độ (°C)")
        handles,labels=axes.flat[0].get_legend_handles_labels()
        fig.legend(handles,labels,loc="lower center",ncol=4)
        fig.suptitle(title+" — trung bình trên các điểm hợp lệ",fontsize=14)
        fig.tight_layout(rect=(0,.065,1,.95));save(fig,filename)
    fig,axes=plt.subplots(2,5,figsize=(18,7))
    order=["FLY","CONDITIONAL","NO_FLY"]
    for i,battery in enumerate(batteries):
        for j,factor in enumerate(ERROR_FACTORS):
            part=transitions[(transitions.battery_type==battery)&(transitions.factor==factor)]
            matrix=part.pivot_table(index="baseline_verdict",columns="reassessed_verdict",values="count",aggfunc="sum",fill_value=0).reindex(index=order,columns=order,fill_value=0).to_numpy(float)
            denom=matrix.sum(axis=1,keepdims=True)
            pct=np.divide(matrix,denom,out=np.full_like(matrix,np.nan),where=denom>0)*100
            ax=axes[i,j];ax.imshow(pct,vmin=0,vmax=100,cmap="Blues")
            for a in range(3):
                for b in range(3):ax.text(b,a,"NA" if np.isnan(pct[a,b]) else f"{pct[a,b]:.1f}",ha="center",va="center",color="white" if pct[a,b]>55 else "black",fontsize=9)
            ax.grid(False);ax.set_xticks(range(3),order,rotation=40,ha="right");ax.set_yticks(range(3),order)
            ax.set_title(f"{battery}\n{LABELS[factor]}",fontsize=10)
    fig.suptitle("Chuyển verdict khi tái đánh giá từng yếu tố. Chuẩn hóa theo verdict gốc (%)",fontsize=13)
    fig.tight_layout(rect=(0,0,1,.92));save(fig,"verdict_transitions")
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for ax,ref in zip(axes,["REF-1","REF-2"]):
        part=refs[(refs.factor=="reserve_policy")&(refs.reference_model==ref)&(refs.scope=="all")&(refs.marginal_mapping=="INFEASIBLE")]
        for battery in batteries:
            line=part[part.battery_type==battery].copy();line['x']=pd.to_numeric(line.point_value);line=line.sort_values('x')
            ax.plot(line.x,100*line.false_safe_rate,marker='o',label=battery,color=COLORS[battery])
        ax.set_title(f"{ref}: nhãn D4 giữ cố định");ax.set_xlabel("Mức dự trữ của B5");ax.set_ylabel("FLY trên nhãn không khả thi (%)");ax.legend()
    fig.suptitle("Đổi chính sách dự trữ. Marginal gộp vào không khả thi",fontsize=13)
    fig.tight_layout(rect=(0,0,1,.92));save(fig,"false_safe_vs_reserve")
    count_rows=[]
    for battery in batteries:
        part=diagnosis[diagnosis.battery_type==battery]
        for factor in ERROR_FACTORS:
            count_rows.append(dict(battery_type=battery,factor=factor,focused_cases=len(part),cases_shortfall_on_primary_grid=int(part[factor].sum())))
    attribution=pd.DataFrame(count_rows)
    attribution.to_csv(run/"fly_single_factor_responses.csv",index=False)
    explained=diagnosis.rename(columns={"scenario_id":"ID","battery_type":"Loai_pin",
        "failure_fraction_min":"Ty_le_MC_thieu_min","failure_fraction_max":"Ty_le_MC_thieu_max",
        "soc_error":"SoC_don_le","soh_error":"SoH_don_le","wind_error":"Gio_don_le",
        "kappa_error":"Kappa_don_le","energy_error":"Phan_du_nang_luong_don_le"}).copy()
    def explanation(row):
        active=[LABELS[name] for name in ERROR_FACTORS if row[name]]
        return ("Có điểm thiếu dự trữ khi chỉ thay riêng: "+", ".join(active)+". Các yếu tố khác giữ ở đầu vào gốc.") if active else (
            "Không thiếu khi đổi riêng từng yếu tố trên lưới chính; có mẫu thiếu trong Monte Carlo phối hợp nhiều sai lệch.")
    explained['Dien_giai']=diagnosis.apply(explanation,axis=1)
    explained=explained.drop(columns='single_factor_response')
    explained.to_csv(run/'fly_cases_explained.csv',index=False,encoding='utf-8-sig')
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for ax,battery in zip(axes,batteries):
        part=attribution[attribution.battery_type==battery]
        ax.barh([LABELS[x] for x in part.factor],part.cases_shortfall_on_primary_grid,color=COLORS[battery])
        ax.set_title(f"{battery}: {int(part.focused_cases.iloc[0])} ca FLY đã lọc");ax.set_xlabel("Số ca có thể thiếu dự trữ khi chỉ đổi yếu tố này")
    fig.suptitle("Kiểm tra từng yếu tố trên lưới sai lệch chính. Một ca có thể thuộc nhiều cột",fontsize=12)
    fig.tight_layout(rect=(0,0,1,.92));save(fig,"fly_single_factor_responses")
    ranked=ranks.sort_values(["battery_type","sweep_kind","change_rate"],ascending=[True,True,False]).copy()
    ranked['rank_within_kind']=ranked.groupby(["battery_type","sweep_kind"]).cumcount()+1
    ranked.to_csv(run/"ranking_within_sweep_kind.csv",index=False)
    none=int((diagnosis.single_factor_response=="NONE_ON_PRIMARY_GRID").sum())
    lines=["# Phân tích độ nhạy D5 trên toàn bộ kịch bản", "",
           f"Đã đánh giá **{meta['scenario_count']:,} kịch bản**, hai loại pin, **{len(meta['points'])} điểm quét mỗi pin**, tổng **{meta['total_evaluations']:,} lượt đánh giá xác định**.",
           f"Điểm hợp lệ: {int(curves.valid_scenarios.sum()):,}; điểm không đánh giá vì sai lệch không hợp lệ: {int(curves.invalid_perturbations.sum()):,}.",
           "Đây là phân tích thay từng yếu tố riêng. Không chạy lại 4,41 tỷ mẫu Monte Carlo.","",
           "## Phạm vi và phép đối chiếu", "",
           "- Toàn bộ các tầng chính `main` và `short_high`; các tầng audit/missing của D4 được ghi trong manifest, không nhập vào mẫu số.",
           "- Đã đối chiếu đúng verdict gốc và dự đoán D2 của toàn bộ 29.400 cặp kịch bản–pin với lần chạy Monte Carlo đã lưu.",
           "- Có 34 kiểm thử đối chiếu bộ tính vector với D3 scalar, bao gồm VETO, ngoại suy, dấu phần dư, PH-1 với κ đã đổi, điểm không hợp lệ và mẫu số tham chiếu.",
           "- Mỗi lần chỉ thay một yếu tố; tính lại nhu cầu nếu đặc trưng gió thay đổi, năng lượng khả dụng, PH-1, margin, mức dự trữ và verdict.",
           "- Lưới SoC/SoH/κ: −0,05; −0,02; 0; +0,02; +0,05. Gió: −2; −1; 0; +1; +2 m/s. Giữ riêng các điểm thuộc mức chính.",
           "- Dải SoH, gió, nhiệt độ dùng 11 điểm; nhiệt độ thêm 4,5°C và 18,4°C. Quét năm mức reserve và hai loại pin. Sai số năng lượng dùng đủ 192 phần dư OOF, trọng số mỗi chuyến bằng nhau.","",
           "## Kết quả độ nhạy", "",
           "Tỷ lệ đổi verdict dưới đây là tần suất trên lưới đã khai, không phải xác suất Monte Carlo hoặc mức ảnh hưởng nhân quả. Các loại lưới có phạm vi và độ phân giải khác nhau; xem thứ hạng trong từng loại phép quét.","",
           "| Pin | Yếu tố | Loại phép quét | Số ca có ít nhất một điểm đổi verdict | Lượt đổi verdict / hợp lệ | Khoảng biến thiên margin trung bình (Wh) |",
           "|---|---|---|---:|---:|---:|"]
    for r in ranked.to_dict('records'):
        lines.append(f"| {r['battery_type']} | {LABELS[r['factor']]} | {r['sweep_kind']} | {r['scenarios_any_verdict_change']:,} | {r['change_rate']:.2%} | {r['mean_margin_range_Wh']:.3f} |")
    lines += ["", "![Độ nhạy](figures/sensitivity_ranking.png)","",
              "## Năng lượng, mức dư và chuyển verdict", "",
              "![Năng lượng](figures/energy_curves.png)","", "![Mức dư](figures/margin_curves.png)","",
              "![Chuyển verdict](figures/verdict_transitions.png)","",
              "## Phân tích sâu các ca FLY có mẫu thiếu dự trữ", "",
              f"Đã kiểm tra đủ **{len(diagnosis)} ca** từ bảng lọc trước đó, giữ riêng ID và pin. Một ca có thể phản ứng với nhiều yếu tố; không cộng các số dưới đây thành tổng ca.","",
              "| Pin | Yếu tố thay riêng | Số ca có ít nhất một điểm thiếu dự trữ trên lưới chính | Tổng ca đã lọc của pin |",
              "|---|---|---:|---:|"]
    for r in count_rows:lines.append(f"| {r['battery_type']} | {LABELS[r['factor']]} | {r['cases_shortfall_on_primary_grid']} | {r['focused_cases']} |")
    lines += ["",f"Có {none} ca không thiếu dự trữ khi quét riêng từng yếu tố trên lưới chính. Điều này không phủ nhận kết quả Monte Carlo phối hợp nhiều yếu tố; phép quét riêng không thể phân rã tương tác của các yếu tố.","",
              "Các số 0 ở cột SoH/gió/κ chỉ có nghĩa: khi đổi riêng yếu tố đó trong khoảng chính, chưa có ca trong nhóm này vượt ngưỡng thiếu dự trữ. Chúng vẫn làm thay đổi năng lượng/margin và có thể góp phần khi cùng các sai lệch khác xuất hiện.","",
              "Độ nhạy verdict và thiếu dự trữ là hai tiêu chí khác nhau. Ví dụ, gió có thể làm đổi verdict vì vượt VETO 10 m/s dù mức thay đổi nhu cầu năng lượng từ mô hình D2 tương đối nhỏ.","",
              "![Phản ứng từng yếu tố](figures/fly_single_factor_responses.png)","",
              "## Hai nhãn tham chiếu và vùng biên", "",
              "Đã chấm riêng REF-1/REF-2, cả hai cách gộp marginal; vùng biên và ngoài vùng biên tại w = 0,025; 0,05; 0,10. Membership tính riêng từ margin của đúng REF và giữ cố định theo D4. Có thêm bảng riêng nhóm marginal, tầng kịch bản và miền hỗ trợ cự ly/gió/nhiệt độ ban đầu.",
              "Nhãn gốc D4 dùng giả định pin TB47D và được giữ nguyên ngay cả khi ứng viên chuyển sang TB48D. Những con số này mô tả so sánh với chuẩn cố định, chưa phải phân tích nhãn tái tính theo thế giới đã thay đổi.","",
              "![Mức dự trữ và false-safe](figures/false_safe_vs_reserve.png)","",
              "## Các file để kiểm tra tiếp", "",
              "- `one_factor_curves.csv`: năng lượng, margin, thay đổi quyết định, vi phạm VETO ở mỗi điểm quét.",
              "- `one_factor_evaluations.csv.gz`: đủ từng kịch bản–pin–điểm quét, cả điểm không hợp lệ; CSV nén để giảm kích thước.",
              "- `scenario_factor_sensitivity.csv.gz`: tổng hợp từng kịch bản–pin–yếu tố.",
              "- `fly_case_factor_details.csv`, `fly_case_diagnosis.csv`: đủ các ca FLY đã lọc, không chỉ ca 4757.",
              "- `fly_cases_explained.csv`: bảng 457 ca với các cột giải thích bằng tiếng Việt; tỷ lệ MC vẫn giữ riêng với kết quả quét từng yếu tố.",
              "- `reference_metrics.csv`: tử số/mẫu số và số bị loại theo REF, cách gộp marginal và nhóm/vùng biên.",
              "- `verdict_transitions.csv`: số đếm chuyển verdict; `sensitivity_ranking.csv`: tần suất đổi và khoảng margin.","",
              "## Giới hạn và phần còn lại", "",
              "- Không kẹp các offset vượt miền vật lý vào biên: ghi không đánh giá và đếm riêng. Điểm ngoài miền dữ liệu hoặc vi phạm VETO vẫn được giữ nếu hợp lệ vật lý.",
              "- Cột `primary_error_shortfall` của các phép quét miền/policy/battery không được dùng để giải thích sai số đầu vào; chỉ dùng các nhánh sai lệch đã khai và pool OOF.",
              "- SoH/gió/nhiệt độ có quét toàn dải để xem độ nhạy kịch bản; khác với sai số quanh đầu vào. Hướng gió chưa được thêm vì D2 không có ánh xạ hướng đã kiểm chứng.",
              "- Các đường năng lượng là trung bình trên cohort hợp lệ của từng điểm; khi cohort đổi do offset không hợp lệ, đọc cùng số điểm bị loại. Đường delta so với baseline dùng cùng cohort hợp lệ.",
              "- Đây là kết quả phát triển, chưa có đóng băng/kiểm chéo cuối. Snapshot/replay E5, matched-reference secondary và danh mục ca thất bại đầy đủ vẫn cần hoàn tất trước nghiệm thu D5."]
    report=run/"sensitivity_report.md";report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    artifacts=[report,run/'fly_single_factor_responses.csv',run/'ranking_within_sweep_kind.csv',run/'fly_cases_explained.csv']+list(figdir.iterdir())
    (run/'report_manifest.json').write_text(json.dumps(dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_manifest_sha256=sha(run/'input_manifest.json'),code_sha256=sha(__file__),
        output_hashes={str(p.relative_to(run)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8')
    print(attribution.to_string(index=False));print(f"Saved report and 6 scientific figures to {run}")


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--refresh',action='store_true',help='Regenerate report/figures, retaining the core OAT results')
    a=p.parse_args();render(a.run,refresh=a.refresh)


if __name__=='__main__':main()
