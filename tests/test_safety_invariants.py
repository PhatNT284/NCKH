"""
Test cho src/safety_invariants.py — lop luat cung, khoi (d) cua san pham D3.

Tam nhom:
    TestManufacturerRules  HR-1..HR-4, luat cua DJI
    TestPH1                PH-1, san nang luong ha canh (P§4.6, quyet dinh B10)
    TestProjectDerived     PD-1, PD-2, gioi han nhom rut ra tu thi nghiem
    TestAircraftProfiles   quyet dinh B6 — hai ho so may bay
    TestVetoSemantics      §4.6 — khong gi lat duoc vi pham luat cung
    TestFailClosed         §4.6 — thieu dau vao thi khong duoc qua
    TestNangLuongHaCanh    ham tinh nang luong ha canh trong physics_m100
    TestINV8               bat bien INV-8, tren duong chay day du qua assess()
    TestProtocolHardRules  doi chieu voi configs/d3_protocol.yaml

BA HO MA LUAT — nguon goc va muc do la HAI TRUC KHAC NHAU:
    HR-1..HR-4   DJI cong bo                      -> VETO
    PH-1         nguyen tac P§4.6 + con so nhom   -> VETO
    PD-1, PD-2   thi nghiem cua nhom              -> DOWNGRADE

Hai test canh quy uoc do, va ca hai tung bat loi that:
    test_moi_luat_hr_co_ghi_nguon          — HR-* phai co "DJI" trong nguon
    test_lop_nay_khong_nhan_dau_ra_mo_hinh — chu ky ham khong duoc co tham so
                                             mang ten nang luong (§4.6)
"""

from __future__ import annotations

import math

import pytest

from src.available_energy import kappa
from src.decision_rules import (
    FLY, INSUFFICIENT_DATA, NO_FLY, VERDICT_ORDER, assess,
)
from src.physics_m100 import landing_energy_Wh, min_soc_for_landing
from src.safety_invariants import (
    DOWNGRADE, KNOWN_EXCEEDED, MISSING, PASS, PROFILE_CMU, PROFILE_STOCK,
    RECORD_ONLY, VETO, VIOLATED, check_hard_rules, load_protocol,
)

# Mot chuyen bay hop le moi mat — dung lam goc roi doi tung tham so.
# Tu ban 1.4.0 phai co them altitude_m, soc, soh cho luat PH-1; thieu thi PH-1
# bao MISSING va all_clear thanh False (fail closed dung, nhung khong phai y do
# cua fixture).
HOP_LE = dict(payload_g=250, speed_commanded_ms=8, distance_2d_m=472,
              wind_forecast_ms=3.0, ambient_temp_c=15,
              altitude_m=50, soc=0.80, soh=1.0)

# Khung may bay theo ho so — dung de tinh khoi luong cat canh trong test
KHUNG_STOCK_TB47D = 2355
KHUNG_CMU = 3680


def _check(rep, rule_id):
    return next(c for c in rep.checks if c.rule_id == rule_id)


# ---------------------------------------------------------------------------

class TestManufacturerRules:
    """HR-1..HR-4 — gioi han cong bo cua DJI Matrice 100."""

    def test_chuyen_hop_le_qua_het(self):
        rep = check_hard_rules(**HOP_LE)
        assert rep.all_clear
        assert not rep.must_no_fly
        assert rep.violations == []

    @pytest.mark.parametrize("gio,vi_pham", [
        (0.0, False), (5.0, False), (9.9, False), (10.0, False),
        (10.1, True), (14.0, True), (25.0, True),
    ])
    def test_hr1_gio(self, gio, vi_pham):
        rep = check_hard_rules(**{**HOP_LE, "wind_forecast_ms": gio})
        assert (_check(rep, "HR-1").status == VIOLATED) is vi_pham

    @pytest.mark.parametrize("nhiet,vi_pham", [
        (-10.0, False), (0.0, False), (25.0, False), (40.0, False),
        (-10.1, True), (40.1, True), (-40.0, True), (60.0, True),
    ])
    def test_hr2_nhiet_do(self, nhiet, vi_pham):
        rep = check_hard_rules(**{**HOP_LE, "ambient_temp_c": nhiet})
        assert (_check(rep, "HR-2").status == VIOLATED) is vi_pham

    @pytest.mark.parametrize("toc,vi_pham", [
        (4.0, False), (12.0, False), (17.0, False), (17.1, True), (25.0, True),
    ])
    def test_hr4_toc_do(self, toc, vi_pham):
        rep = check_hard_rules(**{**HOP_LE, "speed_commanded_ms": toc})
        assert (_check(rep, "HR-4").status == VIOLATED) is vi_pham

    def test_moi_luat_hr_deu_la_veto(self):
        rep = check_hard_rules(**HOP_LE)
        for rid in ("HR-1", "HR-2", "HR-4"):
            assert _check(rep, rid).severity == VETO

    def test_moi_luat_hr_co_ghi_nguon(self):
        """
        Tien to HR- danh RIENG cho luat co so la SO DJI CONG BO.

        Test nay tung bat mot loi that: luat san nang luong ha canh ban dau
        duoc dat ten HR-5 trong khi nguon la P§4.6 + mo hinh vat ly cua nhom.
        Da doi thanh PH-1 (quyet dinh B10). Giu test nay de khong tai dien —
        thay se hoi "con so nay DJI cong bo o dau" va cau tra loi phai dung.
        """
        rep = check_hard_rules(**HOP_LE)
        for c in rep.checks:
            if c.rule_id.startswith("HR-"):
                assert "DJI" in c.source

    def test_nguong_doc_tu_giao_thuc_khong_viet_cung(self):
        """
        Doi nguong trong giao thuc thi hanh vi phai doi theo. Neu test nay do
        thi co con so viet cung trong ma nguon.
        """
        protocol = load_protocol()
        for r in protocol["hard_rules"]["manufacturer"]:
            if r["id"] == "HR-1":
                r["check"] = "wind_forecast_ms <= 5.0"
        rep = check_hard_rules(**{**HOP_LE, "wind_forecast_ms": 7.0},
                               protocol=protocol)
        assert _check(rep, "HR-1").status == VIOLATED


# ---------------------------------------------------------------------------

class TestPH1:
    """
    PH-1 — pin phai con du nang luong ha canh tu do cao hanh trinh (P§4.6).

    KHONG phai nang luong ha canh BINH THUONG cuoi chuyen: cai do da nam trong
    E_required (quyet dinh B9). Day la SAN cho tinh huong huy chuyen giua duong.
    """

    CHUNG = dict(payload_g=500, speed_commanded_ms=8, distance_2d_m=472,
                 wind_forecast_ms=3.0, ambient_temp_c=15,
                 profile=PROFILE_CMU)

    def _ph1(self, **kw):
        rep = check_hard_rules(**{**self.CHUNG, **kw})
        return next(c for c in rep.checks if c.rule_id == "PH-1")

    def test_du_pin_thi_pass(self):
        assert self._ph1(altitude_m=50, soc=0.50, soh=1.0).status == PASS

    def test_thieu_pin_thi_violated(self):
        c = self._ph1(altitude_m=100, soc=0.03, soh=1.0)
        assert c.status == VIOLATED
        assert c.severity == VETO

    def test_thieu_do_cao_thi_missing(self):
        assert self._ph1(altitude_m=None, soc=0.50, soh=1.0).status == MISSING

    def test_thieu_soc_thi_missing(self):
        assert self._ph1(altitude_m=50, soc=None, soh=1.0).status == MISSING

    def test_thieu_soh_thi_missing(self):
        assert self._ph1(altitude_m=50, soc=0.50, soh=None).status == MISSING

    def test_thieu_tai_trong_thi_missing(self):
        assert self._ph1(altitude_m=50, payload_g=None,
                         soc=0.50, soh=1.0).status == MISSING

    def test_vi_pham_bat_buoc_no_fly(self):
        rep = check_hard_rules(**{**self.CHUNG, "altitude_m": 100,
                                  "soc": 0.03, "soh": 1.0})
        assert rep.must_no_fly is True

    def test_dung_ngay_tai_nguong_thi_pass(self):
        """
        PHAI truyen kappa THAT. min_soc_for_landing() mac dinh kappa = 1.0,
        nhung CHUNG dung 15 C nen kappa = 0.9954 — nguong that CAO HON.
        Khong truyen kappa thi test nay do, va do la do DUNG: nguong mac dinh
        la nguong LAC QUAN.
        """
        k, _ = kappa(15.0)
        nguong = min_soc_for_landing(100, KHUNG_CMU + 500, kappa=k)
        assert self._ph1(altitude_m=100, soc=nguong, soh=1.0).status == PASS

    def test_duoi_nguong_mot_chut_thi_violated(self):
        k, _ = kappa(15.0)
        nguong = min_soc_for_landing(100, KHUNG_CMU + 500, kappa=k)
        assert self._ph1(altitude_m=100, soc=nguong * 0.99,
                         soh=1.0).status == VIOLATED

    def test_nguong_mac_dinh_la_nguong_LAC_QUAN(self):
        """
        min_soc_for_landing() mac dinh kappa = 1.0, tuc gia dinh pin khong bi
        suy giam vi nhiet do. Troi lanh thi nguong THAT cao hon.

        Ai dung ham nay de quyet dinh PHAI truyen kappa that. Bang trong
        reports/d3_landing_energy.csv dung mac dinh nen phai doc la
        "nguong toi thieu o dieu kien tot nhat", khong phai nguong van hanh.
        """
        k_lanh, _ = kappa(0.0)          # 0.9203
        assert k_lanh < 1.0
        mac_dinh = min_soc_for_landing(100, 4180)
        that_su = min_soc_for_landing(100, 4180, kappa=k_lanh)
        assert that_su > mac_dinh, "nguong mac dinh phai LAC QUAN hon"
        assert that_su == pytest.approx(mac_dinh / k_lanh, abs=1e-9)

    def test_hai_ho_so_cho_nguong_khac_nhau(self):
        """Ho so CMU nang hon 1325 g nen ton nhieu nang luong ha canh hon."""
        n_cmu = min_soc_for_landing(100, KHUNG_CMU + 500)
        n_stock = min_soc_for_landing(100, KHUNG_STOCK_TB47D + 500)
        assert n_cmu > n_stock

        # Mot muc SoC co the PASS o ho so stock ma VIOLATED o ho so CMU
        giua = (n_cmu + n_stock) / 2
        assert self._ph1(altitude_m=100, soc=giua, soh=1.0).status == VIOLATED
        rep = check_hard_rules(**{**self.CHUNG, "profile": PROFILE_STOCK,
                                  "altitude_m": 100, "soc": giua, "soh": 1.0})
        assert _check(rep, "PH-1").status == PASS

    def test_bay_cao_hon_thi_nguong_cao_hon(self):
        truoc = -1.0
        for h in (25, 50, 75, 100):
            n = min_soc_for_landing(h, KHUNG_CMU + 500)
            assert n > truoc
            truoc = n

    def test_soc_ngoai_dai_thi_missing_khong_phai_violated(self):
        """
        SoC = 1.5 la SAI chu khong phai thieu. PH-1 khong tinh duoc nen bao
        MISSING; viec tra NO_FLY la cua src/decision_rules.py (quyet dinh B5).
        """
        assert self._ph1(altitude_m=50, soc=1.5, soh=1.0).status == MISSING

    def test_nguon_khong_phai_dji(self):
        """
        PH-1 co NGUYEN TAC tu thay nhung CON SO tu mo hinh vat ly cua nhom.
        Khong duoc trich nhu gioi han nha san xuat.
        """
        c = self._ph1(altitude_m=50, soc=0.50, soh=1.0)
        assert "DJI" not in c.source
        assert "physics_m100" in c.source


# ---------------------------------------------------------------------------

class TestProjectDerived:
    """PD-1, PD-2 — gioi han NHOM rut ra, khong phai cua nha san xuat."""

    @pytest.mark.parametrize("cu_ly,vi_pham", [
        (420.0, False), (472.0, False), (610.0, False),
        (419.9, True), (610.1, True), (835.0, True),
    ])
    def test_pd1_envelope_cu_ly(self, cu_ly, vi_pham):
        rep = check_hard_rules(**{**HOP_LE, "distance_2d_m": cu_ly})
        assert (_check(rep, "PD-1").status == VIOLATED) is vi_pham

    @pytest.mark.parametrize("tai,vi_pham", [
        (0.0, False), (250.0, False), (500.0, False),
        (-1.0, True), (501.0, True), (1000.0, True),
    ])
    def test_pd2_dai_tai_trong(self, tai, vi_pham):
        rep = check_hard_rules(**{**HOP_LE, "payload_g": tai})
        assert (_check(rep, "PD-2").status == VIOLATED) is vi_pham

    def test_pd_la_downgrade_khong_phai_veto(self):
        """
        Khac biet quan trong: PD-* ngan FLY nhung KHONG bat buoc NO_FLY.
        Mo hinh van cho so ngoai envelope, chi la so khong dang tin.
        """
        rep = check_hard_rules(**{**HOP_LE, "distance_2d_m": 835.0})
        c = _check(rep, "PD-1")
        assert c.severity == DOWNGRADE
        assert c.blocks_fly is True
        assert c.forces_no_fly is False
        assert rep.must_no_fly is False
        assert rep.blocks_fly is True

    def test_ngoai_envelope_duoc_danh_dau_ngoai_suy(self):
        """§6/E3: 'clearly label any extrapolated ranges'."""
        assert check_hard_rules(**{**HOP_LE, "distance_2d_m": 835.0}).extrapolated
        assert check_hard_rules(**{**HOP_LE, "payload_g": 800}).extrapolated
        assert not check_hard_rules(**HOP_LE).extrapolated

    def test_pd_khong_ghi_nguon_dji(self):
        """
        PD-* la phat hien cua nhom, khong duoc trich nhu gioi han nha san xuat.
        Tron hai loai lai la loi hoc thuat.
        """
        rep = check_hard_rules(**HOP_LE)
        for c in rep.checks:
            if c.rule_id.startswith("PD-"):
                assert "DJI" not in c.source


# ---------------------------------------------------------------------------

class TestAircraftProfiles:
    """Quyet dinh B6 — hai ho so may bay."""

    def test_stock_tai_500g_qua_mtow(self):
        """2355 + 500 = 2855 g < 3600 g."""
        rep = check_hard_rules(**{**HOP_LE, "payload_g": 500},
                               profile=PROFILE_STOCK)
        assert _check(rep, "HR-3").status == PASS

    def test_stock_tai_1500g_vuot_mtow(self):
        """2355 + 1500 = 3855 g > 3600 g."""
        rep = check_hard_rules(**{**HOP_LE, "payload_g": 1500},
                               profile=PROFILE_STOCK)
        c = _check(rep, "HR-3")
        assert c.status == VIOLATED
        assert c.severity == VETO
        assert rep.must_no_fly

    def test_stock_pin_tb48d_nang_hon(self):
        """Khung TB48D nang hon 76 g nen nguong tai thap hon."""
        a = check_hard_rules(**{**HOP_LE, "payload_g": 1200},
                             battery_type="TB47D", profile=PROFILE_STOCK)
        b = check_hard_rules(**{**HOP_LE, "payload_g": 1200},
                             battery_type="TB48D", profile=PROFILE_STOCK)
        assert _check(a, "HR-3").status == PASS      # 2355 + 1200 = 3555
        assert _check(b, "HR-3").status == VIOLATED  # 2431 + 1200 = 3631

    @pytest.mark.parametrize("tai", [0, 250, 500])
    def test_cmu_moi_cau_hinh_deu_vuot_mtow(self, tai):
        """
        Phat hien o parameter_table.md muc 3.1: 3680-4180 g, vuot MTOW o MOI
        cau hinh. Phai bao KNOWN_EXCEEDED, KHONG duoc veto.
        """
        rep = check_hard_rules(**{**HOP_LE, "payload_g": tai},
                               profile=PROFILE_CMU)
        c = _check(rep, "HR-3")
        assert c.status == KNOWN_EXCEEDED
        assert c.severity == RECORD_ONLY

    def test_cmu_khong_lam_moi_chuyen_thanh_no_fly(self):
        """
        Day la ly do ton tai cua B6. Neu HR-3 veto o ho so CMU thi 192/192
        chuyen NO_FLY va benchmark vo nghia.
        """
        for tai in (0, 250, 500):
            rep = check_hard_rules(**{**HOP_LE, "payload_g": tai},
                                   profile=PROFILE_CMU)
            assert not rep.must_no_fly
            assert rep.all_clear

    def test_khoi_luong_khop_bang_parameter_table(self):
        """3680 + 500 = 4180 g — phai khop bang o parameter_table.md muc 3.1."""
        rep = check_hard_rules(**{**HOP_LE, "payload_g": 500},
                               profile=PROFILE_CMU)
        assert "4180 g" in _check(rep, "HR-3").detail

    def test_ho_so_la(self):
        with pytest.raises(ValueError, match="ho so may bay khong biet"):
            check_hard_rules(**HOP_LE, profile="M210")

    def test_mac_dinh_la_ho_so_van_hanh(self):
        assert check_hard_rules(**HOP_LE).profile == PROFILE_STOCK


# ---------------------------------------------------------------------------

class TestVetoSemantics:
    """
    §4.6: "no score, no model output and no human approval may convert a
    hard-rule violation into FLY."
    """

    def test_lop_nay_khong_nhan_dau_ra_mo_hinh(self):
        """
        Kiem tren chu ky ham: neu co tham so nao lien quan nang luong hay bien
        du tru thi lop luat cung da khong con doc lap voi mo hinh.

        Test nay tung bat mot loi that: ban dau PH-1 duoc cai bang cach truyen
        `e_available_Wh` vao ham nay. Da doi thanh truyen `soc`/`soh` (dau vao
        THO) va de lop luat cung tu goi available_energy() — quyet dinh B10b.
        """
        import inspect
        from src import safety_invariants

        tham_so = set(inspect.signature(
            safety_invariants.check_hard_rules).parameters)
        cam = {"energy", "e_required", "e_available", "margin", "reserve",
               "score", "verdict", "prediction"}
        assert not (tham_so & cam)
        assert not any(any(c in p for c in cam) for p in tham_so)

    @pytest.mark.parametrize("kw", [
        {"wind_forecast_ms": 14.0},
        {"ambient_temp_c": -25.0},
        {"speed_commanded_ms": 20.0},
        {"payload_g": 2000},
    ])
    def test_vi_pham_veto_luon_bat_buoc_no_fly(self, kw):
        assert check_hard_rules(**{**HOP_LE, **kw}).must_no_fly

    def test_nhieu_vi_pham_cung_luc_deu_duoc_ghi(self):
        """Phai liet ke HET, khong dung o cai dau tien — nguoi dung can biet ca."""
        rep = check_hard_rules(**{**HOP_LE, "wind_forecast_ms": 14.0,
                                  "ambient_temp_c": -25.0,
                                  "speed_commanded_ms": 20.0})
        assert {c.rule_id for c in rep.violations} >= {"HR-1", "HR-2", "HR-4"}
        assert len(rep.reasons()) >= 3

    def test_downgrade_khong_nang_cap_duoc(self):
        """PD-* ngan FLY ngay ca khi moi luat nha san xuat deu qua."""
        rep = check_hard_rules(**{**HOP_LE, "distance_2d_m": 900})
        assert not rep.violations or all(
            c.rule_id.startswith("PD-") for c in rep.violations)
        assert rep.blocks_fly

    def test_luon_kiem_du_bay_luat(self):
        """
        Khong duoc bo qua luat nao, ke ca khi da co vi pham.

        Bay luat, ba ho ma: HR-1..HR-4 (DJI), PH-1 (P§4.6 + nhom),
        PD-1..PD-2 (thi nghiem nhom).
        """
        rep = check_hard_rules(**{**HOP_LE, "wind_forecast_ms": 99.0})
        assert {c.rule_id for c in rep.checks} == {
            "HR-1", "HR-2", "HR-3", "HR-4", "PH-1", "PD-1", "PD-2"}

    def test_tat_dinh(self):
        """INV-4."""
        goc = str(check_hard_rules(**HOP_LE))
        for _ in range(100):
            assert str(check_hard_rules(**HOP_LE)) == goc


# ---------------------------------------------------------------------------

class TestFailClosed:
    """§4.6 — thieu dau vao khong duoc roi ve gia tri thuan loi."""

    @pytest.mark.parametrize("thieu", [
        "payload_g", "speed_commanded_ms", "distance_2d_m",
        "wind_forecast_ms", "ambient_temp_c", "altitude_m", "soc", "soh",
    ])
    def test_thieu_bat_ky_dau_vao_nao_deu_chan_fly(self, thieu):
        rep = check_hard_rules(**{**HOP_LE, thieu: None})
        assert rep.missing, f"thieu {thieu} ma khong bao"
        assert rep.blocks_fly
        assert not rep.all_clear

    def test_thieu_khong_phai_la_vi_pham(self):
        """
        Phan biet 'khong biet' voi 'sai'. §4.6 cho hai ket cuc khac nhau:
        INSUFFICIENT_DATA va NO_FLY.
        """
        rep = check_hard_rules(**{**HOP_LE, "wind_forecast_ms": None})
        c = _check(rep, "HR-1")
        assert c.status == MISSING
        assert c.status != VIOLATED
        assert not rep.must_no_fly

    def test_thieu_het_dau_vao(self):
        """Bay luat, moi luat deu phai bao thieu."""
        rep = check_hard_rules()
        assert len(rep.missing) == 7
        assert rep.blocks_fly

    def test_nan_khong_lot_qua(self):
        for truong in ("distance_2d_m", "ambient_temp_c", "payload_g"):
            rep = check_hard_rules(**{**HOP_LE, truong: math.nan})
            assert rep.blocks_fly, f"NaN lot qua o {truong}"

    def test_moi_ly_do_deu_doc_duoc(self):
        rep = check_hard_rules(**{**HOP_LE, "wind_forecast_ms": None,
                                  "ambient_temp_c": -50})
        ly_do = rep.reasons()
        assert any("thieu" in r for r in ly_do)
        assert any("ngoai dai" in r for r in ly_do)


# ---------------------------------------------------------------------------

class TestNangLuongHaCanh:
    """Ham tinh nang luong ha canh — src/physics_m100.py, phuc vu PH-1."""

    def test_tang_do_cao_thi_tang_nang_luong(self):
        truoc = -1.0
        for h in (0, 25, 50, 75, 100):
            e = landing_energy_Wh(h, 4180)
            assert e > truoc, f"khong don dieu tang tai h={h}"
            truoc = e

    def test_tang_khoi_luong_thi_tang_nang_luong(self):
        nhe = landing_energy_Wh(50, KHUNG_STOCK_TB47D)
        nang = landing_energy_Wh(50, KHUNG_CMU + 500)
        assert nang > nhe

    def test_do_cao_bang_khong_thi_khong_ton_gi(self):
        assert landing_energy_Wh(0, 4180) == 0.0

    def test_thieu_dau_vao_tra_none(self):
        """Tra None de lop luat cung bao MISSING — KHONG tu dien mac dinh."""
        assert landing_energy_Wh(None, 4180) is None
        assert landing_energy_Wh(50, None) is None
        assert min_soc_for_landing(None, 4180) is None
        assert min_soc_for_landing(50, None) is None

    def test_tham_so_vo_ly_thi_bao_loi(self):
        with pytest.raises(ValueError):
            landing_energy_Wh(-10, 4180)
        with pytest.raises(ValueError):
            landing_energy_Wh(50, 0)
        with pytest.raises(ValueError):
            landing_energy_Wh(50, -100)
        with pytest.raises(ValueError):
            landing_energy_Wh(50, 4180, descent_rate_ms=0)

    def test_soc_min_khop_voi_nang_luong(self):
        """SoC_min * E_nominal phai bang DUNG E_landing."""
        e = landing_energy_Wh(100, 4180)
        soc = min_soc_for_landing(100, 4180)
        assert abs(soc * 99.9 - e) < 1e-9

    def test_soc_min_tang_khi_pin_yeu_di(self):
        tot = min_soc_for_landing(100, 4180, soh=1.0)
        yeu = min_soc_for_landing(100, 4180, soh=0.8)
        assert yeu > tot

    def test_soc_min_bi_chan_tren_boi_1(self):
        """Pin gan het suc khoe -> yeu cau khong duoc vuot 100 %."""
        assert min_soc_for_landing(100, 4180, soh=0.01) == 1.0

    def test_khop_gia_tri_da_cong_bo(self):
        """
        Doi chieu voi reports/d3_landing_energy.csv (lam tron 4 chu so) va
        bang trong d3_protocol.yaml muc physics_derived.binding_analysis.
        """
        mong_doi = {25: 2.9828, 50: 5.9655, 75: 8.9483, 100: 11.9310}
        for h, v in mong_doi.items():
            assert abs(round(landing_energy_Wh(h, 4180), 4) - v) < 1e-9, (
                f"lech o h={h}: CSV ghi {v}")


# ---------------------------------------------------------------------------

class TestINV8:
    """
    INV-8 — thieu pin ha canh thi KHONG BAO GIO ra FLY, va bien phap giam
    thieu KHONG lat duoc (vi PH-1 la VETO).

    Khac TestPH1: nhom nay di qua duong chay DAY DU (assess()), nen kiem ca
    viec PH-1 noi dung day voi cac buoc phan quyet phia sau.
    """

    GOC = dict(speed_commanded_ms=8, distance_2d_m=472,
               wind_forecast_ms=3.0, ambient_temp_c=15,
               soh=1.0, e_required_Wh=5.0, profile=PROFILE_CMU)

    def test_quet_do_cao_va_tai_trong(self):
        da_kiem = 0
        for h in (25, 50, 75, 100):
            for tai in (0, 250, 500):
                nguong = min_soc_for_landing(h, KHUNG_CMU + tai)
                for he_so in (0.3, 0.6, 0.9):
                    soc = nguong * he_so
                    if soc <= 0:
                        continue
                    d = assess(payload_g=tai, altitude_m=h, soc=soc, **self.GOC)
                    assert d.verdict != FLY, (
                        f"ra FLY voi SoC {soc:.4f} < nguong ha canh "
                        f"{nguong:.4f} tai h={h} m, tai={tai} g")
                    da_kiem += 1
        assert da_kiem >= 30, f"quet qua it truong hop: {da_kiem}"

    def test_vi_pham_ra_dung_no_fly_khong_phai_insufficient(self):
        nguong = min_soc_for_landing(100, KHUNG_CMU + 500)
        d = assess(payload_g=500, altitude_m=100, soc=nguong * 0.5, **self.GOC)
        assert d.verdict == NO_FLY
        assert any("PH-1" in r for r in d.reasons)

    def test_ly_do_chan_that_dung_dau_danh_sach(self):
        """
        Ly do THUC SU chan phai la reasons[0]. Neu khong, muc HR-3
        KNOWN_EXCEEDED (von "ghi nhan, khong chan") se chiem cho va che mat ly
        do that — nguoi dieu phoi doc se di sua sai cho.
        """
        nguong = min_soc_for_landing(100, KHUNG_CMU + 500)
        d = assess(payload_g=500, altitude_m=100, soc=nguong * 0.5, **self.GOC)
        assert "PH-1" in d.reasons[0]

    def test_du_pin_ha_canh_thi_khong_bi_chan(self):
        d = assess(payload_g=250, altitude_m=50, soc=0.80, **self.GOC)
        ph1 = next(c for c in d.hard_rule_report.checks
                   if c.rule_id == "PH-1")
        assert ph1.status == PASS

    def test_veto_bien_phap_khong_lat_duoc(self):
        """
        Quan trong nhat trong nhom nay. Khong co test nay thi bien phap giam
        thieu (M1 sac them pin...) co the thanh CUA SAU de lach PH-1 — dung loi
        ma mitigations.py da co test chan cho HR-1.
        """
        nguong = min_soc_for_landing(100, KHUNG_CMU + 500)
        for bp in ("M1", "M2", "M5", "M7"):
            d = assess(payload_g=500, altitude_m=100, soc=nguong * 0.5,
                       mitigation_applied=bp, **self.GOC)
            assert d.verdict == NO_FLY, f"bien phap {bp} lat duoc PH-1"
            assert d.actionable is False

    def test_thieu_do_cao_thi_khong_ra_fly(self):
        d = assess(payload_g=250, altitude_m=None, soc=1.0, **self.GOC)
        assert d.verdict == INSUFFICIENT_DATA

    def test_soc_ngoai_dai_ra_no_fly_khong_phai_insufficient(self):
        """
        Quyet dinh B5: 'biet chac la sai' -> NO_FLY; 'khong biet' ->
        INSUFFICIENT_DATA. Buoc kiem ngoai-dai phai xet TRUOC buoc thieu
        du lieu, neu khong thi PH-1 (bao MISSING vi khong tinh duoc) se chiem
        truoc va cho ra INSUFFICIENT_DATA.
        """
        d = assess(payload_g=250, altitude_m=50, soc=1.5, **self.GOC)
        assert d.verdict == NO_FLY

    def test_pin_day_thi_khong_bao_gio_bi_chan(self):
        """Pin day 99.9 Wh > nang luong ha canh lon nhat 11.93 Wh."""
        for h in (25, 50, 75, 100):
            for tai in (0, 250, 500):
                d = assess(payload_g=tai, altitude_m=h, soc=1.0, **self.GOC)
                ph1 = next(c for c in d.hard_rule_report.checks
                           if c.rule_id == "PH-1")
                assert ph1.status == PASS, f"h={h}, tai={tai}"

    def test_don_dieu_van_dung_sau_khi_them_ph1(self):
        """
        INV-3 phai con hieu luc: pin nhieu hon -> phan quyet khong xau di.
        PH-1 la mot nguong theo nang luong kha dung nen no KHONG duoc pha tinh
        don dieu. Day la dieu kien tien quyet de thuat toan chia doi tim SoC
        toi thieu o evaluation_decision.py co nghia.
        """
        truoc = -1
        for soc in [i / 50 for i in range(1, 51)]:
            d = assess(payload_g=500, altitude_m=100, soc=soc, **self.GOC)
            muc = VERDICT_ORDER.index(d.verdict)
            assert muc >= truoc, (
                f"phan quyet xau di khi SoC tang len {soc:.2f}: {d.verdict}")
            truoc = muc


# ---------------------------------------------------------------------------

class TestProtocolHardRules:
    """Kiem phan luat cung cua configs/d3_protocol.yaml."""

    @pytest.fixture(scope="class")
    def protocol(self):
        return load_protocol()

    def test_hai_ho_so_may_bay(self, protocol):
        p = protocol["aircraft_profiles"]
        assert PROFILE_STOCK in p and PROFILE_CMU in p

    def test_ho_so_cmu_khong_veto_mtow(self, protocol):
        cfg = protocol["aircraft_profiles"][PROFILE_CMU]
        assert cfg["mtow_rule"].startswith("KNOWN_EXCEEDED")
        assert cfg["airframe_mass_g"] == 3680

    def test_ho_so_stock_veto_mtow(self, protocol):
        cfg = protocol["aircraft_profiles"][PROFILE_STOCK]
        assert cfg["mtow_rule"].startswith("VETO")
        assert cfg["airframe_mass_g"]["TB47D"] == 2355

    def test_hai_muc_do_vi_pham(self, protocol):
        sev = protocol["hard_rules"]["severity"]
        assert sev["manufacturer"].startswith("VETO")
        assert sev["project_derived"].startswith("DOWNGRADE")

    def test_quyet_dinh_b6_duoc_ghi(self, protocol):
        ids = [d["id"] for c in protocol["change_log"]
               for d in c.get("decisions", [])]
        assert "B6" in ids

    def test_ph1_khai_trong_giao_thuc(self, protocol):
        """PH-1 phai nam o muc rieng, KHONG nhet vao `manufacturer`."""
        pd_ = protocol["hard_rules"]["physics_derived"]
        assert [r["id"] for r in pd_] == ["PH-1"]
        assert pd_[0]["severity"] == VETO
        assert "DJI" not in pd_[0]["source"]
        assert pd_[0]["descent_rate_ms"] == 1.5
        ma_manufacturer = [r["id"] for r in protocol["hard_rules"]["manufacturer"]]
        assert "PH-1" not in ma_manufacturer
        assert "HR-5" not in ma_manufacturer

    def test_quyet_dinh_b10_duoc_ghi(self, protocol):
        ids = [d["id"] for c in protocol["change_log"]
               for d in c.get("decisions", [])]
        assert "B10" in ids
        assert "B10b" in ids

    def test_minimum_soc_da_cai(self, protocol):
        """OI-D3-1 da dong — muc minimum_soc khong con treo."""
        ms = protocol["hard_rules"]["minimum_soc"]
        assert ms["status"].startswith("DA CAI")
        oi = [o for o in protocol["open_items"] if o["id"] == "OI-D3-1"]
        assert oi and oi[0].get("status") == "DONG"