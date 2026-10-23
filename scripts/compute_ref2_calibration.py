"""
Tinh he so hieu chinh cho nhan tham chieu REF-2 — dong OI-D4-5.

    python3 scripts/compute_ref2_calibration.py

In ra con so de DIEN TAY vao configs/d4_protocol.yaml muc
`reference_label.sensitivity_method.frozen_numbers`.

-----------------------------------------------------------------------------
VI SAO CAN HE SO NAY
-----------------------------------------------------------------------------
Ban 1.0.0-1.0.7 dinh nghia REF-2 la

    E_ref2 = P_hover(khoi luong) / eta * t_ke_hoach / 3600 * (1 + 0.034)

Chay thu tren 18000 kich ban thi REF-2 doi NHU CAU trung vi 7.56 Wh, trong khi
REF-1 doi 23.65 Wh va nang luong DO DUOC THAT cua 192 chuyen la 20.79 Wh. Tuc
REF-2 doi it hon muc do duoc 2.7 LAN, va thap hon REF-1 o 98 % kich ban.

Ma §6/E3 giao cho REF-2 dung mot viec: "add a sensitivity analysis with a
distinct CONSERVATIVE reference assumption." REF-2 nhu cu KHONG bao thu — no
lac quan nhat trong ca he thong, nen khong lam duoc viec do.

Nguyen nhan: cong thuc P_hover * (cu ly / toc do) bo qua nang luong LEO
25-100 m, HA, va TREO. Thoi gian thuc cua chuyen bay dai hon cu ly/toc do, va
cong suat bay hanh trinh cao hon cong suat treo ly tuong.

-----------------------------------------------------------------------------
CACH SUA — HIEU CHINH BANG TI SO DO DUOC
-----------------------------------------------------------------------------
    k = p95( E_do_duoc / (P_ideal(khoi luong) * t_ke_hoach / 3600) )

tren 192 chuyen that. Roi

    E_ref2 = k * P_ideal(khoi luong) * t_ke_hoach / 3600

HAI DIEU DANG CHU Y:

1. `eta` TRIET TIEU. k ti le thuan voi eta, con uoc luong ti le nghich, nen
   E_ref2 khong con phu thuoc he so hieu suat khop duoc. REF-2 gio chi dua vao
   (a) cong suat treo ly tuong — dang dong, suy tu khoi luong va dien tich dia,
   khong co tham so khop nao, va (b) MOT so vo huong do duoc.

2. VAN DOC LAP VOI MO HINH D2. §6/E3 doi "independent of the candidate model".
   k rut tu nang luong DO DUOC, khong phai tu dau ra hoi quy. Khong he so hoi
   quy nao di vao REF-2.

   Khac han `safety_k = 1.25` cua ban 1.0.0: con so do khong do tu gi ca, va da
   bi bo o quyet dinh C12.

Lay p95 chu khong p50: nhan tham chieu phai BAO THU, tuc tha doi THUA nang
luong hon la doi THIEU. Doi thieu thi nhan goi mot kich ban la kha thi trong
khi thuc te khong — tuc dap an sai theo huong nguy hiem.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# File nay chay nhu MOT FILE (`python3 scripts/...`), khong phai mot module, nen
# goc repo khong nam tren sys.path va `import src` se that bai. Chen vao truoc
# khi import — cung khuon voi scripts/diagnose_distance.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.physics_m100 import ideal_hover_power_W                  # noqa: E402
from src.reference_labeller import (                              # noqa: E402
    _doc_bang_chuyen_bay, load_d3_protocol,
)
from src.safety_invariants import PROFILE_CMU, takeoff_mass_g     # noqa: E402

PHAN_VI = 95


def main() -> None:
    can = ["energy_Wh", "payload_num", "duration_planned_s",
           "distance_2d_m", "speed_num"]
    df, nguon = _doc_bang_chuyen_bay(can)
    print(f"Doc {nguon.relative_to(REPO_ROOT)} — {len(df)} chuyen\n")

    profiles = load_d3_protocol()["aircraft_profiles"]
    khung_g = takeoff_mass_g(0.0, "TB47D", PROFILE_CMU, profiles)
    print(f"Khoi luong khung (ho so {PROFILE_CMU}): {khung_g:.0f} g")

    mass_kg = (khung_g + df["payload_num"].to_numpy(float)) / 1000.0
    t_s = df["duration_planned_s"].to_numpy(float)
    p_ideal = np.array([ideal_hover_power_W(m) for m in mass_kg])
    uoc_luong = p_ideal * t_s / 3600.0

    do_duoc = df["energy_Wh"].to_numpy(float)
    k = do_duoc / uoc_luong

    print(f"\nUOC LUONG THO  (P_ideal x t/3600, KHONG co eta)")
    print(f"  trung vi {np.median(uoc_luong):6.2f} Wh")
    print(f"NANG LUONG DO DUOC")
    print(f"  trung vi {np.median(do_duoc):6.2f} Wh")

    print(f"\nTI SO k = do duoc / uoc luong tho")
    for q in (50, 75, 90, 95, 99):
        dau = "  <-- DUNG SO NAY" if q == PHAN_VI else ""
        print(f"  p{q:<3} {np.percentile(k, q):8.4f}{dau}")
    print(f"  min  {k.min():8.4f}")
    print(f"  max  {k.max():8.4f}")

    k95 = float(np.percentile(k, PHAN_VI))
    ref2 = uoc_luong * k95
    thieu = int((ref2 < do_duoc).sum())

    print(f"\n{'=' * 66}")
    print(f"HE SO HIEU CHINH REF-2 : {k95:.4f}   (phan vi {PHAN_VI})")
    print(f"{'=' * 66}")
    print(f"  REF-2 tren 192 chuyen that: trung vi {np.median(ref2):.2f} Wh")
    print(f"  Nang luong do duoc        : trung vi {np.median(do_duoc):.2f} Wh")
    print(f"  => REF-2 doi THUA {np.median(ref2) / np.median(do_duoc) - 1:+.0%} "
          f"so voi muc do duoc — DUNG huong bao thu")
    print(f"  So chuyen REF-2 doi THIEU hon do duoc: {thieu}/{len(df)} "
          f"({thieu / len(df):.0%})")
    print(f"     (phan vi {PHAN_VI} nen ky vong khoang "
          f"{100 - PHAN_VI} % — khop thi dung)")

    print("\n" + "-" * 66)
    print("DIEN VAO configs/d4_protocol.yaml:")
    print("-" * 66)
    print("  reference_label:")
    print("    sensitivity_method:")
    print("      frozen_numbers:")
    print(f"        calibration_k: {k95:.4f}")
    print(f"        percentile: {PHAN_VI}")
    print(f"        n_flights: {len(df)}")
    print(f"        computed_on: \"<ngay hom nay>\"")
    print(f"        computed_from: \"{nguon.relative_to(REPO_ROOT)}\"")
    print("\nSau khi dien: nho Duy KY LAI muc sensitivity_method (OI-D4-5),")
    print("roi chay lai `python3 -m src.reference_labeller`.")


if __name__ == "__main__":
    main()
