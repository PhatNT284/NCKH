"""
Dien giai mo hinh — D3 feature importance va D2 he so hoi quy (§5.2).

§5.2 ghi ve D3: "Feature importance is descriptive, not causal."
Script nay trich xuat con so do, va kem luon he so hoi quy cua Ridge — thu
dien giai duoc tot hon vi no co don vi.

    python3 -m src.interpretability
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, KFold

from src.evaluation_energy import (
    TARGET, feature_columns, load_dataset, load_protocol,
)
from src.models import model_registry

REPO_ROOT = Path(__file__).resolve().parent.parent


def fit_full(spec: dict, X: np.ndarray, y: np.ndarray, seed: int = 42):
    """
    Huan luyen tren TOAN BO du lieu de lay he so / do quan trong.

    Luu y: mo hinh nay chi dung de DIEN GIAI, khong dung de bao diem. Diem so
    lay tu kiem dinh cheo o evaluation_energy.py, noi mo hinh khong duoc thay
    du lieu kiem.
    """
    model = spec["factory"]()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if spec["param_grid"]:
            search = GridSearchCV(
                model, spec["param_grid"],
                cv=KFold(n_splits=5, shuffle=True, random_state=seed),
                scoring="neg_mean_absolute_error", n_jobs=-1,
            )
            search.fit(X, y)
            return search.best_estimator_, search.best_params_
        model.fit(X, y)
    return model, {}


def ridge_coefficients(df: pd.DataFrame, protocol: dict,
                       model_name: str = "D2_ridge_preflight") -> pd.DataFrame:
    """
    He so hoi quy Ridge, bao ca dang chuan hoa lan dang don vi goc.

    Hai cach doc khac nhau:
      - he so CHUAN HOA: so sanh duoc giua cac dac trung ("cai nao anh huong
        manh hon"), vi moi dac trung da dua ve cung thang do
      - he so DON VI GOC: doc duoc truc tiep ("tang 1 g tai thi ton them bao
        nhieu Wh"), nhung khong so sanh giua cac dac trung duoc
    """
    spec = model_registry()[model_name]
    cols = feature_columns(spec["features"], protocol)
    X = df[cols].to_numpy(float)
    y = df[TARGET].to_numpy(float)

    est, best = fit_full(spec, X, y)
    coef_scaled = est.named_steps["model"].coef_
    scale = est.named_steps["scaler"].scale_

    rows = []
    for col, c_scaled, s in zip(cols, coef_scaled, scale):
        rows.append({
            "dac_trung": col,
            "he_so_chuan_hoa": float(c_scaled),
            "he_so_don_vi_goc": float(c_scaled / s),
            "do_lon": abs(float(c_scaled)),
        })
    out = pd.DataFrame(rows).sort_values("do_lon", ascending=False)
    out.attrs["alpha"] = best.get("model__alpha")
    out.attrs["intercept"] = float(est.named_steps["model"].intercept_)
    return out.reset_index(drop=True)


def rf_importance(df: pd.DataFrame, protocol: dict,
                  model_name: str = "D3_rf_preflight") -> pd.DataFrame:
    """Do quan trong dac trung cua Random Forest. MO TA, khong phai nhan qua."""
    spec = model_registry()[model_name]
    cols = feature_columns(spec["features"], protocol)
    X = df[cols].to_numpy(float)
    y = df[TARGET].to_numpy(float)

    est, best = fit_full(spec, X, y)
    rf = est.named_steps["model"]

    # Do phan tan giua cac cay — cho biet con so co on dinh khong
    per_tree = np.array([t.feature_importances_ for t in rf.estimators_])

    out = pd.DataFrame({
        "dac_trung": cols,
        "do_quan_trong": rf.feature_importances_,
        "do_lech_chuan": per_tree.std(axis=0),
    }).sort_values("do_quan_trong", ascending=False).reset_index(drop=True)
    out.attrs["best_params"] = best
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="D2/D3 — dien giai mo hinh")
    ap.add_argument("--outdir", default="reports")
    args = ap.parse_args()

    protocol = load_protocol()
    df = load_dataset()
    outdir = REPO_ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    coef = ridge_coefficients(df, protocol)
    print("=" * 76)
    print("D2-b RIDGE — HE SO HOI QUY")
    print("=" * 76)
    print(f"alpha chon duoc: {coef.attrs['alpha']}   "
          f"hang so: {coef.attrs['intercept']:.3f} Wh")
    print()
    print(f"{'dac trung':<24}{'he so chuan hoa':>18}{'he so don vi goc':>20}")
    print("-" * 76)
    for _, r in coef.iterrows():
        print(f"{r['dac_trung']:<24}{r['he_so_chuan_hoa']:>18.4f}"
              f"{r['he_so_don_vi_goc']:>20.6f}")
    coef.drop(columns="do_lon").to_csv(outdir / "d2_ridge_coefficients.csv", index=False)

    imp = rf_importance(df, protocol)
    print()
    print("=" * 76)
    print("D3-b RANDOM FOREST — DO QUAN TRONG DAC TRUNG")
    print("=" * 76)
    print(f"tham so chon duoc: {imp.attrs['best_params']}")
    print()
    print(f"{'dac trung':<24}{'do quan trong':>16}{'do lech chuan':>16}")
    print("-" * 76)
    for _, r in imp.iterrows():
        bar = "#" * int(round(r["do_quan_trong"] * 40))
        print(f"{r['dac_trung']:<24}{r['do_quan_trong']:>16.4f}"
              f"{r['do_lech_chuan']:>16.4f}  {bar}")
    imp.to_csv(outdir / "d3_feature_importance.csv", index=False)

    print()
    print("LUU Y BAT BUOC NEU TRONG BAI (§5.2):")
    print("  Do quan trong dac trung chi MO TA mo hinh dung cot nao nhieu khi")
    print("  chia cay. No KHONG phai quan he nhan qua, va khong doc duoc thanh")
    print("  'tang bien X len thi nang luong tang bao nhieu'.")
    print()
    print(f"Da ghi ket qua vao {outdir}/")


if __name__ == "__main__":
    main()
