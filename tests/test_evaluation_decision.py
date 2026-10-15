"""
Test cho src/evaluation_decision.py — buoc chay cua san pham D3.

Module nay la mot bo chay, nen test tap trung vao cho de sai nhat: dung lai
du bao out-of-fold tu phan du, va tinh dung SoC toi thieu.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.decision_rules import CONDITIONAL, FLY, VERDICT_ORDER, assess, load_protocol
from src.evaluation_decision import (
    ESTIMATOR, R_LEVELS, SOH_MAIN, TEMP_MAIN, _mission_kwargs, load_missions,
    min_soc_for, run_invariants,
)


@pytest.fixture(scope="module")
def df():
    return load_missions()


@pytest.fixture(scope="module")
def protocol():
    return load_protocol()


# ---------------------------------------------------------------------------

class TestLoadMissions:
    """Dung lai nhiem vu tu bo du lieu."""

    def test_du_192_chuyen(self, df):
        assert len(df) == 192
        assert df["flight"].nunique() == 192

    def test_du_bao_dung_lai_khop_mae_da_cong_bo(self, df, protocol):
        """
        pred = energy_Wh + phan du. Neu dau hoac nguon sai thi MAE tinh lai se
        khong khop con so trong giao thuc — day la phep kiem doc lap.
        """
        mae = float(np.mean(np.abs(df["e_required_Wh"] - df["energy_Wh"])))
        ghi = protocol["energy_required"]["measured_error"]["MAE_Wh"]
        assert mae == pytest.approx(ghi, abs=1e-3)

    def test_du_bao_nam_trong_dai_hop_ly(self, df):
        assert df["e_required_Wh"].min() > 0
        assert df["e_required_Wh"].max() < 50

    def test_khong_co_gia_tri_thieu(self, df):
        assert not df.isna().any().any()

    def test_gio_chua_bao_gio_cham_gioi_han(self, df):
        """
        Toan chien dich bay trong dai gio hep, nen HR-1 khong bao gio kich hoat
        tren bo du lieu nay. Phai neu trong bao cao, khong de nguoi doc tuong
        lop luat cung da duoc thu thach o day.
        """
        assert df["wind_forecast_ms"].max() < 10.0

    def test_mo_hinh_dung_la_d2b(self):
        assert ESTIMATOR == "D2_ridge_preflight"


class TestMinSoc:
    """SoC toi thieu — dung chia doi, hop le nho INV-3."""

    def test_duoi_nguong_thi_khong_dat_tren_nguong_thi_dat(self, df, protocol):
        row = next(df.itertuples())
        v = min_soc_for(row, FLY, SOH_MAIN, TEMP_MAIN, 0.20, protocol)
        assert v is not None
        duoi = assess(**_mission_kwargs(row, v - 0.01, SOH_MAIN, TEMP_MAIN),
                      reserve_factor=0.20, protocol=protocol).verdict
        tren = assess(**_mission_kwargs(row, v + 0.01, SOH_MAIN, TEMP_MAIN),
                      reserve_factor=0.20, protocol=protocol).verdict
        assert VERDICT_ORDER.index(duoi) < VERDICT_ORDER.index(FLY)
        assert VERDICT_ORDER.index(tren) >= VERDICT_ORDER.index(FLY)

    def test_he_so_du_tru_cao_hon_doi_hoi_pin_nhieu_hon(self, df, protocol):
        row = next(df.itertuples())
        vs = [min_soc_for(row, FLY, SOH_MAIN, TEMP_MAIN, r, protocol)
              for r in R_LEVELS]
        assert vs == sorted(vs)

    def test_pin_cu_hon_doi_hoi_soc_cao_hon(self, df, protocol):
        row = next(df.itertuples())
        moi = min_soc_for(row, FLY, 1.00, TEMP_MAIN, 0.20, protocol)
        cu = min_soc_for(row, FLY, 0.80, TEMP_MAIN, 0.20, protocol)
        assert cu > moi

    def test_nguong_conditional_thap_hon_nguong_fly(self, df, protocol):
        for row in list(df.itertuples())[:20]:
            f = min_soc_for(row, FLY, SOH_MAIN, TEMP_MAIN, 0.20, protocol)
            c = min_soc_for(row, CONDITIONAL, SOH_MAIN, TEMP_MAIN, 0.20, protocol)
            if f is not None:
                assert c is not None and c <= f

    def test_nam_chuyen_ngoai_envelope_khong_bao_gio_dat_fly(self, df, protocol):
        """
        Ket qua manh nhat cua D3: 5 chuyen R6 ~835 m bi PD-1 chan vinh vien o
        CONDITIONAL, du pin day. Dung 5 chuyen cua thi nghiem E2c.
        """
        xa = df[df["distance_2d_m"] > 700]
        assert len(xa) == 5
        for row in xa.itertuples():
            assert min_soc_for(row, FLY, SOH_MAIN, TEMP_MAIN, 0.20,
                               protocol) is None
            assert min_soc_for(row, CONDITIONAL, SOH_MAIN, TEMP_MAIN, 0.20,
                               protocol) is not None

    def test_chuyen_trong_envelope_dat_duoc_fly(self, df, protocol):
        trong = df[(df["distance_2d_m"] >= 420) & (df["distance_2d_m"] <= 610)]
        assert len(trong) == 187
        for row in list(trong.itertuples())[:20]:
            assert min_soc_for(row, FLY, SOH_MAIN, TEMP_MAIN, 0.20,
                               protocol) is not None


class TestInvariantsOnRealData:
    """Sau bat bien, chay tren cau hinh bay co that."""

    @pytest.fixture(scope="class")
    def kq(self, df, protocol):
        return run_invariants(df, protocol)

    def test_du_sau_bat_bien(self, kq):
        assert list(kq["invariant"]) == [f"INV-{i}" for i in range(1, 7)]

    def test_khong_bat_bien_nao_bi_vi_pham(self, kq):
        xau = kq[kq["vi_pham"] > 0]
        assert xau.empty, f"vi pham: {xau.to_dict('records')}"

    def test_moi_bat_bien_deu_duoc_thu_that(self, kq):
        """Mot phep kiem chay tren 0 truong hop thi khong chung minh gi."""
        assert (kq["so_truong_hop"] > 0).all()

    def test_tong_so_truong_hop_dang_ke(self, kq):
        assert kq["so_truong_hop"].sum() > 2000
