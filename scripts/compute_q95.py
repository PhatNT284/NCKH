"""
Tinh khoan du phong bat dinh cho nhan tham chieu REF-1 — dong OI-D4-3.

    python3 scripts/compute_q95.py

In ra con so de DIEN TAY vao configs/d4_protocol.yaml muc
`reference_label.frozen_numbers`. Co y khong tu ghi vao file giao thuc: mot con
so dong bang phai do nguoi dien va biet minh dang dien gi.

-----------------------------------------------------------------------------
DAU CUA PHAN DU — tra tu ma nguon, khong doan
-----------------------------------------------------------------------------
src/evaluation_energy.py:

    residuals[name] = (oof_sum / np.maximum(oof_cnt, 1)) - y

Tuc PHAN DU = DU BAO - DO DUOC. Nen:

    phan du DUONG  ->  mo hinh doan THUA  ->  huong AN TOAN
    phan du AM     ->  mo hinh doan THIEU ->  huong NGUY HIEM

(Ban dau file nay ghi nguoc dau. Da sua sau khi doc ma nguon.)

P§4.9: "Signed error is reported separately because systematic underprediction
is the direction that produces unsafe approvals."

Nen khoan du phong phai phu DUOI dai phan du — tuc phan vi 5 cua phan du co
dau, lay do lon. KHONG phai phan vi 95.

-----------------------------------------------------------------------------
§6/E3 cam: "never estimate the allowance from the final test fold."
d2_oof_residuals.csv la phan du OUT-OF-FOLD. Dung nguon.
-----------------------------------------------------------------------------
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
NGUON = REPO_ROOT / "reports" / "d2_oof_residuals.csv"

# Mo hinh da chot o san pham D2 — cung la ten COT trong file dang rong
MO_HINH = "D2_ridge_preflight"

# Con so d3_protocol.yaml dang dung cho nguong R_fly (quyet dinh B4)
B4_ALLOWANCE = 1.4687


def main() -> None:
    if not NGUON.exists():
        raise SystemExit(
            f"Khong tim thay {NGUON}.\n"
            "Chay `python3 -m src.evaluation_energy` truoc.")

    df = pd.read_csv(NGUON)
    print(f"Doc {NGUON.relative_to(REPO_ROOT)} — {len(df)} dong")

    # File o dang RONG: moi mo hinh mot cot, gia tri la phan du out-of-fold.
    if MO_HINH not in df.columns:
        raise SystemExit(
            f"Khong co cot `{MO_HINH}`. Cot co: {list(df.columns)}\n"
            "Doi bien MO_HINH trong script nay cho dung, dung doan.")

    r = df[MO_HINH].astype(float).dropna()
    print(f"Cot `{MO_HINH}` — {len(r)} gia tri\n")

    print("PHAN BO PHAN DU  (= du bao - do duoc)")
    print(f"  trung binh (bias) : {r.mean():+.4f} Wh")
    print(f"  trung vi          : {r.median():+.4f} Wh")
    print(f"  do lech chuan     : {r.std():.4f} Wh")
    print(f"  nho nhat          : {r.min():+.4f} Wh   (doan thieu nhieu nhat)")
    print(f"  lon nhat          : {r.max():+.4f} Wh   (doan thua nhieu nhat)")

    am = int((r < 0).sum())
    print(f"\n  doan THIEU (am)   : {am}/{len(r)} = {am / len(r):.1%}"
          f"   <- huong nguy hiem")
    print(f"  doan THUA (duong) : {len(r) - am}/{len(r)}"
          f"   <- huong an toan")

    q05 = float(np.percentile(r, 5))
    q95 = float(np.percentile(r, 95))
    q95_abs = float(np.percentile(r.abs(), 95))
    allowance = abs(q05)

    print("\n" + "=" * 66)
    print("BA THONG KE — DO BA THU KHAC NHAU")
    print("=" * 66)
    print(f"  q05 phan du co dau   : {q05:+.4f} Wh"
          f"   -> do lon {allowance:.4f}")
    print(f"     95 % so chuyen mo hinh doan thieu KHONG QUA {allowance:.4f} Wh")
    print(f"  q95 phan du co dau   : {q95:+.4f} Wh")
    print(f"     doi chieu phia an toan — KHONG dung lam khoan du phong")
    print(f"  q95 |phan du|        :  {q95_abs:.4f} Wh")
    print(f"     tron ca hai huong; day la con so B4 cua D3 dang dung")

    print("\n" + "=" * 66)
    print(f"KHOAN DU PHONG CHO REF-1 : {allowance:.4f} Wh")
    print("=" * 66)
    print("  Lay |q05| chu khong lay q95(|phan du|). Hai ly do:")
    print("  1. P§4.9 — chi huong doan THIEU moi gay duyet bay nguy hiem.")
    print("     Tri tuyet doi tron ca huong an toan vao, cho mot con so")
    print("     khong noi len dieu gi ve an toan.")
    print("  2. Nhan tham chieu KHONG duoc dung chung con so voi nguong cua")
    print("     he thong dang bi cham diem. Dung chung thi neu con so sai, ca")
    print("     dap an va he thong sai cung mot huong — va loi bien mat.")

    lech = q95_abs - allowance
    print(f"\n  Lech so voi B4 cua D3 : {lech:+.4f} Wh "
          f"({lech / allowance:+.1%})")
    if abs(q95_abs - B4_ALLOWANCE) < 1e-3:
        print(f"  q95|phan du| = {q95_abs:.4f} KHOP con so B4 da dong bang "
              f"({B4_ALLOWANCE}).")
        print("  => d3_protocol.yaml dung tri tuyet doi. Khong co mau thuan,")
        print("     chi la hai cho chon hai thong ke khac nhau CO Y THUC.")
    else:
        print(f"  CHU Y: q95|phan du| = {q95_abs:.4f} KHONG khop con so B4 "
              f"da dong bang ({B4_ALLOWANCE}).")
        print("  Phai giai thich duoc truoc khi dien — co the hai cho loc")
        print("  mo hinh khac nhau, hoac file phan du da bi sinh lai.")

    print("\n" + "-" * 66)
    print("DIEN VAO configs/d4_protocol.yaml:")
    print("-" * 66)
    print("  reference_label:")
    print("    frozen_numbers:")
    print(f"      uncertainty_allowance_Wh: {allowance:.4f}")
    print(f"      source_statistic: \"abs(q05) cua phan du co dau\"")
    print(f"      q05_signed_Wh: {q05:.4f}")
    print(f"      q95_abs_for_reference_Wh: {q95_abs:.4f}")
    print(f"      computed_on: \"<ngay hom nay>\"")
    print("      computed_from: \"reports/d2_oof_residuals.csv\"")
    print(f"      model_column: \"{MO_HINH}\"")
    print("\nSau khi dien: doi OI-D4-3 sang DONG, va KHONG sua con so nua.")


if __name__ == "__main__":
    main()
