"""
Test cho src/reference_labeller.py — buoc 3 cua san pham D4.

Phan de sai nhat cua ca san pham D4 nam o day, nen test tap trung vao bon cho:
anh xa dac trung (co mot phep thay the), buoc khop mo hinh (khong duoc lan sang
tinh chinh), quy tac ba lop nhan, va cong chan Muc 10.

Test chay tren du lieu BIA trong chinh file nay, khong tren 6000 kich ban that —
vi chua duoc gan nhan that cho tien khi Duy ky (OI-D4-1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.reference_labeller import (
    FEASIBLE, HAI_NHAN, INFEASIBLE, MARGINAL, UNKNOWN,
    _doc_bang_chuyen_bay, _kiem_cong_chan_muc_10, e_reference_ref2,
    fit_frozen_estimator, freeze_coefficients, gan_nhan, load_d2_protocol,
    load_protocol, run_labeller_checks, scenario_features,
)


@pytest.fixture(scope="module")
def protocol():
    return load_protocol()


@pytest.fixture(scope="module")
def d2():
    return load_d2_protocol()


@pytest.fixture(scope="module")
def khop():
    """Khop mot lan, dung chung cho ca file test — cham, dung lai."""
    return fit_frozen_estimator()


def _kich_ban(**ghi_de) -> pd.DataFrame:
    """Mot kich ban toi thieu, du cot de gan nhan."""
    goc = dict(scenario_id=1, stratum="main",
               payload_g=250.0, speed_commanded_ms=8.0, altitude_m=50.0,
               distance_2d_m=472.0, wind_forecast_ms=3.0,
               soc=0.8, soh=0.95, ambient_temp_c=15.0,
               hard_rule_probe=False, probe_limit=None, missing_field=None)
    goc.update(ghi_de)
    return pd.DataFrame([goc])


# ---------------------------------------------------------------------------

class TestGiaoThuc:
    """Kiem file dong bang truoc khi kiem code."""

    def test_cong_thuc_dung_ten_du_bao_khong_phai_so_do(self, protocol):
        """
        Quyet dinh C16. `E_measured_proxy` noi doi: so hang do la DU BAO cua mo
        hinh D2, khong phai so do. Muc 12.1 bat PHOI vong tron ra, khong che.
        """
        ct = protocol["reference_label"]["method"]["formula"]
        assert "E_d2_prediction" in ct
        assert "measured_proxy" not in ct

    def test_khai_du_anh_xa_cho_moi_dac_trung(self, protocol, d2):
        """Thieu mot dong anh xa thi code se doan ten cot — phai chan tu giao thuc."""
        amx = protocol["reference_label"]["feature_mapping"]["map"]
        assert set(amx) == set(d2["features"]["preflight"])

    def test_phep_thay_the_gio_duoc_khai_ro(self, protocol):
        """
        Mo hinh hoc tren gio DO DUOC, kich ban cho gio DU BAO. Nhet cai nay vao
        o cai kia ma khong khai la loi im lang. Quyet dinh C17.
        """
        st = protocol["reference_label"]["feature_mapping"]["substitution_declared"]
        assert st["slot"] == "wind_raw_mean_ms"
        assert st["fed_with"] == "wind_forecast_ms"
        assert st["must_state_in_paper"] is True

    def test_hai_bien_the_d2_khac_nhau_o_thoi_luong_khong_phai_gio(self, d2):
        """
        Chot lai cho de nho lan: D2-a va D2-b khac nhau DUNG MOT dac trung va
        do la THOI LUONG. CA HAI deu dung cot gio do duoc — bo du lieu CMU
        khong co cot gio du bao nao.
        """
        a = set(d2["features"]["as_written"])
        b = set(d2["features"]["preflight"])
        assert a - b == {"duration_s"}
        assert b - a == {"duration_planned_s"}
        assert "wind_raw_mean_ms" in a and "wind_raw_mean_ms" in b

    def test_khai_ro_mo_hinh_khong_hoc_tu_kich_ban(self, protocol):
        mf = protocol["reference_label"]["model_fit"]
        assert "192" in mf["learns_from"]
        assert mf["spec_frozen"]["degrees_of_freedom"] == 0

    def test_buoc_khop_co_nguon_cho_phep(self, protocol):
        """
        Muc 11 tuan 6 "finalize selected energy model" va Muc 7 B3. Khong co
        nguon thi buoc nay la nhom tu cho phep minh. Quyet dinh C18.
        """
        auth = protocol["reference_label"]["model_fit"]["authorised_by"]
        assert "finalize selected energy model" in auth
        assert "B3" in auth

    def test_dieu_cam_khong_con_chan_chinh_buoc_khop(self, protocol):
        """
        Ban truoc ghi "KHONG huan luyen lai bat ky mo hinh nao" — doc chu thi
        cam luon buoc khop, ma khong co buoc do thi khong du bao duoc gi.
        """
        cam = " ".join(protocol["prohibitions"])
        assert "huan luyen lai bat ky mo hinh nao" not in cam
        assert "doi thiet lap mo hinh sau khi da thay ket qua cuoi" in cam

    def test_cam_goi_sai_so_cuoi_la_0657(self, protocol):
        """
        MAE 0.657 la sai so cua QUY TRINH cross-validation, do tren 25 lan khop
        khac. Bo he so cuoi khong do duoc sai so cua chinh no.
        """
        assert any("0.657" in c for c in protocol["prohibitions"])

    def test_he_so_ref2_co_nguon_do_duoc(self, protocol):
        """
        Hai con so da bi bo khoi REF-2:
          safety_k = 1.25  (C12) — nhom tu dat, khong do tu gi
          eta_dev  = 0.034 (C22) — co nguon nhung SAI VIEC: no do sai lech cua
                     he so hieu suat, khong do sai lech cua ca cong thuc
        Thay bang he so hieu chinh k, do tu 192 chuyen that.
        """
        ref2 = protocol["reference_label"]["sensitivity_method"]
        assert "safety_k" not in ref2
        assert "eta_dev" not in ref2
        assert ref2["calibration"]["source"] == "MEASURED"
        assert ref2["frozen_numbers"]["percentile"] == 95

    def test_ref2_hieu_chinh_tren_thoi_luong_ke_hoach(self, protocol):
        """
        Phai hieu chinh tren `duration_planned_s`, khong `duration_s`: kich ban
        tong hop khong co thoi luong do duoc.
        """
        cal = protocol["reference_label"]["sensitivity_method"]["calibration"]
        assert "duration_planned_s" in cal["which_duration"]

    def test_moi_nhan_phai_dan_simulation_derived(self, protocol):
        assert protocol["reference_label"]["simulation_derived_label"]["required"]


class TestAnhXaDacTrung:
    """Sai o day thi mo hinh nhan sai dau vao ma khong bao gi."""

    def test_du_cot_va_dung_thu_tu(self, protocol, d2):
        cot = d2["features"]["preflight"]
        X = scenario_features(_kich_ban(), protocol, cot)
        assert list(X.columns) == list(cot)

    def test_thoi_luong_ke_hoach_dung_cong_thuc_giao_thuc_d2(self, protocol, d2):
        """duration_planned_s = distance_2d_m / speed_num — cong thuc cua D2."""
        kb = _kich_ban(distance_2d_m=480.0, speed_commanded_ms=8.0)
        X = scenario_features(kb, protocol, d2["features"]["preflight"])
        assert X["duration_planned_s"].iloc[0] == pytest.approx(60.0)

    def test_gio_du_bao_vao_o_gio_do_duoc(self, protocol, d2):
        kb = _kich_ban(wind_forecast_ms=4.2)
        X = scenario_features(kb, protocol, d2["features"]["preflight"])
        assert X["wind_raw_mean_ms"].iloc[0] == 4.2

    def test_thieu_anh_xa_thi_ban_loi_khong_doan(self, protocol, d2):
        xau = {**protocol, "reference_label": {
            **protocol["reference_label"],
            "feature_mapping": {"map": {"payload_num": "payload_g"}}}}
        with pytest.raises(RuntimeError, match="khong khai anh xa"):
            scenario_features(_kich_ban(), xau, d2["features"]["preflight"])

    def test_anh_xa_tro_vao_cot_khong_ton_tai_thi_ban_loi(self, protocol):
        xau = {**protocol, "reference_label": {
            **protocol["reference_label"],
            "feature_mapping": {"map": {"payload_num": "khong_co_cot_nay"}}}}
        with pytest.raises(RuntimeError, match="khong_co_cot_nay"):
            scenario_features(_kich_ban(), xau, ["payload_num"])


class TestChonBangDuLieu:
    """
    Chon dung bang cap chuyen bay.

    reports/flight_level_week3.csv chi la bang DOI CHIEU 8 cot cua tuan 3,
    khong co wind_raw_mean_ms. Bang day du la
    data/processed/flight_level.csv (27 cot). Chon theo thu tu ten file thay vi
    theo COT da lam 16 test do cung mot luc.
    """

    def test_bang_duoc_chon_co_du_cot_preflight(self, d2):
        can = list(d2["features"]["preflight"]) + [d2["target"]["column"]]
        df, p = _doc_bang_chuyen_bay(can)
        assert not [c for c in can if c not in df.columns]
        assert len(df) == 192

    def test_khong_chon_bang_thieu_cot(self, d2):
        """Bang doi chieu tuan 3 khong duoc chon cho viec khop mo hinh."""
        can = list(d2["features"]["preflight"]) + [d2["target"]["column"]]
        _, p = _doc_bang_chuyen_bay(can)
        assert p.name != "flight_level_week3.csv"

    def test_thieu_cot_o_moi_file_thi_bao_ro_thieu_gi(self):
        """
        Thong bao loi phai noi THIEU COT NAO o TUNG file, khong chi "khong tim
        thay". Loi dau tien chi noi "thieu cot ['wind_raw_mean_ms']" ma khong
        noi dang doc file nao — mat mot luot doan.
        """
        with pytest.raises(SystemExit, match="cot_khong_bao_gio_ton_tai"):
            _doc_bang_chuyen_bay(["cot_khong_bao_gio_ton_tai"])


class TestKhopMoHinh:
    """Khop MOT LAN, dung spec dong bang, bac tu do = 0."""

    def test_alpha_nam_trong_dai_da_khai(self, khop, d2):
        _, _, alpha, _ = khop
        assert alpha in d2["models"]["D2"]["alpha_grid"]

    def test_khop_tren_dung_192_chuyen(self, khop):
        _, _, _, n = khop
        assert n == 192

    def test_dung_sau_dac_trung_preflight(self, khop, d2):
        _, cot, _, _ = khop
        assert cot == list(d2["features"]["preflight"])

    def test_tat_dinh_khop_lai_ra_cung_he_so(self, khop):
        """Bac tu do = 0 nen khop lai phai ra y het."""
        pipe1, cot, alpha, n = khop
        pipe2, _, alpha2, _ = fit_frozen_estimator()
        assert alpha2 == alpha
        np.testing.assert_allclose(
            pipe1.named_steps["model"].coef_,
            pipe2.named_steps["model"].coef_, rtol=1e-10)

    def test_he_so_duoc_dong_bang_ra_file_kiem_duoc(self, khop):
        """
        Khong co file he so thi buoc khop nay khong ai kiem duoc — va mot buoc
        khong kiem duoc thi khong khac gi mot con so bia.
        """
        pipe, cot, alpha, n = khop
        hs = freeze_coefficients(pipe, cot, alpha, n)
        assert len(hs) == len(cot)
        assert set(hs.columns) >= {"feature", "coef_standardised",
                                   "coef_original_units", "alpha", "intercept"}
        assert (hs["n_flights_fitted"] == 192).all()

    def test_cach_chon_alpha_khop_giao_thuc_d2(self, khop, d2):
        """
        File he so phai ghi CACH CHON alpha, khong chi ghi alpha.

        Trong repo co HAI cho chon alpha bang hai cach khac nhau:
          src/interpretability.py  KFold(5, shuffle, 42)        -> alpha 1.0
          src/reference_labeller.py RepeatedKFold(5x5, 42)      -> alpha 0.1
        Ca hai deu khop tren 192 chuyen, nen hai bo he so khac nhau CHI vi
        alpha. Giao thuc d2 khai repeated_k_fold, nen file nay dung.
        Xem OI-D4-4.
        """
        pipe, cot, alpha, n = khop
        hs = freeze_coefficients(pipe, cot, alpha, n)
        cv = d2["partitioning"]["cv"]
        assert (hs["alpha_cv_scheme"] == cv["scheme"]).all()
        assert (hs["alpha_cv_splits"] == cv["n_splits"]).all()
        assert (hs["alpha_cv_repeats"] == cv["n_repeats"]).all()
        assert (hs["alpha_cv_seed"] == cv["random_state"]).all()

    def test_doi_cach_chia_trong_giao_thuc_thi_ban_loi(self, monkeypatch):
        """
        Doi `scheme` trong d2_protocol ma khong doi ham khop thi he so se doi
        am tham. Phai dung lai va noi ro.
        """
        import src.reference_labeller as rl
        goc = rl.load_d2_protocol()
        xau = {**goc, "partitioning": {
            **goc["partitioning"],
            "cv": {**goc["partitioning"]["cv"], "scheme": "k_fold"}}}
        monkeypatch.setattr(rl, "load_d2_protocol", lambda: xau)
        with pytest.raises(RuntimeError, match="repeated_k_fold"):
            rl.fit_frozen_estimator()

    def test_dai_alpha_lech_giua_hai_cho_thi_ban_loi(self, monkeypatch):
        """
        Dai alpha nam o CA d2_protocol.yaml VA src/models.py. Lech nhau thi mot
        trong hai da bi sua — phai dung, khong duoc chay tiep voi dai nao.
        """
        import src.reference_labeller as rl
        goc = rl.load_d2_protocol()
        xau = {**goc, "models": {**goc["models"],
                                 "D2": {**goc["models"]["D2"],
                                        "alpha_grid": [0.5]}}}
        monkeypatch.setattr(rl, "load_d2_protocol", lambda: xau)
        with pytest.raises(RuntimeError, match="Dai alpha"):
            rl.fit_frozen_estimator()

    def test_du_bao_ra_so_hop_ly(self, khop, protocol, d2):
        pipe, cot, _, _ = khop
        X = scenario_features(_kich_ban(), protocol, cot)
        du_bao = float(pipe.predict(X.to_numpy(float))[0])
        assert 5.0 < du_bao < 60.0


class TestBaLopNhan:
    """§6/E3 — "simulated feasible/marginal/infeasible cases"."""

    def test_pin_day_thi_kha_thi(self, khop, protocol):
        pipe, cot, _, _ = khop
        kq = gan_nhan(_kich_ban(soc=1.0, soh=1.0), protocol, pipe, cot)
        assert kq["label_ref1"].iloc[0] == FEASIBLE

    def test_pin_can_thi_khong_kha_thi(self, khop, protocol):
        pipe, cot, _, _ = khop
        kq = gan_nhan(_kich_ban(soc=0.05), protocol, pipe, cot)
        assert kq["label_ref1"].iloc[0] == INFEASIBLE

    def test_co_vung_marginal_o_giua(self, khop, protocol):
        """Ba lop phai that su co ba, khong phai nhi phan tra hinh."""
        pipe, cot, _, _ = khop
        nhan = [gan_nhan(_kich_ban(soc=s), protocol, pipe, cot)
                ["label_ref1"].iloc[0]
                for s in np.arange(0.05, 1.01, 0.01)]
        assert set(nhan) >= {INFEASIBLE, MARGINAL, FEASIBLE}

    def test_thieu_dau_vao_thi_khong_gan_nhan(self, khop, protocol):
        """
        §4.6 fail closed: khong du du kien thi khong ket luan, ke ca khi ket
        luan do la "khong kha thi".
        """
        pipe, cot, _, _ = khop
        for thieu in ("soc", "soh", "ambient_temp_c"):
            kq = gan_nhan(_kich_ban(**{thieu: np.nan}), protocol, pipe, cot)
            assert kq["label_ref1"].iloc[0] == UNKNOWN
            assert not bool(kq["inputs_valid"].iloc[0])

    def test_thieu_gio_thi_khong_hoi_mo_hinh(self, khop, protocol):
        """
        `wind_forecast_ms` la MOT TRONG 6 DAC TRUNG cua mo hinh. Thieu no thi
        Ridge khong du bao duoc — pipe.predict() nem "Input X contains NaN".

        Dung ra khong duoc hoi mo hinh: §4.6 bat fail closed. Dien trung binh
        roi du bao la bien mot dong "khong biet" thanh mot con so trong nhu
        biet — dung loi ma ca san pham D3 dung de chan.

        Tang `missing_input` cua bo kich ban co ~100 dong nhu vay, va chung da
        lam bo chay no that.
        """
        pipe, cot, _, _ = khop
        kq = gan_nhan(_kich_ban(wind_forecast_ms=np.nan), protocol, pipe, cot)
        assert kq["label_ref1"].iloc[0] == UNKNOWN
        assert not np.isfinite(kq["e_reference_ref1_Wh"].iloc[0])

    def test_tron_dong_du_va_dong_thieu_thi_van_chay(self, khop, protocol):
        """
        Dong thieu KHONG duoc lam chet ca lo. Day moi la truong hop that: bo
        kich ban co 5600 dong du va 400 dong thieu, nam lan nhau.
        """
        pipe, cot, _, _ = khop
        kb = pd.concat([
            _kich_ban(scenario_id=1),
            _kich_ban(scenario_id=2, wind_forecast_ms=np.nan),
            _kich_ban(scenario_id=3, soc=np.nan),
            _kich_ban(scenario_id=4),
        ], ignore_index=True)
        kq = gan_nhan(kb, protocol, pipe, cot)
        assert list(kq["label_ref1"] == UNKNOWN) == [False, True, True, False]
        assert np.isfinite(kq["e_reference_ref1_Wh"].iloc[[0, 3]]).all()

    def test_soc_tang_thi_nhan_khong_xau_di(self, khop, protocol):
        """
        Don dieu — cung tinh chat INV-3 cua san pham D3.

        Luoi SoC dung so nguyen roi chia, KHONG dung np.arange voi buoc thap
        phan: arange(0.1, 1.01, 0.05) tra ve 1.0000000000000002 o gia tri cuoi,
        tuc SoC > 1, va available_energy() dung ra tra OUT_OF_RANGE -> UNKNOWN.
        Ban dau test nay dua dau vao rac roi bat he thong phai don dieu.
        """
        pipe, cot, _, _ = khop
        thu_tu = [INFEASIBLE, MARGINAL, FEASIBLE]
        nhan = [gan_nhan(_kich_ban(soc=i / 100), protocol, pipe, cot)
                ["label_ref1"].iloc[0]
                for i in range(10, 101, 5)]
        assert UNKNOWN not in nhan, "luoi SoC co gia tri ngoai dai [0, 1]"
        chi_so = [thu_tu.index(n) for n in nhan]
        assert chi_so == sorted(chi_so)

    def test_soc_ngoai_dai_thi_khong_gan_nhan(self, khop, protocol):
        """
        Fail closed cho SoC ngoai dai [0, 1] — §4.6.

        Khoa lai hanh vi ma loi trong test tren phoi ra: SoC = 1.0000000000000002
        KHONG duoc lam tron thanh 1.0 roi chay tiep. Mot gia tri ngoai dai la
        dau hieu dau vao co van de, khong phai mot so can lam dep.
        """
        pipe, cot, _, _ = khop
        for xau in (1.0000000000000002, 1.5, -0.01):
            kq = gan_nhan(_kich_ban(soc=xau), protocol, pipe, cot)
            assert kq["label_ref1"].iloc[0] == UNKNOWN
            assert not bool(kq["inputs_valid"].iloc[0])

    def test_soc_dung_bang_1_thi_van_gan_duoc(self, khop, protocol):
        """Bien hop le phai NAM TRONG dai — 1.0 dung la hop le."""
        pipe, cot, _, _ = khop
        kq = gan_nhan(_kich_ban(soc=1.0), protocol, pipe, cot)
        assert kq["label_ref1"].iloc[0] != UNKNOWN

    def test_nhan_mang_co_simulation_derived(self, khop, protocol):
        pipe, cot, _, _ = khop
        kq = gan_nhan(_kich_ban(), protocol, pipe, cot)
        for ma in HAI_NHAN:
            h = ma.replace("-", "").lower()
            assert kq[f"label_{h}_kind"].iloc[0] == "simulation-derived"

    def test_luu_du_truong_e3_doi(self, khop, protocol):
        """
        §6/E3: "Save the reference-model version, parameter file, scenario
        seed, reserve policy, and per-scenario label."
        """
        pipe, cot, _, _ = khop
        kq = gan_nhan(_kich_ban(), protocol, pipe, cot)
        for c in ("reference_model_version", "reserve_policy",
                  "label_ref1", "label_ref2"):
            assert c in kq.columns


class TestHieuNang:
    """
    Khong doc lai giao thuc tung dong.

    `available_energy()` mac dinh `protocol=None` va khi do TU DOC
    d3_protocol.yaml tu dia. Goi 6000 lan thi parse file YAML hon nghin dong
    6000 lan, va bo chay dung nhu treo — da xay ra that. Test nay dem so lan
    nap giao thuc.
    """

    def test_nap_giao_thuc_so_lan_khong_doi_theo_so_dong(self, khop, protocol,
                                                         monkeypatch):
        import src.reference_labeller as rl

        dem = {"n": 0}
        goc = rl.load_d3_protocol

        def nap_co_dem():
            dem["n"] += 1
            return goc()

        monkeypatch.setattr(rl, "load_d3_protocol", nap_co_dem)
        pipe, cot, _, _ = khop
        kb = pd.concat([_kich_ban(scenario_id=i, soc=0.3 + i / 500)
                        for i in range(100)], ignore_index=True)
        rl.gan_nhan(kb, protocol, pipe, cot)

        assert dem["n"] <= 3, (
            f"nap giao thuc {dem['n']} lan cho 100 dong — dang nap theo tung "
            f"dong, se treo o 6000 kich ban")


class TestHaiNhan:
    """Hai nhan phai that su khac nhau, khong thi do nhay S-2 vo nghia."""

    def test_ref2_khong_dung_he_so_hoi_quy_nao(self, protocol):
        """
        REF-2 doc lap ho mo hinh: khong goi pipeline, khong nhan `pipe`.
        Do la ca ly do no ton tai.
        """
        import inspect
        sig = inspect.signature(e_reference_ref2)
        assert "pipe" not in sig.parameters

    def test_ref2_ra_so_duong(self, protocol):
        er = e_reference_ref2(_kich_ban(), protocol)
        assert np.all(er > 0)

    def test_ref2_tang_theo_tai_trong(self, protocol):
        """Nang hon thi ton nang luong hon — kiem tinh vat ly co ban."""
        nhe = e_reference_ref2(_kich_ban(payload_g=0.0), protocol)[0]
        nang = e_reference_ref2(_kich_ban(payload_g=500.0), protocol)[0]
        assert nang > nhe

    def test_ref2_tang_theo_cu_ly(self, protocol):
        gan = e_reference_ref2(_kich_ban(distance_2d_m=400.0), protocol)[0]
        xa = e_reference_ref2(_kich_ban(distance_2d_m=800.0), protocol)[0]
        assert xa > gan

    def test_hai_nhan_khong_trung_nhau_hoan_toan(self, khop, protocol):
        """
        Neu hai nhan luon trung nhau thi khong co gi doc lap de doi chieu, va
        do nhay S-2 bat buoc cua §6/E3 chi la hinh thuc.
        """
        pipe, cot, _, _ = khop
        kb = pd.concat([_kich_ban(scenario_id=i, soc=s, distance_2d_m=d)
                        for i, (s, d) in enumerate(
                            [(0.3, 350.0), (0.5, 500.0), (0.7, 700.0),
                             (0.9, 850.0), (0.2, 300.0)], start=1)],
                       ignore_index=True)
        kq = gan_nhan(kb, protocol, pipe, cot)
        assert not (kq["e_reference_ref1_Wh"]
                    .round(3)
                    .equals(kq["e_reference_ref2_Wh"].round(3)))

    def test_he_so_bi_sua_tay_thi_ban_loi(self, protocol):
        """
        Code tinh lai k tu 192 chuyen va doi chieu voi so dong bang. Sua tay mot
        con so thi phai bi bat, khong duoc di qua im lang.
        """
        sm = protocol["reference_label"]["sensitivity_method"]
        xau = {**protocol, "reference_label": {
            **protocol["reference_label"],
            "sensitivity_method": {**sm, "frozen_numbers": {
                **sm["frozen_numbers"], "calibration_k": 1.0}}}}
        with pytest.raises(RuntimeError, match="lech"):
            e_reference_ref2(_kich_ban(), xau)

    def test_chua_dien_he_so_thi_dung_lai(self, protocol):
        sm = protocol["reference_label"]["sensitivity_method"]
        xau = {**protocol, "reference_label": {
            **protocol["reference_label"],
            "sensitivity_method": {**sm, "frozen_numbers": {
                **sm["frozen_numbers"], "calibration_k": None}}}}
        with pytest.raises(SystemExit, match="OI-D4-5"):
            e_reference_ref2(_kich_ban(), xau)

    def test_ref2_bao_thu_hon_muc_do_duoc(self, protocol):
        """
        Dieu kien §6/E3 giao cho REF-2: "a distinct CONSERVATIVE reference
        assumption". Ban 1.0.7 THAT BAI o day — REF-2 doi 7.56 Wh khi nang
        luong do duoc that la 20.79 Wh. Test nay khoa lai tinh chat do.

        Kiem tren mot nhiem vu dung bang cau hinh CMU dien hinh.
        """
        er = e_reference_ref2(_kich_ban(payload_g=0.0, distance_2d_m=472.0,
                                        speed_commanded_ms=8.0), protocol)[0]
        assert er > 20.0, (
            f"REF-2 doi {er:.2f} Wh cho mot nhiem vu ma nang luong do duoc "
            f"thuc te khoang 21 Wh — khong bao thu")


class TestCongChanMuc10:
    """
    Muc 10: "Student 3 and Student 4 must jointly verify the definition of the
    reference scenario labels."
    """

    def test_chua_ky_thi_tu_choi_ghi_nhan(self, protocol):
        chua = {**protocol, "reference_label": {
            **protocol["reference_label"], "approved_by": None}}
        with pytest.raises(SystemExit, match="OI-D4-1"):
            _kiem_cong_chan_muc_10(chua)

    def test_da_ky_thi_cho_chay(self, protocol):
        da = {**protocol, "reference_label": {
            **protocol["reference_label"], "approved_by": "Duy"}}
        _kiem_cong_chan_muc_10(da)          # khong duoc nem gi

    def test_oi_d4_1_da_dong_va_co_nguoi_ky(self, protocol):
        """
        OI-D4-1 dong 21/10/2026. Test nay truoc do khoa `status == "MO"`, tuc
        khoa mot trang thai TAM THOI — no do ngay khi Duy ky. Gio khoa dieu
        thuc su phai dung mai: viec treo da dong VA co ten nguoi ky VA co ngay.
        """
        oi = next(x for x in protocol["open_items"] if x["id"] == "OI-D4-1")
        assert "Duy" in oi["owner"]
        assert oi["status"].startswith("DONG")
        rl = protocol["reference_label"]
        assert rl["approved_by"]
        assert str(rl["approved_on"]).startswith("2026-")

    def test_ngay_ky_la_ngay_hop_le(self, protocol):
        """
        Ban ky dau tien ghi `20206-10-21` — loi danh may nam. Mot nhat ky co
        ngay sai thi khong truy vet duoc, nen khoa dang ngay lai.
        """
        import datetime as dt
        ngay = str(protocol["reference_label"]["approved_on"])
        dt.date.fromisoformat(ngay)          # nem loi neu khong phai YYYY-MM-DD
        assert 2026 <= int(ngay[:4]) <= 2027


class TestBangKiem:
    """GEN-4b va GEN-6 — nhung phep kiem chi lam duoc o buoc nay."""

    @staticmethod
    @pytest.fixture(scope="class")
    def kq(protocol, khop):
        pipe, cot, _, _ = khop
        kb = pd.concat([_kich_ban(scenario_id=i, soc=s)
                        for i, s in enumerate(np.arange(0.1, 1.0, 0.01), 1)],
                       ignore_index=True)
        return run_labeller_checks(protocol, gan_nhan(kb, protocol, pipe, cot))

    def test_khop_danh_sach_giao_thuc(self, kq, protocol):
        khai = [t["id"] for t in protocol["generator_invariants"]["tests"]
                if t["verified_at"] == "labeller"]
        assert list(kq["check"]) == khai

    def test_gen6_dat(self, kq):
        """Khoan du phong khong lay tu fold kiem cuoi — §6/E3 cam thang."""
        g6 = kq[kq["check"] == "GEN-6"].iloc[0]
        assert g6["vi_pham"] == 0

    def test_gen6_bat_duoc_nguon_sai(self, protocol):
        xau = {**protocol, "reference_label": {
            **protocol["reference_label"],
            "frozen_numbers": {
                **protocol["reference_label"]["frozen_numbers"],
                "computed_from": "reports/d2_final_test_fold.csv"}}}
        kq = run_labeller_checks(xau, pd.DataFrame({"boundary_ref1": [True] * 2000}))
        assert kq[kq["check"] == "GEN-6"].iloc[0]["vi_pham"] > 0

    def test_giao_thuc_khai_thieu_ham_thi_ban_loi(self, protocol):
        xau = {**protocol, "generator_invariants": {
            "tests": protocol["generator_invariants"]["tests"]
                     + [{"id": "GEN-99", "statement": "bia", "method": "bia",
                         "verified_at": "labeller"}]}}
        with pytest.raises(RuntimeError, match="GEN-99"):
            run_labeller_checks(xau, pd.DataFrame({"boundary_ref1": [True]}))
