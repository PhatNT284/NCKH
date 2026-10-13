"""
Trich dac trung cap chuyen bay (§4.2 buoc 5) va dung bang flight_level.

    python -m src.features --out data/processed/flight_level.csv
    python -m src.features --verify reports/flight_level_week3.csv

Nguyen tac §5.3: don vi phan tich la CHUYEN BAY. Moi chuyen -> dung mot dong.

Cac dac trung o day chia lam hai nhom va PHAI giu rieng:
  - TRUOC CHUYEN BAY: payload, speed ra lenh, altitude, cu ly tuyen, gio du bao.
    Chi nhom nay duoc vao mo hinh du bao (xem configs/d2_protocol.yaml).
  - HAU NGHIEM: duration do duoc, toc do thuc, climb/descent, cong suat.
    Giu lai de phan tich phan du, KHONG dua vao mo hinh chinh.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_ingestion import (
    REPO_ROOT, check_flight_quality, iter_flights, load_config, load_parameters,
)
from src.energy_reconstruction import reconstruct_flight_energy

VALID_ALTITUDES = {25.0, 50.0, 75.0, 100.0}
VALID_PAYLOADS = {0.0, 250.0, 500.0}


# ---------------------------------------------------------------------------
# Dac trung hinh hoc duong bay
# ---------------------------------------------------------------------------

def trajectory_features(df: pd.DataFrame) -> dict:
    """
    Cu ly 2D/3D, do cao trung binh, tong leo va tong ha.

    Cu ly 2D cong don tren mat phang ngang; cu ly 3D co them thanh phan dung.
    `climb_m` va `descent_m` la tong gia tri duong va am cua bien thien do cao.
    """
    out = {
        "distance_2d_m": np.nan, "distance_3d_m": np.nan,
        "alt_mean_m": np.nan, "climb_m": np.nan, "descent_m": np.nan,
    }
    if not {"position_x", "position_y"}.issubset(df.columns):
        return out

    d = df.sort_values("time") if "time" in df.columns else df
    dx = d["position_x"].diff()
    dy = d["position_y"].diff()
    step_2d = np.sqrt(dx**2 + dy**2)
    out["distance_2d_m"] = float(step_2d.sum(skipna=True))

    if "position_z" in d.columns:
        dz = d["position_z"].diff()
        out["distance_3d_m"] = float(np.sqrt(dx**2 + dy**2 + dz**2).sum(skipna=True))
        out["alt_mean_m"] = float(d["position_z"].mean())
        out["climb_m"] = float(dz[dz > 0].sum())
        out["descent_m"] = float(-dz[dz < 0].sum())
    else:
        out["distance_3d_m"] = out["distance_2d_m"]

    return out


def wind_features(df: pd.DataFrame) -> dict:
    """
    Gio THO, trung binh va do lech chuan trong chuyen bay.

    CHU Y: day la gio chua hieu chinh. configs/d2_protocol.yaml chot dung cot
    tho lam dac trung chinh, vi d2_report.md da chung minh cot hieu chinh
    tuong quan voi toc do UAV manh hon ca gio tho — dau hieu no dang do toc do
    bay chu khong do gio.
    """
    out = {"wind_raw_mean_ms": np.nan, "wind_raw_std_ms": np.nan,
           "wind_dir_mean_deg": np.nan}
    if "wind_speed" in df.columns:
        w = df["wind_speed"].dropna()
        if len(w):
            out["wind_raw_mean_ms"] = float(w.mean())
            out["wind_raw_std_ms"] = float(w.std())
    if "wind_angle" in df.columns:
        a = df["wind_angle"].dropna()
        if len(a):
            # Trung binh huong phai lam tren vong tron, khong lay trung binh so hoc
            rad = np.deg2rad(a.to_numpy(dtype=float))
            out["wind_dir_mean_deg"] = float(
                np.rad2deg(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360
            )
    return out


# ---------------------------------------------------------------------------
# Loc theo quality_report.md
# ---------------------------------------------------------------------------

def apply_exclusions(params: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Ap quy tac loai tru, tra ve (giu_lai, nhat_ky_loai_tru).

    Bon quy tac theo quality_report.md: khong phai bay hanh trinh, do cao
    ngoai luoi, tai ngoai luoi, cam bien dong hong. Quy tac cuoi can du lieu
    bay nen xu ly o buoc sau.
    """
    df = params.copy()
    log = []

    route = df["route"].astype(str)
    mask_non_cruise = route.str.upper().str.startswith(("A", "H"))
    for _, r in df[mask_non_cruise].iterrows():
        log.append({"flight": r["flight"], "reason":
                    "khong phai bay hanh trinh (chay khong tai A* hoac bay treo H)"})
    df = df[~mask_non_cruise]

    alt = pd.to_numeric(df["altitude"], errors="coerce")
    mask_alt = ~alt.isin(VALID_ALTITUDES)
    for _, r in df[mask_alt].iterrows():
        log.append({"flight": r["flight"], "reason":
                    f"do cao khong phai gia tri chuan 25/50/75/100 m ({r['altitude']})"})
    df = df[~mask_alt]

    pay = pd.to_numeric(df["payload"], errors="coerce")
    mask_pay = ~pay.isin(VALID_PAYLOADS)
    for _, r in df[mask_pay].iterrows():
        log.append({"flight": r["flight"], "reason":
                    f"tai trong ngoai thiet ke 0/250/500 g ({r['payload']})"})
    df = df[~mask_pay]

    return df, pd.DataFrame(log)


# ---------------------------------------------------------------------------
# Dung bang flight_level
# ---------------------------------------------------------------------------

def build_flight_level(cfg: dict | None = None, verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Duyet flights.csv, gop voi parameters.csv, tra ve (flight_level, exclusion_log).
    """
    cfg = cfg or load_config()
    params = load_parameters(cfg)
    kept, log = apply_exclusions(params, cfg)
    keep_ids = set(kept["flight"])

    if verbose:
        print(f"parameters.csv: {len(params)} dong")
        print(f"Sau khi loc theo tham so: giu {len(kept)}, loai {len(log)}")
        print("Dang doc flights.csv...")

    rows, extra_log = [], []
    current_threshold = cfg["exclusions"]["broken_current_sensor"]["threshold_a"]

    for fid, fdf in iter_flights(cfg):
        if fid not in keep_ids:
            continue

        issues = check_flight_quality(fdf)
        if "current_sensor_suspect" in issues:
            extra_log.append({
                "flight": fid,
                "reason": f"cam bien dong hong (dong trung vi "
                          f"{issues['current_sensor_suspect']:.2f} A "
                          f"< {current_threshold} A)",
            })
            continue

        rec = {"flight": fid}
        rec.update(reconstruct_flight_energy(fdf))
        rec.update(trajectory_features(fdf))
        rec.update(wind_features(fdf))
        rec["quality_issues"] = "; ".join(issues) if issues else ""
        rows.append(rec)

    flight_level = pd.DataFrame(rows)

    # Gop tham so nhiem vu
    pcols = ["flight", "payload", "speed", "altitude", "route", "date", "local_time"]
    pcols = [c for c in pcols if c in kept.columns]
    flight_level = flight_level.merge(kept[pcols], on="flight", how="left")
    flight_level = flight_level.rename(columns={
        "payload": "payload_num", "speed": "speed_num", "altitude": "altitude_num",
    })
    for c in ("payload_num", "speed_num", "altitude_num"):
        flight_level[c] = pd.to_numeric(flight_level[c], errors="coerce")

    # Dac trung dan xuat
    flight_level["speed_realised_ms"] = (
        flight_level["distance_2d_m"] / flight_level["duration_s"]
    )
    flight_level["energy_per_metre_J"] = (
        flight_level["energy_Wh"] * 3600.0 / flight_level["distance_2d_m"]
    )
    # Thoi luong KE HOACH — suy ra, dung cho D2-b (§5.5)
    flight_level["duration_planned_s"] = (
        flight_level["distance_2d_m"] / flight_level["speed_num"]
    )

    exclusion_log = pd.concat([log, pd.DataFrame(extra_log)], ignore_index=True)
    flight_level = flight_level.sort_values("flight").reset_index(drop=True)

    if verbose:
        print(f"Giu lai cuoi cung: {len(flight_level)} chuyen")
        print(f"Loai tong cong: {len(exclusion_log)} chuyen")
        expected = cfg["exclusions"]["expected_kept"]
        if len(flight_level) != expected:
            print(f"  CANH BAO: ky vong {expected} chuyen, thuc te {len(flight_level)}")

    return flight_level, exclusion_log


def verify_against(flight_level: pd.DataFrame, reference_path: Path | str,
                   tolerance: float = 1e-6) -> bool:
    """
    Doi chieu bang vua dung voi bang tham chieu da co tu tuan 3.

    Day la phep kiem tai lap: cung mot du lieu goc, cung mot quy tac, phai ra
    cung mot so. Lech qua nguong -> in ra chuyen bay nao lech.
    """
    ref = pd.read_csv(reference_path)
    print(f"Tham chieu : {len(ref)} chuyen  ({reference_path})")
    print(f"Tai lap    : {len(flight_level)} chuyen")

    ids_ref, ids_new = set(ref["flight"]), set(flight_level["flight"])
    ok = True

    if ids_ref != ids_new:
        ok = False
        if ids_ref - ids_new:
            print(f"  THIEU so voi tham chieu: {sorted(ids_ref - ids_new)}")
        if ids_new - ids_ref:
            print(f"  THUA so voi tham chieu: {sorted(ids_new - ids_ref)}")

    common = sorted(ids_ref & ids_new)
    a = ref[ref["flight"].isin(common)].sort_values("flight").reset_index(drop=True)
    b = flight_level[flight_level["flight"].isin(common)].sort_values("flight").reset_index(drop=True)

    print()
    print(f"{'cot':<22} {'lech lon nhat':>16}  ket qua")
    print("-" * 56)
    for col in ["energy_Wh", "distance_2d_m", "distance_3d_m", "duration_s",
                "climb_m", "descent_m", "P_mean_W", "P_max_W"]:
        if col in a.columns and col in b.columns:
            diff = (a[col] - b[col]).abs().max()
            passed = diff < tolerance
            ok &= bool(passed)
            print(f"{col:<22} {diff:>16.3e}  {'OK' if passed else 'LECH'}")

    print()
    print("KET QUA: " + ("TAI LAP DUNG" if ok else "CO SAI LECH — xem lai"))
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description="Dung bang dac trung cap chuyen bay")
    ap.add_argument("--out", default="data/processed/flight_level.csv")
    ap.add_argument("--exclusion-log", default="reports/exclusion_log.csv")
    ap.add_argument("--verify", metavar="REFERENCE_CSV",
                    help="doi chieu voi bang da co tu tuan 3 thay vi ghi file moi")
    args = ap.parse_args()

    cfg = load_config()
    flight_level, log = build_flight_level(cfg)

    if args.verify:
        print()
        ok = verify_against(flight_level, args.verify)
        raise SystemExit(0 if ok else 1)

    out = Path(args.out)
    out = out if out.is_absolute() else REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    flight_level.to_csv(out, index=False)
    print(f"\nDa ghi {out}  ({len(flight_level)} chuyen)")

    logp = Path(args.exclusion_log)
    logp = logp if logp.is_absolute() else REPO_ROOT / logp
    logp.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(logp, index=False)
    print(f"Da ghi {logp}  ({len(log)} chuyen bi loai)")


if __name__ == "__main__":
    main()
