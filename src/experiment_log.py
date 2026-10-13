"""
Nhat ky thi nghiem (§8 muc 6).

Thay yeu cau luu: phien ban bo du lieu, seed ngau nhien, cau hinh mo hinh,
danh sach dac trung, duong dan dau ra.

`configs/d2_protocol.yaml` ghi KE HOACH. File nay ghi LICH SU CHAY: moi lan
chay thuc te noi them mot ban ghi vao `reports/experiment_log.jsonl`.

Dinh dang JSONL (moi dong mot ban ghi JSON) de vua doc bang mat vua doc bang
code, va de noi them ma khong phai doc lai ca file.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = REPO_ROOT / "reports" / "experiment_log.jsonl"


def file_sha256(path: Path, max_bytes: int | None = None) -> str | None:
    """
    Bam file de dinh danh phien ban bo du lieu.

    `max_bytes` bam phan dau file thay vi toan bo — dung cho flights.csv 107 MB
    khi khong can dam bao tuyet doi. De None thi bam toan bo.
    """
    if not path.exists():
        return None
    h = hashlib.sha256()
    read = 0
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            if max_bytes is not None and read + len(block) > max_bytes:
                h.update(block[: max_bytes - read])
                break
            h.update(block)
            read += len(block)
    return h.hexdigest()


def git_commit() -> str | None:
    """Ma commit hien tai, de truy nguoc dung phien ban ma nguon."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def log_run(experiment: str, *, seed: int, n_flights: int,
            features: list[str] | None = None,
            models: list[str] | None = None,
            config: dict | None = None,
            outputs: list[str] | None = None,
            data_path: Path | str | None = None,
            notes: str | None = None) -> dict:
    """Noi mot ban ghi vao nhat ky. Tra ve chinh ban ghi do."""
    data_path = Path(data_path) if data_path else None

    record = {
        "thoi_diem": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "thi_nghiem": experiment,
        "seed": seed,
        "so_chuyen_bay": n_flights,
        "du_lieu": {
            "duong_dan": str(data_path) if data_path else None,
            "sha256": file_sha256(data_path) if data_path else None,
        },
        "dac_trung": features,
        "mo_hinh": models,
        "cau_hinh": config,
        "dau_ra": outputs,
        "ma_nguon": {
            "git_commit": git_commit(),
            "python": platform.python_version(),
        },
        "ghi_chu": notes,
    }

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_log() -> list[dict]:
    """Doc toan bo nhat ky."""
    if not LOG_PATH.exists():
        return []
    with open(LOG_PATH, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def print_log(limit: int = 20) -> None:
    """In nhat ky dang bang cho de doc."""
    records = read_log()
    if not records:
        print("Nhat ky trong. Chay mot thi nghiem truoc.")
        return
    print(f"{'thoi diem (UTC)':<27}{'thi nghiem':<16}{'seed':>6}{'n':>6}  dau ra")
    print("-" * 96)
    for r in records[-limit:]:
        outs = ", ".join(Path(o).name for o in (r.get("dau_ra") or []))
        print(f"{r['thoi_diem']:<27}{r['thi_nghiem']:<16}"
              f"{r['seed']:>6}{r['so_chuyen_bay']:>6}  {outs[:40]}")
    print()
    print(f"Tong {len(records)} lan chay — {LOG_PATH}")


if __name__ == "__main__":
    print_log()
