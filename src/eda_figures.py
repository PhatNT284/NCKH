"""
Sinh bo bieu do phan tich du lieu (EDA) cho 192 chuyen bay va bo quyet dinh D3.

Bo sung cho src/figures.py (hinh D2): o day la hinh mo ta du lieu va hinh D3.

    python3 -m src.eda_figures

Doc tu reports/*.csv (khong can du lieu tho). Hinh ghi vao reports/figures/eda/
dang PNG 300 dpi, cung bang mau va kieu chu voi src/figures.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.figures import (C_BLUE, C_ORANGE, C_PURPLE, C_GREEN, INK, INK_MUTED,
                         SURFACE, _despine, setup_style)

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"

PAYLOAD_COLORS = {0.0: C_BLUE, 250.0: C_ORANGE, 500.0: C_PURPLE}
# Mau ngu nghia cho phan quyet D3
C_FLY, C_COND, C_NOFLY = C_GREEN, "#d39b2a", "#b8483e"


def _flights() -> pd.DataFrame:
    return pd.read_csv(REPORTS / "flight_level_week3.csv")


def _payload_legend(ax, loc="upper left"):
    for p, c in PAYLOAD_COLORS.items():
        ax.scatter([], [], s=14, color=c, label=f"{int(p)} g")
    ax.legend(title="Tải trọng", loc=loc, title_fontsize=8)


# ---------------------------------------------------------------------------

def eda1_distributions(outdir: Path, df: pd.DataFrame) -> None:
    """Phan bo nang luong, thoi gian bay va cong suat trung binh."""
    cols = [("energy_Wh", "Năng lượng tiêu thụ (Wh)"),
            ("duration_s", "Thời gian bay (s)"),
            ("P_mean_W", "Công suất trung bình (W)")]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.4))
    for ax, (col, label) in zip(axes, cols):
        v = df[col]
        ax.hist(v, bins=24, color=C_BLUE, edgecolor=SURFACE, linewidth=0.5, zorder=2)
        ax.axvline(v.median(), color=INK, lw=1, ls="--", zorder=3)
        ax.text(v.median(), ax.get_ylim()[1] * 0.97, f" trung vị {v.median():.1f}",
                fontsize=7, color=INK, va="top")
        ax.set_xlabel(label)
        _despine(ax)
    axes[0].set_ylabel("Số chuyến bay")
    fig.suptitle(f"Phân bố các đại lượng chính (n = {len(df)} chuyến bay)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(outdir / "eda1_phan_bo.png")
    plt.close(fig)


def eda2_energy_by_condition(outdir: Path, df: pd.DataFrame) -> None:
    """Nang luong theo tung yeu to thiet ke thi nghiem: diem + trung vi."""
    factors = [("payload_num", "Tải trọng (g)"),
               ("speed_num", "Tốc độ ra lệnh (m/s)"),
               ("altitude_num", "Độ cao (m)")]
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=True)
    for ax, (col, label) in zip(axes, factors):
        levels = sorted(df[col].unique())
        for i, lv in enumerate(levels):
            v = df.loc[df[col] == lv, "energy_Wh"]
            x = i + rng.uniform(-0.18, 0.18, len(v))
            ax.scatter(x, v, s=6, color=C_BLUE, alpha=0.45, lw=0, zorder=2)
            q1, med, q3 = v.quantile([0.25, 0.5, 0.75])
            ax.plot([i - 0.28, i + 0.28], [med, med], color=INK, lw=1.6, zorder=3)
            ax.plot([i, i], [q1, q3], color=INK, lw=0.8, zorder=3)
        ax.set_xticks(range(len(levels)), [f"{int(lv)}" for lv in levels])
        ax.set_xlabel(label)
        _despine(ax)
    axes[0].set_ylabel("Năng lượng (Wh)")
    fig.suptitle("Năng lượng theo từng yếu tố (vạch đậm: trung vị, vạch đứng: IQR)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(outdir / "eda2_nang_luong_theo_yeu_to.png")
    plt.close(fig)


def eda3_heatmap(outdir: Path, df: pd.DataFrame) -> None:
    """Nang luong trung binh theo toc do x tai trong, va toc do x do cao."""
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 2.8),
                             gridspec_kw={"wspace": 0.35})
    pairs = [("payload_num", "Tải trọng (g)"), ("altitude_num", "Độ cao (m)")]
    vmin, vmax = None, None
    tables = []
    for col, _ in pairs:
        t = df.pivot_table(index=col, columns="speed_num", values="energy_Wh",
                           aggfunc="mean")
        n = df.pivot_table(index=col, columns="speed_num", values="energy_Wh",
                           aggfunc="count")
        tables.append((t, n))
    vmin = min(t.min().min() for t, _ in tables)
    vmax = max(t.max().max() for t, _ in tables)
    for ax, (col, label), (t, n) in zip(axes, pairs, tables):
        im = ax.imshow(t.values, cmap="Blues", vmin=vmin, vmax=vmax, aspect="auto",
                       origin="lower")
        for i in range(t.shape[0]):
            for j in range(t.shape[1]):
                val = t.values[i, j]
                if np.isnan(val):
                    continue
                dark = (val - vmin) / (vmax - vmin) > 0.55
                ax.text(j, i, f"{val:.1f}\n(n={int(n.values[i, j])})", ha="center",
                        va="center", fontsize=6.5, color=SURFACE if dark else INK)
        ax.set_xticks(range(t.shape[1]), [f"{int(c)}" for c in t.columns])
        ax.set_yticks(range(t.shape[0]), [f"{int(r)}" for r in t.index])
        ax.set_xlabel("Tốc độ ra lệnh (m/s)")
        ax.set_ylabel(label)
        for s in ax.spines.values():
            s.set_visible(False)
    cb = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.02)
    cb.set_label("Năng lượng trung bình (Wh)")
    cb.outline.set_visible(False)
    fig.suptitle("Năng lượng trung bình theo tổ hợp điều kiện bay",
                 fontsize=10, x=0.01, ha="left")
    fig.savefig(outdir / "eda3_heatmap_dieu_kien.png")
    plt.close(fig)


def eda4_power_speed(outdir: Path, df: pd.DataFrame) -> None:
    """Cong suat va nang luong tren met theo toc do, tach theo tai trong."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    metrics = [("P_mean_W", "Công suất trung bình (W)"),
               ("energy_per_metre_J", "Năng lượng trên mét (J/m)")]
    for ax, (col, label) in zip(axes, metrics):
        for p, c in PAYLOAD_COLORS.items():
            g = df[df.payload_num == p].groupby("speed_num")[col]
            m, s = g.mean(), g.std()
            ax.fill_between(m.index, m - s, m + s, color=c, alpha=0.12, lw=0)
            ax.plot(m.index, m.values, color=c, lw=1.6, marker="o", ms=3.5,
                    label=f"{int(p)} g")
        ax.set_xlabel("Tốc độ ra lệnh (m/s)")
        ax.set_ylabel(label)
        ax.set_xticks(sorted(df.speed_num.unique()))
        _despine(ax)
    axes[1].legend(title="Tải trọng", title_fontsize=8, loc="upper right", ncol=3)
    fig.suptitle("Công suất và hiệu suất theo tốc độ (đường: trung bình, dải: ±1 độ lệch chuẩn)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(outdir / "eda4_cong_suat_theo_toc_do.png")
    plt.close(fig)


def eda5_energy_drivers(outdir: Path, df: pd.DataFrame) -> None:
    """Nang luong so voi thoi gian bay, cu ly 2D va toc do gio."""
    xs = [("duration_s", "Thời gian bay (s)"),
          ("distance_2d_m", "Cự ly 2D (m)"),
          ("wind_mean_ms", "Tốc độ gió trung bình (m/s)")]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=True)
    for ax, (col, label) in zip(axes, xs):
        for p, c in PAYLOAD_COLORS.items():
            g = df[df.payload_num == p]
            ax.scatter(g[col], g["energy_Wh"], s=8, color=c, alpha=0.7, lw=0, zorder=2)
        r = df[[col, "energy_Wh"]].corr().iloc[0, 1]
        ax.text(0.97, 0.96, f"r = {r:.2f}", transform=ax.transAxes, ha="right",
                va="top", fontsize=8, color=INK,
                bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5))
        ax.set_xlabel(label)
        _despine(ax, grid_axis="both")
    axes[0].set_ylabel("Năng lượng (Wh)")
    _payload_legend(axes[0])
    fig.suptitle("Năng lượng so với các biến giải thích (r: hệ số tương quan Pearson)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(outdir / "eda5_nang_luong_vs_bien.png")
    plt.close(fig)


def eda6_correlation(outdir: Path, df: pd.DataFrame) -> None:
    """Ma tran tuong quan Pearson giua cac bien so cap chuyen bay."""
    cols = {"energy_Wh": "Năng lượng", "duration_s": "Thời gian bay",
            "distance_2d_m": "Cự ly 2D", "payload_num": "Tải trọng",
            "speed_num": "Tốc độ lệnh", "speed_realised_ms": "Tốc độ thực",
            "altitude_num": "Độ cao", "climb_m": "Leo cao",
            "wind_mean_ms": "Gió TB", "P_mean_W": "Công suất TB"}
    c = df[list(cols)].corr()
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    im = ax.imshow(c.values, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(len(c)):
        for j in range(len(c)):
            v = c.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                    color=SURFACE if abs(v) > 0.6 else INK)
    names = list(cols.values())
    ax.set_xticks(range(len(c)), names, rotation=45, ha="right")
    ax.set_yticks(range(len(c)), names)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("Hệ số tương quan Pearson")
    ax.set_title("Ma trận tương quan giữa các biến cấp chuyến bay", loc="left")
    fig.tight_layout()
    fig.savefig(outdir / "eda6_ma_tran_tuong_quan.png")
    plt.close(fig)


def d3_verdicts(outdir: Path) -> None:
    """Ty le FLY / CONDITIONAL / NO_FLY theo SoC, voi 3 muc du phong."""
    g = pd.read_csv(REPORTS / "d3_verdict_grid.csv")
    reserves = sorted(g.reserve_factor.unique())
    fig, axes = plt.subplots(1, len(reserves), figsize=(7.2, 2.6), sharey=True)
    for ax, r in zip(axes, reserves):
        s = g[g.reserve_factor == r].sort_values("soc")
        x = s.soc * 100
        ax.stackplot(x, s.FLY, s.CONDITIONAL, s.NO_FLY,
                     colors=[C_FLY, C_COND, C_NOFLY], alpha=0.9,
                     labels=["FLY", "CONDITIONAL", "NO_FLY"], edgecolor=SURFACE,
                     linewidth=0.4)
        ax.set_title(f"Dự phòng {int(r * 100)}%", loc="left")
        ax.set_xlabel("SoC khi cất cánh (%)")
        ax.set_xlim(x.min(), 60)  # tren 60% khong con thay doi
        ax.set_ylim(0, s.n.max())
        _despine(ax, grid_axis=None)
    axes[0].set_ylabel("Số chuyến bay")
    axes[-1].legend(loc="lower right", fontsize=7)
    fig.suptitle("Phán quyết của bộ quyết định D3 theo mức pin (192 chuyến bay)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(outdir / "d3a_phan_quyet_theo_soc.png")
    plt.close(fig)


def d3_sensitivity(outdir: Path) -> None:
    """SoC toi thieu can de FLY theo SoH va nhiet do (du phong 20%)."""
    s = pd.read_csv(REPORTS / "d3_scenario_sensitivity.csv")
    s = s[s.reserve_factor == 0.2]
    sohs = sorted(s.soh.unique(), reverse=True)
    temps = sorted(s.ambient_temp_c.unique())
    temp_colors = [C_BLUE, C_GREEN, C_ORANGE]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7), sharey=True)
    w = 0.26
    for ax, (col, title) in zip(axes, [("min_soc_trung_vi", "Trung vị"),
                                       ("min_soc_p90", "Phân vị 90")]):
        for k, (t, c) in enumerate(zip(temps, temp_colors)):
            vals = [s[(s.soh == h) & (s.ambient_temp_c == t)][col].iloc[0] * 100
                    for h in sohs]
            xs = np.arange(len(sohs)) + (k - 1) * w
            ax.bar(xs, vals, width=w * 0.92, color=c, label=f"{int(t)} °C", zorder=2)
            for x, v in zip(xs, vals):
                ax.text(x, v + 0.6, f"{v:.0f}", ha="center", fontsize=6.5, color=INK)
        ax.set_xticks(range(len(sohs)), [f"SoH {int(h * 100)}%" for h in sohs])
        ax.set_title(title, loc="left")
        _despine(ax)
    axes[0].set_ylabel("SoC tối thiểu để FLY (%)")
    axes[0].set_ylim(0, 58)
    axes[0].legend(title="Nhiệt độ", title_fontsize=8, loc="upper left", ncol=3)
    fig.suptitle("Mức pin tối thiểu cần để bay theo sức khoẻ pin và nhiệt độ (dự phòng 20%)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(outdir / "d3b_do_nhay_soh_nhiet_do.png")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path, default=REPORTS / "figures" / "eda")
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    setup_style()
    df = _flights()
    eda1_distributions(args.outdir, df)
    eda2_energy_by_condition(args.outdir, df)
    eda3_heatmap(args.outdir, df)
    eda4_power_speed(args.outdir, df)
    eda5_energy_drivers(args.outdir, df)
    eda6_correlation(args.outdir, df)
    d3_verdicts(args.outdir)
    d3_sensitivity(args.outdir)
    print(f"Da ghi hinh vao {args.outdir}")


if __name__ == "__main__":
    main()
