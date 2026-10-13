"""
Sinh hinh cho bai bao — D2 (§5.3, §6/E2).

Thay yeu cau o Muc 9: "Every figure in the paper should be generated from a
script." Khong ve tay, khong chinh trong Excel.

    python3 -m src.figures

Hinh ghi vao reports/figures/ dang PNG 300 dpi, nen trang, dung cho ban in.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.evaluation_energy import TARGET, load_dataset, load_protocol
from src.interpretability import rf_importance, ridge_coefficients

REPO_ROOT = Path(__file__).resolve().parent.parent

# Bang mau da qua kiem dinh six-checks o che do nen sang:
# dai do sang, nguong chroma, tach biet voi mu mau, do tuong phan voi nen.
C_BLUE, C_ORANGE, C_PURPLE, C_GREEN = "#3b6ea5", "#c8692a", "#8a5fa8", "#4c8c5a"
INK, INK_MUTED, GRID = "#1f1f1f", "#5a5a5a", "#d8d8d4"
SURFACE = "#ffffff"

MODEL_MAIN = "D2_ridge_preflight"


def setup_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "axes.edgecolor": INK_MUTED,
        "axes.labelcolor": INK,
        "axes.linewidth": 0.8,
        "text.color": INK,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })


def _despine(ax, grid_axis="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid_axis:
        ax.grid(True, axis=grid_axis, zorder=0)
        ax.set_axisbelow(True)


# ---------------------------------------------------------------------------

def fig1_model_comparison(outdir: Path) -> None:
    """Hinh 1 — MAE cua tung mo hinh, kem thanh sai so qua cac fold."""
    e2a = pd.read_csv(REPO_ROOT / "reports" / "d2_e2a_flight_level_cv.csv")
    e2a = e2a.sort_values("MAE", ascending=True)

    labels = {
        "D2_ridge_preflight": "D2-b Ridge\n(trước chuyến bay)",
        "D3_rf_preflight": "D3-b Random Forest\n(trước chuyến bay)",
        "D2_ridge_as_written": "D2-a Ridge\n(duration đo được)",
        "D3_rf_as_written": "D3-a Random Forest\n(duration đo được)",
        "D1_distance_huber": "D1 chỉ cự ly\n(Huber)",
        "D1_distance_ols": "D1 chỉ cự ly\n(OLS)",
        "D0_constant_mean": "D0 trung bình hằng",
    }
    # Mau theo ho mo hinh, khong theo thu hang (quy tac: mau bam vao thuc the)
    family = {"D2": C_BLUE, "D3": C_ORANGE, "D1": C_PURPLE, "D0": C_GREEN}

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    y = np.arange(len(e2a))
    colors = [family[m.split("_")[0]] for m in e2a["model"]]

    ax.barh(y, e2a["MAE"], xerr=e2a["MAE_std"], height=0.62,
            color=colors, zorder=3,
            error_kw=dict(ecolor=INK_MUTED, elinewidth=1, capsize=2.5))
    ax.set_yticks(y)
    ax.set_yticklabels([labels.get(m, m) for m in e2a["model"]])
    ax.invert_yaxis()
    ax.set_xlabel("MAE (Wh) — thấp hơn là tốt hơn")
    ax.set_title("Sai số dự báo năng lượng, CV 5-fold lặp 5 lần (n = 192 chuyến bay)",
                 loc="left", pad=10)
    _despine(ax, grid_axis="x")

    for yi, (mae, std) in enumerate(zip(e2a["MAE"], e2a["MAE_std"])):
        ax.text(mae + std + 0.09, yi, f"{mae:.3f}", va="center",
                fontsize=8, color=INK)

    ax.text(0.99, -0.20, "Thanh ngang: độ lệch chuẩn qua 25 lần chạy",
            transform=ax.transAxes, ha="right", fontsize=7.5, color=INK_MUTED)
    fig.savefig(outdir / "fig1_model_comparison.png")
    plt.close(fig)


def fig2_predicted_vs_measured(outdir: Path, df: pd.DataFrame) -> None:
    """Hinh 2 — du bao so voi do duoc, du bao out-of-fold cua mo hinh chinh."""
    res = pd.read_csv(REPO_ROOT / "reports" / "d2_oof_residuals.csv")
    res = res.sort_values("flight").reset_index(drop=True)
    d = df.sort_values("flight").reset_index(drop=True)

    measured = d[TARGET].to_numpy(float)
    predicted = measured + res[MODEL_MAIN].to_numpy(float)

    fig, ax = plt.subplots(figsize=(4.6, 4.6))
    lo = min(measured.min(), predicted.min()) - 1
    hi = max(measured.max(), predicted.max()) + 1

    ax.plot([lo, hi], [lo, hi], color=INK_MUTED, lw=1, ls="--", zorder=2)
    ax.scatter(measured, predicted, s=22, color=C_BLUE, alpha=0.75,
               edgecolor=SURFACE, linewidth=0.5, zorder=3)

    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.set_xlabel("Năng lượng đo được (Wh)")
    ax.set_ylabel("Năng lượng dự báo (Wh)")
    ax.set_title("D2-b Ridge: dự báo out-of-fold", loc="left", pad=10)
    _despine(ax, grid_axis="both")

    mae = np.mean(np.abs(predicted - measured))
    bias = np.mean(predicted - measured)
    ax.text(0.04, 0.95, f"MAE  {mae:.3f} Wh\nbias  {bias:+.3f} Wh",
            transform=ax.transAxes, va="top", fontsize=8.5, color=INK)
    ax.text(0.97, 0.04, "đường đứt: dự báo hoàn hảo", transform=ax.transAxes,
            ha="right", fontsize=7.5, color=INK_MUTED)

    fig.savefig(outdir / "fig2_predicted_vs_measured.png")
    plt.close(fig)


def fig3_residuals_by_condition(outdir: Path, df: pd.DataFrame) -> None:
    """Hinh 3 — phan du theo tung dieu kien van hanh (§5.3)."""
    res = pd.read_csv(REPO_ROOT / "reports" / "d2_oof_residuals.csv")
    res = res.sort_values("flight").reset_index(drop=True)
    d = df.sort_values("flight").reset_index(drop=True)
    err = res[MODEL_MAIN].to_numpy(float)

    panels = [
        ("payload_num", "Tải trọng (g)", C_BLUE),
        ("speed_num", "Tốc độ ra lệnh (m/s)", C_ORANGE),
        ("altitude_num", "Độ cao (m)", C_PURPLE),
        ("wind_raw_mean_ms", "Gió trung bình (m/s)", C_GREEN),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(9.6, 2.9), sharey=True)
    for ax, (col, label, color) in zip(axes, panels):
        x = d[col].to_numpy(float)
        ax.axhline(0, color=INK_MUTED, lw=1, ls="--", zorder=2)
        if col == "wind_raw_mean_ms":
            ax.scatter(x, err, s=16, color=color, alpha=0.65,
                       edgecolor=SURFACE, linewidth=0.4, zorder=3)
        else:
            # Gia tri roi rac -> tan nhe de khong chong nhau
            jitter = (np.random.default_rng(42).random(len(x)) - 0.5)
            spread = np.diff(np.unique(x)).min() * 0.30 if len(np.unique(x)) > 1 else 0.2
            ax.scatter(x + jitter * spread, err, s=16, color=color, alpha=0.65,
                       edgecolor=SURFACE, linewidth=0.4, zorder=3)
            ax.set_xticks(np.unique(x))
        ax.set_xlabel(label)
        _despine(ax, grid_axis="y")

    axes[0].set_ylabel("Phần dư (Wh)\ndự báo − đo được")
    axes[0].text(0.03, 0.96, "đoán thừa", transform=axes[0].transAxes,
                 va="top", fontsize=7.5, color=INK_MUTED)
    axes[0].text(0.03, 0.04, "đoán thiếu", transform=axes[0].transAxes,
                 va="bottom", fontsize=7.5, color=INK_MUTED)

    fig.suptitle("D2-b Ridge: phần dư theo điều kiện vận hành — không có vùng lệch hệ thống",
                 x=0.012, ha="left", fontsize=10, y=1.04)
    fig.savefig(outdir / "fig3_residuals_by_condition.png")
    plt.close(fig)


def fig4_distance_extrapolation(outdir: Path) -> None:
    """Hinh 4 — ngoai suy cu ly: bias theo dai cu ly (thi nghiem bo sung E2c)."""
    e2c = pd.read_csv(REPO_ROOT / "reports" / "d2_e2c_distance_holdout.csv")

    models = [
        ("D2_ridge_preflight", "D2-b Ridge", C_BLUE),
        ("D3_rf_preflight", "D3-b Random Forest", C_ORANGE),
        ("D1_distance_ols", "D1 chỉ cự ly", C_PURPLE),
    ]
    bands = ["mid_range_427_609m", "long_range_~835m"]
    band_labels = ["427–609 m\n(7 chuyến)", "~835 m\n(5 chuyến)"]

    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    width = 0.24
    x = np.arange(len(bands))

    for i, (m, label, color) in enumerate(models):
        vals = [
            e2c[(e2c["model"] == m) & (e2c["band"] == b)]["bias"].iloc[0]
            if not e2c[(e2c["model"] == m) & (e2c["band"] == b)].empty else np.nan
            for b in bands
        ]
        pos = x + (i - 1) * (width + 0.02)
        ax.bar(pos, vals, width, color=color, label=label, zorder=3)
        for p, v in zip(pos, vals):
            off = -1.4 if v < 0 else 0.6
            ax.text(p, v + off, f"{v:+.1f}", ha="center", fontsize=7.5, color=INK)

    ax.axhline(0, color=INK, lw=1, zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels(band_labels)
    ax.set_ylabel("bias (Wh)\ndự báo − đo được")
    ax.set_title("Ngoại suy cự ly: huấn luyện chỉ trên tuyến R1 (~472 m)",
                 loc="left", pad=10)
    ax.legend(loc="lower left", ncol=1)
    _despine(ax, grid_axis="y")

    ax.text(0.99, 0.95, "bias âm = đoán thiếu = cho bay nhầm",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8, color=INK)
    ax.text(0.99, -0.26, "Thí nghiệm bổ sung ngoài giao thức. "
                         "Cả 5 chuyến dài bay cùng một ngày.",
            transform=ax.transAxes, ha="right", fontsize=7.5, color=INK_MUTED)

    fig.savefig(outdir / "fig4_distance_extrapolation.png")
    plt.close(fig)


def fig5_interpretation(outdir: Path, df: pd.DataFrame, protocol: dict) -> None:
    """Hinh 5 — he so Ridge va do quan trong dac trung cua Random Forest."""
    coef = ridge_coefficients(df, protocol)
    imp = rf_importance(df, protocol)

    nice = {
        "duration_planned_s": "thời lượng kế hoạch",
        "altitude_num": "độ cao",
        "payload_num": "tải trọng",
        "speed_num": "tốc độ ra lệnh",
        "wind_raw_mean_ms": "gió trung bình",
        "distance_2d_m": "cự ly",
    }

    # wspace rong vi ca hai o deu co nhan chu o truc y — de mac dinh thi nhan
    # cua o ben phai de len vung ve cua o ben trai.
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.2),
                             gridspec_kw={"wspace": 0.42})

    ax = axes[0]
    c = coef.iloc[::-1]
    y = np.arange(len(c))
    ax.barh(y, c["he_so_chuan_hoa"], height=0.62, color=C_BLUE, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([nice.get(v, v) for v in c["dac_trung"]])
    ax.axvline(0, color=INK, lw=1, zorder=4)
    ax.set_xlabel("hệ số (đặc trưng đã chuẩn hoá)")
    ax.set_title("D2-b Ridge: hệ số hồi quy", loc="left", pad=8)
    _despine(ax, grid_axis="x")

    ax = axes[1]
    i = imp.iloc[::-1]
    y = np.arange(len(i))
    ax.barh(y, i["do_quan_trong"], xerr=i["do_lech_chuan"], height=0.62,
            color=C_ORANGE, zorder=3,
            error_kw=dict(ecolor=INK_MUTED, elinewidth=1, capsize=2.5))
    ax.set_yticks(y)
    ax.set_yticklabels([nice.get(v, v) for v in i["dac_trung"]])
    ax.set_xlabel("độ quan trọng đặc trưng")
    ax.set_title("D3-b Random Forest: độ quan trọng", loc="left", pad=8)
    _despine(ax, grid_axis="x")

    fig.text(0.012, -0.06,
             "Độ quan trọng đặc trưng chỉ mô tả mô hình dùng cột nào khi chia cây; "
             "không phải quan hệ nhân quả (§5.2).",
             fontsize=7.5, color=INK_MUTED)
    fig.savefig(outdir / "fig5_interpretation.png")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Sinh hinh cho bai bao")
    ap.add_argument("--outdir", default="reports/figures")
    args = ap.parse_args()

    setup_style()
    outdir = REPO_ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    protocol = load_protocol()
    df = load_dataset()

    fig1_model_comparison(outdir)
    print("fig1_model_comparison.png")
    fig2_predicted_vs_measured(outdir, df)
    print("fig2_predicted_vs_measured.png")
    fig3_residuals_by_condition(outdir, df)
    print("fig3_residuals_by_condition.png")
    fig4_distance_extrapolation(outdir)
    print("fig4_distance_extrapolation.png")
    fig5_interpretation(outdir, df, protocol)
    print("fig5_interpretation.png")

    print()
    print(f"Da ghi 5 hinh vao {outdir}/ (PNG 300 dpi)")


if __name__ == "__main__":
    main()
