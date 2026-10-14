"""
Lop luat cung — khoi (d) cua san pham D3.

Nguyen van §4.6: "A layer of hard constraints is applied independently of the
model and can only lower a verdict; no score, no model output and no human
approval may convert a hard-rule violation into FLY."

Vi vay module nay:
    - KHONG nhan vao bat ky dau ra nao cua mo hinh
    - KHONG nhan vao bien du tru
    - KHONG biet gi ve nang luong
No chi nhin ke hoach bay va moi truong, roi tra ve danh sach luat da kiem.
Viec ghep voi bien du tru thuoc src/decision_rules.py.

HAI MUC DO VI PHAM (giao thuc muc 4, quyet dinh B6):

    VETO       luat nha san xuat (HR-*) — vi pham thi NO_FLY, khong gi lat duoc
    DOWNGRADE  gioi han nhom rut ra tu thi nghiem (PD-*) — van bay duoc nhung
               KHONG duoc tra FLY; cao nhat la CONDITIONAL kem nhan EXTRAPOLATED

Tach hai muc vi hai nguon goc khac nhau. Gioi han nha san xuat la rang buoc vat
ly va chung nhan. Gioi han PD-* la GIOI HAN HIEU LUC CUA MO HINH — ngoai do mo
hinh van cho so, chi la so khong dang tin, nen he thong phai noi ro thay vi chan.

HAI HO SO MAY BAY (quyet dinh B6):

    M100_stock         khung 2355 g — ho so VAN HANH, HR-3 veto binh thuong
    CMU_instrumented   khung 3680 g — may bay that trong bo du lieu, da mang
                       1249 g thiet bi do. Vuot MTOW o MOI cau hinh, nen HR-3
                       bao KNOWN_EXCEEDED thay vi veto; neu veto thi 192/192
                       chuyen NO_FLY va benchmark vo nghia.

    python3 -m src.safety_invariants --demo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ket qua kiem mot luat
PASS = "PASS"
VIOLATED = "VIOLATED"               # vi pham
KNOWN_EXCEEDED = "KNOWN_EXCEEDED"   # vuot nhung da biet va da khai bao (B6)
MISSING = "MISSING"                 # thieu dau vao de kiem

# Muc do
VETO = "VETO"
DOWNGRADE = "DOWNGRADE"
RECORD_ONLY = "RECORD_ONLY"

PROFILE_STOCK = "M100_stock"
PROFILE_CMU = "CMU_instrumented"


def load_protocol() -> dict:
    with open(REPO_ROOT / "configs" / "d3_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------

@dataclass
class RuleCheck:
    """Ket qua kiem MOT luat."""
    rule_id: str
    status: str
    severity: str
    detail: str
    source: str = ""

    @property
    def blocks_fly(self) -> bool:
        """Luat nay co ngan phan quyet FLY khong."""
        if self.status in (VIOLATED, MISSING):
            return self.severity in (VETO, DOWNGRADE)
        return False

    @property
    def forces_no_fly(self) -> bool:
        """Luat nay co bat buoc NO_FLY khong (khong gi lat duoc)."""
        return self.status == VIOLATED and self.severity == VETO


@dataclass
class SafetyReport:
    """Ket qua kiem TOAN BO lop luat cung cho mot nhiem vu."""
    profile: str
    checks: list[RuleCheck] = field(default_factory=list)

    @property
    def violations(self) -> list[RuleCheck]:
        return [c for c in self.checks if c.status == VIOLATED]

    @property
    def missing(self) -> list[RuleCheck]:
        return [c for c in self.checks if c.status == MISSING]

    @property
    def must_no_fly(self) -> bool:
        """Co luat VETO nao bi vi pham khong — §4.6, khong gi lat duoc."""
        return any(c.forces_no_fly for c in self.checks)

    @property
    def blocks_fly(self) -> bool:
        """Co ly do nao ngan FLY khong (ke ca DOWNGRADE va thieu du lieu)."""
        return any(c.blocks_fly for c in self.checks)

    @property
    def extrapolated(self) -> bool:
        """Co dang chay ngoai dai co du lieu do lung khong (PD-*)."""
        return any(c.rule_id.startswith("PD-") and c.status == VIOLATED
                   for c in self.checks)

    @property
    def all_clear(self) -> bool:
        return not self.blocks_fly

    def reasons(self) -> list[str]:
        return [f"{c.rule_id}: {c.detail}"
                for c in self.checks if c.status != PASS]

    def __str__(self) -> str:
        if self.all_clear:
            extra = [c for c in self.checks if c.status == KNOWN_EXCEEDED]
            ghi = f" (ghi nhan: {len(extra)})" if extra else ""
            return f"dat {len(self.checks)}/{len(self.checks)} luat{ghi}"
        return "; ".join(self.reasons())


# ---------------------------------------------------------------------------
# Kiem luat cung
# ---------------------------------------------------------------------------

def check_hard_rules(payload_g: float | None = None,
                     speed_commanded_ms: float | None = None,
                     distance_2d_m: float | None = None,
                     wind_forecast_ms: float | None = None,
                     ambient_temp_c: float | None = None,
                     battery_type: str = "TB47D",
                     profile: str = PROFILE_STOCK,
                     protocol: dict | None = None) -> SafetyReport:
    """
    Kiem toan bo lop luat cung. KHONG nhan dau ra mo hinh — §4.6 doi lop nay
    chay DOC LAP voi mo hinh.

    `profile` quyet dinh cach ap HR-3, xem quyet dinh B6.
    """
    protocol = protocol or load_protocol()
    rules = protocol["hard_rules"]
    profiles = protocol["aircraft_profiles"]
    if profile not in (PROFILE_STOCK, PROFILE_CMU):
        raise ValueError(f"ho so may bay khong biet: {profile!r}")

    rep = SafetyReport(profile=profile)
    man = {r["id"]: r for r in rules["manufacturer"]}

    # --- HR-1: gio -------------------------------------------------------
    gioi_han_gio = _nguong(man["HR-1"]["check"])
    rep.checks.append(_so_sanh_tren(
        "HR-1", "gio du bao", wind_forecast_ms, gioi_han_gio, "m/s",
        VETO, man["HR-1"]["source"]))

    # --- HR-2: nhiet do ---------------------------------------------------
    t_lo, t_hi = _khoang(man["HR-2"]["check"])
    rep.checks.append(_trong_khoang(
        "HR-2", "nhiet do moi truong", ambient_temp_c, t_lo, t_hi, "C",
        VETO, man["HR-2"]["source"]))

    # --- HR-3: khoi luong cat canh (phu thuoc ho so — B6) ------------------
    rep.checks.append(_kiem_khoi_luong(payload_g, battery_type, profile,
                                       profiles, man["HR-3"]["source"]))

    # --- HR-4: toc do -----------------------------------------------------
    gioi_han_toc = _nguong(man["HR-4"]["check"])
    rep.checks.append(_so_sanh_tren(
        "HR-4", "toc do ra lenh", speed_commanded_ms, gioi_han_toc, "m/s",
        VETO, man["HR-4"]["source"]))

    # --- PD-1: envelope cu ly (gioi han hieu luc mo hinh) -----------------
    pd = {r["id"]: r for r in rules["project_derived"]}
    d_lo, d_hi = _khoang(pd["PD-1"]["check"])
    rep.checks.append(_trong_khoang(
        "PD-1", "cu ly", distance_2d_m, d_lo, d_hi, "m",
        DOWNGRADE, pd["PD-1"]["source"]))

    # --- PD-2: dai tai trong co du lieu do lung ---------------------------
    p_lo, p_hi = _khoang(pd["PD-2"]["check"])
    rep.checks.append(_trong_khoang(
        "PD-2", "tai trong", payload_g, p_lo, p_hi, "g",
        DOWNGRADE, pd["PD-2"]["source"]))

    return rep


# ---------------------------------------------------------------------------
# Kiem tung luat
# ---------------------------------------------------------------------------

def _so_sanh_tren(rule_id: str, ten: str, gia_tri: float | None,
                  gioi_han: float, don_vi: str, muc: str,
                  nguon: str) -> RuleCheck:
    """Luat dang `x <= gioi_han`."""
    if gia_tri is None:
        return RuleCheck(rule_id, MISSING, muc, f"thieu {ten}", nguon)
    if gia_tri > gioi_han:
        return RuleCheck(rule_id, VIOLATED, muc,
                         f"{ten} {gia_tri} {don_vi} > gioi han "
                         f"{gioi_han} {don_vi}", nguon)
    return RuleCheck(rule_id, PASS, muc,
                     f"{ten} {gia_tri} {don_vi} <= {gioi_han} {don_vi}", nguon)


def _trong_khoang(rule_id: str, ten: str, gia_tri: float | None,
                  lo: float, hi: float, don_vi: str, muc: str,
                  nguon: str) -> RuleCheck:
    """Luat dang `lo <= x <= hi`."""
    if gia_tri is None:
        return RuleCheck(rule_id, MISSING, muc, f"thieu {ten}", nguon)
    if gia_tri != gia_tri:                       # NaN
        return RuleCheck(rule_id, VIOLATED, muc, f"{ten} khong phai so", nguon)
    if not lo <= gia_tri <= hi:
        return RuleCheck(rule_id, VIOLATED, muc,
                         f"{ten} {gia_tri} {don_vi} ngoai dai "
                         f"[{lo}, {hi}] {don_vi}", nguon)
    return RuleCheck(rule_id, PASS, muc,
                     f"{ten} {gia_tri} {don_vi} trong [{lo}, {hi}]", nguon)


def _kiem_khoi_luong(payload_g: float | None, battery_type: str,
                     profile: str, profiles: dict, nguon: str) -> RuleCheck:
    """
    HR-3 — khoi luong cat canh. Cach ap phu thuoc ho so may bay (B6).

    M100_stock       : khung 2355/2431 g -> veto binh thuong
    CMU_instrumented : khung 3680 g, vuot MTOW o MOI cau hinh -> KNOWN_EXCEEDED,
                       khong veto. Neu veto thi 192/192 chuyen NO_FLY.
    """
    if payload_g is None:
        muc = VETO if profile == PROFILE_STOCK else RECORD_ONLY
        return RuleCheck("HR-3", MISSING, muc, "thieu tai trong", nguon)

    cfg = profiles[profile]
    mtow = float(cfg["mtow_g"])

    if profile == PROFILE_STOCK:
        khung = float(cfg["airframe_mass_g"][battery_type])
        tong = khung + payload_g
        if tong > mtow:
            return RuleCheck("HR-3", VIOLATED, VETO,
                             f"khoi luong cat canh {tong:.0f} g > MTOW "
                             f"{mtow:.0f} g (khung {khung:.0f} + tai {payload_g:.0f})",
                             nguon)
        return RuleCheck("HR-3", PASS, VETO,
                         f"khoi luong cat canh {tong:.0f} g <= MTOW {mtow:.0f} g",
                         nguon)

    # CMU_instrumented — da biet la vuot, khai bao chu khong chan
    khung = float(cfg["airframe_mass_g"])
    tong = khung + payload_g
    if tong > mtow:
        return RuleCheck("HR-3", KNOWN_EXCEEDED, RECORD_ONLY,
                         f"khoi luong cat canh {tong:.0f} g vuot MTOW "
                         f"{mtow:.0f} g — DA BIET, may bay mang "
                         f"{cfg['instrumentation_mass_g']} g thiet bi do; "
                         f"ghi nhan, khong chan (B6)", nguon)
    return RuleCheck("HR-3", PASS, RECORD_ONLY,
                     f"khoi luong cat canh {tong:.0f} g <= MTOW {mtow:.0f} g",
                     nguon)


# ---------------------------------------------------------------------------
# Doc nguong tu chuoi luat trong giao thuc — khong viet cung con so
# ---------------------------------------------------------------------------

def _nguong(check: str) -> float:
    """'wind_forecast_ms <= 10.0' -> 10.0"""
    return float(check.split("<=")[-1].strip())


def _khoang(check: str) -> tuple[float, float]:
    """'-10 <= ambient_temp_c <= 40' -> (-10.0, 40.0)"""
    parts = check.split("<=")
    if len(parts) != 3:
        raise ValueError(f"khong doc duoc khoang tu luat: {check!r}")
    return float(parts[0].strip()), float(parts[-1].strip())


# ---------------------------------------------------------------------------

def _demo() -> None:
    print("Lop luat cung — §4.6\n")

    truong_hop = [
        ("chuyen binh thuong",
         dict(payload_g=250, speed_commanded_ms=8, distance_2d_m=472,
              wind_forecast_ms=3.0, ambient_temp_c=15)),
        ("gio 14 m/s (vuot HR-1)",
         dict(payload_g=250, speed_commanded_ms=8, distance_2d_m=472,
              wind_forecast_ms=14.0, ambient_temp_c=15)),
        ("nhiet do -25 C (vuot HR-2)",
         dict(payload_g=250, speed_commanded_ms=8, distance_2d_m=472,
              wind_forecast_ms=3.0, ambient_temp_c=-25)),
        ("tai 1500 g (vuot HR-3 o ho so stock)",
         dict(payload_g=1500, speed_commanded_ms=8, distance_2d_m=472,
              wind_forecast_ms=3.0, ambient_temp_c=15)),
        ("cu ly 835 m (ngoai PD-1)",
         dict(payload_g=250, speed_commanded_ms=8, distance_2d_m=835,
              wind_forecast_ms=3.0, ambient_temp_c=15)),
        ("thieu gio",
         dict(payload_g=250, speed_commanded_ms=8, distance_2d_m=472,
              wind_forecast_ms=None, ambient_temp_c=15)),
    ]

    for ten, kw in truong_hop:
        rep = check_hard_rules(**kw)
        co = "NO_FLY bat buoc" if rep.must_no_fly else (
            "khong duoc FLY" if rep.blocks_fly else "qua")
        print(f"  {ten:<38} -> {co}")
        for r in rep.reasons():
            print(f"       {r}")

    print("\n\nHai ho so may bay (quyet dinh B6), tai 500 g\n")
    for prof in (PROFILE_STOCK, PROFILE_CMU):
        rep = check_hard_rules(payload_g=500, speed_commanded_ms=8,
                               distance_2d_m=472, wind_forecast_ms=3.0,
                               ambient_temp_c=15, profile=prof)
        hr3 = next(c for c in rep.checks if c.rule_id == "HR-3")
        print(f"  {prof:<18} HR-3 = {hr3.status}")
        print(f"       {hr3.detail}")
        print(f"       bat buoc NO_FLY: {rep.must_no_fly}\n")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        _demo()
    else:
        ap.print_help()
