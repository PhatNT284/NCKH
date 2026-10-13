"""
Cac mo hinh du bao nang luong D0-D3 (§5.2, Proposal 4.3).

Dinh nghia lay nguyen tu giao thuc. KHONG them mo hinh ngoai danh sach de lam
day bang so sanh (§5.2).

    D0  trung binh hang        — moc kiem tra
    D1  chi cu ly              — hoi quy tuyen tinh, co ban the ben vung Huber
    D2  Ridge                  — da yeu to, tuyen tinh co phat
    D3  Random Forest          — da yeu to, phi tuyen, gioi han do sau

Moi mo hinh deu duoc boc trong Pipeline co buoc chuan hoa, de viec chuan hoa
chi dung thong ke cua fold huan luyen (§5.3).
"""

from __future__ import annotations

from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import HuberRegressor, LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Luoi sieu tham so — tinh chinh bang CV long ben trong fold huan luyen (§5.3)
RIDGE_ALPHAS = [0.01, 0.1, 1.0, 10.0, 100.0]
RF_PARAM_GRID = {
    "model__max_depth": [3, 5, 8],
    "model__min_samples_leaf": [2, 4, 8],
}


def make_d0() -> Pipeline:
    """D0 — du bao bang trung binh cua fold huan luyen."""
    return Pipeline([("model", DummyRegressor(strategy="mean"))])


def make_d1(robust: bool = False) -> Pipeline:
    """D1 — hoi quy chi dung cu ly. `robust=True` cho ban the Huber."""
    model = HuberRegressor(max_iter=1000) if robust else LinearRegression()
    return Pipeline([("scaler", StandardScaler()), ("model", model)])


def make_d2(alpha: float = 1.0) -> Pipeline:
    """D2 — Ridge tren tap dac trung da chot."""
    return Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=alpha))])


def make_d3(max_depth: int = 5, min_samples_leaf: int = 4,
            random_state: int = 42) -> Pipeline:
    """D3 — Random Forest gioi han do sau."""
    return Pipeline([
        ("model", RandomForestRegressor(
            n_estimators=300,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state,
            # n_jobs=1: viec song song da nam o lop GridSearchCV ben ngoai.
            # Long hai lop song song se tranh nhau CPU va cham hon han.
            n_jobs=1,
        )),
    ])


def model_registry() -> dict:
    """
    Danh sach mo hinh se chay, kem tap dac trung va luoi tinh chinh cua tung cai.

    `features` nhan mot trong ba gia tri:
        "distance_only"  chi dung cu ly
        "preflight"      tap D2-b — chi dai luong biet truoc khi cat canh
        "as_written"     tap D2-a — dung chu §5.2, co duration do duoc
        None             khong dung dac trung nao (D0)
    """
    return {
        "D0_constant_mean": {
            "factory": make_d0, "features": None, "param_grid": None,
            "label": "D0 trung binh hang",
        },
        "D1_distance_ols": {
            "factory": make_d1, "features": "distance_only", "param_grid": None,
            "label": "D1 chi cu ly (OLS)",
        },
        "D1_distance_huber": {
            "factory": lambda: make_d1(robust=True), "features": "distance_only",
            "param_grid": None, "label": "D1 chi cu ly (Huber)",
        },
        "D2_ridge_preflight": {
            "factory": make_d2, "features": "preflight",
            "param_grid": {"model__alpha": RIDGE_ALPHAS},
            "label": "D2-b Ridge (truoc chuyen bay)",
        },
        "D2_ridge_as_written": {
            "factory": make_d2, "features": "as_written",
            "param_grid": {"model__alpha": RIDGE_ALPHAS},
            "label": "D2-a Ridge (co duration do duoc)",
        },
        "D3_rf_preflight": {
            "factory": make_d3, "features": "preflight",
            "param_grid": RF_PARAM_GRID,
            "label": "D3-b Random Forest (truoc chuyen bay)",
        },
        "D3_rf_as_written": {
            "factory": make_d3, "features": "as_written",
            "param_grid": RF_PARAM_GRID,
            "label": "D3-a Random Forest (co duration do duoc)",
        },
    }
