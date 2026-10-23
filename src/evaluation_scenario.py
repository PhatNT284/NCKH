"""
Cham diem cac duong co so — buoc 5 cua san pham D4 (Muc 7, §6/E3, P§4.9).

Day la cho ca san pham D4 ra ket qua. Moi thu truoc do chi la chuan bi: bo sinh
ra DE BAI, bo gan nhan ra DAP AN, cac duong co so ra BAI LAM. Module nay cham.

-----------------------------------------------------------------------------
KHONG CHAM TREN CA 18000 KICH BAN
-----------------------------------------------------------------------------
Hai tang bi loai khoi bang chinh, da khai o giao thuc tu ban 1.0.1:

    hard_rule_probe   kich ban CO Y vuot gioi han. Moi phuong phap deu phai tu
                      choi, nen dua vao lam loang con so va lam B0/B1 trong
                      khoe len mot cach gia. Tang nay co bang RIENG, phuc vu
                      thuoc do M-7.
    missing_input     thieu dau vao thi phan quyet dung la INSUFFICIENT_DATA,
                      khong phai FLY/NO_FLY. Nhet vao confusion matrix se bop
                      meo ca ba lop. Tang nay phuc vu thuoc do M-10.

Va kich ban co nhan `unknown` bi loai khoi moi phep cham: khong co dap an thi
khong cham duoc. So luong bi loai PHAI in ra, khong duoc im lang.

-----------------------------------------------------------------------------
HAI PHEP ANH XA, ca hai deu phai khai
-----------------------------------------------------------------------------
NHAN THAM CHIEU (ba lop) -> nhi phan:
    infeasible -> KHONG kha thi
    marginal   -> KHONG kha thi   (mac dinh bao thu, quyet dinh C4)
    feasible   -> kha thi
Do nhay S-3 chay lai voi marginal -> kha thi.

PHAN QUYET HE THONG -> nhi phan:
    FLY                        -> duyet bay
    CONDITIONAL                -> KHONG duyet (§2.3: chua thuc thi duoc khi
                                  chua co bien phap) — quyet dinh C24
    NO_FLY, INSUFFICIENT_DATA  -> KHONG duyet

-----------------------------------------------------------------------------
BON O CUA BANG CHAM
-----------------------------------------------------------------------------
                         he thong DUYET      he thong TU CHOI
    dap an KHA THI       dung                TU CHOI THUA      (M-4)
    dap an KHONG KHA THI FALSE-SAFE  (M-2)   dung              (M-1)

O goc tren phai la o NGUY HIEM. Moi so sanh cuoi cung deu quy ve danh doi giua
o do va o duoi trai.

    python3 -m src.evaluation_scenario            # chay day du, ~10-20 phut
    python3 -m src.evaluation_scenario --nhanh    # bo qua do nhay S-1 (cham nhat)
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.baselines_decision import (
    B0, B1, B1_PURE, B2, B3, B5, B5_NOHR, THU_TU, chay_tat_ca, khop_hai_mo_hinh,
)
from src.decision_rules import CONDITIONAL, FLY, INSUFFICIENT_DATA, NO_FLY
from src.reference_labeller import (
    FEASIBLE, INFEASIBLE, MARGINAL, UNKNOWN, load_protocol,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"

EVAL_VERSION = "1.0.0"

# Tang bi loai khoi bang chinh — ly do o docstring dau file
TANG_LOAI = ("hard_rule_probe", "missing_input")


def doc_kich_ban_da_gan_nhan() -> pd.DataFrame:
    p = REPORTS / "d4_scenarios_labelled.csv"
    if not p.exists():
        raise SystemExit(
            f"Khong tim thay {p.relative_to(REPO_ROOT)}.\n"
            "Chay truoc:\n"
            "  python3 -m src.scenario_generator\n"
            "  python3 -m src.reference_labeller")
    # low_memory=False: hai cot `probe_limit` va `missing_field` lan None voi
    # chuoi nen pandas doan kieu khac nhau giua cac khoi, sinh DtypeWarning.
    return pd.read_csv(p, low_memory=False)


# ---------------------------------------------------------------------------
# Hai phep anh xa
# ---------------------------------------------------------------------------

def nhan_sang_nhi_phan(nhan: pd.Series, marginal_la_kha_thi: bool = False):
    """
    Ba lop -> nhi phan. `None` cho `unknown` (khong cham duoc).

    `marginal_la_kha_thi` False la mac dinh BAO THU (quyet dinh C4): mot kich
    ban nam duoi he so du tru duoc coi la khong kha thi. True la do nhay S-3.
    Cach gop quyet dinh truc tiep con so false-safe, nen phai bao ca hai.
    """
    anh_xa = {FEASIBLE: True, INFEASIBLE: False,
              MARGINAL: bool(marginal_la_kha_thi), UNKNOWN: None}
    return nhan.map(anh_xa)


def phan_quyet_sang_nhi_phan(pq: pd.Series, conditional_la_duyet: bool = False):
    """
    Phan quyet -> co duyet bay hay khong.

    CONDITIONAL mac dinh tinh la KHONG duyet: §2.3 noi no chua thuc thi duoc khi
    chua co bien phap giam thieu. Quyet dinh C24.
    """
    duyet = {FLY}
    if conditional_la_duyet:
        duyet.add(CONDITIONAL)
    return pq.isin(duyet)


# ---------------------------------------------------------------------------
# Thuoc do
# ---------------------------------------------------------------------------

def _mot_phuong_phap(dap_an: pd.Series, duyet: pd.Series,
                     vung_bien: pd.Series | None = None) -> dict:
    """
    Bon o cua bang cham, roi moi thuoc do rut ra tu do.

    `dap_an` True = kha thi, False = khong kha thi, None = khong cham duoc.
    """
    co = dap_an.notna()
    da, du = dap_an[co].astype(bool), duyet[co].astype(bool)

    tp = int(( da &  du).sum())   # kha thi, duyet       -> dung
    fp = int((~da &  du).sum())   # KHONG kha thi, duyet -> FALSE-SAFE
    fn = int(( da & ~du).sum())   # kha thi, tu choi     -> TU CHOI THUA
    tn = int((~da & ~du).sum())   # khong kha thi, tu choi -> dung

    kha_thi = tp + fn
    khong_kha_thi = fp + tn

    def ty_le(a, b):
        return float(a / b) if b else float("nan")

    kq = {
        "n_cham": int(co.sum()),
        "n_bo_qua_unknown": int((~co).sum()),
        "n_kha_thi": kha_thi,
        "n_khong_kha_thi": khong_kha_thi,
        "TP": tp, "FP_false_safe": fp, "FN_tu_choi_thua": fn, "TN": tn,
        # M-1 thuoc do an toan CHINH
        "M1_infeasible_recall": ty_le(tn, khong_kha_thi),
        # M-2 huong nguy hiem
        "M2_false_safe_rate": ty_le(fp, khong_kha_thi),
        # M-4 huong phien toai
        "M4_unnecessary_rejection_rate": ty_le(fn, kha_thi),
        # M-5
        "M5_precision": ty_le(tp, tp + fp),
        "M5_recall": ty_le(tp, tp + fn),
    }
    p, r = kq["M5_precision"], kq["M5_recall"]
    kq["M5_f1"] = float(2 * p * r / (p + r)) if (p + r) else float("nan")

    # M-3 tach theo vung bien
    if vung_bien is not None:
        vb = vung_bien[co].astype(bool)
        for ten, mask in (("bien", vb), ("ngoai_bien", ~vb)):
            n_khong = int((~da & mask).sum())
            n_fs = int((~da & du & mask).sum())
            kq[f"M3_false_safe_count_{ten}"] = n_fs
            kq[f"M3_false_safe_rate_{ten}"] = ty_le(n_fs, n_khong)
    return kq


def cham_diem(df: pd.DataFrame,
              cot_nhan: str = "label_ref1",
              cot_bien: str = "boundary_ref1",
              marginal_la_kha_thi: bool = False,
              conditional_la_duyet: bool = False) -> pd.DataFrame:
    """Mot bang: moi dong mot phuong phap, moi cot mot thuoc do."""
    dap_an = nhan_sang_nhi_phan(df[cot_nhan], marginal_la_kha_thi)
    vb = df[cot_bien] if cot_bien in df.columns else None

    hang = []
    for ma in THU_TU:
        duyet = phan_quyet_sang_nhi_phan(df[f"verdict_{ma}"],
                                         conditional_la_duyet)
        hang.append({"phuong_phap": ma, **_mot_phuong_phap(dap_an, duyet, vb)})
    return pd.DataFrame(hang)


def confusion_nhi_phan(df: pd.DataFrame, cot_nhan: str = "label_ref1",
                       **kw) -> pd.DataFrame:
    """M-5 — bang bon o cho tung phuong phap, dang dai."""
    dap_an = nhan_sang_nhi_phan(df[cot_nhan], kw.get("marginal_la_kha_thi", False))
    co = dap_an.notna()
    hang = []
    for ma in THU_TU:
        duyet = phan_quyet_sang_nhi_phan(df[f"verdict_{ma}"],
                                         kw.get("conditional_la_duyet", False))
        da, du = dap_an[co].astype(bool), duyet[co].astype(bool)
        for ten_da, m_da in (("kha_thi", da), ("khong_kha_thi", ~da)):
            for ten_du, m_du in (("duyet", du), ("tu_choi", ~du)):
                hang.append({"phuong_phap": ma, "dap_an": ten_da,
                             "he_thong": ten_du, "so_kich_ban": int((m_da & m_du).sum())})
    return pd.DataFrame(hang)


def confusion_ba_lop(df: pd.DataFrame, cot_nhan: str = "label_ref1") -> pd.DataFrame:
    """
    M-6 — confusion matrix ba lop. CHI cho B5 va B5-noHR.

    B0..B3 la quy tac nhi phan (quyet dinh C24), khong co bac giua, nen bang ba
    lop cua chung se co mot cot rong — vo nghia chu khong phai thong tin.
    """
    hang = []
    for ma in (B5, B5_NOHR):
        for nhan in (FEASIBLE, MARGINAL, INFEASIBLE):
            con = df[df[cot_nhan] == nhan]
            for pq in (FLY, CONDITIONAL, NO_FLY, INSUFFICIENT_DATA):
                hang.append({"phuong_phap": ma, "dap_an": nhan, "phan_quyet": pq,
                             "so_kich_ban": int((con[f"verdict_{ma}"] == pq).sum())})
    return pd.DataFrame(hang)


# ---------------------------------------------------------------------------
# M-7, M-8, M-9, M-10 — do tren tang rieng
# ---------------------------------------------------------------------------

def kiem_toan_luat_cung(kb_day_du: pd.DataFrame, protocol: dict,
                        mo_hinh: dict) -> pd.DataFrame:
    """
    M-7 — so vi pham luat cung bi duyet sai. Muc tieu 0.

    Do tren tang `hard_rule_probe`, voi CA HAI cau hinh:
      - luat cung bat cho tat ca (bang chinh): ky vong 0 cho moi phuong phap,
        THEO THIET KE chu khong phai thanh tich
      - luat cung tat cho B0..B3 (bang thu hai): day moi la con so co y nghia

    Quyet dinh C23 bat viet ro dieu nay, neu khong "0 vi pham" doc nhu mot ket
    qua trong khi no la mot hang so.
    """
    probe = kb_day_du[kb_day_du["stratum"] == "hard_rule_probe"]
    hang = []
    for ap, ten in ((True, "bang_chinh"), (False, "bang_thu_hai")):
        d = chay_tat_ca(probe, protocol, ap_dung_luat_cung=ap, mo_hinh=mo_hinh)
        for ma in THU_TU:
            duyet = int((d[f"verdict_{ma}"] == FLY).sum())
            hang.append({
                "cau_hinh": ten, "luat_cung_ap_cho_tat_ca": ap,
                "phuong_phap": ma, "n_kich_ban_vi_pham": len(probe),
                "M7_duyet_sai": duyet,
                "M7_ty_le": float(duyet / len(probe)) if len(probe) else np.nan,
                "dat_muc_tieu_0": duyet == 0,
            })
    return pd.DataFrame(hang)


def fail_closed(kb_day_du: pd.DataFrame, protocol: dict,
                mo_hinh: dict) -> pd.DataFrame:
    """
    M-10 — thieu dau vao thi khong duoc duyet bay. Do tren tang `missing_input`.

    §4.6 fail closed. Ty le phai bang 1.0 cho moi phuong phap; khac 1.0 la LOI
    AN TOAN, khong phai diem kem.
    """
    thieu = kb_day_du[kb_day_du["stratum"] == "missing_input"]
    d = chay_tat_ca(thieu, protocol, mo_hinh=mo_hinh)
    hang = []
    for ma in THU_TU:
        pq = d[f"verdict_{ma}"]
        khong_duyet = int((pq != FLY).sum())
        hang.append({
            "phuong_phap": ma, "n_kich_ban_thieu": len(thieu),
            "M10_khong_duyet": khong_duyet,
            "M10_ty_le_fail_closed": float(khong_duyet / len(thieu)),
            "dat": khong_duyet == len(thieu),
            "n_insufficient_data": int((pq == INSUFFICIENT_DATA).sum()),
        })
    return pd.DataFrame(hang)


def do_do_tre(kb: pd.DataFrame, protocol: dict, mo_hinh: dict,
              n_mau: int = 200) -> pd.DataFrame:
    """
    M-8 — do tre quyet dinh.

    Con so PHU THUOC PHAN CUNG. Quy uoc cua repo (README muc 2): tai lieu chi
    duoc noi ve TI LE giua cac phuong phap, khong chep con so tuyet doi.
    """
    mau = kb.head(n_mau)
    t0 = time.perf_counter()
    chay_tat_ca(mau, protocol, mo_hinh=mo_hinh)
    tong_ms = (time.perf_counter() - t0) * 1000
    return pd.DataFrame([{
        "n_kich_ban": len(mau),
        "tong_ms_cho_ca_7_phuong_phap": round(tong_ms, 1),
        "ms_moi_kich_ban": round(tong_ms / len(mau), 3),
        "ghi_chu": "phu thuoc phan cung — chi doc TI LE, khong chep so tuyet doi",
    }])


def ph1_rang_buoc_hon(df: pd.DataFrame) -> pd.DataFrame:
    """
    M-9 — so kich ban ma PH-1 rang buoc hon luat du tru.

    Tren 192 chuyen CMU con so nay la 0/192. Neu o D4 cung ra 0 thi KET LUAN LA
    BO SINH CHUA QUET DU RONG, khong phai PH-1 vo dung — xem COV-2.
    """
    ngan_cao = (df["distance_2d_m"] < 420) & (df["altitude_m"] >= 75)
    return pd.DataFrame([{
        "n_kich_ban": len(df),
        "n_ngan_va_bay_cao": int(ngan_cao.sum()),
        "ty_le": float(ngan_cao.mean()),
        "ghi_chu": "vung duy nhat PH-1 co the rang buoc hon luat du tru (COV-2)",
    }])


def tu_choi_theo_nguyen_nhan(df: pd.DataFrame,
                             cot_nhan: str = "label_ref1") -> pd.DataFrame:
    """
    Tach phan quyet cua B5 theo NGUYEN NHAN — quyet dinh C26.

    Khong co bang nay thi con so M-4 cua B5 chac chan bi doc nham. Tren bo kich
    ban nay phan lon "tu choi" cua B5 KHONG phai quyet dinh nang luong ma la co
    NGOAI SUY: mo hinh dang chay ngoai dai cu ly co du lieu do lung, va B5 noi
    ra. Do chinh la viec no duoc thiet ke de lam (§5.7), khong phai mot khiem
    khuyet.

    Bang nay chia rieng tung nguyen nhan, va chia rieng cho nhung kich ban ma
    DAP AN noi la kha thi — tuc dung nhung kich ban tinh vao M-4.
    """
    dap_an = nhan_sang_nhi_phan(df[cot_nhan])
    hang = []
    for ten, con in (("tat_ca", df),
                     ("dap_an_kha_thi", df[dap_an == True]),      # noqa: E712
                     ("dap_an_khong_kha_thi", df[dap_an == False])):  # noqa: E712
        if not len(con):
            continue
        dem = con["ly_do_B5"].value_counts()
        for ly_do, n in dem.items():
            hang.append({"tap": ten, "ly_do": ly_do, "so_kich_ban": int(n),
                         "ty_le_trong_tap": float(n / len(con)),
                         "n_tap": len(con)})
    return pd.DataFrame(hang)


def quan_he_cau_truc(protocol: dict) -> pd.DataFrame:
    """
    Ghi lai quan he DAI SO giua khoan du phong cua nhan va nguong cua he thong.

        nhan goi KHA THI  <=>  E_av >= (1+r)(E_pred + a)
        => R_sys >= r + (1+r)*a / E_pred
        nguong FLY        :    R_fly = r + b / E_pred

    Khi (1+r)*a >= b thi MOI kich ban nhan goi la kha thi deu tu dong vuot
    nguong FLY. Tuc bac giua CONDITIONAL KHONG THE bi tinh la tu choi thua, va
    M-4 bang 0 la TAT YEU chu khong phai do duoc.

    Day la mot tinh chat phai BAO, khong phai mot thu de sua: a va b da dong
    bang va co nguoi ky. Chinh chung sau khi thay ket qua la dung dieu ma ca
    file giao thuc nay dung de chan.
    """
    a = float(protocol["reference_label"]["frozen_numbers"]
              ["uncertainty_allowance_Wh"])
    r = float(protocol["reference_label"]["method"]
              ["reserve_policy_for_reference"]["r"])
    import yaml
    with open(REPO_ROOT / "configs" / "d3_protocol.yaml", encoding="utf-8") as fh:
        b = float(yaml.safe_load(fh)["energy_required"]["measured_error"]
                  ["p95_abs_residual_Wh"])
    trai = (1 + r) * a
    return pd.DataFrame([{
        "a_khoan_du_phong_nhan_Wh": a,
        "b_khoan_bat_dinh_he_thong_Wh": b,
        "r": r,
        "(1+r)*a": round(trai, 4),
        "M4_bang_0_la_tat_yeu": bool(trai >= b),
        "bien_cua_bat_dang_thuc_Wh": round(trai - b, 4),
        "a_doi_dau_khi_nho_hon": round(b / (1 + r), 4),
        "ghi_chu": ("Khi (1+r)*a >= b, moi kich ban nhan goi la kha thi deu tu "
                    "dong vuot nguong FLY. M-4 = 0 KHONG phai ket qua do duoc."),
    }])


# ---------------------------------------------------------------------------
# Duong danh doi
# ---------------------------------------------------------------------------

def duong_danh_doi(kb: pd.DataFrame, protocol: dict, mo_hinh: dict) -> pd.DataFrame:
    """
    Muc 7: "Results must include the trade-off curve over reserve factors and
    fixed-SoC thresholds."

    Quet he so du tru cho moi phuong phap dung mo hinh nang luong, va quet
    nguong SoC cho B0. Hai truc khac nhau nen quet rieng roi ghep.
    """
    cfg = protocol["metrics"]["tradeoff_curve"]
    hang = []

    for r in cfg["reserve_sweep"]:
        d = chay_tat_ca(kb, protocol, reserve_factor=r, mo_hinh=mo_hinh)
        bang = cham_diem(d)
        for _, row in bang.iterrows():
            hang.append({"truc": "he_so_du_tru", "gia_tri": r,
                         "phuong_phap": row["phuong_phap"],
                         "M2_false_safe_rate": row["M2_false_safe_rate"],
                         "M4_unnecessary_rejection_rate":
                             row["M4_unnecessary_rejection_rate"],
                         "M1_infeasible_recall": row["M1_infeasible_recall"]})

    for s in cfg["soc_threshold_sweep"]:
        d = chay_tat_ca(kb, protocol, soc_threshold=s, mo_hinh=mo_hinh)
        bang = cham_diem(d)
        row = bang[bang["phuong_phap"] == B0].iloc[0]
        hang.append({"truc": "nguong_soc_B0", "gia_tri": s, "phuong_phap": B0,
                     "M2_false_safe_rate": row["M2_false_safe_rate"],
                     "M4_unnecessary_rejection_rate":
                         row["M4_unnecessary_rejection_rate"],
                     "M1_infeasible_recall": row["M1_infeasible_recall"]})
    return pd.DataFrame(hang)


# ---------------------------------------------------------------------------
# Bon do nhay bat buoc
# ---------------------------------------------------------------------------

def do_nhay(kb: pd.DataFrame, kb_chinh: pd.DataFrame, protocol: dict,
            mo_hinh: dict, bo_qua_s1: bool = False) -> pd.DataFrame:
    """
    S-1 pin TB48D · S-2 nhan REF-2 · S-3 marginal la kha thi · S-4 do rong vung bien

    Ca bon deu khai BAT BUOC trong giao thuc. S-1 phai chay lai toan bo nen
    cham nhat; `--nhanh` bo qua no de thu nhanh, nhung ban cuoi PHAI co.
    """
    hang = []

    def them(ma_do_nhay, mo_ta, bang):
        for _, row in bang.iterrows():
            hang.append({"do_nhay": ma_do_nhay, "mo_ta": mo_ta,
                         "phuong_phap": row["phuong_phap"],
                         "M2_false_safe_rate": row["M2_false_safe_rate"],
                         "M4_unnecessary_rejection_rate":
                             row["M4_unnecessary_rejection_rate"],
                         "M1_infeasible_recall": row["M1_infeasible_recall"]})

    them("goc", "cau hinh chinh", cham_diem(kb_chinh))

    if not bo_qua_s1:
        d = chay_tat_ca(kb, protocol, battery_type="TB48D", mo_hinh=mo_hinh)
        d = d[~d["stratum"].isin(TANG_LOAI)]
        them("S-1", "E_nominal = 129.96 Wh (TB48D) thay cho 99.9 (TB47D)",
             cham_diem(d))

    them("S-2", "cham theo nhan REF-2 (mo hinh vat ly) thay cho REF-1",
         cham_diem(kb_chinh, cot_nhan="label_ref2", cot_bien="boundary_ref1"))

    them("S-3", "marginal gop vao KHA THI thay vi khong kha thi",
         cham_diem(kb_chinh, marginal_la_kha_thi=True))

    # S-4 — do rong vung bien. Tinh lai co tu margin_ratio da luu.
    r = float(protocol["reference_label"]["method"]
              ["reserve_policy_for_reference"]["r"])
    for w in (0.025, 0.10):
        rr = kb_chinh["margin_ratio_ref1"].to_numpy(float)
        tam = kb_chinh.copy()
        tam["boundary_w"] = (np.abs(rr - r) <= w) | (np.abs(rr) <= w)
        them(f"S-4 (w={w})", f"do rong vung bien {w} thay cho 0.05",
             cham_diem(tam, cot_bien="boundary_w"))

    return pd.DataFrame(hang)


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nhanh", action="store_true",
                    help="bo qua do nhay S-1 (cham nhat); ban cuoi PHAI co")
    args = ap.parse_args()

    protocol = load_protocol()
    print(f"Giao thuc D4 {protocol['meta']['version']}\n")

    kb = doc_kich_ban_da_gan_nhan()
    print(f"Doc {len(kb)} kich ban da gan nhan")

    kb_chinh_tho = kb[~kb["stratum"].isin(TANG_LOAI)]
    print(f"  bang chinh: {len(kb_chinh_tho)} kich ban "
          f"(da loai {len(kb) - len(kb_chinh_tho)} cua hai tang "
          f"{', '.join(TANG_LOAI)})")
    n_unknown = int((kb_chinh_tho["label_ref1"] == UNKNOWN).sum())
    print(f"  trong do {n_unknown} kich ban nhan `unknown` — khong cham duoc\n")

    print("Khop hai mo hinh nang luong ...")
    mo_hinh = khop_hai_mo_hinh()

    print("\nChay 7 phuong phap tren bang chinh ...")
    kb_chinh = chay_tat_ca(kb_chinh_tho, protocol, mo_hinh=mo_hinh)

    REPORTS.mkdir(exist_ok=True)

    print("\n1/8  bang so sanh chinh ...")
    chinh = cham_diem(kb_chinh)
    chinh.insert(0, "cau_hinh", "luat cung ap cho tat ca (C23)")
    chinh.to_csv(REPORTS / "d4_main_comparison.csv", index=False)

    print("2/8  confusion matrix ...")
    pd.concat([
        confusion_nhi_phan(kb_chinh).assign(loai="nhi_phan"),
        confusion_ba_lop(kb_chinh).rename(
            columns={"phan_quyet": "he_thong"}).assign(loai="ba_lop"),
    ], ignore_index=True).to_csv(
        REPORTS / "d4_confusion_matrices.csv", index=False)

    print("3/8  tach theo vung bien ...")
    chinh[["phuong_phap"] + [c for c in chinh.columns if c.startswith("M3")]] \
        .to_csv(REPORTS / "d4_boundary_breakdown.csv", index=False)

    print("4/8  kiem toan luat cung (M-7) va fail-closed (M-10) ...")
    pd.concat([
        kiem_toan_luat_cung(kb, protocol, mo_hinh).assign(bang="M7_luat_cung"),
        fail_closed(kb, protocol, mo_hinh).assign(bang="M10_fail_closed"),
    ], ignore_index=True).to_csv(
        REPORTS / "d4_hard_rule_audit.csv", index=False)

    print("5/8  tach tu choi cua B5 theo nguyen nhan ...")
    tc = tu_choi_theo_nguyen_nhan(kb_chinh)
    tc.to_csv(REPORTS / "d4_b5_rejection_causes.csv", index=False)

    print("6/8  quan he cau truc giua khoan du phong va nguong ...")
    qh = quan_he_cau_truc(protocol)
    qh.to_csv(REPORTS / "d4_structural_relation.csv", index=False)

    print("7/8  duong danh doi ...")
    duong_danh_doi(kb_chinh_tho, protocol, mo_hinh).to_csv(
        REPORTS / "d4_tradeoff_curve.csv", index=False)

    print("8/8  bon do nhay bat buoc ...")
    do_nhay(kb, kb_chinh, protocol, mo_hinh, bo_qua_s1=args.nhanh).to_csv(
        REPORTS / "d4_sensitivity_runs.csv", index=False)

    # ---------------------------------------------------------------- in ra
    cot = ["phuong_phap", "M1_infeasible_recall", "M2_false_safe_rate",
           "M4_unnecessary_rejection_rate", "M5_f1"]
    print("\n" + "=" * 74)
    print("BANG CHINH — simulation-derived, KHONG phai ground truth")
    print("=" * 74)
    print(chinh[cot].to_string(
        index=False, float_format=lambda v: f"{v:.4f}"))

    print("\n  M-2 (false-safe) la huong NGUY HIEM: dap an noi khong kha thi ma")
    print("  he thong duyet bay. M-4 la huong phien toai. Doc hai cot do CUNG")
    print("  NHAU — mot phuong phap tu choi tat ca se co M-2 = 0 hoan hao.")

    tot = chinh.loc[chinh["M2_false_safe_rate"].idxmin(), "phuong_phap"]
    print(f"\n  M-2 thap nhat: {tot}")
    print(f"  M-4 cua B5: {chinh.loc[chinh.phuong_phap == B5, 'M4_unnecessary_rejection_rate'].iloc[0]:.4f}")

    # ------------------------------------------------- hai canh bao bat buoc
    print("\n" + "=" * 74)
    print("HAI CON SO KHONG DUOC BAO NHU NO HIEN RA")
    print("=" * 74)

    q = qh.iloc[0]
    if q["M4_bang_0_la_tat_yeu"]:
        print(f"1. M-4 = 0 la TAT YEU, khong phai do duoc.")
        print(f"   (1+r)*a = {q['(1+r)*a']} >= b = {q['b_khoan_bat_dinh_he_thong_Wh']}")
        print(f"   => moi kich ban nhan goi la kha thi deu tu dong vuot nguong")
        print(f"   FLY. Bac giua CONDITIONAL khong the bi tinh la tu choi thua.")
        print(f"   Bien cua bat dang thuc chi {q['bien_cua_bat_dang_thuc_Wh']} Wh.")
        print(f"   => CAM viet 'bac giua cai thien an toan ma khong ton them'.")

    kt = tc[tc["tap"] == "dap_an_kha_thi"]
    ns = kt[kt["ly_do"] == "ha_bac_vi_ngoai_suy_PD"]
    if len(ns):
        ty = float(ns["ty_le_trong_tap"].iloc[0])
        print(f"\n2. M-4 cua B5 phan lon KHONG phai quyet dinh nang luong:")
        print(f"   {ty:.1%} kich ban dap-an-kha-thi bi B5 ha bac vi NGOAI SUY")
        print(f"   (luat PD-1/PD-2 — mo hinh chay ngoai dai cu ly co du lieu).")
        print(f"   Doc nguyen con so thanh 'B5 tu choi thua 72 %' la SAI. Dung")
        print(f"   la: B5 gan co ngoai vung hieu luc cho {ty:.0%} kich ban.")

    print("\n" + "=" * 74)
    print("DA GHI 8 BANG VAO reports/")
    print("=" * 74)
    for f in ("d4_main_comparison", "d4_confusion_matrices",
              "d4_boundary_breakdown", "d4_hard_rule_audit",
              "d4_b5_rejection_causes", "d4_structural_relation",
              "d4_tradeoff_curve", "d4_sensitivity_runs"):
        print(f"  {f}.csv")

    if args.nhanh:
        print("\nCHU Y: da bo qua do nhay S-1. Ban cuoi PHAI chay day du.")

    print("\nMOI con so o day la simulation-derived. KHONG chung minh gi ve an")
    print("toan trong thuc te (cong chan Muc 12.1).")


if __name__ == "__main__":
    main()
