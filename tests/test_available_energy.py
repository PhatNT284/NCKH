"""
Test cho src/available_energy.py — khoi (a) cua san pham D3.

Bon nhom:
    TestKappa            he so nhiet do, quyet dinh B3
    TestAvailableEnergy  cong thuc §5.4 Eq (2)
    TestFailClosed       §4.6 — thieu / sai dau vao thi KHONG duoc tra so
    TestProtocolD3       kiem chinh file configs/d3_protocol.yaml
"""

from __future__ import annotations

import math

import pytest

from src.available_energy import (
    REGIME_ABOVE, REGIME_BELOW, REGIME_IN,
    STATUS_MISSING, STATUS_OK, STATUS_OUT_OF_RANGE,
    _poly, available_energy, kappa, load_protocol,
)

LO, HI = 4.5, 18.4


# ---------------------------------------------------------------------------

class TestKappa:
    """He so nhiet do — quyet dinh B3, kep MOT PHIA."""

    def test_trong_dai_bang_da_thuc(self):
        for t in (5.0, 10.0, 15.0, 18.0):
            k, regime = kappa(t)
            assert regime == REGIME_IN
            assert k == pytest.approx(min(1.0, _poly(t)), abs=1e-12)

    def test_duoi_dai_giu_o_bien_lanh(self):
        """
        Day la noi dung chinh cua B3. Quy tac cu tra ve 1.0 o day — SAI, vi
        cang lanh thi pin cang yeu, khong the cang khoe.
        """
        bien = _poly(LO)
        for t in (4.4, 0.0, -5.0, -10.0):
            k, regime = kappa(t)
            assert regime == REGIME_BELOW
            assert k == pytest.approx(bien, abs=1e-12)
            assert k < 1.0, "kappa o phia lanh KHONG duoc bang 1"

    def test_tren_dai_chan_tren_bang_1(self):
        """
        Da thuc goc tra ve > 1 trong khoang ~15.8-75.2 C. Pin khong the chua
        nhieu nang luong hon muc danh dinh cua chinh no.
        """
        for t in (18.5, 25.0, 40.0, 45.5):
            k, regime = kappa(t)
            assert regime == REGIME_ABOVE
            assert k == 1.0

    def test_khong_bao_gio_vuot_1(self):
        for t in range(-20, 81):
            k, _ = kappa(float(t))
            assert k <= 1.0

    def test_khong_bao_gio_am(self):
        for t in range(-20, 81):
            k, _ = kappa(float(t))
            assert k > 0.0

    def test_lien_tuc_tai_bien_lanh(self):
        """Khong duoc co buoc nhay tai 4.5 C — do la loi cua quy tac cu."""
        assert kappa(LO - 1e-9)[0] == pytest.approx(kappa(LO)[0], abs=1e-6)

    def test_khong_nhay_nguoc_khi_lanh_dan(self):
        """
        Bat bien quan trong nhat cua B3: di tu nong ve lanh, kappa khong bao gio
        TANG. Quy tac cu vi pham dung cho nay tai 4.5 C.
        """
        temps = [t / 10 for t in range(400, -101, -1)]   # 40.0 -> -10.0
        truoc = kappa(temps[0])[0]
        for t in temps[1:]:
            hien = kappa(t)[0]
            assert hien <= truoc + 1e-12, f"kappa tang nguoc tai T = {t}"
            truoc = hien

    def test_gia_tri_bien_khop_giao_thuc(self):
        """0.9203 ghi trong giao thuc phai khop da thuc tinh tai 4.5 C."""
        assert _poly(LO) == pytest.approx(0.9203, abs=5e-5)


# ---------------------------------------------------------------------------

class TestAvailableEnergy:
    """E_available = E_nominal * SoC * SoH * kappa(T) — §5.4, Eq (2)."""

    def test_cong_thuc_dung(self):
        r = available_energy(soc=0.8, soh=0.9, temp_c=15.0)
        k, _ = kappa(15.0)
        assert r.ok
        assert r.value_Wh == pytest.approx(99.9 * 0.8 * 0.9 * k, abs=1e-9)

    def test_pin_day_moi_trong_dai_nong(self):
        """SoC = SoH = 1, kappa = 1 -> dung bang muc danh dinh."""
        r = available_energy(soc=1.0, soh=1.0, temp_c=25.0)
        assert r.value_Wh == pytest.approx(99.9, abs=1e-9)

    def test_khong_bao_gio_vuot_muc_danh_dinh(self):
        for soc in (0.0, 0.5, 1.0):
            for soh in (0.5, 0.8, 1.0):
                for t in (-10, 0, 10, 20, 40):
                    r = available_energy(soc, soh, t)
                    assert r.ok
                    assert r.value_Wh <= 99.9 + 1e-9

    def test_don_dieu_theo_soc(self):
        """Pin nhieu hon -> nang luong kha dung khong bao gio it di (INV-3)."""
        truoc = -1.0
        for soc in [i / 100 for i in range(0, 101)]:
            v = available_energy(soc, 0.9, 15.0).value_Wh
            assert v >= truoc
            truoc = v

    def test_don_dieu_theo_soh(self):
        truoc = -1.0
        for soh in [i / 100 for i in range(0, 101)]:
            v = available_energy(0.8, soh, 15.0).value_Wh
            assert v >= truoc
            truoc = v

    def test_soc_bang_0_cho_0_wh(self):
        assert available_energy(0.0, 1.0, 15.0).value_Wh == 0.0

    def test_do_nhay_loai_pin(self):
        """OI-2: TB48D phai cho nhieu hon, va dung ti le 129.96/99.9."""
        a = available_energy(0.8, 0.9, 15.0, battery_type="TB47D")
        b = available_energy(0.8, 0.9, 15.0, battery_type="TB48D")
        assert b.value_Wh > a.value_Wh
        assert b.value_Wh / a.value_Wh == pytest.approx(129.96 / 99.9, abs=1e-9)

    def test_mac_dinh_la_pin_bao_thu(self):
        """Mac dinh phai la TB47D — gia tri NHO HON, huong an toan."""
        assert (available_energy(0.8, 0.9, 15.0).value_Wh
                == available_energy(0.8, 0.9, 15.0, battery_type="TB47D").value_Wh)

    def test_loai_pin_la(self):
        with pytest.raises(ValueError, match="loai pin khong biet"):
            available_energy(0.8, 0.9, 15.0, battery_type="TB55")

    def test_tat_dinh(self):
        """INV-4: cung dau vao -> cung dau ra, moi lan chay."""
        goc = available_energy(0.73, 0.88, 11.3).value_Wh
        for _ in range(100):
            assert available_energy(0.73, 0.88, 11.3).value_Wh == goc

    def test_ghi_nhan_che_do_nhiet_do(self):
        """Bao cao phai biet bao nhieu truong hop roi ra ngoai dai hieu chinh."""
        assert available_energy(0.8, 0.9, 0.0).temp_regime == REGIME_BELOW
        assert available_energy(0.8, 0.9, 10.0).temp_regime == REGIME_IN
        assert available_energy(0.8, 0.9, 30.0).temp_regime == REGIME_ABOVE

    def test_ngoai_dai_hieu_chinh_co_ghi_chu(self):
        assert available_energy(0.8, 0.9, 0.0).reasons
        assert available_energy(0.8, 0.9, 30.0).reasons


# ---------------------------------------------------------------------------

class TestFailClosed:
    """
    §4.6: "a missing, invalid, out-of-range or stale safety-critical input does
    not fall back to a favourable default".
    """

    @pytest.mark.parametrize("soc,soh,temp", [
        (None, 0.9, 15.0),
        (0.8, None, 15.0),
        (0.8, 0.9, None),
        (None, None, None),
    ])
    def test_thieu_dau_vao_tra_missing(self, soc, soh, temp):
        r = available_energy(soc, soh, temp)
        assert r.status == STATUS_MISSING
        assert r.value_Wh is None, "thieu du lieu ma van tra ve mot con so"
        assert r.reasons
        assert not r.ok

    def test_thieu_khong_duoc_coi_la_0(self):
        """
        Bay quen nhat: coi None la 0. Hai truong hop nay PHAI khac nhau —
        mot cai la 'khong biet', mot cai la 'pin can'.
        """
        assert available_energy(None, 0.9, 15.0).status == STATUS_MISSING
        assert available_energy(0.0, 0.9, 15.0).status == STATUS_OK

    def test_thieu_khong_duoc_coi_la_1(self):
        assert available_energy(0.8, None, 15.0).value_Wh is None

    @pytest.mark.parametrize("soc,soh", [
        (1.5, 0.9), (-0.1, 0.9), (0.8, 1.2), (0.8, -0.5),
    ])
    def test_ngoai_dai_tra_out_of_range(self, soc, soh):
        r = available_energy(soc, soh, 15.0)
        assert r.status == STATUS_OUT_OF_RANGE
        assert r.value_Wh is None

    @pytest.mark.parametrize("temp", [-40.0, -10.1, 40.1, 100.0])
    def test_nhiet_do_ngoai_dai_van_hanh(self, temp):
        """HR-2: dai van hanh M100 la -10..40 C."""
        r = available_energy(0.8, 0.9, temp)
        assert r.status == STATUS_OUT_OF_RANGE
        assert r.value_Wh is None
        assert "HR-2" in " ".join(r.reasons)

    def test_bien_dai_van_hanh_van_hop_le(self):
        assert available_energy(0.8, 0.9, -10.0).ok
        assert available_energy(0.8, 0.9, 40.0).ok

    def test_thieu_uu_tien_hon_ngoai_dai(self):
        """Thieu va sai cung luc -> bao thieu truoc, vi do la van de goc."""
        assert available_energy(None, 5.0, 15.0).status == STATUS_MISSING

    def test_gia_tri_la_nan_khong_lot_qua(self):
        r = available_energy(math.nan, 0.9, 15.0)
        assert r.status == STATUS_OUT_OF_RANGE


# ---------------------------------------------------------------------------

class TestProtocolD3:
    """Kiem chinh file giao thuc, giong TestProtocolIntegrity cua D2."""

    @pytest.fixture(scope="class")
    def protocol(self):
        return load_protocol()

    def test_phien_ban_va_chu_so_huu(self, protocol):
        assert protocol["meta"]["version"]
        assert protocol["meta"]["work_package"] == "WP3"
        assert protocol["meta"]["deliverable"] == "D3"

    def test_d3_khong_chua_mo_hinh_hoc_may(self, protocol):
        assert protocol["foundation"]["d3_contains_no_learned_model"] is True

    def test_du_bon_muc_phan_quyet(self, protocol):
        ids = [v["id"] for v in protocol["reserve_and_verdict"]["verdicts"]["levels"]]
        assert ids == ["FLY", "CONDITIONAL", "NO_FLY", "INSUFFICIENT_DATA"]

    def test_dai_hieu_chinh_kappa(self, protocol):
        assert (protocol["available_energy"]["kappa_temperature"]
                ["calibrated_range_c"] == [4.5, 18.4])

    def test_e_nominal_bao_thu_la_chinh(self, protocol):
        cfg = protocol["available_energy"]["e_nominal"]
        assert cfg["primary_Wh"] == 99.9
        assert cfg["sensitivity_Wh"] == 129.96
        assert cfg["primary_Wh"] < cfg["sensitivity_Wh"], "gia tri chinh phai bao thu hon"

    def test_du_bon_luat_cung_nha_san_xuat(self, protocol):
        """
        Muc `manufacturer` chi duoc chua luat co so la SO DJI CONG BO.
        PH-1 (san nang luong ha canh) nam o muc rieng `physics_derived`.
        """
        ids = [r["id"] for r in protocol["hard_rules"]["manufacturer"]]
        assert ids == ["HR-1", "HR-2", "HR-3", "HR-4"]

    def test_luat_cung_co_quyen_phu_quyet(self, protocol):
        assert protocol["hard_rules"]["veto"] is True

    def test_khong_dung_tai_trong_1245g(self, protocol):
        """d2_protocol 1.3.0: may bay trong bo du lieu vuot MTOW."""
        rule = protocol["hard_rules"]["payload_rule"]
        assert rule["do_not_use_value_g"] == 1245
        assert rule["use_range_g"] == [0, 500]

    def test_envelope_cu_ly_tach_khoi_luat_nha_san_xuat(self, protocol):
        """
        Envelope 420-610 m la phat hien cua NHOM tu E2c, khong phai gioi han
        nha san xuat. Tron hai loai lai la loi hoc thuat.
        """
        pd_ids = [r["id"] for r in protocol["hard_rules"]["project_derived"]]
        assert "PD-1" in pd_ids
        hr_sources = {r["source"] for r in protocol["hard_rules"]["manufacturer"]}
        assert all("DJI" in s for s in hr_sources)

    def test_he_so_du_tru_co_quet_ba_muc(self, protocol):
        cfg = protocol["reserve_and_verdict"]["reserve_factor"]
        assert cfg["primary"] == 0.20
        assert cfg["sweep"] == [0.10, 0.20, 0.30]

    def test_khoan_bat_dinh_khop_phan_du_d2(self, protocol):
        """
        Nguong FLY cong them p95(|phan du|) cua D2-b. Con so phai khop
        reports/d2_oof_residuals.csv, neu khong thi nguong mat can cu.
        """
        import numpy as np
        import pandas as pd
        from src.available_energy import REPO_ROOT

        ghi = protocol["energy_required"]["measured_error"]["p95_abs_residual_Wh"]
        r = pd.read_csv(REPO_ROOT / "reports" / "d2_oof_residuals.csv")
        that = np.percentile(np.abs(r["D2_ridge_preflight"].to_numpy()), 95)
        assert ghi == pytest.approx(that, abs=1e-3)

    def test_sai_so_d2_khop_phan_du_oof(self, protocol):
        """
        Moi con so trong `measured_error` phai tinh tu CUNG mot nguon —
        phan du out-of-fold gop. Tron voi trung binh fold cua E2a se lech o
        chu so thap phan thu ba va lam mat can cu cua nguong FLY.
        """
        import numpy as np
        import pandas as pd
        from src.available_energy import REPO_ROOT

        r = (pd.read_csv(REPO_ROOT / "reports" / "d2_oof_residuals.csv")
             ["D2_ridge_preflight"].to_numpy())
        cfg = protocol["energy_required"]["measured_error"]
        assert cfg["MAE_Wh"] == pytest.approx(np.mean(np.abs(r)), abs=1e-3)
        assert cfg["RMSE_Wh"] == pytest.approx(np.sqrt(np.mean(r**2)), abs=1e-3)
        assert cfg["bias_Wh"] == pytest.approx(np.mean(r), abs=1e-3)

    def test_khong_tron_hai_nguon_sai_so(self, protocol):
        """
        E2a bao trung binh qua fold, lech o chu so thu ba. Test nay chot rang
        giao thuc dung nguon GOP chu khong phai nguon E2a.
        """
        import pandas as pd
        from src.available_energy import REPO_ROOT

        cv = pd.read_csv(REPO_ROOT / "reports" / "d2_e2a_flight_level_cv.csv")
        e2a = cv[cv["model"] == "D2_ridge_preflight"].iloc[0]["MAE"]
        cfg = protocol["energy_required"]["measured_error"]
        assert cfg["basis"] == "phan du out-of-fold gop, 192 chuyen"
        assert cfg["MAE_Wh"] != pytest.approx(e2a, abs=1e-5)

    def test_mo_hinh_duoc_chot_la_d2b(self, protocol):
        assert protocol["energy_required"]["estimator"] == "D2_ridge_preflight"
        assert protocol["energy_required"]["frozen"] is True

    def test_envelope_khop_d2(self, protocol):
        assert protocol["energy_required"]["validity_envelope"]["distance_2d_m"] == [420, 610]

    def test_du_tam_bat_bien(self, protocol):
        """
        Tam bat bien tu ban 1.4.0 (them INV-8 — san nang luong ha canh).

        Test nay la cho phai sua moi khi them bat bien. Va src/evaluation_decision.py
        giờ doc danh sach TU GIAO THUC roi nem loi neu thieu ham kiem, nen CSV
        khong con lech so dong voi giao thuc nua.
        """
        ids = [t["id"] for t in protocol["invariants"]["tests"]]
        assert ids == [f"INV-{i}" for i in range(1, 9)]

    def test_quy_uoc_ngan_sach_nang_luong_day_du(self, protocol):
        """
        P§4.5 bat khai BON quy uoc de chong dem hai lan (quyet dinh B9).
        Thieu mot cai la mo duong cho loi cong nang luong ha canh hai lan.
        """
        bc = protocol["energy_required"]["budget_conventions"]
        assert bc["distance_convention"] == "ROUND_TRIP"
        assert bc["takeoff_landing_energy"] == "INCLUDED_IN_ESTIMATOR_OUTPUT"
        assert bc["return_leg_carries_payload"] is True
        assert bc["cruise_speed_assumption"]
        assert bc["cruise_altitude_assumption"]
        assert bc["e_hover_Wh"] == 0.0

    def test_cam_cong_hai_lan_nang_luong_ha_canh(self, protocol):
        """Dieu cam nay la ket qua truc tiep cua quyet dinh B9."""
        assert any("DEM HAI LAN" in p for p in protocol["prohibitions"])

    def test_cam_noi_du_lieu_thoi_tiet(self, protocol):
        """§4.4 — ghi lai de khong ai de xuat lai."""
        assert any("thoi tiet" in p for p in protocol["prohibitions"])

    def test_cam_goi_dau_ra_la_xac_suat(self, protocol):
        assert any("xac suat" in p for p in protocol["prohibitions"])

    def test_co_nhat_ky_thay_doi(self, protocol):
        assert protocol["change_log"]
        assert protocol["change_log"][-1]["version"] == protocol["meta"]["version"]

    def test_ba_quyet_dinh_duoc_ghi(self, protocol):
        ids = [d["id"] for d in protocol["change_log"][0]["decisions"]]
        assert ids == ["B3", "B4", "B5"]