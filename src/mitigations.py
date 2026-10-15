"""
Bien phap giam thieu cho phan quyet CONDITIONAL — Muc 12.1, §2.3.

VI SAO CAN MODULE NAY

    Muc 12.1, tieu chi D3: "conditional verdicts require an explicit mitigation".
    §2.3 noi ro hon:

        "CONDITIONAL / DEGRADED is actionable only when an approved mitigation
         is selected and the scenario is re-evaluated where the mitigation
         changes energy demand or constraints."

    Truoc khi co module nay, CONDITIONAL la mot NGO CUT: he thong noi "sat
    nguong" roi het. Nguoi dieu phoi khong biet lam gi tiep.

    Gio no la mot trang thai CO DUONG RA:

        CONDITIONAL
            |  he thong de xuat cac bien phap THUC SU doi duoc phan quyet
            |     sac them pin  -> chay lai -> FLY
            |     doi pin TB48D -> chay lai -> FLY
            |  nguoi duyet chon mot
            v
        danh gia lai -> phan quyet moi, actionable = True

HAI DIEU KIEN DE MOT BIEN PHAP LA HOP LE

    1. Phai doi NHU CAU NANG LUONG hoac RANG BUOC (§2.3). "Can than hon khi
       bay" khong phai bien phap. "Giam tai 250 g" thi phai.
    2. Phai THUC SU cai thien phan quyet khi ap dung. De xuat mot bien phap
       khong doi duoc gi la lua nguoi dung. Day la bat bien INV-7, va `propose()`
       bao dam bang cach CHAY THU tung bien phap truoc khi de xuat.

HAI NHOM BIEN PHAP

    Nhom A — doi NANG LUONG KHA DUNG hoac RANG BUOC. Tinh duoc ngay, khong can
    mo hinh du bao:
        M1 sac them pin        -> doi SoC
        M2 doi sang pin TB48D  -> doi E_nominal
        M3 doi gio giam        -> go vi pham HR-1
        M4 doi troi am hon     -> doi kappa(T)

    Nhom B — doi NHU CAU NANG LUONG. Phai du bao lai bang mo hinh D2, nen can
    mot ham `estimator` truyen tu ngoai vao:
        M5 giam tai trong
        M6 giam toc do ra lenh
        M7 rut ngan tuyen bay

    Khong truyen `estimator` thi nhom B bi bo qua va bao ro trong ket qua, chu
    KHONG im lang. D3 tuyet doi khong duoc tu import mo hinh — INV-6 quet ma
    nguon tim `.fit()`, `.predict()` va `import sklearn`.

    python3 -m src.mitigations --demo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from src.decision_rules import (
    CONDITIONAL, FLY, NO_FLY, VERDICT_ORDER, Decision, assess, load_protocol,
)

GROUP_A = "A"      # doi nang luong kha dung hoac rang buoc
GROUP_B = "B"      # doi nhu cau nang luong — can estimator

# Cac muc roi rac co trong bo du lieu (reports/parameter_table.md muc 5)
PAYLOAD_LEVELS = (0.0, 250.0, 500.0)
SPEED_LEVELS = (4.0, 6.0, 8.0, 10.0, 12.0)


@dataclass
class Mitigation:
    """Mot bien phap giam thieu."""
    id: str
    name: str
    group: str
    changes: str                       # doi cai gi — de nguoi duyet hieu
    apply: Callable[[dict], dict | None]
    note: str = ""

    @property
    def needs_estimator(self) -> bool:
        return self.group == GROUP_B


@dataclass
class Proposal:
    """Mot bien phap DA CHAY THU va cho ket qua tot hon."""
    mitigation: Mitigation
    before: str
    after: str
    inputs_after: dict = field(default_factory=dict)
    decision_after: Decision | None = None

    def __str__(self) -> str:
        return (f"{self.mitigation.id}  {self.mitigation.name:<34} "
                f"{self.before} -> {self.after}")


# ---------------------------------------------------------------------------
# Nhom A — khong can mo hinh du bao
# ---------------------------------------------------------------------------

def _sac_them(kw: dict) -> dict | None:
    soc = kw.get("soc")
    if soc is None or soc >= 0.999:
        return None
    return {**kw, "soc": 1.0}


def _doi_pin(kw: dict) -> dict | None:
    if kw.get("battery_type") == "TB48D":
        return None
    return {**kw, "battery_type": "TB48D"}


def _doi_gio_giam(kw: dict, protocol: dict) -> dict | None:
    """Chi co nghia khi gio dang la thu chan. Dat ve nguong gioi han."""
    gio = kw.get("wind_forecast_ms")
    if gio is None:
        return None
    gioi_han = float(
        next(r for r in protocol["hard_rules"]["manufacturer"]
             if r["id"] == "HR-1")["check"].split("<=")[-1])
    if gio <= gioi_han:
        return None
    return {**kw, "wind_forecast_ms": gioi_han}


def _doi_am_hon(kw: dict, protocol: dict) -> dict | None:
    """
    Doi toi khi nhiet do vao dai hieu chinh cua Kim. Chi co nghia khi dang
    duoi dai — tren dai thi kappa da bang 1, doi them khong duoc gi.
    """
    t = kw.get("ambient_temp_c")
    if t is None:
        return None
    hi = protocol["available_energy"]["kappa_temperature"]["calibrated_range_c"][1]
    if t >= hi:
        return None
    return {**kw, "ambient_temp_c": float(hi)}


# ---------------------------------------------------------------------------
# Nhom B — can mo hinh du bao
# ---------------------------------------------------------------------------

def _xuong_muc(gia_tri: float, cac_muc: tuple) -> float | None:
    thap_hon = [m for m in cac_muc if m < gia_tri]
    return max(thap_hon) if thap_hon else None


def _giam_tai(kw: dict) -> dict | None:
    v = kw.get("payload_g")
    if v is None:
        return None
    moi = _xuong_muc(float(v), PAYLOAD_LEVELS)
    return None if moi is None else {**kw, "payload_g": moi}


def _giam_toc(kw: dict) -> dict | None:
    v = kw.get("speed_commanded_ms")
    if v is None:
        return None
    moi = _xuong_muc(float(v), SPEED_LEVELS)
    return None if moi is None else {**kw, "speed_commanded_ms": moi}


def _rut_ngan(kw: dict, protocol: dict) -> dict | None:
    """Rut tuyen ve bien tren cua envelope — chi co nghia khi dang ngoai envelope."""
    d = kw.get("distance_2d_m")
    if d is None:
        return None
    lo, hi = protocol["energy_required"]["validity_envelope"]["distance_2d_m"]
    if d <= hi:
        return None
    return {**kw, "distance_2d_m": float(hi)}


# ---------------------------------------------------------------------------

def catalogue(protocol: dict | None = None) -> list[Mitigation]:
    """Danh muc bien phap. Thu tu tu it ton kem den nhieu."""
    p = protocol or load_protocol()
    return [
        Mitigation("M1", "Sac them pin truoc khi bay", GROUP_A,
                   "tang SoC -> tang E_available", _sac_them),
        Mitigation("M2", "Doi sang pin TB48D", GROUP_A,
                   "tang E_nominal 99.9 -> 129.96 Wh", _doi_pin,
                   note="OI-2 chua chot chac loai pin; dung bien phap nay thi "
                        "phai ghi ro gia dinh"),
        Mitigation("M3", "Doi toi khi gio giam", GROUP_A,
                   "go vi pham HR-1", lambda kw: _doi_gio_giam(kw, p)),
        Mitigation("M4", "Doi toi khi troi am hon", GROUP_A,
                   "tang kappa(T) -> tang E_available",
                   lambda kw: _doi_am_hon(kw, p)),
        Mitigation("M5", "Giam tai trong mot muc", GROUP_B,
                   "giam nhu cau nang luong", _giam_tai),
        Mitigation("M6", "Giam toc do ra lenh mot muc", GROUP_B,
                   "giam nhu cau nang luong", _giam_toc),
        Mitigation("M7", "Rut tuyen ve trong envelope", GROUP_B,
                   "giam nhu cau nang luong, go PD-1",
                   lambda kw: _rut_ngan(kw, p)),
    ]


# ---------------------------------------------------------------------------

def propose(mission: dict, estimator: Callable[[dict], float] | None = None,
            protocol: dict | None = None) -> tuple[list[Proposal], list[str]]:
    """
    De xuat cac bien phap THUC SU cai thien duoc phan quyet.

    Tra ve (danh_sach_de_xuat, canh_bao). Canh bao noi ro bien phap nao bi bo
    qua va vi sao — khong im lang.

    `estimator` nhan dict tham so nhiem vu, tra ve E_required moi (Wh). Thuong
    la mo hinh D2 da chot. Khong truyen thi nhom B bi bo qua.

    INV-7: moi bien phap trong danh sach tra ve deu DA DUOC CHAY THU va cho
    phan quyet tot hon. Khong de xuat bien phap vo dung.
    """
    protocol = protocol or load_protocol()
    goc = assess(**mission, protocol=protocol)
    muc_goc = VERDICT_ORDER.index(goc.verdict)

    de_xuat: list[Proposal] = []
    canh_bao: list[str] = []

    for m in catalogue(protocol):
        if m.needs_estimator and estimator is None:
            canh_bao.append(f"{m.id} ({m.name}): bo qua — can ham du bao "
                            f"nang luong, chua truyen `estimator`")
            continue

        moi = m.apply(dict(mission))
        if moi is None:
            continue                               # khong ap dung duoc

        if m.needs_estimator:
            try:
                moi["e_required_Wh"] = float(estimator(moi))
            except Exception as e:                 # pragma: no cover
                canh_bao.append(f"{m.id}: ham du bao loi — {e}")
                continue

        sau = assess(**moi, mitigation_applied=m.id, protocol=protocol)
        if VERDICT_ORDER.index(sau.verdict) > muc_goc:
            de_xuat.append(Proposal(m, goc.verdict, sau.verdict, moi, sau))

    return de_xuat, canh_bao


def apply_mitigation(mission: dict, mitigation_id: str,
                     estimator: Callable[[dict], float] | None = None,
                     protocol: dict | None = None) -> Decision:
    """
    Ap dung mot bien phap da duoc duyet va DANH GIA LAI.

    §2.3 doi phai danh gia lai, khong duoc chi dan nhan roi cho bay.
    """
    protocol = protocol or load_protocol()
    m = next((x for x in catalogue(protocol) if x.id == mitigation_id), None)
    if m is None:
        raise ValueError(f"bien phap khong biet: {mitigation_id!r}")

    moi = m.apply(dict(mission))
    if moi is None:
        raise ValueError(f"{mitigation_id} khong ap dung duoc cho nhiem vu nay")

    if m.needs_estimator:
        if estimator is None:
            raise ValueError(
                f"{mitigation_id} doi nhu cau nang luong, phai truyen `estimator` "
                f"de du bao lai — khong duoc giu nguyen E_required cu")
        moi["e_required_Wh"] = float(estimator(moi))

    return assess(**moi, mitigation_applied=mitigation_id, protocol=protocol)


# ---------------------------------------------------------------------------

def _demo() -> None:
    goc = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50,
               distance_2d_m=472, wind_forecast_ms=3.0, ambient_temp_c=15,
               soc=0.28, soh=0.95, e_required_Wh=22.0)

    d = assess(**goc)
    print("1. Phan quyet goc\n")
    print(f"   {d.verdict}, bien du tru {d.margin_ratio:+.1%}")
    print(f"   thuc thi duoc: {d.actionable}   <- CONDITIONAL chua co bien phap\n")

    print("\n2. He thong de xuat (khong co ham du bao)\n")
    dx, cb = propose(goc)
    for p in dx:
        print(f"   {p}")
    print()
    for c in cb:
        print(f"   [bo qua] {c}")

    print("\n\n3. Nguoi duyet chon M1 — danh gia lai\n")
    sau = apply_mitigation(goc, "M1")
    print(f"   {sau.verdict}, bien du tru {sau.margin_ratio:+.1%}")
    print(f"   bien phap: {sau.mitigation_applied}")
    print(f"   thuc thi duoc: {sau.actionable}")

    print("\n\n4. Co ham du bao thi nhom B dung duoc\n")

    def uoc_luong_gia(kw: dict) -> float:
        """
        Xap xi tuyen tinh tu he so Ridge (reports/d2_ridge_coefficients.csv),
        CHI de minh hoa trong demo. Chay that thi truyen mo hinh D2 da chot.
        """
        return (22.0
                + 0.008121 * (kw["payload_g"] - 250)
                + 0.235256 * (kw["speed_commanded_ms"] - 8)
                - 0.001305 * (kw["distance_2d_m"] - 472))

    dx2, cb2 = propose(goc, estimator=uoc_luong_gia)
    for p in dx2:
        print(f"   {p}")
    print(f"\n   canh bao: {cb2 if cb2 else 'khong'}")

    print("\n\n5. Nhiem vu ngoai envelope — M7 go duoc PD-1\n")
    xa = {**goc, "soc": 1.0, "distance_2d_m": 835}
    d3 = assess(**xa)
    print(f"   goc: {d3.verdict}, ngoai suy = {d3.extrapolated}, "
          f"thuc thi duoc = {d3.actionable}")
    dx3, _ = propose(xa, estimator=uoc_luong_gia)
    for p in dx3:
        print(f"   {p}")

    print("\n\n6. Bien phap vo dung KHONG duoc de xuat\n")
    day = {**goc, "soc": 1.0}
    d4 = assess(**day)
    dx4, _ = propose(day, estimator=uoc_luong_gia)
    print(f"   nhiem vu da {d4.verdict} san -> de xuat {len(dx4)} bien phap")
    print("   (khong co gi cai thien duoc nua, nen khong de xuat gi — INV-7)")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        _demo()
    else:
        ap.print_help()
