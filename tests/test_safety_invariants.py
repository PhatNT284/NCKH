"""
Test cho src/safety_invariants.py — lop luat cung, khoi (d) cua san pham D3.

Nam nhom:
    TestManufacturerRules  HR-1..HR-4, luat cua DJI
    TestProjectDerived     PD-1, PD-2, gioi han nhom rut ra tu thi nghiem
    TestAircraftProfiles   quyet dinh B6 — hai ho so may bay
    TestVetoSemantics      §4.6 — khong gi lat duoc vi pham luat cung
    TestFailClosed         §4.6 — thieu dau vao thi khong duoc qua
"""

from __future__ import annotations

import math

import pytest

from src.safety_invariants import (
    DOWNGRADE, KNOWN_EXCEEDED, MISSING, PASS, PROFILE_CMU, PROFILE_STOCK,
    RECORD_ONLY, VETO, VIOLATED, check_hard_rules, load_protocol,
)

# Mot chuyen bay hop le moi mat — dung lam goc roi doi tung tham so
HOP_LE = dict(payload_g=250, speed_commanded_ms=8, distance_2d_m=472,
              wind_forecast_ms=3.0, ambient_temp_c=15)


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

    def test_luon_kiem_du_sau_luat(self):
        """Khong duoc bo qua luat nao, ke ca khi da co vi pham."""
        rep = check_hard_rules(**{**HOP_LE, "wind_forecast_ms": 99.0})
        assert {c.rule_id for c in rep.checks} == {
            "HR-1", "HR-2", "HR-3", "HR-4", "PD-1", "PD-2"}

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
        "wind_forecast_ms", "ambient_temp_c",
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
        rep = check_hard_rules()
        assert len(rep.missing) == 6
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
