"""
Sau duong co so quyet dinh — buoc 4 cua san pham D4 (Muc 7).

Module nay KHONG cham diem. No chi tra loi: voi mot kich ban, tung phuong phap
ra phan quyet gi. Viec do diem o src/evaluation_scenario.py.

-----------------------------------------------------------------------------
SAU PHUONG PHAP + MOT ABLATION
-----------------------------------------------------------------------------
Muc 7 nguyen van, tung dong:

    B0  Fixed SoC threshold
        "approve if SoC is above a pre-registered threshold; otherwise reject.
         Test several threshold values (e.g., 20%, 30%, 40%)"
        -> KHONG biet gi ve nhu cau nhiem vu. Do la han che cua chinh no.

    B1  Nominal endurance
        "compare planned mission time with a documented nominal endurance
         figure and reserve"
        -> 13 phut (DJI, TB47D, tai 1000 g) x SoC x SoH, roi so voi thoi luong
           ke hoach. Xem quyet dinh C19 ve viec nhan SoC.

    B1-pure
        Nhu B1 nhung KHONG nhan SoC — cach doc sat chu Muc 7 nhat. Bao ca hai
        de thay ro phan nao cua ket qua den tu viec B1 khong biet SoC.

    B2  Distance-only energy model
        "use D1 to estimate energy demand and compare it with available energy"

    B3  Multi-factor empirical model
        "use the best validated model selected in E2"   -> D2_ridge_preflight

    B5  Proposed safety-aware graded decision
        "use the selected energy model, available-energy calculation, reserve
         thresholds, and hard-rule veto"
        -> goi thang src.decision_rules.assess()

    B5-noHR  ablation, Muc 7 bat bao rieng
        "report a separate ablation where the proposed method's hard-rule layer
         is disabled, FOR ANALYSIS ONLY, never as the operational recommendation"

-----------------------------------------------------------------------------
LOP LUAT CUNG AP CHO AI — quyet dinh C23
-----------------------------------------------------------------------------
BANG CHINH: ap cho TAT CA. Muc 7: "Keep the safety-rule policy identical across
methods where the comparison is intended to isolate the energy-decision method."
Nho vay chenh lech giua cac duong co so den hoan toan tu cach quyet dinh nang
luong.

BANG THU HAI (bat buoc): tat luat cung cho B0..B3, giu cho B5 — cach doc sat
chu nhat. Chay bang co `ap_dung_luat_cung=False`.

Chi ap cho B5 thi B0 se duyet bay mot kich ban gio 15 m/s, va B5 thang khong
phai vi quyet dinh nang luong tot hon ma vi doi thu khong co lop an toan.

-----------------------------------------------------------------------------
NHI PHAN hay BA BAC — quyet dinh C24
-----------------------------------------------------------------------------
B0..B3 chi ra FLY / NO_FLY / INSUFFICIENT_DATA. Bac giua CHINH LA dong gop cua
phuong phap nhom (§5.7), nen cho B0..B3 muon bac do la xoa mat thu dang do.

    python3 -m src.baselines_decision --demo
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import GridSearchCV, RepeatedKFold

from src.available_energy import STATUS_OK, STATUS_OUT_OF_RANGE, available_energy
from src.decision_rules import (
    CONDITIONAL, FLY, INSUFFICIENT_DATA, NO_FLY, assess,
)
from src.models import model_registry
from src.reference_labeller import (
    _doc_bang_chuyen_bay, load_d2_protocol, load_d3_protocol, load_protocol,
    nan_sang_none, scenario_features,
)
from src.safety_invariants import PROFILE_CMU, check_hard_rules

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"

BASELINES_VERSION = "1.0.0"

# Ten phuong phap — thu tu nay dung cho moi bang ket qua
B0 = "B0"
B1 = "B1"
B1_PURE = "B1-pure"
B2 = "B2"
B3 = "B3"
B5 = "B5"
B5_NOHR = "B5-noHR"

THU_TU = [B0, B1, B1_PURE, B2, B3, B5, B5_NOHR]

# Ho so may bay — kich ban mo phong may bay CMU co thiet bi do
PROFILE = PROFILE_CMU

# Ly do B5 ra phan quyet — de tach "tu choi thua" theo NGUYEN NHAN.
# Khong co bang nay thi con so M-4 cua B5 chac chan bi doc nham: phan lon
# khong phai quyet dinh nang luong ma la co NGOAI SUY. Xem quyet dinh C26.
LD_DUYET = "duyet"
LD_LUAT_CUNG = "luat_cung_veto"
LD_NGOAI_DAI = "dau_vao_ngoai_dai"
LD_THIEU = "thieu_du_lieu"
LD_BIEN_DU_TRU = "bien_du_tru_duoi_nguong"
LD_BANG_BAT_DINH = "nam_trong_bang_bat_dinh"
LD_NGOAI_SUY = "ha_bac_vi_ngoai_suy_PD"


# ---------------------------------------------------------------------------
# Khop hai mo hinh nang luong, moi cai MOT LAN
# ---------------------------------------------------------------------------

def _khop_mo_hinh(ten: str):
    """
    Khop mot mo hinh trong `model_registry()` tren ca 192 chuyen that.

    Dung spec DA DONG BANG o configs/d2_protocol.yaml — khong them bot dac trung,
    khong doi dai sieu tham so. Bac tu do = 0.

    Cho phep boi Muc 11 tuan 6 ("finalize selected energy model") va Muc 7 B3
    ("use the best validated model selected in E2"). Thay cam chuyen khac —
    Muc 10 cam DOI THIET LAP sau khi thay ket qua cuoi.

    Tra ve (pipeline da khop, ten cot dac trung).
    """
    d2 = load_d2_protocol()
    spec = model_registry()[ten]

    nhom = {"distance_only": ["distance_2d_m"],
            "preflight": list(d2["features"]["preflight"]),
            "as_written": list(d2["features"]["as_written"])}
    cot = nhom[spec["features"]]

    muc_tieu = d2["target"]["column"]
    can = [c for c in cot if c != "duration_planned_s"] + [
        muc_tieu, "distance_2d_m", "speed_num"]
    df, _ = _doc_bang_chuyen_bay(can)
    if "duration_planned_s" not in df.columns:
        df["duration_planned_s"] = df["distance_2d_m"] / df["speed_num"]

    X = df[cot].to_numpy(float)
    y = df[muc_tieu].to_numpy(float)
    mo_hinh = spec["factory"]()

    if spec["param_grid"]:
        cv_cfg = d2["partitioning"]["cv"]
        if cv_cfg["scheme"] != "repeated_k_fold":
            raise RuntimeError(
                f"d2_protocol.yaml khai cach chia {cv_cfg['scheme']!r}, ham nay "
                f"chi cai dat repeated_k_fold.")
        gs = GridSearchCV(
            mo_hinh, spec["param_grid"], scoring="neg_mean_absolute_error",
            cv=RepeatedKFold(n_splits=cv_cfg["n_splits"],
                             n_repeats=cv_cfg["n_repeats"],
                             random_state=cv_cfg["random_state"]),
            n_jobs=-1)
        gs.fit(X, y)
        return gs.best_estimator_, cot

    mo_hinh.fit(X, y)
    return mo_hinh, cot


def khop_hai_mo_hinh() -> dict:
    """
    D1 cho duong co so B2, D2 cho B3 va B5.

    D1 KHONG co sieu tham so nen khong can CV — khop thang. D2 chon alpha bang
    CV long, dung cach d2_protocol.yaml khai.
    """
    return {
        "D1": _khop_mo_hinh("D1_distance_ols"),
        "D2": _khop_mo_hinh("D2_ridge_preflight"),
    }


def du_bao(mo_hinh, cot: list[str], df: pd.DataFrame,
           protocol: dict) -> np.ndarray:
    """
    Du bao nhu cau nang luong cho tung kich ban.

    Dong THIEU dac trung -> NaN, KHONG hoi mo hinh. §4.6 fail closed: dien gia
    tri thay the roi du bao la bien mot dong "khong biet" thanh mot con so trong
    nhu biet.
    """
    X = scenario_features(df, protocol, cot).to_numpy(float)
    du = np.isfinite(X).all(axis=1)
    out = np.full(len(df), np.nan)
    if du.any():
        out[du] = mo_hinh.predict(X[du])
    return out


# ---------------------------------------------------------------------------
# Lop luat cung dung chung
# ---------------------------------------------------------------------------

def _bao_cao_luat_cung(row, d3: dict, battery_type: str = "TB47D"):
    """
    Chay lop luat cung mot lan cho mot kich ban.

    MOI dau vao di qua `nan_sang_none()`. Hop dong cua D3 la "None nghia la
    THIEU"; bang kich ban doc tu CSV nen o trong thanh NaN, ma `NaN is None` la
    False. Khong quy doi thi NaN lot qua buoc kiem thieu, roi `NaN > 10.0` cung
    False nen HR-1 bao PASS — mot kich ban khong biet gio di qua lop luat cung
    nhu the gio binh thuong. Da gap that, xem OI-D4-6.
    """
    return check_hard_rules(
        payload_g=nan_sang_none(row.payload_g),
        speed_commanded_ms=nan_sang_none(row.speed_commanded_ms),
        distance_2d_m=nan_sang_none(row.distance_2d_m),
        wind_forecast_ms=nan_sang_none(row.wind_forecast_ms),
        ambient_temp_c=nan_sang_none(row.ambient_temp_c),
        altitude_m=nan_sang_none(row.altitude_m),
        soc=nan_sang_none(row.soc), soh=nan_sang_none(row.soh),
        battery_type=battery_type, profile=PROFILE, protocol=d3)


def _ap_luat_cung(phan_quyet: str, hard) -> str:
    """
    Ap lop luat cung len mot phan quyet da co.

    §4.6: lop nay chi HA, khong bao gio nang. Nen chi can hai nhanh.

    CO Y KHONG ap `hard.blocks_fly` (luat PD-1, PD-2 — ngoai dai co du lieu do
    lung). Hai luat do la DOWNGRADE: ha FLY xuong CONDITIONAL. Mot phuong phap
    NHI PHAN khong co bac giua nen khong ha duoc.
    Day la mot BAT DOI XUNG THAT va phai khai: tren kich ban ngoai envelope,
    B2 va B3 se ra FLY trong khi B5 ra CONDITIONAL. Do KHONG phai B5 kem hon —
    do chinh la dong gop cua no (§5.7). Nhung phai bao so kich ban bi anh huong,
    neu khong nguoi doc se doc thanh "B5 tu choi thua". Xem quyet dinh C25.
    """
    if hard.must_no_fly:
        return NO_FLY
    if hard.missing:
        return INSUFFICIENT_DATA
    return phan_quyet


# ---------------------------------------------------------------------------
# Tung duong co so
# ---------------------------------------------------------------------------

def _b0(row, nguong: float) -> str:
    """
    B0 — nguong SoC co dinh. KHONG biet gi ve nhu cau nhiem vu.

    Muc 7 cot "Limitation": "Ignores mission demand; threshold sweep required."
    Day la han che cua chinh phuong phap, phai de nguyen chu khong vá.
    """
    if row.soc is None or not np.isfinite(row.soc):
        return INSUFFICIENT_DATA
    if not 0.0 <= row.soc <= 1.0:
        return NO_FLY
    return FLY if row.soc >= nguong else NO_FLY


def _b1(row, cfg: dict, r: float, nhan_soc: bool) -> str:
    """
    B1 — nguong thoi luong bay danh dinh.

        t_ke_hoach  <=  endurance_kha_dung / (1 + r)

    `nhan_soc` True : endurance_kha_dung = 13 phut x SoC x SoH   (B1)
    `nhan_soc` False: endurance_kha_dung = 13 phut               (B1-pure)

    Dang `/(1 + r)` khop dinh nghia R = (co - can)/can cua §5.6, nen so sanh
    duoc voi B5. Dung `(1 - r)` se la mot dinh nghia du tru KHAC.

    HAI THIEN LECH, ca hai ve phia LAC QUAN, da khai o giao thuc:
      1. 13 phut do o 3355 g; may bay CMU 3680-4180 g
      2. bang DJI la "Hovering Time", khong phai bay hanh trinh
    """
    gt = [row.distance_2d_m, row.speed_commanded_ms]
    if nhan_soc:
        gt += [row.soc, row.soh]
    if any(g is None or not np.isfinite(g) for g in gt):
        return INSUFFICIENT_DATA
    if row.speed_commanded_ms <= 0:
        return NO_FLY
    if nhan_soc and not (0.0 <= row.soc <= 1.0 and 0.0 <= row.soh <= 1.0):
        return NO_FLY

    endurance_s = float(cfg["endurance_min"]) * 60.0
    if nhan_soc:
        endurance_s *= row.soc * row.soh

    t_ke_hoach = row.distance_2d_m / row.speed_commanded_ms
    return FLY if t_ke_hoach <= endurance_s / (1.0 + r) else NO_FLY


def _b_nang_luong(e_required: float, e_available: float | None,
                  trang_thai: str, r: float) -> str:
    """
    Than chung cua B2 va B3 — mot nguong duy nhat.

        R = (E_available - E_required) / E_required  >=  r  ->  FLY

    MOT nguong chu khong hai: bac giua la dong gop cua B5 (§5.7), cho B2/B3
    muon la xoa mat thu dang do. Xem quyet dinh C24.
    """
    if trang_thai == STATUS_OUT_OF_RANGE:
        return NO_FLY
    if trang_thai != STATUS_OK or e_available is None:
        return INSUFFICIENT_DATA
    if e_required is None or not np.isfinite(e_required):
        return INSUFFICIENT_DATA
    if e_required <= 0:
        return NO_FLY
    return FLY if (e_available - e_required) / e_required >= r else NO_FLY


def _ly_do_b5(d) -> str:
    """
    Vi sao B5 ra phan quyet do.

    Phan biet HAI nguon cua CONDITIONAL, vi chung noi hai chuyen khac han:
      - nam trong bang bat dinh cua mo hinh (r_min <= R < R_fly)
      - bi HA BAC vi dang ngoai suy (luat PD-1/PD-2)

    assess() xet bang bat dinh TRUOC, roi moi ha bac neu con la FLY. Nen mot
    CONDITIONAL do ha bac se co ly do ngoai suy dung o DAU danh sach reasons —
    do la cach duy nhat phan biet tu doi tuong Decision.
    """
    if d.verdict == FLY:
        return LD_DUYET
    if d.verdict == INSUFFICIENT_DATA:
        return LD_THIEU
    if d.verdict == NO_FLY:
        if d.hard_rule_report is not None and d.hard_rule_report.must_no_fly:
            return LD_LUAT_CUNG
        if d.available is not None and d.available.status == STATUS_OUT_OF_RANGE:
            return LD_NGOAI_DAI
        return LD_BIEN_DU_TRU
    # CONDITIONAL
    if d.reasons and "ngoai dai co du lieu do lung" in d.reasons[0]:
        return LD_NGOAI_SUY
    return LD_BANG_BAT_DINH


def _b5_khong_luat_cung(d) -> str:
    """
    B5-noHR — ablation, Muc 7 bat bao rieng.

    Dung LAI chinh cac con so ma assess() da tinh (margin_ratio, r_min, r_fly)
    thay vi tinh lai, de khong the lech khoi B5 vi mot ly do khac ngoai lop luat
    cung.

    `margin_ratio` None nghia la assess() dung som — vi vi pham luat cung, vi
    dau vao ngoai dai, hoac vi thieu du lieu. Hai truong hop sau van phai giu;
    chi truong hop dau moi duoc go.
    """
    if d.margin_ratio is None:
        if d.verdict == INSUFFICIENT_DATA:
            return INSUFFICIENT_DATA
        if d.available is not None and d.available.status == STATUS_OUT_OF_RANGE:
            return NO_FLY
        # Dung som vi luat cung — khong con so bien du tru de phan quyet.
        return INSUFFICIENT_DATA
    if d.margin_ratio < d.r_min:
        return NO_FLY
    if d.margin_ratio < d.r_fly:
        return CONDITIONAL
    return FLY


# ---------------------------------------------------------------------------
# Chay het cac duong co so tren ca bo kich ban
# ---------------------------------------------------------------------------

def chay_tat_ca(df: pd.DataFrame,
                protocol: dict | None = None,
                reserve_factor: float | None = None,
                soc_threshold: float | None = None,
                ap_dung_luat_cung: bool = True,
                battery_type: str = "TB47D",
                mo_hinh: dict | None = None) -> pd.DataFrame:
    """
    Chay bay phuong phap tren cung mot bo kich ban.

    `battery_type` "TB47D" (99.9 Wh) la gia tri chinh. "TB48D" (129.96 Wh) la
    DO NHAY BAT BUOC S-1: P§4.4 ghi ro "which pack the recorded flights used
    must be confirmed from the dataset documentation rather than assumed", ma
    bai Rodrigues TU MAU THUAN ve loai pin.

    `ap_dung_luat_cung` True  -> bang CHINH (quyet dinh C23)
                        False -> bang THU HAI; B5 van giu luat cung vi lop do
                                 la mot phan dinh nghia cua no (Muc 7)

    Tra ve `df` cong bay cot phan quyet, dat ten `verdict_<ma>`.
    """
    protocol = protocol or load_protocol()
    d3 = load_d3_protocol()
    cfg_b1 = protocol["baselines"]["B1"]

    r = (float(protocol["reference_label"]["method"]
               ["reserve_policy_for_reference"]["r"])
         if reserve_factor is None else float(reserve_factor))
    nguong_soc = (float(protocol["baselines"]["B0"]["thresholds"][0])
                  if soc_threshold is None else float(soc_threshold))

    mo_hinh = mo_hinh or khop_hai_mo_hinh()
    e_d1 = du_bao(*mo_hinh["D1"], df, protocol)
    e_d2 = du_bao(*mo_hinh["D2"], df, protocol)

    kq = {ma: [] for ma in THU_TU}
    ly_do_b5: list[str] = []

    for i, row in enumerate(df.itertuples()):
        if i and i % 3000 == 0:
            print(f"    duong co so {i}/{len(df)} ...", flush=True)

        hard = _bao_cao_luat_cung(row, d3, battery_type)
        av = available_energy(soc=nan_sang_none(row.soc),
                              soh=nan_sang_none(row.soh),
                              temp_c=nan_sang_none(row.ambient_temp_c),
                              battery_type=battery_type, protocol=d3)
        e_av = av.value_Wh if av.status == STATUS_OK else None

        tho = {
            B0: _b0(row, nguong_soc),
            B1: _b1(row, cfg_b1, r, nhan_soc=True),
            B1_PURE: _b1(row, cfg_b1, r, nhan_soc=False),
            B2: _b_nang_luong(e_d1[i], e_av, av.status, r),
            B3: _b_nang_luong(e_d2[i], e_av, av.status, r),
        }
        for ma, pq in tho.items():
            kq[ma].append(_ap_luat_cung(pq, hard) if ap_dung_luat_cung else pq)

        # B5 — goi thang assess(). Luat cung LUON bat: no la mot phan dinh
        # nghia cua B5 theo Muc 7, khong phai mot tuy chon.
        d = assess(payload_g=nan_sang_none(row.payload_g),
                   speed_commanded_ms=nan_sang_none(row.speed_commanded_ms),
                   altitude_m=nan_sang_none(row.altitude_m),
                   distance_2d_m=nan_sang_none(row.distance_2d_m),
                   wind_forecast_ms=nan_sang_none(row.wind_forecast_ms),
                   ambient_temp_c=nan_sang_none(row.ambient_temp_c),
                   soc=nan_sang_none(row.soc), soh=nan_sang_none(row.soh),
                   e_required_Wh=None if not np.isfinite(e_d2[i]) else e_d2[i],
                   reserve_factor=r, battery_type=battery_type,
                   profile=PROFILE, protocol=d3)
        kq[B5].append(d.verdict)
        kq[B5_NOHR].append(_b5_khong_luat_cung(d))
        ly_do_b5.append(_ly_do_b5(d))

    out = df.copy()
    for ma in THU_TU:
        out[f"verdict_{ma}"] = kq[ma]
    out["ly_do_B5"] = ly_do_b5
    out["e_required_D1_Wh"] = e_d1
    out["e_required_D2_Wh"] = e_d2
    out["reserve_factor"] = r
    out["soc_threshold_B0"] = nguong_soc
    out["hard_rules_applied_to_all"] = ap_dung_luat_cung
    out["battery_type"] = battery_type
    out["baselines_version"] = BASELINES_VERSION
    return out


# ---------------------------------------------------------------------------

def bang_phan_bo(df: pd.DataFrame) -> pd.DataFrame:
    """Dem phan quyet tung phuong phap — de nhin nhanh, chua phai cham diem."""
    return pd.DataFrame(
        {ma: df[f"verdict_{ma}"].value_counts() for ma in THU_TU}
    ).fillna(0).astype(int)


def _demo() -> None:
    protocol = load_protocol()
    print("Khop hai mo hinh nang luong ...")
    mh = khop_hai_mo_hinh()
    for ten, (_, cot) in mh.items():
        print(f"  {ten}: {len(cot)} dac trung — {', '.join(cot)}")

    goc = dict(scenario_id=1, stratum="main", payload_g=250.0,
               speed_commanded_ms=8.0, altitude_m=50.0, distance_2d_m=472.0,
               wind_forecast_ms=3.0, soc=0.8, soh=0.95, ambient_temp_c=15.0,
               hard_rule_probe=False, probe_limit=None, missing_field=None)

    print("\nPhan quyet theo SoC — tai 250 g, 472 m, 8 m/s, 15 C\n")
    print(f"{'SoC':>6}  " + "  ".join(f"{ma:>10}" for ma in THU_TU))
    print("-" * 86)
    for soc in (0.10, 0.20, 0.30, 0.40, 0.60, 1.00):
        kb = pd.DataFrame([{**goc, "soc": soc}])
        d = chay_tat_ca(kb, protocol, mo_hinh=mh)
        print(f"{soc:>6.2f}  " + "  ".join(
            f"{d[f'verdict_{ma}'].iloc[0]:>10}" for ma in THU_TU))

    print("\n\nLuat cung phu quyet — pin day\n")
    for ten, kw in (("gio 15 m/s", {"wind_forecast_ms": 15.0}),
                    ("toc do 25 m/s", {"speed_commanded_ms": 25.0}),
                    ("nhiet do -25 C", {"ambient_temp_c": -25.0})):
        kb = pd.DataFrame([{**goc, "soc": 1.0, **kw}])
        a = chay_tat_ca(kb, protocol, ap_dung_luat_cung=True, mo_hinh=mh)
        b = chay_tat_ca(kb, protocol, ap_dung_luat_cung=False, mo_hinh=mh)
        print(f"  {ten}")
        print(f"    co luat cung   : " + "  ".join(
            f"{ma}={a[f'verdict_{ma}'].iloc[0]}" for ma in (B0, B1, B2, B3, B5)))
        print(f"    khong luat cung: " + "  ".join(
            f"{ma}={b[f'verdict_{ma}'].iloc[0]}" for ma in (B0, B1, B2, B3, B5)))
    print("\n  Do la ly do quyet dinh C23 bat bao CA HAI bang: khong co lop luat")
    print("  cung, B0 va B1 duyet bay nhung kich ban nay.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        _demo()
        return
    ap.print_help()
    print("\nBuoc 4 chi cung cap ham. Viec chay tren ca bo kich ban va cham")
    print("diem thuoc src/evaluation_scenario.py (buoc 5).")


if __name__ == "__main__":
    main()
