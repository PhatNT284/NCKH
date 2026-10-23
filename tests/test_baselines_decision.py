"""
Test cho src/baselines_decision.py — buoc 4 cua san pham D4.

Cho de sai nhat o buoc nay KHONG phai cong thuc, ma la CONG BANG: mot duong co
so bi cai dat yeu hon muc Muc 7 mo ta se lam B5 trong gioi mot cach gia. Loi do
khong lo ra — bang ket qua van dep, chi la dep vi doi thu bi lam yeu.

Nen phan lon test o day kiem hai thu:
  - moi phuong phap DUNG duoc thong tin ma Muc 7 cho phep no dung, khong hon
  - va KHONG bi tuoc thong tin ma Muc 7 cho phep
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.baselines_decision import (
    B0, B1, B1_PURE, B2, B3, B5, B5_NOHR, THU_TU, bang_phan_bo, chay_tat_ca,
    khop_hai_mo_hinh, _b0, _b1, _b_nang_luong,
)
from src.decision_rules import CONDITIONAL, FLY, INSUFFICIENT_DATA, NO_FLY
from src.reference_labeller import load_protocol


@pytest.fixture(scope="module")
def protocol():
    return load_protocol()


@pytest.fixture(scope="module")
def mo_hinh():
    """Khop mot lan, dung chung ca file — cham, dung lai."""
    return khop_hai_mo_hinh()


def _kb(**ghi_de) -> pd.DataFrame:
    goc = dict(scenario_id=1, stratum="main", payload_g=250.0,
               speed_commanded_ms=8.0, altitude_m=50.0, distance_2d_m=472.0,
               wind_forecast_ms=3.0, soc=0.8, soh=0.95, ambient_temp_c=15.0,
               hard_rule_probe=False, probe_limit=None, missing_field=None)
    goc.update(ghi_de)
    return pd.DataFrame([goc])


def _chay(protocol, mo_hinh, **ghi_de) -> dict:
    d = chay_tat_ca(_kb(**ghi_de), protocol, mo_hinh=mo_hinh)
    return {ma: d[f"verdict_{ma}"].iloc[0] for ma in THU_TU}


# ---------------------------------------------------------------------------

class TestGiaoThuc:
    """Chinh sach phai khai o file dong bang truoc khi code dua vao."""

    def test_chinh_sach_luat_cung_duoc_khai(self, protocol):
        cfg = protocol["baselines"]["hard_rule_policy"]
        assert cfg["primary"] == "APPLY_TO_ALL"
        assert cfg["source"] == "TEAM_CHOICE"
        assert cfg["affects_results"] is True
        assert cfg["secondary_run_required"]

    def test_tu_vung_phan_quyet_duoc_khai(self, protocol):
        """
        B0..B3 nhi phan, chi B5 co bac giua. Bac giua la dong gop cua phuong
        phap nhom (§5.7) — cho duong co so muon la xoa mat thu dang do.
        """
        v = protocol["baselines"]["verdict_vocabulary"]
        assert set(v["binary_methods"]) == {B0, B1, B1_PURE, B2, B3}
        assert CONDITIONAL not in v["binary_values"]
        assert CONDITIONAL in v["graded_values"]

    def test_quyet_dinh_c23_c24_duoc_ghi(self, protocol):
        ids = [d["id"] for c in protocol["change_log"]
               for d in c.get("decisions", [])]
        assert "C23" in ids and "C24" in ids

    def test_b1_dung_so_dji_khong_phai_so_tu_dat(self, protocol):
        cfg = protocol["baselines"]["B1"]
        assert cfg["endurance_min"] == 13.0
        assert "DJI" in cfg["endurance_source"]
        # Hai thien lech lac quan phai duoc khai
        assert "LAC QUAN" in cfg["fairness_condition"].upper()


class TestKhopMoHinh:
    """Hai mo hinh, moi cai khop MOT LAN tren 192 chuyen that."""

    def test_d1_dung_mot_dac_trung(self, mo_hinh):
        _, cot = mo_hinh["D1"]
        assert cot == ["distance_2d_m"]

    def test_d2_dung_sau_dac_trung_preflight(self, mo_hinh):
        from src.reference_labeller import load_d2_protocol
        _, cot = mo_hinh["D2"]
        assert cot == list(load_d2_protocol()["features"]["preflight"])

    def test_d2_khop_giong_het_buoc_gan_nhan(self, mo_hinh):
        """
        B3 va B5 phai dung DUNG bo he so ma buoc 3 da dong bang. Lech mot chut
        thi B3 va nhan tham chieu REF-1 khong con cung goc, va chenh lech do se
        bi doc nham thanh chat luong quyet dinh.
        """
        from src.reference_labeller import fit_frozen_estimator
        pipe_goc, cot_goc, _, _ = fit_frozen_estimator()
        pipe, cot = mo_hinh["D2"]
        assert cot == cot_goc
        np.testing.assert_allclose(
            pipe.named_steps["model"].coef_,
            pipe_goc.named_steps["model"].coef_, rtol=1e-10)

    def test_tat_dinh(self, mo_hinh):
        lai = khop_hai_mo_hinh()
        for ten in ("D1", "D2"):
            np.testing.assert_allclose(
                lai[ten][0].named_steps["model"].coef_,
                mo_hinh[ten][0].named_steps["model"].coef_, rtol=1e-10)


class TestB0:
    """Nguong SoC co dinh — KHONG biet gi ve nhu cau nhiem vu."""

    def test_tren_nguong_thi_duyet(self):
        assert _b0(_kb(soc=0.5).itertuples().__next__(), 0.20) == FLY

    def test_duoi_nguong_thi_tu_choi(self):
        assert _b0(_kb(soc=0.15).itertuples().__next__(), 0.20) == NO_FLY

    def test_dung_tai_nguong_thi_duyet(self):
        assert _b0(_kb(soc=0.20).itertuples().__next__(), 0.20) == FLY

    def test_khong_doi_theo_nhiem_vu(self, protocol, mo_hinh):
        """
        Dac trung cua B0 theo Muc 7: "Ignores mission demand". Hai nhiem vu
        khac han nhau nhung cung SoC phai cho cung phan quyet.
        Day la HAN CHE cua phuong phap, phai de nguyen chu khong duoc va.
        """
        a = _chay(protocol, mo_hinh, soc=0.5, distance_2d_m=320.0, payload_g=0.0)
        b = _chay(protocol, mo_hinh, soc=0.5, distance_2d_m=610.0, payload_g=500.0)
        assert a[B0] == b[B0]

    def test_ba_nguong_lay_tu_giao_thuc(self, protocol):
        """Ba nguong 20/30/40 % la so cua THAY (Muc 7), khong phai nhom chon."""
        assert protocol["baselines"]["B0"]["thresholds"] == [0.20, 0.30, 0.40]


class TestB1:
    """Thoi luong bay danh dinh."""

    @pytest.fixture
    def cfg(self, protocol):
        return protocol["baselines"]["B1"]

    def test_nhiem_vu_ngan_thi_duyet(self, cfg):
        row = _kb(distance_2d_m=472.0, speed_commanded_ms=8.0,
                  soc=1.0, soh=1.0).itertuples().__next__()
        assert _b1(row, cfg, 0.20, nhan_soc=True) == FLY

    def test_pin_can_thi_b1_tu_choi_nhung_b1_pure_van_duyet(self, cfg):
        """
        Day la ca ly do bao CA HAI bien the. B1-pure khong biet SoC nen duyet
        bay ca khi pin gan can — doc sat chu Muc 7 thi dung vay, va con so do
        phai hien ra trong bao cao.
        """
        row = _kb(soc=0.02, soh=1.0).itertuples().__next__()
        assert _b1(row, cfg, 0.20, nhan_soc=True) == NO_FLY
        assert _b1(row, cfg, 0.20, nhan_soc=False) == FLY

    def test_nhiem_vu_rat_dai_thi_tu_choi(self, cfg):
        """13 phut / 1.2 = 650 s. Bay 900 m o 1 m/s = 900 s > 650."""
        row = _kb(distance_2d_m=900.0, speed_commanded_ms=1.0,
                  soc=1.0, soh=1.0).itertuples().__next__()
        assert _b1(row, cfg, 0.20, nhan_soc=True) == NO_FLY

    def test_he_so_du_tru_cao_hon_thi_kho_hon(self, cfg):
        """
        Quet he so du tru phai thuc su doi hanh vi, khong phai trang tri.

        So hoc: endurance 13 phut = 780 s. Nguong la 780/(1+r).
            r = 0.10 -> 709.1 s
            r = 0.30 -> 600.0 s
        Nen phai chon t_ke_hoach nam GIUA hai so do. 650 m o 1 m/s = 650 s.
        (Ban dau test nay dung 620 m o 1.2 m/s = 516.7 s — duoi ca hai nguong,
        nen ra FLY o ca hai va test do. Loi so hoc cua nguoi viet test.)
        """
        row = _kb(distance_2d_m=650.0, speed_commanded_ms=1.0,
                  soc=1.0, soh=1.0).itertuples().__next__()
        assert _b1(row, cfg, 0.10, nhan_soc=True) == FLY     # 650 <= 709.1
        assert _b1(row, cfg, 0.30, nhan_soc=True) == NO_FLY  # 650 >  600.0

    def test_thieu_dau_vao_thi_khong_ket_luan(self, cfg):
        row = _kb(soc=np.nan).itertuples().__next__()
        assert _b1(row, cfg, 0.20, nhan_soc=True) == INSUFFICIENT_DATA
        # B1-pure khong dung SoC nen van ket luan duoc — dung, khong phai loi
        assert _b1(row, cfg, 0.20, nhan_soc=False) == FLY


class TestB2B3:
    """Hai duong co so dung mo hinh nang luong — khac nhau DUNG mot thu."""

    def test_mot_nguong_khong_phai_hai(self):
        """
        B2/B3 nhi phan. Bac giua la dong gop cua B5 (quyet dinh C24).
        Mot bien du tru nam giua r va R_fly phai ra FLY o B3, CONDITIONAL o B5.
        """
        assert _b_nang_luong(20.0, 24.5, "OK", 0.20) == FLY      # R = 22.5 %
        assert _b_nang_luong(20.0, 23.0, "OK", 0.20) == NO_FLY   # R = 15 %

    def test_dau_vao_ngoai_dai_la_no_fly(self):
        assert _b_nang_luong(20.0, None, "OUT_OF_RANGE", 0.20) == NO_FLY

    def test_thieu_du_lieu_la_insufficient(self):
        assert _b_nang_luong(20.0, None, "MISSING_INPUT", 0.20) == INSUFFICIENT_DATA
        assert _b_nang_luong(np.nan, 50.0, "OK", 0.20) == INSUFFICIENT_DATA

    def test_b2_va_b3_khac_nhau_tren_du_lieu_that(self, protocol, mo_hinh):
        """
        Neu hai cai luon trung nhau thi so sanh B2 vs B3 khong do duoc gi, va
        ket luan "mo hinh da yeu to tot hon" khong co bang chung.

        Kich ban chon CO CHU DICH: cu ly NGAN (D1 doan thap) nhung tai nang,
        toc do cao, bay cao, gio manh (D2 doan cao). Do bang so:
            D1 = 19.34 Wh   D2 = 23.64 Wh
        Nen SoC trong khoang (0.246, 0.300) lam hai cai ra hai phan quyet khac
        nhau. Lay 0.27.

        Ban dau test nay lay nam kich ban "cho co", va ca nam deu ra FLY o ca
        hai — khong chung minh duoc gi. Phai tinh truoc roi moi chon.
        """
        kb = _kb(payload_g=500.0, speed_commanded_ms=12.0, altitude_m=100.0,
                 distance_2d_m=320.0, wind_forecast_ms=9.0,
                 soc=0.27, soh=0.95, ambient_temp_c=15.0)
        d = chay_tat_ca(kb, protocol, mo_hinh=mo_hinh)
        assert d[f"verdict_{B2}"].iloc[0] == FLY
        assert d[f"verdict_{B3}"].iloc[0] == NO_FLY

    def test_b3_dung_cung_mo_hinh_voi_b5(self, protocol, mo_hinh):
        """
        B3 va B5 phai dung CUNG du bao nang luong. Khac nhau giua chung chi
        duoc den tu chinh sach phan quyet, khong tu mo hinh.
        """
        d = chay_tat_ca(_kb(soc=0.5), protocol, mo_hinh=mo_hinh)
        assert np.isfinite(d["e_required_D2_Wh"].iloc[0])


class TestLuatCung:
    """Quyet dinh C23 — bang chinh ap cho tat ca, bang thu hai thi khong."""

    @pytest.mark.parametrize("kw", [
        {"wind_forecast_ms": 15.0},        # HR-1
        {"speed_commanded_ms": 25.0},      # HR-4
        {"ambient_temp_c": -25.0},         # HR-2
    ])
    def test_bang_chinh_moi_phuong_phap_deu_bi_chan(self, protocol, mo_hinh, kw):
        v = _chay(protocol, mo_hinh, soc=1.0, **kw)
        for ma in (B0, B1, B1_PURE, B2, B3, B5):
            assert v[ma] in (NO_FLY, INSUFFICIENT_DATA), f"{ma} duyet bay {kw}"

    @pytest.mark.parametrize("kw", [
        {"wind_forecast_ms": 15.0},
        {"speed_commanded_ms": 25.0},
    ])
    def test_bang_thu_hai_b0_duyet_bay_cai_dang_le_phai_chan(
            self, protocol, mo_hinh, kw):
        """
        Day chinh la ly do quyet dinh C23 chon ap luat cung cho tat ca o bang
        chinh. Khong co lop do, B0 duyet bay mot kich ban gio 15 m/s — va B5
        thang khong phai vi quyet dinh nang luong tot hon.
        """
        d = chay_tat_ca(_kb(soc=1.0, **kw), protocol,
                        ap_dung_luat_cung=False, mo_hinh=mo_hinh)
        assert d[f"verdict_{B0}"].iloc[0] == FLY
        # B5 VAN bi chan: lop luat cung la mot phan dinh nghia cua no (Muc 7)
        assert d[f"verdict_{B5}"].iloc[0] == NO_FLY

    def test_co_duoc_ghi_vao_bang_ket_qua(self, protocol, mo_hinh):
        a = chay_tat_ca(_kb(), protocol, ap_dung_luat_cung=True, mo_hinh=mo_hinh)
        b = chay_tat_ca(_kb(), protocol, ap_dung_luat_cung=False, mo_hinh=mo_hinh)
        assert bool(a["hard_rules_applied_to_all"].iloc[0]) is True
        assert bool(b["hard_rules_applied_to_all"].iloc[0]) is False


class TestB5VaAblation:
    """B5 va B5-noHR — Muc 7 bat bao ablation rieng."""

    def test_b5_co_bac_giua(self, protocol, mo_hinh):
        """Quet SoC phai cham duoc CONDITIONAL, neu khong thi bac giua la trang tri."""
        nhan = {_chay(protocol, mo_hinh, soc=s)[B5]
                for s in np.arange(0.20, 0.80, 0.01)}
        assert CONDITIONAL in nhan

    def test_ablation_go_duoc_luat_cung(self, protocol, mo_hinh):
        """
        Pin day, gio 15 m/s: B5 chan vi HR-1. B5-noHR khong con so bien du tru
        de phan quyet (assess dung som) nen phai ra INSUFFICIENT_DATA — KHONG
        duoc tu bia ra mot phan quyet.
        """
        v = _chay(protocol, mo_hinh, soc=1.0, wind_forecast_ms=15.0)
        assert v[B5] == NO_FLY
        assert v[B5_NOHR] == INSUFFICIENT_DATA

    def test_ablation_trung_b5_khi_khong_vi_pham(self, protocol, mo_hinh):
        """Khong vi pham luat cung thi hai cai phai y het."""
        for soc in (0.25, 0.35, 0.50, 0.80, 1.00):
            v = _chay(protocol, mo_hinh, soc=soc)
            assert v[B5] == v[B5_NOHR], f"lech o SoC {soc}"

    def test_ablation_khong_duoc_dung_lam_khuyen_nghi(self, protocol):
        """
        Muc 7: "for analysis only, never as the operational recommendation."
        Giao thuc phai ghi rang buoc do.
        """
        ab = protocol["baselines"]["ablation"]
        assert ab["id"] == B5_NOHR
        assert "never as the operational" in ab["hard_constraint"]


class TestCongBang:
    """
    Muc 7 cot "fairness condition". Mot duong co so bi lam yeu hon muc mo ta se
    lam B5 trong gioi mot cach gia — va loi do khong lo ra o bang ket qua.
    """

    def test_moi_phuong_phap_deu_ra_du_hai_phia(self, protocol, mo_hinh):
        """
        Mot phuong phap luon tra ve cung mot phan quyet thi khong phai doi thu,
        chi la mot hang so. Quet SoC phai cho moi cai ca FLY lan NO_FLY.
        """
        nhan = {ma: set() for ma in THU_TU}
        for soc in (0.05, 0.15, 0.30, 0.50, 0.90):
            v = _chay(protocol, mo_hinh, soc=soc)
            for ma in THU_TU:
                nhan[ma].add(v[ma])
        for ma in (B0, B1, B2, B3, B5):
            assert {FLY, NO_FLY} <= nhan[ma], f"{ma} chi ra {nhan[ma]}"

    def test_cung_bo_kich_ban_cho_moi_phuong_phap(self, protocol, mo_hinh):
        """
        §6/E3: "All methods must be evaluated on the same scenario set."
        Bay cot phan quyet phai cung so dong voi bang kich ban.
        """
        kb = pd.concat([_kb(scenario_id=i, soc=0.2 + i / 20)
                        for i in range(10)], ignore_index=True)
        d = chay_tat_ca(kb, protocol, mo_hinh=mo_hinh)
        for ma in THU_TU:
            assert d[f"verdict_{ma}"].notna().all()
            assert len(d) == len(kb)

    def test_cung_he_so_du_tru_cho_moi_phuong_phap(self, protocol, mo_hinh):
        """
        Muc 7: "identical scenarios and reserve policy used for comparisons".
        Mot he so du tru duy nhat ghi vao bang, dung chung.
        """
        d = chay_tat_ca(_kb(), protocol, reserve_factor=0.30, mo_hinh=mo_hinh)
        assert float(d["reserve_factor"].iloc[0]) == 0.30

    def test_thieu_dau_vao_khong_phuong_phap_nao_duyet_bay(self, protocol, mo_hinh):
        """
        §4.6 fail closed, ap cho moi phuong phap.

        Test nay TUNG BAT MOT LOI THAT: B0 duyet bay khi thieu gio. Nguyen nhan
        la NaN lot qua lop luat cung — hop dong cua D3 la "None nghia la thieu",
        ma bang kich ban doc tu CSV nen o trong thanh NaN, va `NaN is None` la
        False. Roi `NaN > 10.0` cung False nen HR-1 bao PASS.
        Da sua bang `nan_sang_none()` o ranh gioi D4-D3. Xem OI-D4-6.

        B1-pure la ngoai le DUY NHAT va co ly do: no khong dung SoC, nen thieu
        SoC khong lam no mat thong tin. Nhung thieu GIO thi ke ca B1-pure cung
        phai dung, vi lop luat cung chan.
        """
        for thieu in ("soc", "soh", "ambient_temp_c", "wind_forecast_ms"):
            v = _chay(protocol, mo_hinh, **{thieu: np.nan})
            for ma in THU_TU:
                if ma == B1_PURE and thieu in ("soc", "soh"):
                    continue
                assert v[ma] != FLY, f"{ma} duyet bay khi thieu {thieu}"

    def test_nan_khong_lot_qua_lop_luat_cung(self, protocol, mo_hinh):
        """
        Khoa rieng lo hong da gap: NaN o mot dau vao cua luat cung phai thanh
        INSUFFICIENT_DATA, KHONG duoc di qua nhu gia tri hop le.

        Kiem o muc thap nhat — bao cao luat cung — de neu ai bo `nan_sang_none()`
        thi do ngay day chu khong phai do gian tiep qua mot phuong phap nao do.
        """
        from src.baselines_decision import _bao_cao_luat_cung
        from src.reference_labeller import load_d3_protocol
        d3 = load_d3_protocol()

        for thieu in ("wind_forecast_ms", "ambient_temp_c", "payload_g",
                      "speed_commanded_ms", "altitude_m"):
            row = _kb(**{thieu: np.nan}).itertuples().__next__()
            hard = _bao_cao_luat_cung(row, d3)
            assert hard.missing, f"NaN o {thieu} lot qua lop luat cung"

    def test_nan_va_none_cho_cung_ket_qua(self, protocol, mo_hinh):
        """
        Hai cach bieu dien "thieu" phai cho cung phan quyet. Khac nhau thi tuc
        la mot trong hai duong di co lo hong.
        """
        from src.reference_labeller import nan_sang_none
        assert nan_sang_none(np.nan) is None
        assert nan_sang_none(None) is None
        assert nan_sang_none(float("inf")) is None
        assert nan_sang_none(3.0) == 3.0


class TestBangPhanBo:
    def test_du_bay_cot(self, protocol, mo_hinh):
        kb = pd.concat([_kb(scenario_id=i, soc=0.1 + i / 15)
                        for i in range(12)], ignore_index=True)
        b = bang_phan_bo(chay_tat_ca(kb, protocol, mo_hinh=mo_hinh))
        assert list(b.columns) == THU_TU
        assert b.sum().min() == len(kb)
