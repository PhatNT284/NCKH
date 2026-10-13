"""
Sai so theo nhom — D2 (§5.3: "Error by payload, speed, altitude, wind condition,
and flight pattern").

MAE trung binh giau mat cac vung mo hinh yeu. Script nay tach sai so ra theo
tung dieu kien van hanh de tim vung do.

Doc `reports/d2_oof_residuals.csv` (phan du out-of-fold, sinh boi
evaluation_energy.py) nen chay rat nhanh — khong phai huan luyen lai.

    python3 -m src.subgroup_analysis
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation_energy import load_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent

# Mo hinh dua vao bang trong bai. Cac mo hinh con lai van tinh va ghi ra file,
# nhung bang in ra man hinh chi hien nhung cai nay cho de doc.
HEADLINE_MODELS = ["D2_ridge_preflight", "D3_rf_preflight", "D1_distance_ols"]


def wind_regime(series: pd.Series) -> pd.Series:
    """Chia gio thanh ba che do theo tam phan vi cua chinh du lieu."""
    q1, q2 = series.quantile([1 / 3, 2 / 3])
    return pd.cut(
        series, bins=[-np.inf, q1, q2, np.inf],
        labels=[f"thap (<{q1:.2f})", f"vua ({q1:.2f}-{q2:.2f})", f"cao (>{q2:.2f})"],
    )


def distance_band(series: pd.Series) -> pd.Series:
    """Chia cu ly theo tuyen bay, khong chia deu — vi R1 chiem 94 %."""
    return pd.cut(
        series, bins=[0, 500, 700, np.inf],
        labels=["~472 m (R1)", "500-700 m", ">700 m"],
    )


def build_groups(df: pd.DataFrame) -> dict:
    """Cac cach chia nhom. Khoa la ten chieu, gia tri la cot nhan."""
    return {
        "Tai trong (g)": df["payload_num"].astype(int).astype(str),
        "Toc do ra lenh (m/s)": df["speed_num"].astype(int).astype(str),
        "Do cao (m)": df["altitude_num"].astype(int).astype(str),
        "Che do gio (m/s)": wind_regime(df["wind_raw_mean_ms"]).astype(str),
        "Dai cu ly": distance_band(df["distance_2d_m"]).astype(str),
    }


def subgroup_table(residuals: pd.DataFrame, df: pd.DataFrame,
                   models: list[str]) -> pd.DataFrame:
    """
    Tinh MAE va bias cho tung nhom, tung mo hinh.

    `residuals` chua sai so co dau (du bao - thuc te) cho tung chuyen bay.
    MAE = trung binh tri tuyet doi; bias = trung binh giu nguyen dau.
    """
    rows = []
    for dim, labels in build_groups(df).items():
        for value in pd.unique(labels):
            mask = (labels == value).to_numpy()
            rec = {"chieu": dim, "nhom": value, "n": int(mask.sum())}
            for m in models:
                if m not in residuals.columns:
                    continue
                err = residuals.loc[mask, m].to_numpy(float)
                rec[f"{m}__MAE"] = float(np.mean(np.abs(err)))
                rec[f"{m}__bias"] = float(np.mean(err))
            rows.append(rec)
    return pd.DataFrame(rows)


def print_dimension(table: pd.DataFrame, model: str) -> None:
    """In bang cho mot mo hinh, nhom theo tung chieu."""
    mae_col, bias_col = f"{model}__MAE", f"{model}__bias"
    if mae_col not in table.columns:
        return

    overall_mae = np.average(table.groupby("chieu").first()[mae_col])  # xap xi
    print()
    print("=" * 72)
    print(f"MO HINH: {model}")
    print("=" * 72)
    print(f"{'chieu':<22}{'nhom':<18}{'n':>5}{'MAE':>9}{'bias':>9}   canh bao")
    print("-" * 72)

    for dim in table["chieu"].unique():
        sub = table[table["chieu"] == dim].sort_values("nhom")
        best = sub[mae_col].min()
        worst = sub[mae_col].max()
        for i, (_, r) in enumerate(sub.iterrows()):
            flag = ""
            # Bias am dang ke = mo hinh doan THIEU = vung nguy hiem
            if r[bias_col] < -0.3:
                flag = "DOAN THIEU"
            elif r[mae_col] == worst and worst > 2 * best:
                flag = "sai nang hon han"
            label = dim if i == 0 else ""
            print(f"{label:<22}{str(r['nhom']):<18}{int(r['n']):>5}"
                  f"{r[mae_col]:>9.3f}{r[bias_col]:>9.3f}   {flag}")
        print("-" * 72)


def main() -> None:
    ap = argparse.ArgumentParser(description="D2 — sai so theo nhom")
    ap.add_argument("--residuals", default="reports/d2_oof_residuals.csv")
    ap.add_argument("--out", default="reports/d2_subgroup_errors.csv")
    args = ap.parse_args()

    rpath = REPO_ROOT / args.residuals
    if not rpath.exists():
        raise FileNotFoundError(
            f"Khong tim thay {rpath}. Chay truoc: python3 -m src.evaluation_energy"
        )

    residuals = pd.read_csv(rpath)
    df = load_dataset().sort_values("flight").reset_index(drop=True)

    if "flight" in residuals.columns:
        residuals = residuals.sort_values("flight").reset_index(drop=True)
        if not np.array_equal(residuals["flight"].to_numpy(), df["flight"].to_numpy()):
            raise ValueError("Danh sach chuyen bay trong hai file khong khop.")

    models = [c for c in residuals.columns if c != "flight"]
    table = subgroup_table(residuals, df, models)

    for m in HEADLINE_MODELS:
        print_dimension(table, m)

    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    print()
    print(f"Da ghi {out}  ({len(table)} nhom x {len(models)} mo hinh)")


if __name__ == "__main__":
    main()
