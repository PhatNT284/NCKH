"""
Khoang tin cay bootstrap cho chenh lech giua cac mo hinh (§5.3, §8 muc 2).

Cot MAE_std trong bang E2a cho biet ket qua co ON DINH qua cac lan chia. No
KHONG tra loi duoc cau hoi khac: chenh lech giua hai mo hinh co that khong,
hay chi la may rui cua viec chia du lieu.

Bootstrap tra loi cau do: boc ngau nhien CO HOAN LAI 192 chuyen bay, tinh lai
chenh lech MAE, lap 2000 lan, roi xem 95 % so lan nam trong khoang nao. Khoang
khong chua 0 -> chenh lech la that.

§8 muc 2 canh bao ro: boc o cap CHUYEN BAY, khong duoc boc tung dong telemetry
nhu the chung doc lap. Script nay doc phan du out-of-fold (moi chuyen mot gia
tri) nen dung cap, va chay rat nhanh vi khong phai huan luyen lai.

    python3 -m src.bootstrap_ci
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

# Mo hinh lam moc so sanh — cac mo hinh khac deu so voi no
BASELINE = "D2_ridge_preflight"


def bootstrap_mae(err: np.ndarray, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """Phan phoi bootstrap cua MAE cho mot mo hinh."""
    n = len(err)
    idx = rng.integers(0, n, size=(n_boot, n))
    return np.mean(np.abs(err[idx]), axis=1)


def bootstrap_difference(err_a: np.ndarray, err_b: np.ndarray,
                         n_boot: int = 2000, seed: int = 42) -> dict:
    """
    Khoang tin cay cho chenh lech MAE giua hai mo hinh.

    Quan trong: dung CUNG mot bo chi so boc cho ca hai mo hinh (bootstrap theo
    cap). Boc rieng se lam mat tuong quan — hai mo hinh cung sai nang o cung
    nhung chuyen bay kho — va cho khoang rong hon thuc te.
    """
    rng = np.random.default_rng(seed)
    n = len(err_a)
    idx = rng.integers(0, n, size=(n_boot, n))

    mae_a = np.mean(np.abs(err_a[idx]), axis=1)
    mae_b = np.mean(np.abs(err_b[idx]), axis=1)
    diff = mae_b - mae_a          # duong = mo hinh B te hon mo hinh A

    lo, hi = np.percentile(diff, [2.5, 97.5])
    return {
        "chenh_lech_MAE": float(np.mean(np.abs(err_b)) - np.mean(np.abs(err_a))),
        "ci_thap": float(lo),
        "ci_cao": float(hi),
        "co_y_nghia": bool(lo > 0 or hi < 0),   # khoang khong chua 0
        "ti_le_B_tot_hon": float(np.mean(diff < 0)),
    }


def run(residuals: pd.DataFrame, n_boot: int = 2000, seed: int = 42) -> tuple:
    models = [c for c in residuals.columns if c != "flight"]
    if BASELINE not in models:
        raise ValueError(f"Khong tim thay mo hinh moc {BASELINE}")

    rng = np.random.default_rng(seed)

    # Khoang tin cay cho MAE cua TUNG mo hinh
    per_model = []
    for m in models:
        err = residuals[m].to_numpy(float)
        boot = bootstrap_mae(err, n_boot, rng)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        per_model.append({
            "mo_hinh": m,
            "MAE": float(np.mean(np.abs(err))),
            "ci_thap": float(lo),
            "ci_cao": float(hi),
        })
    per_model = pd.DataFrame(per_model).sort_values("MAE").reset_index(drop=True)

    # Chenh lech so voi mo hinh moc
    base_err = residuals[BASELINE].to_numpy(float)
    diffs = []
    for m in models:
        if m == BASELINE:
            continue
        d = bootstrap_difference(base_err, residuals[m].to_numpy(float), n_boot, seed)
        d["mo_hinh"] = m
        diffs.append(d)
    diffs = pd.DataFrame(diffs).sort_values("chenh_lech_MAE").reset_index(drop=True)

    return per_model, diffs


def main() -> None:
    ap = argparse.ArgumentParser(description="Khoang tin cay bootstrap (§8 muc 2)")
    ap.add_argument("--residuals", default="reports/d2_oof_residuals.csv")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default="reports")
    args = ap.parse_args()

    rpath = REPO_ROOT / args.residuals
    if not rpath.exists():
        raise FileNotFoundError(
            f"Khong tim thay {rpath}. Chay truoc: python3 -m src.evaluation_energy"
        )
    residuals = pd.read_csv(rpath)
    per_model, diffs = run(residuals, args.n_boot, args.seed)

    print("=" * 78)
    print(f"MAE KEM KHOANG TIN CAY 95 %  ({args.n_boot} lan boc, cap chuyen bay)")
    print("=" * 78)
    print(f"{'mo hinh':<28}{'MAE':>9}{'khoang tin cay 95%':>26}")
    print("-" * 78)
    for _, r in per_model.iterrows():
        ci = f"[{r['ci_thap']:.3f} ; {r['ci_cao']:.3f}]"
        print(f"{r['mo_hinh']:<28}{r['MAE']:>9.3f}{ci:>26}")

    print()
    print("=" * 78)
    print(f"CHENH LECH SO VOI {BASELINE}")
    print("=" * 78)
    print(f"{'mo hinh':<28}{'chenh lech':>12}{'khoang tin cay 95%':>24}   ket luan")
    print("-" * 78)
    for _, r in diffs.iterrows():
        ci = f"[{r['ci_thap']:.3f} ; {r['ci_cao']:.3f}]"
        verdict = "CO Y NGHIA" if r["co_y_nghia"] else "khong ket luan duoc"
        print(f"{r['mo_hinh']:<28}{r['chenh_lech_MAE']:>12.3f}{ci:>24}   {verdict}")

    print()
    print("Doc bang: chenh lech duong = mo hinh do TE HON mo hinh moc.")
    print("Khoang tin cay khong chua 0 -> chenh lech la that, khong phai nhieu.")
    print("Khoang chua 0 -> KHONG duoc tuyen bo mo hinh nao thang (§5.3).")

    outdir = REPO_ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    per_model.to_csv(outdir / "d2_bootstrap_mae_ci.csv", index=False)
    diffs.to_csv(outdir / "d2_bootstrap_differences.csv", index=False)

    try:
        from src.experiment_log import log_run
        log_run(
            "d2_bootstrap", seed=args.seed, n_flights=len(residuals),
            models=[c for c in residuals.columns if c != "flight"],
            config={"n_boot": args.n_boot, "moc_so_sanh": BASELINE,
                    "cap_boc": "chuyen bay"},
            outputs=["reports/d2_bootstrap_mae_ci.csv",
                     "reports/d2_bootstrap_differences.csv"],
            notes="Bootstrap theo cap tren phan du out-of-fold (§8 muc 2).",
        )
    except Exception as exc:  # nhat ky la phu, khong duoc lam hong ket qua
        print(f"(khong ghi duoc nhat ky: {exc})")

    print()
    print(f"Da ghi ket qua vao {outdir}/")


if __name__ == "__main__":
    main()
