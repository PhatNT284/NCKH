"""
Do dinh nghia `distance_2d_m` cua bang tuan 3 — vong 3.

Vong 1 ket luan sai rang position_x/y dung yen. Thuc te chung o DON VI DO
(kinh do -79.78, vi do 40.45 — Pittsburgh), bien do ~0.0015 do nen tong hieu
so theo do chi khoang 0.002 va bi in thanh 0.0.

Vong nay doi do sang met roi moi cong don, thu cac he so quy doi khac nhau.

Chay:
    python3 scripts/diagnose_distance.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.data_ingestion import load_config, iter_flights  # noqa: E402

PROBE_FLIGHTS = [1, 2, 10, 50, 272]
R_EARTH = 6_371_000.0


def _cumsum(dx, dy):
    return float(np.nansum(np.hypot(dx, dy)))


def candidates(d: pd.DataFrame) -> dict:
    """position_x = kinh do, position_y = vi do, deu o don vi DO."""
    d = d.sort_values("time")
    lon = d["position_x"].to_numpy(float)
    lat = d["position_y"].to_numpy(float)
    z = d["position_z"].to_numpy(float)

    dlon, dlat, dz = np.diff(lon), np.diff(lat), np.diff(z)
    lat0 = float(np.nanmean(lat))
    coslat = np.cos(np.deg2rad(lat0))

    out = {}

    # --- A. He so phang (equirectangular), vai bo hang so pho bien ---
    sets = {
        "111320_111320": (111_320.0, 111_320.0),
        "111320_110540": (111_320.0, 110_540.0),   # chuan WGS84 xap xi
        "111139_111139": (111_139.0, 111_139.0),   # 1 do = 60 hai ly
        "111111_111111": (111_111.0, 111_111.0),   # lam tron thuong gap
    }
    for name, (m_lon, m_lat) in sets.items():
        dx = dlon * m_lon * coslat
        dy = dlat * m_lat
        out[f"equirect_{name}"] = _cumsum(dx, dy)

    # --- B. Dung ban kinh Trai Dat truc tiep ---
    dx = np.deg2rad(dlon) * R_EARTH * coslat
    dy = np.deg2rad(dlat) * R_EARTH
    out["radian_R6371"] = _cumsum(dx, dy)

    # --- C. Khong nhan cos(lat) — loi thuong gap, de nhan ra ---
    out["equirect_no_coslat"] = _cumsum(dlon * 111_320.0, dlat * 111_320.0)

    # --- D. Haversine tung buoc ---
    la1, la2 = np.deg2rad(lat[:-1]), np.deg2rad(lat[1:])
    dla, dlo = la2 - la1, np.deg2rad(dlon)
    a = np.sin(dla / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin(dlo / 2) ** 2
    out["haversine"] = float(np.nansum(2 * R_EARTH * np.arcsin(np.sqrt(a))))

    # --- E. cos(lat) tinh tung diem thay vi dung lat trung binh ---
    dx_pt = np.deg2rad(dlon) * R_EARTH * np.cos(np.deg2rad(lat[:-1]))
    out["radian_coslat_pointwise"] = _cumsum(dx_pt, np.deg2rad(dlat) * R_EARTH)

    # --- F. Bien the 3D: cach 2D tot nhat cong them thanh phan dung ---
    for key in ("equirect_111320_111320", "equirect_111320_110540", "radian_R6371"):
        m_lon, m_lat = sets.get(key.replace("equirect_", ""), (None, None))
        if m_lon is None:
            dx3 = np.deg2rad(dlon) * R_EARTH * coslat
            dy3 = np.deg2rad(dlat) * R_EARTH
        else:
            dx3, dy3 = dlon * m_lon * coslat, dlat * m_lat
        out[f"3D_{key}"] = float(np.nansum(np.sqrt(dx3**2 + dy3**2 + dz**2)))

    return out


def main() -> None:
    ref = pd.read_csv(REPO_ROOT / "reports" / "flight_level_week3.csv").set_index("flight")
    cfg = load_config()

    results = {}
    wanted = set(PROBE_FLIGHTS)
    print("Dang doc flights.csv...")
    for fid, fdf in iter_flights(cfg):
        if fid in wanted:
            results[fid] = candidates(fdf)
            wanted.discard(fid)
            print(f"  xong chuyen {fid}")
        if not wanted:
            break

    if not results:
        print("Khong lay duoc chuyen nao.")
        return

    names = list(next(iter(results.values())).keys())

    print()
    print("=" * 94)
    print("GIA TRI TUNG CACH TINH")
    print("=" * 94)
    print(f"{'cach tinh':<30}" + "".join(f"{f'F{fid}':>12}" for fid in results))
    print(f"{'--- THAM CHIEU 2D ---':<30}" +
          "".join(f"{ref.loc[fid, 'distance_2d_m']:>12.2f}" for fid in results))
    print(f"{'--- THAM CHIEU 3D ---':<30}" +
          "".join(f"{ref.loc[fid, 'distance_3d_m']:>12.2f}" for fid in results))
    print("-" * 94)
    for name in names:
        print(f"{name:<30}" + "".join(f"{results[fid][name]:>12.2f}" for fid in results))

    for label, refcol in (("2D", "distance_2d_m"), ("3D", "distance_3d_m")):
        print()
        print("=" * 94)
        print(f"SAI LECH SO VOI THAM CHIEU {label}")
        print("=" * 94)
        scores = []
        for name in names:
            errs = [abs(results[fid][name] - ref.loc[fid, refcol]) for fid in results]
            scores.append((float(np.mean(errs)), name, errs))
        scores.sort()
        print(f"{'cach tinh':<30}{'lech tb':>14}   lech tung chuyen")
        print("-" * 94)
        for mean_err, name, errs in scores[:6]:
            detail = "  ".join(f"{e:.3f}" for e in errs)
            print(f"{name:<30}{mean_err:>14.4f}   {detail}")
        best_err, best_name, _ = scores[0]
        if best_err < 0.01:
            print(f">>> KHOP CHINH XAC {label}: `{best_name}` (lech tb {best_err:.2e} m)")
        elif best_err < 1.0:
            print(f">>> RAT SAT {label}: `{best_name}` (lech tb {best_err:.4f} m)")
        else:
            print(f">>> {label} gan nhat: `{best_name}`, lech tb {best_err:.2f} m")


if __name__ == "__main__":
    main()
