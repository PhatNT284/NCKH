"""
Test cho src/decision_rules.py — khoi (c) va (e) cua san pham D3.

Day cung la noi hien thuc hoa cac BAT BIEN INV-1..INV-4 cua giao thuc. Khong
co dap an "chuyen nay dang le co nen bay khong", nen KHONG do duoc do chinh xac
o D3 — thay vao do kiem cac TINH CHAT phai luon dung.

    INV-1  luat cung phu quyet      -> TestInv1Veto
    INV-2  fail closed              -> TestInv2FailClosed
    INV-3  don dieu theo nang luong -> TestInv3Monotonic
    INV-4  tat dinh                 -> TestInv4Deterministic
"""

from __future__ import annotations

import math

import pytest

from src.decision_rules import (
    CONDITIONAL, FLY, INSUFFICIENT_DATA, NO_FLY, VERDICT_ORDER,
    assess, load_protocol, sweep_reserve,
)
from src.safety_invariants import PROFILE_CMU, PROFILE_STOCK

# Nhiem vu hop le moi mat, bien du tru rong rai
GOC = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50,
           distance_2d_m=472, wind_forecast_ms=3.0, ambient_temp_c=15,
           soc=0.80, soh=0.95, e_required_Wh=22.0)


def _v(**kw) -> str:
    return assess(**{**GOC, **kw}).verdict


# ---------------------------------------------------------------------------

class TestThresholds:
    """Hai nguong — quyet dinh B4."""

    def test_r_min_bang_he_so_du_tru(self):
        d = assess(**GOC)
        assert d.r_min == pytest.approx(0.20)
        assert d.reserve_factor == pytest.approx(0.20)

    def test_r_fly_cong_khoan_bat_dinh(self):
        d = assess(**GOC)
        assert d.r_fly == pytest.approx(0.20 + 1.4687 / 22.0, abs=1e-6)

    def test_r_fly_luon_lon_hon_r_min(self):
        for e in (5.0, 10.0, 22.0, 50.0, 100.0):
            d = assess(**{**GOC, "e_required_Wh": e})
            assert d.r_fly > d.r_min

    def test_chuyen_ton_nhieu_thi_khoan_cong_them_nho_di(self):
        """
        Khoan bat dinh la Wh TUYET DOI, nen quy ra ti le thi chuyen ton nhieu
        nang luong se bi cong them it hon. Dung ve vat ly: sai so 1.5 Wh tren
        nen 100 Wh it nghiem trong hon tren nen 10 Wh.
        """
        nho = assess(**{**GOC, "e_required_Wh": 10.0}).r_fly
        lon = assess(**{**GOC, "e_required_Wh": 100.0}).r_fly
        assert nho > lon

    def test_bien_tuyet_doi_va_ti_le_nhat_quan(self):
        d = assess(**GOC)
        assert d.margin_Wh == pytest.approx(d.e_available_Wh - d.e_required_Wh)
        assert d.margin_ratio == pytest.approx(d.margin_Wh / d.e_required_Wh)


class TestVerdictBands:
    """Ba dai bien du tru."""

    def test_duoi_r_min_la_no_fly(self):
        assert _v(soc=0.25) == NO_FLY

    def test_giua_hai_nguong_la_conditional(self):
        d = assess(**{**GOC, "soc": 0.28})
        assert d.verdict == CONDITIONAL
        assert d.r_min <= d.margin_ratio < d.r_fly

    def test_tren_r_fly_la_fly(self):
        d = assess(**{**GOC, "soc": 0.30})
        assert d.verdict == FLY
        assert d.margin_ratio >= d.r_fly

    def test_bon_muc_deu_dat_duoc(self):
        """Neu mot muc khong bao gio xuat hien thi thiet ke co van de."""
        thay = {
            _v(soc=0.30),                    # FLY
            _v(soc=0.28),                    # CONDITIONAL
            _v(soc=0.25),                    # NO_FLY
            _v(soc=None),                    # INSUFFICIENT_DATA
        }
        assert thay == set(VERDICT_ORDER)

    def test_khong_co_truong_diem_so(self):
        """
        §5.6 loai bo cach cham diem gop; §5.8 cam goi dau ra la do tin cay.
        Test nay chan viec vo tinh them lai mot truong nhu vay.
        """
        d = assess(**GOC)
        cam = {"score", "confidence", "probability", "do_tin_cay", "xac_suat"}
        assert not (set(vars(d)) & cam)


# ---------------------------------------------------------------------------

class TestInv1Veto:
    """INV-1 — vi pham luat cung thi KHONG BAO GIO ra FLY."""

    @pytest.mark.parametrize("kw", [
        {"wind_forecast_ms": 14.0},
        {"ambient_temp_c": -25.0},
        {"speed_commanded_ms": 20.0},
        {"payload_g": 1500},
    ])
    def test_vi_pham_luon_no_fly_du_pin_day(self, kw):
        """Pin day 100 %, SoH moi, bien du tru +330 % — van NO_FLY."""
        assert _v(soc=1.0, soh=1.0, **kw) == NO_FLY

    @pytest.mark.parametrize("soc", [0.3, 0.5, 0.8, 1.0])
    def test_vi_pham_no_fly_o_moi_muc_pin(self, soc):
        assert _v(soc=soc, wind_forecast_ms=14.0) == NO_FLY

    @pytest.mark.parametrize("r", [0.0, 0.05, 0.10, 0.20, 0.30])
    def test_khong_the_ha_nguong_de_lat_vi_pham(self, r):
        """Khong duoc dung he so du tru de lach mot vi pham luat cung."""
        assert _v(soc=1.0, wind_forecast_ms=14.0, reserve_factor=r) == NO_FLY

    def test_vi_pham_xet_truoc_thieu_du_lieu(self):
        """
        Vi pham DA BIET CHAC van la vi pham, du dau vao khac co thieu. Neu dao
        thu tu thi se bao INSUFFICIENT_DATA va che mat mot NO_FLY that.
        """
        assert _v(wind_forecast_ms=14.0, soc=None) == NO_FLY

    def test_ly_do_vi_pham_duoc_ghi_ro(self):
        d = assess(**{**GOC, "wind_forecast_ms": 14.0})
        assert any("HR-1" in r for r in d.reasons)
        assert any("luat cung" in r for r in d.reasons)


class TestExtrapolation:
    """PD-* ha cap FLY xuong CONDITIONAL, khong bat buoc NO_FLY."""

    def test_ngoai_envelope_ha_fly_xuong_conditional(self):
        d = assess(**{**GOC, "soc": 1.0, "distance_2d_m": 835})
        assert d.verdict == CONDITIONAL
        assert d.extrapolated

    def test_ngoai_envelope_khong_bien_thanh_no_fly(self):
        """Khac VETO: mo hinh van cho so, chi la so khong dang tin."""
        assert _v(soc=1.0, distance_2d_m=835) != NO_FLY

    def test_ngoai_envelope_van_no_fly_neu_thieu_pin(self):
        """Ha cap khong cuu duoc mot bien du tru qua thap."""
        assert _v(soc=0.25, distance_2d_m=835) == NO_FLY

    def test_trong_envelope_khong_bi_danh_dau(self):
        assert not assess(**{**GOC, "soc": 1.0}).extrapolated

    def test_tai_ngoai_dai_cung_ha_cap(self):
        d = assess(**{**GOC, "soc": 1.0, "payload_g": 800,
                      "profile": PROFILE_CMU})
        assert d.verdict == CONDITIONAL
        assert d.extrapolated

    def test_ly_do_ngoai_suy_dung_dau_danh_sach(self):
        """Nguoi doc phai thay ly do ha cap truoc, khong phai sau."""
        d = assess(**{**GOC, "soc": 1.0, "distance_2d_m": 835})
        assert "PD-1" in d.reasons[0]


# ---------------------------------------------------------------------------

class TestInv2FailClosed:
    """INV-2 — thieu dau vao thi KHONG BAO GIO ra FLY (§4.6)."""

    @pytest.mark.parametrize("thieu", [
        "payload_g", "speed_commanded_ms", "distance_2d_m",
        "wind_forecast_ms", "ambient_temp_c", "soc", "soh", "e_required_Wh",
    ])
    def test_thieu_bat_ky_dau_vao_nao(self, thieu):
        d = assess(**{**GOC, thieu: None})
        assert d.verdict == INSUFFICIENT_DATA
        assert d.reasons

    @pytest.mark.parametrize("thieu", [
        "soc", "soh", "ambient_temp_c", "e_required_Wh",
    ])
    def test_thieu_khong_duoc_ra_fly_du_pin_day(self, thieu):
        assert _v(**{"soc": 1.0, "soh": 1.0, thieu: None}) != FLY

    def test_khong_tu_dien_gia_tri_mac_dinh(self):
        """
        Che do hong nguy hiem nhat: tu dien 25 C roi bao FLY mau xanh. Thieu
        nhiet do PHAI khac han voi co nhiet do.
        """
        assert _v(ambient_temp_c=None) == INSUFFICIENT_DATA
        assert _v(ambient_temp_c=25.0) == FLY

    def test_thieu_het(self):
        assert assess().verdict == INSUFFICIENT_DATA

    def test_insufficient_khac_no_fly(self):
        """
        §4.6 cho hai ket cuc rieng. Gop lam mot thi mat thong tin: 'khong biet'
        khac 'biet la khong duoc'.
        """
        assert _v(soc=None) == INSUFFICIENT_DATA
        assert _v(soc=0.25) == NO_FLY

    @pytest.mark.parametrize("truong", ["soc", "soh", "ambient_temp_c",
                                        "distance_2d_m", "payload_g"])
    def test_nan_khong_ra_fly(self, truong):
        assert _v(**{truong: math.nan}) != FLY

    def test_e_required_am_hoac_0(self):
        assert _v(e_required_Wh=0.0) == NO_FLY
        assert _v(e_required_Wh=-5.0) == NO_FLY

    def test_soc_ngoai_dai_la_no_fly_khong_phai_insufficient(self):
        """Sai khac thieu: sai thi biet la sai -> NO_FLY."""
        assert _v(soc=1.5) == NO_FLY


# ---------------------------------------------------------------------------

class TestInv3Monotonic:
    """INV-3 — nang luong nhieu hon thi phan quyet khong bao gio xau di."""

    def test_don_dieu_theo_soc(self):
        truoc = -1
        for soc in [i / 200 for i in range(1, 201)]:
            muc = VERDICT_ORDER.index(_v(soc=soc))
            assert muc >= truoc, f"phan quyet xau di khi SoC tang len {soc}"
            truoc = muc

    def test_don_dieu_theo_soh(self):
        truoc = -1
        for soh in [i / 100 for i in range(1, 101)]:
            muc = VERDICT_ORDER.index(_v(soc=0.35, soh=soh))
            assert muc >= truoc
            truoc = muc

    def test_don_dieu_nguoc_theo_nang_luong_can(self):
        """Chuyen can NHIEU hon thi phan quyet khong bao gio tot len."""
        truoc = len(VERDICT_ORDER)
        for e in [float(i) for i in range(5, 80)]:
            muc = VERDICT_ORDER.index(_v(soc=0.5, e_required_Wh=e))
            assert muc <= truoc
            truoc = muc

    def test_don_dieu_theo_he_so_du_tru(self):
        """He so du tru cao hon thi phan quyet khong bao gio tot len."""
        truoc = len(VERDICT_ORDER)
        for r in [i / 100 for i in range(0, 61)]:
            muc = VERDICT_ORDER.index(_v(soc=0.35, reserve_factor=r))
            assert muc <= truoc
            truoc = muc


class TestInv4Deterministic:
    """INV-4 — cung dau vao, cung dau ra."""

    def test_tat_dinh(self):
        goc = str(assess(**GOC))
        for _ in range(100):
            assert str(assess(**GOC)) == goc

    def test_tat_dinh_moi_nhanh(self):
        for kw in ({"soc": 0.25}, {"soc": 0.28}, {"soc": None},
                   {"wind_forecast_ms": 14.0}, {"distance_2d_m": 835}):
            a = assess(**{**GOC, **kw})
            b = assess(**{**GOC, **kw})
            assert (a.verdict, a.reasons) == (b.verdict, b.reasons)


# ---------------------------------------------------------------------------

class TestReserveSweep:
    """P§4.5 — bat buoc bao ca ba muc he so du tru."""

    def test_quet_du_ba_muc(self):
        kq = sweep_reserve(**GOC)
        assert sorted(kq) == [0.10, 0.20, 0.30]

    def test_ket_luan_co_the_doi_theo_muc(self):
        """
        Day la ly do P§4.5 bat bao ca ba: "a finding that holds only at one
        arbitrary reserve setting is not a finding about the method."
        """
        kq = sweep_reserve(**{**GOC, "soc": 0.30})
        assert len({d.verdict for d in kq.values()}) > 1

    def test_muc_cao_hon_khong_bao_gio_de_hon(self):
        kq = sweep_reserve(**{**GOC, "soc": 0.30})
        muc = [VERDICT_ORDER.index(kq[r].verdict) for r in (0.10, 0.20, 0.30)]
        assert muc == sorted(muc, reverse=True)


class TestBatteryAndProfile:
    """Do nhay loai pin (OI-2) va ho so may bay (B6)."""

    def test_tb48d_cho_bien_du_tru_lon_hon(self):
        a = assess(**{**GOC, "soc": 0.30, "battery_type": "TB47D"})
        b = assess(**{**GOC, "soc": 0.30, "battery_type": "TB48D"})
        assert b.margin_ratio > a.margin_ratio

    def test_gia_tri_chinh_la_huong_bao_thu(self):
        """
        Mac dinh TB47D (99.9 Wh) phai cho phan quyet khong de hon TB48D.
        Neu nguoc lai thi lua chon "bao thu" o OI-2 da sai huong.
        """
        for soc in [i / 100 for i in range(20, 101, 5)]:
            a = VERDICT_ORDER.index(_v(soc=soc, battery_type="TB47D"))
            b = VERDICT_ORDER.index(_v(soc=soc, battery_type="TB48D"))
            assert a <= b

    def test_ho_so_cmu_khong_lam_moi_chuyen_no_fly(self):
        """B6 — neu HR-3 veto o ho so CMU thi 192/192 chuyen NO_FLY."""
        for tai in (0, 250, 500):
            assert _v(soc=0.5, payload_g=tai, profile=PROFILE_CMU) != NO_FLY

    def test_ho_so_stock_la_mac_dinh(self):
        a = assess(**{**GOC, "payload_g": 1500})
        b = assess(**{**GOC, "payload_g": 1500, "profile": PROFILE_STOCK})
        assert a.verdict == b.verdict == NO_FLY


class TestProtocolDecision:
    """Kiem phan phan quyet cua configs/d3_protocol.yaml."""

    @pytest.fixture(scope="class")
    def protocol(self):
        return load_protocol()

    def test_cong_thuc_ghi_dung(self, protocol):
        f = protocol["reserve_and_verdict"]["formulas"]
        assert "E_available - E_required" in f["margin_absolute_Wh"]
        assert "/ E_required" in f["margin_ratio"]

    def test_vi_du_tinh_tay_khop_code(self, protocol):
        """
        Giao thuc co mot vi du tinh san. Neu code va vi du lech thi mot trong
        hai sai — test nay bat.
        """
        vd = protocol["reserve_and_verdict"]["thresholds"]["worked_example"]
        d = assess(**{**GOC, "e_required_Wh": vd["E_required_Wh"],
                      "reserve_factor": vd["r"]})
        assert d.r_min == pytest.approx(vd["R_min"], abs=1e-3)
        assert d.r_fly == pytest.approx(vd["R_fly"], abs=1e-3)

    def test_cam_goi_la_xac_suat(self, protocol):
        assert any("xac suat" in p for p in protocol["prohibitions"])

    def test_cam_bao_mot_muc_du_tru(self, protocol):
        assert any("he so du tru" in p for p in protocol["prohibitions"])
