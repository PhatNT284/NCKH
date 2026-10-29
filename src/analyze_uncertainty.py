"""Extract initial FLY decisions with simulated reserve shortfalls from a saved D5 run.

No Monte Carlo is rerun. Keep configurations and batteries separate and summarize
the range across seeds, including seeds with zero shortfalls. Never infer which
input caused a shortfall from joint-input draws alone.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["scenario_id", "aircraft_profile", "reserve_ratio", "battery_type", "assumption_config_id"]
COUNTS = ["draws_total", "valid_draws", "invalid_draws", "energy_success_count", "joint_success_count"]
CONTEXT = ["baseline_prediction_Wh", "baseline_available_Wh", "baseline_margin_Wh",
           "fixed_label_ref1", "fixed_label_ref2"]
INPUTS = ["payload_g", "speed_commanded_ms", "altitude_m", "distance_2d_m", "wind_forecast_ms",
          "soc", "soh", "ambient_temp_c", "stratum"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize_fly(rows):
    """Return every evaluated FLY case, preserving zero-shortfall seeds."""
    selected = rows[(rows.baseline_verdict == "FLY") & (rows.valid_draws > 0)].copy()
    selected["reserve_failure_count"] = selected.valid_draws - selected.energy_success_count
    selected["reserve_failure_fraction"] = selected.reserve_failure_count / selected.valid_draws
    selected["extra_veto_failure_count"] = selected.energy_success_count - selected.joint_success_count
    selected["joint_failure_fraction"] = 1 - selected.joint_success_count / selected.valid_draws
    selected["baseline_reserve_slack_Wh"] = selected.baseline_available_Wh - (1+selected.reserve_ratio)*selected.baseline_prediction_Wh
    grouped = selected.groupby(KEYS, sort=False, dropna=False)
    for name in CONTEXT:
        if (grouped[name].nunique(dropna=False) > 1).any():
            raise ValueError(f"Baseline context changes between seeds: {name}")
    cases = grouped.agg(
        seed_count=("seed", "nunique"), seeds_with_shortfall=("reserve_failure_count", lambda x: int((x > 0).sum())),
        failure_fraction_min=("reserve_failure_fraction", "min"), failure_fraction_max=("reserve_failure_fraction", "max"),
        failures_min=("reserve_failure_count", "min"), failures_max=("reserve_failure_count", "max"),
        valid_draws_min=("valid_draws", "min"), valid_draws_max=("valid_draws", "max"),
        joint_failure_fraction_max=("joint_failure_fraction", "max"),
        extra_veto_failures_max=("extra_veto_failure_count", "max"),
        baseline_reserve_slack_Wh=("baseline_reserve_slack_Wh", "first"),
        **{name: (name, "first") for name in CONTEXT}).reset_index()
    cases["seed_spread"] = cases.failure_fraction_max - cases.failure_fraction_min
    cases["has_reserve_shortfall"] = cases.failure_fraction_max > 0
    return selected, cases


def analyze(run, out, *, root=ROOT, top=20, chunksize=20000):
    run, out, root = Path(run), Path(out), Path(root)
    if out.exists():
        raise FileExistsError(f"Choose a new analysis directory: {out}")
    if top < 1:
        raise ValueError("top must be positive")
    status = json.loads((run / "run_status.json").read_text(encoding="utf-8"))
    if status["status"] != "COMPLETED_DEVELOPMENT_PARTIAL":
        raise ValueError("Source run must be completed")
    manifest_path = run / "input_manifest.json"
    if sha(manifest_path) != status["input_manifest_hash"]:
        raise ValueError("Source manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = run / "monte_carlo_fractions.csv"
    source_hash = sha(source)
    if source_hash != status["output_hashes"][source.name]:
        raise ValueError("Source CSV hash mismatch")
    scenario_relative = "reports/d4_scenarios_labelled.csv"
    if sha(root / scenario_relative) != manifest["input_hashes"][scenario_relative]:
        raise ValueError("D4 inputs changed since this run; use the historical source")
    columns = KEYS + COUNTS + CONTEXT + ["seed", "baseline_verdict", "status", "run_id", "input_manifest_hash"]
    seen, pieces, selected_ids = set(), [], set(manifest["selected_scenario_ids"])
    total_rows = total_draws = total_invalid = zero_valid_fly_rows = 0
    expected_seeds = set(manifest["seeds"])
    for chunk in pd.read_csv(source, usecols=columns, chunksize=chunksize):
        keys = set(chunk[KEYS+["seed"]].itertuples(index=False, name=None))
        if len(keys) != len(chunk) or seen.intersection(keys):
            raise ValueError("Duplicate result key")
        seen.update(keys)
        if (not set(chunk.scenario_id) <= selected_ids or not set(chunk.seed) <= expected_seeds
                or not set(chunk.battery_type) <= set(manifest["battery_types"])
                or not set(chunk.assumption_config_id) <= set(manifest["configurations"])
                or not (chunk.run_id == manifest["run_id"]).all()
                or not (chunk.input_manifest_hash == status["input_manifest_hash"]).all()):
            raise ValueError("Result metadata disagrees with source manifest")
        if not (chunk[COUNTS].notna().all().all() and (chunk[COUNTS] >= 0).all().all()
                and (chunk[COUNTS] % 1 == 0).all().all()
                and (chunk.valid_draws + chunk.invalid_draws == chunk.draws_total).all()
                and (chunk.joint_success_count <= chunk.energy_success_count).all()
                and (chunk.energy_success_count <= chunk.valid_draws).all()):
            raise ValueError("Inconsistent simulation counts")
        total_rows += len(chunk)
        total_draws += int(chunk.draws_total.sum())
        total_invalid += int(chunk.invalid_draws.sum())
        zero_valid_fly_rows += int(((chunk.baseline_verdict == "FLY") & (chunk.valid_draws == 0)).sum())
        pieces.append(chunk[chunk.baseline_verdict == "FLY"].copy())
    expected_rows = len(selected_ids)*len(expected_seeds)*len(manifest["battery_types"])*len(manifest["configurations"])
    if total_rows != expected_rows:
        raise ValueError(f"Incomplete source grid: {total_rows} vs expected {expected_rows}")
    fly = pd.concat(pieces, ignore_index=True)
    by_seed, all_cases = summarize_fly(fly)
    if len(all_cases) and not (all_cases.seed_count == len(expected_seeds)).all():
        raise ValueError("Missing valid seed coverage for at least one FLY case")
    scenarios = pd.read_csv(root / scenario_relative, usecols=["scenario_id"] + INPUTS)
    all_cases = all_cases.merge(scenarios, on="scenario_id", how="left", validate="many_to_one")
    if all_cases[INPUTS].isna().any().any():
        raise ValueError("A FLY case has no complete D4 inputs")
    failed = all_cases[all_cases.has_reserve_shortfall].copy()
    failed = failed.sort_values(["assumption_config_id", "battery_type", "failure_fraction_max", "scenario_id"],
                                ascending=[True, True, False, True])
    primary = failed[failed.assumption_config_id == "PRIMARY_INDEPENDENT"].copy()
    priority = primary.sort_values(["failure_fraction_max", "scenario_id", "battery_type"],
                                   ascending=[False, True, True]).head(top).copy()
    priority.insert(0, "rank", range(1, len(priority)+1))
    summaries = []
    for key, group in all_cases.groupby(["aircraft_profile", "reserve_ratio", "assumption_config_id", "battery_type"], sort=True):
        hit = group[group.has_reserve_shortfall]
        summaries.append(dict(aircraft_profile=key[0], reserve_ratio=key[1], assumption_config_id=key[2], battery_type=key[3],
                              initial_fly_cases=len(group), cases_with_shortfall=len(hit),
                              cases_with_shortfall_all_seeds=int((hit.seeds_with_shortfall == hit.seed_count).sum()),
                              fraction_of_fly_cases=len(hit)/len(group),
                              maximum_draw_failure_fraction=float(group.failure_fraction_max.max()),
                              maximum_seed_spread=float(group.seed_spread.max())))
    summary = pd.DataFrame(summaries)
    run_info = dict(source_run_id=manifest["run_id"], source_protocol_version=manifest["protocol_version"],
                    source_input_manifest_hash=status["input_manifest_hash"], source_csv_sha256=source_hash,
                    created_at_utc=datetime.now(timezone.utc).isoformat(), script_sha256=sha(Path(__file__)),
                    source_rows=total_rows, source_draws=total_draws, source_invalid_draws=total_invalid,
                    seed_values=manifest["seeds"], initial_fly_scenario_battery_cases=int(len(all_cases[all_cases.assumption_config_id == "PRIMARY_INDEPENDENT"])),
                    affected_primary_cases=len(primary), priority_case_count=len(priority),
                    zero_valid_fly_rows=zero_valid_fly_rows,
                    selection_rule="Initial verdict FLY, valid_draws > 0, valid_draws - energy_success_count > 0 in at least one seed",
                    ranking_rule="PRIMARY_INDEPENDENT only; max reserve-failure fraction across seeds descending; ties scenario_id then battery_type",
                    scope="Descriptive analysis of saved Monte Carlo; no resimulation, causal attribution, verdict flip evaluation or real-world failure probability")
    if sha(source) != source_hash:
        raise ValueError("Source results changed during analysis")
    out.mkdir(parents=True, exist_ok=False)
    tables = {
        "fly_case_summary.csv": summary,
        "fly_reserve_failures.csv": failed,
        "fly_priority_cases.csv": priority,
        "fly_reserve_failures_by_seed.csv": by_seed[by_seed.reserve_failure_count > 0].sort_values(KEYS+["seed"]),
    }
    for name, frame in tables.items():
        frame = frame.assign(source_run_id=manifest["run_id"], source_input_manifest_hash=status["input_manifest_hash"])
        frame.to_csv(out / name, index=False, encoding="utf-8-sig")
    def records(frame):
        return json.loads(frame.to_json(orient="records", force_ascii=False, double_precision=15))
    payload = dict(metadata=run_info, summary=records(summary), priority=records(priority),
                   all_primary_cases=records(primary), all_failed_case_count=len(failed))
    (out / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    lines = ["# Các ca FLY có lượt mô phỏng thiếu dự trữ", "",
             f"Nguồn: lần chạy `{manifest['run_id']}`, protocol {manifest['protocol_version']}.",
             f"Đã đọc {total_rows:,} dòng và {total_draws:,} lượt lấy mẫu; không chạy lại mô phỏng.", "",
             "Điều kiện lọc: quyết định ban đầu FLY, có mẫu hợp lệ và ít nhất một mẫu thiếu mức dự trữ yêu cầu.",
             "Mỗi ca là một scenario_id + hồ sơ + mức dự trữ + loại pin + cấu hình sai số. Khoảng thấp/cao được lấy qua các seed, bao gồm seed không có mẫu thiếu.",
             "Không gộp các cấu hình sai số hoặc pin thành một tỷ lệ chung.", "",
             "## Số ca theo cấu hình và pin", "",
             "| Cấu hình | Pin | Ca FLY ban đầu | Có mẫu thiếu | Có mẫu thiếu ở mọi seed |",
             "|---|---|---:|---:|---:|"]
    for row in summaries:
        lines.append(f"| {row['assumption_config_id']} | {row['battery_type']} | {row['initial_fly_cases']:,} | {row['cases_with_shortfall']:,} | {row['cases_with_shortfall_all_seeds']:,} |")
    lines += ["", "## Các ca cần xem trước", "",
              "Bảng này chỉ xếp các ca PRIMARY_INDEPENDENT theo tỷ lệ thiếu cao nhất qua các seed; đây là thứ tự để xem, chưa phải ngưỡng chấp nhận vận hành.", "",
              "| Hạng | ID | Pin | Tỷ lệ mẫu thiếu thấp nhất | Cao nhất | Seed có mẫu thiếu |",
              "|---:|---:|---|---:|---:|---:|"]
    for row in priority.to_dict("records"):
        lines.append(f"| {row['rank']} | {row['scenario_id']} | {row['battery_type']} | {row['failure_fraction_min']:.2%} | {row['failure_fraction_max']:.2%} | {row['seeds_with_shortfall']}/{row['seed_count']} |")
    lines += ["", "## Cách đọc và giới hạn", "",
              "- Tỷ lệ mẫu thiếu = (mẫu hợp lệ − mẫu đủ năng lượng và dự trữ) / mẫu hợp lệ, tính riêng mỗi seed.",
              "- Cột `baseline_reserve_slack_Wh` là năng lượng khả dụng trừ nhu cầu nhân (1 + reserve); nó khác margin thông thường trước khi trừ phần dự trữ.",
              "- Vi phạm VETO và thiếu dự trữ là hai điều khác nhau. `extra_veto_failures_max` chỉ đếm phần đã đủ dự trữ nhưng không qua VETO.",
              "- Có một lượt thiếu trong 10.000 lượt đủ để vào danh sách; điều này không tự xác lập một ngưỡng nguy hiểm hay độ tin cậy thống kê.",
              "- Các đầu vào SoC/SoH/gió/κ bị thay đổi cùng lúc trong nhánh chính. File tổng hợp hiện có không chứng minh yếu tố nào gây ra một lượt thiếu; cần phân tích từng yếu tố riêng để quy nguyên nhân.",
              "- Verdict ban đầu được giữ cố định trong D5. Đây là lượt thiếu dự trữ mô phỏng, chưa phải bằng chứng verdict đã đổi hay chuyến bay thực tế thất bại.",
              "- REF-1/REF-2 giữ nguyên nhãn gốc D4, kể cả khi đổi pin; chúng là nhãn simulation-derived.",
              "- Danh sách này là bước phân tích đầu tiên, chưa thay thế danh mục ca thất bại E4/E5 đầy đủ."]
    (out / "fly_reserve_review.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    run_info["output_hashes"] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out / "analysis_manifest.json").write_text(json.dumps(run_info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Saved {len(primary)} affected PRIMARY_INDEPENDENT cases and {len(priority)} priority cases to {out}")
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    analyze(args.run, args.out, top=args.top)


if __name__ == "__main__":
    main()
