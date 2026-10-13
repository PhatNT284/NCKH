"""
Do xem bang tuan 3 da dinh nghia `distance_2d_m` theo cach nao.

Chay:
    python3 scripts/diagnose_distance.py

Script thu nhieu dinh nghia cu ly khac nhau tren vai chuyen bay, roi so voi
gia tri trong reports/flight_level_week3.csv de xem cach nao khop.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.data_ingestion import load_config, iter_flights  # noqa: E402

# Chuyen bay de kiem: 3 chuyen R1 binh thuong + chuyen dai nhat + 1 chuyen R5
PROBE_FLIGHTS = [1, 2, 10, 50, 272]


def candidates(d: pd.DataFrame) -> dict:
    """Cac cach dinh nghia cu ly 2D co the da duoc dung."""
    d = d.sort_values("time")
    x, y = d["position_x"].to_numpy(float), d["position_y"].to_numpy(float)
    t = d["time"].to_numpy(float)
    dx, dy = np.diff(x), np.diff(y)
    step = np.hypot(dx, dy)
    dt = np.diff(t)

    out = {}

    # 1. Tong chieu dai duong di (cach hien tai cua src/features.py)
    out["cumulative_path"] = float(np.nansum(step))

    # 2. Khoang cach thang tu diem dau den diem xa nhat, nhan doi (di va ve)
    dist_from_start = np.hypot(x - x[0], y - y[0])
    out["max_displacement_x2"] = float(2 * np.nanmax(dist_from_start))

    # 3. Khoang cach thang diem dau -> diem cuoi
    out["start_to_end"] = float(np.hypot(x[-1] - x[0], y[-1] - y[0]))

    # 4. Tong duong di nhung bo cac mau gan nhu dung yen (loc nhieu GPS khi treo)
    with np.errstate(divide="ignore", invalid="ignore"):
        inst_speed = np.where(dt > 0, step / dt, 0.0)
    for thr in (0.2, 0.5, 1.0):
        out[f"cumulative_speed_gt_{thr}"] = float(np.nansum(step[inst_speed > thr]))

    # 5. Tich phan toc do ngang tu cot velocity (neu co)
    if {"velocity_x", "velocity_y"}.issubset(d.columns):
        vx = d["velocity_x"].to_numpy(float)[:-1]
        vy = d["velocity_y"].to_numpy(float)[:-1]
        out["velocity_integral"] = float(np.nansum(np.hypot(vx, vy) * dt))

    # 6. Tong duong di, lam tron toa do ve 1 m truoc (giam nhieu GPS)
    xr, yr = np.round(x, 0), np.round(y, 0)
    out["cumulative_rounded_1m"] = float(np.nansum(np.hypot(np.diff(xr), np.diff(yr))))

    return out


def main() -> None:
    ref_path = REPO_ROOT / "reports" / "flight_level_week3.csv"
    ref = pd.read_csv(ref_path).set_index("flight")

    cfg = load_config()
    results = {}
    wanted = set(PROBE_FLIGHTS)

    print("Dang doc flights.csv, chi lay cac chuyen can kiem...")
    for fid, fdf in iter_flights(cfg):
        if fid in wanted:
            results[fid] = candidates(fdf)
            wanted.discard(fid)
            print(f"  xong chuyen {fid}")
        if not wanted:
            break

    if not results:
        print("Khong lay duoc chuyen nao. Kiem lai data/raw/flights.csv.")
        return

    names = list(next(iter(results.values())).keys())

    print()
    print("=" * 92)
    print("SO SANH VOI GIA TRI THAM CHIEU (distance_2d_m trong bang tuan 3)")
    print("=" * 92)
    header = f"{'cach tinh':<28}" + "".join(f"{f'F{fid}':>12}" for fid in results)
    print(header)
    print(f"{'--- THAM CHIEU ---':<28}" +
          "".join(f"{ref.loc[fid, 'distance_2d_m']:>12.1f}" for fid in results))
    print("-" * 92)
    for name in names:
        row = f"{name:<28}" + "".join(f"{results[fid][name]:>12.1f}" for fid in results)
        print(row)

    print()
    print("=" * 92)
    print("SAI LECH TUYET DOI SO VOI THAM CHIEU (cang nho cang khop)")
    print("=" * 92)
    scores = []
    for name in names:
        errs = [abs(results[fid][name] - ref.loc[fid, "distance_2d_m"]) for fid in results]
        scores.append((float(np.mean(errs)), name, errs))
    scores.sort()

    print(f"{'cach tinh':<28}{'lech trung binh':>18}   lech tung chuyen")
    print("-" * 92)
    for mean_err, name, errs in scores:
        detail = "  ".join(f"{e:.1f}" for e in errs)
        print(f"{name:<28}{mean_err:>18.2f}   {detail}")

    print()
    best_err, best_name, _ = scores[0]
    if best_err < 1.0:
        print(f">>> KHOP: tuan 3 dung cach `{best_name}` (lech trung binh {best_err:.3f} m)")
    else:
        print(f">>> Chua cach nao khop. Gan nhat la `{best_name}`, lech {best_err:.1f} m.")
        print(">>> Gui ket qua nay lai de xem them cach khac.")


if __name__ == "__main__":
    main()
