"""
Nhan tham chieu cho 18000 kich ban — buoc 3 cua san pham D4 (§6/E3).

Tra loi mot cau duy nhat cho tung kich ban: DANG LE no kha thi hay khong.
Module nay KHONG cham diem phuong phap nao — viec do o src/baselines_decision.py.

-----------------------------------------------------------------------------
HAI NHAN, KHONG PHAI MOT
-----------------------------------------------------------------------------
§6/E3: "Prefer a reference procedure independent of the candidate model. If the
reference uses the same model family or fitted predictions as a candidate, flag
that comparison as potentially circular and add a sensitivity analysis with a
distinct conservative reference assumption."

    REF-1   E_ref = E_d2_prediction + 1.2924 Wh
            Du bao cua chinh mo hinh D2, cong khoan du phong tu phan du
            out-of-fold. VONG TRON — va thay cho phep, voi dieu kien ghi co.

    REF-2   E_ref = k * P_ideal(mass) * t_planned / 3600
            voi k = p95( E_do_duoc / (P_ideal * t/3600) ) tren 192 chuyen that.
            Mo hinh vat ly, hieu chinh bang mot so vo huong DO DUOC. Khong dung
            he so hoi quy nao khop tu CMU, nen doc lap ho mo hinh voi ca D1, D2,
            D3. `eta` triet tieu nen cong thuc khong phu thuoc tham so khop nao.
            Do nhay bat buoc S-2. Xem quyet dinh C22.

Chay benchmark HAI LAN, bao ca hai bang canh nhau. Neu xep hang cac duong co so
DOI khi thay nhan — do la ket qua phai bao, khong phai loi.

-----------------------------------------------------------------------------
MO HINH HOC TU DAU
-----------------------------------------------------------------------------
Hoc tu 192 CHUYEN BAY THAT. KHONG hoc tu kich ban — va khong the, vi kich ban
khong co cot muc tieu nao (GEN-5 cam, co test canh).

Khop MOT LAN tren ca 192 chuyen roi dong bang he so ra file. Cho phep boi Muc 11
tuan 6 ("finalize selected energy model") va Muc 7 B3 ("use the best validated
model selected in E2"). Thay cam chuyen khac — Muc 10 cam DOI THIET LAP sau khi
thay ket qua cuoi. Bac tu do cua buoc khop nay = 0: spec dong bang tu tuan 2.

CAM noi "mo hinh nay sai 0.657 Wh". Con so do la sai so cua QUY TRINH
cross-validation, do tren 25 lan khop khac. Bo he so cuoi khong do duoc sai so
cua chinh no — khong con du lieu nao no chua thay.

    python3 -m src.reference_labeller --fit      # chi khop + ghi he so
    python3 -m src.reference_labeller            # gan nhan, ghi d4_scenarios_labelled.csv
    python3 -m src.reference_labeller --check     # chi chay GEN-4b, GEN-6
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import GridSearchCV, RepeatedKFold

from src.available_energy import STATUS_OK, available_energy
from src.models import RIDGE_ALPHAS, make_d2
from src.physics_m100 import ideal_hover_power_W
from src.scenario_generator import S_MISSING, S_PROBE

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"

LABELLER_VERSION = "1.0.0"

# Ba lop nhan — §6/E3 "simulated feasible/marginal/infeasible cases"
FEASIBLE = "feasible"
MARGINAL = "marginal"
INFEASIBLE = "infeasible"
UNKNOWN = "unknown"          # thieu dau vao -> khong gan nhan duoc

HAI_NHAN = ("REF-1", "REF-2")


def nan_sang_none(x):
    """
    Quy doi NaN -> None truoc khi goi cac module cua san pham D3.

    HOP DONG cua D3 la "None nghia la THIEU" — xem §4.6 fail closed. Nhung bang
    kich ban doc tu CSV nen o trong thanh NaN, ma `NaN is None` la False.

    HAU QUA NEU KHONG QUY DOI, da gap that o buoc 4:
      - safety_invariants kiem thieu bang `gia_tri is None` -> NaN lot qua
      - roi `NaN > 10.0` cung la False -> HR-1 bao PASS
      => mot kich ban KHONG BIET gio di qua lop luat cung nhu the gio binh
         thuong. Huong sai nguy hiem: thieu du lieu an toan ma he thong noi qua.

    Loi nam o RANH GIOI D4-D3, khong phai trong D3. Quy doi o day, mot cho.
    """
    if x is None:
        return None
    try:
        return None if not np.isfinite(x) else x
    except TypeError:
        return x


def load_protocol() -> dict:
    with open(REPO_ROOT / "configs" / "d4_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_d2_protocol() -> dict:
    with open(REPO_ROOT / "configs" / "d2_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_d3_protocol() -> dict:
    """Can `aircraft_profiles` cho takeoff_mass_g()."""
    with open(REPO_ROOT / "configs" / "d3_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Khop mo hinh mot lan
# ---------------------------------------------------------------------------

def _doc_bang_chuyen_bay(can: list[str]) -> tuple[pd.DataFrame, Path]:
    """
    Doc bang cap chuyen bay, chon file CO DU COT can dung.

    KHONG chon theo thu tu ten file: reports/flight_level_week3.csv chi la bang
    DOI CHIEU 8 cot cua tuan 3, khong phai bang day du — no khong co
    wind_raw_mean_ms. Ban dau ham nay uu tien file do va lam 16 test do cung mot
    luc. Gio do theo COT, nen mot file thieu cot khong the bi chon im lang.

    Tra ve (bang, duong dan da dung) — in duong dan ra de biet so den tu dau.
    """
    ung_vien = [REPO_ROOT / "data" / "processed" / "flight_level.csv",
                REPORTS / "flight_level_week3.csv"]
    da_thu = []
    for p in ung_vien:
        if not p.exists():
            da_thu.append(f"  {p.relative_to(REPO_ROOT)} — khong co file")
            continue
        df = pd.read_csv(p)
        thieu = [c for c in can if c not in df.columns]
        if not thieu:
            # In ra de biet con so den tu file nao — hai file nay khac nhau
            print(f"  Bang cap chuyen bay: {p.relative_to(REPO_ROOT)} "
                  f"({len(df)} dong)")
            return df, p
        da_thu.append(f"  {p.relative_to(REPO_ROOT)} — thieu cot {thieu}")

    raise SystemExit(
        "Khong tim thay bang cap chuyen bay co du cot.\n"
        + "\n".join(da_thu)
        + "\n\nSinh lai bang day du:\n"
          "  python3 -m src.features --out data/processed/flight_level.csv")


def fit_frozen_estimator(protocol: dict | None = None):
    """
    Khop MOT LAN mo hinh D2_ridge_preflight tren ca 192 chuyen that.

    Spec doc tu configs/d2_protocol.yaml, KHONG viet cung o day: doi spec thi
    phai sua giao thuc D2 va chay lai ca san pham D2, chu khong sua file nay.

    Tra ve (pipeline da khop, ten cot dac trung, alpha da chon).
    """
    protocol = protocol or load_protocol()
    d2 = load_d2_protocol()

    cot = list(d2["features"]["preflight"])
    alpha_grid = list(d2["models"]["D2"]["alpha_grid"])
    if alpha_grid != list(RIDGE_ALPHAS):
        raise RuntimeError(
            f"Dai alpha trong d2_protocol.yaml {alpha_grid} khac src/models.py "
            f"{list(RIDGE_ALPHAS)}. Mot trong hai da bi sua — dung chay tiep.")

    muc_tieu = d2["target"]["column"]

    # duration_planned_s la dai luong SUY RA — bang day du da co san cot nay,
    # nhung neu khong co thi dung duoc cong thuc cua giao thuc D2.
    ct = d2["features"]["derived"]["duration_planned_s"]["formula"]
    if ct.replace(" ", "") != "distance_2d_m/speed_num":
        raise RuntimeError(f"Cong thuc duration_planned_s doi: {ct!r}")

    can = [c for c in cot if c != "duration_planned_s"] + [
        muc_tieu, "distance_2d_m", "speed_num"]
    df, _ = _doc_bang_chuyen_bay(can)

    if "duration_planned_s" not in df.columns:
        df["duration_planned_s"] = df["distance_2d_m"] / df["speed_num"]

    X = df[cot].to_numpy(float)
    y = df[muc_tieu].to_numpy(float)

    # Cach chon alpha doc TU d2_protocol.yaml, khong viet cung. `scheme` phai
    # dung la repeated_k_fold: src/interpretability.py dung mot KFold rieng va
    # ra alpha khac (1.0 thay vi 0.1) — xem OI-D4-4. Kiem o day de khong ai doi
    # am tham.
    cv_cfg = d2["partitioning"]["cv"]
    if cv_cfg["scheme"] != "repeated_k_fold":
        raise RuntimeError(
            f"d2_protocol.yaml khai cach chia {cv_cfg['scheme']!r}, ham nay chi "
            f"cai dat repeated_k_fold. Doi giao thuc thi phai doi ca ham nay, "
            f"va phai chay lai buoc khop — he so se doi.")
    cv = RepeatedKFold(
        n_splits=cv_cfg["n_splits"],
        n_repeats=cv_cfg["n_repeats"],
        random_state=cv_cfg["random_state"],
    )
    gs = GridSearchCV(make_d2(), {"model__alpha": alpha_grid},
                      scoring="neg_mean_absolute_error", cv=cv, n_jobs=-1)
    gs.fit(X, y)

    return gs.best_estimator_, cot, float(gs.best_params_["model__alpha"]), len(df)


def freeze_coefficients(pipe, cot: list[str], alpha: float,
                        n_flights: int) -> pd.DataFrame:
    """
    Ghi he so ra reports/d4_d2_frozen_coefficients.csv de kiem cheo duoc.

    Duy doi chieu file nay voi reports/d2_ridge_coefficients.csv da co tu tuan
    6. Khop thi dung la mo hinh da chot; lech thi co gi sai.

    Mot buoc khong kiem duoc thi khong khac gi mot con so bia — do la ly do
    buoc ghi file nay bat buoc, khong phai tuy chon.
    """
    mo_hinh = pipe.named_steps["model"]
    scaler = pipe.named_steps["scaler"]
    out = pd.DataFrame({
        "feature": cot,
        "coef_standardised": mo_hinh.coef_,
        "scaler_mean": scaler.mean_,
        "scaler_scale": scaler.scale_,
        # He so ve don vi goc, de so sanh truc tiep voi d2_ridge_coefficients.csv
        "coef_original_units": mo_hinh.coef_ / scaler.scale_,
    })
    out["alpha"] = alpha
    out["intercept"] = mo_hinh.intercept_
    out["n_flights_fitted"] = n_flights
    out["labeller_version"] = LABELLER_VERSION
    out["fit_scope"] = "ALL_192_FLIGHTS_once"

    # Ghi CACH CHON ALPHA — khong chi ghi alpha.
    # Ly do: hai cho trong repo chon alpha bang hai cach khac nhau va ra hai
    # alpha khac nhau (xem OI-D4-4). Chi ghi "alpha = 0.1" thi nguoi doc khong
    # biet no den tu dau, va khong phat hien duoc neu ai sua cach chon.
    cv = load_d2_protocol()["partitioning"]["cv"]
    out["alpha_cv_scheme"] = cv["scheme"]
    out["alpha_cv_splits"] = cv["n_splits"]
    out["alpha_cv_repeats"] = cv["n_repeats"]
    out["alpha_cv_seed"] = cv["random_state"]
    out["alpha_cv_source"] = "d2_protocol.yaml partitioning.cv"
    return out


# ---------------------------------------------------------------------------
# Anh xa dac trung kich ban -> dac trung mo hinh
# ---------------------------------------------------------------------------

def scenario_features(df: pd.DataFrame, protocol: dict,
                      cot_mo_hinh: list[str]) -> pd.DataFrame:
    """
    Dung ma tran dac trung cho mo hinh tu bang kich ban, theo anh xa da khai.

    Anh xa doc TU GIAO THUC (`reference_label.feature_mapping.map`), khong viet
    cung o day — de phep thay the gio khong the bi lam im lang trong code.
    """
    amx = protocol["reference_label"]["feature_mapping"]["map"]

    thieu = [c for c in cot_mo_hinh if c not in amx]
    if thieu:
        raise RuntimeError(
            f"Giao thuc D4 khong khai anh xa cho dac trung {thieu}. Them vao "
            f"`reference_label.feature_mapping.map`. KHONG duoc doan ten cot.")

    out = pd.DataFrame(index=df.index)
    for dac_trung in cot_mo_hinh:
        nguon = amx[dac_trung]
        if nguon.startswith("DERIVED:"):
            # Chi mot dai luong suy ra, cong thuc cua giao thuc D2
            out[dac_trung] = df["distance_2d_m"] / df["speed_commanded_ms"]
        else:
            if nguon not in df.columns:
                raise RuntimeError(
                    f"Anh xa {dac_trung} <- {nguon}, nhung bang kich ban khong "
                    f"co cot {nguon}.")
            out[dac_trung] = df[nguon]
    return out


# ---------------------------------------------------------------------------
# Hai nhan tham chieu
# ---------------------------------------------------------------------------

def e_reference_ref1(df: pd.DataFrame, protocol: dict,
                     pipe, cot_mo_hinh: list[str]) -> np.ndarray:
    """
    REF-1 — du bao cua mo hinh D2 cong khoan du phong bat dinh.

        E_ref = E_d2_prediction + abs(q05(phan du co dau))

    So hang dau la DU BAO, khong phai so do. Ten bien noi dung ban chat de
    khong ai doc nham — xem quyet dinh C16.

    Dong THIEU dac trung mo hinh thi KHONG hoi mo hinh — tra NaN, va gan_nhan()
    se cho ra UNKNOWN.

    Vi sao khong dien gia tri thay the: `wind_forecast_ms` la mot trong 6 dac
    trung cua mo hinh VA la dau vao an toan ma HR-1 can. Thieu no thi §4.6 bat
    fail closed — khong ket luan. Dien trung binh roi du bao la bien mot dong
    "khong biet" thanh mot con so trong nhu biet, dung loi ma ca san pham D3
    dung de chan.

    Ban dau ham nay goi pipe.predict() tren ca 6000 dong va no bao
    "Input X contains NaN" — 100 dong cua tang missing_input de trong cot gio.
    """
    fn = protocol["reference_label"]["frozen_numbers"]
    allowance = float(fn["uncertainty_allowance_Wh"])

    X = scenario_features(df, protocol, cot_mo_hinh).to_numpy(float)
    du_dac_trung = np.isfinite(X).all(axis=1)

    er = np.full(len(df), np.nan)
    if du_dac_trung.any():
        Xd = X[du_dac_trung]
        # Chot an toan: den day Xd phai sach tuyet doi. Neu khong, sklearn se
        # chi canh bao RuntimeWarning roi tra ra so rac — mot ket qua trong nhu
        # binh thuong. Dung han va noi ro cot nao.
        if not np.isfinite(Xd).all():
            xau = [c for i, c in enumerate(cot_mo_hinh)
                   if not np.isfinite(Xd[:, i]).all()]
            raise RuntimeError(
                f"Ma tran dac trung con gia tri khong huu han o cot {xau} sau "
                f"khi da loc. Dung chay tiep: mot du bao tu NaN/inf se trong "
                f"nhu mot con so that.")
        er[du_dac_trung] = pipe.predict(Xd) + allowance
    return er


def e_reference_ref2(df: pd.DataFrame, protocol: dict,
                     battery: str = "TB47D") -> np.ndarray:
    """
    REF-2 — mo hinh vat ly, doc lap ho mo hinh.

        E_ref2 = k * P_ideal(khoi luong) * t_ke_hoach / 3600

        k = p95( E_do_duoc / (P_ideal(khoi luong) * t_ke_hoach / 3600) )
            tren 192 chuyen that

    `k` doc tu giao thuc VA duoc tinh lai moi lan chay de doi chieu — sua tay
    mot con so thi bi bat ngay.

    BA DIEU CAN BIET:

    1. KHONG chia cho `eta`. `k` ti le THUAN voi eta con uoc luong ti le NGHICH,
       nen eta TRIET TIEU. REF-2 chi dua vao cong suat treo LY TUONG (dang dong
       tu khoi luong va dien tich dia, khong tham so khop nao) va MOT so vo
       huong do duoc.

    2. VAN doc lap voi mo hinh D2: `k` rut tu nang luong DO DUOC, khong phai tu
       dau ra hoi quy. §6/E3 doi "independent of the candidate model".

    3. Lay p95 chu khong p50 vi nhan tham chieu phai BAO THU. Doi thieu nang
       luong thi nhan goi mot kich ban la kha thi trong khi thuc te khong — dap
       an sai theo huong nguy hiem.

    HAI CON SO DA BI BO khoi cong thuc nay, dung lan:
        safety_k = 1.25   (C12) — nhom TU DAT, khong do tu gi
        eta_dev  = 0.034  (C22) — CO nguon nhung SAI VIEC: no do sai lech cua
                   he so hieu suat, khong do sai lech cua ca cong thuc. Voi no,
                   REF-2 doi nhu cau trung vi 7.56 Wh khi nang luong do duoc
                   that la 20.79 — lac quan gap 2.7 lan, nguoc han vai
                   "conservative reference" ma §6/E3 giao.
    """
    ref2 = protocol["reference_label"]["sensitivity_method"]
    fn = ref2.get("frozen_numbers") or {}
    k_dong_bang = fn.get("calibration_k")
    if k_dong_bang is None:
        raise SystemExit(
            "\nCHUA CO HE SO HIEU CHINH REF-2 — OI-D4-5 con mo.\n\n"
            "Chay:  python3 scripts/compute_ref2_calibration.py\n"
            "roi dien `calibration_k` vao configs/d4_protocol.yaml muc\n"
            "`reference_label.sensitivity_method.frozen_numbers`.")

    # Tinh lai k tu 192 chuyen that va DOI CHIEU voi so da dong bang.
    # Khong co buoc doi chieu nay thi mot con so bi sua tay se di qua im lang.
    k_tinh_lai = _he_so_hieu_chinh_ref2(int(fn["percentile"]))
    if abs(k_tinh_lai - float(k_dong_bang)) > 1e-3:
        raise RuntimeError(
            f"He so hieu chinh REF-2 lech: giao thuc ghi {k_dong_bang}, tinh "
            f"lai tu du lieu ra {k_tinh_lai:.4f}. Mot trong hai da bi sua. "
            f"Chay lai scripts/compute_ref2_calibration.py de biet so dung.")
    k = float(k_dong_bang)

    # Chu ky: takeoff_mass_g(payload_g, battery_type, profile, profiles)
    # `profiles` la muc `aircraft_profiles` cua d3_protocol.yaml.
    from src.safety_invariants import PROFILE_CMU, takeoff_mass_g

    profiles = load_d3_protocol()["aircraft_profiles"]

    # Khoi luong khung la HANG SO theo ho so, nen tinh mot lan roi cong tai —
    # thay vi goi takeoff_mass_g() 6000 lan. Van goi ham do MOT lan de lay
    # khung, de khong viet cung con so 3680 g o day.
    khung_g = takeoff_mass_g(0.0, battery, PROFILE_CMU, profiles)
    khoi_luong_g = khung_g + df["payload_g"].to_numpy(float)

    t_s = (df["distance_2d_m"] / df["speed_commanded_ms"]).to_numpy(float)

    # KHONG chia cho eta. `eta` da TRIET TIEU: k ti le thuan voi eta con uoc
    # luong ti le nghich, nen E_ref2 khong phu thuoc he so hieu suat khop duoc.
    # REF-2 gio chi dua vao cong suat treo LY TUONG (dang dong, khong tham so
    # khop) va MOT so vo huong do duoc. Xem quyet dinh C22.
    p_ideal = np.array([ideal_hover_power_W(m / 1000.0) for m in khoi_luong_g])
    return k * p_ideal * t_s / 3600.0


def _he_so_hieu_chinh_ref2(phan_vi: int) -> float:
    """
    Tinh lai he so hieu chinh REF-2 tu 192 chuyen that.

        k = p{phan_vi}( E_do_duoc / (P_ideal(khoi luong) * t_ke_hoach / 3600) )

    Dung `duration_planned_s` chu khong `duration_s`: kich ban tong hop khong co
    thoi luong do duoc, nen phai hieu chinh tren cung dai luong ma REF-2 se dung.
    """
    profiles = load_d3_protocol()["aircraft_profiles"]
    from src.safety_invariants import PROFILE_CMU, takeoff_mass_g

    df, _ = _doc_bang_chuyen_bay(
        ["energy_Wh", "payload_num", "duration_planned_s",
         "distance_2d_m", "speed_num"])

    khung_g = takeoff_mass_g(0.0, "TB47D", PROFILE_CMU, profiles)
    mass_kg = (khung_g + df["payload_num"].to_numpy(float)) / 1000.0
    t_s = df["duration_planned_s"].to_numpy(float)
    uoc_luong = np.array([ideal_hover_power_W(m) for m in mass_kg]) * t_s / 3600.0
    ti_so = df["energy_Wh"].to_numpy(float) / uoc_luong
    return float(np.percentile(ti_so, phan_vi))


# ---------------------------------------------------------------------------
# Gan nhan
# ---------------------------------------------------------------------------

def _e_available(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Nang luong kha dung tung kich ban. Tra ve (gia tri, co hop le).

    Dung src/available_energy.py cua san pham D3 — khong tinh lai cong thuc o
    day. Thieu hoac ngoai dai -> khong hop le -> nhan UNKNOWN.

    Chu y chu ky: tham so nhiet do ten `temp_c`, va truong ket qua ten
    `value_Wh` — khong phai `ambient_temp_c` va `e_available_Wh`. Da tra
    src/available_energy.py de lay dung ten, khong doan.

    `available_energy()` tra OUT_OF_RANGE khi nhiet do ra ngoai dai van hanh
    [-10, 40] (HR-2). Dai lay mau nhiet do cua kich ban dung la [-10, 40], nen
    hai dau dai co the roi vao do — va dung ra UNKNOWN, khong phai lam tron.

    HIEU NANG: `available_energy()` mac dinh `protocol=None`, va khi do no TU
    DOC d3_protocol.yaml tu dia. Goi 6000 lan thi doc va parse file YAML hon
    nghin dong 6000 lan — ban dau ham nay lam dung vay va bo chay dung nhu
    treo. Nap giao thuc MOT LAN roi truyen vao.
    """
    d3 = load_d3_protocol()
    gt, ok = [], []
    for i, row in enumerate(df.itertuples()):
        if i and i % 2000 == 0:
            print(f"    nang luong kha dung {i}/{len(df)} ...", flush=True)
        kq = available_energy(soc=nan_sang_none(row.soc),
                              soh=nan_sang_none(row.soh),
                              temp_c=nan_sang_none(row.ambient_temp_c),
                              protocol=d3)
        gt.append(kq.value_Wh if kq.status == STATUS_OK else np.nan)
        ok.append(kq.status == STATUS_OK)
    return np.asarray(gt, float), np.asarray(ok, bool)


def gan_nhan(df: pd.DataFrame, protocol: dict,
             pipe, cot_mo_hinh: list[str]) -> pd.DataFrame:
    """
    Gan ca hai nhan tham chieu cho tung kich ban.

    Kich ban thieu dau vao an toan -> UNKNOWN, khong gan nhan. §4.6 fail closed:
    khong du du kien thi khong ket luan, ke ca khi ket luan do la "khong kha
    thi". Nhan UNKNOWN cung la cach giu tang `missing_input` ra khoi confusion
    matrix — xem `in_main_comparison` cua tang do.
    """
    r = float(protocol["reference_label"]["method"][
        "reserve_policy_for_reference"]["r"])

    print("  1/3  nang luong kha dung tung kich ban ...", flush=True)
    e_av, hop_le = _e_available(df)
    out = df.copy()
    out["e_available_Wh"] = e_av
    out["inputs_valid"] = hop_le

    print("  2/3  nhan REF-1 (du bao D2 + khoan du phong) ...", flush=True)
    ref1 = e_reference_ref1(df, protocol, pipe, cot_mo_hinh)

    print("  3/3  nhan REF-2 (mo hinh vat ly, doc lap) ...", flush=True)
    ref2 = e_reference_ref2(df, protocol)

    e_ref = {"REF-1": ref1, "REF-2": ref2}

    for ma in HAI_NHAN:
        er = e_ref[ma]
        m = e_av - er                        # bien du tru, Wh
        with np.errstate(divide="ignore", invalid="ignore"):
            rr = np.where(er > 0, m / er, np.nan)

        nhan = np.full(len(df), UNKNOWN, dtype=object)
        co_so = hop_le & np.isfinite(er) & np.isfinite(m)
        nhan[co_so & (m <= 0)] = INFEASIBLE
        nhan[co_so & (m > 0) & (rr < r)] = MARGINAL
        nhan[co_so & (m > 0) & (rr >= r)] = FEASIBLE

        hau_to = ma.replace("-", "").lower()        # ref1 / ref2
        out[f"e_reference_{hau_to}_Wh"] = er
        out[f"margin_{hau_to}_Wh"] = np.where(co_so, m, np.nan)
        out[f"margin_ratio_{hau_to}"] = np.where(co_so, rr, np.nan)
        out[f"label_{hau_to}"] = nhan
        # Muc 12.1 bat dan nhan ro moi nhan la simulation-derived
        out[f"label_{hau_to}_kind"] = "simulation-derived"

    out["boundary_ref1"] = _la_vung_bien(out, protocol, "ref1")
    out["reference_model_version"] = LABELLER_VERSION
    out["reserve_policy"] = r
    return out


def _la_vung_bien(df: pd.DataFrame, protocol: dict, hau_to: str) -> np.ndarray:
    """
    Vung bien theo boundary_definition. Do rong `w` la lua chon cua nhom VA doi
    duoc ket qua, nen co do nhay S-4 bat buoc voi w = 0.025 va 0.10.
    """
    bd = protocol["boundary_definition"]
    w = float(bd["w"])
    r = float(protocol["reference_label"]["method"][
        "reserve_policy_for_reference"]["r"])
    rr = df[f"margin_ratio_{hau_to}"].to_numpy(float)
    return (np.abs(rr - r) <= w) | (np.abs(rr - 0.0) <= w)


# ---------------------------------------------------------------------------
# GEN-4b va GEN-6
# ---------------------------------------------------------------------------

def _gen4b(protocol: dict, df: pd.DataFrame) -> tuple[int, int]:
    """
    COV-3 — du kich ban vung bien. Chi kiem duoc o buoc nay, vi vung bien can
    R = M / E_required, tuc dau ra mo hinh (quyet dinh C10).

    Khong dat thi CAM noi dai kich ban de chay theo: phai nang n_scenarios va
    ghi vao change_log. Noi dai sau khi da biet R la dung dinh nghia "doi tham
    so sau khi thay ket qua".
    """
    yc = next(c for c in protocol["scenario_generator"]["mandatory_coverage"]
              if c["id"] == "COV-3")
    n = int(df["boundary_ref1"].sum())
    return 1, int(n < yc["min_count"])


def _gen6(protocol: dict) -> tuple[int, int]:
    """
    Khoan du phong khong lay tu fold kiem cuoi — §6/E3 cam thang.

    Kiem ba dieu: nguon la file phan du out-of-fold, thong ke la q05 co dau, va
    con so khop dung gia tri da dong bang.
    """
    fn = protocol["reference_label"]["frozen_numbers"]
    loi = 0
    if "oof" not in fn["computed_from"]:
        loi += 1
    if "q05" not in fn["source_statistic"]:
        loi += 1
    if abs(float(fn["uncertainty_allowance_Wh"])
           - abs(float(fn["q05_signed_Wh"]))) > 1e-6:
        loi += 1
    return 3, loi


def run_labeller_checks(protocol: dict, df: pd.DataFrame) -> pd.DataFrame:
    """
    Chay nhung phep kiem ma giao thuc khai la `verified_at: labeller`.

    Danh sach doc TU GIAO THUC va nem loi neu lech — khong viet cung. O san pham
    D3 danh sach bat bien tung viet cung o nam cho va da lech ba lan, lan nao
    cung im lang.
    """
    ham = {"GEN-4b": lambda: _gen4b(protocol, df),
           "GEN-6": lambda: _gen6(protocol)}

    khai = [t["id"] for t in protocol["generator_invariants"]["tests"]
            if t["verified_at"] == "labeller"]
    ten = {t["id"]: t["statement"]
           for t in protocol["generator_invariants"]["tests"]}

    thieu_ham = [i for i in khai if i not in ham]
    if thieu_ham:
        raise RuntimeError(
            f"Giao thuc khai {thieu_ham} o buoc labeller nhung khong co ham "
            f"kiem. Them vao src/reference_labeller.py hoac bo khoi giao thuc.")
    thieu_khai = [i for i in ham if i not in khai]
    if thieu_khai:
        raise RuntimeError(
            f"Co ham kiem cho {thieu_khai} nhung giao thuc khong khai o buoc "
            f"labeller.")

    kq = []
    for ma in khai:
        so_tr, so_vp = ham[ma]()
        kq.append({"check": ma, "noi_dung": ten[ma],
                   "so_truong_hop": so_tr, "vi_pham": so_vp,
                   "ket_qua": "DAT" if so_vp == 0 else "KHONG DAT"})
    return pd.DataFrame(kq)


# ---------------------------------------------------------------------------

def _kiem_cong_chan_muc_10(protocol: dict) -> None:
    """
    Muc 10: "Student 3 and Student 4 must jointly verify the definition of the
    reference scenario labels."

    Dinh nghia nhan phai co HAI nguoi xac nhan — nguoi lam khong duoc tu dinh
    nghia roi tu dung, vi day la cho de tao vong tron nhat trong ca de tai.
    Nen module nay TU CHOI ghi file nhan khi chua co nguoi ky.
    """
    rl = protocol["reference_label"]
    if not rl.get("approved_by"):
        raise SystemExit(
            "\nCHUA DU DIEU KIEN GAN NHAN — OI-D4-1 con mo.\n\n"
            "Muc 10 cua thay: dinh nghia nhan tham chieu phai co HAI nguoi xac "
            "nhan.\nDuy can doc muc `reference_label` cua configs/"
            "d4_protocol.yaml (REF-1,\nREF-2, ba lop nhan, rui ro vong tron), "
            "roi dien:\n\n"
            "  reference_label:\n"
            "    approved_by: \"Duy\"\n"
            "    approved_on: \"<ngay>\"\n\n"
            "Buoc khop mo hinh KHONG bi chan: chay "
            "`--fit` de lam truoc va kiem cheo he so.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true",
                    help="chi khop mo hinh va ghi he so, khong gan nhan")
    ap.add_argument("--check", action="store_true",
                    help="chi chay GEN-4b va GEN-6")
    args = ap.parse_args()

    protocol = load_protocol()
    print(f"Giao thuc D4 {protocol['meta']['version']}")

    print("\nKhop mo hinh D2_ridge_preflight — MOT LAN, tren 192 chuyen that")
    print("  (kich ban KHONG tham gia huan luyen; chung khong co cot muc tieu)")
    pipe, cot, alpha, n = fit_frozen_estimator(protocol)
    print(f"  alpha chon duoc: {alpha}   ·   {n} chuyen   ·   {len(cot)} dac trung")

    he_so = freeze_coefficients(pipe, cot, alpha, n)
    REPORTS.mkdir(exist_ok=True)
    he_so.to_csv(REPORTS / "d4_d2_frozen_coefficients.csv", index=False)
    print("  Da ghi reports/d4_d2_frozen_coefficients.csv")
    print("  -> Duy doi chieu voi reports/d2_ridge_coefficients.csv")
    print(he_so[["feature", "coef_original_units"]].to_string(
        index=False, float_format=lambda v: f"{v:+.6f}"))

    if args.fit:
        return

    _kiem_cong_chan_muc_10(protocol)

    kb = pd.read_csv(REPORTS / "d4_scenarios.csv")
    print(f"\nDoc {len(kb)} kich ban")

    nhan = gan_nhan(kb, protocol, pipe, cot)

    print("\nKiem buoc gan nhan ...")
    kiem = run_labeller_checks(protocol, nhan)
    print(kiem.to_string(index=False))

    if args.check:
        return
    if (kiem["vi_pham"] > 0).any():
        raise SystemExit(
            "\nCO PHEP KIEM KHONG DAT — KHONG ghi file. Neu GEN-4b khong dat "
            "thi NANG n_scenarios va ghi change_log; TUYET DOI khong noi dai "
            "kich ban de chay theo.")

    print("\n" + "=" * 62)
    print("PHAN BO NHAN  (simulation-derived)")
    print("=" * 62)
    bang = pd.DataFrame({
        ma: nhan[f"label_{ma.replace('-', '').lower()}"].value_counts()
        for ma in HAI_NHAN
    }).fillna(0).astype(int)
    print(bang.to_string())
    print(f"\n  vung bien (REF-1): {int(nhan.boundary_ref1.sum())}")
    print(f"  khong gan duoc   : {int((nhan.label_ref1 == UNKNOWN).sum())}"
          f"   (tang {S_MISSING})")

    kh = (nhan["label_ref1"] != nhan["label_ref2"]).sum()
    print(f"\n  HAI NHAN KHAC NHAU o {kh}/{len(nhan)} kich ban "
          f"({kh / len(nhan):.1%})")
    print("  => do la ly do §6/E3 bat chay ca hai. Bao ca hai bang canh nhau,")
    print("     khong chon mot cai cho ket qua dep.")

    nhan.to_csv(REPORTS / "d4_scenarios_labelled.csv", index=False)
    kiem.to_csv(REPORTS / "d4_labeller_check.csv", index=False)
    print(f"\nDa ghi reports/d4_scenarios_labelled.csv")
    print("Da ghi reports/d4_labeller_check.csv")
    print("\nMOI nhan la simulation-derived. KHONG phai ground truth, va khong")
    print("chung minh gi ve an toan trong thuc te (cong chan Muc 12.1).")


if __name__ == "__main__":
    main()
