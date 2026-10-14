"""
Nang luong kha dung cua pin — khoi (a) cua san pham D3.

    E_available = E_nominal * SoC * SoH * kappa(T)        (§5.4, Eq (2))

Module nay chi tra loi MOT cau: pin thuc su cho ta bao nhieu Wh. No KHONG biet
gi ve chuyen bay, khong biet gi ve luat cung, khong ra phan quyet. Viec do thuoc
src/decision_rules.py va src/safety_invariants.py.

Moi con so deu doc tu configs/d3_protocol.yaml — khong viet cung trong ma nguon.
Doi tham so thi sua giao thuc, khong sua file nay.

Hai diem quan trong:

1. kappa(T) kep MOT PHIA (quyet dinh B3). Duoi 4.5 C giu o gia tri bien lanh
   poly(4.5) = 0.9203, KHONG cho ve 1.0. Quy tac cu (kappa = 1 ngoai moi dai)
   sai o phia lanh: tai 4.4 C no nhay tu 0.920 len 1.000, tuc cang lanh cang
   gia dinh pin cang khoe -> E_available tinh THUA -> cho bay chuyen khong du pin.

2. Module FAIL CLOSED (§4.6). Thieu dau vao -> status MISSING_INPUT.
   Ngoai dai -> status OUT_OF_RANGE. KHONG BAO GIO tu dien gia tri mac dinh.

    python3 -m src.available_energy --demo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Trang thai tra ve — src/decision_rules.py se anh xa sang phan quyet:
#   OK            -> tinh tiep binh thuong
#   MISSING_INPUT -> INSUFFICIENT_DATA
#   OUT_OF_RANGE  -> NO_FLY
STATUS_OK = "OK"
STATUS_MISSING = "MISSING_INPUT"
STATUS_OUT_OF_RANGE = "OUT_OF_RANGE"

# Che do nhiet do, de bao cao va de ve hinh
REGIME_BELOW = "below_calibration"     # T < 4.5 C   — giu o bien lanh
REGIME_IN = "in_calibration"           # 4.5-18.4 C  — dung da thuc
REGIME_ABOVE = "above_calibration"     # T > 18.4 C  — chan tren bang 1


def load_protocol() -> dict:
    with open(REPO_ROOT / "configs" / "d3_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# He so nhiet do
# ---------------------------------------------------------------------------

def _poly(t_c: float) -> float:
    """Da thuc bac hai cua Kim et al. Khong chan, khong kep — xem kappa()."""
    return 0.8814 + 0.0091 * t_c - 0.0001 * t_c**2


def kappa(t_c: float, protocol: dict | None = None) -> tuple[float, str]:
    """
    He so suy giam dung luong theo nhiet do (quyet dinh B3).

    Tra ve (gia_tri_kappa, che_do). Che do de bao cao biet con so den tu nhanh
    nao — trong bai phai noi ro bao nhieu chuyen roi ra ngoai dai hieu chinh.

        T < 4.5      -> poly(4.5) = 0.9203    giu o bien lanh
        4.5..18.4    -> min(1, poly(T))       trong dai hieu chinh cua Kim
        T > 18.4     -> 1.0                   chan tren

    Vi sao chan tren bang 1: da thuc goc tra ve > 1 trong khoang ~15.8-75.2 C,
    dat 1.089 tai 45.5 C — tuc khang dinh pin chua nhieu nang luong hon muc
    danh dinh cua chinh no. Vo ly ve vat ly.

    Vi sao KHONG cho ve 1 o phia lanh: xem docstring dau file.
    """
    protocol = protocol or load_protocol()
    lo, hi = protocol["available_energy"]["kappa_temperature"]["calibrated_range_c"]

    if t_c < lo:
        return _poly(lo), REGIME_BELOW
    if t_c > hi:
        return 1.0, REGIME_ABOVE
    return min(1.0, _poly(t_c)), REGIME_IN


# ---------------------------------------------------------------------------
# Ket qua
# ---------------------------------------------------------------------------

@dataclass
class AvailableEnergy:
    """
    Ket qua mot lan tinh nang luong kha dung.

    `status` khac OK thi `value_Wh` la None — KHONG co gia tri du phong. Day la
    nguyen tac fail closed cua §4.6: thieu du lieu thi noi thieu du lieu, khong
    tu dien roi chay tiep.
    """
    status: str
    value_Wh: float | None = None
    e_nominal_Wh: float | None = None
    soc: float | None = None
    soh: float | None = None
    temp_c: float | None = None
    kappa: float | None = None
    temp_regime: str | None = None
    battery_type: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    def __str__(self) -> str:
        if not self.ok:
            return f"{self.status}: {'; '.join(self.reasons)}"
        return (f"{self.value_Wh:.2f} Wh "
                f"({self.e_nominal_Wh:.1f} x SoC {self.soc:.2f} "
                f"x SoH {self.soh:.2f} x kappa {self.kappa:.4f})")


# ---------------------------------------------------------------------------
# Tinh nang luong kha dung
# ---------------------------------------------------------------------------

def available_energy(soc: float | None,
                     soh: float | None,
                     temp_c: float | None,
                     battery_type: str = "TB47D",
                     protocol: dict | None = None) -> AvailableEnergy:
    """
    E_available = E_nominal * SoC * SoH * kappa(T)        (§5.4, Eq (2))

    Quy uoc SoC x SoH (P§4.4 — de sai, phai viet ro trong bai):

        SoC * SoH = Q(t)/Q_tot,t * Q_tot,t/Q_tot,i = Q(t)/Q_tot,i

    tuc DIEN TICH HIEN CO so voi DUNG LUONG LUC PIN CON MOI. Ghep nham cap se
    dem dung luong hien tai hai lan.

    Tham so
    -------
    soc, soh : 0..1. `None` nghia la THIEU, khong phai 0.
    temp_c   : nhiet do moi truong, °C. `None` nghia la THIEU.
    battery_type : "TB47D" (99.9 Wh, mac dinh bao thu) hoac "TB48D" (129.96 Wh).
                   Chay lai toan bo voi TB48D la phan tich do nhay BAT BUOC o
                   san pham D4 (§8 muc 3).
    """
    protocol = protocol or load_protocol()
    cfg = protocol["available_energy"]
    rules = protocol["hard_rules"]

    reasons: list[str] = []

    # --- 1. Thieu dau vao -> INSUFFICIENT_DATA (§4.6) -----------------------
    for name, value in (("SoC", soc), ("SoH", soh), ("nhiet do", temp_c)):
        if value is None:
            reasons.append(f"thieu {name}")
    if reasons:
        return AvailableEnergy(status=STATUS_MISSING, reasons=reasons,
                               battery_type=battery_type)

    # --- 2. Ngoai dai -> NO_FLY -------------------------------------------
    for name, value in (("SoC", soc), ("SoH", soh)):
        if not 0.0 <= value <= 1.0:
            reasons.append(f"{name} = {value} ngoai dai [0, 1]")

    # Nhiet do ngoai dai van hanh cua nha san xuat la vi pham luat cung HR-2.
    # Kiem ca o day de module nay khong bao gio tra ve mot con so cho mot nhiet
    # do ma may bay khong duoc phep hoat dong.
    t_lo, t_hi = _operating_temp_range(rules)
    if not t_lo <= temp_c <= t_hi:
        reasons.append(f"nhiet do {temp_c} C ngoai dai van hanh "
                       f"[{t_lo}, {t_hi}] (HR-2)")

    if reasons:
        return AvailableEnergy(status=STATUS_OUT_OF_RANGE, reasons=reasons,
                               temp_c=temp_c, soc=soc, soh=soh,
                               battery_type=battery_type)

    # --- 3. Tinh ------------------------------------------------------------
    e_nominal = _e_nominal(battery_type, cfg)
    k, regime = kappa(temp_c, protocol)
    value = e_nominal * soc * soh * k

    notes: list[str] = []
    if regime == REGIME_BELOW:
        notes.append("nhiet do duoi dai hieu chinh cua Kim (4.5 C); "
                     "kappa giu o gia tri bien lanh, khong ngoai suy")
    elif regime == REGIME_ABOVE:
        notes.append("nhiet do tren dai hieu chinh cua Kim (18.4 C); "
                     "kappa chan tren bang 1")

    return AvailableEnergy(
        status=STATUS_OK, value_Wh=value, e_nominal_Wh=e_nominal,
        soc=soc, soh=soh, temp_c=temp_c, kappa=k, temp_regime=regime,
        battery_type=battery_type, reasons=notes,
    )


def _e_nominal(battery_type: str, cfg: dict) -> float:
    """Nang luong danh dinh theo loai pin. Mac dinh TB47D — huong bao thu."""
    table = {
        "TB47D": float(cfg["e_nominal"]["primary_Wh"]),
        "TB48D": float(cfg["e_nominal"]["sensitivity_Wh"]),
    }
    if battery_type not in table:
        raise ValueError(f"loai pin khong biet: {battery_type!r}; "
                         f"chi nhan {sorted(table)}")
    return table[battery_type]


def _operating_temp_range(rules: dict) -> tuple[float, float]:
    """Doc dai nhiet do van hanh tu luat cung HR-2, khong viet cung."""
    for rule in rules["manufacturer"]:
        if rule["id"] == "HR-2":
            # "-10 <= ambient_temp_c <= 40"
            parts = rule["check"].split("<=")
            return float(parts[0].strip()), float(parts[-1].strip())
    raise KeyError("khong tim thay luat HR-2 trong giao thuc")


# ---------------------------------------------------------------------------
# Chay thu — in bang de dua vao bao cao
# ---------------------------------------------------------------------------

def _demo() -> None:
    protocol = load_protocol()
    lo, hi = protocol["available_energy"]["kappa_temperature"]["calibrated_range_c"]

    print("kappa(T) — quyet dinh B3\n")
    print(f"{'T (C)':>7} {'kappa':>8} {'da thuc':>9}  che do")
    print("-" * 46)
    for t in (-10, -5, 0, 4.4, 4.5, 10, 15, 18.4, 18.5, 25, 40):
        k, regime = kappa(t, protocol)
        mark = "" if lo <= t <= hi else "  *"
        print(f"{t:>7} {k:>8.4f} {_poly(t):>9.4f}  {regime}{mark}")
    print("\n* ngoai dai hieu chinh cua Kim "
          f"({lo}-{hi} C) — gia tri giu o bien, khong ngoai suy")

    print("\n\nE_available theo SoC, pin TB47D, SoH = 1.0, T = 15 C\n")
    print(f"{'SoC':>6} {'E_available (Wh)':>18}")
    print("-" * 26)
    for soc in (0.2, 0.4, 0.6, 0.8, 1.0):
        print(f"{soc:>6.1f} {available_energy(soc, 1.0, 15).value_Wh:>18.2f}")

    print("\n\nFail closed (§4.6)\n")
    for label, args in (
        ("thieu SoC",        (None, 1.0, 15)),
        ("thieu nhiet do",   (0.8, 1.0, None)),
        ("SoC ngoai dai",    (1.5, 1.0, 15)),
        ("nhiet do -40 C",   (0.8, 1.0, -40)),
    ):
        print(f"  {label:<18} -> {available_energy(*args)}")

    print("\n\nDo nhay loai pin (OI-2), SoC 0.8 / SoH 0.9 / 15 C\n")
    for bt in ("TB47D", "TB48D"):
        r = available_energy(0.8, 0.9, 15, battery_type=bt)
        print(f"  {bt}  {r.value_Wh:>7.2f} Wh")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true",
                    help="in bang kappa(T) va vi du fail closed")
    args = ap.parse_args()
    if args.demo:
        _demo()
    else:
        ap.print_help()
