"""
Doc va kiem tra du lieu goc (§4.2 buoc 1-2).

Chay truoc tien de xem flights.csv thuc su co nhung cot gi:

    python -m src.data_ingestion --inspect

Doi chieu ket qua voi configs/dataset.yaml roi sua muc `columns` cho khop.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "dataset.yaml"


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict:
    """Doc file cau hinh anh xa cot."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _resolve(relative: str) -> Path:
    """Duong dan tuong doi trong config -> duong dan tuyet doi tu goc repo."""
    p = Path(relative)
    return p if p.is_absolute() else REPO_ROOT / p


def load_parameters(cfg: dict | None = None) -> pd.DataFrame:
    """Doc parameters.csv va doi ten cot ve ten noi bo."""
    cfg = cfg or load_config()
    path = _resolve(cfg["paths"]["parameters"])
    if not path.exists():
        raise FileNotFoundError(
            f"Khong tim thay {path}.\n"
            "Tai bo du lieu tu https://doi.org/10.1184/R1/12683453 "
            "va dat vao data/raw/."
        )
    df = pd.read_csv(path)
    rename = {v: k for k, v in cfg["parameter_columns"].items() if v in df.columns}
    return df.rename(columns=rename)


def iter_flights(cfg: dict | None = None, chunksize: int = 500_000):
    """
    Doc flights.csv theo tung khoi va gom lai thanh tung chuyen bay.

    flights.csv khoang 102 MB nen doc theo khoi de khong an het bo nho tren
    may yeu. Tra ve lan luot (flight_id, DataFrame cua chuyen do), voi cot da
    doi ve ten noi bo.

    Chuyen bay duoc gom day du truoc khi tra ve: mot chuyen co the nam vat
    qua hai khoi, nen phan duoi cung cua moi khoi duoc giu lai de ghep voi
    khoi ke tiep.
    """
    cfg = cfg or load_config()
    path = _resolve(cfg["paths"]["flights"])
    if not path.exists():
        raise FileNotFoundError(
            f"Khong tim thay {path}.\n"
            "Tai flights.csv tu https://doi.org/10.1184/R1/12683453 "
            "va dat vao data/raw/. File nay ~102 MB va KHONG commit vao repo."
        )

    colmap = cfg["columns"]
    rename = {v: k for k, v in colmap.items()}
    flight_col = colmap["flight"]

    # Cot `altitude` trong flights.csv lan ca kieu chu va so, gay DtypeWarning.
    # Doc no nhu chuoi cho nhat quan; tham so nhiem vu lay tu parameters.csv
    # chu khong lay tu day, nen khong anh huong gi.
    carry: pd.DataFrame | None = None
    for chunk in pd.read_csv(path, chunksize=chunksize, dtype={"altitude": "string"}):
        chunk = chunk.rename(columns={k: v for k, v in rename.items() if k in chunk.columns})
        if carry is not None:
            chunk = pd.concat([carry, chunk], ignore_index=True)
        ids = chunk["flight"].unique()
        # Chuyen cuoi cung co the con tiep o khoi sau -> giu lai
        for fid in ids[:-1]:
            yield fid, chunk[chunk["flight"] == fid].copy()
        carry = chunk[chunk["flight"] == ids[-1]].copy()

    if carry is not None and len(carry):
        yield carry["flight"].iloc[0], carry


# ---------------------------------------------------------------------------
# Kiem tra chat luong (§4.2 buoc 2)
# ---------------------------------------------------------------------------

def check_flight_quality(df: pd.DataFrame) -> dict:
    """
    Kiem mot chuyen bay. Tra ve dict cac van de tim thay — rong nghia la sach.

    Kiem: moc thoi gian tang dan, mau trung lap, gia tri thieu, dien ap va
    dong dien nam trong dai hop ly.
    """
    issues: dict[str, object] = {}

    if "time" in df:
        t = df["time"]
        if not t.is_monotonic_increasing:
            issues["timestamp_not_monotonic"] = int((t.diff() < 0).sum())
        if t.duplicated().any():
            issues["duplicate_timestamps"] = int(t.duplicated().sum())

    for col in ("voltage", "current"):
        if col in df:
            n_missing = int(df[col].isna().sum())
            if n_missing:
                issues[f"{col}_missing"] = n_missing

    if "voltage" in df and len(df):
        v = df["voltage"].dropna()
        # M100 dung pin 6S: khoang hop ly ~18-26 V
        if len(v) and (v.min() < 10 or v.max() > 30):
            issues["voltage_out_of_range"] = (float(v.min()), float(v.max()))

    if "current" in df and len(df):
        c = df["current"].dropna()
        if len(c) and c.median() < 1.0:
            issues["current_sensor_suspect"] = float(c.median())

    return issues


def inspect(cfg: dict | None = None, n_preview: int = 3) -> None:
    """In ra cau truc that su cua cac file goc, de doi chieu voi dataset.yaml."""
    cfg = cfg or load_config()

    print("=" * 70)
    print("PARAMETERS.CSV")
    print("=" * 70)
    ppath = _resolve(cfg["paths"]["parameters"])
    if ppath.exists():
        params = pd.read_csv(ppath)
        print(f"Kich thuoc: {params.shape[0]} dong x {params.shape[1]} cot")
        print(f"Cot: {list(params.columns)}")
        print(params.head(n_preview).to_string())
    else:
        print(f"KHONG TIM THAY: {ppath}")

    print()
    print("=" * 70)
    print("FLIGHTS.CSV")
    print("=" * 70)
    fpath = _resolve(cfg["paths"]["flights"])
    if not fpath.exists():
        print(f"KHONG TIM THAY: {fpath}")
        return

    head = pd.read_csv(fpath, nrows=2000)
    print(f"Kich thuoc file: {fpath.stat().st_size / 1e6:.1f} MB")
    print(f"So cot: {head.shape[1]}")
    print(f"Cot: {list(head.columns)}")
    print()
    print(head.head(n_preview).to_string())
    print()

    expected = set(cfg["columns"].values())
    actual = set(head.columns)
    missing = expected - actual
    print("-" * 70)
    if missing:
        print("CANH BAO — cot khai trong dataset.yaml nhung KHONG co trong file:")
        for m in sorted(missing):
            print(f"  - {m}")
        print()
        print("Sua muc `columns` trong configs/dataset.yaml cho khop ten that.")
    else:
        print("OK — moi cot khai trong dataset.yaml deu co trong flights.csv.")

    extra = actual - expected
    if extra:
        print()
        print(f"Cot co trong file nhung chua khai ({len(extra)}): {sorted(extra)}")


def check_frame(cfg: dict | None = None, n_rows: int = 200_000) -> None:
    """
    Kiem he quy chieu van toc — position_x la huong dong hay huong bac.

    d2_report.md ghi nhan ket qua la `x_east`. Lenh nay tai lap phep kiem do:
    so sanh dao ham cua vi tri voi cot van toc tuong ung.
    """
    cfg = cfg or load_config()
    fpath = _resolve(cfg["paths"]["flights"])
    df = pd.read_csv(fpath, nrows=n_rows)
    rename = {v: k for k, v in cfg["columns"].items()}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    need = {"time", "position_x", "position_y", "velocity_x", "velocity_y", "flight"}
    if not need.issubset(df.columns):
        print(f"Thieu cot, khong kiem duoc. Can: {sorted(need)}")
        return

    g = df[df["flight"] == df["flight"].iloc[0]].copy()
    dt = g["time"].diff()
    dx = g["position_x"].diff() / dt
    dy = g["position_y"].diff() / dt
    ok = dt.notna() & (dt > 0)

    print("Tuong quan giua dao ham vi tri va cot van toc:")
    print(f"  d(position_x)/dt  vs velocity_x : {dx[ok].corr(g['velocity_x'][ok]):+.3f}")
    print(f"  d(position_x)/dt  vs velocity_y : {dx[ok].corr(g['velocity_y'][ok]):+.3f}")
    print(f"  d(position_y)/dt  vs velocity_x : {dy[ok].corr(g['velocity_x'][ok]):+.3f}")
    print(f"  d(position_y)/dt  vs velocity_y : {dy[ok].corr(g['velocity_y'][ok]):+.3f}")
    print()
    print("Duong cheo cao -> truc khop nhau truc tiep (x_east theo d2_report.md).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Doc va kiem tra du lieu goc CMU")
    ap.add_argument("--inspect", action="store_true",
                    help="in cau truc that su cua flights.csv va parameters.csv")
    ap.add_argument("--check-frame", action="store_true",
                    help="kiem he quy chieu van toc (x_east hay x_north)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.check_frame:
        check_frame(cfg)
    else:
        inspect(cfg)


if __name__ == "__main__":
    main()