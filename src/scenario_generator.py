"""
Bo sinh kich ban — buoc dau cua san pham D4 (§6/E3).

Sinh 6000 kich ban nhiem vu tai lap duoc tu configs/d4_protocol.yaml. Module nay
CHI sinh kich ban: no khong du bao nang luong, khong gan nhan tham chieu, khong
ra phan quyet. Ba viec do o src/reference_labeller.py, src/baselines_decision.py
va src/decision_rules.py.

Giu rieng nhu vay la CO Y. Neu bo sinh biet duoc du bao cua mo hinh thi no co
the (vo tinh) nan dai kich ban theo cho mo hinh lam tot — do la mot dang ro ri
nguoc, va khong ai phat hien duoc tu ket qua.

BON TANG KICH BAN — khai o giao thuc muc 1, `strata`:

    main              4200   lay mau trong dai co tai lieu do lung
    hard_rule_probe    700   CO Y vuot gioi han, de thu lop luat cung
    short_high         700   chuyen NGAN ma bay CAO — vung PH-1 rang buoc
    missing_input      400   thieu mot dau vao an toan, de do fail-closed

Tang `hard_rule_probe` KHONG duoc vao bang so sanh chinh. Ly do: so sanh cac
duong co so chi co nghia tren kich ban kha thi ve nguyen tac. Mot kich ban gio
16 m/s thi MOI phuong phap deu phai tu choi, dua vao bang chung chi lam loang
con so. No co bang rieng, do thuoc do M-7.

    python3 -m src.scenario_generator            # sinh ra reports/d4_scenarios.csv
    python3 -m src.scenario_generator --demo     # in 10 dong, khong ghi file
    python3 -m src.scenario_generator --check    # chi kiem GEN-1..GEN-5
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import qmc

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"

GENERATOR_VERSION = "1.0.0"

# Ten tang — dung lam gia tri cot `stratum`
S_MAIN = "main"
S_PROBE = "hard_rule_probe"
S_SHORT_HIGH = "short_high"
S_MISSING = "missing_input"

# Cot dau vao an toan co the bi bo trong o tang missing_input.
# Lay dung nhung cot ma §4.6 goi la safety-critical.
COT_AN_TOAN = ["soc", "soh", "ambient_temp_c", "wind_forecast_ms"]

# Thu tu cot trong file ra — co dinh de hash on dinh
COT_RA = [
    "scenario_id", "stratum",
    "payload_g", "speed_commanded_ms", "altitude_m", "distance_2d_m",
    "wind_forecast_ms", "soc", "soh", "ambient_temp_c",
    "extrapolated_distance", "extrapolated_wind",
    "extrapolated_soh", "extrapolated_temp",
    "hard_rule_probe", "probe_limit", "missing_field",
    "scenario_seed", "protocol_version", "generator_version",
]


def load_protocol() -> dict:
    with open(REPO_ROOT / "configs" / "d4_protocol.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Lay mau
# ---------------------------------------------------------------------------

def _lhs(n: int, d: int, seed: int) -> np.ndarray:
    """
    Latin hypercube tren [0,1)^d, tat dinh theo seed.

    Dung scipy.stats.qmc chu khong tu cai: tu cai thi de sai cho xao tron tung
    chieu doc lap, ma sai do khong lo ra ngoai — chi lam do phu te di mot cach
    im lang.
    """
    return qmc.LatinHypercube(d=d, seed=seed).random(n)


def _scale(u: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return lo + u * (hi - lo)


def _roi_rac(u: np.ndarray, values: list[float]) -> np.ndarray:
    """Anh xa [0,1) sang mot trong cac gia tri roi rac, chia deu."""
    idx = np.minimum((u * len(values)).astype(int), len(values) - 1)
    return np.asarray(values, dtype=float)[idx]


def _dai(protocol: dict, ten: str) -> list[float]:
    return protocol["scenario_generator"]["variables"][ten]["range"]


def _sinh_tang_probe(n: int, seed: int, protocol: dict) -> pd.DataFrame:
    """
    Tang `hard_rule_probe` — LUOI BOI SO cua gioi han nha san xuat.

    KHONG lay mau ngau nhien. Luat cung HR-1..HR-4 la nguong NHI PHAN: vuot la
    VETO, khong co muc do. Nen khong can lay mau mot dai — chi can vai diem
    tren nguong, va boi so cu the khong the doi bat ky thuoc do nao.

    Vi sao dieu do dang noi: no la ly do ba boi so 1.10/1.25/1.50 duoc phep la
    lua chon cua nhom. Mot con so cua nhom MA doi duoc ket qua thi phai co
    nguon hoac phai co do nhay — xem quyet dinh C12 (safety_k da bi bo) va C14
    (do rong vung bien, co do nhay S-4).

    Moi kich ban vuot DUNG MOT gioi han; hai gioi han con lai giu o giua dai
    an toan. Vuot mot cai moi biet luat NAO chan — vuot ca ba thi khong phan
    biet duoc.
    """
    cfg = protocol["scenario_generator"]["strata"][S_PROBE]
    boi_so = cfg["probe_multipliers"]
    gioi_han = cfg["limits_probed"]
    bien = protocol["scenario_generator"]["variables"]

    # Nen an toan: gia tri giua dai cua tung bien, de chi co MOT bien vuot
    nen = {ten: float(np.mean(mo_ta["range"]))
           for ten, mo_ta in bien.items() if "range" in mo_ta}

    to_hop = [(g["variable"], g["dji_limit"] * b)
              for g in gioi_han for b in boi_so]

    u = _lhs(n, 4, seed)
    dong = []
    for i in range(n):
        ten_bien, gia_tri = to_hop[i % len(to_hop)]
        d = dict(nen)
        # Bon bien khong lien quan toi gioi han van lay mau, de tang nay khong
        # phai n ban sao cua mot diem duy nhat
        d["soc"] = _scale(u[i, 0], *bien["soc"]["range"])
        d["soh"] = _scale(u[i, 1], *bien["soh"]["range"])
        d["ambient_temp_c"] = _scale(u[i, 2], *bien["ambient_temp_c"]["range"])
        d["distance_2d_m"] = _scale(u[i, 3], *bien["distance_2d_m"]["range"])
        d[ten_bien] = gia_tri
        d["altitude_m"] = float(bien["altitude_m"]["values"][
            i % len(bien["altitude_m"]["values"])])
        d["probe_limit"] = ten_bien
        dong.append(d)

    df = pd.DataFrame(dong)
    df["stratum"] = S_PROBE
    df["hard_rule_probe"] = True
    df["missing_field"] = None
    return df


def _sinh_mot_tang(n: int, seed: int, protocol: dict,
                   ten_tang: str,
                   ghi_de: dict | None = None) -> pd.DataFrame:
    """
    Sinh `n` kich ban cho mot tang.

    `ghi_de` cho phep tang thay dai cua mot vai bien (vi du tang probe vuot
    gioi han). Moi khoa trong `ghi_de` PHAI la ten bien co trong giao thuc —
    kiem o day de mot loi chinh ta khong bien thanh mot tang lay mau sai dai
    ma khong ai biet.
    """
    bien = protocol["scenario_generator"]["variables"]
    ghi_de = ghi_de or {}
    la = [k for k in ghi_de if k not in bien]
    if la:
        raise ValueError(f"ghi_de co bien khong co trong giao thuc: {la}")

    def dai(ten: str) -> list[float]:
        return ghi_de.get(ten, bien[ten].get("range"))

    u = _lhs(n, 7, seed)
    do_cao_values = ghi_de.get("altitude_m", bien["altitude_m"]["values"])

    df = pd.DataFrame({
        "payload_g": _scale(u[:, 0], *dai("payload_g")),
        "speed_commanded_ms": _scale(u[:, 1], *dai("speed_commanded_ms")),
        "distance_2d_m": _scale(u[:, 2], *dai("distance_2d_m")),
        "wind_forecast_ms": _scale(u[:, 3], *dai("wind_forecast_ms")),
        "soc": _scale(u[:, 4], *dai("soc")),
        "soh": _scale(u[:, 5], *dai("soh")),
        "ambient_temp_c": _scale(u[:, 6], *dai("ambient_temp_c")),
        "altitude_m": _roi_rac(_lhs(n, 1, seed + 1000)[:, 0], do_cao_values),
    })
    df["stratum"] = ten_tang
    df["hard_rule_probe"] = (ten_tang == S_PROBE)
    df["missing_field"] = None
    return df


# ---------------------------------------------------------------------------
# Co ngoai suy
# ---------------------------------------------------------------------------

def gan_co_ngoai_suy(df: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    """
    Dat bon co `extrapolated_*` tu gia tri, theo dung dieu kien khai o giao thuc.

    §6/E3 bat: "clearly label any extrapolated ranges". Hai co duoi day LUON
    True vi bo du lieu CMU khong he co hai bien do:

        extrapolated_soh   — bo du lieu khong co SoH
        extrapolated_temp  — bo du lieu khong ghi nhiet do moi truong
    """
    bien = protocol["scenario_generator"]["variables"]
    lo_d, hi_d = bien["distance_2d_m"]["envelope_supported"]
    lo_w, hi_w = bien["wind_forecast_ms"]["dataset_coverage"]

    out = df.copy()
    out["extrapolated_distance"] = ~out["distance_2d_m"].between(lo_d, hi_d)
    out["extrapolated_wind"] = ~out["wind_forecast_ms"].between(lo_w, hi_w)
    out["extrapolated_soh"] = True
    out["extrapolated_temp"] = True
    return out


# ---------------------------------------------------------------------------
# Sinh toan bo
# ---------------------------------------------------------------------------

def generate(protocol: dict | None = None) -> pd.DataFrame:
    """
    Sinh toan bo bo kich ban theo giao thuc. Tat dinh: cung seed -> cung bo.

    Moi tang dung mot seed DAN XUAT tu seed goc (`seed + offset` khai trong
    giao thuc) chu khong dung chung mot seed. Dung chung thi hai tang se lay
    cung mot chuoi quasi-random, tuc hai tang tuong quan voi nhau — mot loi im
    lang nua.
    """
    protocol = protocol or load_protocol()
    cfg = protocol["scenario_generator"]
    seed = cfg["seed"]
    phan = []

    for ten, spec in cfg["strata"].items():
        if ten == S_PROBE:
            df = _sinh_tang_probe(spec["n"], seed + spec["seed_offset"], protocol)
        else:
            df = _sinh_mot_tang(
                n=spec["n"],
                seed=seed + spec["seed_offset"],
                protocol=protocol,
                ten_tang=ten,
                ghi_de=spec.get("range_overrides"),
            )
        phan.append(df)

    df = pd.concat(phan, ignore_index=True)

    # Tang missing_input: bo trong MOT dau vao an toan, chia deu qua bon cot.
    # Bo trong deterministic theo chi so, khong rut tham — de tai lap duoc va
    # de bao dam ca bon cot deu duoc thu.
    mask = df["stratum"] == S_MISSING
    idx = df.index[mask]
    for i, ix in enumerate(idx):
        cot = COT_AN_TOAN[i % len(COT_AN_TOAN)]
        df.at[ix, cot] = np.nan
        df.at[ix, "missing_field"] = cot

    df = gan_co_ngoai_suy(df, protocol)

    df.insert(0, "scenario_id", range(1, len(df) + 1))
    df["scenario_seed"] = seed
    df["protocol_version"] = protocol["meta"]["version"]
    df["generator_version"] = GENERATOR_VERSION

    return df[COT_RA]


def hash_bo_kich_ban(df: pd.DataFrame) -> str:
    """
    Hash on dinh cua bo kich ban — dung cho GEN-1 (tat dinh).

    Lam tron 9 chu so thap phan truoc khi hash: so thuc co the lech bit cuoi
    giua cac phien ban numpy, ma GEN-1 muon kiem tat dinh cua BO SINH chu khong
    phai cua bo xu ly so hoc.
    """
    s = df.round(9).to_csv(index=False).encode("utf-8")
    return hashlib.sha256(s).hexdigest()


# ---------------------------------------------------------------------------
# GEN-1..GEN-5 — kiem truoc khi tin bat ky ket qua nao
# ---------------------------------------------------------------------------

def _gen1(protocol: dict) -> tuple[int, int]:
    """Cung seed -> cung bo, tung bit."""
    a = hash_bo_kich_ban(generate(protocol))
    b = hash_bo_kich_ban(generate(protocol))
    return 1, int(a != b)


def _gen2(protocol: dict, df: pd.DataFrame) -> tuple[int, int]:
    """
    Moi kich ban nam trong dai khai bao CUA TANG CUA NO.

    Tang `hard_rule_probe` kiem bang luat khac: no CO Y vuot gioi han, nen
    kiem xem no vuot DUNG MOT gioi han va dung boi so da khai.
    """
    cfg = protocol["scenario_generator"]
    bien = cfg["variables"]
    so_tr = so_vp = 0

    for ten, spec in cfg["strata"].items():
        phan = df[df["stratum"] == ten]

        if ten == S_PROBE:
            boi_so = spec["probe_multipliers"]
            hop_le = {g["variable"]: {round(g["dji_limit"] * b, 6)
                                      for b in boi_so}
                      for g in spec["limits_probed"]}
            for row in phan.itertuples():
                so_tr += 1
                bien_vuot = row.probe_limit
                if bien_vuot not in hop_le:
                    so_vp += 1
                    continue
                # Dung mot trong cac boi so da khai
                if round(getattr(row, bien_vuot), 6) not in hop_le[bien_vuot]:
                    so_vp += 1
                    continue
                # Va dung MOT bien vuot, khong phai nhieu
                dem = sum(
                    1 for g in spec["limits_probed"]
                    if getattr(row, g["variable"]) > g["dji_limit"])
                if dem != 1:
                    so_vp += 1
            continue

        ghi_de = spec.get("range_overrides") or {}
        for ten_bien, mo_ta in bien.items():
            dai = ghi_de.get(ten_bien, mo_ta.get("range"))
            if dai is None:                 # bien roi rac
                hop_le = set(ghi_de.get(ten_bien, mo_ta["values"]))
                cot = phan[ten_bien].dropna()
                so_tr += len(cot)
                so_vp += int((~cot.isin(hop_le)).sum())
                continue
            cot = phan[ten_bien].dropna()
            so_tr += len(cot)
            so_vp += int((~cot.between(dai[0], dai[1])).sum())
    return so_tr, so_vp


def _gen3(protocol: dict, df: pd.DataFrame) -> tuple[int, int]:
    """Co ngoai suy dat dung — tinh lai tu gia tri roi so voi cot da luu."""
    lai = gan_co_ngoai_suy(df, protocol)
    co = ["extrapolated_distance", "extrapolated_wind",
          "extrapolated_soh", "extrapolated_temp"]
    so_vp = int(sum((lai[c] != df[c]).sum() for c in co))
    return len(df) * len(co), so_vp


def _gen4a(protocol: dict, df: pd.DataFrame) -> tuple[int, int]:
    """
    Do phu COV-1, COV-2, COV-4 — nhung yeu cau tinh duoc TU TRUONG THO.

    COV-3 (vung bien) KHONG kiem o day: vung bien dinh nghia theo R = M /
    E_required, ma E_required la dau ra mo hinh. Bo sinh khong biet no, va cung
    khong duoc biet. COV-3 kiem o buoc gan nhan — GEN-4b.
    """
    yc = {c["id"]: c for c in protocol["scenario_generator"]["mandatory_coverage"]
          if c["verified_by"] == "GEN-4a"}
    so_vp = 0

    n1 = int(df["hard_rule_probe"].sum())
    if n1 < yc["COV-1"]["min_count"]:
        so_vp += 1

    bien = protocol["scenario_generator"]["variables"]
    lo_d = bien["distance_2d_m"]["envelope_supported"][0]
    n2 = int(((df["distance_2d_m"] < lo_d) & (df["altitude_m"] >= 75)).sum())
    if n2 < yc["COV-2"]["min_count"]:
        so_vp += 1

    n4 = int(df["missing_field"].notna().sum())
    if n4 < yc["COV-4"]["min_count"]:
        so_vp += 1

    return len(yc), so_vp


def _gen5(protocol: dict, df: pd.DataFrame) -> tuple[int, int]:
    """
    Khong cot nao trong bo kich ban la nang luong — quy uoc ngan sach B9.

    Bo sinh KHONG duoc sinh san truong `e_required_Wh`. Neu no sinh thi se co
    nguoi cong them khoan ha canh vao do, dung cai loi ma B9 dung de chan.
    """
    xau = [c for c in df.columns if "_Wh" in c or "energy" in c.lower()]
    return 1, int(bool(xau))


def run_generator_checks(protocol: dict | None = None,
                         df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Chay nhung phep kiem bo sinh ma giao thuc khai la `verified_at: generator`.

    Danh sach doc TU GIAO THUC, khong viet cung. O san pham D3 danh sach bat
    bien tung duoc viet cung o nam cho va da lech ba lan, lan nao cung im lang.
    Khong lap lai o D4.
    """
    protocol = protocol or load_protocol()
    df = generate(protocol) if df is None else df

    ham = {
        "GEN-1": lambda: _gen1(protocol),
        "GEN-2": lambda: _gen2(protocol, df),
        "GEN-3": lambda: _gen3(protocol, df),
        "GEN-4a": lambda: _gen4a(protocol, df),
        "GEN-5": lambda: _gen5(protocol, df),
    }

    khai = [t["id"] for t in protocol["generator_invariants"]["tests"]
            if t["verified_at"] == "generator"]
    ten = {t["id"]: t["statement"]
           for t in protocol["generator_invariants"]["tests"]}

    thieu_ham = [i for i in khai if i not in ham]
    if thieu_ham:
        raise RuntimeError(
            f"Giao thuc khai {thieu_ham} nhung khong co ham kiem. Them ham vao "
            f"src/scenario_generator.py, hoac bo khoi giao thuc. KHONG duoc de "
            f"giao thuc noi mot dang va bang chung noi mot dang.")

    thieu_khai = [i for i in ham if i not in khai]
    if thieu_khai:
        raise RuntimeError(
            f"Co ham kiem cho {thieu_khai} nhung giao thuc khong khai o buoc "
            f"generator. Them vao `generator_invariants.tests`.")

    kq = []
    for ma in khai:
        so_tr, so_vp = ham[ma]()
        kq.append({"check": ma, "noi_dung": ten[ma],
                   "so_truong_hop": so_tr, "vi_pham": so_vp,
                   "ket_qua": "DAT" if so_vp == 0 else "KHONG DAT"})
    return pd.DataFrame(kq)


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="in 10 dong, khong ghi file")
    ap.add_argument("--check", action="store_true", help="chi chay GEN-*")
    args = ap.parse_args()

    protocol = load_protocol()
    cfg = protocol["scenario_generator"]

    print(f"Giao thuc D4 {protocol['meta']['version']}, seed {cfg['seed']}")
    print(f"Bon tang: " + ", ".join(
        f"{k} {v['n']}" for k, v in cfg["strata"].items()))
    print()

    df = generate(protocol)

    if args.demo:
        print(df.head(10).to_string(index=False))
        return

    print("Kiem bo sinh ...")
    kiem = run_generator_checks(protocol, df)
    print(kiem.to_string(index=False))
    print(f"\n  Hash bo kich ban: {hash_bo_kich_ban(df)[:16]}")

    if args.check:
        return

    if (kiem["vi_pham"] > 0).any():
        raise SystemExit(
            "\nCO PHEP KIEM KHONG DAT — KHONG ghi file. Sua bo sinh hoac giao "
            "thuc truoc, dung chay tiep voi bo kich ban sai.")

    print("\n" + "=" * 62)
    print("DO PHU")
    print("=" * 62)
    print(df["stratum"].value_counts().to_string())
    print(f"\n  ngoai envelope cu ly : {int(df.extrapolated_distance.sum())}")
    print(f"  ngoai dai gio du lieu: {int(df.extrapolated_wind.sum())}")
    print(f"  thieu dau vao        : {int(df.missing_field.notna().sum())}")

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / "d4_scenarios.csv"
    df.to_csv(out, index=False)
    kiem.to_csv(REPORTS / "d4_generator_check.csv", index=False)
    print(f"\nDa ghi {len(df)} kich ban vao {out.relative_to(REPO_ROOT)}")
    print(f"Da ghi bang kiem vao reports/d4_generator_check.csv")
    print("\nCHUA GAN NHAN. Nhan tham chieu cho Duy ky — xem OI-D4-1.")


if __name__ == "__main__":
    main()
