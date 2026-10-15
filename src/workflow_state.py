"""
Ban ghi nhiem vu va quan trang thai — khoi (f) cua san pham D3.

Bon khoi truoc tra ve mot phan quyet TAI MOT THOI DIEM. Module nay tra loi cau
khac: phan quyet do CON HIEU LUC KHONG.

Che do hong ma no chong:

    08:00  danh gia chuyen giao hang        -> FLY
    08:30  du bao gio cap nhat: 3 -> 12 m/s
    09:00  nguoi dieu phoi nhin man hinh, thay FLY, cho cat canh

Khong ai lam gi sai. Chi la khong ai bao he thong rang du lieu da doi.

BA VIEC

1. DAU CON HAN (P§4.2)
   Nguyen van: "when any safety-relevant input, the mission plan, the aircraft or
   battery selection, a threshold or the model itself changes, the previous
   assessment is marked stale and must be recomputed before the mission may
   proceed."

2. BAN GHI DU DE TINH LAI (P§4.2, RQ4)
   "given a stored record and the published platform parameters, the verdict can
   be recomputed exactly". Nen ban ghi phai mang theo PHIEN BAN cua moi thu:
   mo hinh nao, nguong nao, luat nao, ho so may bay nao. Ba thang sau co su co,
   mo ban ghi ra la dung lai duoc dung cau hinh hom do.

3. TRUONG KET CUC GHI DOC LAP
   Ghi thuc te chuyen do ra sao, va duoc phep la "khong biet". P§4.2 doi vay de
   danh gia ve sau KHONG BAO GIO lay chinh phan quyet cua he thong lam su that
   nen — neu khong he thong tu cham diem chinh no va luon duoc 100 %.

Module nay KHONG tinh toan gi moi. No boc quanh src/decision_rules.py.
Day cung la nen cho san pham D6 (ban ghi nhiem vu tai lap, tuan 11).

    python3 -m src.workflow_state --demo
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.decision_rules import assess, load_protocol
from src.safety_invariants import PROFILE_STOCK

REPO_ROOT = Path(__file__).resolve().parent.parent

FRESH = "FRESH"
STALE = "STALE"

# Ket cuc that cua chuyen bay — ghi DOC LAP voi khuyen nghi cua he thong
OUTCOME_UNKNOWN = "UNKNOWN"
OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_ABORTED = "ABORTED"
OUTCOME_NOT_FLOWN = "NOT_FLOWN"

# Cac truong dau vao an toan — doi bat ky cai nao thi ban ghi het han
SAFETY_INPUTS = (
    "payload_g", "speed_commanded_ms", "altitude_m", "distance_2d_m",
    "wind_forecast_ms", "ambient_temp_c", "soc", "soh",
    "battery_type", "profile", "e_required_Wh",
)

# Cac module thuoc san pham D3 — INV-6 quet tren chinh chung
D3_MODULES = ("available_energy.py", "safety_invariants.py",
              "decision_rules.py", "workflow_state.py")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------

@dataclass
class MissionRecord:
    """
    Mot ban ghi nhiem vu — don vi du lieu ma moi buoc sau deu thao tac tren no.

    Thiet ke de TU NO LA DU: co ban ghi nay va tham so nen tang da cong bo thi
    tinh lai duoc dung phan quyet cu (P§4.2, RQ4).
    """
    mission_id: str
    created_at: str

    # Dau vao, dong bang tai thoi diem danh gia
    inputs: dict = field(default_factory=dict)

    # Dau ra
    verdict: str = ""
    reasons: list[str] = field(default_factory=list)
    e_available_Wh: float | None = None
    e_required_Wh: float | None = None
    margin_Wh: float | None = None
    margin_ratio: float | None = None
    r_min: float | None = None
    r_fly: float | None = None
    extrapolated: bool = False

    # Phien ban — thieu cai nao la mat kha nang tinh lai
    versions: dict = field(default_factory=dict)

    # Trang thai
    state: str = FRESH
    stale_reasons: list[str] = field(default_factory=list)

    # Ket cuc that, ghi DOC LAP. "UNKNOWN" la gia tri hop le va la mac dinh.
    outcome: str = OUTCOME_UNKNOWN
    outcome_note: str = ""

    @property
    def is_fresh(self) -> bool:
        return self.state == FRESH

    @property
    def may_proceed(self) -> bool:
        """
        Nhiem vu co duoc phep tien hanh khong.

        Het han thi KHONG, du phan quyet cu la FLY — P§4.2 doi phai tinh lai
        truoc khi tien hanh.
        """
        return self.is_fresh and self.verdict in ("FLY", "CONDITIONAL")

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent,
                          sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "MissionRecord":
        return cls(**json.loads(text))

    def __str__(self) -> str:
        dau = "" if self.is_fresh else "  [HET HAN]"
        return f"{self.mission_id}: {self.verdict}{dau}"


# ---------------------------------------------------------------------------

def evaluate(mission_id: str, protocol: dict | None = None,
             created_at: str | None = None, **inputs) -> MissionRecord:
    """
    Chay danh gia va dong goi thanh mot ban ghi nhiem vu.

    Moi tham so cua src.decision_rules.assess() deu truyen qua duoc.
    """
    protocol = protocol or load_protocol()
    d = assess(protocol=protocol, **inputs)

    day_du = {k: inputs.get(k) for k in SAFETY_INPUTS}
    day_du["profile"] = inputs.get("profile", PROFILE_STOCK)
    day_du["battery_type"] = inputs.get("battery_type", "TB47D")

    return MissionRecord(
        mission_id=mission_id,
        created_at=created_at or _now(),
        inputs=day_du,
        verdict=d.verdict,
        reasons=list(d.reasons),
        e_available_Wh=d.e_available_Wh,
        e_required_Wh=d.e_required_Wh,
        margin_Wh=d.margin_Wh,
        margin_ratio=d.margin_ratio,
        r_min=d.r_min,
        r_fly=d.r_fly,
        extrapolated=d.extrapolated,
        versions=capture_versions(protocol, d.reserve_factor),
    )


def capture_versions(protocol: dict | None = None,
                     reserve_factor: float | None = None) -> dict:
    """
    Chup lai phien ban cua moi thu anh huong toi phan quyet.

    Thieu mot muc o day la mat kha nang tinh lai — nen khi them tham so moi
    vao he thong, PHAI them vao day cung luc.
    """
    protocol = protocol or load_protocol()
    rv = protocol["reserve_and_verdict"]
    return {
        "protocol_version": protocol["meta"]["version"],
        "estimator": protocol["energy_required"]["estimator"],
        "uncertainty_allowance_Wh":
            protocol["energy_required"]["measured_error"]["p95_abs_residual_Wh"],
        "reserve_factor": (float(rv["reserve_factor"]["primary"])
                           if reserve_factor is None else float(reserve_factor)),
        "validity_envelope_m":
            protocol["energy_required"]["validity_envelope"]["distance_2d_m"],
        "e_nominal_Wh": protocol["available_energy"]["e_nominal"]["primary_Wh"],
        "kappa_range_c":
            protocol["available_energy"]["kappa_temperature"]["calibrated_range_c"],
    }


# ---------------------------------------------------------------------------
# Het han
# ---------------------------------------------------------------------------

def check_freshness(record: MissionRecord,
                    current_inputs: dict | None = None,
                    current_versions: dict | None = None,
                    protocol: dict | None = None) -> MissionRecord:
    """
    Doi chieu ban ghi voi tinh hinh HIEN TAI. Lech cho nao thi danh dau het han.

    Tra ve mot ban ghi MOI, khong sua ban ghi cu — de ban goc van tra cuu duoc.
    """
    protocol = protocol or load_protocol()
    ly_do: list[str] = []

    if current_inputs:
        for khoa, moi in current_inputs.items():
            if khoa not in SAFETY_INPUTS:
                raise ValueError(f"truong khong thuoc dau vao an toan: {khoa!r}")
            cu = record.inputs.get(khoa)
            if moi != cu:
                ly_do.append(f"{khoa}: {cu} -> {moi}")

    hien = current_versions or capture_versions(
        protocol, record.versions.get("reserve_factor"))
    for khoa, moi in hien.items():
        cu = record.versions.get(khoa)
        if moi != cu:
            ly_do.append(f"phien ban {khoa}: {cu} -> {moi}")

    moi_ban = MissionRecord(**asdict(record))
    if ly_do:
        moi_ban.state = STALE
        moi_ban.stale_reasons = ly_do
    return moi_ban


def recompute(record: MissionRecord, current_inputs: dict | None = None,
              protocol: dict | None = None) -> MissionRecord:
    """
    Tinh lai mot ban ghi het han, voi dau vao moi nhat. Giu nguyen mission_id.
    """
    protocol = protocol or load_protocol()
    dau_vao = dict(record.inputs)
    dau_vao.update(current_inputs or {})
    moi = evaluate(record.mission_id, protocol=protocol, **dau_vao)
    moi.outcome = record.outcome
    moi.outcome_note = record.outcome_note
    return moi


# ---------------------------------------------------------------------------
# Tinh lai tu ban ghi — INV-5
# ---------------------------------------------------------------------------

def replay(record: MissionRecord, protocol: dict | None = None) -> MissionRecord:
    """
    Dung lai phan quyet tu ban ghi da luu. INV-5.

    Day la tinh chat RQ4 khang dinh: ban ghi TU NO LA DU. Neu phien ban trong
    ban ghi khac phien ban hien tai thi ham nay van dung so trong ban ghi —
    do moi la "tinh lai dung cau hinh hom do".
    """
    protocol = protocol or load_protocol()
    r = record.versions.get("reserve_factor")
    moi = evaluate(record.mission_id, protocol=protocol,
                   created_at=record.created_at,
                   reserve_factor=r, **record.inputs)
    moi.outcome = record.outcome
    moi.outcome_note = record.outcome_note
    return moi


def replay_matches(record: MissionRecord, protocol: dict | None = None) -> bool:
    """Tinh lai co ra DUNG phan quyet cu khong."""
    lai = replay(record, protocol)
    return (lai.verdict == record.verdict
            and lai.reasons == record.reasons
            and _gan_bang(lai.margin_ratio, record.margin_ratio)
            and _gan_bang(lai.e_available_Wh, record.e_available_Wh))


def _gan_bang(a: float | None, b: float | None, eps: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b or a == b
    return abs(a - b) < eps


# ---------------------------------------------------------------------------
# Ket cuc that — ghi doc lap
# ---------------------------------------------------------------------------

def record_outcome(record: MissionRecord, outcome: str,
                   note: str = "") -> MissionRecord:
    """
    Ghi ket cuc THAT cua chuyen bay, doc lap voi khuyen nghi cua he thong.

    P§4.2 doi truong nay ton tai rieng de danh gia ve sau khong dung chinh phan
    quyet cua he thong lam su that nen. Vi vay ham nay KHONG suy ra ket cuc tu
    verdict — nguoi dung phai cung cap.
    """
    hop_le = (OUTCOME_UNKNOWN, OUTCOME_COMPLETED, OUTCOME_ABORTED,
              OUTCOME_NOT_FLOWN)
    if outcome not in hop_le:
        raise ValueError(f"ket cuc khong hop le: {outcome!r}; chi nhan {hop_le}")
    moi = MissionRecord(**asdict(record))
    moi.outcome = outcome
    moi.outcome_note = note
    return moi


# ---------------------------------------------------------------------------
# INV-6 — D3 khong duoc chua mo hinh hoc may
# ---------------------------------------------------------------------------

def scan_for_learned_models(modules: tuple[str, ...] = D3_MODULES) -> list[str]:
    """
    Quet ma nguon cac module D3, tra ve danh sach vi pham.

    Giao thuc muc 0 khai: `d3_contains_no_learned_model: true`. Day la phep
    kiem tinh bien khai do thanh dieu kiem duoc — D3 phai la cong thuc va luat,
    khong co gi duoc huan luyen.
    """
    cam = (
        (re.compile(r"\.fit\s*\("), "goi .fit()"),
        (re.compile(r"^\s*(from|import)\s+sklearn", re.M), "import sklearn"),
        (re.compile(r"\.predict\s*\("), "goi .predict()"),
    )
    vi_pham: list[str] = []
    for ten in modules:
        p = REPO_ROOT / "src" / ten
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        # Bo chu thich va docstring de khong bat nham van ban giai thich
        ma = _strip_comments(text)
        for mau, nhan in cam:
            if mau.search(ma):
                vi_pham.append(f"{ten}: {nhan}")
    return vi_pham


def _strip_comments(text: str) -> str:
    """
    Bo docstring, chu thich VA chuoi ky tu truoc khi quet.

    Bo chuoi ky tu la bat buoc: chinh file nay chua mau regex r"\\.fit\\s*\\("
    duoi dang chuoi, va neu khong bo thi phep quet se tu bao chinh no vi pham.
    """
    text = re.sub(r'"""(?:.|\n)*?"""', "", text)
    text = re.sub(r"'''(?:.|\n)*?'''", "", text)
    text = re.sub(r"#.*$", "", text, flags=re.M)
    text = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', text)
    text = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", text)
    return text


# ---------------------------------------------------------------------------

def _demo() -> None:
    goc = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50,
               distance_2d_m=472, wind_forecast_ms=3.0, ambient_temp_c=15,
               soc=0.30, soh=0.95, e_required_Wh=22.0)

    print("1. Danh gia luc 08:00\n")
    r = evaluate("M-2026-1015-001", created_at="2026-10-15T08:00:00+00:00", **goc)
    print(f"   {r}")
    print(f"   bien du tru {r.margin_ratio:+.1%}, duoc tien hanh: {r.may_proceed}")

    print("\n\n2. 08:30 — du bao gio cap nhat 3 -> 12 m/s\n")
    r2 = check_freshness(r, current_inputs={"wind_forecast_ms": 12.0})
    print(f"   trang thai: {r2.state}")
    for ly in r2.stale_reasons:
        print(f"     {ly}")
    print(f"   phan quyet cu van ghi: {r2.verdict}")
    print(f"   nhung duoc tien hanh: {r2.may_proceed}   <- day la diem mau chot")

    print("\n\n3. Tinh lai voi du lieu moi\n")
    r3 = recompute(r2, current_inputs={"wind_forecast_ms": 12.0})
    print(f"   {r3}")
    print(f"   {r3.reasons[0]}")

    print("\n\n4. Doi mo hinh cung lam het han\n")
    v = capture_versions()
    v["estimator"] = "D2_ridge_v2"
    r4 = check_freshness(r, current_versions=v)
    print(f"   trang thai: {r4.state}")
    for ly in r4.stale_reasons:
        print(f"     {ly}")

    print("\n\n5. Tinh lai tu ban ghi da luu (INV-5)\n")
    text = r.to_json()
    doc_lai = MissionRecord.from_json(text)
    print(f"   luu {len(text)} ky tu JSON, doc lai -> {doc_lai.verdict}")
    print(f"   tinh lai ra dung phan quyet cu: {replay_matches(doc_lai)}")

    print("\n\n6. Ket cuc that, ghi doc lap\n")
    print(f"   mac dinh: {r.outcome}  <- 'khong biet' la gia tri hop le")
    r6 = record_outcome(r, OUTCOME_COMPLETED, "ha canh 08:47, con 31 % pin")
    print(f"   sau khi ghi: {r6.outcome} — {r6.outcome_note}")

    print("\n\n7. Quet mo hinh hoc may trong D3 (INV-6)\n")
    vp = scan_for_learned_models()
    print(f"   vi pham: {vp if vp else 'khong co'}")

    print("\n\n8. Ban ghi day du\n")
    print("\n".join("   " + d for d in r.to_json().splitlines()[:16]))
    print("   ...")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        _demo()
    else:
        ap.print_help()
