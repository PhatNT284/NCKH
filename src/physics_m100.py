"""
Mo hinh vat ly D5 — tham so hoa cho DJI Matrice 100 (§5.2 D5, §3.2).

Thay yeu cau o §5.2: chi trien khai mo hinh cong suat vat ly sau khi ghi nhan
day du moi tham so va xac nhan viec tham so hoa phu hop voi M100. Thieu tham so
thi KHONG duoc bia.

Script nay lam hai viec:
  1. Tap hop moi tham so M100 lay duoc tu nguon cong bo, ghi ro nguon
  2. Khop he so hieu suat eta tu thoi luong bay treo nha san xuat cong bo, roi
     KIEM CHEO voi cac tri so khong dung de khop

    python3 -m src.physics_m100

Nguon tham so: trang ho tro chinh thuc DJI cho Matrice 100
https://www.dji.com/global/support/product/matrice100
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# THAM SO — moi dong phai co nguon. Khong bia (§5.2 D5).
# ---------------------------------------------------------------------------

RHO_AIR = 1.225          # kg/m3, khi quyen chuan muc nuoc bien, 15 C
G = 9.81                 # m/s2

M100 = {
    "n_rotors": 4,                      # DJI — quadrotor
    "propeller": "DJI 1345s",           # DJI
    "prop_diameter_in": 13.0,           # tu ma 1345s: 13 inch duong kinh, 4.5 inch buoc
    "motor": "DJI 3510",                # DJI
    "motor_kv": None,                   # DJI KHONG cong bo
    "max_takeoff_g": 3600,              # DJI
}

# CANH BAO VE PHAM VI AP DUNG
# ---------------------------
# Cac khoi luong duoi day la cua M100 NGUYEN BAN theo DJI. May bay trong bo du
# lieu CMU da duoc lap them thiet bi do (cam bien gio 136 g + may tinh tren
# khoang 1113 g), khoi luong cat canh thuc te 3680-4180 g — VUOT MTOW 3600 g.
# He so eta khop duoi day chi hop le tren dai 2431-3431 g (dai DJI cong bo thoi
# luong bay treo). Ap mo hinh len cac chuyen bay thuc te la NGOAI SUY.
# Chi tiet: reports/parameter_table.md muc 3.1
#
# Hai cau hinh pin. Bai Rodrigues TU MAU THUAN ve loai pin (xem OI-2):
#   Methods>Airframe:   4500 mAh, 22 phut, pin 600 g  -> TB47D
#   Methods>Safety:     "LiPo DJI TB48D batteries"    -> TB48D
# Nhom chot TB47D (99.9 Wh) lam gia tri chinh vi da so bang chung va vi no la
# huong bao thu. Chi tiet: reports/parameter_table.md muc 1.1
BATTERIES = {
    "TB47D": {
        "energy_Wh": 99.9,              # DJI — 4500 mAh, 22.2 V
        "aircraft_mass_g": 2355,        # DJI — khoi luong may bay KEM pin nay
        "hover_min": {0: 22, 500: 17, 1000: 13},   # DJI, theo tai trong (g)
    },
    "TB48D": {
        "energy_Wh": 129.96,            # DJI — 5700 mAh, 22.2 V
        "aircraft_mass_g": 2431,        # DJI
        "hover_min": {0: 28, 500: 20, 1000: 16},
    },
}

# Tham so KHONG lay duoc tu nguon cong bo — can cho mo hinh Gong day du
MISSING = {
    "blade_chord_m": "chieu rong canh quat — DJI khong cong bo",
    "solidity_ratio": "ti so dac — can chieu rong canh va so canh moi canh quat",
    "blade_drag_coefficient": "he so can canh quat — can do trong ham gio",
    "fuselage_drag_area_m2": "dien tich can than may bay — can do trong ham gio",
    "motor_kv": "DJI khong cong bo",
}


# ---------------------------------------------------------------------------
# Ly thuyet dong luong — cong suat cam ung khi bay treo
# ---------------------------------------------------------------------------

def disk_area_m2() -> float:
    """Tong dien tich dia quay cua tat ca canh quat."""
    r = M100["prop_diameter_in"] * 0.0254 / 2
    return M100["n_rotors"] * np.pi * r**2


def ideal_hover_power_W(mass_kg: float, area_m2: float | None = None) -> float:
    """
    Cong suat KHI DONG ly tuong khi bay treo, theo ly thuyet dong luong:

        P = T^1.5 / sqrt(2 * rho * A)        voi T = m * g

    Day la can duoi ly thuyet — cong suat DIEN thuc te cao hon nhieu vi co ton
    hao canh quat, dong co, bo dieu toc va mach dien. Phan chenh lech do nam
    trong he so eta (xem `fit_efficiency`).
    """
    area = area_m2 if area_m2 is not None else disk_area_m2()
    thrust_N = mass_kg * G
    return float(thrust_N**1.5 / np.sqrt(2 * RHO_AIR * area))


def fit_efficiency(battery: str) -> float:
    """
    Khop he so hieu suat eta tu DUNG MOT diem: thoi luong bay treo khong tai.

        eta = P_ly_tuong / P_dien_cong_bo

    Chi dung mot diem de khop, de cac tri so con lai (tai 500 g va 1000 g) van
    la kiem chung doc lap. Day la cach Proposal muc 4.2 da lam cho M210.
    """
    b = BATTERIES[battery]
    mass_kg = b["aircraft_mass_g"] / 1000
    p_ideal = ideal_hover_power_W(mass_kg)
    p_electrical = b["energy_Wh"] / (b["hover_min"][0] / 60)
    return p_ideal / p_electrical


def predict_hover_minutes(battery: str, payload_g: float, eta: float) -> float:
    """Du bao thoi luong bay treo voi tai trong cho truoc."""
    b = BATTERIES[battery]
    mass_kg = (b["aircraft_mass_g"] + payload_g) / 1000
    p_electrical = ideal_hover_power_W(mass_kg) / eta
    return b["energy_Wh"] / p_electrical * 60


def validation_table() -> pd.DataFrame:
    """Doi chieu du bao voi moi tri so thoi luong bay treo DJI cong bo."""
    rows = []
    for name, b in BATTERIES.items():
        eta = fit_efficiency(name)
        for payload, published in b["hover_min"].items():
            pred = predict_hover_minutes(name, payload, eta)
            rows.append({
                "pin": name,
                "tai_trong_g": payload,
                "eta_khop": round(eta, 4),
                "du_bao_phut": round(pred, 2),
                "cong_bo_phut": published,
                "lech_pct": round(abs(pred - published) / published * 100, 2),
                "dung_de_khop": payload == 0,
            })
    return pd.DataFrame(rows)


def max_payload_g(battery: str) -> int:
    """Tai trong toi da = khoi luong cat canh toi da tru khoi luong may bay."""
    return M100["max_takeoff_g"] - BATTERIES[battery]["aircraft_mass_g"]


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="D5 — tham so hoa mo hinh vat ly M100")
    ap.add_argument("--outdir", default="reports")
    args = ap.parse_args()

    area = disk_area_m2()
    r = M100["prop_diameter_in"] * 0.0254 / 2

    print("=" * 74)
    print("THAM SO HINH HOC — nguon: trang ho tro chinh thuc DJI")
    print("=" * 74)
    print(f"  canh quat                {M100['propeller']} ({M100['prop_diameter_in']}\")")
    print(f"  ban kinh canh quat       {r:.4f} m")
    print(f"  so canh quat             {M100['n_rotors']}")
    print(f"  tong dien tich dia       {area:.5f} m2")
    print(f"  dong co                  {M100['motor']}  (KV khong cong bo)")
    print(f"  khoi luong cat canh toi da {M100['max_takeoff_g']} g")

    print()
    print("=" * 74)
    print("TAI TRONG TOI DA THEO CAU HINH PIN")
    print("=" * 74)
    for name in BATTERIES:
        print(f"  {name}: {M100['max_takeoff_g']} - "
              f"{BATTERIES[name]['aircraft_mass_g']} = {max_payload_g(name)} g")
    print("  (bo du lieu CMU chi bay toi 500 g — nam gon trong gioi han)")

    print()
    print("=" * 74)
    print("KHOP HE SO HIEU SUAT VA KIEM CHEO")
    print("=" * 74)
    table = validation_table()
    print(f"{'pin':<8}{'tai (g)':>9}{'eta':>9}{'du bao':>9}{'cong bo':>9}"
          f"{'lech':>8}   ghi chu")
    print("-" * 74)
    for _, r_ in table.iterrows():
        note = "dung de khop" if r_["dung_de_khop"] else "KIEM CHEO doc lap"
        print(f"{r_['pin']:<8}{r_['tai_trong_g']:>9.0f}{r_['eta_khop']:>9.4f}"
              f"{r_['du_bao_phut']:>9.2f}{r_['cong_bo_phut']:>9.0f}"
              f"{r_['lech_pct']:>7.1f}%   {note}")

    ind = table[~table["dung_de_khop"]]
    print()
    print(f"  Sai lech tren {len(ind)} tri so KHONG dung de khop: "
          f"trung binh {ind['lech_pct'].mean():.1f} %, "
          f"lon nhat {ind['lech_pct'].max():.1f} %")
    print(f"  eta khop duoc cho hai cau hinh pin: "
          f"{table['eta_khop'].min():.4f} va {table['eta_khop'].max():.4f} "
          f"— chenh {abs(table['eta_khop'].max()/table['eta_khop'].min()-1)*100:.1f} %")

    print()
    print("=" * 74)
    print("THAM SO KHONG LAY DUOC — khong duoc bia (§5.2 D5)")
    print("=" * 74)
    for k, v in MISSING.items():
        print(f"  {k:<28} {v}")

    print()
    print("KET LUAN: xem docs/cach_lam/D5_mo_hinh_vat_ly.md")

    outdir = REPO_ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    table.to_csv(outdir / "d5_hover_validation.csv", index=False)
    print(f"Da ghi {outdir}/d5_hover_validation.csv")


if __name__ == "__main__":
    main()
