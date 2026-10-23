"""
Test cho src/evaluation_scenario.py — buoc 5 cua san pham D4.

Day la module ra KET QUA, nen cho de sai nhat khong phai cong thuc ma la:
  - cham nham chieu (false-safe va tu choi thua bi doi cho)
  - cham tren tap sai (quen loai tang probe, hoac cham ca kich ban `unknown`)
  - mot thuoc do trong co ve binh thuong nhung do tren 0 truong hop

Ba thu do deu khong lo ra o bang ket qua. Nen test o day dung du lieu BIA, noi
dap an biet truoc, de kiem dung tung o mot.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.baselines_decision import B0, B2, B3, B5, B5_NOHR, THU_TU
from src.decision_rules import CONDITIONAL, FLY, INSUFFICIENT_DATA, NO_FLY
from src.evaluation_scenario import (
    TANG_LOAI, _mot_phuong_phap, cham_diem, confusion_ba_lop,
    confusion_nhi_phan, nhan_sang_nhi_phan, ph1_rang_buoc_hon,
    phan_quyet_sang_nhi_phan, quan_he_cau_truc, tu_choi_theo_nguyen_nhan,
)
from src.reference_labeller import (
    FEASIBLE, INFEASIBLE, MARGINAL, UNKNOWN, load_protocol,
)


@pytest.fixture(scope="module")
def protocol():
    return load_protocol()


def _bang(nhan, phan_quyet, bien=None) -> pd.DataFrame:
    """Mot bang bia, dap an va phan quyet deu biet truoc."""
    n = len(nhan)
    d = pd.DataFrame({
        "label_ref1": nhan,
        "label_ref2": nhan,
        "boundary_ref1": bien if bien is not None else [False] * n,
        "margin_ratio_ref1": np.linspace(-0.1, 0.5, n),
        "distance_2d_m": [472.0] * n,
        "altitude_m": [50.0] * n,
        "stratum": ["main"] * n,
    })
    for ma in THU_TU:
        d[f"verdict_{ma}"] = phan_quyet
    d["ly_do_B5"] = ["duyet" if p == FLY else "bien_du_tru_duoi_nguong"
                     for p in phan_quyet]
    return d


# ---------------------------------------------------------------------------

class TestAnhXa:
    """Hai phep anh xa phai khai ro, va phai dung chieu."""

    def test_ba_lop_sang_nhi_phan_mac_dinh_bao_thu(self):
        """marginal -> KHONG kha thi (quyet dinh C4)."""
        s = pd.Series([FEASIBLE, MARGINAL, INFEASIBLE, UNKNOWN])
        kq = nhan_sang_nhi_phan(s)
        assert list(kq[:3]) == [True, False, False]
        assert kq.iloc[3] is None or pd.isna(kq.iloc[3])

    def test_do_nhay_s3_doi_chieu_marginal(self):
        s = pd.Series([MARGINAL])
        assert nhan_sang_nhi_phan(s, marginal_la_kha_thi=True).iloc[0] is True

    def test_conditional_mac_dinh_khong_tinh_la_duyet(self):
        """
        §2.3: CONDITIONAL chua thuc thi duoc khi chua co bien phap. Quyet dinh
        C24. Tinh no la duyet se lam false-safe cua B5 cao len mot cach sai.
        """
        s = pd.Series([FLY, CONDITIONAL, NO_FLY, INSUFFICIENT_DATA])
        assert list(phan_quyet_sang_nhi_phan(s)) == [True, False, False, False]

    def test_co_the_doi_conditional_thanh_duyet(self):
        s = pd.Series([CONDITIONAL])
        assert phan_quyet_sang_nhi_phan(s, conditional_la_duyet=True).iloc[0]

    def test_insufficient_data_khong_bao_gio_la_duyet(self):
        """§4.6 fail closed — khong co duong nao de no thanh duyet bay."""
        s = pd.Series([INSUFFICIENT_DATA])
        for co in (True, False):
            assert not phan_quyet_sang_nhi_phan(s, conditional_la_duyet=co).iloc[0]


class TestBonO:
    """
    Bon o cua bang cham. Doi cho false-safe va tu choi thua la loi nguy hiem
    nhat o ca module nay — bang ket qua van dep, chi la dep nguoc.
    """

    def test_false_safe_dung_o(self):
        """KHONG kha thi ma duyet bay -> false-safe."""
        dap_an = pd.Series([False])
        duyet = pd.Series([True])
        kq = _mot_phuong_phap(dap_an, duyet)
        assert kq["FP_false_safe"] == 1
        assert kq["M2_false_safe_rate"] == 1.0
        assert kq["FN_tu_choi_thua"] == 0

    def test_tu_choi_thua_dung_o(self):
        """Kha thi ma tu choi -> tu choi thua."""
        kq = _mot_phuong_phap(pd.Series([True]), pd.Series([False]))
        assert kq["FN_tu_choi_thua"] == 1
        assert kq["M4_unnecessary_rejection_rate"] == 1.0
        assert kq["FP_false_safe"] == 0

    def test_hai_thuoc_do_doc_lap(self):
        """
        M-2 va M-4 do hai mau so KHAC NHAU (so kich ban khong kha thi, va so
        kich ban kha thi). Gop nham mau so la loi im lang.
        """
        dap_an = pd.Series([True, True, True, False])
        duyet = pd.Series([False, True, True, True])
        kq = _mot_phuong_phap(dap_an, duyet)
        assert kq["M4_unnecessary_rejection_rate"] == pytest.approx(1 / 3)
        assert kq["M2_false_safe_rate"] == pytest.approx(1 / 1)

    def test_recall_va_false_safe_cong_lai_bang_1(self):
        """Hai cai chia cung mau so va phu het — kiem tinh nhat quan."""
        dap_an = pd.Series([False] * 10)
        duyet = pd.Series([True] * 3 + [False] * 7)
        kq = _mot_phuong_phap(dap_an, duyet)
        assert kq["M1_infeasible_recall"] + kq["M2_false_safe_rate"] == pytest.approx(1.0)

    def test_tu_choi_tat_ca_cho_false_safe_hoan_hao(self):
        """
        Mot phuong phap tu choi MOI THU co M-2 = 0 — hoan hao ve an toan va vo
        dung ve van hanh. Day la ly do bao cao PHAI doc M-2 cung M-4.
        """
        dap_an = pd.Series([True] * 5 + [False] * 5)
        kq = _mot_phuong_phap(dap_an, pd.Series([False] * 10))
        assert kq["M2_false_safe_rate"] == 0.0
        assert kq["M4_unnecessary_rejection_rate"] == 1.0

    def test_khong_cham_kich_ban_unknown(self):
        """Khong co dap an thi khong cham duoc — va phai DEM so bi bo."""
        dap_an = pd.Series([True, None, False])
        kq = _mot_phuong_phap(dap_an, pd.Series([True, True, True]))
        assert kq["n_cham"] == 2
        assert kq["n_bo_qua_unknown"] == 1


class TestChamDiem:
    def test_du_bay_phuong_phap(self):
        b = cham_diem(_bang([FEASIBLE] * 4, [FLY] * 4))
        assert list(b["phuong_phap"]) == THU_TU

    def test_moi_thuoc_do_chay_tren_truong_hop_that(self):
        """Mot thuoc do do tren 0 truong hop thi khong chung minh gi."""
        b = cham_diem(_bang([FEASIBLE, INFEASIBLE] * 5, [FLY] * 10))
        assert (b["n_cham"] > 0).all()
        assert (b["n_kha_thi"] > 0).all()
        assert (b["n_khong_kha_thi"] > 0).all()

    def test_tach_vung_bien(self):
        b = cham_diem(_bang([INFEASIBLE] * 4, [FLY] * 4,
                            bien=[True, True, False, False]))
        r = b.iloc[0]
        assert r["M3_false_safe_count_bien"] == 2
        assert r["M3_false_safe_count_ngoai_bien"] == 2


class TestConfusion:
    def test_nhi_phan_du_bon_o_cho_moi_phuong_phap(self):
        c = confusion_nhi_phan(_bang([FEASIBLE, INFEASIBLE], [FLY, NO_FLY]))
        assert len(c) == len(THU_TU) * 4
        assert c.groupby("phuong_phap")["so_kich_ban"].sum().unique().tolist() == [2]

    def test_ba_lop_chi_cho_b5(self):
        """
        B0..B3 khong co bac giua (quyet dinh C24) nen bang ba lop cua chung se
        co cot rong — vo nghia chu khong phai thong tin.
        """
        c = confusion_ba_lop(_bang([FEASIBLE] * 3, [FLY] * 3))
        assert set(c["phuong_phap"]) == {B5, B5_NOHR}


class TestTapCham:
    """Cham tren tap SAI la loi khong lo ra o bang ket qua."""

    def test_hai_tang_bi_loai_khoi_bang_chinh(self):
        assert set(TANG_LOAI) == {"hard_rule_probe", "missing_input"}

    def test_ly_do_loai_duoc_khai_o_giao_thuc(self, protocol):
        for tang in TANG_LOAI:
            cfg = protocol["scenario_generator"]["strata"][tang]
            assert cfg["in_main_comparison"] is False
            assert cfg["excluded_from_main_tables_because"]

    def test_m9_dem_dung_vung_ngan_va_cao(self):
        d = pd.DataFrame({"distance_2d_m": [300.0, 300.0, 500.0, 500.0],
                          "altitude_m": [100.0, 25.0, 100.0, 25.0]})
        assert int(ph1_rang_buoc_hon(d)["n_ngan_va_bay_cao"].iloc[0]) == 1


class TestGiaoThuc:
    def test_du_bon_do_nhay_bat_buoc(self, protocol):
        s = [x["id"] for x in protocol["mandatory_sensitivity_runs"]]
        assert s == ["S-1", "S-2", "S-3", "S-4"]

    def test_duong_danh_doi_quet_hai_truc(self, protocol):
        """
        Muc 7: "trade-off curve over reserve factors AND fixed-SoC thresholds."
        Thieu mot truc la thieu mot nua yeu cau.
        """
        cfg = protocol["metrics"]["tradeoff_curve"]
        assert cfg["required"] is True
        assert len(cfg["reserve_sweep"]) >= 3
        assert cfg["soc_threshold_sweep"] == [0.20, 0.30, 0.40]

    def test_thuoc_do_chinh_la_infeasible_recall(self, protocol):
        assert protocol["metrics"]["primary"] == "infeasible_scenario_recall"

    def test_muc_tieu_m7_la_0(self, protocol):
        m7 = next(m for m in protocol["metrics"]["required"] if m["id"] == "M-7")
        assert m7["target"] == 0

    def test_c23_bat_bao_ca_hai_cau_hinh(self, protocol):
        """
        M-7 bang 0 o bang chinh la THEO THIET KE. Khong bao bang thu hai thi
        "0 vi pham" doc nhu mot ket qua trong khi no la mot hang so.
        """
        cfg = protocol["baselines"]["hard_rule_policy"]
        assert cfg["secondary_run_required"]
        assert "M-7" in cfg["secondary_run_required"]


class TestPhatHienCauTruc:
    """
    Quyet dinh C26 — hai con so khong duoc bao nhu no hien ra.

    Day la loai loi nguy hiem nhat con lai o san pham D4: mot ket qua TRONG
    nhu bang chung nhung thuc ra la he qua cua cach dung so. Khong test duoc
    bang cach chay — phai kiem thang quan he dai so.
    """

    def test_phat_hien_quan_he_a_b(self, protocol):
        """
        Khi (1+r)*a >= b thi moi kich ban nhan goi la kha thi deu tu dong vuot
        nguong FLY, nen M-4 = 0 la TAT YEU.

        Test nay khong khoa mot GIA TRI ma khoa viec quan he do duoc PHAT HIEN
        va GHI RA. Neu sau nay a hoac b doi thi ket luan co the lat, va bang
        d4_structural_relation.csv phai noi dung chieu moi.
        """
        q = quan_he_cau_truc(protocol).iloc[0]
        a = float(q["a_khoan_du_phong_nhan_Wh"])
        b = float(q["b_khoan_bat_dinh_he_thong_Wh"])
        r = float(q["r"])
        # Bang lam tron 4 chu so thap phan khi ghi ra CSV — so voi gia tri da
        # lam tron, khong so voi gia tri tho.
        assert float(q["(1+r)*a"]) == pytest.approx(round((1 + r) * a, 4))
        assert bool(q["M4_bang_0_la_tat_yeu"]) == ((1 + r) * a >= b)
        assert float(q["bien_cua_bat_dang_thuc_Wh"]) == pytest.approx(
            round((1 + r) * a - b, 4))

    def test_voi_con_so_hien_tai_thi_m4_bang_0_la_tat_yeu(self, protocol):
        """
        Chot lai tinh huong DANG co: a = 1.2924, b = 1.4687, r = 0.20.
        (1+r)*a = 1.5509 > 1.4687 nen quan he dung.
        """
        q = quan_he_cau_truc(protocol).iloc[0]
        # pandas tra np.bool_ chu khong phai bool cua Python, nen `is True`
        # luon sai. Ep kieu truoc khi so.
        assert bool(q["M4_bang_0_la_tat_yeu"]) is True
        assert float(q["bien_cua_bat_dang_thuc_Wh"]) > 0

    def test_giao_thuc_bat_neu_hai_cau_trong_bai(self, protocol):
        ids = [d["id"] for c in protocol["change_log"]
               for d in c.get("decisions", [])]
        assert "C26" in ids
        c26 = next(d for c in protocol["change_log"]
                   for d in c.get("decisions", []) if d["id"] == "C26")
        assert "must_state_in_paper" in c26
        assert "khong_duoc_sua_bang_cach" in c26

    def test_cam_chinh_a_b_r_sau_khi_thay_ket_qua(self, protocol):
        """
        Cach sua SAI va hap dan nhat o day la chinh a hoac b cho M-4 "co y
        nghia hon". Giao thuc phai cam thang.
        """
        c26 = next(d for c in protocol["change_log"]
                   for d in c.get("decisions", []) if d["id"] == "C26")
        assert "CAM chinh" in c26["khong_duoc_sua_bang_cach"]


class TestTachNguyenNhan:
    """
    Bang tach tu choi cua B5 theo nguyen nhan. Khong co no thi con so M-4 cua
    B5 chac chan bi doc nham thanh "tu choi thua 72 %".
    """

    def test_tach_du_ba_tap(self):
        d = _bang([FEASIBLE, INFEASIBLE, FEASIBLE], [NO_FLY] * 3)
        b = tu_choi_theo_nguyen_nhan(d)
        assert set(b["tap"]) == {"tat_ca", "dap_an_kha_thi",
                                 "dap_an_khong_kha_thi"}

    def test_ty_le_cong_lai_bang_1_trong_tung_tap(self):
        d = _bang([FEASIBLE] * 3 + [INFEASIBLE] * 2, [FLY, NO_FLY] * 2 + [FLY])
        b = tu_choi_theo_nguyen_nhan(d)
        for tap in b["tap"].unique():
            assert b[b["tap"] == tap]["ty_le_trong_tap"].sum() == pytest.approx(1.0)

    def test_phan_biet_hai_nguon_cua_conditional(self):
        """
        CONDITIONAL co HAI nguon va chung noi hai chuyen khac han:
          - nam trong bang bat dinh cua mo hinh
          - bi ha bac vi ngoai suy (PD-1/PD-2)
        Gop chung lai la xoa mat phat hien thu hai cua C26.
        """
        from src.baselines_decision import LD_BANG_BAT_DINH, LD_NGOAI_SUY
        assert LD_BANG_BAT_DINH != LD_NGOAI_SUY
