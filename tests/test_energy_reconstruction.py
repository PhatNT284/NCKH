"""
Unit test cho phep tich phan dien ap x dong dien (nhiem vu tuan 3).

Tieu chi nghiem thu D1 cua thay: "test phep tich phan dien ap-dong dien".
Cach kiem: dung tin hieu da biet dap an bang tay, roi doi chieu.
"""

import numpy as np
import pandas as pd
import pytest

from src.energy_reconstruction import (
    JOULES_PER_WH, instantaneous_power, integrate_energy_riemann,
    integrate_energy_trapezoid, joules_to_wh, reconstruct_flight_energy,
)


class TestInstantaneousPower:
    def test_power_is_product(self):
        v = np.array([20.0, 22.0, 24.0])
        i = np.array([10.0, 5.0, 2.0])
        np.testing.assert_allclose(instantaneous_power(v, i), [200.0, 110.0, 48.0])

    def test_scalar_case(self):
        assert instantaneous_power(np.array([24.0]), np.array([15.0]))[0] == 360.0


class TestIntegration:
    """Dap an tinh tay cho tung truong hop."""

    def test_constant_power(self):
        # 100 W trong 100 s = 10 000 J
        t = np.linspace(0, 100, 101)
        p = np.full_like(t, 100.0)
        assert integrate_energy_trapezoid(t, p) == pytest.approx(10_000.0)

    def test_linear_ramp(self):
        # Cong suat tang tuyen tinh 0 -> 100 W trong 10 s = dien tich tam giac = 500 J
        t = np.linspace(0, 10, 1001)
        p = t * 10.0
        assert integrate_energy_trapezoid(t, p) == pytest.approx(500.0, rel=1e-6)

    def test_irregular_timestamps(self):
        # §4.2: phai dung khoang thoi gian THUC, khong gia dinh lay mau deu.
        # 50 W hang so tren moc thoi gian khong deu, tong 10 s = 500 J
        t = np.array([0.0, 0.5, 3.0, 3.1, 7.0, 10.0])
        p = np.full_like(t, 50.0)
        assert integrate_energy_trapezoid(t, p) == pytest.approx(500.0)

    def test_trapezoid_differs_from_riemann_on_ramp(self):
        # Voi tin hieu tang dan, Riemann tien luon thap hon hinh thang.
        t = np.linspace(0, 10, 11)
        p = t * 10.0
        assert integrate_energy_riemann(t, p) < integrate_energy_trapezoid(t, p)

    def test_methods_agree_on_constant(self):
        t = np.linspace(0, 10, 11)
        p = np.full_like(t, 42.0)
        assert integrate_energy_riemann(t, p) == pytest.approx(
            integrate_energy_trapezoid(t, p)
        )

    def test_too_few_samples(self):
        assert integrate_energy_trapezoid(np.array([1.0]), np.array([100.0])) == 0.0
        assert integrate_energy_trapezoid(np.array([]), np.array([])) == 0.0


class TestUnitConversion:
    def test_joules_to_wh(self):
        assert joules_to_wh(3600.0) == pytest.approx(1.0)
        assert joules_to_wh(0.0) == 0.0

    def test_round_trip_realistic(self):
        # 400 W trong 180 s = 72 000 J = 20 Wh — dung tam gia tri thuc cua M100
        assert joules_to_wh(400.0 * 180.0) == pytest.approx(20.0)

    def test_constant_matches_module(self):
        assert JOULES_PER_WH == 3600.0


class TestReconstructFlightEnergy:
    @staticmethod
    def _synthetic(n=600, hz=10.0, voltage=22.0, current=18.0):
        t = np.arange(n) / hz
        return pd.DataFrame({
            "time": t,
            "voltage": np.full(n, voltage),
            "current": np.full(n, current),
        })

    def test_known_answer(self):
        # 22 V x 18 A = 396 W, keo dai 59.9 s -> 396 * 59.9 / 3600 Wh
        df = self._synthetic()
        res = reconstruct_flight_energy(df)
        expected_wh = 22.0 * 18.0 * 59.9 / 3600.0
        assert res["energy_Wh"] == pytest.approx(expected_wh, rel=1e-9)
        assert res["P_mean_W"] == pytest.approx(396.0)
        assert res["P_max_W"] == pytest.approx(396.0)
        assert res["duration_s"] == pytest.approx(59.9)
        assert res["n_samples"] == 600

    def test_sample_rate(self):
        res = reconstruct_flight_energy(self._synthetic(n=600, hz=10.0))
        assert res["sample_hz"] == pytest.approx(10.0, rel=1e-6)

    def test_cross_check_small_for_constant_power(self):
        res = reconstruct_flight_energy(self._synthetic())
        assert res["cross_check_pct"] < 0.5

    def test_unsorted_input_is_sorted(self):
        df = self._synthetic(n=100).sample(frac=1.0, random_state=0)
        res = reconstruct_flight_energy(df)
        expected_wh = 22.0 * 18.0 * 9.9 / 3600.0
        assert res["energy_Wh"] == pytest.approx(expected_wh, rel=1e-9)

    def test_duplicate_timestamps_dropped(self):
        df = self._synthetic(n=100)
        df = pd.concat([df, df.iloc[:10]], ignore_index=True)
        assert reconstruct_flight_energy(df)["n_samples"] == 100

    def test_missing_values_dropped(self):
        df = self._synthetic(n=100)
        df.loc[5:9, "current"] = np.nan
        assert reconstruct_flight_energy(df)["n_samples"] == 95

    def test_missing_column_raises(self):
        with pytest.raises(KeyError):
            reconstruct_flight_energy(pd.DataFrame({"time": [0, 1], "voltage": [1, 2]}))

    def test_empty_returns_nan(self):
        res = reconstruct_flight_energy(
            pd.DataFrame({"time": [], "voltage": [], "current": []})
        )
        assert np.isnan(res["energy_Wh"])

    def test_realistic_magnitude(self):
        # Dai thuc cua bo du lieu: 13.0 - 37.7 Wh, cong suat trung binh ~405 W.
        # Mot chuyen 190 s o 405 W phai roi vao trong dai do.
        df = self._synthetic(n=1900, hz=10.0, voltage=22.5, current=18.0)
        res = reconstruct_flight_energy(df)
        assert 13.0 < res["energy_Wh"] < 37.7
