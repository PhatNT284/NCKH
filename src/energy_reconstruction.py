"""
Tai lap nang luong tieu thu tung chuyen bay tu dien ap va dong dien (§4.2).

Cong thuc rang buoc — KHONG duoc thay doi:

    P_t = V_t * I_t
    E_measured = sum_t  V_t * I_t * dt                              (§4.2)

Phuong phap cong bo: trapezoid, dung khoang thoi gian THUC giua hai mau.
Doi chieu voi tong Riemann de phat hien loi; quality_report.md ghi lech
trung vi 0.040 % giua hai phuong phap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

JOULES_PER_WH = 3600.0


def instantaneous_power(voltage: np.ndarray, current: np.ndarray) -> np.ndarray:
    """P_t = V_t * I_t, don vi W."""
    return np.asarray(voltage, dtype=float) * np.asarray(current, dtype=float)


def integrate_energy_trapezoid(time_s: np.ndarray, power_w: np.ndarray) -> float:
    """
    Tich phan cong suat theo thoi gian bang quy tac hinh thang -> nang luong (J).

    Dung khoang thoi gian thuc giua hai mau, khong gia dinh tan so lay mau deu
    (§4.2: "If timestamps are irregular, use the actual time difference between
    consecutive samples").
    """
    t = np.asarray(time_s, dtype=float)
    p = np.asarray(power_w, dtype=float)
    if len(t) < 2:
        return 0.0
    return float(np.trapezoid(p, t)) if hasattr(np, "trapezoid") else float(np.trapz(p, t))


def integrate_energy_riemann(time_s: np.ndarray, power_w: np.ndarray) -> float:
    """
    Tong Riemann tien (forward) — CHI dung de doi chieu, khong phai so cong bo.
    """
    t = np.asarray(time_s, dtype=float)
    p = np.asarray(power_w, dtype=float)
    if len(t) < 2:
        return 0.0
    return float(np.sum(p[:-1] * np.diff(t)))


def joules_to_wh(joules: float) -> float:
    """J -> Wh."""
    return joules / JOULES_PER_WH


def reconstruct_flight_energy(
    df: pd.DataFrame,
    time_col: str = "time",
    voltage_col: str = "voltage",
    current_col: str = "current",
) -> dict:
    """
    Tinh nang luong va cac dai luong cong suat cho MOT chuyen bay.

    Loai cac dong thieu du lieu, sap xep theo thoi gian, bo moc thoi gian
    trung lap (giu ban ghi dau tien).

    Tra ve dict gom: energy_Wh, energy_Wh_riemann, cross_check_pct,
    P_mean_W, P_max_W, duration_s, n_samples, sample_hz.
    """
    need = [time_col, voltage_col, current_col]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"Thieu cot: {missing}. Co: {list(df.columns)}")

    d = df[need].dropna().sort_values(time_col)
    d = d[~d[time_col].duplicated(keep="first")]

    if len(d) < 2:
        return {
            "energy_Wh": np.nan, "energy_Wh_riemann": np.nan,
            "cross_check_pct": np.nan, "P_mean_W": np.nan, "P_max_W": np.nan,
            "duration_s": np.nan, "n_samples": len(d), "sample_hz": np.nan,
        }

    t = d[time_col].to_numpy(dtype=float)
    p = instantaneous_power(d[voltage_col].to_numpy(), d[current_col].to_numpy())

    e_trap = joules_to_wh(integrate_energy_trapezoid(t, p))
    e_riem = joules_to_wh(integrate_energy_riemann(t, p))
    duration = float(t[-1] - t[0])

    cross = abs(e_trap - e_riem) / e_trap * 100.0 if e_trap else np.nan

    return {
        "energy_Wh": e_trap,                 # so CONG BO
        "energy_Wh_riemann": e_riem,         # chi doi chieu
        "cross_check_pct": cross,
        "P_mean_W": float(np.mean(p)),
        "P_max_W": float(np.max(p)),
        "duration_s": duration,
        "n_samples": int(len(d)),
        "sample_hz": float((len(d) - 1) / duration) if duration > 0 else np.nan,
    }
