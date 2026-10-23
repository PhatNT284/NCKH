"""
Bien du tru va phan quyet — khoi (c) va (e) cua san pham D3.

    M = E_available - E_required                         (§5.6)
    R = (E_available - E_required) / E_required          (§5.6)

BON MUC PHAN QUYET (§5.7 cho ba muc, §4.6 them muc thu tu):

    FLY                R >= R_fly, khong vi pham luat cung, du dau vao
    CONDITIONAL        R_min <= R < R_fly, hoac dang ngoai suy (PD-*)
    NO_FLY             R < R_min, hoac vi pham luat cung VETO
    INSUFFICIENT_DATA  thieu / het han bat ky dau vao an toan nao

HAI NGUONG (quyet dinh B4):

    R_min = r                                   r = 0.20, tham so chinh sach
    R_fly = r + p95(|phan du|) / E_required      khoan bat dinh cua mo hinh

Vi sao cong them: he so du tru r chong RUI RO VAN HANH (gio, vong cho, lech
tuyen). No KHONG chong SAI SO DU BAO cua chinh mo hinh — do la rui ro rieng.
Khoan cong them lay tu phan vi 95 cua |phan du| out-of-fold cua D2-b = 1.4687 Wh,
dung cach §4.7 chi: "a documented uncertainty allowance" rut tu phan du DO DUOC,
khong phai tu chinh mo hinh (neu lay tu chinh mo hinh thi danh gia thanh vong tron).

DIEU r KHONG BAO GOM (quyet dinh B9 va B10):

    - Nang luong cat canh va ha canh BINH THUONG -> nam trong E_required, vi
      muc tieu du bao cua D2 la tong nang luong ca chuyen bay (§4.2 buoc 4).
      Xem d3_protocol.yaml muc energy_required.budget_conventions.
      Cong them hoac nang r de "bu cho ha canh" la DEM HAI LAN.
    - San nang luong ha canh khi co SU CO -> luat cung PH-1 (P§4.6).

THU TU XET — bat buoc, khong duoc doi:

    1. Thieu dau vao        -> INSUFFICIENT_DATA   (§4.6 fail closed)
    2. Vi pham luat cung    -> NO_FLY              (§4.6 veto, khong gi lat duoc)
    3. Bien du tru          -> FLY / CONDITIONAL / NO_FLY
    4. Dang ngoai suy PD-*  -> ha FLY xuong CONDITIONAL

Buoc 2 truoc buoc 3 la bat buoc. §4.6 nguyen van: "no score, no model output and
no human approval may convert a hard-rule violation into FLY."

§5.6 loai bo cach cham diem gop, nen module nay KHONG tao ra diem so nao. Va
§5.6/§5.8 cam goi bat ky dau ra nao la "xac suat" hay "do tin cay".

    python3 -m src.decision_rules --demo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.available_energy import (
    STATUS_MISSING, STATUS_OK, STATUS_OUT_OF_RANGE, AvailableEnergy,
    available_energy,
)
from src.safety_invariants import (
    PASS, PROFILE_STOCK, SafetyReport, check_hard_rules,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

FLY = "FLY"
CONDITIONAL = "CONDITIONAL"
NO_FLY = "NO_FLY"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# Thu tu tu xau den tot — dung cho bat bien don dieu (INV-3)
VERDICT_ORDER = [INSUFFICIENT_DATA, NO_FLY, CONDITIONAL, FLY]


def load_protocol() -> dict:
    with open(REPO_ROOT / "configs" / "d3_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------

@dataclass
class Decision:
    """
    Ket qua mot lan danh gia kha thi.

    KHONG co truong "diem so" hay "do tin cay" — §5.6 loai bo cach cham diem gop,
    §5.8 cam goi dau ra la do tin cay. Moi thu o day la dai luong vat ly hoac
    mot nhan phan quyet.
    """
    verdict: str
    reasons: list[str] = field(default_factory=list)

    # Dai luong nang luong, Wh
    e_available_Wh: float | None = None
    e_required_Wh: float | None = None
    margin_Wh: float | None = None              # M
    margin_ratio: float | None = None           # R

    # Nguong dang hieu luc
    reserve_factor: float | None = None         # r
    r_min: float | None = None
    r_fly: float | None = None
    uncertainty_allowance_Wh: float | None = None

    # Nhan
    extrapolated: bool = False
    mitigation_applied: str | None = None
    hard_rule_report: SafetyReport | None = None
    available: AvailableEnergy | None = None

    @property
    def may_fly(self) -> bool:
        return self.verdict in (FLY, CONDITIONAL)

    @property
    def actionable(self) -> bool:
        """
        Phan quyet nay da THUC THI DUOC chua — Muc 12.1, §2.3.

        Nguyen van §2.3: "CONDITIONAL / DEGRADED is actionable only when an
        approved mitigation is selected and the scenario is re-evaluated where
        the mitigation changes energy demand or constraints."

        Nen CONDITIONAL ma chua chon bien phap thi CHUA thuc thi duoc: no moi la
        mot nhan, chua phai mot trang thai co duong ra. Xem src/mitigations.py.
        """
        if self.verdict == FLY:
            return True
        if self.verdict == CONDITIONAL:
            return self.mitigation_applied is not None
        return False

    def __str__(self) -> str:
        if self.margin_ratio is None:
            return f"{self.verdict}: {'; '.join(self.reasons)}"
        nhan = " [NGOAI SUY]" if self.extrapolated else ""
        return (f"{self.verdict}{nhan}  "
                f"M = {self.margin_Wh:+.2f} Wh, R = {self.margin_ratio:+.1%} "
                f"(nguong {self.r_min:.1%} / {self.r_fly:.1%})")


# ---------------------------------------------------------------------------

def assess(payload_g: float | None = None,
           speed_commanded_ms: float | None = None,
           altitude_m: float | None = None,
           distance_2d_m: float | None = None,
           wind_forecast_ms: float | None = None,
           ambient_temp_c: float | None = None,
           soc: float | None = None,
           soh: float | None = None,
           battery_type: str = "TB47D",
           profile: str = PROFILE_STOCK,
           e_required_Wh: float | None = None,
           reserve_factor: float | None = None,
           mitigation_applied: str | None = None,
           protocol: dict | None = None) -> Decision:
    """
    Danh gia kha thi nang luong cho mot nhiem vu.

    `e_required_Wh` la nang luong du bao cua mo hinh D2. Truyen tu ngoai vao de
    module nay KHONG phu thuoc vao scikit-learn va kiem duoc doc lap. Luong
    chay that do src/workflow_state.py ghep.

    `reserve_factor` None -> dung gia tri chinh trong giao thuc (0.20). Truyen
    0.10 hoac 0.30 de quet — P§4.5 BAT BUOC bao ca ba muc.

    `mitigation_applied` la ma bien phap giam thieu da duoc duyet va ap dung.
    CONDITIONAL khong kem bien phap thi `actionable` = False (Muc 12.1, §2.3).
    Dung src/mitigations.py de de xuat va ap dung.
    """
    protocol = protocol or load_protocol()
    cfg = protocol["reserve_and_verdict"]
    r = float(cfg["reserve_factor"]["primary"]) if reserve_factor is None \
        else float(reserve_factor)
    allowance = float(
        protocol["energy_required"]["measured_error"]["p95_abs_residual_Wh"])

    # --- Buoc 1: luat cung (chay TRUOC, doc lap voi mo hinh — §4.6) --------
    # Lop nay nhan DAU VAO THO (ke ca soc/soh cho luat PH-1) va tu tinh nang
    # luong kha dung bang cong thuc §5.4. No KHONG nhan dau ra mo hinh nao va
    # khong biet gi ve E_required — xem quyet dinh B10b.
    hard = check_hard_rules(
        payload_g=payload_g, speed_commanded_ms=speed_commanded_ms,
        distance_2d_m=distance_2d_m, wind_forecast_ms=wind_forecast_ms,
        ambient_temp_c=ambient_temp_c, altitude_m=altitude_m,
        soc=soc, soh=soh,
        battery_type=battery_type, profile=profile, protocol=protocol)

    avail = available_energy(soc=soc, soh=soh, temp_c=ambient_temp_c,
                             battery_type=battery_type, protocol=protocol)

    d = Decision(verdict=NO_FLY, hard_rule_report=hard, available=avail,
                 reserve_factor=r, r_min=r,
                 uncertainty_allowance_Wh=allowance,
                 extrapolated=hard.extrapolated,
                 mitigation_applied=mitigation_applied)

    # --- Buoc 3: vi pham VETO -> NO_FLY, khong gi lat duoc -----------------
    # Xet TRUOC thieu du lieu: mot vi pham da biet chac chan van la vi pham,
    # du cac dau vao khac co thieu hay khong.
    if hard.must_no_fly:
        d.verdict = NO_FLY
        # Luat THUC SU chan phai dung DAU danh sach. Neu khong, mot muc
        # KNOWN_EXCEEDED (vi du HR-3 o ho so CMU_instrumented, von "ghi nhan,
        # khong chan") co the chiem cho reasons[0] va che mat ly do that.
        d.reasons = [f"vi pham luat cung: {c.rule_id}: {c.detail}"
                     for c in hard.checks if c.forces_no_fly]
        d.reasons += [f"ghi nhan them: {c.rule_id}: {c.detail}"
                      for c in hard.checks
                      if c.status != PASS and not c.forces_no_fly]
        return d

    # --- Buoc 4: dau vao pin SAI DAI -> NO_FLY (quyet dinh B5) ------------
    # Xet TRUOC phan thieu du lieu: "biet chac la sai" la thong tin manh hon
    # "khong biet". Mot SoC = 1.5 la sai chu khong phai thieu, nen phai ra
    # NO_FLY. Neu de sau thi PH-1 (bao MISSING vi khong tinh duoc nang luong
    # kha dung) se chiem truoc va cho ra INSUFFICIENT_DATA — sai quyet dinh B5.
    if avail.status == STATUS_OUT_OF_RANGE:
        d.verdict = NO_FLY
        d.reasons = [f"dau vao pin ngoai dai: {x}" for x in avail.reasons]
        return d

    # --- Buoc 5: thieu dau vao -> INSUFFICIENT_DATA (§4.6 fail closed) -----
    # Thu tu: NGUYEN NHAN GOC truoc, TRIEU CHUNG KEO THEO sau.
    # Thieu SoC lam PH-1 khong tinh duoc nang luong ha canh, nen PH-1 cung bao
    # thieu. Neu in PH-1 truoc thi nguoi doc di sua sai cho.
    thieu: list[str] = []
    if avail.status == STATUS_MISSING:
        thieu += avail.reasons
    if e_required_Wh is None:
        thieu.append("thieu du bao nang luong can (E_required)")
    if hard.missing:
        thieu += [f"{c.rule_id}: {c.detail}" for c in hard.missing]
    if thieu:
        d.verdict = INSUFFICIENT_DATA
        d.reasons = thieu
        return d

    if avail.status != STATUS_OK:                        # pragma: no cover
        raise AssertionError(f"trang thai la: {avail.status}")

    if e_required_Wh <= 0:
        d.verdict = NO_FLY
        d.reasons = [f"E_required = {e_required_Wh} Wh khong hop le"]
        return d

    # --- Buoc 5: bien du tru ----------------------------------------------
    d.e_available_Wh = avail.value_Wh
    d.e_required_Wh = float(e_required_Wh)
    d.margin_Wh = d.e_available_Wh - d.e_required_Wh
    d.margin_ratio = d.margin_Wh / d.e_required_Wh
    d.r_fly = r + allowance / d.e_required_Wh

    if d.margin_ratio < d.r_min:
        d.verdict = NO_FLY
        d.reasons = [f"bien du tru {d.margin_ratio:.1%} duoi nguong "
                     f"{d.r_min:.1%} (he so du tru r = {r:.2f})"]
        return d

    if d.margin_ratio < d.r_fly:
        d.verdict = CONDITIONAL
        d.reasons = [f"bien du tru {d.margin_ratio:.1%} nam giua "
                     f"{d.r_min:.1%} va {d.r_fly:.1%} — du so voi he so du tru "
                     f"nhung chua phu het khoan bat dinh cua mo hinh "
                     f"({allowance:.3f} Wh)"]
    else:
        d.verdict = FLY
        d.reasons = [f"bien du tru {d.margin_ratio:.1%} >= {d.r_fly:.1%}"]

    # --- Buoc 6: dang ngoai suy -> ha FLY xuong CONDITIONAL ---------------
    if hard.blocks_fly and d.verdict == FLY:
        d.verdict = CONDITIONAL
        d.reasons = [f"ngoai dai co du lieu do lung: {r_}"
                     for r_ in hard.reasons()] + d.reasons

    # Ghi chu ve nhiet do ngoai dai hieu chinh
    if avail.reasons:
        d.reasons += avail.reasons

    return d


# ---------------------------------------------------------------------------

def sweep_reserve(protocol: dict | None = None, **kw) -> dict[float, Decision]:
    """
    Chay lai cung mot nhiem vu o ca ba muc he so du tru.

    P§4.5 BAT BUOC: "a finding that holds only at one arbitrary reserve setting
    is not a finding about the method."
    """
    protocol = protocol or load_protocol()
    muc = protocol["reserve_and_verdict"]["reserve_factor"]["sweep"]
    return {float(r): assess(reserve_factor=r, protocol=protocol, **kw)
            for r in muc}


# ---------------------------------------------------------------------------

def _demo() -> None:
    goc = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50,
               distance_2d_m=472, wind_forecast_ms=3.0, ambient_temp_c=15,
               soh=0.95, e_required_Wh=22.0)

    print("Phan quyet theo SoC — pin TB47D, SoH 0.95, T 15 C, can 22.0 Wh\n")
    print(f"{'SoC':>6} {'E_av':>8} {'M':>8} {'R':>9}   phan quyet")
    print("-" * 52)
    for soc in (0.25, 0.28, 0.285, 0.30, 0.40, 0.70, 1.00):
        d = assess(**{**goc, "soc": soc})
        print(f"{soc:>6.3f} {d.e_available_Wh:>8.2f} {d.margin_Wh:>+8.2f} "
              f"{d.margin_ratio:>+9.1%}   {d.verdict}")

    d = assess(**{**goc, "soc": 0.35})
    print(f"\nNguong cho chuyen nay: R_min = {d.r_min:.1%}, "
          f"R_fly = {d.r_fly:.1%}")
    print(f"  = {d.reserve_factor:.2f} + {d.uncertainty_allowance_Wh:.4f} Wh "
          f"/ {d.e_required_Wh:.1f} Wh")

    print("\n\nLuat cung phu quyet — pin day, bien du tru rat lon\n")
    for ten, kw in (
        ("gio 14 m/s",     {"wind_forecast_ms": 14.0}),
        ("nhiet do -25 C", {"ambient_temp_c": -25.0}),
        ("tai 1500 g",     {"payload_g": 1500}),
    ):
        d = assess(**{**goc, "soc": 1.0, **kw})
        print(f"  {ten:<16} -> {d.verdict}")
        print(f"       {d.reasons[0]}")

    print("\n\nPH-1 — san nang luong ha canh (P§4.6)\n")
    from src.physics_m100 import min_soc_for_landing
    from src.safety_invariants import PROFILE_CMU
    for alt in (50, 100):
        nguong = min_soc_for_landing(alt, 3680 + 500)
        for he_so in (0.5, 1.5):
            soc = min(1.0, nguong * he_so)
            d = assess(**{**goc, "payload_g": 500, "altitude_m": alt,
                          "soc": soc, "soh": 1.0, "e_required_Wh": 5.0,
                          "profile": PROFILE_CMU})
            print(f"  cao {alt} m, tai 500 g, SoC {soc:.1%} "
                  f"(nguong ha canh {nguong:.1%}) -> {d.verdict}")
            print(f"       {d.reasons[0]}")

    print("\n\nNgoai suy ha cap FLY -> CONDITIONAL\n")
    d = assess(**{**goc, "soc": 1.0, "distance_2d_m": 835})
    print(f"  cu ly 835 m, pin day -> {d.verdict}, ngoai suy = {d.extrapolated}")
    print(f"       {d.reasons[0]}")

    print("\n\nFail closed\n")
    for ten, kw in (
        ("thieu SoC",       {"soc": None}),
        ("thieu nhiet do",  {"soc": 0.8, "ambient_temp_c": None}),
        ("thieu du bao D2", {"soc": 0.8, "e_required_Wh": None}),
        ("thieu do cao",    {"soc": 0.8, "altitude_m": None}),
    ):
        d = assess(**{**goc, **kw})
        print(f"  {ten:<18} -> {d.verdict}: {d.reasons[0]}")

    print("\n\nQuet he so du tru (P§4.5 bat buoc) — SoC 0.30, R = +28.8 %\n")
    print(f"{'r':>6} {'R_min':>8} {'R_fly':>8}   phan quyet")
    print("-" * 40)
    for r, d in sweep_reserve(**{**goc, "soc": 0.30}).items():
        print(f"{r:>6.2f} {d.r_min:>8.1%} {d.r_fly:>8.1%}   {d.verdict}")
    print("\n  Cung mot chuyen bay, ba ket luan khac nhau. Day la ly do §5.7 goi\n"
          "  he so du tru la THAM SO CHINH SACH, va P§4.5 bat bao ca ba muc.")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        _demo()
    else:
        ap.print_help()