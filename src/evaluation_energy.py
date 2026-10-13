"""
Danh gia du bao nang luong — D2 (§5.3, §6/E2).

Ba thi nghiem:
    E2a  CV 5-fold lap 5 lan o cap chuyen bay
    E2b  giu lai cau hinh — bo nguyen mot to hop (tai x toc do x do cao)
    E2c  giu lai cu ly — huan luyen chi tren R1, du bao 12 chuyen ngoai R1
         (BO SUNG ngoai giao thuc cua thay, khai bao ro)

Nguyen tac chong ro ri (§5.3):
    - don vi danh gia la CHUYEN BAY, moi chuyen mot dong
    - chuan hoa va tinh chinh sieu tham so chi trong fold huan luyen
    - tinh chinh bang CV long, khong cham vao fold kiem

    python3 -m src.evaluation_energy
"""

from __future__ import annotations

import argparse
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.model_selection import GridSearchCV, KFold, RepeatedKFold

from src.models import model_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = "energy_Wh"


# ---------------------------------------------------------------------------
# Du lieu
# ---------------------------------------------------------------------------

def load_protocol() -> dict:
    with open(REPO_ROOT / "configs" / "d2_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_dataset(path: Path | str | None = None) -> pd.DataFrame:
    """
    Doc bang cap chuyen bay va dam bao co du cac cot dac trung.

    `duration_planned_s` duoc suy ra tai day neu chua co, theo §5.5:
    thoi luong ke hoach = cu ly / toc do hanh trinh gia dinh.
    """
    path = Path(path) if path else REPO_ROOT / "data" / "processed" / "flight_level.csv"
    if not path.exists():
        alt = REPO_ROOT / "reports" / "flight_level_week3.csv"
        if alt.exists():
            path = alt
        else:
            raise FileNotFoundError(
                "Khong tim thay bang cap chuyen bay. Chay truoc:\n"
                "  python3 -m src.features --out data/processed/flight_level.csv"
            )

    df = pd.read_csv(path)

    if "duration_planned_s" not in df.columns:
        df["duration_planned_s"] = df["distance_2d_m"] / df["speed_num"]

    # Bang tuan 3 dat ten cot gio la `wind_mean_ms`; giao thuc dung
    # `wind_raw_mean_ms`. Hai cot nay la mot: deu la gio THO.
    if "wind_raw_mean_ms" not in df.columns and "wind_mean_ms" in df.columns:
        df["wind_raw_mean_ms"] = df["wind_mean_ms"]

    return df


def feature_columns(kind: str | None, protocol: dict) -> list[str]:
    if kind is None:
        return []
    if kind == "distance_only":
        return ["distance_2d_m"]
    return list(protocol["features"][kind])


def assert_no_leakage(cols: list[str], protocol: dict) -> None:
    """Chan bien hau nghiem — hang rao cuoi cung truoc khi huan luyen."""
    forbidden = {e["column"] for e in protocol["features"]["forbidden"]}
    leaked = forbidden & set(cols)
    if leaked:
        raise ValueError(f"RO RI: bien hau nghiem trong tap dac trung: {leaked}")


# ---------------------------------------------------------------------------
# Thuoc do (§5.3)
# ---------------------------------------------------------------------------

def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_pred - y_true
    return {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err**2))),
        # Sai so CO DAU: du bao thieu he thong la van de an toan, vi no khien
        # he thong cho bay nhung chuyen khong du pin.
        "bias": float(np.mean(err)),
        "WAPE": float(np.sum(np.abs(err)) / np.sum(np.abs(y_true)) * 100),
    }


def measure_inference_time(spec: dict, X: np.ndarray, y: np.ndarray,
                           n_repeat: int = 50, seed: int = 42) -> float:
    """
    Thoi gian suy luan cho MOT chuyen bay, don vi mili giay (§5.3, thuoc do phu).

    Do thoi gian `predict`, khong do thoi gian huan luyen: khi van hanh, mo hinh
    da duoc huan luyen san, nguoi dieu phoi chi cho mot lan du bao.
    """
    model = spec["factory"]()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X, y)

    one = X[:1]
    model.predict(one)                       # lan dau co chi phi khoi tao
    start = time.perf_counter()
    for _ in range(n_repeat):
        model.predict(one)
    return (time.perf_counter() - start) / n_repeat * 1000.0


def fit_predict(spec: dict, X_tr, y_tr, X_te, seed: int = 42):
    """Huan luyen mot mo hinh, tinh chinh bang CV LONG trong fold huan luyen."""
    model = spec["factory"]()
    if spec["param_grid"]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            search = GridSearchCV(
                model, spec["param_grid"],
                cv=KFold(n_splits=3, shuffle=True, random_state=seed),
                scoring="neg_mean_absolute_error", n_jobs=-1,
            )
            search.fit(X_tr, y_tr)
        return search.predict(X_te), search.best_params_
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X_tr, y_tr)
    return model.predict(X_te), {}


# ---------------------------------------------------------------------------
# E2a — CV cap chuyen bay
# ---------------------------------------------------------------------------

def run_e2a(df: pd.DataFrame, protocol: dict, n_splits=5, n_repeats=5, seed=42):
    """CV 5-fold lap 5 lan. Tra ve (bang ket qua, phan du out-of-fold)."""
    y = df[TARGET].to_numpy(float)
    cv = RepeatedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    rows, residuals = [], {}

    for name, spec in model_registry().items():
        cols = feature_columns(spec["features"], protocol)
        assert_no_leakage(cols, protocol)
        X = df[cols].to_numpy(float) if cols else np.zeros((len(df), 1))

        fold_metrics, oof_sum, oof_cnt = [], np.zeros(len(df)), np.zeros(len(df))
        for tr, te in cv.split(X):
            pred, _ = fit_predict(spec, X[tr], y[tr], X[te], seed)
            fold_metrics.append(metrics(y[te], pred))
            oof_sum[te] += pred
            oof_cnt[te] += 1

        agg = {"model": name, "label": spec["label"], "n_features": len(cols)}
        for m in ("MAE", "RMSE", "bias", "WAPE"):
            vals = [f[m] for f in fold_metrics]
            agg[m] = float(np.mean(vals))
            agg[f"{m}_std"] = float(np.std(vals))
        # Thuoc do phu (§5.3)
        agg["inference_ms"] = measure_inference_time(spec, X, y, seed=seed)
        rows.append(agg)

        # Phan du out-of-fold — nguyen lieu cho lop bat dinh o D5 (§5.8)
        residuals[name] = (oof_sum / np.maximum(oof_cnt, 1)) - y

    return pd.DataFrame(rows).sort_values("MAE").reset_index(drop=True), residuals


# ---------------------------------------------------------------------------
# E2b — giu lai cau hinh
# ---------------------------------------------------------------------------

def run_e2b(df: pd.DataFrame, protocol: dict, seed=42) -> pd.DataFrame:
    """
    Bo nguyen mot to hop (tai x toc do x do cao) ra khoi tap huan luyen.

    Kiem kha nang tong quat ngoai dieu kien gan trung lap — chia ngau nhien
    thong thuong se de cac chuyen gan trung nhau nam o ca hai phia (§5.3).
    """
    y = df[TARGET].to_numpy(float)
    groups = df.groupby(["payload_num", "speed_num", "altitude_num"]).ngroup().to_numpy()
    rows = []

    for name, spec in model_registry().items():
        cols = feature_columns(spec["features"], protocol)
        assert_no_leakage(cols, protocol)
        X = df[cols].to_numpy(float) if cols else np.zeros((len(df), 1))

        preds, truths = [], []
        for g in np.unique(groups):
            te = groups == g
            tr = ~te
            if tr.sum() < 10:
                continue
            pred, _ = fit_predict(spec, X[tr], y[tr], X[te], seed)
            preds.append(pred)
            truths.append(y[te])

        agg = metrics(np.concatenate(truths), np.concatenate(preds))
        agg.update({"model": name, "label": spec["label"],
                    "n_configs": int(len(np.unique(groups)))})
        rows.append(agg)

    return pd.DataFrame(rows).sort_values("MAE").reset_index(drop=True)


# ---------------------------------------------------------------------------
# E2c — giu lai cu ly (BO SUNG ngoai giao thuc)
# ---------------------------------------------------------------------------

def run_e2c(df: pd.DataFrame, protocol: dict, seed=42) -> pd.DataFrame:
    """
    Huan luyen CHI tren tuyen R1 (~472 m), du bao cac chuyen ngoai R1.

    Kiem xem phep nhan cu ly trong Eq (5) co dung vung khi cu ly dai ra khong.
    KHONG dung ket qua nay de chon mo hinh.
    """
    train = df[df["route"] == "R1"]
    rows = []

    bands = {
        "mid_range_427_609m": df[(df["route"] != "R1") & (df["distance_2d_m"] < 700)],
        "long_range_~835m": df[(df["route"] != "R1") & (df["distance_2d_m"] >= 700)],
    }

    for name, spec in model_registry().items():
        cols = feature_columns(spec["features"], protocol)
        assert_no_leakage(cols, protocol)
        if not cols:
            continue
        X_tr = train[cols].to_numpy(float)
        y_tr = train[TARGET].to_numpy(float)

        for band, test in bands.items():
            if test.empty:
                continue
            pred, _ = fit_predict(spec, X_tr, y_tr,
                                  test[cols].to_numpy(float), seed)
            agg = metrics(test[TARGET].to_numpy(float), pred)
            agg.update({"model": name, "label": spec["label"],
                        "band": band, "n_test": len(test)})
            rows.append(agg)

    return pd.DataFrame(rows)[
        ["model", "label", "band", "n_test", "MAE", "RMSE", "bias", "WAPE"]
    ].reset_index(drop=True)


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="D2 — benchmark du bao nang luong")
    ap.add_argument("--data", default=None)
    ap.add_argument("--outdir", default="reports")
    args = ap.parse_args()

    protocol = load_protocol()
    df = load_dataset(args.data)
    outdir = REPO_ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Du lieu: {len(df)} chuyen bay")
    print(f"Muc tieu: {TARGET}  "
          f"(trung binh {df[TARGET].mean():.2f} Wh, "
          f"khoang {df[TARGET].min():.1f}-{df[TARGET].max():.1f})")
    print()

    print("E2a — CV 5-fold lap 5 lan o cap chuyen bay")
    e2a, residuals = run_e2a(df, protocol)
    print(e2a[["label", "n_features", "MAE", "MAE_std", "RMSE", "bias", "WAPE",
               "inference_ms"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    e2a.to_csv(outdir / "d2_e2a_flight_level_cv.csv", index=False)
    pd.DataFrame(residuals).assign(flight=df["flight"].values).to_csv(
        outdir / "d2_oof_residuals.csv", index=False)

    print()
    print("E2b — giu lai cau hinh")
    e2b = run_e2b(df, protocol)
    print(e2b[["label", "MAE", "RMSE", "bias", "WAPE"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    e2b.to_csv(outdir / "d2_e2b_configuration_holdout.csv", index=False)

    print()
    print("E2c — giu lai cu ly (BO SUNG ngoai giao thuc)")
    e2c = run_e2c(df, protocol)
    print(e2c[["label", "band", "n_test", "MAE", "bias", "WAPE"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    e2c.to_csv(outdir / "d2_e2c_distance_holdout.csv", index=False)

    # Nhat ky thi nghiem (§8 muc 6)
    try:
        from src.experiment_log import log_run
        log_run(
            "d2_benchmark",
            seed=protocol["partitioning"]["cv"]["random_state"],
            n_flights=len(df),
            features={
                "preflight": protocol["features"]["preflight"],
                "as_written": protocol["features"]["as_written"],
            },
            models=list(model_registry().keys()),
            config={
                "cv": protocol["partitioning"]["cv"],
                "protocol_version": protocol["meta"]["version"],
                "thi_nghiem": ["E2a", "E2b", "E2c"],
            },
            outputs=[
                "reports/d2_e2a_flight_level_cv.csv",
                "reports/d2_e2b_configuration_holdout.csv",
                "reports/d2_e2c_distance_holdout.csv",
                "reports/d2_oof_residuals.csv",
            ],
            data_path=REPO_ROOT / "reports" / "flight_level_week3.csv",
            notes="Nang luong tinh tren TOAN chuyen bay, khong phan doan theo pha "
                  "(§4.2 buoc 4 cho phep khi phan doan khong dang tin).",
        )
    except Exception as exc:  # nhat ky la phu, khong duoc lam hong ket qua
        print(f"(khong ghi duoc nhat ky: {exc})")

    print()
    print(f"Da ghi ket qua vao {outdir}/")


if __name__ == "__main__":
    main()