"""
Unit test cho phan trich dac trung cap chuyen bay va cho giao thuc da dong bang.

Nhom test cuoi (TestProtocolIntegrity) khong kiem code ma kiem FILE CAU HINH:
no chan viec vo tinh dua bien hau nghiem vao mo hinh du bao. Day la loai loi
khong lam chuong trinh bao sai, chi lam ket qua sai — nen phai co test.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.features import (
    VALID_ALTITUDES, VALID_PAYLOADS, apply_exclusions, trajectory_features,
    wind_features,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestTrajectoryFeatures:
    def test_straight_line_2d(self):
        # Di thang 100 m doc truc x
        df = pd.DataFrame({
            "time": np.arange(11, dtype=float),
            "position_x": np.linspace(0, 100, 11),
            "position_y": np.zeros(11),
            "position_z": np.zeros(11),
        })
        f = trajectory_features(df)
        assert f["distance_2d_m"] == pytest.approx(100.0)
        assert f["distance_3d_m"] == pytest.approx(100.0)
        assert f["climb_m"] == pytest.approx(0.0)

    def test_diagonal_uses_pythagoras(self):
        # 3-4-5: di 30 m theo x va 40 m theo y -> 50 m
        df = pd.DataFrame({
            "time": [0.0, 1.0],
            "position_x": [0.0, 30.0],
            "position_y": [0.0, 40.0],
            "position_z": [0.0, 0.0],
        })
        assert trajectory_features(df)["distance_2d_m"] == pytest.approx(50.0)

    def test_3d_longer_than_2d_when_climbing(self):
        df = pd.DataFrame({
            "time": [0.0, 1.0],
            "position_x": [0.0, 30.0],
            "position_y": [0.0, 40.0],
            "position_z": [0.0, 120.0],
        })
        f = trajectory_features(df)
        assert f["distance_2d_m"] == pytest.approx(50.0)
        assert f["distance_3d_m"] == pytest.approx(130.0)   # 5-12-13

    def test_climb_and_descent_separated(self):
        # Len 50 m roi xuong 30 m
        df = pd.DataFrame({
            "time": [0.0, 1.0, 2.0],
            "position_x": [0.0, 0.0, 0.0],
            "position_y": [0.0, 0.0, 0.0],
            "position_z": [0.0, 50.0, 20.0],
        })
        f = trajectory_features(df)
        assert f["climb_m"] == pytest.approx(50.0)
        assert f["descent_m"] == pytest.approx(30.0)

    def test_out_and_back_counts_both_legs(self):
        # Di 100 m roi quay ve -> tong duong di 200 m, khong phai 0
        df = pd.DataFrame({
            "time": [0.0, 1.0, 2.0],
            "position_x": [0.0, 100.0, 0.0],
            "position_y": [0.0, 0.0, 0.0],
            "position_z": [0.0, 0.0, 0.0],
        })
        assert trajectory_features(df)["distance_2d_m"] == pytest.approx(200.0)

    def test_missing_columns_returns_nan(self):
        f = trajectory_features(pd.DataFrame({"time": [0.0, 1.0]}))
        assert np.isnan(f["distance_2d_m"])


class TestWindFeatures:
    def test_mean_of_constant(self):
        df = pd.DataFrame({"wind_speed": [4.0] * 10})
        assert wind_features(df)["wind_raw_mean_ms"] == pytest.approx(4.0)

    def test_direction_averaged_on_circle(self):
        # 350 do va 10 do: trung binh so hoc cho 180 (sai), trung binh vong tron cho 0
        df = pd.DataFrame({"wind_angle": [350.0, 10.0]})
        got = wind_features(df)["wind_dir_mean_deg"]
        assert min(got, 360 - got) == pytest.approx(0.0, abs=1e-6)

    def test_missing_wind_returns_nan(self):
        assert np.isnan(wind_features(pd.DataFrame({"time": [0.0]}))["wind_raw_mean_ms"])


class TestExclusions:
    @staticmethod
    def _params(rows):
        return pd.DataFrame(rows)

    def test_hover_and_idle_routes_removed(self):
        p = self._params([
            {"flight": 1, "route": "R1", "altitude": 25, "payload": 0},
            {"flight": 2, "route": "H1", "altitude": 25, "payload": 0},
            {"flight": 3, "route": "A2", "altitude": 25, "payload": 0},
        ])
        kept, log = apply_exclusions(p, {})
        assert set(kept["flight"]) == {1}
        assert len(log) == 2

    def test_off_grid_altitude_removed(self):
        p = self._params([
            {"flight": 1, "route": "R1", "altitude": 25, "payload": 0},
            {"flight": 2, "route": "R1", "altitude": 60, "payload": 0},
        ])
        kept, log = apply_exclusions(p, {})
        assert set(kept["flight"]) == {1}
        assert "do cao" in log.iloc[0]["reason"]

    def test_off_grid_payload_removed(self):
        p = self._params([
            {"flight": 1, "route": "R1", "altitude": 25, "payload": 250},
            {"flight": 2, "route": "R1", "altitude": 25, "payload": 100},
        ])
        kept, _ = apply_exclusions(p, {})
        assert set(kept["flight"]) == {1}

    def test_every_exclusion_is_logged(self):
        # Khong duoc loai chuyen nao ma khong ghi ly do (tieu chi D1)
        p = self._params([
            {"flight": i, "route": r, "altitude": a, "payload": pl}
            for i, (r, a, pl) in enumerate([
                ("R1", 25, 0), ("H1", 25, 0), ("R1", 60, 0), ("R1", 25, 123),
            ], start=1)
        ])
        kept, log = apply_exclusions(p, {})
        assert len(kept) + len(log) == len(p)

    def test_valid_grids_match_dataset_design(self):
        assert VALID_ALTITUDES == {25.0, 50.0, 75.0, 100.0}
        assert VALID_PAYLOADS == {0.0, 250.0, 500.0}


class TestProtocolIntegrity:
    """
    Kiem configs/d2_protocol.yaml — chan loi ro ri dac trung.

    Day la test quan trong nhat trong file: no bat loi ma chuong trinh van
    chay binh thuong nhung ket qua thi vo nghia.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def protocol():
        with open(REPO_ROOT / "configs" / "d2_protocol.yaml", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def test_protocol_loads(self, protocol):
        assert protocol["meta"]["deliverable"] == "D2"

    def test_no_forbidden_column_in_preflight_set(self, protocol):
        forbidden = {e["column"] for e in protocol["features"]["forbidden"]}
        leaked = forbidden & set(protocol["features"]["preflight"])
        assert not leaked, f"Bien hau nghiem lot vao tap preflight: {leaked}"

    def test_no_forbidden_column_in_as_written_set(self, protocol):
        forbidden = {e["column"] for e in protocol["features"]["forbidden"]}
        leaked = forbidden & set(protocol["features"]["as_written"])
        assert not leaked, f"Bien hau nghiem lot vao tap as_written: {leaked}"

    def test_energy_per_metre_is_forbidden(self, protocol):
        # Cot nay tinh truc tiep tu chinh cot muc tieu — ro ri trang tron
        forbidden = {e["column"] for e in protocol["features"]["forbidden"]}
        assert "energy_per_metre_J" in forbidden

    def test_measured_duration_only_in_as_written(self, protocol):
        assert "duration_s" in protocol["features"]["as_written"]
        assert "duration_s" not in protocol["features"]["preflight"]

    def test_planned_duration_only_in_preflight(self, protocol):
        assert "duration_planned_s" in protocol["features"]["preflight"]
        assert "duration_planned_s" not in protocol["features"]["as_written"]

    def test_two_variants_differ_by_exactly_one_feature(self, protocol):
        a = set(protocol["features"]["as_written"])
        b = set(protocol["features"]["preflight"])
        assert a - b == {"duration_s"}
        assert b - a == {"duration_planned_s"}

    def test_target_is_measured_energy(self, protocol):
        assert protocol["target"]["column"] == "energy_Wh"
        assert protocol["target"]["unit"] == "Wh"

    def test_unit_of_analysis_is_flight(self, protocol):
        assert protocol["partitioning"]["unit_of_analysis"] == "flight"

    def test_required_models_present(self, protocol):
        required = {k for k, v in protocol["models"].items() if v.get("required")}
        assert {"D0", "D1", "D2", "D3"}.issubset(required)

    def test_bias_metric_present(self, protocol):
        # Sai so CO DAU la bat buoc: du bao thieu he thong la van de an toan
        names = {m["name"] for m in protocol["metrics"]["primary"]}
        assert "bias" in names

    def test_wind_primary_is_raw(self, protocol):
        assert protocol["wind"]["primary_column"] == "wind_raw_mean_ms"

    def test_distance_holdout_declared_as_extension(self, protocol):
        exp = protocol["experiments"]["E2c_distance_extrapolation_holdout"]
        assert "BO SUNG" in exp["status"]
        assert len(exp["holdout_flights"]["long_range"]) == 5

    def test_long_range_holdout_configs_are_distinct(self, protocol):
        # 5 chuyen phai la 5 cau hinh khac nhau, khong phai 5 ban sao
        lr = protocol["experiments"]["E2c_distance_extrapolation_holdout"]["holdout_flights"]["long_range"]
        combos = {(f["payload"], f["speed"], f["altitude"]) for f in lr}
        assert len(combos) == 5
