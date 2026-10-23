"""
Test cho src/scenario_generator.py — buoc dau cua san pham D4.

Tap trung vao cho de sai nhat cua mot bo sinh kich ban: tat dinh, dai lay mau
theo tung tang, co ngoai suy, va do phu. Mot bo sinh sai thi MOI con so cua san
pham D4 vo nghia, ma loi do khong lo ra ngoai — bang ket qua van in binh thuong.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scenario_generator import (
    COT_AN_TOAN, COT_RA, GENERATOR_VERSION, S_MAIN, S_MISSING, S_PROBE,
    S_SHORT_HIGH, gan_co_ngoai_suy, generate, hash_bo_kich_ban, load_protocol,
    run_generator_checks,
)


@pytest.fixture(scope="module")
def protocol():
    return load_protocol()


@pytest.fixture(scope="module")
def df(protocol):
    return generate(protocol)


# ---------------------------------------------------------------------------

class TestGiaoThuc:
    """Kiem file dong bang truoc khi kiem code — code chi dung neu giao thuc dung."""

    def test_doc_duoc_va_dung_san_pham(self, protocol):
        assert protocol["meta"]["deliverable"].startswith("D4")

    def test_du_so_kich_ban_thay_doi(self, protocol):
        cfg = protocol["scenario_generator"]
        assert cfg["n_scenarios"] >= cfg["n_scenarios_min_required"] == 5000

    def test_tong_cac_tang_dung_bang_tong_khai_bao(self, protocol):
        """
        Loi cong sai o day lam bo kich ban thieu hoac thua ma khong ai thay:
        cac bang ket qua van chay, chi la chay tren so luong khac voi khai bao.
        """
        cfg = protocol["scenario_generator"]
        tong = sum(t["n"] for t in cfg["strata"].values())
        assert tong == cfg["n_scenarios"]

    def test_moi_tang_co_seed_offset_rieng(self, protocol):
        """
        Dung chung seed thi hai tang lay cung chuoi quasi-random, tuc tuong quan
        voi nhau — mot loi im lang lam do phu te di ma khong bao gi.
        """
        off = [t["seed_offset"] for t in protocol["scenario_generator"]["strata"].values()]
        assert len(off) == len(set(off))

    def test_moi_yeu_cau_do_phu_khai_ro_ai_kiem(self, protocol):
        """
        COV-3 khong kiem duoc o bo sinh (can E_required). Truong `verified_by`
        bat phai noi ro, de khong ai tuong bo sinh da kiem roi.
        """
        for c in protocol["scenario_generator"]["mandatory_coverage"]:
            assert c["verified_by"] in ("GEN-4a", "GEN-4b")
            assert isinstance(c["min_count"], int)

    def test_cov3_khong_do_bo_sinh_kiem(self, protocol):
        cov3 = next(c for c in protocol["scenario_generator"]["mandatory_coverage"]
                    if c["id"] == "COV-3")
        assert cov3["verified_by"] == "GEN-4b"
        assert cov3["satisfied_by_stratum"] is None

    def test_moi_phep_kiem_khai_ro_kiem_o_buoc_nao(self, protocol):
        for t in protocol["generator_invariants"]["tests"]:
            assert t["verified_at"] in ("generator", "labeller")

    def test_quyet_dinh_c9_c10_duoc_ghi(self, protocol):
        """C9 — chia bon tang. C10 — tach GEN-4."""
        ids = [d["id"] for c in protocol["change_log"]
               for d in c.get("decisions", [])]
        assert "C9" in ids and "C10" in ids

    def test_quyet_dinh_ra_soat_nguon_duoc_ghi(self, protocol):
        """C12 bo safety_k · C13 luoi probe · C14 do rong vung bien · C15 trich dan."""
        ids = [d["id"] for c in protocol["change_log"]
               for d in c.get("decisions", [])]
        for ma in ("C12", "C13", "C14", "C15"):
            assert ma in ids

    # Da BO `test_khong_con_safety_k` o day.
    #
    # Test do kiem hop dong cua nhan tham chieu REF-2 — mot thu khong thuoc pham
    # vi cua bo sinh kich ban. Va no khai cung mot dieu voi mot test trong
    # tests/test_reference_labeller.py, nen khi REF-2 doi phuong phap o quyet
    # dinh C22 thi phai sua HAI cho, va da sot cho nay: no do voi
    # `KeyError: 'eta_dev_source'`.
    #
    # Dung loai loi "khai cung mot thu o nhieu cho" da lap nhieu lan trong de
    # tai nay. Cach sua khong phai va ca hai cho ma BO cho trung: hop dong
    # REF-2 chi con mot noi giu, la
    # tests/test_reference_labeller.py::TestGiaoThuc::test_he_so_ref2_co_nguon_do_duoc

    def test_do_rong_vung_bien_khai_ro_la_lua_chon_nhom(self, protocol):
        """
        w doi duoc ket qua, nen phai khai TEAM_CHOICE va phai co do nhay. Thieu
        mot trong hai thi no doc ra nhu mot con so cua thay.
        """
        bd = protocol["boundary_definition"]
        assert bd["source"] == "TEAM_CHOICE"
        assert bd["affects_results"] is True
        s = [x["id"] for x in protocol["mandatory_sensitivity_runs"]]
        assert "S-4" in s, "co w la lua chon cua nhom ma khong co do nhay"

    def test_moi_lua_chon_cua_nhom_khai_co_doi_ket_qua_hay_khong(self, protocol):
        """
        Quy uoc `provenance_rule`: con so TEAM_CHOICE phai kem
        `affects_results`. Neu doi duoc ket qua thi phai co do nhay tuong ung.

        Test nay quet nhung cho da khai, de khong ai them mot TEAM_CHOICE tran.
        """
        can_kiem = [
            protocol["boundary_definition"],
            protocol["scenario_generator"]["strata"]["hard_rule_probe"],
        ]
        for muc in can_kiem:
            khoa_src = [k for k in muc if k.endswith("source")]
            assert khoa_src, f"thieu truong nguon: {list(muc)[:3]}"
        assert "provenance_rule" in protocol["meta"]

    def test_duong_co_so_b4_bi_loai_co_ly_do(self, protocol):
        """
        Muc 7 cho B4 dieu kien "only quantitative if M100 parameters are
        documented". Loai thi phai ghi ly do, khong duoc im lang bo.
        """
        b4 = protocol["baselines"]["B4"]
        assert b4["excluded"] is True
        assert len(b4["exclusion_reason"]) > 100

    def test_du_duong_co_so_muc_12_1_doi(self, protocol):
        """Muc 12.1: "B0/B1/B2/B3/B5 implemented where applicable"."""
        for ma in ("B0", "B1", "B2", "B3", "B5"):
            assert protocol["baselines"][ma]["required"] is True


class TestTatDinh:
    """GEN-1 — cung seed thi cung bo, tung bit."""

    def test_sinh_hai_lan_cho_cung_hash(self, protocol):
        assert hash_bo_kich_ban(generate(protocol)) == \
               hash_bo_kich_ban(generate(protocol))

    def test_doi_seed_thi_doi_bo(self, protocol):
        khac = {**protocol, "scenario_generator":
                {**protocol["scenario_generator"], "seed": 43}}
        assert hash_bo_kich_ban(generate(protocol)) != \
               hash_bo_kich_ban(generate(khac))

    def test_seed_duoc_luu_vao_tung_dong(self, df, protocol):
        """§6/E3 bat luu scenario seed theo tung kich ban."""
        assert (df["scenario_seed"] == protocol["scenario_generator"]["seed"]).all()

    def test_phien_ban_duoc_luu_vao_tung_dong(self, df, protocol):
        assert (df["protocol_version"] == protocol["meta"]["version"]).all()
        assert (df["generator_version"] == GENERATOR_VERSION).all()


class TestHinhDang:
    """Co ban — nhung sai o day thi moi thu ve sau sai theo."""

    def test_du_so_dong(self, df, protocol):
        assert len(df) == protocol["scenario_generator"]["n_scenarios"]

    def test_dung_thu_tu_cot(self, df):
        assert list(df.columns) == COT_RA

    def test_id_duy_nhat_va_lien_tuc(self, df):
        assert df["scenario_id"].is_unique
        assert list(df["scenario_id"]) == list(range(1, len(df) + 1))

    def test_dung_bon_tang(self, df):
        assert set(df["stratum"]) == {S_MAIN, S_PROBE, S_SHORT_HIGH, S_MISSING}

    def test_so_dong_tung_tang_khop_giao_thuc(self, df, protocol):
        for ten, spec in protocol["scenario_generator"]["strata"].items():
            assert (df["stratum"] == ten).sum() == spec["n"]


class TestDaiLayMau:
    """GEN-2 — moi tang phai nam trong dai CUA NO, khong phai dai chung."""

    def test_tang_main_nam_trong_gioi_han_van_hanh(self, df):
        m = df[df["stratum"] == S_MAIN]
        assert m["payload_g"].between(0, 500).all()
        assert m["speed_commanded_ms"].between(4, 12).all()
        assert m["wind_forecast_ms"].between(0, 10).all()

    def test_tang_probe_that_su_vuot_gioi_han(self, df, protocol):
        """
        Tang probe co MUC DICH la vuot gioi han. Neu no khong vuot thi thuoc do
        M-7 (vi pham luat cung bi duyet sai) se do tren 0 truong hop — tuc bao
        "dat muc tieu 0" ma khong chung minh gi.

        Nguong doc TU GIAO THUC. Ban truoc viet cung 500 g va 12 m/s — ma do la
        dai LAY MAU, khong phai gioi han DJI (1245 g va 17 m/s). Nen test cu
        van xanh trong khi tang probe probe sai cho. Xem quyet dinh C13.
        """
        p = df[df["stratum"] == S_PROBE]
        gh = protocol["scenario_generator"]["strata"][S_PROBE]["limits_probed"]
        vuot = pd.Series(False, index=p.index)
        for g in gh:
            vuot |= p[g["variable"]] > g["dji_limit"]
        assert vuot.all(), "co kich ban trong tang probe khong vuot gioi han nao"

    def test_probe_vuot_dung_mot_gioi_han(self, df, protocol):
        """
        Vuot MOT gioi han moi biet luat NAO chan. Vuot ca ba thi khong phan
        biet duoc HR-1 voi HR-2 — va thuoc do M-7 mat y nghia.
        """
        p = df[df["stratum"] == S_PROBE]
        gh = protocol["scenario_generator"]["strata"][S_PROBE]["limits_probed"]
        dem = sum((p[g["variable"]] > g["dji_limit"]).astype(int) for g in gh)
        assert (dem == 1).all()

    def test_probe_dung_luoi_boi_so_khong_lay_mau(self, df, protocol):
        """
        Gia tri vuot phai la gioi han NHAN boi so da khai, khong phai mot so
        ngau nhien trong mot dai.

        Vi sao quan trong: boi so la lua chon cua nhom. No duoc phep la lua
        chon vi luat cung la nguong NHI PHAN nen boi so khong doi duoc ket qua.
        Nhung neu lay mau mot DAI thi chan tren cua dai lai la mot con so cua
        nhom — va chan tren do khong co nguon. Luoi thi truy nguon duoc tung
        gia tri.
        """
        spec = protocol["scenario_generator"]["strata"][S_PROBE]
        p = df[df["stratum"] == S_PROBE]
        for g in spec["limits_probed"]:
            hop_le = {round(g["dji_limit"] * b, 6)
                      for b in spec["probe_multipliers"]}
            cot = p[p["probe_limit"] == g["variable"]][g["variable"]]
            assert set(cot.round(6)) <= hop_le, (
                f"{g['variable']}: co gia tri ngoai luoi {sorted(hop_le)}")

    def test_moi_gioi_han_deu_duoc_probe(self, df, protocol):
        """Khai ba gioi han ma chi probe hai cai thi mot luat khong duoc thu."""
        spec = protocol["scenario_generator"]["strata"][S_PROBE]
        p = df[df["stratum"] == S_PROBE]
        assert set(p["probe_limit"]) == {g["variable"]
                                         for g in spec["limits_probed"]}

    def test_gioi_han_probe_khop_bang_tham_so(self, protocol):
        """
        Gioi han phai la so DJI cong bo, ghi o reports/parameter_table.md muc 5.
        Test nay khoa chung lai de khong ai sua thanh so khac ma khong doi nguon.
        """
        gh = {g["variable"]: g["dji_limit"] for g in
              protocol["scenario_generator"]["strata"][S_PROBE]["limits_probed"]}
        assert gh == {"wind_forecast_ms": 10.0,
                      "payload_g": 1245.0,
                      "speed_commanded_ms": 17.0}

    def test_tang_short_high_dung_la_ngan_va_cao(self, df):
        s = df[df["stratum"] == S_SHORT_HIGH]
        assert (s["distance_2d_m"] < 420).all()
        assert s["altitude_m"].isin([75, 100]).all()

    def test_do_cao_chi_lay_gia_tri_roi_rac(self, df, protocol):
        hop_le = set(protocol["scenario_generator"]["variables"]["altitude_m"]["values"])
        assert set(df["altitude_m"]) <= hop_le

    def test_soc_soh_trong_dai_vat_ly(self, df):
        assert df["soc"].dropna().between(0, 1).all()
        assert df["soh"].dropna().between(0, 1).all()

    def test_khong_gia_tri_am_o_cho_khong_duoc_am(self, df):
        for cot in ("payload_g", "speed_commanded_ms", "distance_2d_m",
                    "wind_forecast_ms", "altitude_m"):
            assert (df[cot].dropna() >= 0).all()


class TestCoNgoaiSuy:
    """GEN-3 — §6/E3: "clearly label any extrapolated ranges"."""

    def test_tinh_lai_cho_cung_ket_qua(self, df, protocol):
        lai = gan_co_ngoai_suy(df, protocol)
        for c in ("extrapolated_distance", "extrapolated_wind",
                  "extrapolated_soh", "extrapolated_temp"):
            assert (lai[c] == df[c]).all()

    def test_soh_va_nhiet_do_luon_la_ngoai_suy(self, df):
        """
        Bo du lieu CMU khong co SoH va khong ghi nhiet do moi truong. Nen MOI
        kich ban deu la ngoai suy o hai chieu nay — khong co ngoai le.
        """
        assert df["extrapolated_soh"].all()
        assert df["extrapolated_temp"].all()

    def test_co_cu_ly_khop_envelope(self, df, protocol):
        lo, hi = protocol["scenario_generator"]["variables"][
            "distance_2d_m"]["envelope_supported"]
        trong = df[~df["extrapolated_distance"]]
        ngoai = df[df["extrapolated_distance"]]
        assert trong["distance_2d_m"].between(lo, hi).all()
        assert not ngoai["distance_2d_m"].between(lo, hi).any()

    def test_co_ca_hai_phia_trong_va_ngoai_envelope(self, df):
        """Chi co mot phia thi khong so sanh duoc hai vung — Muc 7 bat bao rieng."""
        assert df["extrapolated_distance"].sum() > 0
        assert (~df["extrapolated_distance"]).sum() > 0


class TestThieuDauVao:
    """Tang missing_input — do ty le fail-closed tren kich ban tong hop."""

    def test_chi_tang_missing_moi_co_o_trong(self, df):
        khac = df[df["stratum"] != S_MISSING]
        assert khac[COT_AN_TOAN].notna().all().all()

    def test_moi_dong_thieu_dung_mot_cot(self, df):
        m = df[df["stratum"] == S_MISSING]
        assert (m[COT_AN_TOAN].isna().sum(axis=1) == 1).all()

    def test_cot_bi_thieu_duoc_ghi_lai(self, df):
        m = df[df["stratum"] == S_MISSING]
        for row in m.itertuples():
            assert pd.isna(getattr(row, row.missing_field))

    def test_ca_bon_cot_an_toan_deu_duoc_thu(self, df):
        """
        Bo trong theo chi so chu khong rut tham, nen ca bon cot phai xuat hien.
        Rut tham thi co the bo sot mot cot ma khong ai biet.
        """
        m = df[df["stratum"] == S_MISSING]
        assert set(m["missing_field"]) == set(COT_AN_TOAN)

    def test_so_luong_moi_cot_gan_deu(self, df):
        m = df[df["stratum"] == S_MISSING]
        dem = m["missing_field"].value_counts()
        assert dem.max() - dem.min() <= 1


class TestDoPhu:
    """GEN-4a — COV-1, COV-2, COV-4."""

    def test_cov1_du_kich_ban_vuot_luat_cung(self, df, protocol):
        yc = next(c for c in protocol["scenario_generator"]["mandatory_coverage"]
                  if c["id"] == "COV-1")
        assert int(df["hard_rule_probe"].sum()) >= yc["min_count"]

    def test_cov2_du_kich_ban_ngan_ma_bay_cao(self, df, protocol):
        """
        Vung duy nhat PH-1 rang buoc hon luat du tru. Bo du lieu CMU co 0/192
        truong hop nhu vay, nen neu D4 cung ra 0 thi khong phai PH-1 vo dung ma
        la bo sinh chua quet du rong.
        """
        yc = next(c for c in protocol["scenario_generator"]["mandatory_coverage"]
                  if c["id"] == "COV-2")
        n = int(((df["distance_2d_m"] < 420) & (df["altitude_m"] >= 75)).sum())
        assert n >= yc["min_count"]

    def test_cov4_du_kich_ban_thieu_dau_vao(self, df, protocol):
        yc = next(c for c in protocol["scenario_generator"]["mandatory_coverage"]
                  if c["id"] == "COV-4")
        assert int(df["missing_field"].notna().sum()) >= yc["min_count"]


class TestKhongLanSangViecKhac:
    """
    Bo sinh CHI sinh kich ban. Lan sang viec cua mo hinh la ro ri nguoc: bo sinh
    biet dau ra mo hinh thi co the nan dai kich ban theo cho mo hinh lam tot, ma
    khong ai phat hien duoc tu ket qua.
    """

    def test_khong_cot_nang_luong_nao(self, df):
        """GEN-5. Co E_required o day thi se co nguoi cong them khoan ha canh."""
        assert not [c for c in df.columns
                    if "_Wh" in c or "energy" in c.lower()]

    def test_khong_cot_phan_quyet_hay_nhan(self, df):
        xau = [c for c in df.columns
               if any(k in c.lower() for k in
                      ("verdict", "label", "fly", "feasib", "margin"))]
        assert not xau, f"bo sinh lan sang viec gan nhan: {xau}"

    def test_khong_import_mo_hinh(self):
        import src.scenario_generator as sg
        ma = open(sg.__file__, encoding="utf-8").read()
        for cam in ("from src.models", "import src.models",
                    "from src.decision_rules", "from src.evaluation_energy"):
            assert cam not in ma, f"bo sinh import {cam}"


class TestBangKiem:
    """run_generator_checks() — bang bang chung ghi ra reports/."""

    @staticmethod
    @pytest.fixture(scope="class")
    def kq(protocol, df):
        return run_generator_checks(protocol, df)

    def test_khop_danh_sach_giao_thuc(self, kq, protocol):
        """
        Bang bang chung phai liet ke DUNG nhung phep kiem ma giao thuc khai o
        buoc generator — khong thieu, khong thua, dung thu tu.

        Khong viet cung danh sach o day. O san pham D3 danh sach bat bien tung
        duoc viet cung o nam cho va da lech BA LAN, lan nao cung im lang.
        """
        khai = [t["id"] for t in protocol["generator_invariants"]["tests"]
                if t["verified_at"] == "generator"]
        assert list(kq["check"]) == khai

    def test_khong_phep_kiem_nao_khong_dat(self, kq):
        xau = kq[kq["vi_pham"] > 0]
        assert xau.empty, f"khong dat: {xau.to_dict('records')}"

    def test_moi_phep_kiem_chay_tren_truong_hop_that(self, kq):
        """Mot phep kiem chay tren 0 truong hop thi khong chung minh gi."""
        assert (kq["so_truong_hop"] > 0).all()

    def test_giao_thuc_khai_thieu_ham_thi_ban_loi(self, protocol, df):
        """
        Khai mot phep kiem ma khong co ham thi phai NEM LOI, khong duoc im lang
        bo qua — day dung la cach loi lech danh sach o D3 di qua ba lan.
        """
        xau = {**protocol, "generator_invariants": {
            "tests": protocol["generator_invariants"]["tests"]
                     + [{"id": "GEN-99", "statement": "bia",
                         "method": "bia", "verified_at": "generator"}]}}
        with pytest.raises(RuntimeError, match="GEN-99"):
            run_generator_checks(xau, df)


class TestChanLoiCauHinh:
    """Loi chinh ta trong giao thuc khong duoc bien thanh bo kich ban sai."""

    def test_ghi_de_bien_khong_ton_tai_thi_ban_loi(self, protocol):
        xau = {**protocol, "scenario_generator": {
            **protocol["scenario_generator"],
            "strata": {"main": {"n": 10, "seed_offset": 0,
                                "range_overrides": {"payload_gram": [0, 100]}}}}}
        with pytest.raises(ValueError, match="payload_gram"):
            generate(xau)
