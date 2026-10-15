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

    python3 -m src.evaluation_decision
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.decision_rules import (
    CONDITIONAL, FLY, INSUFFICIENT_DATA, NO_FLY, VERDICT_ORDER,
    assess, load_protocol,
)
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
        for r in R_LEVELS:
            for nhan, muc in (("fly", FLY), ("cond", CONDITIONAL)):
                v = min_soc_for(row, muc, SOH_MAIN, TEMP_MAIN, r, protocol)
                ban_ghi[f"min_soc_{nhan}_r{int(r*100)}"] = (
                    None if v is None else round(v, 4))
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
            for row in df.itertuples():
                d = assess(**_mission_kwargs(row, soc, SOH_MAIN, TEMP_MAIN),
                           reserve_factor=r, protocol=protocol)
                dem[d.verdict] += 1
                ngoai_suy += int(d.extrapolated)
            rows.append({"reserve_factor": r, "soc": soc, "n": len(df),
                         "FLY": dem[FLY], "CONDITIONAL": dem[CONDITIONAL],
                         "NO_FLY": dem[NO_FLY],
                         "INSUFFICIENT_DATA": dem[INSUFFICIENT_DATA],
                         "extrapolated": ngoai_suy})
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
# Kiem sau bat bien tren du lieu that
# ---------------------------------------------------------------------------

def run_invariants(df: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    """
    Kiem INV-1..INV-6 tren 192 cau hinh bay co that.

    Khac test don vi: test don vi kiem vai chuc truong hop do nguoi chon; o day
    la hang nghin truong hop lay tu du lieu that.
    """
    kq = []

    # INV-1 — vi pham luat cung thi khong bao gio FLY
    n = 0
    for row in df.itertuples():
        for pv in ({"wind_forecast_ms": 25.0}, {"ambient_temp_c": -40.0},
                   {"speed_commanded_ms": 30.0}):
            kw = _mission_kwargs(row, 1.0, 1.0, TEMP_MAIN)
            kw.update(pv)
            if assess(**kw, protocol=protocol).verdict != NO_FLY:
                n += 1
    kq.append(("INV-1", "luat cung phu quyet", len(df) * 3, n))

    # INV-2 — thieu dau vao thi khong bao gio FLY
    n = 0
    truong = ("soc", "soh", "ambient_temp_c", "wind_forecast_ms",
              "e_required_Wh")
    for row in df.itertuples():
        for t in truong:
            kw = _mission_kwargs(row, 1.0, 1.0, TEMP_MAIN)
            kw[t] = None
            if assess(**kw, protocol=protocol).verdict == FLY:
                n += 1
    kq.append(("INV-2", "fail closed", len(df) * len(truong), n))

    # INV-3 — don dieu theo SoC
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
    kq.append(("INV-3", "don dieu theo nang luong", len(df), n))

    # INV-4 — tat dinh
    n = 0
    for row in df.itertuples():
        kw = _mission_kwargs(row, 0.5, SOH_MAIN, TEMP_MAIN)
        a = assess(**kw, protocol=protocol)
        b = assess(**kw, protocol=protocol)
        if (a.verdict, a.reasons) != (b.verdict, b.reasons):
            n += 1
    kq.append(("INV-4", "tat dinh", len(df), n))

    # INV-5 — luu ban ghi roi tinh lai ra dung phan quyet cu
    n = 0
    for row in df.itertuples():
        rec = evaluate(f"M-{row.flight}", protocol=protocol,
                       **_mission_kwargs(row, 0.5, SOH_MAIN, TEMP_MAIN))
        if not replay_matches(rec, protocol):
            n += 1
    kq.append(("INV-5", "tinh lai tu ban ghi", len(df), n))

    # INV-6 — khong co mo hinh hoc may trong D3
    vp = scan_for_learned_models()
    kq.append(("INV-6", "D3 khong chua mo hinh hoc may", 1, len(vp)))

    # INV-7 — moi bien phap de xuat phai cai thien duoc phan quyet
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
    kq.append(("INV-7", "bien phap giam thieu co tac dung", m, n))

    return pd.DataFrame(
        [{"invariant": a, "noi_dung": b, "so_truong_hop": c, "vi_pham": d,
          "ket_qua": "DAT" if d == 0 else "KHONG DAT"} for a, b, c, d in kq])


# ---------------------------------------------------------------------------

def main() -> None:
    protocol = load_protocol()
    df = load_missions()
    print(f"Doc {len(df)} nhiem vu tu bo du lieu CMU")
    print(f"  E_required (du bao out-of-fold D2-b): "
          f"{df.e_required_Wh.min():.2f} - {df.e_required_Wh.max():.2f} Wh, "
          f"trung binh {df.e_required_Wh.mean():.2f}\n")

    print("1/4  SoC toi thieu tung chuyen ...")
    a = run_min_soc(df, protocol)
    a.to_csv(REPORTS / "d3_min_soc_per_flight.csv", index=False)

    print("2/4  Phan bo phan quyet tren luoi SoC ...")
    b = run_verdict_grid(df, protocol)
    b.to_csv(REPORTS / "d3_verdict_grid.csv", index=False)

    print("3/4  Do nhay theo SoH x nhiet do x he so du tru ...")
    c = run_scenario_sensitivity(df, protocol)
    c.to_csv(REPORTS / "d3_scenario_sensitivity.csv", index=False)

    print("4/4  Kiem sau bat bien tren du lieu that ...")
    d = run_invariants(df, protocol)
    d.to_csv(REPORTS / "d3_invariant_check.csv", index=False)

    print("\n" + "=" * 62)
    print("SAU BAT BIEN")
    print("=" * 62)
    print(d.to_string(index=False))

    print("\n" + "=" * 62)
    print(f"SoC TOI THIEU DE FLY  (SoH {SOH_MAIN}, {TEMP_MAIN:.0f} C)")
    print("=" * 62)
    for r in R_LEVELS:
        cot = a[f"min_soc_fly_r{int(r*100)}"].dropna()
        print(f"  r = {r:.2f}   trung vi {cot.median():.3f}   "
              f"p90 {cot.quantile(0.9):.3f}   max {cot.max():.3f}   "
              f"kha thi {len(cot)}/{len(a)}")

    print("\n" + "=" * 62)
    print(f"PHAN BO PHAN QUYET  (r = {R_MAIN})")
    print("=" * 62)
    sub = b[b.reserve_factor == R_MAIN]
    print(f"{'SoC':>6} {'FLY':>6} {'COND':>6} {'NO_FLY':>8} {'ngoai suy':>11}")
    print("-" * 42)
    for row in sub.itertuples():
        print(f"{row.soc:>6.2f} {row.FLY:>6} {row.CONDITIONAL:>6} "
              f"{row.NO_FLY:>8} {row.extrapolated:>11}")

    print("\nDa ghi 4 file vao reports/:")
    for ten in ("d3_min_soc_per_flight.csv", "d3_verdict_grid.csv",
                "d3_scenario_sensitivity.csv", "d3_invariant_check.csv"):
        print(f"  {ten}")


if __name__ == "__main__":
    main()
