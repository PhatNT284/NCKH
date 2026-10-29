"""Export validated D6 JSON records to a human-readable Excel workbook.

Uses Node.js and @oai/artifact-tool from the Codex workspace runtime.
Override their locations with D6_NODE and D6_ARTIFACT_NODE_MODULES.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess


def export_tables(records, output):
    from src.mission_schema import read_record

    records, output = Path(records).resolve(), Path(output).resolve()
    if output.suffix.lower() != ".xlsx":
        raise ValueError("Excel output must end in .xlsx")
    for target in (output,):
        if target.exists():
            raise FileExistsError(f"Output already exists: {target}")
    paths = sorted(records.glob("*.json")) if records.is_dir() else [records]
    if not paths:
        raise ValueError(f"No D6 records found: {records}")
    for path in paths:
        read_record(path)  # Verify schema and embedded checksums before exporting.
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    node = os.environ.get("D6_NODE") or (str(bundled) if bundled.is_file() else shutil.which("node"))
    if not node:
        raise RuntimeError("Excel export requires Node.js; set D6_NODE to its executable")
    script = Path(__file__).with_name("d6_excel.mjs")
    result = subprocess.run([node, str(script), str(records), str(output)],
                            capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"D6 Excel export failed: {result.stderr or result.stdout}")
    if not output.is_file():
        raise RuntimeError("D6 export did not produce Excel")
    return (output,)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in export_tables(args.records, args.out):
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
