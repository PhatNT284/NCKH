"""
Chay bo may quyet dinh tren 192 chuyen bay — buoc cuoi cua san pham D3.

MUC DICH — doc ky truoc khi diem ket qua

    Day KHONG phai phep cham diem D3. Bo du lieu CMU khong co nhan "chuyen nay
    dang le co nen bay khong", nen khong co dap an de so. §4.7 ghi ro viec danh
    gia hanh vi quyet dinh thuoc san pham D4, tren tap kich ban tong hop.

    Chay o day de lam ba viec:
        1. MINH HOA — he thong xu su the nao tren cau hinh bay co that
        2. KIEM BAT BIEN tren du lieu that, khong chi tren vi du tu nghi ra
        3. Sinh BANG va SO cho bai bao

NGUON SO LIEU

    E_required : du bao OUT-OF-FOLD cua mo hinh D2-b, dung lai tu
                 reports/d2_oof_residuals.csv + reports/flight_level_week3.csv
                 (pred = energy_Wh do duoc + phan du). Out-of-fold nghia la moi
                 du bao den tu mot mo hinh CHUA TUNG THAY chuyen do — khong ro ri.

    Gio       : wind_mean_ms (gio THO do duoc) dung thay cho gio DU BAO.
                PHAI KHAI BAO trong bai: day la xap xi, vi bo du lieu khong co
                du bao gio. Anh huong nho vi toan bo chien dich bay trong dai
                2.81-6.67 m/s, chua bao gio cham gioi han 10 m/s cua HR-1.

    SoC, SoH, nhiet do : THAM SO KICH BAN (§4.3). Bo du lieu khong co. Dung dai
                gia tri khai bao ro, va moi ket qua lien quan trinh bay nhu
                PHAN TICH DO NHAY, khong phai du bao.

    Ho so may bay : CMU_instrumented (quyet dinh B6), vi day la may bay that
                trong bo du lieu, da mang 1249 g thiet bi do.

DANH SACH BAT BIEN LAY TU GIAO THUC, KHONG VIET CUNG

    Tu ban 1.4.0, `run_invariants()` doc `invariants.tests` tu
    configs/d3_protocol.yaml roi tra cuu ham kiem tuong ung trong `KIEM_BAT_BIEN`.
    Neu giao thuc khai mot bat bien ma khong co ham kiem -> NEM LOI NGAY, khong
    im lang bo qua.

    Vi sao doi: truoc day danh sach viet cung trong ham. Khi them INV-7 roi INV-8,
    giao thuc khai bat bien moi nhung CSV van giu so dong cu — giao thuc noi mot
    dang, bang chung noi mot dang. Loi im lang, va da xay ra HAI LAN.

    python3 -m src.evaluation_decision
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.available_energy import kappa
from src.decision_rules import (
    CONDITIONAL, FLY, INSUFFICIENT_DATA, NO_FLY, VERDICT_ORDER,
    assess, load_protocol,
)
from src.physics_m100 import min_soc_for_landing
from src.safety_invariants import PROFILE_CMU
from src.mitigations import propose
from src.workflow_state import evaluate, replay_matches, scan_for_learned_models

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"

ESTIMATOR = "D2_ridge_preflight"

# Dai kich ban — KHAI BAO, khong do duoc tu bo du lieu (§4.3)
SOH_LEVELS = (1.00, 0.90, 0.80)        # pin moi / da dung / gan cuoi doi
TEMP_LEVELS = (5.0, 15.0, 25.0)        # duoi / trong / tren dai hieu chinh Kim
R_LEVELS = (0.10, 0.20, 0.30)          # §5.7, P§4.5 bat buoc bao ca ba

SOH_MAIN, TEMP_MAIN, R_MAIN = 1.00, 15.0, 0.20

# Khung may bay o ho so CMU_instrumented — dung cho nguong ha canh (PH-1)
CMU_AIRFRAME_G = 3680


# ---------------------------------------------------------------------------

def _uoc_luong_ridge(kw: dict) -> float:
    """
    Xap xi tuyen tinh tu he so Ridge o reports/d2_ridge_coefficients.csv, dung
    cho bien phap nhom B khi kiem INV-7.

    KHONG phai mo hinh D2 that — D3 khong duoc import sklearn (INV-6). Chay
    that thi truyen mo hinh da chot vao. O day chi can mot ham DON DIEU dung
    chieu de kiem bat bien.
    """
    return max(0.1, kw["e_required_Wh"]
               + 0.008121 * (kw["payload_g"] - 250)
               + 0.235256 * (kw["speed_commanded_ms"] - 8)
               - 0.001305 * (kw["distance_2d_m"] - 472))


def load_missions() -> pd.DataFrame:
    """
    Dung lai 192 nhiem vu tu bo du lieu, kem du bao out-of-fold cua D2-b.

    pred = energy_Wh (do duoc) + phan du out-of-fold
    """
    fl = pd.read_csv(REPORTS / "flight_level_week3.csv")
    oof = pd.read_csv(REPORTS / "d2_oof_residuals.csv")[["flight", ESTIMATOR]]
    df = fl.merge(oof, on="flight", how="inner")
    df["e_required_Wh"] = df["energy_Wh"] + df[ESTIMATOR]
    df = df.rename(columns={
        "payload_num": "payload_g",
        "speed_num": "speed_commanded_ms",
        "altitude_num": "altitude_m",
        "wind_mean_ms": "wind_forecast_ms",
    })
    return df[["flight", "route", "payload_g", "speed_commanded_ms",
               "altitude_m", "distance_2d_m", "wind_forecast_ms",
               "energy_Wh", "e_required_Wh"]].copy()


def _mission_kwargs(row, soc, soh, temp) -> dict:
    return dict(payload_g=float(row.payload_g),
                speed_commanded_ms=float(row.speed_commanded_ms),
                altitude_m=float(row.altitude_m),
                distance_2d_m=float(row.distance_2d_m),
                wind_forecast_ms=float(row.wind_forecast_ms),
                ambient_temp_c=float(temp),
                soc=float(soc), soh=float(soh),
                e_required_Wh=float(row.e_required_Wh),
                profile=PROFILE_CMU)


# ---------------------------------------------------------------------------
# SoC toi thieu — con so co nghia voi nguoi van hanh
# ---------------------------------------------------------------------------

def min_soc_for(row, target: str, soh: float, temp: float, r: float,
                protocol: dict, eps: float = 1e-4) -> float | None:
    """
    SoC thap nhat cho ra phan quyet >= `target`.

    Dung chia doi thay vi quet luoi, hop le vi INV-3 bao dam phan quyet DON DIEU
    theo SoC — khong don dieu thi chia doi vo nghia, nen bat bien do la dieu kien
    tien quyet chu khong phai chi tiet cai dat.
    """
    muc = VERDICT_ORDER.index(target)

    def dat(soc: float) -> bool:
        v = assess(**_mission_kwargs(row, soc, soh, temp),
                   reserve_factor=r, protocol=protocol).verdict
        return VERDICT_ORDER.index(v) >= muc

    if not dat(1.0):
        return None                          # pin day cung khong dat
    if dat(eps):
        return eps

    lo, hi = eps, 1.0
    while hi - lo > eps:
        giua = (lo + hi) / 2
        if dat(giua):
            hi = giua
        else:
            lo = giua
    return hi


def run_min_soc(df: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    """SoC toi thieu cho FLY va cho CONDITIONAL, o ca ba muc he so du tru."""
    rows = []
    for row in df.itertuples():
        ban_ghi = {"flight": row.flight, "route": row.route,
                   "payload_g": row.payload_g,
                   "speed_commanded_ms": row.speed_commanded_ms,
                   "altitude_m": row.altitude_m,
                   "distance_2d_m": round(row.distance_2d_m, 1),
                   "e_required_Wh": round(row.e_required_Wh, 3)}
        # Nguong PH-1 cho chuyen nay — de doi chieu voi nguong do luat du tru.
        # PHAI truyen kappa THAT: mac dinh kappa = 1.0 cho nguong LAC QUAN, va
        # o TEMP_MAIN = 15 C thi kappa = 0.9954 nen nguong that cao hon ~0.5 %.
        k_main, _ = kappa(TEMP_MAIN)
        nguong_ha = min_soc_for_landing(row.altitude_m,
                                        CMU_AIRFRAME_G + row.payload_g,
                                        soh=SOH_MAIN, kappa=k_main)
        ban_ghi["min_soc_landing_ph1"] = round(nguong_ha, 4)
        for r in R_LEVELS:
            for nhan, muc in (("fly", FLY), ("cond", CONDITIONAL)):
                v = min_soc_for(row, muc, SOH_MAIN, TEMP_MAIN, r, protocol)
                ban_ghi[f"min_soc_{nhan}_r{int(r*100)}"] = (
                    None if v is None else round(v, 4))
        # Luat nao rang buoc hon o muc r chinh
        v_fly = ban_ghi[f"min_soc_fly_r{int(R_MAIN*100)}"]
        ban_ghi["ph1_rang_buoc_hon"] = (
            None if v_fly is None else bool(nguong_ha > v_fly))
        rows.append(ban_ghi)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Phan bo phan quyet tren luoi SoC
# ---------------------------------------------------------------------------

def run_verdict_grid(df: pd.DataFrame, protocol: dict,
                     soc_levels=tuple(round(x / 20, 2) for x in range(2, 21))
                     ) -> pd.DataFrame:
    """Dem phan quyet tren luoi 192 chuyen x SoC x he so du tru."""
    rows = []
    for r in R_LEVELS:
        for soc in soc_levels:
            dem = {FLY: 0, CONDITIONAL: 0, NO_FLY: 0, INSUFFICIENT_DATA: 0}
            ngoai_suy = 0
            ph1_chan = 0
            for row in df.itertuples():
                d = assess(**_mission_kwargs(row, soc, SOH_MAIN, TEMP_MAIN),
                           reserve_factor=r, protocol=protocol)
                dem[d.verdict] += 1
                ngoai_suy += int(d.extrapolated)
                ph1_chan += int(any(
                    c.rule_id == "PH-1" and c.status == "VIOLATED"
                    for c in d.hard_rule_report.checks))
            rows.append({"reserve_factor": r, "soc": soc, "n": len(df),
                         "FLY": dem[FLY], "CONDITIONAL": dem[CONDITIONAL],
                         "NO_FLY": dem[NO_FLY],
                         "INSUFFICIENT_DATA": dem[INSUFFICIENT_DATA],
                         "extrapolated": ngoai_suy,
                         "ph1_violated": ph1_chan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Do nhay theo kich ban
# ---------------------------------------------------------------------------

def run_scenario_sensitivity(df: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    """
    SoC toi thieu de FLY, theo SoH x nhiet do x he so du tru.

    SoH va nhiet do la THAM SO KICH BAN (§4.3) — bang nay la PHAN TICH DO NHAY,
    khong phai hieu ung hoc duoc tu du lieu.
    """
    rows = []
    for soh in SOH_LEVELS:
        for temp in TEMP_LEVELS:
            for r in R_LEVELS:
                vs = [min_soc_for(row, FLY, soh, temp, r, protocol)
                      for row in df.itertuples()]
                hop_le = [v for v in vs if v is not None]
                rows.append({
                    "soh": soh, "ambient_temp_c": temp, "reserve_factor": r,
                    "n_kha_thi": len(hop_le), "n": len(vs),
                    "min_soc_trung_vi": round(float(np.median(hop_le)), 4)
                    if hop_le else None,
                    "min_soc_p90": round(float(np.percentile(hop_le, 90)), 4)
                    if hop_le else None,
                    "min_soc_max": round(max(hop_le), 4) if hop_le else None,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Kiem bat bien tren du lieu that
# ---------------------------------------------------------------------------
# Moi ham duoi day tra ve (so_truong_hop, so_vi_pham).
# Danh sach bat bien lay tu GIAO THUC, khong viet cung — xem run_invariants().

def _inv1(df, protocol):
    """Vi pham luat cung -> khong bao gio FLY."""
    n = 0
    pv_list = ({"wind_forecast_ms": 25.0}, {"ambient_temp_c": -40.0},
               {"speed_commanded_ms": 30.0})
    for row in df.itertuples():
        for pv in pv_list:
            kw = _mission_kwargs(row, 1.0, 1.0, TEMP_MAIN)
            kw.update(pv)
            if assess(**kw, protocol=protocol).verdict != NO_FLY:
                n += 1
    return len(df) * len(pv_list), n


def _inv2(df, protocol):
    """Thieu dau vao -> khong bao gio FLY."""
    n = 0
    truong = ("soc", "soh", "ambient_temp_c", "wind_forecast_ms",
              "e_required_Wh")
    for row in df.itertuples():
        for t in truong:
            kw = _mission_kwargs(row, 1.0, 1.0, TEMP_MAIN)
            kw[t] = None
            if assess(**kw, protocol=protocol).verdict == FLY:
                n += 1
    return len(df) * len(truong), n


def _inv3(df, protocol):
    """Don dieu theo SoC — pin nhieu hon thi phan quyet khong xau di."""
    n = 0
    luoi = [x / 50 for x in range(1, 51)]
    for row in df.itertuples():
        truoc = -1
        for soc in luoi:
            muc = VERDICT_ORDER.index(
                assess(**_mission_kwargs(row, soc, SOH_MAIN, TEMP_MAIN),
                       protocol=protocol).verdict)
            if muc < truoc:
                n += 1
                break
            truoc = muc
    return len(df), n


def _inv4(df, protocol):
    """Tat dinh — cung dau vao, cung dau ra."""
    n = 0
    for row in df.itertuples():
        kw = _mission_kwargs(row, 0.5, SOH_MAIN, TEMP_MAIN)
        a = assess(**kw, protocol=protocol)
        b = assess(**kw, protocol=protocol)
        if (a.verdict, a.reasons) != (b.verdict, b.reasons):
            n += 1
    return len(df), n


def _inv5(df, protocol):
    """Luu ban ghi roi tinh lai -> ra dung phan quyet cu."""
    n = 0
    for row in df.itertuples():
        rec = evaluate(f"M-{row.flight}", protocol=protocol,
                       **_mission_kwargs(row, 0.5, SOH_MAIN, TEMP_MAIN))
        if not replay_matches(rec, protocol):
            n += 1
    return len(df), n


def _inv6(df, protocol):
    """Khong co mo hinh hoc may trong D3 — quet ma nguon."""
    return 1, len(scan_for_learned_models())


def _inv7(df, protocol):
    """Moi bien phap de xuat phai cai thien duoc phan quyet."""
    n = m = 0
    for row in df.itertuples():
        # Lay muc SoC sat nguong de co nhieu CONDITIONAL ma kiem
        kw = _mission_kwargs(row, 0.27, SOH_MAIN, TEMP_MAIN)
        kw.pop("profile", None)
        goc = assess(**kw, protocol=protocol)
        dx, _ = propose(kw, estimator=_uoc_luong_ridge, protocol=protocol)
        m += len(dx)
        for p_ in dx:
            if (VERDICT_ORDER.index(p_.after)
                    <= VERDICT_ORDER.index(goc.verdict)):
                n += 1
    return m, n


def _inv8(df, protocol):
    """
    Khong du pin ha canh -> khong bao gio FLY (luat PH-1, P§4.6).

    Kiem hai chieu:
      (a) SoC duoi nguong ha canh -> phai NO_FLY, du bien du tru co lon
      (b) ap bien phap giam thieu -> VAN NO_FLY, vi PH-1 la VETO

    Chieu (b) quan trong khong kem: khong co no thi M1 (sac them pin) thanh
    cua sau de lach PH-1 — dung loi ma mitigations.py da co test chan cho HR-1.
    """
    n = m = 0
    he_so = (0.3, 0.6, 0.9)
    for row in df.itertuples():
        nguong = min_soc_for_landing(row.altitude_m,
                                     CMU_AIRFRAME_G + row.payload_g)
        for hs in he_so:
            soc = nguong * hs
            if soc <= 0:
                continue
            m += 1
            if assess(**_mission_kwargs(row, soc, SOH_MAIN, TEMP_MAIN),
                      protocol=protocol).verdict == FLY:
                n += 1
        # (b) bien phap khong lat duoc VETO
        m += 1
        d = assess(**_mission_kwargs(row, nguong * 0.5, SOH_MAIN, TEMP_MAIN),
                   mitigation_applied="M1", protocol=protocol)
        if d.verdict != NO_FLY or d.actionable:
            n += 1
    return m, n


# Ban do bat bien -> ham kiem. Them bat bien moi thi them CA HAI cho:
# muc `invariants.tests` trong giao thuc, va mot dong o day.
KIEM_BAT_BIEN = {
    "INV-1": _inv1, "INV-2": _inv2, "INV-3": _inv3, "INV-4": _inv4,
    "INV-5": _inv5, "INV-6": _inv6, "INV-7": _inv7, "INV-8": _inv8,
}


def run_invariants(df: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    """
    Kiem TOAN BO bat bien khai trong giao thuc, tren 192 cau hinh bay co that.

    Danh sach lay tu `invariants.tests` cua configs/d3_protocol.yaml. Neu giao
    thuc khai mot bat bien ma khong co ham kiem -> NEM LOI, khong im lang bo qua.
    Day la cho da sai HAI LAN truoc day: them INV-7 roi INV-8 vao giao thuc
    nhung CSV van giu so dong cu.

    Khac test don vi: test don vi kiem vai chuc truong hop do nguoi chon; o day
    la hang nghin truong hop lay tu du lieu that.
    """
    khai = [t["id"] for t in protocol["invariants"]["tests"]]
    ten = {t["id"]: t["name"] for t in protocol["invariants"]["tests"]}

    thieu_ham = [i for i in khai if i not in KIEM_BAT_BIEN]
    if thieu_ham:
        raise RuntimeError(
            f"Giao thuc khai bat bien {thieu_ham} nhung khong co ham kiem "
            f"trong KIEM_BAT_BIEN. Them ham vao src/evaluation_decision.py, "
            f"hoac bo khoi giao thuc. KHONG duoc de giao thuc noi mot dang va "
            f"bang chung noi mot dang.")

    thieu_khai = [i for i in KIEM_BAT_BIEN if i not in khai]
    if thieu_khai:
        raise RuntimeError(
            f"Co ham kiem cho {thieu_khai} nhung giao thuc khong khai. Them vao "
            f"muc `invariants.tests` cua configs/d3_protocol.yaml.")

    kq = []
    for i, ma in enumerate(khai, 1):
        print(f"      {ma} ({i}/{len(khai)}) ...", flush=True)
        so_tr, so_vp = KIEM_BAT_BIEN[ma](df, protocol)
        kq.append((ma, ten[ma], so_tr, so_vp))

    return pd.DataFrame(
        [{"invariant": a, "noi_dung": b, "so_truong_hop": c, "vi_pham": d,
          "ket_qua": "DAT" if d == 0 else "KHONG DAT"} for a, b, c, d in kq])


# ---------------------------------------------------------------------------

def main() -> None:
    protocol = load_protocol()
    df = load_missions()
    n_bat_bien = len(protocol["invariants"]["tests"])

    print(f"Doc {len(df)} nhiem vu tu bo du lieu CMU")
    print(f"  E_required (du bao out-of-fold D2-b): "
          f"{df.e_required_Wh.min():.2f} - {df.e_required_Wh.max():.2f} Wh, "
          f"trung binh {df.e_required_Wh.mean():.2f}")
    print(f"  Giao thuc {protocol['meta']['version']}, "
          f"{n_bat_bien} bat bien khai bao\n")

    print("1/4  SoC toi thieu tung chuyen ...")
    a = run_min_soc(df, protocol)
    a.to_csv(REPORTS / "d3_min_soc_per_flight.csv", index=False)

    print("2/4  Phan bo phan quyet tren luoi SoC ...")
    b = run_verdict_grid(df, protocol)
    b.to_csv(REPORTS / "d3_verdict_grid.csv", index=False)

    print("3/4  Do nhay theo SoH x nhiet do x he so du tru ...")
    c = run_scenario_sensitivity(df, protocol)
    c.to_csv(REPORTS / "d3_scenario_sensitivity.csv", index=False)

    print(f"4/4  Kiem {n_bat_bien} bat bien tren du lieu that ...")
    d = run_invariants(df, protocol)
    d.to_csv(REPORTS / "d3_invariant_check.csv", index=False)

    print("\n" + "=" * 62)
    print(f"{n_bat_bien} BAT BIEN")
    print("=" * 62)
    print(d.to_string(index=False))
    print(f"\n  Tong {d.so_truong_hop.sum()} truong hop, "
          f"{d.vi_pham.sum()} vi pham")

    print("\n" + "=" * 62)
    print(f"SoC TOI THIEU DE FLY  (SoH {SOH_MAIN}, {TEMP_MAIN:.0f} C)")
    print("=" * 62)
    for r in R_LEVELS:
        cot = a[f"min_soc_fly_r{int(r*100)}"].dropna()
        print(f"  r = {r:.2f}   trung vi {cot.median():.3f}   "
              f"p90 {cot.quantile(0.9):.3f}   max {cot.max():.3f}   "
              f"kha thi {len(cot)}/{len(a)}")

    print("\n" + "=" * 62)
    print("LUAT PH-1 CO RANG BUOC HON LUAT DU TRU KHONG?")
    print("=" * 62)
    nguong = a["min_soc_landing_ph1"]
    print(f"  Nguong PH-1 (san ha canh): "
          f"{nguong.min():.1%} - {nguong.max():.1%}, "
          f"trung vi {nguong.median():.1%}")
    cot = a[f"min_soc_fly_r{int(R_MAIN*100)}"].dropna()
    print(f"  Nguong luat du tru (r={R_MAIN}): "
          f"{cot.min():.1%} - {cot.max():.1%}, trung vi {cot.median():.1%}")
    rb = a["ph1_rang_buoc_hon"].sum()
    print(f"\n  So chuyen ma PH-1 rang buoc HON luat du tru: {rb}/{len(a)}")
    if rb == 0:
        print("  => Tren bo du lieu nay luat du tru luon nghiem hon, nen PH-1")
        print("     KHONG doi phan quyet nao. Dung nhu du doan o quyet dinh B10.")
        print("     PH-1 van can thiet cho san pham D4: bo sinh kich ban quet")
        print("     doc lap cu ly va do cao, nen se sinh ra chuyen NGAN ma bay")
        print("     CAO — do la cho luat du tru long hon PH-1.")
    else:
        print(f"  => PH-1 rang buoc hon o {rb} chuyen. Phai neu ro trong bao cao.")

    print("\n" + "=" * 62)
    print(f"PHAN BO PHAN QUYET  (r = {R_MAIN})")
    print("=" * 62)
    sub = b[b.reserve_factor == R_MAIN]
    print(f"{'SoC':>6} {'FLY':>6} {'COND':>6} {'NO_FLY':>8} "
          f"{'ngoai suy':>11} {'PH-1 chan':>11}")
    print("-" * 56)
    for row in sub.itertuples():
        print(f"{row.soc:>6.2f} {row.FLY:>6} {row.CONDITIONAL:>6} "
              f"{row.NO_FLY:>8} {row.extrapolated:>11} {row.ph1_violated:>11}")

    print("\nDa ghi 4 file vao reports/:")
    for ten_ in ("d3_min_soc_per_flight.csv", "d3_verdict_grid.csv",
                 "d3_scenario_sensitivity.csv", "d3_invariant_check.csv"):
        print(f"  {ten_}")


if __name__ == "__main__":
    main()